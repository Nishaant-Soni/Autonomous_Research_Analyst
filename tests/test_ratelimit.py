"""Tests for API rate limiting (slowapi wiring + key function).

The key-function tests are pure logic (no DB/network). The 429 integration test is gated on
RUN_DB_TESTS because the only limited unauthenticated endpoint (`/auth/register`) hits the DB.
"""

import os

import pytest
from starlette.requests import Request

from app.api import ratelimit

_DB = os.environ.get("RUN_DB_TESTS") == "1"


def _request_with(cookie: str | None = None, client_ip: str = "203.0.113.7") -> Request:
    """Build a minimal Starlette Request with an optional Cookie header + a client IP."""
    headers = []
    if cookie is not None:
        headers.append((b"cookie", cookie.encode()))
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "path": "/",
            "headers": headers,
            "client": (client_ip, 12345),
        }
    )


# --- key function -----------------------------------------------------------


def test_key_falls_back_to_ip_without_cookie():
    assert ratelimit._user_or_ip(_request_with()) == "ip:203.0.113.7"


def test_key_falls_back_to_ip_on_invalid_token():
    req = _request_with(cookie="access_token=not-a-real-jwt")
    assert ratelimit._user_or_ip(req) == "ip:203.0.113.7"


def test_key_uses_user_id_for_valid_access_token(monkeypatch):
    monkeypatch.setattr(ratelimit.settings, "jwt_secret", "test-secret-ratelimit")
    monkeypatch.setattr("app.auth.utils.settings.jwt_secret", "test-secret-ratelimit")
    from app.auth.utils import create_access_token

    token = create_access_token(42)
    req = _request_with(cookie=f"access_token={token}")
    assert ratelimit._user_or_ip(req) == "user:42"


def test_key_ignores_refresh_token_typ(monkeypatch):
    # A refresh token in the access_token slot must NOT be honored as a user identity.
    monkeypatch.setattr(ratelimit.settings, "jwt_secret", "test-secret-ratelimit")
    monkeypatch.setattr("app.auth.utils.settings.jwt_secret", "test-secret-ratelimit")
    from app.auth.utils import create_refresh_token

    refresh, _, _ = create_refresh_token(42)
    req = _request_with(cookie=f"access_token={refresh}")
    assert ratelimit._user_or_ip(req) == "ip:203.0.113.7"


# --- end-to-end 429 ---------------------------------------------------------


@pytest.mark.skipif(not _DB, reason="requires RUN_DB_TESTS=1 (register hits the DB)")
def test_register_returns_429_past_the_limit(monkeypatch):
    """The 6th register in a window trips AUTH_REGISTER_LIMIT (5/minute) → 429."""
    import app.config as cfg_mod
    from app.api.ratelimit import limiter
    from app.main import app

    monkeypatch.setattr(cfg_mod.settings, "jwt_secret", "test-secret-ratelimit")
    monkeypatch.setattr(cfg_mod.settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(cfg_mod.settings, "tavily_api_key", "tvly-test")

    # The autouse conftest fixture disabled the limiter; turn it back on for this test only,
    # with a clean storage, and restore disabled state on the way out.
    limiter.reset()
    limiter.enabled = True

    from fastapi.testclient import TestClient

    try:
        with TestClient(app) as client:
            statuses = [
                client.post(
                    "/auth/register",
                    json={"email": f"rl{i}@test.com", "password": "pw"},
                ).status_code
                for i in range(6)
            ]
    finally:
        limiter.reset()
        limiter.enabled = False

    assert statuses[:5] == [201, 201, 201, 201, 201]
    assert statuses[5] == 429
