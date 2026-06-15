from __future__ import annotations

from app.clients.ollama_client import OllamaClientError
from app.config import GatewaySettings
from app.schemas.common import LlmMessage, LlmProviderResult
from app.schemas.context_answer import ContextAnswerRequest
from app.services.context_answer_service import ContextAnswerService


class FakeLlmClient:
    def __init__(
        self,
        *,
        answer: str | None = None,
        answers: list[str] | None = None,
        error: OllamaClientError | None = None,
    ) -> None:
        self.messages: list[LlmMessage] = []
        self.calls: list[list[LlmMessage]] = []
        self.model: str | None = None
        self.timeout_seconds: float | None = None
        self.max_tokens: int | None = None
        self.settings = GatewaySettings()
        default_answer = (
            '{"answer":"SMAIナビとして、質問に直接答えます。画面の目的、確認材料、注意点を分けて見ると、次に確認することを決めやすくなります。",'
            '"materials":["LLM material 1","LLM material 2"],'
            '"cautions":["LLM caution"],"next_checkpoints":["LLM next check"],'
            '"confidence":"high"}'
        )
        self.answers = list(answers or ([answer] if answer is not None else [default_answer]))
        self.error = error

    def chat(
        self,
        messages: list[LlmMessage],
        *,
        model: str | None = None,
        timeout_seconds: float | None = None,
        max_tokens: int | None = None,
    ) -> LlmProviderResult:
        self.messages = messages
        self.calls.append(messages)
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        if self.error is not None:
            raise self.error
        answer = self.answers[min(len(self.calls) - 1, len(self.answers) - 1)]
        return LlmProviderResult(
            answer=answer,
            model=model or "qwen3:4b",
            provider="fake",
            elapsed_ms=7,
            prompt_chars=sum(len(message.content) for message in messages),
            response_chars=len(answer),
        )


def test_context_answer_service_uses_structured_llm_payload():
    client = FakeLlmClient()
    service = ContextAnswerService(client)  # type: ignore[arg-type]
    request = _request()

    response = service.answer(request)

    assert response.answer.startswith("SMAIナビとして、質問に直接答えます。")
    assert response.provider == "fake"
    assert response.model == "qwen3:8b"
    assert response.profile == "notebook_dev"
    assert response.elapsed_ms == 7
    assert response.materials == ["LLM material 1", "LLM material 2"]
    assert response.cautions == ["LLM caution"]
    assert response.next_checkpoints == ["LLM next check"]
    assert response.referenced_sections == []
    assert response.confidence == "high"
    assert response.safety_notes
    assert client.model == "qwen3:8b"
    assert client.timeout_seconds == 25.0
    assert client.max_tokens == 160
    assert response.timeout_sec == 25.0
    assert response.context_tokens_estimate is not None
    assert response.context_tokens_estimate > 0
    assert response.prompt_chars is not None
    assert response.prompt_chars > 0
    assert response.response_chars == len(client.answers[0])
    assert response.tool_execution_ms == 0
    assert response.llm_generation_ms == 7
    assert response.total_elapsed_ms is not None
    assert any("Minimal context" in message.content for message in client.messages)


def test_context_answer_service_drops_internal_notes_from_payload_lists():
    client = FakeLlmClient(
        answer=(
            '{"answer":"SMAIナビでは、価格とニュースを分けて確認します。",'
            '"materials":["価格トレンド","Provider raw fields were excluded"],'
            '"cautions":["AI予測だけで判断しないでください","debug logs are omitted"],'
            '"next_checkpoints":["ニュースを確認","score or ranking recomputation is not performed"],'
            '"confidence":"medium"}'
        )
    )
    service = ContextAnswerService(client)  # type: ignore[arg-type]
    request = _request().model_copy(update={"task_type": "stock_summary"})

    response = service.answer(request)

    assert response.materials == ["価格トレンド"]
    assert response.cautions == ["AI予測だけで判断しないでください"]
    assert response.next_checkpoints == ["ニュースを確認"]


def test_context_answer_service_uses_active_section_when_payload_is_unstructured():
    client = FakeLlmClient(answer="LLM plain answer")
    service = ContextAnswerService(client)  # type: ignore[arg-type]
    request = _request(active_context_id="risk-1")
    request.task_type = "forecast_risk_compare"

    response = service.answer(request)

    assert response.answer == "LLM plain answer"
    assert response.gateway_status == "ok"
    assert response.fallback_reason is None
    assert response.confidence == "low"
    assert response.materials[0] == "下振れ警戒"
    assert response.referenced_sections[0].section_id == "risk-1"


def test_context_answer_service_extracts_answer_label_from_reasoning_text():
    client = FakeLlmClient(
        answer='Reasoning first.\n\nanswer: "Check the materials by screen first."\n\nMore text.'
    )
    service = ContextAnswerService(client)  # type: ignore[arg-type]
    request = _request()
    request.task_type = "forecast_risk_compare"

    response = service.answer(request)

    assert response.gateway_status == "ok"
    assert response.answer == "Check the materials by screen first."


def test_context_answer_service_falls_back_when_llm_payload_is_invalid_json():
    client = FakeLlmClient(answer='{"answer": "", "materials": ["中心予測"]}')
    service = ContextAnswerService(client)  # type: ignore[arg-type]
    request = _request()
    request.task_type = "forecast_risk_compare"

    response = service.answer(request)

    assert response.answer.startswith("AI予測インサイトでは")
    assert response.materials[:3] == ["AI予測インサイト", "中心予測", "予測レンジ"]
    assert "予測レンジが広めです。" in response.cautions
    assert "根拠資料とデータ品質を確認します。" in response.next_checkpoints
    assert response.confidence == "medium"


def test_context_answer_service_falls_back_when_llm_payload_has_broken_text():
    client = FakeLlmClient(
        answer=(
            '{"answer":"AI??????? is unclear.","materials":["AI???????"],'
            '"cautions":["????"],"next_checkpoints":["????"],"confidence":"low"}'
        )
    )
    service = ContextAnswerService(client)  # type: ignore[arg-type]
    request = _request()
    request.task_type = "forecast_risk_compare"

    response = service.answer(request)

    assert response.answer.startswith("AI予測インサイトでは")
    assert response.materials[:3] == ["AI予測インサイト", "中心予測", "予測レンジ"]
    assert "????" not in response.answer


def test_context_answer_service_falls_back_when_plain_answer_is_reasoning_trace():
    client = FakeLlmClient(answer="We are given a task. Steps: return JSON.")
    service = ContextAnswerService(client)  # type: ignore[arg-type]
    request = _request()

    response = service.answer(request)

    assert response.gateway_status == "fallback"
    assert response.fallback_reason == "response_validation_failure"
    assert not response.answer.startswith("We are given")


def test_context_answer_service_prompt_includes_intent_specific_guide():
    client = FakeLlmClient()
    service = ContextAnswerService(client)  # type: ignore[arg-type]
    request = _request()
    request.user_question = (
        "SMAI Assistant intent: forecast_risk_compare\n"
        "User question: 予測とリスクを比べて"
    )
    request.task_type = "forecast_risk_compare"

    service.answer(request)

    joined = "\n".join(message.content for message in client.messages)
    assert "Intent-specific response guide" in joined
    assert "Compare forecast-side information and risk-side information" in joined
    assert "SMAI Navi" in joined


def test_context_answer_service_routes_task_type_to_standard_profile():
    client = FakeLlmClient()
    service = ContextAnswerService(client)  # type: ignore[arg-type]
    request = _request()
    request.task_type = "forecast_risk_compare"

    response = service.answer(request)

    assert response.profile == "notebook_dev"
    assert client.timeout_seconds == 45.0
    assert client.max_tokens == 700


def test_context_answer_service_accepts_profile_alias():
    client = FakeLlmClient()
    service = ContextAnswerService(client)  # type: ignore[arg-type]
    request = _request()
    request.profile = "desktop_fast"

    response = service.answer(request)

    assert response.profile == "desktop_fast"
    assert client.timeout_seconds == 25.0
    assert client.max_tokens == 160


def test_context_answer_service_off_mode_uses_deterministic_fallback():
    client = FakeLlmClient()
    service = ContextAnswerService(client)  # type: ignore[arg-type]
    request = _request()
    request.execution_mode = "off"

    response = service.answer(request)

    assert response.provider == "deterministic"
    assert response.model == "fallback"
    assert response.profile == "fallback"
    assert client.messages == []


def test_context_answer_service_returns_fallback_metadata_when_provider_times_out():
    client = FakeLlmClient(
        error=OllamaClientError(
            "provider timed out",
            code="provider_timeout",
            retryable=True,
            http_status=504,
        )
    )
    service = ContextAnswerService(client)  # type: ignore[arg-type]
    request = _request()

    response = service.answer(request)

    assert response.gateway_status == "fallback"
    assert response.fallback_reason == "local_conversation_fallback"
    assert response.provider == "ollama"
    assert response.model == "qwen3:8b"
    assert response.timeout_sec == 25.0
    assert response.prompt_chars is not None
    assert response.context_tokens_estimate is not None
    assert response.tool_execution_ms == 0
    assert response.llm_generation_ms is not None
    assert response.total_elapsed_ms is not None


def test_context_answer_service_free_chat_timeout_uses_conversation_fallback():
    client = FakeLlmClient(
        error=OllamaClientError(
            "provider timed out",
            code="provider_timeout",
            retryable=True,
            http_status=504,
        )
    )
    service = ContextAnswerService(client)  # type: ignore[arg-type]
    request = _request()
    request.user_question = "SMAIについて短く教えて"
    request.task_type = "free_chat"

    response = service.answer(request)

    assert response.gateway_status == "fallback"
    assert response.fallback_reason == "local_conversation_fallback"
    assert len(response.answer) >= 40
    assert not response.answer.startswith("分かる範囲で短く整理します。")
    assert "Free chat" not in response.answer


def test_context_answer_service_free_chat_identity_timeout_stays_on_identity():
    client = FakeLlmClient(
        error=OllamaClientError(
            "provider timed out",
            code="provider_timeout",
            retryable=True,
            http_status=504,
        )
    )
    service = ContextAnswerService(client)  # type: ignore[arg-type]
    request = _request()
    request.user_question = "あなたの名前は？"
    request.task_type = "free_chat"

    response = service.answer(request)

    assert response.fallback_reason == "local_conversation_fallback"
    assert "SMAIナビ" in response.answer
    assert "Smart Market AI" in response.answer
    assert "SMAIで確認する観点" not in response.answer


def test_context_answer_service_free_chat_greeting_uses_llm_micro_provider_call():
    client = FakeLlmClient()
    service = ContextAnswerService(client)  # type: ignore[arg-type]
    request = _request()
    request.user_question = "こんにちは"
    request.task_type = "free_chat"

    response = service.answer(request)

    assert response.gateway_status == "ok"
    assert response.fallback_reason is None
    assert response.provider == "fake"
    assert response.answer.startswith("SMAIナビとして、質問に直接答えます。")
    assert response.llm_generation_ms == 7
    assert len(client.calls) == 1
    joined = "\n".join(message.content for message in client.messages)
    assert "/no_think" in joined
    assert "Minimal context" in joined
    assert "銘柄コックピット" not in joined


def test_context_answer_service_regenerates_once_when_micro_answer_is_weak():
    client = FakeLlmClient(
        answers=[
            "分かる範囲で短く整理します。",
            "私はSMAIナビです。Smart Market AIの中で、SMAIの使い方や確認材料の整理をお手伝いします。",
        ]
    )
    service = ContextAnswerService(client)  # type: ignore[arg-type]
    request = _request()
    request.user_question = "あなたの名前は？"
    request.task_type = "free_chat"

    response = service.answer(request)

    assert response.gateway_status == "ok"
    assert response.fallback_reason is None
    assert "SMAIナビ" in response.answer
    assert len(client.calls) == 2
    assert "前回の回答が短すぎる" in client.calls[1][-1].content


def test_context_answer_service_identity_timeout_uses_identity_fallback():
    client = FakeLlmClient(
        error=OllamaClientError(
            "provider timed out",
            code="provider_timeout",
            retryable=True,
            http_status=504,
        )
    )
    service = ContextAnswerService(client)  # type: ignore[arg-type]
    request = _request()
    request.user_question = "あなたの名前は？"
    request.task_type = "identity"

    response = service.answer(request)

    assert response.gateway_status == "fallback"
    assert response.fallback_reason == "local_conversation_fallback"
    assert "SMAIナビ" in response.answer
    assert "Smart Market AI" in response.answer
    assert "SMAIで確認する観点" not in response.answer


def test_context_answer_service_capability_timeout_uses_capability_fallback():
    client = FakeLlmClient(
        error=OllamaClientError(
            "provider timed out",
            code="provider_timeout",
            retryable=True,
            http_status=504,
        )
    )
    service = ContextAnswerService(client)  # type: ignore[arg-type]
    request = _request()
    request.user_question = "何ができるの？"
    request.task_type = "capability_help"

    response = service.answer(request)

    assert response.gateway_status == "fallback"
    assert response.fallback_reason == "local_conversation_fallback"
    assert "SMAIの使い方" in response.answer
    assert "AI予測とリスク" in response.answer
    assert "SMAIで確認する観点" not in response.answer


def _request(*, active_context_id: str = "forecast-1") -> ContextAnswerRequest:
    return ContextAnswerRequest.model_validate(
        {
            "task": "explain",
            "language": "ja",
            "user_question": "何を見ればよいですか？",
            "active_context_id": active_context_id,
            "model": "qwen3:8b",
            "context": {
                "bundle_id": "bundle-1",
                "title": "銘柄コックピット",
                "source": "decision_report",
                "active_context_id": active_context_id,
                "sections": [
                    {
                        "section_id": "forecast-1",
                        "title": "AI予測インサイト",
                        "source_kind": "forecast",
                        "summary": {
                            "中心予測": "+1.2%",
                            "予測レンジ": "-3.0%から+4.5%",
                        },
                        "included_fields": ["中心予測", "予測レンジ", "信頼度"],
                        "warnings": ["予測レンジが広めです。"],
                        "notes": ["根拠資料とデータ品質を確認します。"],
                    },
                    {
                        "section_id": "risk-1",
                        "title": "下振れ警戒",
                        "source_kind": "risk",
                        "summary": {"下振れ警戒": "42.0"},
                        "included_fields": ["下振れ警戒", "注意点"],
                    },
                ],
                "privacy_notes": [
                    "Provider raw fields, debug logs, and full external source bodies are excluded."
                ],
            },
        }
    )
