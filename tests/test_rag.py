import os

import pytest

# Needs both Postgres AND the real embedding model — kept out of CI (HF 429 on shared
# runner IPs). Covered locally with the cached model.
requires_db_and_model = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1" or os.environ.get("RUN_MODEL_TESTS") != "1",
    reason="set RUN_DB_TESTS=1 and RUN_MODEL_TESTS=1 (needs Postgres + embedding model)",
)


@requires_db_and_model
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
