"""Integration tests for /auth endpoints (plan 6.3). Requires RUN_DB_TESTS=1."""

import os

import pytest

_DB = os.environ.get("RUN_DB_TESTS") == "1"
pytestmark = pytest.mark.skipif(not _DB, reason="requires RUN_DB_TESTS=1")


@pytest.fixture(autouse=True)
def _set_required_settings(monkeypatch):
    import app.auth.utils as utils_mod
    import app.config as cfg_mod

    monkeypatch.setattr(
        cfg_mod.settings, "jwt_secret", "test-secret-for-auth-api-tests"
    )
    monkeypatch.setattr(
        utils_mod.settings, "jwt_secret", "test-secret-for-auth-api-tests"
    )
    monkeypatch.setattr(cfg_mod.settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(cfg_mod.settings, "tavily_api_key", "tvly-test")


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def test_register(client):
    r = client.post("/auth/register", json={"email": "a@test.com", "password": "pw1"})
    assert r.status_code == 201
    data = r.json()
    assert data["email"] == "a@test.com"
    assert "user_id" in data


def test_register_duplicate_email(client):
    client.post("/auth/register", json={"email": "dup@test.com", "password": "pw"})
    r = client.post("/auth/register", json={"email": "dup@test.com", "password": "pw2"})
    assert r.status_code == 409


def test_login_success_sets_cookies(client):
    client.post("/auth/register", json={"email": "b@test.com", "password": "pw2"})
    r = client.post("/auth/login", json={"email": "b@test.com", "password": "pw2"})
    assert r.status_code == 200
    assert "access_token" in r.cookies
    assert "refresh_token" in r.cookies


def test_login_wrong_password(client):
    client.post("/auth/register", json={"email": "c@test.com", "password": "right"})
    r = client.post("/auth/login", json={"email": "c@test.com", "password": "wrong"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid credentials"


def test_login_unknown_email_same_message(client):
    r = client.post("/auth/login", json={"email": "nobody@test.com", "password": "x"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid credentials"


def test_refresh_rotates_tokens(client):
    from app.db.models import RefreshToken
    from app.db.session import SessionLocal

    client.post("/auth/register", json={"email": "d@test.com", "password": "pw"})
    client.post("/auth/login", json={"email": "d@test.com", "password": "pw"})

    old_refresh = client.cookies.get("refresh_token")
    r = client.post("/auth/refresh")
    assert r.status_code == 200

    # Old jti must be marked used in DB.
    import jwt

    payload = jwt.decode(old_refresh, options={"verify_signature": False})
    old_jti = payload["jti"]
    with SessionLocal() as db:
        row = db.get(RefreshToken, old_jti)
    assert row is not None and row.used


def test_refresh_used_token_returns_401(client):
    client.post("/auth/register", json={"email": "e@test.com", "password": "pw"})
    login_r = client.post("/auth/login", json={"email": "e@test.com", "password": "pw"})
    assert login_r.status_code == 200
    # Capture the original refresh token before it gets rotated.
    original_refresh = login_r.cookies.get("refresh_token")

    # First refresh succeeds and rotates the token.
    r1 = client.post("/auth/refresh")
    assert r1.status_code == 200

    # Force the old (now-used) token into a fresh client and try to use it.
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as fresh:
        fresh.cookies.set("refresh_token", original_refresh)
        r2 = fresh.post("/auth/refresh")
    assert r2.status_code == 401


def test_logout_clears_cookies(client):
    client.post("/auth/register", json={"email": "f@test.com", "password": "pw"})
    client.post("/auth/login", json={"email": "f@test.com", "password": "pw"})

    r = client.post("/auth/logout")
    assert r.status_code == 200
    # Starlette's TestClient reflects cookie deletions as empty-string or absent.
    assert not client.cookies.get("access_token")
    assert not client.cookies.get("refresh_token")


def test_me_without_cookie_returns_401(client):
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_me_after_login(client):
    client.post("/auth/register", json={"email": "g@test.com", "password": "pw"})
    client.post("/auth/login", json={"email": "g@test.com", "password": "pw"})
    r = client.get("/auth/me")
    assert r.status_code == 200
    assert r.json()["email"] == "g@test.com"
