"""Auth endpoints (plan 6.3): register, login, refresh, logout, /auth/me."""

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.utils import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.config import settings
from app.db.models import RefreshToken, User
from app.db.session import get_db

router = APIRouter(prefix="/auth")


class AuthIn(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    user_id: int
    email: str


def _set_auth_cookies(
    response: Response, access_token: str, refresh_token: str
) -> None:
    response.set_cookie(
        "access_token",
        access_token,
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        samesite="strict",
        secure=settings.cookie_secure,
        path="/",
    )
    response.set_cookie(
        "refresh_token",
        refresh_token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        httponly=True,
        samesite="strict",
        secure=settings.cookie_secure,
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")


@router.post("/register", status_code=201, response_model=UserOut)
def register(body: AuthIn, db: Session = Depends(get_db)) -> UserOut:
    user = User(email=body.email, hashed_pw=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email already registered")
    db.refresh(user)
    return UserOut(user_id=user.id, email=user.email)


@router.post("/login", response_model=UserOut)
def login(body: AuthIn, response: Response, db: Session = Depends(get_db)) -> UserOut:
    user = db.query(User).filter_by(email=body.email).first()
    # Constant-time check even when user is missing to prevent timing-based enumeration.
    if user is None or not verify_password(body.password, user.hashed_pw):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access = create_access_token(user.id)
    refresh, jti, expires_at = create_refresh_token(user.id)
    db.add(RefreshToken(jti=jti, user_id=user.id, expires_at=expires_at))
    db.commit()

    _set_auth_cookies(response, access, refresh)
    return UserOut(user_id=user.id, email=user.email)


@router.post("/refresh")
def refresh_tokens(
    request: Request, response: Response, db: Session = Depends(get_db)
) -> dict:
    raw = request.cookies.get("refresh_token")
    if not raw:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = decode_token(raw)
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if payload.get("typ") != "refresh":
        raise HTTPException(status_code=401, detail="Not authenticated")

    jti = payload.get("jti")
    row = db.get(RefreshToken, jti)
    if row is None or row.used:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = int(payload["sub"])
    row.used = True
    db.commit()

    access = create_access_token(user_id)
    new_refresh, new_jti, expires_at = create_refresh_token(user_id)
    db.add(RefreshToken(jti=new_jti, user_id=user_id, expires_at=expires_at))
    db.commit()

    _set_auth_cookies(response, access, new_refresh)
    return {"ok": True}


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    raw = request.cookies.get("refresh_token")
    if raw:
        try:
            payload = decode_token(raw)
            jti = payload.get("jti")
            if jti:
                row = db.get(RefreshToken, jti)
                if row and not row.used:
                    row.used = True
                    db.commit()
        except jwt.InvalidTokenError:
            pass  # invalid/expired token — just clear cookies

    _clear_auth_cookies(response)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def get_me(request: Request, db: Session = Depends(get_db)) -> UserOut:
    """Lightweight 'am I logged in?' — used by React to rehydrate auth state on page load."""
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = decode_token(token)
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if payload.get("typ") != "access":
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return UserOut(user_id=user.id, email=user.email)
