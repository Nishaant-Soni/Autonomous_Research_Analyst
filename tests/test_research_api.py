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
