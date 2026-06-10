from __future__ import annotations

from time import perf_counter
from typing import Sequence

import httpx

from app.config import GatewaySettings
from app.schemas.common import LlmMessage, LlmProviderResult


class OllamaClientError(RuntimeError):
    """Normalized error for Ollama provider failures."""


class OllamaClient:
    """Small client that hides Ollama API details behind a provider boundary."""

    provider = "ollama"

    def __init__(self, settings: GatewaySettings) -> None:
        self.settings = settings

    def chat(
        self, messages: Sequence[LlmMessage], *, model: str | None = None
    ) -> LlmProviderResult:
        selected_model = model or self.settings.DEFAULT_LLM_MODEL
        payload = {
            "model": selected_model,
            "messages": [message.model_dump() for message in messages],
            "stream": False,
        }
        started = perf_counter()
        try:
            with httpx.Client(timeout=self.settings.REQUEST_TIMEOUT_SECONDS) as client:
                response = client.post(
                    f"{self.settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat",
                    json=payload,
                )
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise OllamaClientError("Ollama request timed out.") from exc
        except httpx.HTTPStatusError as exc:
            raise OllamaClientError(f"Ollama returned HTTP {exc.response.status_code}.") from exc
        except httpx.RequestError as exc:
            raise OllamaClientError(
                "Ollama request failed. Check base URL and server status."
            ) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise OllamaClientError("Ollama returned invalid JSON.") from exc
        answer = str(data.get("message", {}).get("content", "")).strip()
        if not answer:
            raise OllamaClientError("Ollama returned an empty answer.")
        elapsed_ms = int((perf_counter() - started) * 1000)
        return LlmProviderResult(
            answer=answer,
            model=str(data.get("model") or selected_model),
            provider=self.provider,
            elapsed_ms=elapsed_ms,
        )
