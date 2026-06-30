"""Fast validation tests for the auth input models (#1). No DB/network — these exercise the
Pydantic models directly, proving the policy split (min-length on register only) and the
bcrypt 72-byte cap (on both)."""

import pytest
from pydantic import ValidationError

from app.api.auth import _MAX_PASSWORD_BYTES, LoginIn, RegisterIn


def test_register_requires_minimum_password_length():
    with pytest.raises(ValidationError):
        RegisterIn(email="a@b.com", password="short")  # 5 < 8


def test_login_has_no_minimum_length_policy():
    # Login must accept a short password (so a legacy/short credential returns 401, not 422,
    # preserving the constant-time enumeration guard).
    assert LoginIn(email="a@b.com", password="x").password == "x"


def test_both_models_reject_password_over_bcrypt_limit():
    too_long = "x" * (_MAX_PASSWORD_BYTES + 1)
    with pytest.raises(ValidationError):
        LoginIn(email="a@b.com", password=too_long)
    with pytest.raises(
        ValidationError
    ):  # confirms the inherited validator fires on the subclass
        RegisterIn(email="a@b.com", password=too_long)


def test_multibyte_password_counted_in_bytes_not_chars():
    # 37 emoji = 4 bytes each = 148 bytes > 72, even though it's only 37 characters.
    with pytest.raises(ValidationError):
        LoginIn(email="a@b.com", password="😀" * 37)


def test_both_models_reject_malformed_email():
    with pytest.raises(ValidationError):
        LoginIn(email="not-an-email", password="x")
    with pytest.raises(ValidationError):
        RegisterIn(email="not-an-email", password="longenough")


def test_valid_inputs_accepted():
    assert LoginIn(email="a@b.com", password="x").email == "a@b.com"
    assert RegisterIn(email="a@b.com", password="longenough").email == "a@b.com"
