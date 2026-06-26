"""Document ingestion endpoint (FR-5): chunk + embed + store.

Two POST paths share the same `ingest_document` primitive (`app/ingest/store.py`):
- `POST /documents` (JSON) — original raw-text path; kept for curl/CI use.
- `POST /documents/upload` (multipart) — file upload for the React UI (Phase 5 Group A
  follow-up). Accepts `.txt`, `.md`, `.pdf`; rejects others with 400.
"""

import io
from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.ratelimit import DOCUMENTS_LIMIT, limiter
from app.auth.dependencies import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.ingest.store import ingest_document

router = APIRouter()

# Server-side guard so a 50MB upload doesn't pin the event loop while pypdf chews on it.
# 5 MB is generous for text/markdown and covers most one-off reference PDFs.
_MAX_UPLOAD_BYTES = 5 * 1024 * 1024
_ALLOWED_EXTS = {".txt", ".md", ".pdf"}


class DocumentIn(BaseModel):
    raw_text: str = Field(min_length=1, max_length=_MAX_UPLOAD_BYTES)
    title: str | None = None
    source_uri: str | None = None
    metadata: dict | None = None


class DocumentOut(BaseModel):
    document_id: int
    chunks: int


@router.post("/documents", response_model=DocumentOut)
@limiter.limit(DOCUMENTS_LIMIT)
def ingest_document_endpoint(
    request: Request,
    doc: DocumentIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentOut:
    document_id, chunks = ingest_document(
        db,
        raw_text=doc.raw_text,
        title=doc.title,
        source_uri=doc.source_uri,
        doc_metadata=doc.metadata,
        user_id=current_user.id,
    )
    db.commit()
    return DocumentOut(document_id=document_id, chunks=chunks)


def _extract_text(filename: str, data: bytes) -> str:
    """Decode .txt/.md as UTF-8 (with replace for stray bytes); extract .pdf via pypdf.
    Caller has already enforced the extension allowlist."""
    ext = PurePosixPath(filename).suffix.lower()
    if ext in {".txt", ".md"}:
        return data.decode("utf-8", errors="replace")
    if ext == ".pdf":
        # Lazy import so the .txt path doesn't pay pypdf's import cost.
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages).strip()
    # Defensive; the endpoint already filtered, but make the function safe in isolation.
    raise HTTPException(status_code=400, detail=f"unsupported extension: {ext}")


@router.post("/documents/upload", response_model=DocumentOut)
@limiter.limit(DOCUMENTS_LIMIT)
async def ingest_document_upload(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentOut:
    filename = file.filename or "upload"
    ext = PurePosixPath(filename).suffix.lower()
    if ext not in _ALLOWED_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"unsupported file type {ext!r}; allowed: {sorted(_ALLOWED_EXTS)}",
        )

    data = await file.read(_MAX_UPLOAD_BYTES + 1)
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"file too large; max {_MAX_UPLOAD_BYTES // 1024 // 1024} MB",
        )

    text = _extract_text(filename, data)
    if not text.strip():
        raise HTTPException(
            status_code=400, detail="no extractable text in uploaded file"
        )

    document_id, chunks = ingest_document(
        db,
        raw_text=text,
        title=filename,
        source_uri=f"upload:{filename}",
        doc_metadata={"upload": True, "ext": ext, "size_bytes": len(data)},
        user_id=current_user.id,
    )
    db.commit()
    return DocumentOut(document_id=document_id, chunks=chunks)
