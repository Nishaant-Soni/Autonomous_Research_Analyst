"""Idempotent ingestion of the seed corpus (eval/corpus/*.md) into the running DB.

Each markdown file is stored as a Document with a stable, eval-only title prefix
(`eval-corpus:<filename>`) so re-runs are safe: if the row exists, ingestion is skipped.
The /documents endpoint and this script share the same `ingest_document` primitive,
so chunking + embedding stay in lockstep with the runtime path.
"""

from pathlib import Path

from sqlalchemy import select

from app.db.models import Document
from app.db.session import SessionLocal
from app.ingest.store import ingest_document

_CORPUS_DIR = Path(__file__).parent / "corpus"
_TITLE_PREFIX = "eval-corpus:"


def _title_for(filename: str) -> str:
    return f"{_TITLE_PREFIX}{filename}"


def ingest_seed_corpus(corpus_dir: Path = _CORPUS_DIR) -> dict:
    """Ingest every *.md in `corpus_dir`, skipping files already present (by title).
    Returns {ingested: [filename, ...], skipped: [filename, ...]}."""
    ingested: list[str] = []
    skipped: list[str] = []
    files = sorted(p for p in corpus_dir.glob("*.md") if p.is_file())
    with SessionLocal() as db:
        for path in files:
            title = _title_for(path.name)
            existing = db.scalar(select(Document.id).where(Document.title == title))
            if existing is not None:
                skipped.append(path.name)
                continue
            ingest_document(
                db,
                raw_text=path.read_text(),
                title=title,
                source_uri=f"eval/corpus/{path.name}",
                doc_metadata={"eval_corpus": True},
            )
            ingested.append(path.name)
        db.commit()
    return {"ingested": ingested, "skipped": skipped}
