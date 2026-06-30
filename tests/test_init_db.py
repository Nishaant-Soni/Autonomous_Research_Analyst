"""Tests for the startup zombie sweep (Phase 5 follow-up, post-31).

The runner has no resume logic, so a process death mid-run leaves the session row
stuck at whatever status it last reached. `mark_abandoned_sessions()` is called once
in the FastAPI lifespan to promote those rows to `failed` with a clear error message.
"""

import os

import pytest

requires_db = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="set RUN_DB_TESTS=1 with a running Postgres",
)


@requires_db
def test_marks_non_terminal_sessions_as_failed():
    from app.db.init_db import mark_abandoned_sessions
    from app.db.models import ResearchSession
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        for status in [
            "planning",
            "researching",
            "critiquing",
            "writing",
            "validating",
        ]:
            db.add(ResearchSession(question=f"q-{status}", status=status))
        db.commit()

    n = mark_abandoned_sessions()

    assert n == 5
    with SessionLocal() as db:
        sessions = db.query(ResearchSession).all()
        assert all(s.status == "failed" for s in sessions)
        assert all(
            s.error == "The run was interrupted by a server restart." for s in sessions
        )
        assert all(s.completed_at is not None for s in sessions)


@requires_db
def test_does_not_touch_done_or_already_failed_sessions():
    from app.db.init_db import mark_abandoned_sessions
    from app.db.models import ResearchSession
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        db.add(ResearchSession(question="finished", status="done"))
        db.add(
            ResearchSession(
                question="real failure",
                status="failed",
                error="real error from runner",
            )
        )
        db.commit()

    n = mark_abandoned_sessions()

    assert n == 0
    with SessionLocal() as db:
        done = db.query(ResearchSession).filter_by(question="finished").one()
        failed = db.query(ResearchSession).filter_by(question="real failure").one()
        assert done.status == "done"
        # Real failure's error message must be preserved — not overwritten with the
        # generic abandoned-session string.
        assert failed.error == "real error from runner"


@requires_db
def test_empty_table_is_noop():
    from app.db.init_db import mark_abandoned_sessions

    assert mark_abandoned_sessions() == 0


@requires_db
def test_is_idempotent():
    """Two back-to-back calls leave the table in the same final state — the second call
    finds zero non-terminal rows (because the first already marked them)."""
    from app.db.init_db import mark_abandoned_sessions
    from app.db.models import ResearchSession
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        db.add(ResearchSession(question="zombie", status="critiquing"))
        db.commit()

    assert mark_abandoned_sessions() == 1
    assert mark_abandoned_sessions() == 0
