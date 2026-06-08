"""Tests for the Score-stage artifact loader (plan 4.5, B2; no DB/network/ragas)."""

import json
from pathlib import Path

import pytest

from eval.metrics.artifacts import load_item_samples


def _write_item(
    run_dir: Path,
    item_id: str,
    result: dict,
    report: str = "",
    evidence: list[dict] | None = None,
) -> None:
    d = run_dir / item_id
    d.mkdir(parents=True)
    (d / "result.json").write_text(json.dumps(result))
    if report:
        (d / "report.md").write_text(report)
    if evidence is not None:
        (d / "evidence.jsonl").write_text("\n".join(json.dumps(e) for e in evidence))


def _good_result(item_id: str = "x") -> dict:
    return {
        "id": item_id,
        "question": "q?",
        "target": "web",
        "reference": "the truth.",
        "failed": False,
        "stripped_fraction": 0.0,
    }


def test_loads_one_sample_with_correct_shape(tmp_path: Path):
    _write_item(
        tmp_path,
        "x",
        _good_result("x"),
        report="# Report\n\nfindings [1]\n\n[1] https://a",
        evidence=[
            {
                "content": "alpha",
                "source_url": "https://a",
                "retriever": "web",
                "claim": "c",
            },
            {"content": "beta", "source_chunk_id": 7, "retriever": "rag", "claim": "c"},
        ],
    )

    [sample] = load_item_samples(tmp_path)

    assert sample["id"] == "x"
    assert sample["question"] == "q?"
    assert sample["target"] == "web"
    assert sample["reference"] == "the truth."
    assert sample["answer"].startswith("# Report")
    assert sample["contexts"] == ["alpha", "beta"]


def test_skips_failed_items(tmp_path: Path):
    _write_item(tmp_path, "ok", _good_result("ok"), report="r", evidence=[])
    # Failed item — minimal result.json with no report/evidence on disk.
    (tmp_path / "bad").mkdir()
    (tmp_path / "bad" / "result.json").write_text(
        json.dumps(
            {
                "id": "bad",
                "question": "q?",
                "target": "web",
                "failed": True,
                "error": "boom",
            }
        )
    )

    samples = load_item_samples(tmp_path)

    assert [s["id"] for s in samples] == ["ok"]


def test_raises_loudly_on_half_written_successful_item(tmp_path: Path):
    # result.json claims success but the writer never landed (Run-stage bug); a Ragas pass
    # against an empty answer would silently score zero — surface instead.
    d = tmp_path / "x"
    d.mkdir()
    (d / "result.json").write_text(json.dumps(_good_result("x")))
    # NO report.md or evidence.jsonl

    with pytest.raises(FileNotFoundError, match="result.json says not failed"):
        load_item_samples(tmp_path)


def test_orders_samples_by_id(tmp_path: Path):
    for item_id in ["c", "a", "b"]:
        _write_item(tmp_path, item_id, _good_result(item_id), report="r", evidence=[])

    samples = load_item_samples(tmp_path)

    assert [s["id"] for s in samples] == ["a", "b", "c"]


def test_skips_dirs_without_result_json(tmp_path: Path):
    _write_item(tmp_path, "ok", _good_result("ok"), report="r", evidence=[])
    (tmp_path / "halfwritten").mkdir()  # no result.json

    samples = load_item_samples(tmp_path)

    assert [s["id"] for s in samples] == ["ok"]
