"""Offline end-to-end run (the Phase 2 milestone, now on the shared runner of plan 3.1/3.2).

Takes a question, creates a session, runs the research graph against Postgres (with the
checkpointer), and prints the cited report. The run/persist logic lives in
`app.graph.runner.run_research` so this script and the async API share one code path.

Usage (from the repo root, with Postgres up and OPENAI/TAVILY keys in `.env`):

    python -m scripts.run_once "What are the benefits of on-device LLM inference?"
"""

import asyncio
import sys

from app.db.init_db import checkpointer_cm, init_db
from app.db.models import ResearchSession
from app.db.session import SessionLocal
from app.graph.runner import run_research
from app.observability import configure_langsmith


async def run_once(question: str) -> dict | None:
    configure_langsmith()  # enable tracing if a LANGSMITH_API_KEY is set (3.7); else a no-op
    # Open a session row up front so the run has a stable id (used as the graph thread_id).
    with SessionLocal() as db:
        session = ResearchSession(question=question, status="planning")
        db.add(session)
        db.commit()
        session_id = session.id

    # The script owns the checkpointer + init_db (the API's lifespan does this instead).
    async with checkpointer_cm() as checkpointer:
        await init_db(checkpointer)
        return await run_research(session_id, question, checkpointer)


def main() -> None:
    question = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "What are the benefits of on-device LLM inference?"
    )
    final = asyncio.run(run_once(question))
    if final is None:
        print("Run failed — see the session row's status/error.")
        return
    print(final["report_md"])
    print(
        f"\n[citations_valid={final['citations_valid']} "
        f"low_confidence={final['low_confidence']} evidence={len(final['evidence'])}]"
    )


if __name__ == "__main__":
    main()
