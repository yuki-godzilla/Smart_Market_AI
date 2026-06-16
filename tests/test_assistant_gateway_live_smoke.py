from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

from backend.assistant import AssistantRequest, create_assistant_service_from_settings
from backend.core.config import Settings
from backend.reporting import build_decision_report_context, build_report_section

pytestmark = pytest.mark.skipif(
    os.getenv("SMAI_ASSISTANT_GATEWAY_LIVE_SMOKE") != "1",
    reason=(
        "Set SMAI_ASSISTANT_GATEWAY_LIVE_SMOKE=1 and start smai-ai-gateway "
        "to run the parent SMAI live Gateway smoke."
    ),
)


def test_parent_smai_assistant_can_use_live_gateway_context_answer():
    base_url = os.getenv("SMAI_ASSISTANT_GATEWAY_BASE_URL", "http://127.0.0.1:8088")
    model = os.getenv("SMAI_ASSISTANT_GATEWAY_MODEL") or None
    timeout_seconds = float(os.getenv("SMAI_ASSISTANT_GATEWAY_TIMEOUT_SECONDS", "90"))
    settings = Settings.model_validate(
        {
            "assistant": {
                "gateway": {
                    "enabled": True,
                    "base_url": base_url,
                    "context_answer_path": "/api/v1/context-answer",
                    "timeout_seconds": timeout_seconds,
                    "model": model,
                }
            }
        }
    )
    service = create_assistant_service_from_settings(settings)

    response = service.answer(
        AssistantRequest(
            question="AI予測インサイトでは最初に何を確認しますか？",
            report_context=_sample_report_context(),
            max_points=4,
            conversation_id="live-smoke-context-answer",
            active_context_id="cockpit_forecast",
            referenced_context_ids=["cockpit_forecast"],
            gateway_task_type="forecast_risk_compare",
        )
    )

    assert response.answer.strip()
    assert response.reasons
    assert response.cautions
    assert response.next_checkpoints
    assert response.intent == "forecast"
    assert response.response_source == "llm"
    assert response.provider == "ollama"
    assert response.model == (model or "llama3.2:3b")
    assert response.gateway_status == "ok"
    assert response.fallback_reason is None
    assert response.request_id
    assert response.timeout_sec is not None
    assert response.llm_generation_ms is not None


def _sample_report_context():
    forecast_section = build_report_section(
        title="AI予測インサイト",
        source_kind="cockpit",
        provider="live-smoke",
        symbol="7203.T",
        summary={
            "中心予測": "+1.2%",
            "予測レンジ": "-3.0%から+5.0%",
            "上向き材料": "決算進捗と円安感応度",
            "下振れ警戒": "外部環境と材料不足",
        },
        warnings=["予測は将来価格を保証するものではありません。"],
        notes=["投資判断の補助として、根拠資料とデータ品質を確認します。"],
    )
    return build_decision_report_context(
        title="投資判断レポート - 7203.T",
        sections=[forecast_section],
        tags=["assistant", "cockpit", "live-smoke"],
        created_at=datetime(2026, 6, 13, 10, 0, tzinfo=UTC),
    )
