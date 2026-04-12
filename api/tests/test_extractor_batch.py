"""
test_extractor_batch.py — Pin the durable batch-extraction path.

Bulk concept extraction routes through merLLM's ``/api/batch/submit``
endpoint (hexcaliper#29). Before the migration the extractor called
merLLM's proxy ``/api/chat`` synchronously per chunk; merLLM did not
persist those proxy calls, so a merLLM restart mid-ingest silently
dropped graph edges for every in-flight chunk. These tests pin the new
submit → poll → assemble contract and the fault-tolerance semantics.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import extractor


# ── Helpers ──────────────────────────────────────────────────────────────────


def _mock_submit_response(job_id: str = "job-abc"):
    r = MagicMock()
    r.status_code = 200
    r.raise_for_status = MagicMock()
    r.json.return_value = {"ok": True, "id": job_id}
    return r


def _mock_result_response(status_code: int, *, payload: dict | None = None):
    r = MagicMock()
    r.status_code = status_code
    r.raise_for_status = MagicMock()
    r.json.return_value = payload or {}
    return r


def _valid_extraction_json() -> str:
    """A parseable extraction response the _parse_response helper accepts."""
    return (
        '{"concepts": ["safety integrity level"], '
        '"entities": ["SIL 2"], '
        '"doc_role": "requirement", '
        '"key_assertion": "The SIF shall achieve SIL 2."}'
    )


# ── Submission contract ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_extract_chunks_batch_submits_to_merllm_batch_endpoint(monkeypatch):
    """Every chunk must be POSTed to /api/batch/submit, not /api/chat."""
    monkeypatch.setattr(extractor, "BATCH_POLL_INTERVAL", 0.0)
    post_calls = []

    async def fake_post(url, json=None, timeout=None, **kw):
        post_calls.append((url, json))
        return _mock_submit_response(f"job-{len(post_calls)}")

    async def fake_get(url, timeout=None, **kw):
        return _mock_result_response(200, payload={"result": _valid_extraction_json()})

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=fake_post)
    mock_client.get = AsyncMock(side_effect=fake_get)

    with patch("extractor.httpx.AsyncClient", return_value=mock_client):
        results = await extractor.extract_chunks_batch(
            ["chunk one", "chunk two"], doc_type="theop",
        )

    assert len(results) == 2
    # Both calls hit the batch submit endpoint.
    assert all(url.endswith("/api/batch/submit") for url, _ in post_calls)
    # Source tag is lancellmot so merLLM can attribute queue entries.
    assert all(body["source_app"] == "lancellmot" for _, body in post_calls)
    # Defensive options are populated so qwen3:* cannot wedge a slot.
    for _, body in post_calls:
        assert body["options"]["think"] is False
        assert body["options"]["num_predict"] > 0
        assert body["options"]["num_ctx"] >= 8192


@pytest.mark.asyncio
async def test_extract_chunks_batch_flattens_messages_into_single_prompt(monkeypatch):
    """Batch endpoint runs /api/generate which takes a single prompt string —
    the system+user messages used by extract_chunk must be flattened."""
    monkeypatch.setattr(extractor, "BATCH_POLL_INTERVAL", 0.0)
    submitted = []

    async def fake_post(url, json=None, **kw):
        submitted.append(json["prompt"])
        return _mock_submit_response()

    async def fake_get(url, **kw):
        return _mock_result_response(200, payload={"result": _valid_extraction_json()})

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=fake_post)
    mock_client.get = AsyncMock(side_effect=fake_get)

    with patch("extractor.httpx.AsyncClient", return_value=mock_client):
        await extractor.extract_chunks_batch(["tell me about SIL 2"], doc_type="theop")

    assert len(submitted) == 1
    # Prompt must contain both the system-level instructions (vocabulary,
    # schema) and the user-level chunk text.
    prompt = submitted[0]
    assert "functional-safety document analyst" in prompt
    assert "tell me about SIL 2" in prompt


# ── Polling contract ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_extract_chunks_batch_polls_until_complete(monkeypatch):
    """A 409 queued/running response must not end the poll; we keep trying
    until the job flips to 200 (completed)."""
    monkeypatch.setattr(extractor, "BATCH_POLL_INTERVAL", 0.0)
    get_count = {"n": 0}

    async def fake_post(url, json=None, **kw):
        return _mock_submit_response()

    async def fake_get(url, **kw):
        get_count["n"] += 1
        if get_count["n"] < 3:
            return _mock_result_response(409, payload={"detail": "Job status: queued"})
        return _mock_result_response(200, payload={"result": _valid_extraction_json()})

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=fake_post)
    mock_client.get = AsyncMock(side_effect=fake_get)

    with patch("extractor.httpx.AsyncClient", return_value=mock_client):
        results = await extractor.extract_chunks_batch(["only chunk"])

    assert len(results) == 1
    assert results[0].concepts == ["safety integrity level"]
    assert get_count["n"] == 3  # polled through two queued states


# ── Fault tolerance — every failure mode returns empty, not an exception ────


@pytest.mark.asyncio
async def test_extract_chunks_batch_submit_failure_yields_empty(monkeypatch):
    """A submission failure (merLLM unreachable, 500, etc.) must not crash
    the caller. The slot gets an empty ExtractionResult."""
    monkeypatch.setattr(extractor, "BATCH_POLL_INTERVAL", 0.0)

    async def fake_post(url, **kw):
        raise RuntimeError("merLLM unreachable")

    async def fake_get(url, **kw):
        return _mock_result_response(200, payload={"result": _valid_extraction_json()})

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=fake_post)
    mock_client.get = AsyncMock(side_effect=fake_get)

    with patch("extractor.httpx.AsyncClient", return_value=mock_client):
        results = await extractor.extract_chunks_batch(["chunk"])

    assert len(results) == 1
    assert results[0].is_empty()


@pytest.mark.asyncio
async def test_extract_chunks_batch_merllm_reported_failure_yields_empty(monkeypatch):
    """merLLM returning 409 with 'failed' status must map to an empty
    ExtractionResult — same contract as the pre-migration sync path."""
    monkeypatch.setattr(extractor, "BATCH_POLL_INTERVAL", 0.0)

    async def fake_post(url, **kw):
        return _mock_submit_response()

    async def fake_get(url, **kw):
        return _mock_result_response(409, payload={"detail": "Job status: failed"})

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=fake_post)
    mock_client.get = AsyncMock(side_effect=fake_get)

    with patch("extractor.httpx.AsyncClient", return_value=mock_client):
        results = await extractor.extract_chunks_batch(["chunk"])

    assert len(results) == 1
    assert results[0].is_empty()


@pytest.mark.asyncio
async def test_extract_chunks_batch_404_yields_empty(monkeypatch):
    """404 (job id unknown to merLLM, e.g. DB wiped between submit and poll)
    must give up on that slot rather than poll forever."""
    monkeypatch.setattr(extractor, "BATCH_POLL_INTERVAL", 0.0)

    async def fake_post(url, **kw):
        return _mock_submit_response()

    async def fake_get(url, **kw):
        return _mock_result_response(404)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=fake_post)
    mock_client.get = AsyncMock(side_effect=fake_get)

    with patch("extractor.httpx.AsyncClient", return_value=mock_client):
        results = await extractor.extract_chunks_batch(["chunk"])

    assert len(results) == 1
    assert results[0].is_empty()


@pytest.mark.asyncio
async def test_extract_chunks_batch_preserves_slot_order_under_partial_failure(
        monkeypatch):
    """If chunk 2 of 3 fails, chunks 1 and 3 must still land in slots 0 and
    2 — callers rely on results[i] matching chunk_ids[i]."""
    monkeypatch.setattr(extractor, "BATCH_POLL_INTERVAL", 0.0)
    submit_n = {"n": 0}
    # Map each submit to a job id so we can route polls back.
    job_map = {}

    async def fake_post(url, json=None, **kw):
        submit_n["n"] += 1
        if submit_n["n"] == 2:
            raise RuntimeError("simulated submit failure on chunk 2")
        job_id = f"job-{submit_n['n']}"
        job_map[job_id] = submit_n["n"]
        return _mock_submit_response(job_id)

    async def fake_get(url, **kw):
        return _mock_result_response(200, payload={"result": _valid_extraction_json()})

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=fake_post)
    mock_client.get = AsyncMock(side_effect=fake_get)

    with patch("extractor.httpx.AsyncClient", return_value=mock_client):
        results = await extractor.extract_chunks_batch(["a", "b", "c"])

    assert len(results) == 3
    assert not results[0].is_empty()
    assert results[1].is_empty()           # slot preserved for failed chunk
    assert not results[2].is_empty()


@pytest.mark.asyncio
async def test_extract_chunks_batch_empty_input_is_noop():
    """Zero chunks means zero submissions — don't even open an httpx client."""
    # No patching: if the function tried to call httpx.AsyncClient it would
    # hit the real network. Returning immediately proves the early-out.
    results = await extractor.extract_chunks_batch([])
    assert results == []
