"""
test_extractor_priority.py — Verify extractor calls land in merLLM's
``background`` bucket and user-facing calls land in the ``chat`` bucket.

merLLM runs a 5-bucket priority queue (chat > reserved > short >
feedback > background, strict top-down drain). LanceLLMot's concept
extractor is not latency-sensitive and must go out with
``X-Priority: background`` so merLLM waits indefinitely for a GPU slot
instead of timing out at INTERACTIVE_QUEUE_TIMEOUT and silently dropping
graph edges. Every other LanceLLMot → merLLM call is user-facing and
must land in the ``chat`` bucket.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import config
import extractor
import rag


def test_extractor_headers_are_background_priority():
    """config.OLLAMA_EXTRACTOR_HEADERS must target the background bucket."""
    assert config.OLLAMA_EXTRACTOR_HEADERS["X-Priority"] == "background"
    assert config.OLLAMA_EXTRACTOR_HEADERS["X-Source"] == "lancellmot"


def test_global_ollama_headers_are_chat_priority():
    """Global OLLAMA_HEADERS must target the chat bucket — RAG/query is user-facing."""
    assert config.OLLAMA_HEADERS["X-Priority"] == "chat"
    assert config.OLLAMA_HEADERS["X-Source"] == "lancellmot"


@pytest.mark.asyncio
async def test_extract_chunk_sends_background_priority_header():
    """extract_chunk must build its httpx client with the extractor headers."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"message": {"content": "{}"}}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("extractor.httpx.AsyncClient", return_value=mock_client) as mock_cls:
        await extractor.extract_chunk("some chunk text")

    # httpx.AsyncClient(...) must have been called with the extractor headers.
    _, kwargs = mock_cls.call_args
    assert kwargs["headers"] is config.OLLAMA_EXTRACTOR_HEADERS
    assert kwargs["headers"]["X-Priority"] == "background"


@pytest.mark.asyncio
async def test_embed_defaults_to_chat_priority():
    """rag.embed() with no headers must use chat priority — query path."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"embedding": [0.0]}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("rag.httpx.AsyncClient", return_value=mock_client) as mock_cls:
        await rag.embed("query text")

    _, kwargs = mock_cls.call_args
    assert kwargs["headers"] is config.OLLAMA_HEADERS
    assert kwargs["headers"]["X-Priority"] == "chat"


@pytest.mark.asyncio
async def test_embed_accepts_background_headers_for_ingest():
    """rag.embed(headers=OLLAMA_EXTRACTOR_HEADERS) must use background priority.

    Regression: prior to 2026-04-11, rag.ingest() called rag.embed() with no
    headers argument, so bulk-ingest embedding traffic landed in merLLM's
    chat bucket and preempted real user chats during doc indexing. The
    extractor calls were already background; the embeddings were not.
    """
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"embedding": [0.0]}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("rag.httpx.AsyncClient", return_value=mock_client) as mock_cls:
        await rag.embed("chunk text", headers=config.OLLAMA_EXTRACTOR_HEADERS)

    _, kwargs = mock_cls.call_args
    assert kwargs["headers"] is config.OLLAMA_EXTRACTOR_HEADERS
    assert kwargs["headers"]["X-Priority"] == "background"


@pytest.mark.asyncio
async def test_ingest_routes_embeddings_through_background_bucket():
    """rag.ingest() must pass OLLAMA_EXTRACTOR_HEADERS to every embed() call."""
    captured_headers = []

    async def _fake_embed(text, headers=None):
        captured_headers.append(headers)
        return [0.0]

    fake_col = MagicMock()
    fake_col.add = MagicMock()

    with patch("rag.embed", side_effect=_fake_embed), \
         patch("rag.get_collection", return_value=fake_col), \
         patch("rag.graph") as mock_graph, \
         patch("rag.db"), \
         patch("rag.extractor") as mock_extractor:
        mock_graph.parse_and_index_chunk_references = MagicMock()
        mock_graph.parse_and_index_references = MagicMock()
        mock_graph.index_document = MagicMock()
        mock_graph.index_chunk = MagicMock()
        mock_extractor.extract_chunk = AsyncMock(
            return_value=extractor.ExtractionResult()
        )

        await rag.ingest(
            doc_id="doc-1",
            user_email="user@example.com",
            text="x" * 2500,
            skip_concepts=True,
        )

    assert captured_headers, "ingest() should have called embed() at least once"
    for h in captured_headers:
        assert h is config.OLLAMA_EXTRACTOR_HEADERS, (
            f"ingest() embed call used wrong headers: {h}"
        )
