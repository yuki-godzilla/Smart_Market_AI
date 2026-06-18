from __future__ import annotations

from app.clients.ollama_client import OllamaClientError
from app.config import GatewaySettings
from app.schemas.common import LlmMessage, LlmProviderResult
from app.schemas.llm_factor import LLMFactorGenerationRequest
from app.services.llm_factor_service import LLMFactorGenerationService


class FakeLlmClient:
    def __init__(
        self,
        *,
        answer: str | None = None,
        error: OllamaClientError | None = None,
    ) -> None:
        self.settings = GatewaySettings()
        self.answer = answer or _llm_json_answer()
        self.error = error
        self.messages: list[LlmMessage] = []
        self.model: str | None = None
        self.timeout_seconds: float | None = None
        self.max_tokens: int | None = None

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
        if self.error is not None:
            raise self.error
        return LlmProviderResult(
            answer=self.answer,
            model=model or "qwen3:14b",
            provider="fake",
            elapsed_ms=12,
            prompt_chars=sum(len(message.content) for message in messages),
            response_chars=len(self.answer),
        )


def test_llm_factor_service_returns_structured_provider_payload() -> None:
    client = FakeLlmClient()
    service = LLMFactorGenerationService(client)  # type: ignore[arg-type]
    request = _request()

    response = service.generate(request)

    assert response.gateway_status == "ok"
    assert response.symbol == "7203.T"
    assert response.provider == "fake"
    assert response.model == "qwen3:14b"
    assert response.profile == "desktop_analysis"
    assert response.factors[0].evidence_ids == ["evidence_001"]
    assert client.model == "qwen3:14b"
    assert client.timeout_seconds == 90.0
    assert client.max_tokens == 1800
    joined = "\n".join(message.content for message in client.messages)
    assert "Output JSON only" in joined
    assert "evidence_001" in joined


def test_llm_factor_service_falls_back_on_unknown_evidence_id() -> None:
    client = FakeLlmClient(answer=_llm_json_answer(evidence_id="outside_context"))
    service = LLMFactorGenerationService(client)  # type: ignore[arg-type]

    response = service.generate(_request())

    assert response.gateway_status == "fallback"
    assert response.fallback_reason == "response_validation_failure"
    assert response.confidence <= 0.35
    assert "evidence" not in response.missing_fields


def test_llm_factor_service_falls_back_when_provider_times_out() -> None:
    client = FakeLlmClient(
        error=OllamaClientError(
            "provider timed out",
            code="provider_timeout",
            retryable=True,
            http_status=504,
        )
    )
    service = LLMFactorGenerationService(client)  # type: ignore[arg-type]

    response = service.generate(_request())

    assert response.gateway_status == "fallback"
    assert response.fallback_reason == "provider_timeout"
    assert response.provider == "ollama"
    assert response.model == "qwen3:14b"
    assert response.warnings


def test_llm_factor_service_off_mode_uses_deterministic_fallback() -> None:
    client = FakeLlmClient()
    request = _request()
    request.execution_mode = "off"
    service = LLMFactorGenerationService(client)  # type: ignore[arg-type]

    response = service.generate(request)

    assert response.gateway_status == "fallback"
    assert response.provider == "deterministic"
    assert response.model == "fallback"
    assert client.messages == []


def _request() -> LLMFactorGenerationRequest:
    return LLMFactorGenerationRequest.model_validate(
        {
            "symbol": "7203.T",
            "company_name": "Toyota Motor",
            "as_of": "2026-06-12",
            "language": "ja",
            "context": {
                "symbol_profile": {"company_name": "Toyota Motor"},
                "research_summary": ["増配と自社株買いを確認できます。"],
                "news_summary": [],
                "forecast_summary": {"中心予測": "+1.2%"},
                "evidence": [
                    {
                        "evidence_id": "evidence_001",
                        "title": "増配と自社株買いを発表",
                        "source_type": "company_ir",
                        "source_url": "https://example.com/ir/7203",
                        "source_date": "2026-06-12",
                        "provider": "fixture",
                        "summary": "増配と自社株買いが確認できます。",
                        "reliability_score": 82,
                    }
                ],
            },
            "preferred_profile": "desktop_analysis",
        }
    )


def _llm_json_answer(*, evidence_id: str = "evidence_001") -> str:
    return (
        "{"
        '"schema_version":"llm_factor.v1",'
        '"symbol":"7203.T",'
        '"overall_summary":"株主還元が材料です。",'
        '"sentiment_label":"positive",'
        '"confidence":0.76,'
        '"factors":[{"title":"株主還元","direction":"positive","summary":"増配と自社株買い。","strength":0.8,"evidence_ids":["'
        + evidence_id
        + '"]}],'
        '"risks":[],'
        '"opportunities":[],'
        '"evidence":[{"evidence_id":"'
        + evidence_id
        + '","title":"増配と自社株買いを発表","source_type":"company_ir","source_url":"https://example.com/ir/7203","source_date":"2026-06-12","summary":"増配。"}],'
        '"missing_fields":[],'
        '"warnings":[],'
        '"prompt_version":"llm_factor_live_mvp.v1"'
        "}"
    )
