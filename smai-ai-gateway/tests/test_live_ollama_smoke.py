from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.skipif(
    os.getenv("SMAI_AI_GATEWAY_LIVE_SMOKE") != "1",
    reason="Set SMAI_AI_GATEWAY_LIVE_SMOKE=1 to run the local Ollama smoke test.",
)


def test_live_chat_endpoint_uses_local_ollama():
    client = TestClient(app)
    model = os.getenv("SMAI_OLLAMA_MODEL") or os.getenv("DEFAULT_LLM_MODEL") or "llama3.2:3b"

    response = client.post(
        "/api/v1/chat",
        json={
            "message": "こんにちは。短く一文で返してください。",
            "system_prompt": "You are a concise local assistant.",
            "model": model,
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["answer"].strip()
    assert data["provider"] == "ollama"
    assert data["model"]
    assert data["elapsed_ms"] >= 0
