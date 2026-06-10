from __future__ import annotations

from datetime import UTC, datetime

from backend.assistant import (
    AssistantGatewayError,
    AssistantGatewayReferencedSection,
    AssistantGatewayResponse,
    AssistantRequest,
    GatewayBackedAssistantService,
    MockAssistantGatewayClient,
)
from backend.reporting import build_decision_report_context, build_report_section


def _sample_report_context():
    forecast_section = build_report_section(
        title="AI予測インサイト",
        source_kind="cockpit",
        provider="mock",
        symbol="7203.T",
        summary={
            "中心予測": "+1.2%",
            "予測レンジ": "-3.0%〜+5.0%",
        },
        warnings=["予測は将来価格の保証ではありません。"],
        notes=["AI予測インサイトは確認材料です。"],
    )
    return build_decision_report_context(
        title="投資判断レポート - 7203.T",
        sections=[forecast_section],
        tags=["assistant", "cockpit"],
        created_at=datetime(2026, 6, 10, 10, 0, tzinfo=UTC),
    )


def test_gateway_backed_assistant_uses_gateway_response_when_valid():
    gateway_response = AssistantGatewayResponse(
        answer="Gateway側では、中心予測、予測レンジ、信頼度の順に確認します。",
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
        safety_notes=["スコアや予測値は変更していません。"],
        provider="mock",
        model="mock-assistant-gateway",
    )
    client = MockAssistantGatewayClient(response=gateway_response)
    service = GatewayBackedAssistantService(client)

    response = service.answer(
        AssistantRequest(
            question="AI予測インサイトをどう読む？",
            report_context=_sample_report_context(),
        )
    )

    assert response.intent == "forecast"
    assert response.answer.startswith("Gateway側では")
    assert response.reasons == ["中心予測", "予測レンジ"]
    assert "スコアや予測値は変更していません。" in response.cautions
    assert response.next_checkpoints == ["モデル合意度を確認します。"]
    assert response.citations[0].section_title == "AI予測インサイト"
    assert len(client.requests) == 1
    assert client.requests[0].constraints.no_investment_advice
    assert client.requests[0].context.sections[0].title == "AI予測インサイト"


def test_gateway_backed_assistant_falls_back_when_client_raises():
    client = MockAssistantGatewayClient(error=AssistantGatewayError("gateway unavailable"))
    service = GatewayBackedAssistantService(client)

    response = service.answer(
        AssistantRequest(
            question="AI予測インサイトをどう読む？",
            report_context=_sample_report_context(),
        )
    )

    assert "中心予測を主役" in response.answer
    assert response.intent == "forecast"
    assert len(client.requests) == 1


def test_gateway_backed_assistant_falls_back_when_schema_is_invalid():
    client = MockAssistantGatewayClient(
        response={
            "materials": ["中心予測"],
            "cautions": ["answer が欠落しています。"],
        }
    )
    service = GatewayBackedAssistantService(client)

    response = service.answer(
        AssistantRequest(
            question="AI予測インサイトをどう読む？",
            report_context=_sample_report_context(),
        )
    )

    assert "中心予測を主役" in response.answer
    assert response.intent == "forecast"
    assert len(client.requests) == 1


def test_gateway_backed_assistant_without_context_does_not_call_gateway():
    client = MockAssistantGatewayClient()
    service = GatewayBackedAssistantService(client)

    response = service.answer(AssistantRequest(question="次に何を確認すればいい？"))

    assert "一般的な確認順" in response.answer
    assert client.requests == []


def test_mock_assistant_gateway_client_returns_network_free_default_response():
    client = MockAssistantGatewayClient()
    service = GatewayBackedAssistantService(client)

    response = service.answer(
        AssistantRequest(
            question="AI予測インサイトをどう読む？",
            report_context=_sample_report_context(),
        )
    )

    assert response.answer.startswith("Gateway mock response")
    assert "AI予測インサイト" in response.reasons
    assert "スコア、ランキング、予測値は変更していません。" in response.cautions
    assert len(client.requests) == 1
