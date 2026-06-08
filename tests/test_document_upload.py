"""Tests for the file-upload endpoint (Phase 5 Group A follow-up, FR-5).

Two test surfaces:
- **Cheap (no DB/model)** — extension allowlist + size cap + empty-text rejection,
  asserted by hitting the route directly with `TestClient`. Run on every CI default.
- **DB + model-gated** — actual ingest of a small .txt, mirroring `test_ingest.py`.
  PDF parsing is exercised by the live verify step (no PDF unit test — pypdf itself is
  well-tested, and the route's PDF branch is 5 lines wrapping `PdfReader.extract_text`).
"""

import os

import pytest


# --- non-DB / non-model tests ---------------------------------------------------------


def test_rejects_unsupported_extension():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.post(
        "/documents/upload",
        files={"file": ("malware.exe", b"MZ\x90\x00", "application/octet-stream")},
    )

    assert resp.status_code == 400
    assert "unsupported" in resp.json()["detail"].lower()


def test_rejects_oversize_upload():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    # 6 MB of 'x' — over the 5 MB cap. .txt extension so it passes the allowlist check.
    huge = b"x" * (6 * 1024 * 1024)
    resp = client.post(
        "/documents/upload",
        files={"file": ("big.txt", huge, "text/plain")},
    )

    assert resp.status_code == 413
    assert "too large" in resp.json()["detail"].lower()


def test_rejects_empty_text_file():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.post(
        "/documents/upload",
        files={"file": ("empty.txt", b"   \n\n", "text/plain")},
    )

    assert resp.status_code == 400
    assert "no extractable text" in resp.json()["detail"].lower()


# --- DB + model-gated --------------------------------------------------------------------

requires_db_and_model = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1" or os.environ.get("RUN_MODEL_TESTS") != "1",
    reason="set RUN_DB_TESTS=1 and RUN_MODEL_TESTS=1 (needs Postgres + embedding model)",
)


@requires_db_and_model
def test_upload_txt_ingests_and_chunks():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    text = "Paris is the capital of France. " * 200  # long enough to chunk
    resp = client.post(
        "/documents/upload",
        files={"file": ("geo.txt", text.encode("utf-8"), "text/plain")},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["document_id"] > 0
    assert body["chunks"] >= 2
