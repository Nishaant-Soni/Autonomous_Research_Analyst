import pytest

from app.ingest.chunking import chunk_text


def test_chunks_count_and_overlap():
    text = "abcdefghij" * 10  # 100 chars
    chunks = chunk_text(text, chunk_size=30, overlap=10)  # step = 20

    assert len(chunks) == 5
    assert all(len(c) == 30 for c in chunks[:-1])
    assert len(chunks[-1]) == 20
    # consecutive chunks share `overlap` characters
    assert chunks[0][-10:] == chunks[1][:10]


def test_short_text_single_chunk():
    assert chunk_text("hello", chunk_size=30, overlap=10) == ["hello"]


def test_invalid_params():
    with pytest.raises(ValueError):
        chunk_text("x", chunk_size=0)
    with pytest.raises(ValueError):
        chunk_text("x", chunk_size=10, overlap=10)
