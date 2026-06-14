"""Auth utilities (plan 6.2): password hashing and JWT creation/validation."""

import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import settings


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _secret() -> str:
    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET must be set")
    return settings.jwt_secret


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {"sub": str(user_id), "exp": expire, "typ": "access"}
    return jwt.encode(payload, _secret(), algorithm="HS256")


def create_refresh_token(user_id: int) -> tuple[str, str, datetime]:
    """Returns (encoded_token, jti, expires_at). Caller persists the jti row."""
    jti = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
    payload = {"sub": str(user_id), "jti": jti, "exp": expires_at, "typ": "refresh"}
    encoded = jwt.encode(payload, _secret(), algorithm="HS256")
    return encoded, jti, expires_at


def decode_token(token: str) -> dict:
    """Raises jwt.InvalidTokenError on tampered, expired, or missing-claim tokens."""
    return jwt.decode(
        token,
        _secret(),
        algorithms=["HS256"],
        options={"require": ["exp", "sub", "typ"]},
    )
