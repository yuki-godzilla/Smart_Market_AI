from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.chat import ChatRequest
from app.schemas.summarize import SummarizeRequest


def test_chat_request_schema_accepts_generic_message():
    request = ChatRequest(
        message="こんにちは",
        system_prompt="You are a helpful assistant.",
        model="qwen3:8b",
    )

    assert request.message == "こんにちは"
    assert request.system_prompt == "You are a helpful assistant."
    assert request.model == "qwen3:8b"


def test_summarize_request_schema_accepts_generic_text():
    request = SummarizeRequest(
        text="確認したい文章の要点を箇条書きにしてください。",
        purpose="general_summary",
        model="qwen3:8b",
    )

    assert request.text.startswith("確認")
    assert request.purpose == "general_summary"
    assert request.model == "qwen3:8b"


def test_chat_request_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        ChatRequest(message="hello", smai_symbol="7203.T")
