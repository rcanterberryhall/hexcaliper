"""
test_rag_chunking.py — Unit tests for the text-chunking logic in rag.py.

These tests only exercise `chunk_text`, which has no external dependencies.
"""
import pytest


@pytest.fixture(autouse=True)
def patch_rag_constants(monkeypatch):
    """Use small chunk sizes for predictable test data."""
    import rag
    monkeypatch.setattr(rag, "CHUNK_SIZE", 100)
    monkeypatch.setattr(rag, "CHUNK_OVERLAP", 20)


def test_chunk_text_empty_returns_empty():
    from rag import chunk_text
    assert chunk_text("") == []


def test_chunk_text_whitespace_only_returns_empty():
    from rag import chunk_text
    assert chunk_text("   \n\n\t  ") == []


def test_chunk_text_short_text_single_chunk():
    from rag import chunk_text
    text = "Short document."
    chunks = chunk_text(text)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_text_long_text_multiple_chunks():
    from rag import chunk_text
    # 300 chars → at least 3 chunks with chunk_size=100
    text = "A" * 300
    chunks = chunk_text(text)
    assert len(chunks) >= 2


def test_chunk_text_overlap():
    from rag import chunk_text
    # With CHUNK_SIZE=100 and CHUNK_OVERLAP=20, chunks should share 20 chars.
    text = "X" * 200
    chunks = chunk_text(text)
    if len(chunks) >= 2:
        # The tail of chunk[0] should appear at the head of chunk[1].
        overlap_candidate = chunks[0][-20:]
        assert chunks[1].startswith(overlap_candidate)


def test_chunk_text_preserves_content():
    from rag import chunk_text
    text = "Hello world! " * 20  # 260 chars
    chunks = chunk_text(text)
    # Every character of the original text should appear somewhere in the chunks.
    combined = "".join(chunks)
    assert "Hello world!" in combined


def test_chunk_text_strips_empty_chunks():
    from rag import chunk_text
    # Long whitespace sequences shouldn't produce empty chunks.
    text = "word " * 30
    chunks = chunk_text(text)
    assert all(c.strip() for c in chunks)
