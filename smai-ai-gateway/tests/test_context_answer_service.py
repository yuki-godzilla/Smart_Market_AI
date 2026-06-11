from __future__ import annotations

from app.schemas.common import LlmMessage, LlmProviderResult
from app.schemas.context_answer import ContextAnswerRequest
from app.services.context_answer_service import ContextAnswerService


class FakeLlmClient:
    def __init__(self) -> None:
        self.messages: list[LlmMessage] = []
        self.model: str | None = None

    def chat(
        self,
        messages: list[LlmMessage],
        *,
        model: str | None = None,
    ) -> LlmProviderResult:
        self.messages = messages
        self.model = model
        return LlmProviderResult(
            answer="中心予測、予測レンジ、信頼度を順に確認します。",
            model=model or "qwen3:8b",
            provider="fake",
            elapsed_ms=7,
        )


def test_context_answer_service_wraps_llm_answer_with_structured_context():
    client = FakeLlmClient()
    service = ContextAnswerService(client)  # type: ignore[arg-type]
    request = _request()

    response = service.answer(request)

    assert response.answer == "中心予測、予測レンジ、信頼度を順に確認します。"
    assert response.provider == "fake"
    assert response.model == "qwen3:8b"
    assert response.elapsed_ms == 7
    assert response.materials[:3] == ["AI予測インサイト", "中心予測", "予測レンジ"]
    assert "予測レンジが広めです。" in response.cautions
    assert "根拠資料とデータ品質も確認します。" in response.next_checkpoints
    assert response.referenced_sections[0].section_id == "forecast-1"
    assert response.confidence == "medium"
    assert response.safety_notes
    assert client.model == "qwen3:8b"
    assert any("AI予測インサイト" in message.content for message in client.messages)


def test_context_answer_service_uses_active_section_when_supplied():
    client = FakeLlmClient()
    service = ContextAnswerService(client)  # type: ignore[arg-type]
    request = _request(active_context_id="risk-1")

    response = service.answer(request)

    assert response.materials[0] == "下降警戒"
    assert response.referenced_sections[0].section_id == "risk-1"


def _request(*, active_context_id: str = "forecast-1") -> ContextAnswerRequest:
    return ContextAnswerRequest.model_validate(
        {
            "task": "explain",
            "language": "ja",
            "user_question": "何を見ればいい？",
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
                            "予測レンジ": "-3.0%〜+4.5%",
                        },
                        "included_fields": ["中心予測", "予測レンジ", "信頼度"],
                        "warnings": ["予測レンジが広めです。"],
                        "notes": ["根拠資料とデータ品質も確認します。"],
                    },
                    {
                        "section_id": "risk-1",
                        "title": "下降警戒",
                        "source_kind": "risk",
                        "summary": {"下降警戒": "42.0"},
                        "included_fields": ["下降警戒", "注意点"],
                    },
                ],
                "privacy_notes": [
                    "Provider raw fields, debug logs, and full external source bodies are excluded."
                ],
            },
        }
    )
