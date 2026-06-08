"""Tests for the A/B comparison renderer (plan 4.7, C2; no network)."""

import json
from pathlib import Path

from eval.compare import render_comparison, write_comparison


def _scores(run_id: str, hallucination_mean: float, per_item: dict[str, float]) -> dict:
    return {
        "run_id": run_id,
        "item_count": len(per_item),
        "metrics": {
            "ragas": {
                "faithfulness": {
                    "aggregate": {
                        "n_scored": len(per_item),
                        "n_failed": 0,
                        "mean": 1.0 - hallucination_mean,
                        "min": 0.0,
                        "max": 1.0,
                    },
                    "per_item": {k: 1.0 - v for k, v in per_item.items()},
                },
                "answer_relevancy": {
                    "aggregate": {
                        "n_scored": len(per_item),
                        "n_failed": 0,
                        "mean": 0.9,
                        "min": 0.0,
                        "max": 1.0,
                    },
                    "per_item": {},
                },
                "context_recall": {
                    "aggregate": {
                        "n_scored": len(per_item),
                        "n_failed": 0,
                        "mean": 0.9,
                        "min": 0.0,
                        "max": 1.0,
                    },
                    "per_item": {},
                },
            },
            "hallucination_rate": {
                "aggregate": {
                    "n_scored": len(per_item),
                    "n_failed": 0,
                    "mean": hallucination_mean,
                    "min": min(per_item.values()),
                    "max": max(per_item.values()),
                },
                "per_item": per_item,
            },
        },
    }


def test_headline_attributes_improvement_to_the_actually_better_side():
    # A is clearly better on hallucination rate (down_is_good). Verb should say so.
    a = _scores("with-critic", 0.055, {"item1": 0.0, "item2": 0.11})
    b = _scores("no-critic", 0.140, {"item1": 0.20, "item2": 0.08})

    md = render_comparison(a, b, label_a="Critic ON", label_b="Critic OFF")

    assert "**Critic ON cut hallucination rate from 14.0% to 5.5%" in md
    assert "| Hallucination rate | 5.5% | 14.0% |" in md


def test_headline_flips_when_b_is_actually_better():
    # B is better — the headline must attribute the cut to B, not lie about A.
    a = _scores("worse", 0.140, {"item": 0.14})
    b = _scores("better", 0.055, {"item": 0.055})

    md = render_comparison(a, b, label_a="A", label_b="B")

    assert "**B cut hallucination rate from 14.0% to 5.5%" in md
    assert "A cut" not in md


def test_headline_calls_out_noise_when_delta_under_one_pp():
    # The C2 real-world result: 5.5% vs 4.8% — under 1pp; do NOT claim a win either way.
    a = _scores("on", 0.055, {"item": 0.055})
    b = _scores("off", 0.048, {"item": 0.048})

    md = render_comparison(a, b, label_a="ON", label_b="OFF")

    assert "within noise" in md
    assert "cut hallucination" not in md
    assert "lifted hallucination" not in md


def test_per_item_table_includes_all_ids_from_both_runs():
    a = _scores("a", 0.05, {"only_a": 0.05, "shared": 0.1})
    b = _scores("b", 0.10, {"shared": 0.15, "only_b": 0.20})

    md = render_comparison(a, b)

    assert "| `only_a` |" in md and "| `only_b` |" in md and "| `shared` |" in md


def test_missing_metric_in_one_run_renders_na(tmp_path: Path):
    a = _scores("a", 0.05, {"x": 0.05})
    b = _scores("b", 0.10, {"x": 0.10})
    # Strip cost block from both — it never ran with --skip-ragas etc.
    md = render_comparison(a, b)
    # Cost is not in our test scores, so the row should render n/a / n/a / n/a.
    assert "| Cost / item | n/a | n/a | n/a |" in md


def test_write_persists_under_results(tmp_path: Path, monkeypatch):
    runs_dir = tmp_path / "runs"
    results_dir = tmp_path / "results"
    (runs_dir / "a").mkdir(parents=True)
    (runs_dir / "b").mkdir(parents=True)
    (runs_dir / "a" / "scores.json").write_text(
        json.dumps(_scores("a", 0.05, {"x": 0.05}))
    )
    (runs_dir / "b" / "scores.json").write_text(
        json.dumps(_scores("b", 0.10, {"x": 0.10}))
    )
    monkeypatch.setattr("eval.compare._RUNS_DIR", runs_dir)
    monkeypatch.setattr("eval.compare._RESULTS_DIR", results_dir)

    out = write_comparison(
        "a",
        "b",
        "critic_loop_AB",
        label_a="ON",
        label_b="OFF",
        headline_metric="hallucination_rate",
        headline_direction="down_is_good",
    )

    assert out == results_dir / "critic_loop_AB.md"
    assert "ON cut hallucination rate" in out.read_text()
