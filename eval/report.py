"""Render the human-readable aggregate eval report (plan 4.5 finalize, B3.4).

Reads a run's cached score artifacts and writes `eval/results/<run-id>.md` — a small,
diff-friendly Markdown file that anchors the README's "look at these numbers" claim.
Per the plan decision under 4.5: per-run debug dirs (`eval/runs/<run-id>/`) stay
gitignored; this top-level results file IS committed so iterations are comparable.

    python -m eval.report                  # report on the latest run dir
    python -m eval.report --run-id <id>    # report on a specific run
"""

import argparse
import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger("eval.report")
_RUNS_DIR = Path(__file__).parent / "runs"
_RESULTS_DIR = Path(__file__).parent / "results"


def _latest_run_dir() -> Path:
    runs = sorted(p for p in _RUNS_DIR.iterdir() if p.is_dir())
    if not runs:
        raise SystemExit(f"no runs under {_RUNS_DIR}; run `python -m eval.run` first")
    return runs[-1]


def _fmt_pct(v: float | None) -> str:
    return "n/a" if v is None else f"{v * 100:.1f}%"


def _fmt_seconds(v: float | None) -> str:
    return "n/a" if v is None else f"{v:.1f}s"


def _fmt_usd(v: float | None) -> str:
    return "n/a" if v is None else f"${v:.4f}"


def _fmt_mean(block: dict, formatter) -> str:
    agg = block["aggregate"]
    mean_s = formatter(agg["mean"])
    if agg["n_failed"]:
        return f"{mean_s} (n={agg['n_scored']}, {agg['n_failed']} failed)"
    return f"{mean_s} (n={agg['n_scored']})"


def render_report(run_dir: Path) -> str:
    """Render the Markdown report for `run_dir` and return it as a string."""
    scores = json.loads((run_dir / "scores.json").read_text())
    meta_path = run_dir / "meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.is_file() else {}
    retrievability_path = run_dir / "retrievability.json"
    retrievability = (
        json.loads(retrievability_path.read_text())
        if retrievability_path.is_file()
        else None
    )

    m = scores.get("metrics", {})
    ragas = m.get("ragas", {})
    lines: list[str] = []
    lines.append(f"# Eval report — `{scores['run_id']}`")
    lines.append("")
    lines.append(f"- **Items scored:** {scores['item_count']}")
    if meta.get("limit"):
        lines.append(f"- **Limit:** {meta['limit']} (smoke run)")
    if retrievability is not None:
        lines.append(
            f"- **Corpus retrievability:** {'PASSED' if retrievability.get('all_passed') else 'FAILED'}"
        )
    lines.append("")

    # --- Headline table ----------------------------------------------------
    lines.append("## Headline metrics")
    lines.append("")
    lines.append("| Metric | Mean |")
    lines.append("|---|---|")

    if "ragas" in m and ragas:
        lines.append(f"| Faithfulness | {_fmt_mean(ragas['faithfulness'], _fmt_pct)} |")
        lines.append(
            f"| Answer relevancy | {_fmt_mean(ragas['answer_relevancy'], _fmt_pct)} |"
        )
        lines.append(
            f"| Context recall | {_fmt_mean(ragas['context_recall'], _fmt_pct)} |"
        )
    if "citation_accuracy" in m:
        lines.append(
            f"| Citation accuracy | {_fmt_mean(m['citation_accuracy'], _fmt_pct)} |"
        )
    if "hallucination_rate" in m:
        lines.append(
            f"| Hallucination rate (1 − faithfulness) | {_fmt_mean(m['hallucination_rate'], _fmt_pct)} |"
        )
    if "latency_seconds" in m:
        lines.append(
            f"| Latency / item | {_fmt_mean(m['latency_seconds'], _fmt_seconds)} |"
        )
    if "cost_usd" in m:
        lines.append(f"| Cost / item | {_fmt_mean(m['cost_usd'], _fmt_usd)} |")
    lines.append("")

    # --- Per-item breakdown ------------------------------------------------
    lines.append("## Per-item breakdown")
    lines.append("")
    lines.append(
        "| Item | Faith. | Ans.Rel. | Ctx.Recall | Cite.Acc. | Hallucination | Latency | Cost |"
    )
    lines.append("|---|---|---|---|---|---|---|---|")

    def _pi(block: dict | None) -> dict:
        return (block or {}).get("per_item", {})

    faith = _pi(ragas.get("faithfulness"))
    ans_rel = _pi(ragas.get("answer_relevancy"))
    ctx_rec = _pi(ragas.get("context_recall"))
    cite = _pi(m.get("citation_accuracy"))
    hallu = _pi(m.get("hallucination_rate"))
    lat = _pi(m.get("latency_seconds"))
    cost = _pi(m.get("cost_usd"))

    all_ids = sorted(
        set(faith) | set(ans_rel) | set(ctx_rec) | set(cite) | set(hallu) | set(lat)
    )
    for item_id in all_ids:
        lines.append(
            f"| `{item_id}` "
            f"| {_fmt_pct(faith.get(item_id))} "
            f"| {_fmt_pct(ans_rel.get(item_id))} "
            f"| {_fmt_pct(ctx_rec.get(item_id))} "
            f"| {_fmt_pct(cite.get(item_id))} "
            f"| {_fmt_pct(hallu.get(item_id))} "
            f"| {_fmt_seconds(lat.get(item_id))} "
            f"| {_fmt_usd(cost.get(item_id))} |"
        )
    lines.append("")

    if "cost_usd" not in m:
        lines.append(
            "_Cost unavailable: LangSmith key missing or trace lookup failed for this run._"
        )
        lines.append("")

    return "\n".join(lines)


def write_report(run_dir: Path) -> Path:
    """Render + persist the report. Returns the path written."""
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _RESULTS_DIR / f"{run_dir.name}.md"
    out_path.write_text(render_report(run_dir))
    return out_path


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
    if not (run_dir / "scores.json").is_file():
        raise SystemExit(
            f"no scores.json in {run_dir}; run `python -m eval.score` first"
        )
    out_path = write_report(run_dir)
    logger.info("wrote %s", out_path)


if __name__ == "__main__":
    main()
