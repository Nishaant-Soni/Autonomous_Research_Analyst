"""Async research API (plan 3.1): start a run and return its id immediately."""

import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.progress import create_queue, get_queue, remove_queue
from app.db.models import Evidence as EvidenceRow
from app.db.models import Report, ResearchSession
from app.db.session import SessionLocal, get_db
from app.graph.runner import run_research

router = APIRouter()

# asyncio only keeps weak references to tasks, so a fire-and-forget task can be garbage
# collected mid-run. Hold a strong ref until it finishes (the documented pattern).
_background_tasks: set[asyncio.Task] = set()


class ResearchIn(BaseModel):
    question: str = Field(min_length=1)


class ResearchOut(BaseModel):
    session_id: int


async def _run_and_cleanup(session_id, question, checkpointer, queue) -> None:
    try:
        await run_research(session_id, question, checkpointer, queue)
    finally:
        remove_queue(session_id)


@router.post("/research", response_model=ResearchOut, status_code=202)
async def start_research(body: ResearchIn, request: Request) -> ResearchOut:
    with SessionLocal() as db:
        session = ResearchSession(question=body.question, status="planning")
        db.add(session)
        db.commit()
        session_id = session.id

    queue = create_queue(session_id)
    task = asyncio.create_task(
        _run_and_cleanup(
            session_id, body.question, request.app.state.checkpointer, queue
        )
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return ResearchOut(session_id=session_id)


class ResearchSummaryOut(BaseModel):
    """Per-row payload for the recent-runs sidebar (plan 5.7). Deliberately leaner than
    `ResearchStatusOut` — no `report_md`, no `citations_valid` (those would need a join
    on `reports` per row; cheap detail endpoint already returns them per click)."""

    session_id: int
    question: str
    status: str
    low_confidence: bool
    created_at: datetime
    completed_at: datetime | None = None


_LIST_LIMIT_MAX = 100
_LIST_LIMIT_DEFAULT = 20


@router.get("/research", response_model=list[ResearchSummaryOut])
def list_research(
    limit: int = Query(default=_LIST_LIMIT_DEFAULT, ge=1, le=_LIST_LIMIT_MAX),
    db: Session = Depends(get_db),
) -> list[ResearchSummaryOut]:
    """Recent runs, newest first. Used by the React sidebar to let a reviewer flip between
    questions. v1 portfolio scale is tens of rows; cursor pagination is overkill — keep
    plain `?limit=N`. Clamp protects against accidental large queries."""
    sessions = (
        db.execute(
            select(ResearchSession).order_by(ResearchSession.id.desc()).limit(limit)
        )
        .scalars()
        .all()
    )
    return [
        ResearchSummaryOut(
            session_id=s.id,
            question=s.question,
            status=s.status,
            low_confidence=s.low_confidence,
            created_at=s.created_at,
            completed_at=s.completed_at,
        )
        for s in sessions
    ]


class ResearchStatusOut(BaseModel):
    session_id: int
    status: str
    report_md: str | None = None
    citations_valid: bool | None = None
    low_confidence: bool | None = None
    error: str | None = None


@router.get("/research/{session_id}", response_model=ResearchStatusOut)
def get_research(session_id: int, db: Session = Depends(get_db)) -> ResearchStatusOut:
    """Poll a run's status; once `done`, also return the report + citation validity (3.3)."""
    session = db.get(ResearchSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")

    report = None
    if session.status == "done":
        report = (
            db.query(Report)
            .filter_by(session_id=session_id)
            .order_by(Report.id.desc())
            .first()
        )
    return ResearchStatusOut(
        session_id=session.id,
        status=session.status,
        report_md=report.report_md if report else None,
        citations_valid=report.citations_valid if report else None,
        low_confidence=session.low_confidence,
        error=session.error,
    )


class EvidenceOut(BaseModel):
    claim: str | None = None
    content: str | None = None
    source_url: str | None = None
    source_chunk_id: int | None = None
    retriever: str


@router.get("/research/{session_id}/evidence", response_model=list[EvidenceOut])
def get_evidence(session_id: int, db: Session = Depends(get_db)) -> list[EvidenceOut]:
    """Return the structured evidence persisted for a session (3.4). Empty until the run
    completes (evidence is written on success)."""
    session = db.get(ResearchSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")

    rows = (
        db.query(EvidenceRow)
        .filter_by(session_id=session_id)
        .order_by(EvidenceRow.id)
        .all()
    )
    return [
        EvidenceOut(
            claim=r.claim,
            content=r.content,
            source_url=r.source_url,
            source_chunk_id=r.source_chunk_id,
            retriever=r.retriever,
        )
        for r in rows
    ]


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@router.get("/research/{session_id}/stream")
async def stream_research(session_id: int) -> StreamingResponse:
    """SSE per-agent progress (3.5). Drains the session's in-process queue, emitting each
    per-node event until the run's `None` sentinel. A late/early subscriber with no live
    queue (run already finished and cleaned up) gets the terminal DB status once."""
    queue = get_queue(session_id)
    if queue is not None:

        async def _drain():
            while True:
                item = await queue.get()
                if item is None:  # sentinel: run finished, stream closed
                    break
                yield _sse(item)

        return StreamingResponse(_drain(), media_type="text/event-stream")

    # No live queue: the run already finished (and its queue was removed), or never existed.
    with SessionLocal() as db:
        session = db.get(ResearchSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    status = session.status

    async def _terminal():
        yield _sse({"status": status})

    return StreamingResponse(_terminal(), media_type="text/event-stream")
