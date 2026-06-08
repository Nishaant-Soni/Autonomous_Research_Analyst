"""Tests for eval.retrievability (plan 4.1 mitigation, A2; no DB/network/embedding model).

Uses a stub retriever so we can assert the matching + source-doc attribution logic in
isolation. The live behavior of `rag_retrieve` is covered by existing retrieval tests.
"""

from pathlib import Path

from app.models.evidence import Evidence
from eval.dataset import GoldenItem
from eval.retrievability import check_corpus_retrievability


def _item(facts: list[str], source_docs: list[str], item_id: str = "c") -> GoldenItem:
    return GoldenItem(
        id=item_id,
        question="q?",
        target="corpus",
        key_facts=facts,
        source_docs=source_docs,
    )


def _make_corpus(tmp_path: Path, docs: dict[str, str]) -> Path:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    for name, body in docs.items():
        (corpus / name).write_text(body)
    return corpus


def _stub_retriever(returns: dict[str, list[str]]):
    """Map: query (key_fact) -> list of chunk contents that should come back from rag_retrieve."""

    def _retrieve(query: str, k: int) -> list[Evidence]:
        return [
            Evidence(content=c, source_chunk_id=i, retriever="rag")
            for i, c in enumerate(returns.get(query, []))
        ]

    return _retrieve


def test_passes_when_chunk_verbatim_contains_fact_from_named_source_doc(tmp_path: Path):
    # Real chunks from `chunk_text` are substrings of their source doc, so the stub returns
    # a piece of the doc verbatim.
    doc_text = "Some prose. The sky is blue. More prose."
    corpus = _make_corpus(tmp_path, {"doc.md": doc_text})
    items = [_item(facts=["The sky is blue."], source_docs=["doc.md"])]
    retriever = _stub_retriever({"The sky is blue.": [doc_text]})

    out = check_corpus_retrievability(items, corpus_dir=corpus, retriever=retriever)

    assert out["all_passed"] is True
    assert out["items"]["c"]["passed"] is True
    assert out["items"]["c"]["facts"][0]["matched_doc"] == "doc.md"


def test_fails_when_fact_not_in_any_retrieved_chunk(tmp_path: Path):
    corpus = _make_corpus(tmp_path, {"doc.md": "The sky is blue."})
    items = [_item(facts=["The sky is blue."], source_docs=["doc.md"])]
    retriever = _stub_retriever(
        {"The sky is blue.": ["completely unrelated text", "more unrelated text"]}
    )

    out = check_corpus_retrievability(items, corpus_dir=corpus, retriever=retriever)

    assert out["all_passed"] is False
    fact = out["items"]["c"]["facts"][0]
    assert fact["found"] is False
    assert fact["matched_doc"] is None


def test_fails_when_chunk_came_from_unlisted_source_doc(tmp_path: Path):
    # Item names doc_a as its source, but the retrieved chunk actually came from doc_b.
    # Even if the chunk verbatim-contains the fact, the item shouldn't pass — the dataset
    # is misattributed, which would silently break Ragas context_recall later.
    corpus = _make_corpus(
        tmp_path,
        {
            "doc_a.md": "doc_a is about widgets.",
            "doc_b.md": "doc_b says: the sky is blue.",
        },
    )
    items = [_item(facts=["the sky is blue"], source_docs=["doc_a.md"])]
    retriever = _stub_retriever({"the sky is blue": ["doc_b says: the sky is blue."]})

    out = check_corpus_retrievability(items, corpus_dir=corpus, retriever=retriever)

    assert out["all_passed"] is False
    assert out["items"]["c"]["facts"][0]["found"] is False


def test_normalizes_whitespace_so_line_wraps_dont_defeat_match(tmp_path: Path):
    # Doc has the supporting text split across a line break (typical of markdown soft-wraps).
    # Both the chunk and the doc-text are wrapped; both sides normalize before matching.
    doc_text = "preamble. Chunks that are too large\ndilute the embedding. tail."
    corpus = _make_corpus(tmp_path, {"doc.md": doc_text})
    items = [
        _item(
            facts=["Chunks that are too large dilute the embedding."],
            source_docs=["doc.md"],
        )
    ]
    retriever = _stub_retriever(
        {"Chunks that are too large dilute the embedding.": [doc_text]}
    )

    out = check_corpus_retrievability(items, corpus_dir=corpus, retriever=retriever)

    assert out["items"]["c"]["passed"] is True


def test_skips_non_corpus_items(tmp_path: Path):
    # Web items should not contribute anything to the result; this is a corpus-only check.
    corpus = _make_corpus(tmp_path, {})
    web_item = GoldenItem(
        id="w",
        question="q?",
        target="web",
        key_facts=["a."],
        acceptable_domains=["arxiv.org"],
    )

    out = check_corpus_retrievability([web_item], corpus_dir=corpus)

    assert out["items"] == {}
    assert out["all_passed"] is True
