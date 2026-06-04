import os

import pytest

requires_db = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="set RUN_DB_TESTS=1 with a running Postgres (e.g. docker compose up db)",
)


@requires_db
def test_rag_retrieve_ranks_relevant_chunk_first():
    from fastapi.testclient import TestClient

    from app.main import app
    from app.retrieval.rag import rag_retrieve

    client = TestClient(app)
    client.post(
        "/documents",
        json={
            "raw_text": "Paris is the capital of France. The Louvre museum is in Paris.",
            "title": "france",
        },
    )
    client.post(
        "/documents",
        json={
            "raw_text": "Python is a programming language created by Guido van Rossum.",
            "title": "python",
        },
    )

    results = rag_retrieve("What is the capital of France?", k=3)

    assert results
    top = results[0]
    assert top.retriever == "rag"
    assert top.source_chunk_id is not None
    assert "France" in top.content or "Paris" in top.content
