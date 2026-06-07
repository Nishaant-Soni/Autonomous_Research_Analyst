"""First full end-to-end run (plan 2.9, the Phase 2 milestone).

Takes a question, runs the research graph against Postgres (with the checkpointer), persists
the `evidence` and `reports` rows, and prints the cited report.

Usage (from the repo root, with Postgres up and OPENAI/TAVILY keys in `.env`):

    python -m scripts.run_once "What are the benefits of on-device LLM inference?"
"""

import asyncio
import sys
from datetime import datetime, timezone

from app.config import settings
from app.db.init_db import checkpointer_cm, init_db
from app.db.models import Evidence as EvidenceRow
from app.db.models import Report, ResearchSession
from app.db.session import SessionLocal
from app.graph.build import build_graph


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


async def run_once(question: str) -> dict:
    # 1. Open a session row up front so the run has a stable id (used as the graph thread_id).
    with SessionLocal() as db:
        session = ResearchSession(question=question, status="running")
        db.add(session)
        db.commit()
        session_id = session.id
    thread_id = str(session_id)

    # 2. Run the graph, checkpointing to Postgres under thread_id = session_id.
    async with checkpointer_cm() as checkpointer:
        await init_db(checkpointer)
        graph = build_graph(checkpointer=checkpointer)
        final = await graph.ainvoke(
            _initial_state(thread_id, question),
            config={"configurable": {"thread_id": thread_id}},
        )

    # 3. Persist evidence + report and close out the session.
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
        db.commit()

    return final


def main() -> None:
    question = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "What are the benefits of on-device LLM inference?"
    )
    final = asyncio.run(run_once(question))
    print(final["report_md"])
    print(
        f"\n[citations_valid={final['citations_valid']} "
        f"low_confidence={final['low_confidence']} evidence={len(final['evidence'])}]"
    )


if __name__ == "__main__":
    main()
