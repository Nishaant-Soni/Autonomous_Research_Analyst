"""FastAPI auth dependency (plan 6.4)."""

import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth.utils import decode_token
from app.db.models import User
from app.db.session import get_db


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
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
    return user
