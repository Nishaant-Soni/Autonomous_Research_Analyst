"""Shared test fixtures.

DB-backed tests are gated behind RUN_DB_TESTS=1 (they need a running Postgres with
pgvector). When enabled, the schema is applied once per session and every test starts
from clean tables for isolation.
"""

import os
from unittest.mock import MagicMock

import pytest

# Fake user id used by override_auth and DB seed data that must match it.
FAKE_USER_ID = 1

_DB = os.environ.get("RUN_DB_TESTS") == "1"


@pytest.fixture
def override_auth():
    """Override get_current_user to return a fake user (id=FAKE_USER_ID).

    Use in tests that exercise endpoints requiring auth but don't need real token/DB auth.
    Seed any DB rows that must be visible to this user with user_id=FAKE_USER_ID.
    """
    from app.auth.dependencies import get_current_user
    from app.main import app

    fake = MagicMock()
    fake.id = FAKE_USER_ID
    app.dependency_overrides[get_current_user] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_current_user, None)


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
