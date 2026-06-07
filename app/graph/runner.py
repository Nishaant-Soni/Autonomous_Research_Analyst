"""Shared async graph runner (plan 3.1/3.2, consolidating Phase 2's run_once).

Drives one research run for an already-created session: streams the graph, updates the
session status as each node completes, optionally pushes per-node progress onto a
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

# Graph node name (build.py) -> session status (PRD §9). `astream(stream_mode="updates")`
# fires *after* a node runs, so the status names the stage that has just completed; a poller
# sees planning -> researching -> critiquing -> writing -> validating -> done, with the critic
# loop honestly repeating researching/critiquing. Finer per-node events go to the queue (3.5).
_NODE_STATUS = {
    "planner": "planning",
    "researcher": "researching",
    "critic": "critiquing",
    "writer": "writing",
    "validator": "validating",
}


def _initial_state(session_id: str, question: str) -> dict:
    return {
        "session_id": session_id,
        "question": question,
        "plan": [],
        "evidence": [],
        "draft_findings": "",
        "critique": None,
        "iteration": 0,
        "max_iterations": settings.max_iterations,
        "report_md": "",
        "citations_valid": False,
        "low_confidence": False,
        "stripped_fraction": 0.0,
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


async def run_research(session_id, question, checkpointer, queue=None) -> dict | None:
    """Run the graph for an already-created session. Returns the final state, or `None` on
    failure — the failure is recorded on the session row (status `failed` + error), not
    raised, because this runs as a fire-and-forget task."""
    graph = build_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": str(session_id)}}
    try:
        async for event in graph.astream(
            _initial_state(str(session_id), question), config, stream_mode="updates"
        ):
            for node_name in event:
                status = _NODE_STATUS.get(node_name)
                if status:
                    _update_session(session_id, status=status)
                    _emit(queue, {"node": node_name, "status": status})
        final = (await graph.aget_state(config)).values
        _persist_result(session_id, final)
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
