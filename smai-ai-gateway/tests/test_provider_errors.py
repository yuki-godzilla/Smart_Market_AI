from __future__ import annotations

import json

import httpx

from app.clients.ollama_client import OllamaClient, OllamaClientError
from app.config import GatewaySettings
from app.main import provider_error_to_http_exception
from app.schemas.common import LlmMessage


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


def test_ollama_chat_disables_thinking_for_structured_gateway_tasks(monkeypatch):
    observed: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["payload"] = request.read().decode("utf-8")
        return httpx.Response(
            200,
            json={
                "model": "qwen3:8b",
                "message": {"role": "assistant", "content": '{"answer":"ok"}'},
            },
            request=request,
        )

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *args) -> None:
            pass

        def post(self, url: str, *, json: dict[str, object]) -> httpx.Response:
            request = httpx.Request("POST", url, json=json)
            return handler(request)

    monkeypatch.setattr(httpx, "Client", FakeClient)
    client = OllamaClient(GatewaySettings())

    result = client.chat([LlmMessage(role="user", content="hello")], model="qwen3:8b")

    assert result.answer == '{"answer":"ok"}'
    payload = json.loads(str(observed["payload"]))
    assert payload["think"] is False


def test_ollama_chat_strips_thinking_blocks(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "qwen3:4b",
                "message": {
                    "role": "assistant",
                    "content": "internal reasoning</think>\n\nhello from final",
                },
            },
            request=request,
        )

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *args) -> None:
            pass

        def post(self, url: str, *, json: dict[str, object]) -> httpx.Response:
            request = httpx.Request("POST", url, json=json)
            return handler(request)

    monkeypatch.setattr(httpx, "Client", FakeClient)
    client = OllamaClient(GatewaySettings())

    result = client.chat([LlmMessage(role="user", content="hello")], model="qwen3:4b")

    assert result.answer == "hello from final"
    assert result.response_chars == len("hello from final")


def test_ollama_chat_extracts_labeled_final_answer_from_qwen_planning(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "qwen3:4b",
                "message": {
                    "role": "assistant",
                    "content": (
                        "Okay, the user wants a short self-introduction.\n\n"
                        "Possible response: Hello, I am SMAI Navi. "
                        "I can organize AI forecasts and news into short checkpoints.\n\n"
                        "Wait, maybe make it shorter."
                    ),
                },
            },
            request=request,
        )

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *args) -> None:
            pass

        def post(self, url: str, *, json: dict[str, object]) -> httpx.Response:
            request = httpx.Request("POST", url, json=json)
            return handler(request)

    monkeypatch.setattr(httpx, "Client", FakeClient)
    client = OllamaClient(GatewaySettings())

    result = client.chat([LlmMessage(role="user", content="hello")], model="qwen3:4b")

    assert (
        result.answer
        == "Hello, I am SMAI Navi. I can organize AI forecasts and news into short checkpoints."
    )


def test_ollama_chat_extracts_quoted_answer_after_let_me_think(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "qwen3:4b",
                "message": {
                    "role": "assistant",
                    "content": (
                        "Okay, the user wants a short self-introduction.\n\n"
                        'Let me think: "Hello, I am SMAI Navi. I help with short checks."\n\n'
                        "Wait, but maybe shorter."
                    ),
                },
            },
            request=request,
        )

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *args) -> None:
            pass

        def post(self, url: str, *, json: dict[str, object]) -> httpx.Response:
            request = httpx.Request("POST", url, json=json)
            return handler(request)

    monkeypatch.setattr(httpx, "Client", FakeClient)
    client = OllamaClient(GatewaySettings())

    result = client.chat([LlmMessage(role="user", content="hello")], model="qwen3:4b")

    assert result.answer == "Hello, I am SMAI Navi. I help with short checks."


def test_ollama_chat_extracts_longest_quoted_answer_from_qwen_planning(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "qwen3:4b",
                "message": {
                    "role": "assistant",
                    "content": (
                        'Okay, the user asked "Please introduce yourself briefly."\n\n'
                        'I should answer: "Hello, I am SMAI Navi. '
                        'I help organize forecasts, news, and next checkpoints."\n\n'
                        "Maybe this is enough."
                    ),
                },
            },
            request=request,
        )

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *args) -> None:
            pass

        def post(self, url: str, *, json: dict[str, object]) -> httpx.Response:
            request = httpx.Request("POST", url, json=json)
            return handler(request)

    monkeypatch.setattr(httpx, "Client", FakeClient)
    client = OllamaClient(GatewaySettings())

    result = client.chat([LlmMessage(role="user", content="hello")], model="qwen3:4b")

    assert (
        result.answer
        == "Hello, I am SMAI Navi. I help organize forecasts, news, and next checkpoints."
    )
