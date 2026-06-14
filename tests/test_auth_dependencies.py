"""Unit tests for get_current_user dependency (plan 6.4). No DB required."""

import pytest


@pytest.fixture(autouse=True)
def _patch_settings(monkeypatch):
    import app.auth.utils as utils_mod
    import app.config as cfg_mod

    monkeypatch.setattr(cfg_mod.settings, "jwt_secret", "test-dep-secret")
    monkeypatch.setattr(utils_mod.settings, "jwt_secret", "test-dep-secret")


def _make_request(cookie_name: str | None, token: str | None):
    """Build a minimal Request-like object with a single cookie."""
    from unittest.mock import MagicMock

    req = MagicMock()
    req.cookies = {}
    if cookie_name and token:
        req.cookies[cookie_name] = token
    return req


def _make_db(user=None):
    from unittest.mock import MagicMock

    db = MagicMock()
    db.get.return_value = user
    return db


def _make_user(uid=1):
    from unittest.mock import MagicMock

    u = MagicMock()
    u.id = uid
    return u


def test_missing_cookie_raises_401():
    from fastapi import HTTPException

    from app.auth.dependencies import get_current_user

    with pytest.raises(HTTPException) as exc:
        get_current_user(_make_request(None, None), _make_db())
    assert exc.value.status_code == 401


def test_tampered_token_raises_401():
    from fastapi import HTTPException

    from app.auth.dependencies import get_current_user
    from app.auth.utils import create_access_token

    token = create_access_token(1) + "tampered"
    with pytest.raises(HTTPException) as exc:
        get_current_user(_make_request("access_token", token), _make_db())
    assert exc.value.status_code == 401


def test_wrong_typ_raises_401():
    from fastapi import HTTPException

    from app.auth.dependencies import get_current_user
    from app.auth.utils import create_refresh_token

    token, _, _ = create_refresh_token(1)
    with pytest.raises(HTTPException) as exc:
        get_current_user(_make_request("access_token", token), _make_db())
    assert exc.value.status_code == 401


def test_deleted_user_raises_401():
    from fastapi import HTTPException

    from app.auth.dependencies import get_current_user
    from app.auth.utils import create_access_token

    token = create_access_token(99)
    with pytest.raises(HTTPException) as exc:
        get_current_user(_make_request("access_token", token), _make_db(user=None))
    assert exc.value.status_code == 401
    assert exc.value.detail == "Not authenticated"


def test_valid_token_returns_user():
    from app.auth.dependencies import get_current_user
    from app.auth.utils import create_access_token

    user = _make_user(uid=5)
    token = create_access_token(5)
    result = get_current_user(_make_request("access_token", token), _make_db(user=user))
    assert result is user
