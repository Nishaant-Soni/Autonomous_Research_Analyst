import os

import pytest

# Needs both Postgres AND the real embedding model. Kept out of CI: HF rate-limits
# shared CI runner IPs (HTTP 429), so model downloads there are unreliable. Covered
# locally (cached model) and in the Docker image (baked model).
requires_db_and_model = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1" or os.environ.get("RUN_MODEL_TESTS") != "1",
    reason="set RUN_DB_TESTS=1 and RUN_MODEL_TESTS=1 (needs Postgres + embedding model)",
)


@requires_db_and_model
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


# No DB or model needed: empty text is rejected by pydantic (422) before any work.
def test_ingest_rejects_empty_text(override_auth):
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.post("/documents", json={"raw_text": ""})
    assert resp.status_code == 422  # pydantic min_length validation
