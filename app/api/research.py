"""Async research API (plan 3.1): start a run and return its id immediately."""

import asyncio

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.api.progress import create_queue, remove_queue
from app.db.models import ResearchSession
from app.db.session import SessionLocal
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
