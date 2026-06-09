from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.documents import router as documents_router
from app.api.research import router as research_router
from app.db.init_db import checkpointer_cm, init_db, mark_abandoned_sessions
from app.observability import configure_langsmith

# Phase 5 (Group A): the React app makes cross-origin XHR + EventSource calls. Scope CORS
# to local dev origins; keep `allow_origins=["*"]` off — the API already takes untrusted
# web content from Tavily inside Researcher, and tightening the browser-side surface is
# cheap. The regex covers localhost/127.0.0.1 on any port (Vite occasionally moves to
# 5174 when 5173 is busy; a second concurrent dev instance is the most common
# foot-gun this catches).
_CORS_ALLOW_ORIGIN_REGEX = r"^http://(localhost|127\.0\.0\.1)(:\d+)?$"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Single DB-init path (plan 2.8): apply the schema + set up the checkpoint tables, then
    keep the live checkpointer on `app.state` for the graph to use on every run. The
    `async with` stays open for the app's lifetime so the connection isn't closed at run time.
    (Only runs when the app is actually started — bare `TestClient(app)` does not trigger it.)
    """
    configure_langsmith()  # enable tracing if a LANGSMITH_API_KEY is set (3.7); else a no-op
    async with checkpointer_cm() as checkpointer:
        await init_db(checkpointer)
        mark_abandoned_sessions()
        app.state.checkpointer = checkpointer
        yield


app = FastAPI(title="Autonomous Research Analyst", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=_CORS_ALLOW_ORIGIN_REGEX,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)
app.include_router(documents_router)
app.include_router(research_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
