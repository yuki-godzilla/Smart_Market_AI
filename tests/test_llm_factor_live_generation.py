from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal

import httpx
import pytest

from backend.core.config import LLMFactorLiveConfig, Settings
from backend.llm_factor import (
    EvidenceSource,
    HttpLLMFactorGatewayClient,
    LiveLLMFactorGenerationService,
    LLMFactorGatewayError,
    build_llm_factor_generation_request,
    build_llm_factor_reference_result_from_settings,
    llm_factor_context_hash,
    llm_factor_result_from_gateway_response,
)
from backend.llm_factor.live_contracts import (
    LLMFactorGenerationRequest,
    LLMFactorGenerationResponse,
)
from backend.llm_factor.validation import LLMFactorLiveValidationError


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
    assert result.result.fallback_reason == "gateway_unavailable"
    assert any("live生成に失敗" in warning for warning in result.result.warnings)


def test_live_llm_factor_service_calibrates_scores_from_limited_evidence(tmp_path) -> None:
    source = _evidence_source()
    request = build_llm_factor_generation_request(
        ticker="7203.T",
        as_of=date(2026, 6, 12),
        company_name="Toyota Motor",
        evidence_sources=[source],
    )
    payload = _gateway_response(request).model_dump(mode="json")
    payload.update(
        {
            "confidence": 0.98,
            "factors": [
                {
                    "title": "株主還元",
                    "direction": "positive",
                    "summary": "増配と自社株買いが確認できます。",
                    "strength": 0.98,
                    "evidence_ids": ["evidence_001"],
                }
            ],
        }
    )
    response = LLMFactorGenerationResponse.model_validate(payload)
    service = LiveLLMFactorGenerationService(
        FakeGatewayClient(response=response),
        config=_live_config(),
        cache_dir=tmp_path,
    )

    result = service.build_reference_result(
        ticker="7203.T",
        as_of=date(2026, 6, 12),
        company_name="Toyota Motor",
        evidence_sources=[source],
        now=datetime(2026, 6, 12, 10, 0, tzinfo=UTC),
    ).result

    assert result.llm_confidence_score <= Decimal("70")
    assert result.llm_catalyst_score <= Decimal("80")
    assert result.evidence_selection.retained_count == 1


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
    assert result.result.fallback_reason == "disabled"
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


def test_http_llm_factor_gateway_client_classifies_non_json_response() -> None:
    request = build_llm_factor_generation_request(
        ticker="7203.T",
        as_of=date(2026, 6, 12),
        evidence_sources=[_evidence_source()],
    )
    client = HttpLLMFactorGatewayClient(
        base_url="http://gateway.local",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, text="not json", request=request)
        ),
    )

    with pytest.raises(LLMFactorGatewayError) as exc_info:
        client.generate(request)

    assert exc_info.value.gateway_error_type == "malformed_json"


def test_live_llm_factor_service_cache_key_changes_by_prompt_and_model(tmp_path) -> None:
    source = _evidence_source()
    request = build_llm_factor_generation_request(
        ticker="7203.T",
        as_of=date(2026, 6, 12),
        company_name="Toyota Motor",
        evidence_sources=[source],
    )
    client = FakeGatewayClient(response=_gateway_response(request))

    LiveLLMFactorGenerationService(
        client,
        config=_live_config(model="qwen3:14b"),
        cache_dir=tmp_path,
    ).build_reference_result(
        ticker="7203.T",
        as_of=date(2026, 6, 12),
        company_name="Toyota Motor",
        evidence_sources=[source],
        now=datetime(2026, 6, 12, 10, 0, tzinfo=UTC),
    )
    LiveLLMFactorGenerationService(
        client,
        config=_live_config(model="qwen3:14b", prompt_version="llm_factor_live_mvp.v2"),
        cache_dir=tmp_path,
    ).build_reference_result(
        ticker="7203.T",
        as_of=date(2026, 6, 12),
        company_name="Toyota Motor",
        evidence_sources=[source],
        now=datetime(2026, 6, 12, 10, 1, tzinfo=UTC),
    )
    LiveLLMFactorGenerationService(
        client,
        config=_live_config(model="qwen3:32b"),
        cache_dir=tmp_path,
    ).build_reference_result(
        ticker="7203.T",
        as_of=date(2026, 6, 12),
        company_name="Toyota Motor",
        evidence_sources=[source],
        now=datetime(2026, 6, 12, 10, 2, tzinfo=UTC),
    )

    assert len(client.requests) == 3


def test_live_llm_factor_validation_rejects_wrong_symbol() -> None:
    request = _request()
    response = _gateway_response(request).model_copy(update={"symbol": "9432.T"})

    with pytest.raises(LLMFactorLiveValidationError) as exc_info:
        llm_factor_result_from_gateway_response(
            response,
            request=request,
            context_hash="context",
            fallback_sources=[_evidence_source()],
        )

    assert exc_info.value.reason == "wrong_symbol"


def test_live_llm_factor_validation_rejects_high_confidence_without_evidence() -> None:
    request = _request()
    response = _gateway_response(request).model_copy(
        update={
            "confidence": 0.91,
            "factors": [],
            "risks": [],
            "opportunities": [],
            "evidence": [],
        }
    )

    with pytest.raises(LLMFactorLiveValidationError) as exc_info:
        llm_factor_result_from_gateway_response(
            response,
            request=request,
            context_hash="context",
            fallback_sources=[_evidence_source()],
        )

    assert exc_info.value.reason == "validation_error"


def test_live_llm_factor_validation_rejects_unknown_evidence_id() -> None:
    request = _request()
    response = LLMFactorGenerationResponse.model_validate(
        {
            **_gateway_response_json(),
            "factors": [
                {
                    "title": "株主還元",
                    "direction": "positive",
                    "summary": "増配と自社株買い。",
                    "strength": 0.8,
                    "evidence_ids": ["outside_context"],
                }
            ],
        }
    )

    with pytest.raises(LLMFactorLiveValidationError) as exc_info:
        llm_factor_result_from_gateway_response(
            response,
            request=request,
            context_hash="context",
            fallback_sources=[_evidence_source()],
        )

    assert exc_info.value.reason == "unknown_evidence"


def test_live_llm_factor_validation_caps_confidence_for_stale_sources() -> None:
    source = _evidence_source(source_date=date(2024, 1, 1))
    request = build_llm_factor_generation_request(
        ticker="7203.T",
        as_of=date(2026, 6, 12),
        company_name="Toyota Motor",
        evidence_sources=[source],
    )

    result = llm_factor_result_from_gateway_response(
        _gateway_response(request),
        request=request,
        context_hash="context",
        fallback_sources=[source],
    )

    assert result.llm_confidence_score <= Decimal("55")
    assert any("古い" in warning for warning in result.warnings)


def test_live_llm_factor_validation_warns_on_contradictory_materials() -> None:
    request = _request()
    payload = _gateway_response_json()
    payload["risks"] = [
        {
            "title": "規制リスク",
            "summary": "規制による需要鈍化リスクが大きい。",
            "severity": 0.82,
            "evidence_ids": ["evidence_001"],
        }
    ]
    response = LLMFactorGenerationResponse.model_validate(payload)

    result = llm_factor_result_from_gateway_response(
        response,
        request=request,
        context_hash="context",
        fallback_sources=[_evidence_source()],
    )

    assert result.llm_confidence_score <= Decimal("55")
    assert any("強弱材料" in warning for warning in result.warnings)


def test_live_llm_factor_validation_truncates_overlong_output() -> None:
    request = _request()
    long_text = "長い説明。" * 120
    payload = _gateway_response_json()
    payload["overall_summary"] = long_text
    payload["factors"] = [
        {
            "title": "長いタイトル" * 20,
            "direction": "positive",
            "summary": long_text,
            "strength": 0.8,
            "evidence_ids": ["evidence_001"],
        }
    ]
    response = LLMFactorGenerationResponse.model_validate(payload)

    result = llm_factor_result_from_gateway_response(
        response,
        request=request,
        context_hash="context",
        fallback_sources=[_evidence_source()],
    )

    assert len(result.summary) <= 700
    assert len(result.bullish_factors[0].reason) <= 320
    assert any("短くしました" in warning for warning in result.warnings)


def test_live_llm_factor_validation_warns_on_version_mismatch() -> None:
    request = _request()
    response = _gateway_response(request).model_copy(
        update={
            "schema_version": "llm_factor.v0",
            "prompt_version": "llm_factor_live_mvp.v0",
        }
    )

    result = llm_factor_result_from_gateway_response(
        response,
        request=request,
        context_hash="context",
        fallback_sources=[_evidence_source()],
    )

    assert result.llm_confidence_score <= Decimal("60")
    assert any("schema_version" in warning for warning in result.warnings)
    assert any("prompt_version" in warning for warning in result.warnings)


def _live_config(
    *,
    model: str | None = None,
    prompt_version: str = "llm_factor_live_mvp.v1",
) -> LLMFactorLiveConfig:
    return LLMFactorLiveConfig(
        enabled=True,
        base_url="http://gateway.local",
        model=model,
        prompt_version=prompt_version,
    )


def _request() -> LLMFactorGenerationRequest:
    return build_llm_factor_generation_request(
        ticker="7203.T",
        as_of=date(2026, 6, 12),
        company_name="Toyota Motor",
        evidence_sources=[_evidence_source()],
    )


def _evidence_source(
    *,
    summary: str = "好決算、増配、自社株買い、AI関連需要の成長が確認できます。",
    source_date: date = date(2026, 6, 12),
) -> EvidenceSource:
    return EvidenceSource(
        title="増配と自社株買いを発表",
        source_type="company_ir",
        source_url="https://example.com/ir/7203",
        source_date=source_date,
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
