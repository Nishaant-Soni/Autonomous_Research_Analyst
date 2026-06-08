"""Render an A/B comparison between two scored eval runs (plan 4.7, C2).

Reads `scores.json` from two run dirs and writes a committed Markdown comparison report
at `eval/results/<name>.md`. Designed for the critic-loop A/B (the PRD's headline number)
and reusable for any future A/B (e.g. embedding A/B if 4.6 is un-deferred).

    python -m eval.compare --a <run_id_a> --b <run_id_b> --name critic_loop_AB \
        --label-a "Critic loop ON" --label-b "Critic loop OFF"
"""

import argparse
import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger("eval.compare")
_RUNS_DIR = Path(__file__).parent / "runs"
_RESULTS_DIR = Path(__file__).parent / "results"


def _load_scores(run_id: str) -> dict:
    path = _RUNS_DIR / run_id / "scores.json"
    if not path.is_file():
        raise SystemExit(
            f"no scores.json for {run_id}; run `python -m eval.score --run-id {run_id}` first"
        )
    return json.loads(path.read_text())


def _mean(block: dict | None) -> float | None:
    return ((block or {}).get("aggregate") or {}).get("mean")


def _fmt_pct(v: float | None) -> str:
    return "n/a" if v is None else f"{v * 100:.1f}%"


def _fmt_seconds(v: float | None) -> str:
    return "n/a" if v is None else f"{v:.1f}s"


def _fmt_usd(v: float | None) -> str:
    return "n/a" if v is None else f"${v:.4f}"


def _delta_pct(a: float | None, b: float | None) -> str:
    """Δ between two percentage-style metrics, as `(B − A)` percentage points. The reader
    interprets the sign via the column header — for hallucination/latency/cost a positive
    delta means B is worse than A; for faithfulness it means B is better."""
    if a is None or b is None:
        return "n/a"
    diff = (b - a) * 100
    arrow = "↑" if diff > 0 else "↓" if diff < 0 else "—"
    sign = "+" if diff > 0 else ""
    return f"{sign}{diff:.1f}pp {arrow}"


def _delta_abs(a: float | None, b: float | None, formatter) -> str:
    if a is None or b is None:
        return "n/a"
    diff = b - a
    sign = "+" if diff > 0 else ""
    return f"{sign}{formatter(diff).replace('+', '')}".lstrip()


_HEADLINE_METRICS = [
    # (path, label, formatter) — direction is communicated by the column header "Δ (B − A)"
    ("ragas.faithfulness", "Faithfulness", _fmt_pct),
    ("ragas.answer_relevancy", "Answer relevancy", _fmt_pct),
    ("ragas.context_recall", "Context recall", _fmt_pct),
    ("citation_accuracy", "Citation accuracy", _fmt_pct),
    ("hallucination_rate", "Hallucination rate", _fmt_pct),
    ("latency_seconds", "Latency / item", _fmt_seconds),
    ("cost_usd", "Cost / item", _fmt_usd),
]


def _get_block(metrics: dict, path: str) -> dict | None:
    """`ragas.faithfulness` → metrics['ragas']['faithfulness'], etc."""
    cur: dict | object = metrics
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
        if cur is None:
            return None
    return cur if isinstance(cur, dict) else None


def render_comparison(
    scores_a: dict,
    scores_b: dict,
    label_a: str = "A",
    label_b: str = "B",
    headline_metric: str = "hallucination_rate",
    headline_direction: str = "down_is_good",
) -> str:
    """Render the A/B Markdown report. `headline_metric` is the single number featured at
    the top — for the C2 critic-loop A/B that's `hallucination_rate` (lower is better)."""
    m_a = scores_a.get("metrics", {})
    m_b = scores_b.get("metrics", {})

    lines: list[str] = []
    lines.append(f"# A/B comparison — {label_a} vs {label_b}")
    lines.append("")
    lines.append(
        f"- **{label_a}:** `{scores_a['run_id']}` ({scores_a['item_count']} items)"
    )
    lines.append(
        f"- **{label_b}:** `{scores_b['run_id']}` ({scores_b['item_count']} items)"
    )
    lines.append("")

    # --- Headline -----------------------------------------------------------
    # Pick the verb honestly from the data, not the caller's framing: if A is actually
    # *worse* on a down_is_good metric, "A cut X" would be a misleading lie. Surface the
    # data direction and let the reader judge.
    head_a = _mean(_get_block(m_a, headline_metric))
    head_b = _mean(_get_block(m_b, headline_metric))
    metric_label = headline_metric.replace("_", " ")
    if head_a is not None and head_b is not None:
        a_better = (
            head_a < head_b if headline_direction == "down_is_good" else head_a > head_b
        )
        better_label, better_v = (label_a, head_a) if a_better else (label_b, head_b)
        worse_v = head_b if a_better else head_a
        verb = "cut" if headline_direction == "down_is_good" else "lifted"
        delta_pp = abs(head_a - head_b) * 100
        if delta_pp < 1.0:
            # Within typical n=16 noise; do not claim a win.
            lines.append(
                f"## Headline\n\n**{label_a} vs {label_b} on {metric_label}: "
                f"{head_a * 100:.1f}% vs {head_b * 100:.1f}% (Δ {delta_pp:.1f}pp — within noise at this n).**"
            )
        else:
            lines.append(
                f"## Headline\n\n**{better_label} {verb} {metric_label} from "
                f"{worse_v * 100:.1f}% to {better_v * 100:.1f}% (Δ {delta_pp:.1f}pp).**"
            )
        lines.append("")

    # --- Side-by-side table -------------------------------------------------
    lines.append("## Headline metrics")
    lines.append("")
    lines.append(f"| Metric | {label_a} | {label_b} | Δ ({label_b} − {label_a}) |")
    lines.append("|---|---|---|---|")
    for path, label, formatter in _HEADLINE_METRICS:
        a_block = _get_block(m_a, path)
        b_block = _get_block(m_b, path)
        a_mean = _mean(a_block)
        b_mean = _mean(b_block)
        delta = (
            _delta_pct(a_mean, b_mean)
            if formatter is _fmt_pct
            else _delta_abs(a_mean, b_mean, formatter)
        )
        lines.append(
            f"| {label} | {formatter(a_mean)} | {formatter(b_mean)} | {delta} |"
        )
    lines.append("")

    # --- Per-item hallucination rate (the headline drill-down) --------------
    a_block = _get_block(m_a, "hallucination_rate")
    b_block = _get_block(m_b, "hallucination_rate")
    if a_block and b_block:
        per_a = a_block.get("per_item", {})
        per_b = b_block.get("per_item", {})
        ids = sorted(set(per_a) | set(per_b))
        lines.append("## Per-item hallucination rate")
        lines.append("")
        lines.append(f"| Item | {label_a} | {label_b} | Δ |")
        lines.append("|---|---|---|---|")
        for item_id in ids:
            a_v, b_v = per_a.get(item_id), per_b.get(item_id)
            lines.append(
                f"| `{item_id}` | {_fmt_pct(a_v)} | {_fmt_pct(b_v)} | "
                f"{_delta_pct(a_v, b_v)} |"
            )
        lines.append("")

    return "\n".join(lines)


def write_comparison(
    run_id_a: str,
    run_id_b: str,
    out_name: str,
    label_a: str,
    label_b: str,
    headline_metric: str,
    headline_direction: str,
) -> Path:
    scores_a = _load_scores(run_id_a)
    scores_b = _load_scores(run_id_b)
    md = render_comparison(
        scores_a,
        scores_b,
        label_a=label_a,
        label_b=label_b,
        headline_metric=headline_metric,
        headline_direction=headline_direction,
    )
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _RESULTS_DIR / f"{out_name}.md"
    out_path.write_text(md)
    return out_path


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--a", required=True, help="run_id A (the variant under test)")
    p.add_argument("--b", required=True, help="run_id B (the baseline / control)")
    p.add_argument("--name", required=True, help="output filename stem (no extension)")
    p.add_argument("--label-a", default="A")
    p.add_argument("--label-b", default="B")
    p.add_argument(
        "--headline-metric",
        default="hallucination_rate",
        help="dot-path into metrics for the headline number (default: hallucination_rate)",
    )
    p.add_argument(
        "--headline-direction",
        default="down_is_good",
        choices=["up_is_good", "down_is_good"],
    )
    return p.parse_args(argv)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    args = _parse_args(sys.argv[1:])
    out = write_comparison(
        args.a,
        args.b,
        args.name,
        label_a=args.label_a,
        label_b=args.label_b,
        headline_metric=args.headline_metric,
        headline_direction=args.headline_direction,
    )
    logger.info("wrote %s", out)


if __name__ == "__main__":
    main()
