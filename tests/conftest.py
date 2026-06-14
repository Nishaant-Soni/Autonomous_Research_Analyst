"""Shared test fixtures.

DB-backed tests are gated behind RUN_DB_TESTS=1 (they need a running Postgres with
pgvector). When enabled, the schema is applied once per session and every test starts
from clean tables for isolation.
"""

import os

import pytest

_DB = os.environ.get("RUN_DB_TESTS") == "1"


@pytest.fixture(scope="session", autouse=True)
def _ensure_schema():
    if _DB:
        from app.db.init_db import apply_schema

        apply_schema()
    yield


@pytest.fixture(autouse=True)
def _clean_db():
    if _DB:
        from app.db.session import engine

        with engine.begin() as conn:
            conn.exec_driver_sql(
                "TRUNCATE users, refresh_tokens, documents, chunks, "
                "research_sessions, evidence, reports RESTART IDENTITY CASCADE"
            )
    yield
