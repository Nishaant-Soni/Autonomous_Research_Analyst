import os

import pytest

requires_db = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="set RUN_DB_TESTS=1 with a running Postgres (e.g. docker compose up db)",
)


@requires_db
def test_ingest_document_creates_doc_and_chunks():
    from fastapi.testclient import TestClient

    from app.db.models import Chunk, Document
    from app.db.session import SessionLocal
    from app.main import app

    client = TestClient(app)
    # long enough that chunking produces more than one chunk
    text = "Paris is the capital of France. " * 200
    resp = client.post("/documents", json={"raw_text": text, "title": "geo"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["chunks"] >= 2

    with SessionLocal() as db:
        assert db.query(Document).count() == 1
        chunks = (
            db.query(Chunk)
            .filter(Chunk.document_id == body["document_id"])
            .order_by(Chunk.chunk_index)
            .all()
        )
        assert len(chunks) == body["chunks"]
        # chunk indices are contiguous from 0
        assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
        # every chunk has a non-null 384-dim embedding
        for c in chunks:
            assert c.embedding is not None
            assert len(c.embedding) == 384


@requires_db
def test_ingest_rejects_empty_text():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.post("/documents", json={"raw_text": ""})
    assert resp.status_code == 422  # pydantic min_length validation
