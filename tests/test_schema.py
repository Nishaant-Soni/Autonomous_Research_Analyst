import os

import pytest

requires_db = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="set RUN_DB_TESTS=1 with a running Postgres (e.g. docker compose up db)",
)


@requires_db
def test_schema_applies_and_is_idempotent():
    from sqlalchemy import inspect

    from app.db.init_db import apply_schema
    from app.db.session import engine

    apply_schema()
    apply_schema()  # second run must be a no-op (idempotent DDL)

    insp = inspect(engine)
    tables = set(insp.get_table_names())
    assert {"documents", "chunks", "research_sessions", "evidence", "reports"} <= tables

    cols = {c["name"] for c in insp.get_columns("chunks")}
    assert "embedding" in cols

    index_names = {i["name"] for i in insp.get_indexes("chunks")}
    assert "chunks_embedding_hnsw" in index_names
