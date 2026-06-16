"""Shared async graph runner (plan 3.1/3.2, consolidating Phase 2's run_once).

Drives one research run for an already-created session: streams the graph, updates the
session status as each node starts, optionally pushes per-node progress onto a
caller-supplied queue, and persists the final evidence/report on success (or records
`failed` + the error on exception).

The session row and the checkpointer's lifetime are the **caller's** responsibility (the
API lifespan / `run_once` own them) — this never creates the session or calls `init_db`.
"""

import logging
from datetime import datetime, timezone

from app.config import settings
from app.db.models import Evidence as EvidenceRow
from app.db.models import Report, ResearchSession
from app.db.session import SessionLocal
from app.graph.build import build_graph

logger = logging.getLogger(__name__)

# Strong refs so background scoring tasks aren't GC'd mid-run.
_scoring_tasks: set = set()

# Graph node name (build.py) -> session status (PRD §9). We drive status off
# `astream_events` `on_chain_start`, which fires when a node *begins*, so the status names the
# *currently-running* stage: planning -> researching -> critiquing -> writing -> validating ->
# done, and the critic loop-back correctly re-shows researching/critiquing on each pass
# (verified empirically against langgraph 0.6.x). The same events feed the SSE stream (3.5).
_NODE_STATUS = {
    "planner": "planning",
    "researcher": "researching",
    "critic": "critiquing",
    "writer": "writing",
    "validator": "validating",
}


def build_initial_state(
    session_id: str,
    question: str,
    max_iterations: int | None = None,
    user_id: int | None = None,
) -> dict:
    """Initial `ResearchState` for a new run. Public so the eval harness can build the same
    state without going through `run_research` (which writes a DB session row).

    `max_iterations` overrides `settings.max_iterations` per call — set to `0` to disable
    the critic loop-back (the critic node still runs but the conditional edge never
    routes back to the researcher). Used by the C2 critic-loop A/B (plan 4.7).

    `user_id` scopes RAG retrieval to that user's documents; None means no filter (eval/anon)."""
    return {
        "session_id": session_id,
        "question": question,
        "plan": [],
        "evidence": [],
        "draft_findings": "",
        "critique": None,
        "iteration": 0,
        "max_iterations": (
            max_iterations if max_iterations is not None else settings.max_iterations
        ),
        "report_md": "",
        "citations_valid": False,
        "low_confidence": False,
        "stripped_fraction": 0.0,
        "user_id": user_id,
    }


def _update_session(session_id, **fields) -> None:
    """A short synchronous UPDATE. The runner is async but the DB layer is sync; these are
    tiny single-row writes, so we accept the brief event-loop block at v1 scale rather than
    pull in async SQLAlchemy / a threadpool (the multi-worker scale path)."""
    with SessionLocal() as db:
        session = db.get(ResearchSession, session_id)
        for key, value in fields.items():
            setattr(session, key, value)
        db.commit()


def _persist_result(session_id, final: dict) -> None:
    """On success: write the evidence + report rows and close the session out as `done`,
    carrying the citation validator's low_confidence/stripped_fraction signal onto the row."""
    with SessionLocal() as db:
        for ev in final["evidence"]:
            db.add(
                EvidenceRow(
                    session_id=session_id,
                    claim=ev.claim,
                    content=ev.content,
                    source_url=ev.source_url,
                    source_chunk_id=ev.source_chunk_id,
                    retriever=ev.retriever,
                )
            )
        db.add(
            Report(
                session_id=session_id,
                report_md=final["report_md"],
                citations_valid=final["citations_valid"],
            )
        )
        session = db.get(ResearchSession, session_id)
        session.status = "done"
        session.completed_at = datetime.now(timezone.utc)
        session.plan = final["plan"]
        session.low_confidence = final["low_confidence"]
        session.stripped_fraction = final["stripped_fraction"]
        db.commit()


def _emit(queue, item) -> None:
    if queue is not None:
        queue.put_nowait(item)


def _schedule_scoring(
    session_id: int, question: str, evidence: list, report_md: str
) -> None:
    """Fire a background asyncio task that runs the Ragas scorer in a threadpool.

    Called right after _persist_result so the run is already marked 'done' before
    scoring starts. Scoring failure never affects the run — it's caught inside score_run.
    """
    import asyncio

    from app.scoring.ragas import score_run

    async def _run() -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, score_run, session_id, question, report_md, evidence
        )

    task = asyncio.create_task(_run())
    _scoring_tasks.add(task)
    task.add_done_callback(_scoring_tasks.discard)


async def run_research(
    session_id, question, checkpointer, queue=None, user_id: int | None = None
) -> dict | None:
    """Run the graph for an already-created session. Returns the final state, or `None` on
    failure — the failure is recorded on the session row (status `failed` + error), not
    raised, because this runs as a fire-and-forget task."""
    graph = build_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": str(session_id)}}
    try:
        async for ev in graph.astream_events(
            build_initial_state(str(session_id), question, user_id=user_id),
            config,
            version="v2",
        ):
            if ev["event"] == "on_chain_start":
                status = _NODE_STATUS.get(ev.get("name"))
                if status:
                    _update_session(session_id, status=status)
                    _emit(queue, {"node": ev["name"], "status": status})
        final = (await graph.aget_state(config)).values
        try:
            _persist_result(session_id, final)
        except Exception as persist_exc:
            # Transient DB error — the transaction fully rolled back so retrying is safe.
            logger.warning(
                "persist failed for session %s, retrying once: %s",
                session_id,
                persist_exc,
            )
            _persist_result(
                session_id, final
            )  # propagates to outer handler if it fails again
        # _schedule_scoring(session_id, question, final["evidence"], final["report_md"])
        _emit(queue, {"status": "done"})
        return final
    except Exception as exc:
        logger.exception("research run %s failed", session_id)
        _update_session(session_id, status="failed", error=str(exc))
        _emit(queue, {"status": "failed", "error": str(exc)})
        return None
    finally:
        _emit(
            queue, None
        )  # sentinel: stream closed (the SSE endpoint drains until this)
