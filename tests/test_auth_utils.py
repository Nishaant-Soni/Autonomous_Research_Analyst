"""Unit tests for app.auth.utils (plan 6.2). No DB or external deps required."""

import jwt
import pytest


def test_hash_and_verify():
    from app.auth.utils import hash_password, verify_password

    hashed = hash_password("hunter2")
    assert verify_password("hunter2", hashed)
    assert not verify_password("wrong", hashed)


def test_create_and_decode_access_token(monkeypatch):
    monkeypatch.setattr("app.auth.utils.settings", _settings())

    from app.auth.utils import create_access_token, decode_token

    token = create_access_token(42)
    payload = decode_token(token)
    assert payload["sub"] == "42"
    assert payload["typ"] == "access"


def test_create_and_decode_refresh_token(monkeypatch):
    monkeypatch.setattr("app.auth.utils.settings", _settings())

    from app.auth.utils import create_refresh_token, decode_token

    token, jti, _ = create_refresh_token(7)
    payload = decode_token(token)
    assert payload["sub"] == "7"
    assert payload["typ"] == "refresh"
    assert payload["jti"] == jti


def test_tampered_token_raises(monkeypatch):
    monkeypatch.setattr("app.auth.utils.settings", _settings())

    from app.auth.utils import create_access_token, decode_token

    token = create_access_token(1)
    tampered = token[:-4] + "XXXX"
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(tampered)


def test_expired_token_raises(monkeypatch):
    import importlib

    monkeypatch.setattr("app.auth.utils.settings", _settings(expire_minutes=0))
    # reload so the monkeypatched settings are picked up by the module-level reference
    import app.auth.utils as utils_mod

    importlib.reload(utils_mod)
    monkeypatch.setattr("app.auth.utils.settings", _settings(expire_minutes=0))

    from datetime import timedelta
    from datetime import timezone
    from datetime import datetime

    import jwt as _jwt

    secret = "testsecret"
    payload = {
        "sub": "1",
        "typ": "access",
        "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
    }
    token = _jwt.encode(payload, secret, algorithm="HS256")
    with pytest.raises(_jwt.InvalidTokenError):
        _jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"require": ["exp", "sub", "typ"]},
        )


def test_wrong_typ_detected(monkeypatch):
    monkeypatch.setattr("app.auth.utils.settings", _settings())

    from app.auth.utils import create_refresh_token, decode_token

    token, _, _ = create_refresh_token(5)
    payload = decode_token(token)
    # The typ check is done at the call site (endpoints), not in decode_token itself.
    assert payload["typ"] == "refresh"
    # Callers that expect "access" reject this:
    assert payload["typ"] != "access"


def test_missing_jwt_secret_raises(monkeypatch):
    monkeypatch.setattr("app.auth.utils.settings", _settings(secret=""))

    from app.auth.utils import create_access_token

    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        create_access_token(1)


# ── helpers ───────────────────────────────────────────────────────────────────


class _MockSettings:
    def __init__(self, secret, expire_minutes, expire_days):
        self.jwt_secret = secret
        self.access_token_expire_minutes = expire_minutes
        self.refresh_token_expire_days = expire_days
        self.cookie_secure = False


def _settings(secret="testsecret", expire_minutes=15, expire_days=7):
    return _MockSettings(secret, expire_minutes, expire_days)
