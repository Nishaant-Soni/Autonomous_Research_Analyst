"""Document ingestion endpoint (FR-5): chunk + embed + store."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.models import Chunk, Document
from app.db.session import get_db
from app.embeddings import embed_documents
from app.ingest.chunking import chunk_text

router = APIRouter()


class DocumentIn(BaseModel):
    raw_text: str = Field(min_length=1)
    title: str | None = None
    source_uri: str | None = None
    metadata: dict | None = None


class DocumentOut(BaseModel):
    document_id: int
    chunks: int


@router.post("/documents", response_model=DocumentOut)
def ingest_document(doc: DocumentIn, db: Session = Depends(get_db)) -> DocumentOut:
    document = Document(
        raw_text=doc.raw_text,
        title=doc.title,
        source_uri=doc.source_uri,
        doc_metadata=doc.metadata,
    )
    db.add(document)
    db.flush()  # assigns document.id without committing yet

    pieces = chunk_text(doc.raw_text)
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
    db.commit()
    return DocumentOut(document_id=document.id, chunks=len(pieces))
