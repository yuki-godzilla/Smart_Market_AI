from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from backend.assistant import (
    AssistantGatewayReferencedSection,
    AssistantGatewayResponse,
    MockAssistantGatewayClient,
)
from backend.core.config import Settings
from backend.interpretation import (
    CockpitInterpretationGatewayAdapter,
    CockpitInterpretationService,
    CockpitInterpretationValidationError,
    build_cockpit_interpretation_context,
    build_cockpit_interpretation_from_settings,
    cockpit_interpretation_cache_key,
    cockpit_interpretation_from_gateway_response,
)


def test_cockpit_interpretation_context_builder_is_compact_and_stable() -> None:
    context = _context()
    same_context = _context()

    assert context.symbol == "7203.T"
    assert context.company_name == "Toyota Motor"
    assert context.context_hash == same_context.context_hash
    assert "price_summary" in context.allowed_evidence_ids
    assert "forecast_summary" in context.allowed_evidence_ids
    assert "research_001" in context.allowed_evidence_ids
    assert context.bundle.sections[0].summary["現在値"] == "1234.5"


def test_cockpit_interpretation_validation_maps_gateway_response() -> None:
    context = _context()
    response = _gateway_response()

    result = cockpit_interpretation_from_gateway_response(
        response,
        context=context,
        generated_at=datetime(2026, 6, 18, 10, 0, tzinfo=UTC),
    )

    assert result.status == "live"
    assert result.provider == "fake"
    assert result.model == "qwen3:8b"
    assert result.gateway_profile == "desktop_fast"
    assert result.positive_points[0].title
    assert result.next_checks
    assert not result.is_fallback


def test_cockpit_interpretation_validation_rejects_policy_violation() -> None:
    context = _context()
    response = _gateway_response(answer="この銘柄は買うべきです。")

    with pytest.raises(CockpitInterpretationValidationError) as exc_info:
        cockpit_interpretation_from_gateway_response(response, context=context)

    assert exc_info.value.reason == "policy_violation"


def test_cockpit_interpretation_validation_rejects_unknown_evidence() -> None:
    context = _context()
    response = _gateway_response(
        referenced_sections=[
            AssistantGatewayReferencedSection(
                section_id="unknown",
                title="Unknown",
                source_kind="test",
            )
        ]
    )

    with pytest.raises(CockpitInterpretationValidationError) as exc_info:
        cockpit_interpretation_from_gateway_response(response, context=context)

    assert exc_info.value.reason == "unknown_evidence"


def test_cockpit_interpretation_disabled_uses_deterministic_fallback(tmp_path) -> None:
    result = build_cockpit_interpretation_from_settings(
        _context(),
        settings=Settings(),
        cache_dir=tmp_path,
        now=datetime(2026, 6, 18, 10, 0, tzinfo=UTC),
    )

    assert result.result.status == "disabled"
    assert result.result.fallback_reason == "disabled"
    assert result.result.provider == "deterministic"
    assert result.cache.status == "disabled"


def test_cockpit_interpretation_service_uses_gateway_and_cache(tmp_path) -> None:
    context = _context()
    client = MockAssistantGatewayClient(response=_gateway_response())
    service = CockpitInterpretationService(
        CockpitInterpretationGatewayAdapter(client),
        config=Settings.model_validate(
            {"llm_interpretation": {"cockpit": {"enabled": True}}}
        ).llm_interpretation.cockpit,
        cache_dir=tmp_path,
    )

    first = service.interpret(
        context,
        now=datetime(2026, 6, 18, 10, 0, tzinfo=UTC),
    )
    second = service.interpret(
        context,
        now=datetime(2026, 6, 18, 10, 1, tzinfo=UTC),
    )

    assert first.result.status == "live"
    assert first.cache.status == "miss"
    assert second.cache.status == "hit"
    assert len(client.requests) == 1
    assert client.requests[0].task_type == "cockpit_interpretation"


def test_cockpit_interpretation_cache_key_changes_by_prompt_and_model() -> None:
    base = dict(
        symbol="7203.T",
        as_of="2026-06-18",
        context_hash="abc",
        prompt_version="cockpit_interpretation_mvp.v1",
        schema_version="cockpit_interpretation.v1",
        model="qwen3:8b",
        gateway_profile="desktop_fast",
    )

    assert cockpit_interpretation_cache_key(**base) != cockpit_interpretation_cache_key(
        **{**base, "model": "qwen3:14b"}
    )
    assert cockpit_interpretation_cache_key(**base) != cockpit_interpretation_cache_key(
        **{**base, "prompt_version": "cockpit_interpretation_mvp.v2"}
    )


def _context():
    return build_cockpit_interpretation_context(
        symbol="7203.T",
        company_name="Toyota Motor",
        as_of=date(2026, 6, 18),
        price_summary={"現在値": "1234.5", "前日比": "+1.2%"},
        forecast_summary={"中心予測": "+0.8%", "方向": "mixed"},
        investment_score={"総合": "72", "品質": "16"},
        research_evidence=[
            {
                "title": "増配と自社株買いを発表",
                "source_type": "company_ir",
                "summary": "株主還元姿勢を確認できます。",
                "published_at": "2026-06-18",
            }
        ],
        warnings=["一部ニュースは未確認です。"],
        now=datetime(2026, 6, 18, 9, 0, tzinfo=UTC),
    )


def _gateway_response(
    *,
    answer: str = "価格、予測、根拠資料を分けて確認する局面です。",
    referenced_sections: list[AssistantGatewayReferencedSection] | None = None,
) -> AssistantGatewayResponse:
    return AssistantGatewayResponse(
        answer=answer,
        materials=["Investment Scoreの品質項目は確認材料です。"],
        cautions=["予測とニュース材料の方向が一方で異なる可能性があります。"],
        next_checkpoints=["最新ニュースと適時開示を確認してください。"],
        referenced_sections=referenced_sections
        or [
            AssistantGatewayReferencedSection(
                section_id="investment_score",
                title="Investment Score",
                source_kind="cockpit_score",
            )
        ],
        confidence="medium",
        provider="fake",
        model="qwen3:8b",
        profile="desktop_fast",
        elapsed_ms=12,
        gateway_status="ok",
    )
