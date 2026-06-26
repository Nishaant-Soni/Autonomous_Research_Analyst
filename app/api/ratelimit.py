"""API rate limiting (slowapi).

Identity for a limit is the authenticated user when a valid access-token cookie is present,
else the client IP. So per-user limits apply to logged-in traffic (the expensive `/research`
+ `/documents` writes), and the unauthenticated auth endpoints (`/auth/login`,
`/auth/register`) are throttled per IP as brute-force protection.

Read-only polling endpoints (GET `/research/{id}`, `/stream`, the recent-runs list, `/auth/me`)
are deliberately NOT limited — the UI polls them and a limit there would throttle the user's
own live progress view.

Storage is in-memory (single-process), consistent with the in-process progress queue
(`app/api/progress.py`); Redis is the documented multi-worker scale path for both.

IP identity uses the direct socket address (`request.client.host`) and does NOT parse
`X-Forwarded-For`. Correct for the committed deployment (browser -> API directly, single
container). Behind a reverse proxy / load balancer every client collapses into the proxy's
single IP bucket, weakening the per-IP brute-force protection on the auth endpoints; making
it proxy-aware (trusted `X-Forwarded-For`) is the fix if deployed that way.
"""

import jwt
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.auth.utils import decode_token
from app.config import settings

# Limit strings use the slowapi/`limits` syntax. Tune here; the on/off switch is
# `settings.rate_limit_enabled` (off in tests). Limits are generous enough for a demo
# while still capping abuse and runaway cost.
AUTH_LOGIN_LIMIT = "10/minute"
AUTH_REGISTER_LIMIT = "5/minute"
RESEARCH_LIMIT = "10/minute"
DOCUMENTS_LIMIT = "20/minute"


def _user_or_ip(request: Request) -> str:
    """Rate-limit key: the user id from a valid access-token cookie, else the client IP.

    Mirrors `get_current_user`'s token check but never raises — an absent/invalid token just
    means we fall back to IP-based limiting (correct for the unauthenticated auth endpoints).
    """
    token = request.cookies.get("access_token")
    if token:
        try:
            payload = decode_token(token)
            if payload.get("typ") == "access":
                return f"user:{payload['sub']}"
        except (jwt.InvalidTokenError, RuntimeError):
            # InvalidTokenError: bad/expired token. RuntimeError: JWT_SECRET unset (the case
            # in CI / test envs that don't configure it) — decode_token raises before parsing.
            # Either way this is best-effort identity, never auth enforcement, so fall back to IP.
            pass
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=_user_or_ip, enabled=settings.rate_limit_enabled)
