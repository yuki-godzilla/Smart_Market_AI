from __future__ import annotations

from app.config import GatewaySettings
from app.schemas.common import LlmMessage, LlmProviderResult
from app.schemas.context_answer import ContextAnswerRequest
from app.services.context_answer_service import ContextAnswerService


class FakeLlmClient:
    def __init__(self, *, answer: str | None = None) -> None:
        self.messages: list[LlmMessage] = []
        self.model: str | None = None
        self.timeout_seconds: float | None = None
        self.max_tokens: int | None = None
        self.settings = GatewaySettings(DEFAULT_LLM_MODEL="qwen3:8b")
        self.answer = answer or (
            '{"answer":"LLM structured answer.","materials":["LLM material 1","LLM material 2"],'
            '"cautions":["LLM caution"],"next_checkpoints":["LLM next check"],'
            '"confidence":"high"}'
        )

    def chat(
        self,
        messages: list[LlmMessage],
        *,
        model: str | None = None,
        timeout_seconds: float | None = None,
        max_tokens: int | None = None,
    ) -> LlmProviderResult:
        self.messages = messages
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        return LlmProviderResult(
            answer=self.answer,
            model=model or "qwen3:8b",
            provider="fake",
            elapsed_ms=7,
        )


def test_context_answer_service_uses_structured_llm_payload():
    client = FakeLlmClient()
    service = ContextAnswerService(client)  # type: ignore[arg-type]
    request = _request()

    response = service.answer(request)

    assert response.answer == "LLM structured answer."
    assert response.provider == "fake"
    assert response.model == "qwen3:8b"
    assert response.profile == "assistant_fast"
    assert response.elapsed_ms == 7
    assert response.materials == ["LLM material 1", "LLM material 2"]
    assert response.cautions == ["LLM caution"]
    assert response.next_checkpoints == ["LLM next check"]
    assert response.referenced_sections[0].section_id == "forecast-1"
    assert response.confidence == "high"
    assert response.safety_notes
    assert client.model == "qwen3:8b"
    assert client.timeout_seconds == 75.0
    assert client.max_tokens == 700
    assert any("AI予測インサイト" in message.content for message in client.messages)
    assert any("Return only valid JSON" in message.content for message in client.messages)


def test_context_answer_service_uses_active_section_when_payload_is_unstructured():
    client = FakeLlmClient(answer="LLM plain answer")
    service = ContextAnswerService(client)  # type: ignore[arg-type]
    request = _request(active_context_id="risk-1")

    response = service.answer(request)

    assert response.answer.startswith("下振れ警戒では")
    assert response.materials[0] == "下振れ警戒"
    assert response.referenced_sections[0].section_id == "risk-1"


def test_context_answer_service_falls_back_when_llm_payload_is_invalid_json():
    client = FakeLlmClient(answer='{"answer": "", "materials": ["中心予測"]}')
    service = ContextAnswerService(client)  # type: ignore[arg-type]
    request = _request()

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

    response = service.answer(request)

    assert response.answer.startswith("AI予測インサイトでは")
    assert response.materials[:3] == ["AI予測インサイト", "中心予測", "予測レンジ"]
    assert "????" not in response.answer


def test_context_answer_service_prompt_includes_intent_specific_guide():
    client = FakeLlmClient()
    service = ContextAnswerService(client)  # type: ignore[arg-type]
    request = _request()
    request.user_question = (
        "SMAI Assistant intent: forecast_risk_compare\n"
        "User question: 予測とリスクを比べて"
    )

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

    assert response.profile == "assistant_standard"
    assert client.timeout_seconds == 90.0
    assert client.max_tokens == 1000


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
