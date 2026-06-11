from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.context_answer import (
    ContextAnswerRequest,
    ContextAnswerResponse,
    ContextReferencedSection,
)


def test_context_answer_request_accepts_smai_like_context_bundle():
    request = ContextAnswerRequest.model_validate(
        {
            "schema_version": "assistant-gateway-request-v1",
            "task": "explain",
            "language": "ja",
            "user_question": "AI予測インサイトでは何を見る？",
            "context": {
                "schema_version": "assistant-context-bundle-v1",
                "bundle_id": "bundle-1",
                "title": "銘柄コックピット / AI予測インサイト",
                "source": "decision_report",
                "created_at": "2026-06-11T10:00:00+09:00",
                "language": "ja",
                "active_context_id": "forecast-1",
                "sections": [
                    {
                        "section_id": "forecast-1",
                        "title": "AI予測インサイト",
                        "source_kind": "forecast",
                        "symbol": "7203.T",
                        "summary": {
                            "中心予測": "+1.2%",
                            "予測レンジ": "-3.0%〜+4.5%",
                        },
                        "included_fields": ["中心予測", "予測レンジ", "信頼度"],
                        "warnings": ["予測レンジが広めです。"],
                        "notes": ["根拠資料とデータ品質も確認します。"],
                    }
                ],
                "privacy_notes": [
                    "Provider raw fields, debug logs, and full external source bodies are excluded."
                ],
            },
            "constraints": {
                "no_investment_advice": True,
                "do_not_change_scores": True,
                "do_not_rank_symbols": True,
                "answer_format": "materials_cautions_checkpoints",
                "require_referenced_sections": True,
            },
        }
    )

    assert request.schema_version == "assistant-gateway-request-v1"
    assert request.context.sections[0].section_id == "forecast-1"
    assert request.context.sections[0].summary["中心予測"] == "+1.2%"


def test_context_answer_request_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        ContextAnswerRequest.model_validate(
            {
                "user_question": "hello",
                "context": {
                    "bundle_id": "bundle-1",
                    "title": "context",
                    "sections": [
                        {
                            "section_id": "section-1",
                            "title": "section",
                            "source_kind": "manual",
                        }
                    ],
                },
                "provider_raw": {"debug": "must not pass"},
            }
        )


def test_context_answer_response_schema_contains_structured_fields():
    response = ContextAnswerResponse(
        answer="中心予測、予測レンジ、信頼度の順に確認します。",
        materials=["中心予測", "予測レンジ", "信頼度"],
        cautions=["予測は将来保証ではありません。"],
        next_checkpoints=["根拠資料を確認します。"],
        referenced_sections=[
            ContextReferencedSection(
                section_id="forecast-1",
                title="AI予測インサイト",
                source_kind="forecast",
            )
        ],
        confidence="medium",
        safety_notes=["スコア、予測値、ランキング順位は変更していません。"],
        provider="ollama",
        model="qwen3:8b",
        elapsed_ms=42,
    )

    assert response.schema_version == "assistant-gateway-response-v1"
    assert response.materials == ["中心予測", "予測レンジ", "信頼度"]
    assert response.referenced_sections[0].section_id == "forecast-1"
