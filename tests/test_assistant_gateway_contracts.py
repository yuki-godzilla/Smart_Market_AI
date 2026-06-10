from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from backend.assistant import (
    ASSISTANT_CONTEXT_BUNDLE_SCHEMA_VERSION,
    ASSISTANT_GATEWAY_REQUEST_SCHEMA_VERSION,
    ASSISTANT_GATEWAY_RESPONSE_SCHEMA_VERSION,
    AssistantGatewayMessage,
    AssistantGatewayReferencedSection,
    AssistantGatewayRequest,
    AssistantGatewayResponse,
    build_assistant_context_bundle,
    build_assistant_gateway_request,
)
from backend.reporting import build_decision_report_context, build_report_section


def _sample_gateway_report_context():
    forecast_section = build_report_section(
        title="AI予測インサイト",
        source_kind="cockpit",
        provider="yahoo",
        symbol="7203.T",
        summary={
            "中心予測": "+1.2%",
            "予測レンジ": "-3.0%〜+5.0%",
            "provider_raw_payload": "SECRET_RAW_PAYLOAD",
        },
        rows=[
            {
                "metric": "model_agreement",
                "value": "3/4 models agree",
                "full_text": "SECRET_FULL_TEXT",
            },
            {
                "metric": "confidence",
                "value": "medium",
            },
        ],
        warnings=["予測は将来価格の保証ではありません。"],
        notes=["AI予測インサイトは確認材料です。"],
        metadata={"provider_raw": "SECRET_METADATA"},
    )
    ranking_section = build_report_section(
        title="ランキング理由",
        source_kind="ranking",
        symbol="7203.T",
        summary={"AI総合": "74.2", "上昇気配": "68.0", "下降警戒": "42.0"},
    )
    return build_decision_report_context(
        title="投資判断レポート - 7203.T",
        sections=[forecast_section, ranking_section],
        tags=["assistant", "cockpit"],
        created_at=datetime(2026, 6, 10, 9, 0, tzinfo=UTC),
    )


def test_assistant_context_bundle_redacts_raw_fields_and_keeps_safe_summary():
    bundle = build_assistant_context_bundle(
        _sample_gateway_report_context(),
        bundle_id="bundle-7203",
        active_context_id="cockpit_forecast",
        max_rows_per_section=1,
    )

    assert bundle.schema_version == ASSISTANT_CONTEXT_BUNDLE_SCHEMA_VERSION
    assert bundle.bundle_id == "bundle-7203"
    assert bundle.active_context_id == "cockpit_forecast"
    assert bundle.tags == ["assistant", "cockpit"]
    assert bundle.sections[0].section_id == "cockpit-1"
    assert bundle.sections[0].summary["中心予測"] == "+1.2%"
    assert bundle.sections[0].rows == [{"metric": "model_agreement", "value": "3/4 models agree"}]
    assert "provider_raw_payload" in bundle.sections[0].redacted_fields
    assert "full_text" in bundle.sections[0].redacted_fields
    assert "source.metadata" in bundle.sections[0].redacted_fields
    assert "rows.omitted_by_limit" in bundle.sections[0].redacted_fields
    assert "warnings" in bundle.sections[0].included_fields
    assert "notes" in bundle.sections[0].included_fields
    assert "SECRET" not in repr(bundle.model_dump())


def test_assistant_gateway_request_defaults_to_safety_constraints_and_chat_fields():
    bundle = build_assistant_context_bundle(
        _sample_gateway_report_context(),
        active_context_id="cockpit_forecast",
    )
    request = build_assistant_gateway_request(
        question="  AI予測インサイトはどう読む？  ",
        context=bundle,
        task="chat",
        conversation_id="conversation-1",
        message_history=[AssistantGatewayMessage(role="user", content="前の質問")],
        referenced_context_ids=["cockpit_forecast"],
    )

    assert request.schema_version == ASSISTANT_GATEWAY_REQUEST_SCHEMA_VERSION
    assert request.task == "chat"
    assert request.language == "ja"
    assert request.user_question == "AI予測インサイトはどう読む？"
    assert request.active_context_id == "cockpit_forecast"
    assert request.referenced_context_ids == ["cockpit_forecast"]
    assert request.message_history[0].role == "user"
    assert request.constraints.no_investment_advice
    assert request.constraints.do_not_change_scores
    assert request.constraints.do_not_rank_symbols
    assert request.constraints.answer_format == "materials_cautions_checkpoints"


def test_assistant_gateway_response_schema_is_ui_compatible():
    response = AssistantGatewayResponse(
        answer="中心予測、予測レンジ、信頼度の順に確認します。",
        materials=["中心予測", "予測レンジ"],
        cautions=["予測は将来価格の保証ではありません。"],
        next_checkpoints=["モデル合意度を確認します。"],
        referenced_sections=[
            AssistantGatewayReferencedSection(
                section_id="cockpit-1",
                title="AI予測インサイト",
                source_kind="cockpit",
            )
        ],
        confidence="medium",
        safety_notes=["売買判断ではなく確認材料として回答しました。"],
        provider="ollama",
        model="qwen3:8b",
        elapsed_ms=120,
    )

    assert response.schema_version == ASSISTANT_GATEWAY_RESPONSE_SCHEMA_VERSION
    assert response.referenced_sections[0].section_id == "cockpit-1"
    assert response.confidence == "medium"
    assert response.provider == "ollama"
    assert response.elapsed_ms == 120


def test_assistant_gateway_request_rejects_unknown_fields():
    bundle = build_assistant_context_bundle(_sample_gateway_report_context())

    with pytest.raises(ValidationError):
        AssistantGatewayRequest(
            user_question="この銘柄は買い？",
            context=bundle,
            raw_provider_payload="must not be accepted",
        )
