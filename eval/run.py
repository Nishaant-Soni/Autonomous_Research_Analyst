"""Eval CLI entry point (plan 4.5; A2 covers the Run + retrievability stages).

    python -m eval.run                       # full run over the golden set
    python -m eval.run --limit 2             # smoke run over the first N items
    python -m eval.run --skip-ingest         # skip the corpus ingest step
    python -m eval.run --skip-retrievability # skip the post-run corpus check
    python -m eval.run --only-retrievability # ingest + retrievability only (no graph runs)

Per-question artifacts land under `eval/runs/<run-id>/<item.id>/`. Run-level files:
`meta.json`, `summary.json`, `retrievability.json`. A failed item writes `error.txt` +
a minimal `result.json{failed: true}` and the run continues.
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.observability import configure_langsmith
from eval.dataset import load_golden
from eval.ingest_corpus import ingest_seed_corpus
from eval.retrievability import check_corpus_retrievability
from eval.runner import persist_artifacts, persist_error, run_one_question

logger = logging.getLogger("eval")

_RUNS_DIR = Path(__file__).parent / "runs"


def _new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--limit", type=int, default=0, help="run only the first N items (0 = all)"
    )
    p.add_argument("--skip-ingest", action="store_true")
    p.add_argument("--skip-retrievability", action="store_true")
    p.add_argument(
        "--only-retrievability",
        action="store_true",
        help="ingest + retrievability only; skip graph runs (cheap, no LLM)",
    )
    return p.parse_args(argv)


async def _main(args: argparse.Namespace) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    configure_langsmith()

    # Schema bootstrap: eval doesn't own it. Run the API (lifespan applies the schema) or
    # `python -m scripts.run_once` once on a fresh DB volume before invoking the eval CLI.
    # A missing schema surfaces as a SQL error on the first ingest/retrieval call.

    items = load_golden()
    if args.limit > 0:
        items = items[: args.limit]
    logger.info("loaded %d golden items", len(items))

    run_id = _new_run_id()
    run_dir = _RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    logger.info("run dir: %s", run_dir)

    # --- ingest -----------------------------------------------------------------
    ingest_summary = {"skipped": True}
    if not args.skip_ingest:
        ingest_summary = ingest_seed_corpus()
        logger.info(
            "ingested %d new docs, skipped %d existing",
            len(ingest_summary["ingested"]),
            len(ingest_summary["skipped"]),
        )

    # --- per-question runs ------------------------------------------------------
    per_item: list[dict] = []
    if not args.only_retrievability:
        for item in items:
            item_dir = run_dir / item.id
            logger.info("running %s (%s)", item.id, item.target)
            try:
                result = await run_one_question(item, run_id=run_id)
                persist_artifacts(item_dir, item, result)
                per_item.append(
                    {
                        "id": item.id,
                        "ok": True,
                        "latency_seconds": result["latency_seconds"],
                        "evidence_count": len(result["final"]["evidence"]),
                        "citations_valid": result["final"]["citations_valid"],
                    }
                )
            except Exception as exc:  # one bad item doesn't kill the run
                logger.exception("item %s failed", item.id)
                persist_error(item_dir, item, exc)
                per_item.append({"id": item.id, "ok": False, "error": str(exc)})

    # --- retrievability ---------------------------------------------------------
    retrievability = None
    if not args.skip_retrievability:
        # Run against the *full* golden set (not just the limited slice) — retrievability
        # is a dataset health check, independent of how many graph runs we did.
        retrievability = check_corpus_retrievability(load_golden())
        (run_dir / "retrievability.json").write_text(
            json.dumps(retrievability, indent=2)
        )
        logger.info("retrievability: all_passed=%s", retrievability.get("all_passed"))

    # --- run-level files --------------------------------------------------------
    (run_dir / "meta.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "started_at": run_id,  # the id IS the timestamp
                "limit": args.limit,
                "skipped_ingest": args.skip_ingest,
                "skipped_retrievability": args.skip_retrievability,
                "only_retrievability": args.only_retrievability,
                "item_count": len(items),
                "ingest": ingest_summary,
            },
            indent=2,
        )
    )
    (run_dir / "summary.json").write_text(
        json.dumps(
            {
                "items": per_item,
                "ok_count": sum(1 for r in per_item if r.get("ok")),
                "fail_count": sum(1 for r in per_item if not r.get("ok")),
                "retrievability_all_passed": (
                    retrievability.get("all_passed") if retrievability else None
                ),
            },
            indent=2,
        )
    )
    logger.info("done. artifacts at %s", run_dir)
    return 0


def main() -> None:
    args = _parse_args(sys.argv[1:])
    sys.exit(asyncio.run(_main(args)))


if __name__ == "__main__":
    main()
