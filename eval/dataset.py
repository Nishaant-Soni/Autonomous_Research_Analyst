"""Golden eval dataset (IMPLEMENTATION_PLAN.md 4.1).

Loads and schema-validates `eval/golden.jsonl`: 15-20 research questions, each with a
target evidence source, reference key facts, and either acceptable web domains (web
items) or supporting corpus docs (corpus items).

`key_facts` is the ground truth for Ragas `context_recall` (4.2): the loader exposes it
joined into a single `reference` string, which is the shape Ragas consumes. Web items
state evergreen consensus facts findable on `acceptable_domains`; corpus items state facts
that are verbatim-supported by a doc under `eval/corpus/` (named in `source_docs`), so
their retrievability can be checked deterministically in A2.
"""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

_EVAL_DIR = Path(__file__).parent
_CORPUS_DIR = _EVAL_DIR / "corpus"
_GOLDEN_PATH = _EVAL_DIR / "golden.jsonl"
_MIN_ITEMS = 15
_MAX_ITEMS = 20


class GoldenItem(BaseModel):
    """One golden question. `source_docs` lists corpus filenames (under eval/corpus/) whose
    text supports `key_facts`; required for corpus items, empty for web items."""

    id: str
    question: str
    target: Literal["web", "corpus"]
    key_facts: list[str] = Field(min_length=1)
    acceptable_domains: list[str] = []
    source_docs: list[str] = []

    @property
    def reference(self) -> str:
        """Ground-truth answer for Ragas context_recall: the key facts as one string."""
        return " ".join(self.key_facts)


def _normalize_ws(text: str) -> str:
    """Collapse all whitespace (incl. line wraps) to single spaces so verbatim matching is
    resilient to the markdown's hard line breaks."""
    return " ".join(text.split())


def load_golden(
    path: Path = _GOLDEN_PATH, corpus_dir: Path = _CORPUS_DIR
) -> list[GoldenItem]:
    """Parse + validate the golden dataset. Raises ValueError on any schema violation."""
    items: list[GoldenItem] = []
    for lineno, line in enumerate(path.read_text().splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            items.append(GoldenItem.model_validate_json(stripped))
        except Exception as exc:  # attach the offending line number
            raise ValueError(
                f"{path.name}:{lineno}: invalid golden item: {exc}"
            ) from exc

    if not _MIN_ITEMS <= len(items) <= _MAX_ITEMS:
        raise ValueError(
            f"golden set has {len(items)} items; expected {_MIN_ITEMS}-{_MAX_ITEMS}"
        )

    ids = [it.id for it in items]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise ValueError(f"duplicate golden ids: {dupes}")

    for it in items:
        if it.target == "corpus":
            if not it.source_docs:
                raise ValueError(f"corpus item {it.id!r} must list source_docs")
            # Each key_fact must appear verbatim in at least one named source_doc. This is
            # the deterministic A1 check the plan calls for — without it, an edit to either
            # side can drift unnoticed and silently break the A2 retrievability run.
            doc_texts = {}
            for doc in it.source_docs:
                doc_path = corpus_dir / doc
                if not doc_path.is_file():
                    raise ValueError(
                        f"corpus item {it.id!r} references missing doc {doc!r}"
                    )
                doc_texts[doc] = _normalize_ws(doc_path.read_text())
            haystack = " ".join(doc_texts.values())
            for fact in it.key_facts:
                if _normalize_ws(fact) not in haystack:
                    raise ValueError(
                        f"corpus item {it.id!r}: key_fact not verbatim in {it.source_docs!r}: {fact!r}"
                    )
        elif it.target == "web" and not it.acceptable_domains:
            raise ValueError(f"web item {it.id!r} must list acceptable_domains")

    return items
