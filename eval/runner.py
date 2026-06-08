"""Eval graph runner (plan 4.5 Run stage, A2).

Runs the research graph in-process for one golden item — **no DB session row, no
checkpointer, no HTTP** (plan decision under 4.5: eval artifacts live on disk; running
through `POST /research` would add polling latency for no benefit). Per-question
artifacts land under `eval/runs/<run-id>/<item.id>/` for the Score stage (B1/B2/B3) to
consume.
"""

import json
import time
import traceback
from pathlib import Path

from app.graph.build import build_graph
from app.graph.runner import build_initial_state
from eval.dataset import GoldenItem


async def run_one_question(
    item: GoldenItem,
    run_id: str | None = None,
    max_iterations: int | None = None,
) -> dict:
    """Run the graph for one golden item. Returns {final, latency_seconds} on success;
    raises on graph failure (caller decides whether to continue the run).

    `run_id` is the parent eval run's id (`eval/runs/<run-id>/`); when provided, it is
    forwarded to LangSmith as trace metadata + a `run_name` so the Score stage (B3) can
    query token usage per item via the LangSmith API. `None` runs unlabeled (still traced
    if LANGSMITH_API_KEY is set, just without the eval-specific tags).

    `max_iterations` overrides `settings.max_iterations` for this run only — set to `0`
    to disable the critic loop-back for the C2 A/B."""
    graph = build_graph()  # no checkpointer: eval is one-shot, no resume needed
    initial = build_initial_state(item.id, item.question, max_iterations=max_iterations)
    config: dict = {}
    if run_id is not None:
        config = {
            "metadata": {"eval_run_id": run_id, "eval_item_id": item.id},
            "run_name": f"eval:{run_id}:{item.id}",
        }
    start = time.perf_counter()
    final = await graph.ainvoke(initial, config=config or None)
    latency = time.perf_counter() - start
    return {"final": final, "latency_seconds": latency}


def persist_artifacts(item_dir: Path, item: GoldenItem, run_result: dict) -> None:
    """Write `report.md`, `evidence.jsonl`, and `result.json` for one item. `result.json`
    is the machine-readable summary B2 (Ragas) will load alongside the report + evidence."""
    item_dir.mkdir(parents=True, exist_ok=True)
    final = run_result["final"]
    evidence = final["evidence"]

    (item_dir / "report.md").write_text(final["report_md"])

    with (item_dir / "evidence.jsonl").open("w") as f:
        for ev in evidence:
            f.write(
                json.dumps(
                    {
                        "claim": ev.claim,
                        "content": ev.content,
                        "source_url": ev.source_url,
                        "source_chunk_id": ev.source_chunk_id,
                        "retriever": ev.retriever,
                    }
                )
                + "\n"
            )

    (item_dir / "result.json").write_text(
        json.dumps(
            {
                "id": item.id,
                "question": item.question,
                "target": item.target,
                "reference": item.reference,
                "source_docs": item.source_docs,
                "acceptable_domains": item.acceptable_domains,
                "citations_valid": final["citations_valid"],
                "low_confidence": final["low_confidence"],
                "stripped_fraction": final["stripped_fraction"],
                "latency_seconds": run_result["latency_seconds"],
                "evidence_count": len(evidence),
            },
            indent=2,
        )
    )


def persist_error(item_dir: Path, item: GoldenItem, exc: BaseException) -> None:
    """Record a failed run so the rest of the eval continues. The presence of `error.txt`
    (and absence of `result.json`) is the signal to the Score stage that this item failed."""
    item_dir.mkdir(parents=True, exist_ok=True)
    (item_dir / "error.txt").write_text(
        f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}"
    )
    # A minimal result.json keeps run-level aggregation simple (failed items are filtered out).
    (item_dir / "result.json").write_text(
        json.dumps(
            {
                "id": item.id,
                "question": item.question,
                "target": item.target,
                "failed": True,
                "error": f"{type(exc).__name__}: {exc}",
            },
            indent=2,
        )
    )
