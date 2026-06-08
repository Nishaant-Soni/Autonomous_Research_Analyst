"""Tests for the deterministic metric module + score CLI (plan 4.3, B1).

No DB / network / model. The plan's verify case is the orphan-citation test:
'on a crafted report with one orphan citation, citation accuracy < 100%'.
"""

import json
from pathlib import Path

from eval.metrics.deterministic import (
    citation_accuracy_aggregate,
    citation_accuracy_per_item,
)
from eval.score import score_run


# --- citation_accuracy_per_item ---------------------------------------------


def test_orphan_citation_drops_accuracy_below_100():
    # The plan's verify case: one orphan among five cited sentences.
    result = {"failed": False, "stripped_fraction": 0.2}
    assert citation_accuracy_per_item(result) == 0.8


def test_no_orphans_is_perfect_accuracy():
    result = {"failed": False, "stripped_fraction": 0.0}
    assert citation_accuracy_per_item(result) == 1.0


def test_failed_item_returns_none_not_zero():
    # Distinguishing "scored 0" from "wasn't scored" is the whole point of the None signal.
    assert citation_accuracy_per_item({"failed": True, "error": "boom"}) is None


# --- citation_accuracy_aggregate --------------------------------------------


def test_aggregate_skips_failed_items():
    per_item = {"a": 1.0, "b": 0.8, "c": None}
    agg = citation_accuracy_aggregate(per_item)
    assert agg["n_scored"] == 2
    assert agg["n_failed"] == 1
    assert agg["mean"] == 0.9
    assert agg["min"] == 0.8 and agg["max"] == 1.0


def test_aggregate_all_failed_yields_none_not_crash():
    agg = citation_accuracy_aggregate({"a": None, "b": None})
    assert agg["n_scored"] == 0
    assert agg["n_failed"] == 2
    assert agg["mean"] is None
    assert agg["min"] is None and agg["max"] is None


def test_aggregate_empty_input():
    agg = citation_accuracy_aggregate({})
    assert agg == {
        "n_scored": 0,
        "n_failed": 0,
        "mean": None,
        "min": None,
        "max": None,
    }


# --- score_run end-to-end on a synthetic run dir ----------------------------


def _make_item(run_dir: Path, item_id: str, result: dict) -> None:
    item_dir = run_dir / item_id
    item_dir.mkdir(parents=True)
    (item_dir / "result.json").write_text(json.dumps(result))


def test_score_run_reads_artifacts_and_writes_scores_json(tmp_path: Path):
    run_dir = tmp_path / "20990101T000000Z"
    run_dir.mkdir()
    _make_item(run_dir, "ok1", {"failed": False, "stripped_fraction": 0.0})
    _make_item(run_dir, "ok2", {"failed": False, "stripped_fraction": 0.4})
    _make_item(run_dir, "bad", {"failed": True, "error": "boom"})

    scores = score_run(run_dir)

    # Returns the same dict it persisted to scores.json.
    on_disk = json.loads((run_dir / "scores.json").read_text())
    assert scores == on_disk

    assert scores["item_count"] == 3
    citation = scores["metrics"]["citation_accuracy"]
    assert citation["per_item"] == {"ok1": 1.0, "ok2": 0.6, "bad": None}
    assert citation["aggregate"]["n_scored"] == 2
    assert citation["aggregate"]["n_failed"] == 1
    assert citation["aggregate"]["mean"] == 0.8


def test_score_run_skips_subdirs_without_result_json(tmp_path: Path):
    # An item dir that the Run stage left half-written (no result.json) shouldn't crash
    # the score stage — it just gets skipped with a warning.
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _make_item(run_dir, "ok", {"failed": False, "stripped_fraction": 0.0})
    (run_dir / "halfwritten").mkdir()  # exists but no result.json

    scores = score_run(run_dir)

    assert scores["item_count"] == 1
    assert "ok" in scores["metrics"]["citation_accuracy"]["per_item"]
