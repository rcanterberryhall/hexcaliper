"""
test_models.py — Unit tests for models.py (Pydantic models and domain constants).
"""
import pytest
from pydantic import ValidationError


def test_doc_types_contains_core_types():
    from models import DOC_TYPES
    for t in ("standard", "theop", "fmea", "hazard_analysis", "technical_manual",
              "datasheet", "plc_code", "misc"):
        assert t in DOC_TYPES, f"Expected '{t}' in DOC_TYPES"


def test_chat_request_valid(monkeypatch):
    import config
    monkeypatch.setattr(config, "MAX_INPUT_CHARS", 20000)
    from models import ChatRequest
    req = ChatRequest(message="What is SIL 2?")
    assert req.message == "What is SIL 2?"


def test_chat_request_strips_whitespace(monkeypatch):
    import config
    monkeypatch.setattr(config, "MAX_INPUT_CHARS", 20000)
    from models import ChatRequest
    req = ChatRequest(message="  hello  ")
    assert req.message == "hello"


def test_chat_request_empty_raises(monkeypatch):
    import config
    monkeypatch.setattr(config, "MAX_INPUT_CHARS", 20000)
    from models import ChatRequest
    with pytest.raises(ValidationError):
        ChatRequest(message="   ")


def test_chat_request_too_long_raises(monkeypatch):
    import config
    monkeypatch.setattr(config, "MAX_INPUT_CHARS", 10)
    from models import ChatRequest
    with pytest.raises(ValidationError):
        ChatRequest(message="x" * 11)


def test_chat_request_optional_fields_default_none(monkeypatch):
    import config
    monkeypatch.setattr(config, "MAX_INPUT_CHARS", 20000)
    from models import ChatRequest
    req = ChatRequest(message="hello")
    assert req.model is None
    assert req.system is None
    assert req.conversation_id is None
    assert req.project_id is None
