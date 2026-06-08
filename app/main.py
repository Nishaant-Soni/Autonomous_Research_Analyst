from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.documents import router as documents_router
from app.api.research import router as research_router
from app.db.init_db import checkpointer_cm, init_db
from app.observability import configure_langsmith


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
        app.state.checkpointer = checkpointer
        yield


app = FastAPI(title="Autonomous Research Analyst", lifespan=lifespan)
app.include_router(documents_router)
app.include_router(research_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
