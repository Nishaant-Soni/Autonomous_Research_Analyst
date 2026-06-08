"""Database initialization (PRD §5.2, plan 2.8).

Single idempotent init path: `init_db(checkpointer)` ensures both the app schema
(`schema.sql`) and LangGraph's checkpoint tables exist. The DDL is idempotent (IF NOT
EXISTS), so it's safe to run on every startup or in tests; docker-compose also mounts
schema.sql into the db init dir for the fresh-volume case.

The checkpointer is the **async** `AsyncPostgresSaver` (the Phase 3 runner is async). Its
connection is a context manager that closes on exit, so callers must keep the
`async with checkpointer_cm()` block open for as long as the graph needs to run — see
`app.main`'s lifespan and `scripts/run_once`.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import update

from app.config import settings
from app.db.session import engine

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def apply_schema() -> None:
    sql = SCHEMA_PATH.read_text()
    with engine.begin() as conn:
        conn.exec_driver_sql(sql)


def _checkpointer_conninfo() -> str:
    # AsyncPostgresSaver wants a plain psycopg conninfo, not the SQLAlchemy URL dialect.
    return settings.database_url.replace("postgresql+psycopg://", "postgresql://")


def checkpointer_cm():
    """The AsyncPostgresSaver context manager. Use as `async with checkpointer_cm() as cp:`
    and keep the block open for the lifetime of any graph runs that use `cp`."""
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    return AsyncPostgresSaver.from_conn_string(_checkpointer_conninfo())


async def init_db(checkpointer) -> None:
    """Idempotent: ensure the app schema (`schema.sql`) and the checkpoint tables exist.

    `checkpointer` is an already-opened `AsyncPostgresSaver` (its connection lifetime is the
    caller's responsibility); this only runs the two setup steps.
    """
    apply_schema()
    await checkpointer.setup()


# Terminal session statuses: anything else means a run was in flight when the API last
# stopped (deploy, OOM, crash, dev rebuild). The startup sweep below promotes them to
# `failed` so the UI / API consumers see an honest terminal state instead of a zombie.
_TERMINAL_STATUSES = ("done", "failed")
_ABANDONED_ERROR = "abandoned at startup"


def mark_abandoned_sessions() -> int:
    """Promote any non-terminal `research_sessions` row to `failed` with a clear error.

    Called once at startup (see `app.main.lifespan`). The runner has no resume logic —
    when the API process dies mid-run, asyncio cancels the task and the DB row stays at
    whatever status it last reached (`researching`, `critiquing`, …). Without this sweep,
    those rows are zombies forever. The fix is symmetric with the runner's own failure
    path: same `status="failed"`, same `error` field, `completed_at` stamped now.

    Returns the number of rows updated; logged at INFO when non-zero. Safe to call on
    every boot (idempotent: already-terminal rows are skipped by the WHERE clause).
    """
    # Lazy import — Models live alongside engine bindings; importing at module top would
    # complicate test fixtures that monkey-patch the session before init.
    from app.db.models import ResearchSession
    from app.db.session import SessionLocal

    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        result = db.execute(
            update(ResearchSession)
            .where(~ResearchSession.status.in_(_TERMINAL_STATUSES))
            .values(status="failed", error=_ABANDONED_ERROR, completed_at=now)
        )
        db.commit()
        n = result.rowcount
    if n:
        logger.warning(
            "marked %d abandoned research session(s) as failed at startup", n
        )
    return n
