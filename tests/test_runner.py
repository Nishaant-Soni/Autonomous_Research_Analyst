"""Shared runner tests (plan 3.1/3.2): status lifecycle, final persist, clean failure,
and progress-queue events. DB-gated (real checkpointer + Postgres); the graph nodes are
stubbed so no LLM is needed."""

import asyncio
import os

import pytest

from app.graph import build
from app.graph.state import Critique

requires_db = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="set RUN_DB_TESTS=1 with a running Postgres",
)


def _stub_nodes(monkeypatch):
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


def _new_session(question="Q"):
    from app.db.models import ResearchSession
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        session = ResearchSession(question=question, status="planning")
        db.add(session)
        db.commit()
        return session.id


def _drain(queue):
    items = []
    while not queue.empty():
        items.append(queue.get_nowait())
    return items


@requires_db
def test_run_research_drives_status_persists_and_emits(monkeypatch):
    _stub_nodes(monkeypatch)
    from app.db.init_db import checkpointer_cm, init_db
    from app.db.models import Report, ResearchSession
    from app.db.session import SessionLocal
    from app.graph.runner import run_research

    session_id = _new_session()
    queue: asyncio.Queue = asyncio.Queue()

    async def _body():
        async with checkpointer_cm() as checkpointer:
            await init_db(checkpointer)
            final = await run_research(session_id, "Q", checkpointer, queue=queue)
            assert final is not None
            assert final["citations_valid"] is True

    asyncio.run(_body())

    # Session closed out as done, with the low-confidence signal persisted.
    with SessionLocal() as db:
        session = db.get(ResearchSession, session_id)
        assert session.status == "done"
        assert session.completed_at is not None
        assert session.plan == ["q1"]
        assert session.low_confidence is False
        assert session.stripped_fraction == 0.0
        report = db.query(Report).filter_by(session_id=session_id).one()
        assert report.report_md == "report"
        assert report.citations_valid is True

    # Progress queue: per-node events, a terminal done, then the None sentinel last.
    items = _drain(queue)
    assert {"node": "planner", "status": "planning"} in items
    assert {"node": "validator", "status": "validating"} in items
    assert {"status": "done"} in items
    assert items[-1] is None


@requires_db
def test_run_research_records_failure(monkeypatch):
    _stub_nodes(monkeypatch)

    def _boom(state):
        raise RuntimeError("boom")

    monkeypatch.setattr(build, "critic_node", _boom)

    from app.db.init_db import checkpointer_cm, init_db
    from app.db.models import ResearchSession
    from app.db.session import SessionLocal
    from app.graph.runner import run_research

    session_id = _new_session()
    queue: asyncio.Queue = asyncio.Queue()

    async def _body():
        async with checkpointer_cm() as checkpointer:
            await init_db(checkpointer)
            result = await run_research(session_id, "Q", checkpointer, queue=queue)
            assert result is None  # failure is recorded, not raised

    asyncio.run(_body())

    with SessionLocal() as db:
        session = db.get(ResearchSession, session_id)
        assert session.status == "failed"
        assert "boom" in (session.error or "")

    items = _drain(queue)
    assert any(it and it.get("status") == "failed" for it in items)
    assert items[-1] is None
