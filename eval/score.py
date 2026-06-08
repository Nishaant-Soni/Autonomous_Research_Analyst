"""Score stage CLI (plan 4.5 architecture: Run -> Score -> Report).

Reads per-item `result.json` files under `eval/runs/<run-id>/` and writes a `scores.json`
alongside them. Designed to be extended: B2 will add Ragas metrics to the same file
(faithfulness/answer_relevance/context_recall + the derived hallucination_rate); B3 will
add latency/cost and the aggregate.

Usage:
    python -m eval.score                  # score the latest run dir
    python -m eval.score --run-id <id>    # score a specific run

This stage does NOT run the graph or call any LLM — that's the Run stage's job.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from eval.metrics.deterministic import (
    citation_accuracy_aggregate,
    citation_accuracy_per_item,
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


def score_run(run_dir: Path) -> dict:
    """Compute every deterministic metric defined so far. Writes `scores.json` and returns
    the same dict for caller inspection / tests."""
    results = _load_results(run_dir)
    per_item_citation = {
        item_id: citation_accuracy_per_item(res) for item_id, res in results.items()
    }
    scores = {
        "run_id": run_dir.name,
        "item_count": len(results),
        "metrics": {
            "citation_accuracy": {
                "aggregate": citation_accuracy_aggregate(per_item_citation),
                "per_item": per_item_citation,
            },
        },
    }
    (run_dir / "scores.json").write_text(json.dumps(scores, indent=2))
    return scores


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-id", help="run dir under eval/runs/ (defaults to latest)")
    return p.parse_args(argv)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    args = _parse_args(sys.argv[1:])
    run_dir = _RUNS_DIR / args.run_id if args.run_id else _latest_run_dir()
    if not run_dir.is_dir():
        raise SystemExit(f"run dir not found: {run_dir}")
    logger.info("scoring %s", run_dir)
    scores = score_run(run_dir)
    agg = scores["metrics"]["citation_accuracy"]["aggregate"]
    logger.info(
        "citation_accuracy: mean=%s (scored=%s, failed=%s)",
        f"{agg['mean']:.3f}" if agg["mean"] is not None else "n/a",
        agg["n_scored"],
        agg["n_failed"],
    )
    logger.info("scores written to %s", run_dir / "scores.json")


if __name__ == "__main__":
    main()
