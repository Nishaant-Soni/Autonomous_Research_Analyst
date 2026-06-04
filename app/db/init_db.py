"""Apply `schema.sql` against the configured database.

Idempotent (the DDL uses IF NOT EXISTS), so it's safe to run on every startup or in
tests. docker-compose also mounts schema.sql into the db image's init dir for the
fresh-volume case; this gives a code path that also works against an existing volume.
"""

from pathlib import Path

from app.db.session import engine

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def apply_schema() -> None:
    sql = SCHEMA_PATH.read_text()
    with engine.begin() as conn:
        conn.exec_driver_sql(sql)
