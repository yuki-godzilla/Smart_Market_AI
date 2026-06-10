from __future__ import annotations

import httpx

from app.clients.ollama_client import OllamaClient, OllamaClientError
from app.config import GatewaySettings
from app.main import provider_error_to_http_exception


def test_provider_error_http_detail_is_actionable():
    exc = OllamaClientError(
        "Ollama request failed. Check OLLAMA_BASE_URL and whether Ollama is running.",
        code="provider_unreachable",
        retryable=True,
    )

    http_exc = provider_error_to_http_exception(exc)

    assert http_exc.status_code == 502
    assert http_exc.detail == {
        "error": "Ollama request failed. Check OLLAMA_BASE_URL and whether Ollama is running.",
        "provider": "ollama",
        "code": "provider_unreachable",
        "retryable": True,
    }


def test_ollama_model_not_found_error_mentions_pull_command():
    client = OllamaClient(GatewaySettings())
    response = httpx.Response(404, json={"error": "model 'missing-model' not found"})

    exc = client._http_status_error(response, "missing-model")

    assert exc.code == "model_not_found"
    assert exc.retryable is False
    assert "ollama pull missing-model" in str(exc)
