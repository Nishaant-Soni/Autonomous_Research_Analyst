"""Deterministic retrievability check for corpus key_facts (plan 4.1 mitigation).

For each corpus item's key_fact, embed it (via the production `embed_query`), retrieve
the top-k chunks from the corpus (the production `rag_retrieve`), and pass iff:

  (a) a retrieved chunk *verbatim* contains the fact (whitespace-normalized), AND
  (b) that chunk's content is found in one of the item's named `source_docs`.

(b) guards against false positives where another corpus doc happens to share wording.
The check uses the embedder + retriever the real pipeline uses, so a fact that passes here
is one we know the system can actually surface — the structural prerequisite for
`context_recall` (B2) to even be meaningful.

A2-scoped: this is NOT a metric (B1's job). It only guarantees the dataset isn't broken.
"""

from pathlib import Path
from typing import Callable

from app.retrieval.rag import rag_retrieve
from eval.dataset import GoldenItem

_CORPUS_DIR = Path(__file__).parent / "corpus"


def _default_retriever(query: str, k: int) -> list:
    # Eval corpus is ingested with user_id=NULL → opt into the unscoped path explicitly,
    # since rag_retrieve is fail-closed and would otherwise raise on user_id=None.
    return rag_retrieve(query, k, allow_all_users=True)


def _ws(text: str) -> str:
    """Collapse whitespace; mirrors `eval.dataset._normalize_ws` (substring matching across
    line wraps)."""
    return " ".join(text.split())


def check_corpus_retrievability(
    items: list[GoldenItem],
    k: int = 5,
    corpus_dir: Path = _CORPUS_DIR,
    retriever: Callable[[str, int], list] = _default_retriever,
) -> dict:
    """Run the check across every corpus-targeted item. Returns:

    {
      "all_passed": bool,
      "items": {
        item_id: {
          "passed": bool,
          "facts": [{"fact": str, "found": bool, "matched_doc": str|None}, ...],
        },
      },
    }
    """
    # Pre-read source docs once (ws-normalized) so source-doc attribution is cheap.
    doc_text_ws: dict[str, str] = {}
    for item in items:
        if item.target != "corpus":
            continue
        for doc in item.source_docs:
            if doc not in doc_text_ws:
                doc_text_ws[doc] = _ws((corpus_dir / doc).read_text())

    out: dict = {"items": {}}
    all_passed = True
    for item in items:
        if item.target != "corpus":
            continue
        fact_results = []
        item_passed = True
        for fact in item.key_facts:
            fact_ws = _ws(fact)
            chunks = retriever(fact, k)
            matched_doc = None
            for ch in chunks:
                chunk_ws = _ws(ch.content)
                if fact_ws not in chunk_ws:
                    continue
                # Chunk verbatim-contains the fact; now confirm it came from a named source_doc.
                for doc in item.source_docs:
                    if chunk_ws in doc_text_ws[doc]:
                        matched_doc = doc
                        break
                if matched_doc:
                    break
            found = matched_doc is not None
            fact_results.append(
                {"fact": fact, "found": found, "matched_doc": matched_doc}
            )
            if not found:
                item_passed = False
        out["items"][item.id] = {"passed": item_passed, "facts": fact_results}
        all_passed = all_passed and item_passed

    out["all_passed"] = all_passed
    return out
