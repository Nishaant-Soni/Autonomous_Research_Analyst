"""Document ingestion primitive (chunk + embed + store) shared by the /documents endpoint
and the eval harness. Lifted out of `app/api/documents.py` so eval can call the same code
path instead of duplicating it (preventing drift if chunking/embedding ever change)."""

from sqlalchemy.orm import Session

from app.db.models import Chunk, Document
from app.embeddings import embed_documents
from app.ingest.chunking import chunk_text


def ingest_document(
    db: Session,
    raw_text: str,
    title: str | None = None,
    source_uri: str | None = None,
    doc_metadata: dict | None = None,
    user_id: int | None = None,
) -> tuple[int, int]:
    """Chunk + embed `raw_text` and persist a Document with its Chunks. Caller owns the
    transaction (we flush to assign the document id, but commit is the caller's call).
    Returns (document_id, chunk_count)."""
    document = Document(
        raw_text=raw_text,
        title=title,
        source_uri=source_uri,
        doc_metadata=doc_metadata,
        user_id=user_id,
    )
    db.add(document)
    db.flush()  # assigns document.id without committing

    pieces = chunk_text(raw_text)
    vectors = embed_documents(pieces)
    for index, (content, embedding) in enumerate(zip(pieces, vectors, strict=True)):
        db.add(
            Chunk(
                document_id=document.id,
                chunk_index=index,
                content=content,
                embedding=embedding,
            )
        )
    return document.id, len(pieces)
