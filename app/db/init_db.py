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

from pathlib import Path

from app.config import settings
from app.db.session import engine

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
