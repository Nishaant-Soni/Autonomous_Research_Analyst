"""Score stage CLI (plan 4.5 architecture: Run -> Score -> Report).

Reads per-item `result.json` files under `eval/runs/<run-id>/` and writes a `scores.json`
alongside them. Designed to be extended: B2 will add Ragas metrics to the same file
(faithfulness/answer_relevance/context_recall + the derived hallucination_rate); B3 will
add latency/cost and the aggregate.

Usage:
    python -m eval.score                  # score the latest run dir (deterministic + Ragas)
    python -m eval.score --run-id <id>    # score a specific run
    python -m eval.score --skip-ragas     # skip the Ragas pass (no LLM-judge cost)

This stage does NOT re-run the graph — it only reads cached artifacts. Ragas does call
the judge LLM (OpenAI), so each non-skipped run incurs token cost.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from eval.metrics.artifacts import load_item_samples
from eval.metrics.deterministic import (
    aggregate,
    citation_accuracy_per_item,
    latency_per_item,
)

logger = logging.getLogger("eval.score")
_RUNS_DIR = Path(__file__).parent / "runs"


def _latest_run_dir() -> Path:
    runs = sorted(p for p in _RUNS_DIR.iterdir() if p.is_dir())
    if not runs:
        raise SystemExit(f"no runs under {_RUNS_DIR}; run `python -m eval.run` first")
    return runs[-1]


def _load_results(run_dir: Path) -> dict[str, dict]:
    """Map item_id -> result_json. Each item lives in its own subdir with `result.json`."""
    results: dict[str, dict] = {}
    for item_dir in sorted(p for p in run_dir.iterdir() if p.is_dir()):
        result_path = item_dir / "result.json"
        if not result_path.is_file():
            logger.warning("skipping %s: no result.json", item_dir.name)
            continue
        results[item_dir.name] = json.loads(result_path.read_text())
    return results


def score_run(run_dir: Path, skip_ragas: bool = False) -> dict:
    """Compute every Score-stage metric and write `scores.json`. Returns the same dict.

    Deterministic metrics always run (cheap, no LLM). Ragas runs by default; pass
    `skip_ragas=True` to skip its judge-LLM cost (e.g. when iterating on the deterministic
    path or when the eval extra isn't installed)."""
    results = _load_results(run_dir)
    per_item_citation = {
        item_id: citation_accuracy_per_item(res) for item_id, res in results.items()
    }
    per_item_latency = {
        item_id: latency_per_item(res) for item_id, res in results.items()
    }
    metrics: dict = {
        "citation_accuracy": {
            "aggregate": aggregate(per_item_citation),
            "per_item": per_item_citation,
        },
        "latency_seconds": {
            "aggregate": aggregate(per_item_latency),
            "per_item": per_item_latency,
        },
    }

    if not skip_ragas:
        # Lazy import — the Ragas extra isn't required for deterministic-only scoring.
        from eval.metrics.ragas_scorer import score_with_ragas

        samples = load_item_samples(run_dir)
        ragas_scores = score_with_ragas(samples)
        metrics["ragas"] = ragas_scores["ragas"]
        metrics["hallucination_rate"] = ragas_scores["hallucination_rate"]

    # Cost from LangSmith token counts (B3.3). Degrades cleanly: no key → no cost block.
    from eval.metrics.cost import fetch_cost_per_item

    per_item_cost = fetch_cost_per_item(run_dir.name, list(results.keys()))
    if per_item_cost is not None:
        metrics["cost_usd"] = {
            "aggregate": aggregate(per_item_cost),
            "per_item": per_item_cost,
        }

    scores = {
        "run_id": run_dir.name,
        "item_count": len(results),
        "metrics": metrics,
    }
    (run_dir / "scores.json").write_text(json.dumps(scores, indent=2))
    return scores


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-id", help="run dir under eval/runs/ (defaults to latest)")
    p.add_argument(
        "--skip-ragas",
        action="store_true",
        help="skip the Ragas judge pass (deterministic metrics only)",
    )
    return p.parse_args(argv)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    args = _parse_args(sys.argv[1:])
    run_dir = _RUNS_DIR / args.run_id if args.run_id else _latest_run_dir()
    if not run_dir.is_dir():
        raise SystemExit(f"run dir not found: {run_dir}")
    logger.info("scoring %s (skip_ragas=%s)", run_dir, args.skip_ragas)
    scores = score_run(run_dir, skip_ragas=args.skip_ragas)
    for name, block in scores["metrics"].items():
        # Each block is either {aggregate, per_item} (citation_accuracy, hallucination_rate)
        # or {metric_name: {aggregate, per_item}} (the ragas block).
        if "aggregate" in block:
            agg = block["aggregate"]
            mean_s = f"{agg['mean']:.3f}" if agg["mean"] is not None else "n/a"
            logger.info(
                "%s: mean=%s (scored=%s, failed=%s)",
                name,
                mean_s,
                agg["n_scored"],
                agg["n_failed"],
            )
        else:
            for sub_name, sub_block in block.items():
                agg = sub_block["aggregate"]
                mean_s = f"{agg['mean']:.3f}" if agg["mean"] is not None else "n/a"
                logger.info(
                    "%s.%s: mean=%s (scored=%s, failed=%s)",
                    name,
                    sub_name,
                    mean_s,
                    agg["n_scored"],
                    agg["n_failed"],
                )
    logger.info("scores written to %s", run_dir / "scores.json")


if __name__ == "__main__":
    main()
