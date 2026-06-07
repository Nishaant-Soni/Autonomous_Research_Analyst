import asyncio
import os
import uuid

import pytest

from app.graph import build
from app.graph.state import Critique

requires_db = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="set RUN_DB_TESTS=1 with a running Postgres",
)


def _initial(thread_id):
    return {
        "session_id": thread_id,
        "question": "Q",
        "plan": [],
        "evidence": [],
        "draft_findings": "",
        "critique": None,
        "iteration": 0,
        "max_iterations": 2,
        "report_md": "",
        "citations_valid": False,
        "low_confidence": False,
        "stripped_fraction": 0.0,
    }


@requires_db
def test_checkpointer_is_idempotent_and_persists_a_run(monkeypatch):
    # Stub the nodes so this exercises the checkpointer + init_db only — no LLM needed.
    monkeypatch.setattr(build, "planner_node", lambda s: {"plan": ["q1"]})
    monkeypatch.setattr(
        build, "researcher_node", lambda s: {"evidence": [], "draft_findings": "d"}
    )
    monkeypatch.setattr(
        build,
        "critic_node",
        lambda s: {
            "critique": Critique(groundedness=0.9, needs_more_research=False, gaps=[])
        },
    )
    monkeypatch.setattr(build, "writer_node", lambda s: {"report_md": "report"})
    monkeypatch.setattr(
        build,
        "citation_validator_node",
        lambda s: {
            "citations_valid": True,
            "low_confidence": False,
            "stripped_fraction": 0.0,
        },
    )

    from app.db.init_db import checkpointer_cm, init_db

    thread_id = f"test-{uuid.uuid4()}"

    async def _body():
        async with checkpointer_cm() as checkpointer:
            await init_db(checkpointer)
            await init_db(checkpointer)  # idempotent: a second call must not error
            graph = build.build_graph(checkpointer=checkpointer)
            config = {"configurable": {"thread_id": thread_id}}
            out = await graph.ainvoke(_initial(thread_id), config)
            assert out["citations_valid"] is True
            # a checkpoint row exists for this thread, and is re-readable (resumable)
            tup = await checkpointer.aget_tuple(config)
            assert tup is not None
            assert tup.config["configurable"]["thread_id"] == thread_id

    asyncio.run(_body())
