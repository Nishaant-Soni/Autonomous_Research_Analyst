"""Tests for the golden eval dataset loader (IMPLEMENTATION_PLAN.md 4.1).

Fast: no DB, no network, no model. The full retrievability check on corpus key_facts
(embed -> retrieve -> confirm support) belongs to A2; here we validate schema + that the
corpus docs referenced by the shipped dataset exist on disk.
"""

import json
from pathlib import Path

import pytest

from eval.dataset import _CORPUS_DIR, GoldenItem, load_golden


def _valid(**overrides) -> dict:
    item = {
        "id": "x",
        "question": "q?",
        "target": "web",
        "key_facts": ["a fact."],
        "acceptable_domains": ["arxiv.org"],
    }
    item.update(overrides)
    return item


def _write(tmp_path: Path, objs: list[dict]) -> Path:
    path = tmp_path / "golden.jsonl"
    path.write_text("\n".join(json.dumps(o) for o in objs))
    return path


def _many(n: int) -> list[dict]:
    return [_valid(id=f"id{i}") for i in range(n)]


# --- the shipped dataset ---------------------------------------------------------


def test_real_golden_loads_and_is_valid():
    items = load_golden()
    assert 15 <= len(items) <= 20
    assert len({it.id for it in items}) == len(items)  # unique ids
    assert all(it.key_facts for it in items)


def test_real_corpus_items_reference_existing_docs():
    for it in load_golden():
        if it.target == "corpus":
            assert it.source_docs, f"{it.id} is corpus but has no source_docs"
            for doc in it.source_docs:
                assert (_CORPUS_DIR / doc).is_file(), f"{it.id} -> missing {doc}"


# --- schema / loader behavior ----------------------------------------------------


def test_reference_joins_key_facts():
    item = GoldenItem(**_valid(key_facts=["one.", "two."]))
    assert item.reference == "one. two."


def test_rejects_malformed_line(tmp_path):
    path = tmp_path / "golden.jsonl"
    path.write_text("not json")
    with pytest.raises(ValueError, match="invalid golden item"):
        load_golden(path)


def test_rejects_count_below_minimum(tmp_path):
    path = _write(tmp_path, _many(3))
    with pytest.raises(ValueError, match="expected 15-20"):
        load_golden(path)


def test_rejects_duplicate_ids(tmp_path):
    objs = _many(16)
    objs[5]["id"] = objs[0]["id"]
    path = _write(tmp_path, objs)
    with pytest.raises(ValueError, match="duplicate golden ids"):
        load_golden(path)


def test_rejects_corpus_item_without_source_docs(tmp_path):
    objs = _many(15) + [_valid(id="c", target="corpus", source_docs=[])]
    path = _write(tmp_path, objs)
    with pytest.raises(ValueError, match="must list source_docs"):
        load_golden(path)


def test_rejects_corpus_item_with_missing_doc(tmp_path):
    objs = _many(15) + [_valid(id="c", target="corpus", source_docs=["nope.md"])]
    path = _write(tmp_path, objs)
    with pytest.raises(ValueError, match="missing doc"):
        load_golden(path, corpus_dir=tmp_path)


def test_rejects_corpus_item_whose_key_fact_is_not_verbatim_in_source_doc(tmp_path):
    # Doc exists but doesn't contain the asserted fact -> A1 must fail loud, not defer.
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc.md").write_text("Some unrelated prose about widgets and gears.")
    objs = _many(15) + [
        _valid(
            id="c",
            target="corpus",
            source_docs=["doc.md"],
            key_facts=["A fact that does not appear in the doc."],
            acceptable_domains=[],
        )
    ]
    path = _write(tmp_path, objs)
    with pytest.raises(ValueError, match="not verbatim"):
        load_golden(path, corpus_dir=corpus)


def test_accepts_corpus_item_whose_key_facts_are_verbatim_modulo_whitespace(tmp_path):
    # Hard line breaks inside the doc must not defeat the verbatim check.
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc.md").write_text(
        "Chunks that are too large dilute the embedding\nwith multiple topics."
    )
    objs = _many(15) + [
        _valid(
            id="c",
            target="corpus",
            source_docs=["doc.md"],
            key_facts=[
                "Chunks that are too large dilute the embedding with multiple topics."
            ],
            acceptable_domains=[],
        )
    ]
    path = _write(tmp_path, objs)
    items = load_golden(path, corpus_dir=corpus)
    assert any(it.id == "c" for it in items)


def test_rejects_unsupported_target_value(tmp_path):
    # "both" used to be allowed by the type but never validated; drop it from the schema.
    objs = _many(15) + [_valid(id="x", target="both")]
    path = _write(tmp_path, objs)
    with pytest.raises(ValueError, match="invalid golden item"):
        load_golden(path)


def test_rejects_web_item_without_domains(tmp_path):
    objs = _many(15) + [_valid(id="w", target="web", acceptable_domains=[])]
    path = _write(tmp_path, objs)
    with pytest.raises(ValueError, match="must list acceptable_domains"):
        load_golden(path)
