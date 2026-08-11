from __future__ import annotations

from datetime import UTC, datetime

import pytest

from backend.assistant.gateway_contracts import (
    AssistantGatewayReferencedSection,
    AssistantGatewayResponse,
)
from backend.assistant.news_interpretation_contracts import (
    AssistantGatewayNewsEvidencePoint,
    AssistantGatewayNewsHandoffHint,
    AssistantGatewayNewsInterpretation,
)
from backend.core.config import Settings
from backend.interpretation import (
    build_deterministic_news_interpretation,
    build_news_interpretation_context,
    news_interpretation_from_gateway_response,
)
from backend.interpretation.news_interpretation_validation import NewsInterpretationValidationError
from backend.news.radar_candidates import build_radar_candidate_map
from backend.news.sources import build_demo_news_dashboard_snapshot
from ui.news_interpretation import (
    clear_stale_news_interpretation_state,
    news_interpretation_state_owner,
)


def _context():
    snapshot = build_demo_news_dashboard_snapshot()
    return build_news_interpretation_context(snapshot, build_radar_candidate_map(snapshot))


def test_news_interpretation_context_is_bounded_and_separates_macro_handoffs():
    context = _context()

    assert len(context.bundle.sections) <= 8
    assert len(context.allowed_material_ids) <= 4
    assert len(context.allowed_sector_ids) <= 4
    assert len(context.allowed_handoff_candidate_ids) <= 3
    assert all(
        context.candidate_provenance[candidate_id] != "macro_proxy"
        for candidate_id in context.allowed_handoff_candidate_ids
    )
    assert {"news_scope", "news_source_quality"}.issubset(context.allowed_evidence_ids)


def test_deterministic_news_interpretation_does_not_invent_impact_direction():
    context = _context()
    result = build_deterministic_news_interpretation(
        context,
        status="disabled",
        fallback_reason="disabled",
    )

    assert result.status == "disabled"
    assert result.is_fallback is True
    assert all(item.business_impact_direction == "unclear" for item in result.material_notes)
    assert all(item.impact_horizon == "unclear" for item in result.material_notes)
    assert [item.candidate_id for item in result.handoff_hints] == (
        context.allowed_handoff_candidate_ids
    )


def test_live_news_interpretation_requires_exact_handoff_order():
    context = _context()
    cited = ["news_scope", "news_source_quality"]
    handoffs = []
    if context.allowed_handoff_candidate_ids:
        cited.append("news_cockpit_handoffs")
        handoffs = [
            AssistantGatewayNewsHandoffHint(
                candidate_id=candidate_id,
                reason=AssistantGatewayNewsEvidencePoint(
                    text="表示済みニュースとの関係をコックピットで確認します。",
                    cited_evidence_ids=["news_cockpit_handoffs"],
                ),
            )
            for candidate_id in context.allowed_handoff_candidate_ids
        ]
    by_id = {section.section_id: section for section in context.bundle.sections}
    response = AssistantGatewayResponse(
        answer="表示中のニュース材料を確認します。",
        materials=[],
        cautions=[],
        next_checkpoints=[],
        referenced_sections=[
            AssistantGatewayReferencedSection(
                section_id=evidence_id,
                title=by_id[evidence_id].title,
                source_kind=by_id[evidence_id].source_kind,
            )
            for evidence_id in cited
        ],
        news_interpretation=AssistantGatewayNewsInterpretation(
            news_context_id=context.news_context_id,
            context_hash=context.context_hash,
            summary=AssistantGatewayNewsEvidencePoint(
                text="表示中のニュース材料だけを確認対象にします。",
                cited_evidence_ids=["news_scope"],
            ),
            noise_notes=[
                AssistantGatewayNewsEvidencePoint(
                    text="鮮度と重複を分けて確認します。",
                    cited_evidence_ids=["news_source_quality"],
                )
            ],
            handoff_hints=handoffs,
        ),
        provider="mock",
        model="mock-model",
        profile="desktop_fast",
    )

    result = news_interpretation_from_gateway_response(
        response,
        context=context,
        generated_at=datetime.now(UTC),
    )
    assert result.status == "live"

    unsupported = response.model_copy(deep=True)
    assert unsupported.news_interpretation is not None
    unsupported.news_interpretation.summary.text = "根拠にない99%の影響です。"
    with pytest.raises(NewsInterpretationValidationError, match="unsupported_number"):
        news_interpretation_from_gateway_response(
            unsupported,
            context=context,
            generated_at=datetime.now(UTC),
        )

    if len(handoffs) > 1:
        response.news_interpretation.handoff_hints.reverse()  # type: ignore[union-attr]
        with pytest.raises(NewsInterpretationValidationError, match="wrong_candidate"):
            news_interpretation_from_gateway_response(
                response,
                context=context,
                generated_at=datetime.now(UTC),
            )


def test_news_interpretation_defaults_disabled_and_state_owner_is_user_scoped():
    settings = Settings()
    assert settings.llm_interpretation.news.enabled is False
    assert settings.llm_interpretation.news.schema_version == "news_interpretation.v1"

    state: dict[str, object] = {
        "investment_news_interpretation_owner": "old|hash",
        "investment_news_interpretation_result": {"stale": True},
        "investment_news_interpretation_cache_hit": True,
    }
    owner = news_interpretation_state_owner(user_id="alice", context_hash="new-hash")
    clear_stale_news_interpretation_state(state, owner=owner)
    assert state == {}
