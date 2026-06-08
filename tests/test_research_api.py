"""POST /research tests (plan 3.1). Validation is DB-free; the happy path is DB-gated and
stubs the runner so the endpoint contract is exercised without invoking real LLM agents."""

import os

import pytest
from fastapi.testclient import TestClient

from app.main import app

requires_db = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="set RUN_DB_TESTS=1 with a running Postgres",
)


def test_empty_question_is_rejected():
    # Validation fires before the handler body, so no DB/checkpointer is touched.
    client = TestClient(app)
    resp = client.post("/research", json={"question": ""})
    assert resp.status_code == 422


@requires_db
def test_start_research_returns_id_and_creates_session(monkeypatch):
    # Stub the runner so the background task doesn't run the real graph.
    import app.api.research as research

    async def _stub_run(*args, **kwargs):
        return None

    monkeypatch.setattr(research, "run_research", _stub_run)

    from app.db.models import ResearchSession
    from app.db.session import SessionLocal

    # Context-manager use triggers the lifespan -> opens the checkpointer on app.state.
    with TestClient(app) as client:
        resp = client.post("/research", json={"question": "What is RAG?"})

    assert resp.status_code == 202
    session_id = resp.json()["session_id"]
    assert isinstance(session_id, int)

    with SessionLocal() as db:
        session = db.get(ResearchSession, session_id)
        assert session is not None
        assert session.question == "What is RAG?"
        assert session.status == "planning"


@requires_db
def test_get_research_missing_returns_404():
    client = TestClient(app)
    assert client.get("/research/999999").status_code == 404


@requires_db
def test_get_research_before_and_after_completion():
    from app.db.models import Report, ResearchSession
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        session = ResearchSession(question="Q", status="researching")
        db.add(session)
        db.commit()
        session_id = session.id

    client = TestClient(app)

    # Before completion: non-done status, no report.
    body = client.get(f"/research/{session_id}").json()
    assert body["status"] == "researching"
    assert body["report_md"] is None
    assert body["citations_valid"] is None

    # Complete it (mark done + attach a report + a low-confidence flag).
    with SessionLocal() as db:
        session = db.get(ResearchSession, session_id)
        session.status = "done"
        session.low_confidence = True
        db.add(
            Report(session_id=session_id, report_md="# Report", citations_valid=True)
        )
        db.commit()

    body = client.get(f"/research/{session_id}").json()
    assert body["status"] == "done"
    assert body["report_md"] == "# Report"
    assert body["citations_valid"] is True
    assert body["low_confidence"] is True


@requires_db
def test_get_evidence_returns_web_and_rag_items():
    from app.db.models import Chunk, Document
    from app.db.models import Evidence as EvidenceRow
    from app.db.models import ResearchSession
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        # A rag evidence item references a real chunk (FK), so seed a document + chunk.
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
        session_id = session.id
        db.add(
            EvidenceRow(
                session_id=session_id,
                content="web fact",
                source_url="https://example.com",
                retriever="web",
            )
        )
        db.add(
            EvidenceRow(
                session_id=session_id,
                content="doc fact",
                source_chunk_id=chunk_id,
                retriever="rag",
            )
        )
        db.commit()

    client = TestClient(app)
    items = client.get(f"/research/{session_id}/evidence").json()
    assert len(items) == 2
    web = next(i for i in items if i["retriever"] == "web")
    assert web["source_url"] == "https://example.com"
    rag = next(i for i in items if i["retriever"] == "rag")
    assert rag["source_chunk_id"] == chunk_id
