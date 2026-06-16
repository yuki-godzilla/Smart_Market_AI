from __future__ import annotations

import re
from time import perf_counter
from typing import Sequence

import httpx

from app.config import GatewaySettings
from app.schemas.common import LlmMessage, LlmProviderResult


class OllamaClientError(RuntimeError):
    """Normalized error for Ollama provider failures."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "provider_error",
        retryable: bool = False,
        http_status: int = 502,
        provider: str = "ollama",
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.http_status = http_status
        self.provider = provider


class OllamaClient:
    """Small client that hides Ollama API details behind a provider boundary."""

    provider = "ollama"

    def __init__(self, settings: GatewaySettings) -> None:
        self.settings = settings

    def chat(
        self,
        messages: Sequence[LlmMessage],
        *,
        model: str | None = None,
        timeout_seconds: float | None = None,
        max_tokens: int | None = None,
    ) -> LlmProviderResult:
        selected_model = model or self.settings.DEFAULT_LLM_MODEL
        payload = {
            "model": selected_model,
            "messages": [message.model_dump() for message in messages],
            "stream": False,
            "think": False,
        }
        prompt_chars = sum(len(message.content) for message in messages)
        if max_tokens is not None:
            payload["options"] = {"num_predict": max_tokens}
        started = perf_counter()
        timeout = timeout_seconds or self.settings.REQUEST_TIMEOUT_SECONDS
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    f"{self.settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat",
                    json=payload,
                )
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise OllamaClientError(
                f"Ollama request timed out after {timeout:g}s.",
                code="provider_timeout",
                retryable=True,
                http_status=504,
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise self._http_status_error(exc.response, selected_model) from exc
        except httpx.RequestError as exc:
            raise OllamaClientError(
                "Ollama request failed. Check OLLAMA_BASE_URL and whether Ollama is running.",
                code="provider_unreachable",
                retryable=True,
            ) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise OllamaClientError(
                "Ollama returned invalid JSON.",
                code="invalid_provider_response",
            ) from exc
        answer = _strip_thinking_text(str(data.get("message", {}).get("content", "")))
        if not answer:
            raise OllamaClientError(
                "Ollama returned an empty answer.",
                code="empty_provider_response",
            )
        elapsed_ms = int((perf_counter() - started) * 1000)
        return LlmProviderResult(
            answer=answer,
            model=str(data.get("model") or selected_model),
            provider=self.provider,
            elapsed_ms=elapsed_ms,
            prompt_chars=prompt_chars,
            response_chars=len(answer),
        )

    def list_models(self) -> list[str]:
        try:
            with httpx.Client(timeout=self.settings.REQUEST_TIMEOUT_SECONDS) as client:
                response = client.get(f"{self.settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags")
                response.raise_for_status()
        except httpx.RequestError as exc:
            raise OllamaClientError(
                "Ollama request failed. Check SMAI_OLLAMA_BASE_URL and whether Ollama is running.",
                code="provider_unreachable",
                retryable=True,
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise self._http_status_error(exc.response, self.settings.DEFAULT_LLM_MODEL) from exc
        try:
            data = response.json()
        except ValueError as exc:
            raise OllamaClientError(
                "Ollama returned invalid JSON from /api/tags.",
                code="invalid_provider_response",
            ) from exc
        models = data.get("models", []) if isinstance(data, dict) else []
        return sorted(
            str(item.get("name", "")).strip()
            for item in models
            if isinstance(item, dict) and str(item.get("name", "")).strip()
        )

    def _http_status_error(
        self, response: httpx.Response, selected_model: str
    ) -> OllamaClientError:
        status_code = response.status_code
        provider_message = _extract_provider_error(response)
        if status_code == 404 and "model" in provider_message.lower():
            return OllamaClientError(
                (
                    f"Ollama model '{selected_model}' was not found. "
                    f"Run `ollama pull {selected_model}` or choose an installed model."
                ),
                code="model_not_found",
                retryable=False,
            )
        if provider_message:
            message = f"Ollama returned HTTP {status_code}: {provider_message}"
        else:
            message = f"Ollama returned HTTP {status_code}."
        return OllamaClientError(
            message,
            code="provider_http_error",
            retryable=status_code >= 500,
        )


def _extract_provider_error(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return response.text.strip()
    if isinstance(data, dict):
        error = data.get("error")
        if error:
            return str(error).strip()
    return response.text.strip()


def _strip_thinking_text(answer: str) -> str:
    text = answer.strip()
    text = re.sub(r"(?is)<think>.*?</think>", "", text).strip()
    if "</think>" in text:
        text = text.split("</think>")[-1].strip()
    labeled_answer = _extract_labeled_final_answer(text)
    return labeled_answer or text


def _extract_labeled_final_answer(text: str) -> str | None:
    """Recover the user-facing answer when qwen emits untagged planning prose."""

    label_pattern = re.compile(
        r"(?is)\b(?:possible\s+(?:answer|response)|final\s+answer|answer|"
        r"original\s+response\s+example|let\s+me\s+think)\s*:\s*"
    )
    for match in label_pattern.finditer(text):
        candidate = text[match.end() :].strip()
        candidate = re.split(
            r"(?im)^\s*(?:wait|hmm|another\s+try|alternatively|first\s+sentence)\b",
            candidate,
            maxsplit=1,
        )[0]
        candidate = candidate.strip().strip("\"'`").strip()
        candidate = _strip_wrapping_japanese_quote(candidate)
        candidate = candidate.splitlines()[0].strip() if "\n" in candidate else candidate
        candidate = candidate.strip().strip("\"'`").strip()
        if _looks_like_final_answer(candidate):
            return candidate
    quoted_answer = _extract_quoted_final_answer(text)
    if quoted_answer is not None:
        return quoted_answer
    return None


def _strip_wrapping_japanese_quote(text: str) -> str:
    if len(text) >= 2 and text[0] in {"「", "『"}:
        closing = "」" if text[0] == "「" else "』"
        end = text.find(closing, 1)
        if end > 0:
            return text[1:end].strip()
    return text


def _looks_like_final_answer(text: str) -> bool:
    if len(text) < 8:
        return False
    lowered = text.lower()
    planning_markers = (
        "let me",
        "i need",
        "i should",
        "the user",
        "possible answer",
        "possible response",
        "wait,",
        "hmm,",
    )
    if any(marker in lowered for marker in planning_markers):
        return False
    return bool(re.search(r"[ぁ-んァ-ン一-龥A-Za-z]", text))


def _extract_quoted_final_answer(text: str) -> str | None:
    if not _looks_like_qwen_planning(text):
        return None
    quoted_values = [
        match.group(1).strip()
        for match in re.finditer(r'"([^"\n]{12,500})"', text)
        if _looks_like_final_answer(match.group(1).strip())
    ]
    if not quoted_values:
        return None
    candidates = [
        value
        for value in quoted_values
        if not any(marker in value for marker in ("短く自己紹介", "Please introduce"))
    ]
    return max(candidates or quoted_values, key=len)


def _looks_like_qwen_planning(text: str) -> bool:
    lowered = text.lower().lstrip()
    return lowered.startswith(("okay, the user", "first, i need", "let me"))
