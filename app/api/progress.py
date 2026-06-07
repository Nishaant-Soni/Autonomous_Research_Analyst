"""In-process progress bridge between the runner task and the SSE endpoint (plan 3.1/3.5).

A module-level map of session_id -> asyncio.Queue. The POST handler creates a queue, the
runner (handed the queue) pushes per-node events plus a `None` sentinel, and the SSE
endpoint (3.5) drains it. Single-process only — Redis pub/sub is the multi-worker scale path.
"""

import asyncio

_queues: dict[int, asyncio.Queue] = {}


def create_queue(session_id: int) -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue()
    _queues[session_id] = queue
    return queue


def get_queue(session_id: int) -> asyncio.Queue | None:
    return _queues.get(session_id)


def remove_queue(session_id: int) -> None:
    _queues.pop(session_id, None)
