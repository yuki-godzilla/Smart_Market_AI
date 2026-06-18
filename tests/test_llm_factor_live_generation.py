from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal

import httpx

from backend.core.config import LLMFactorLiveConfig, Settings
from backend.llm_factor import (
    EvidenceSource,
    HttpLLMFactorGatewayClient,
    LiveLLMFactorGenerationService,
    LLMFactorGatewayError,
    build_llm_factor_generation_request,
    build_llm_factor_reference_result_from_settings,
    llm_factor_context_hash,
)
from backend.llm_factor.live_contracts import (
    LLMFactorGenerationRequest,
    LLMFactorGenerationResponse,
)


class FakeGatewayClient:
    def __init__(
        self,
        *,
        response: LLMFactorGenerationResponse | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.requests: list[LLMFactorGenerationRequest] = []

    def generate(self, request: LLMFactorGenerationRequest) -> LLMFactorGenerationResponse:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        if self.response is None:
            raise AssertionError("response is required")
        return self.response


def test_llm_factor_context_builder_is_compact_and_hash_is_stable() -> None:
    request = build_llm_factor_generation_request(
        ticker="7203.T",
        as_of=date(2026, 6, 12),
        company_name="Toyota Motor",
        evidence_sources=[_evidence_source(summary="増配と自社株買い。" * 100)],
        max_text_chars=80,
    )
    same_request = build_llm_factor_generation_request(
        ticker="7203.T",
        as_of=date(2026, 6, 12),
        company_name="Toyota Motor",
        evidence_sources=[_evidence_source(summary="増配と自社株買い。" * 100)],
        max_text_chars=80,
    )

    evidence = request.context.evidence[0]
    assert evidence.evidence_id == "evidence_001"
    assert len(evidence.summary) <= 80
    assert evidence.source_url == "https://example.com/ir/7203"
    assert request.context.symbol_profile["company_name"] == "Toyota Motor"
    assert llm_factor_context_hash(request) == llm_factor_context_hash(same_request)


def test_live_llm_factor_service_maps_gateway_response_and_reuses_cache(tmp_path) -> None:
    source = _evidence_source()
    request = build_llm_factor_generation_request(
        ticker="7203.T",
        as_of=date(2026, 6, 12),
        company_name="Toyota Motor",
        evidence_sources=[source],
    )
    response = _gateway_response(request)
    client = FakeGatewayClient(response=response)
    service = LiveLLMFactorGenerationService(
        client,
        config=_live_config(),
        cache_dir=tmp_path,
        ttl_seconds=3600,
    )

    first = service.build_reference_result(
        ticker="7203.T",
        as_of=date(2026, 6, 12),
        company_name="Toyota Motor",
        evidence_sources=[source],
        now=datetime(2026, 6, 12, 10, 0, tzinfo=UTC),
    )
    second = service.build_reference_result(
        ticker="7203.T",
        as_of=date(2026, 6, 12),
        company_name="Toyota Motor",
        evidence_sources=[source],
        now=datetime(2026, 6, 12, 10, 5, tzinfo=UTC),
    )

    assert first.cache.status == "miss"
    assert first.result.provider == "fake"
    assert first.result.model_name == "qwen3:14b"
    assert first.result.gateway_profile == "desktop_analysis"
    assert first.result.sentiment_label == "positive"
    assert first.result.bullish_factors[0].source_url == source.source_url
    assert second.cache.status == "hit"
    assert second.result.generated_at == first.result.generated_at
    assert len(client.requests) == 1


def test_live_llm_factor_service_falls_back_when_gateway_fails(tmp_path) -> None:
    client = FakeGatewayClient(
        error=LLMFactorGatewayError(
            "gateway unavailable",
            gateway_error_type="connection_refused",
        )
    )
    service = LiveLLMFactorGenerationService(
        client,
        config=_live_config(),
        cache_dir=tmp_path,
        ttl_seconds=3600,
    )

    result = service.build_reference_result(
        ticker="9532.T",
        as_of=date(2026, 6, 12),
        evidence_sources=[_evidence_source()],
        now=datetime(2026, 6, 12, 10, 0, tzinfo=UTC),
    )

    assert result.result.provider == "deterministic"
    assert result.result.gateway_status == "fallback"
    assert result.result.fallback_reason == "connection_refused"
    assert any("live生成に失敗" in warning for warning in result.result.warnings)


def test_llm_factor_reference_from_settings_stays_deterministic_by_default(tmp_path) -> None:
    result = build_llm_factor_reference_result_from_settings(
        ticker="7203.T",
        as_of=date(2026, 6, 12),
        evidence_sources=[_evidence_source()],
        settings=Settings(),
        cache_dir=tmp_path,
        now=datetime(2026, 6, 12, 10, 0, tzinfo=UTC),
    )

    assert result.result.gateway_status == "fallback"
    assert result.result.fallback_reason == "live_disabled"
    assert result.result.provider is None
    assert result.result.model_name == "deterministic_fake_llm_factor"


def test_http_llm_factor_gateway_client_posts_contract_payload() -> None:
    observed: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["url"] = str(request.url)
        payload = request.read().decode("utf-8")
        observed["payload"] = payload
        return httpx.Response(
            200,
            json=_gateway_response_json(),
            request=request,
        )

    request = build_llm_factor_generation_request(
        ticker="7203.T",
        as_of=date(2026, 6, 12),
        evidence_sources=[_evidence_source()],
    )
    client = HttpLLMFactorGatewayClient(
        base_url="http://gateway.local",
        model="qwen3:14b",
        preferred_profile="desktop_analysis",
        transport=httpx.MockTransport(handler),
    )

    response = client.generate(request)

    assert observed["url"] == "http://gateway.local/api/v1/llm-factor/generate"
    payload = json.loads(str(observed["payload"]))
    assert payload["model"] == "qwen3:14b"
    assert response.provider == "fake"
    assert response.model == "qwen3:14b"


def _live_config() -> LLMFactorLiveConfig:
    return LLMFactorLiveConfig(enabled=True, base_url="http://gateway.local")


def _evidence_source(
    *,
    summary: str = "好決算、増配、自社株買い、AI関連需要の成長が確認できます。",
) -> EvidenceSource:
    return EvidenceSource(
        title="増配と自社株買いを発表",
        source_type="company_ir",
        source_url="https://example.com/ir/7203",
        source_date=date(2026, 6, 12),
        fetched_at=datetime(2026, 6, 12, 9, 0, tzinfo=UTC),
        provider="fixture",
        summary=summary,
        reliability_score=Decimal("82"),
    )


def _gateway_response(request: LLMFactorGenerationRequest) -> LLMFactorGenerationResponse:
    payload = _gateway_response_json()
    payload["symbol"] = request.symbol
    payload["request_id"] = request.request_id
    return LLMFactorGenerationResponse.model_validate(payload)


def _gateway_response_json() -> dict[str, object]:
    return {
        "schema_version": "llm_factor.v1",
        "symbol": "7203.T",
        "overall_summary": "出典付き材料では株主還元と成長投資が確認できます。",
        "sentiment_label": "positive",
        "confidence": 0.78,
        "factors": [
            {
                "title": "株主還元",
                "direction": "positive",
                "summary": "増配と自社株買いが確認できます。",
                "strength": 0.82,
                "evidence_ids": ["evidence_001"],
            }
        ],
        "risks": [],
        "opportunities": [
            {
                "title": "AI需要",
                "summary": "AI関連需要の成長が材料です。",
                "impact": 0.7,
                "evidence_ids": ["evidence_001"],
            }
        ],
        "evidence": [
            {
                "evidence_id": "evidence_001",
                "title": "増配と自社株買いを発表",
                "source_type": "company_ir",
                "source_url": "https://example.com/ir/7203",
                "source_date": "2026-06-12",
                "summary": "増配と自社株買い。",
            }
        ],
        "missing_fields": [],
        "warnings": [],
        "prompt_version": "llm_factor_live_mvp.v1",
        "provider": "fake",
        "model": "qwen3:14b",
        "profile": "desktop_analysis",
        "generated_at": "2026-06-12T10:00:00+00:00",
        "elapsed_ms": 10,
        "gateway_status": "ok",
    }
