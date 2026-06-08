"""Tests for the aggregate report renderer (plan 4.5 finalize, B3.4)."""

import json
from pathlib import Path

from eval.report import render_report, write_report


def _scores(extras: dict | None = None) -> dict:
    base = {
        "run_id": "20990101T000000Z",
        "item_count": 2,
        "metrics": {
            "citation_accuracy": {
                "aggregate": {
                    "n_scored": 2,
                    "n_failed": 0,
                    "mean": 1.0,
                    "min": 1.0,
                    "max": 1.0,
                },
                "per_item": {"a": 1.0, "b": 1.0},
            },
            "latency_seconds": {
                "aggregate": {
                    "n_scored": 2,
                    "n_failed": 0,
                    "mean": 60.5,
                    "min": 31.0,
                    "max": 90.0,
                },
                "per_item": {"a": 90.0, "b": 31.0},
            },
            "ragas": {
                "faithfulness": {
                    "aggregate": {
                        "n_scored": 2,
                        "n_failed": 0,
                        "mean": 0.94,
                        "min": 0.88,
                        "max": 1.0,
                    },
                    "per_item": {"a": 0.88, "b": 1.0},
                },
                "answer_relevancy": {
                    "aggregate": {
                        "n_scored": 2,
                        "n_failed": 0,
                        "mean": 0.95,
                        "min": 0.92,
                        "max": 0.98,
                    },
                    "per_item": {"a": 0.92, "b": 0.98},
                },
                "context_recall": {
                    "aggregate": {
                        "n_scored": 2,
                        "n_failed": 0,
                        "mean": 1.0,
                        "min": 1.0,
                        "max": 1.0,
                    },
                    "per_item": {"a": 1.0, "b": 1.0},
                },
            },
            "hallucination_rate": {
                "aggregate": {
                    "n_scored": 2,
                    "n_failed": 0,
                    "mean": 0.06,
                    "min": 0.0,
                    "max": 0.12,
                },
                "per_item": {"a": 0.12, "b": 0.0},
            },
        },
    }
    if extras:
        base["metrics"].update(extras)
    return base


def _make_run_dir(tmp_path: Path, scores: dict, with_meta: bool = True) -> Path:
    run_dir = tmp_path / scores["run_id"]
    run_dir.mkdir()
    (run_dir / "scores.json").write_text(json.dumps(scores))
    if with_meta:
        (run_dir / "meta.json").write_text(json.dumps({"limit": 0, "item_count": 2}))
    return run_dir


def test_renders_headline_table_with_all_metrics(tmp_path: Path):
    cost_block = {
        "cost_usd": {
            "aggregate": {
                "n_scored": 2,
                "n_failed": 0,
                "mean": 0.0123,
                "min": 0.01,
                "max": 0.015,
            },
            "per_item": {"a": 0.015, "b": 0.01},
        }
    }
    run_dir = _make_run_dir(tmp_path, _scores(cost_block))

    md = render_report(run_dir)

    assert "# Eval report — `20990101T000000Z`" in md
    assert "| Faithfulness | 94.0%" in md
    assert "| Citation accuracy | 100.0%" in md
    assert "| Hallucination rate (1 − faithfulness) | 6.0%" in md
    assert "| Latency / item | 60.5s" in md
    assert "| Cost / item | $0.0123" in md
    assert "| `a` |" in md and "| `b` |" in md  # per-item rows
    # No "cost unavailable" footer when cost is present.
    assert "Cost unavailable" not in md


def test_renders_cost_unavailable_when_missing(tmp_path: Path):
    run_dir = _make_run_dir(tmp_path, _scores())  # no cost_usd block

    md = render_report(run_dir)

    assert "Cost unavailable" in md
    # Per-item cost column shows n/a, not a hard zero.
    assert "$" not in md or "$0.0" not in md


def test_failed_items_surface_in_aggregate_line(tmp_path: Path):
    scores = _scores()
    scores["metrics"]["citation_accuracy"]["aggregate"] = {
        "n_scored": 1,
        "n_failed": 1,
        "mean": 0.8,
        "min": 0.8,
        "max": 0.8,
    }
    run_dir = _make_run_dir(tmp_path, scores)

    md = render_report(run_dir)

    assert "Citation accuracy | 80.0% (n=1, 1 failed)" in md


def test_write_report_persists_under_results(tmp_path: Path, monkeypatch):
    run_dir = _make_run_dir(tmp_path, _scores())
    results_dir = tmp_path / "results"
    monkeypatch.setattr("eval.report._RESULTS_DIR", results_dir)

    out_path = write_report(run_dir)

    assert out_path == results_dir / "20990101T000000Z.md"
    assert out_path.is_file()
    assert "Eval report" in out_path.read_text()


def test_renders_without_meta_or_retrievability(tmp_path: Path):
    # An old/partial run dir might be missing meta.json/retrievability.json — should still render.
    run_dir = _make_run_dir(tmp_path, _scores(), with_meta=False)

    md = render_report(run_dir)

    assert "# Eval report" in md
    assert "Corpus retrievability" not in md
