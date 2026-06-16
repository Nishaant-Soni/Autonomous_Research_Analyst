from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.documents import router as documents_router
from app.api.research import router as research_router
from app.config import settings
from app.db.init_db import checkpointer_cm, init_db, mark_abandoned_sessions, purge_expired_refresh_tokens
from app.observability import configure_langsmith

_CORS_ALLOW_ORIGIN_REGEX = r"^http://(localhost|127\.0\.0\.1)(:\d+)?$"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Single DB-init path (plan 2.8): apply the schema + set up the checkpoint tables, then
    keep the live checkpointer on `app.state` for the graph to use on every run. The
    `async with` stays open for the app's lifetime so the connection isn't closed at run time.
    (Only runs when the app is actually started — bare `TestClient(app)` does not trigger it.)
    """
    if not settings.jwt_secret:
        raise RuntimeError(
            "JWT_SECRET is not set. Generate one with: "
            "python -c 'import secrets; print(secrets.token_urlsafe(64))'"
        )
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set — required for LLM agents.")
    if not settings.tavily_api_key:
        raise RuntimeError("TAVILY_API_KEY is not set — required for web search.")
    configure_langsmith()  # enable tracing if a LANGSMITH_API_KEY is set (3.7); else a no-op
    async with checkpointer_cm() as checkpointer:
        await init_db(checkpointer)
        mark_abandoned_sessions()
        purge_expired_refresh_tokens()
        app.state.checkpointer = checkpointer
        yield


app = FastAPI(title="Autonomous Research Analyst", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=_CORS_ALLOW_ORIGIN_REGEX,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    allow_credentials=True,
)
app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(research_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
