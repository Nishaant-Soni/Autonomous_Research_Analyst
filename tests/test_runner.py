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
def test_persist_nulls_dangling_chunk_reference():
    """A source_chunk_id with no chunk row must not FK-fail the whole persist (the bug we hit
    on a stale checkpoint) — it degrades to an unlinked row; valid references are kept."""
    from app.db.models import Chunk, Document
    from app.db.models import Evidence as EvidenceRow
    from app.db.models import ResearchSession
    from app.db.session import SessionLocal
    from app.graph.runner import _persist_result
    from app.models.evidence import Evidence

    with SessionLocal() as db:
        doc = Document(raw_text="t")
        db.add(doc)
        db.flush()
        chunk = Chunk(document_id=doc.id, chunk_index=0, content="c")
        db.add(chunk)
        db.flush()
        valid_chunk_id = chunk.id
        session = ResearchSession(question="Q", status="validating")
        db.add(session)
        db.commit()
        session_id = session.id

    final = {
        "evidence": [
            Evidence(content="web", source_url="https://e.com", retriever="web"),
            Evidence(content="good rag", source_chunk_id=valid_chunk_id, retriever="rag"),
            Evidence(
                content="dangling rag",
                source_chunk_id=valid_chunk_id + 999,  # no such chunk
                retriever="rag",
            ),
        ],
        "report_md": "# R",
        "citations_valid": True,
        "low_confidence": False,
        "stripped_fraction": 0.0,
        "plan": ["q"],
    }

    _persist_result(session_id, final)  # must NOT raise

    with SessionLocal() as db:
        rows = {
            r.content: r
            for r in db.query(EvidenceRow).filter_by(session_id=session_id).all()
        }
        assert len(rows) == 3
        assert rows["good rag"].source_chunk_id == valid_chunk_id  # valid kept
        assert rows["dangling rag"].source_chunk_id is None  # dangling nulled
        assert rows["dangling rag"].retriever == "rag"  # content/retriever preserved
        assert db.get(ResearchSession, session_id).status == "done"


@requires_db
def test_deleting_chunk_nulls_evidence_reference():
    """ON DELETE SET NULL: deleting a referenced chunk unlinks the evidence row rather than
    being blocked by the FK (or cascading the evidence away)."""
    from app.db.models import Chunk, Document
    from app.db.models import Evidence as EvidenceRow
    from app.db.models import ResearchSession
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        doc = Document(raw_text="t")
        db.add(doc)
        db.flush()
        chunk = Chunk(document_id=doc.id, chunk_index=0, content="c")
        db.add(chunk)
        db.flush()
        chunk_id = chunk.id
        session = ResearchSession(question="Q", status="done")
        db.add(session)
        db.flush()
        ev = EvidenceRow(
            session_id=session.id, content="x", source_chunk_id=chunk_id, retriever="rag"
        )
        db.add(ev)
        db.commit()
        ev_id = ev.id

    with SessionLocal() as db:
        db.delete(db.get(Chunk, chunk_id))
        db.commit()

    with SessionLocal() as db:
        ev = db.get(EvidenceRow, ev_id)
        assert ev is not None  # row survives the chunk deletion
        assert ev.source_chunk_id is None  # reference nulled, not blocked


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
