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


def test_empty_question_is_rejected(override_auth):
    # Validation fires before the handler body, so no DB/checkpointer is touched.
    client = TestClient(app)
    resp = client.post("/research", json={"question": ""})
    assert resp.status_code == 422


def test_list_research_clamps_limit_at_validation_layer(override_auth):
    """Validation: limit > max returns 422 (Pydantic Query constraint) — no DB needed.
    Belongs alongside the empty-question test as a pure schema check."""
    client = TestClient(app)
    resp = client.get("/research", params={"limit": 1000})
    assert resp.status_code == 422


def test_list_research_rejects_zero_or_negative_limit(override_auth):
    client = TestClient(app)
    assert client.get("/research", params={"limit": 0}).status_code == 422
    assert client.get("/research", params={"limit": -5}).status_code == 422


@requires_db
def test_stream_drains_queue_events(override_auth):
    from app.api.progress import create_queue, remove_queue
    from app.db.models import ResearchSession
    from app.db.session import SessionLocal
    from tests.conftest import FAKE_USER_ID

    with SessionLocal() as db:
        session = ResearchSession(question="Q", status="planning", user_id=FAKE_USER_ID)
        db.add(session)
        db.commit()
        session_id = session.id

    queue = create_queue(session_id)
    queue.put_nowait({"node": "planner", "status": "planning"})
    queue.put_nowait({"status": "done"})
    queue.put_nowait(None)  # sentinel

    client = TestClient(app)
    resp = client.get(f"/research/{session_id}/stream")
    remove_queue(session_id)

    assert resp.status_code == 200
    assert '"node": "planner"' in resp.text
    assert '"status": "done"' in resp.text


@requires_db
def test_start_research_returns_id_and_creates_session(monkeypatch, override_auth):
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
def test_get_research_missing_returns_404(override_auth):
    client = TestClient(app)
    assert client.get("/research/999999").status_code == 404


@requires_db
def test_get_research_before_and_after_completion(override_auth):
    from app.db.models import Report, ResearchSession
    from app.db.session import SessionLocal
    from tests.conftest import FAKE_USER_ID

    with SessionLocal() as db:
        session = ResearchSession(
            question="Q", status="researching", user_id=FAKE_USER_ID
        )
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
def test_get_evidence_returns_web_and_rag_items(override_auth):
    from app.db.models import Chunk, Document
    from app.db.models import Evidence as EvidenceRow
    from app.db.models import ResearchSession
    from app.db.session import SessionLocal
    from tests.conftest import FAKE_USER_ID

    with SessionLocal() as db:
        # A rag evidence item references a real chunk (FK), so seed a document + chunk.
        doc = Document(raw_text="t")
        db.add(doc)
        db.flush()
        chunk = Chunk(document_id=doc.id, chunk_index=0, content="c")
        db.add(chunk)
        db.flush()
        chunk_id = chunk.id

        session = ResearchSession(question="Q", status="done", user_id=FAKE_USER_ID)
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


@requires_db
def test_list_research_returns_recent_first_with_summary_shape(override_auth):
    """Plan 5.7: the sidebar query. Three sessions inserted in order; the list returns them
    newest-first, with the slim summary shape (no report_md / citations_valid)."""
    from app.db.models import ResearchSession
    from app.db.session import SessionLocal
    from tests.conftest import FAKE_USER_ID

    with SessionLocal() as db:
        for q, status in [
            ("first question", "done"),
            ("second question", "researching"),
            ("third question", "planning"),
        ]:
            db.add(ResearchSession(question=q, status=status, user_id=FAKE_USER_ID))
        db.commit()

    client = TestClient(app)
    rows = client.get("/research").json()

    assert [r["question"] for r in rows] == [
        "third question",
        "second question",
        "first question",
    ]
    # Summary shape only — confirm report_md / citations_valid are NOT leaking from this
    # endpoint (those live on the detail endpoint).
    keys = set(rows[0].keys())
    assert {"session_id", "question", "status", "low_confidence", "created_at"} <= keys
    assert "report_md" not in keys
    assert "citations_valid" not in keys


@requires_db
def test_list_research_honors_explicit_limit(override_auth):
    from app.db.models import ResearchSession
    from app.db.session import SessionLocal
    from tests.conftest import FAKE_USER_ID

    with SessionLocal() as db:
        for i in range(5):
            db.add(
                ResearchSession(question=f"q{i}", status="done", user_id=FAKE_USER_ID)
            )
        db.commit()

    client = TestClient(app)
    rows = client.get("/research", params={"limit": 2}).json()

    assert len(rows) == 2
    assert [r["question"] for r in rows] == ["q4", "q3"]  # newest two


@requires_db
def test_list_research_empty_set_returns_empty_list(override_auth):
    client = TestClient(app)
    resp = client.get("/research")
    assert resp.status_code == 200
    assert resp.json() == []


@requires_db
def test_stream_falls_back_to_status_when_no_queue(override_auth):
    from app.db.models import ResearchSession
    from app.db.session import SessionLocal
    from tests.conftest import FAKE_USER_ID

    with SessionLocal() as db:
        session = ResearchSession(question="Q", status="done", user_id=FAKE_USER_ID)
        db.add(session)
        db.commit()
        session_id = session.id

    client = TestClient(app)
    resp = client.get(f"/research/{session_id}/stream")
    assert resp.status_code == 200
    assert '"status": "done"' in resp.text


@requires_db
def test_stream_missing_session_returns_404(override_auth):
    client = TestClient(app)
    assert client.get("/research/999999/stream").status_code == 404
