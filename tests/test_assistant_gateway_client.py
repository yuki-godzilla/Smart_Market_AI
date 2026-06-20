from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx

from backend.assistant import (
    AssistantGatewayError,
    AssistantGatewayReferencedSection,
    AssistantGatewayResponse,
    AssistantMessage,
    AssistantRequest,
    GatewayBackedAssistantService,
    HttpAssistantGatewayClient,
    MockAssistantGatewayClient,
    TemplateAssistantService,
    build_assistant_context_bundle,
    build_assistant_gateway_request,
    create_assistant_gateway_client_from_settings,
    create_assistant_service_from_settings,
)
from backend.core.config import Settings
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


def _sample_gateway_request():
    return build_assistant_gateway_request(
        question="AI予測インサイトをどう読む？",
        context=build_assistant_context_bundle(_sample_report_context()),
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
        profile="assistant_standard",
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
    assert response.cautions == ["予測は将来価格の保証ではありません。"]
    assert response.next_checkpoints == ["モデル合意度を確認します。"]
    assert response.citations[0].section_title == "AI予測インサイト"
    assert response.response_source == "llm"
    assert response.model == "mock-assistant-gateway"
    assert response.provider == "mock"
    assert response.profile == "assistant_standard"
    assert response.gateway_status == "ok"
    assert response.request_id == client.requests[0].request_id
    assert len(client.requests) == 1
    assert client.requests[0].constraints.no_investment_advice
    assert client.requests[0].context.sections[0].title == "AI予測インサイト"


def test_gateway_backed_assistant_passes_chat_history_to_gateway_request():
    client = MockAssistantGatewayClient()
    service = GatewayBackedAssistantService(client)

    response = service.answer(
        AssistantRequest(
            question="続けて注意点を整理して",
            report_context=_sample_report_context(),
            conversation_id="conversation-1",
            message_history=[
                AssistantMessage(role="user", content="AI予測インサイトをどう読む？"),
                AssistantMessage(role="assistant", content="中心予測とレンジを確認します。"),
            ],
            active_context_id="cockpit-forecast",
            referenced_context_ids=["cockpit-forecast"],
            gateway_task_type="forecast_risk_compare",
        )
    )

    assert response.answer.startswith("Gateway mock response")
    assert len(client.requests) == 1
    request = client.requests[0]
    assert request.task == "chat"
    assert request.conversation_id == "conversation-1"
    assert [message.role for message in request.message_history] == ["user", "assistant"]
    assert request.active_context_id == "cockpit-forecast"
    assert request.referenced_context_ids == ["cockpit-forecast"]
    assert request.task_type == "forecast_risk_compare"


def test_gateway_backed_assistant_falls_back_when_client_raises():
    client = MockAssistantGatewayClient(
        error=AssistantGatewayError(
            "gateway unavailable",
            gateway_error_type="connection_refused",
            gateway_url="http://127.0.0.1:8088/api/v1/context-answer",
        )
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
    assert response.response_source == "deterministic_fallback"
    assert response.fallback_reason == "gateway_unavailable"
    assert response.gateway_error_type == "connection_refused"
    assert response.gateway_url == "http://127.0.0.1:8088/api/v1/context-answer"
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
    assert response.response_source == "deterministic_fallback"
    assert response.fallback_reason == "response_validation_failure"
    assert len(client.requests) == 1


def test_gateway_backed_assistant_without_context_uses_minimal_gateway_context():
    client = MockAssistantGatewayClient()
    service = GatewayBackedAssistantService(client)

    response = service.answer(AssistantRequest(question="次に何を確認すればいい？"))

    assert response.answer.startswith("Gateway mock response")
    assert len(client.requests) == 1
    request = client.requests[0]
    assert request.context.title == "SMAI Assistant Minimal Context"
    assert request.context.sections[0].title == "SMAIアシスタント / 最小文脈"
    assert request.context.sections[0].summary["assistant_name"] == "SMAIナビ"
    assert request.context.sections[0].summary["price"] == "false"


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
    assert response.cautions == ["これはMock応答であり、外部LLMや投資助言ではありません。"]
    assert len(client.requests) == 1


def test_http_assistant_gateway_client_posts_context_answer_request():
    observed: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["url"] = str(request.url)
        payload = request.read()
        observed["payload"] = json.loads(payload.decode("utf-8"))
        request_payload = observed["payload"]
        assert isinstance(request_payload, dict)
        return httpx.Response(
            200,
            json={
                "schema_version": "assistant-gateway-response-v1",
                "answer": "Gateway実接続では、画面文脈に沿って確認点を整理します。",
                "materials": ["AI予測インサイト", "中心予測"],
                "cautions": ["投資助言ではありません。"],
                "next_checkpoints": ["根拠とデータ品質を確認します。"],
                "referenced_sections": [
                    {
                        "section_id": "cockpit-1",
                        "title": "AI予測インサイト",
                        "source_kind": "cockpit",
                    }
                ],
                "confidence": "medium",
                "safety_notes": ["スコアや順位は変更していません。"],
                "provider": "ollama",
                "model": "qwen3:8b",
                "profile": "assistant_standard",
                "elapsed_ms": 42,
                "gateway_status": "ok",
                "request_id": request_payload["request_id"],
            },
        )

    client = HttpAssistantGatewayClient(
        base_url="http://gateway.local/",
        context_answer_path="api/v1/context-answer",
        timeout_seconds=3.0,
        model="qwen3:8b",
        execution_mode="quality",
        environment_profile="desktop",
        transport=httpx.MockTransport(handler),
    )
    service = GatewayBackedAssistantService(client)

    response = service.answer(
        AssistantRequest(
            question="AI予測インサイトをどう読む？",
            report_context=_sample_report_context(),
        )
    )

    assert observed["url"] == "http://gateway.local/api/v1/context-answer"
    payload = observed["payload"]
    assert isinstance(payload, dict)
    assert payload["schema_version"] == "assistant-gateway-request-v1"
    assert payload["model"] == "qwen3:8b"
    assert payload["task_type"] == "free_chat"
    assert payload["execution_mode"] == "quality"
    assert payload["environment_profile"] == "desktop"
    assert response.answer.startswith("Gateway実接続")
    assert response.reasons == ["AI予測インサイト", "中心予測"]
    assert response.cautions == ["投資助言ではありません。"]
    assert response.response_source == "llm"
    assert response.model == "qwen3:8b"
    assert response.provider == "ollama"
    assert response.profile == "assistant_standard"
    assert response.gateway_status == "ok"
    assert response.request_id == payload["request_id"]


def test_http_assistant_gateway_client_timeout_raises_timeout_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    client = HttpAssistantGatewayClient(
        base_url="http://gateway.local",
        transport=httpx.MockTransport(handler),
    )

    try:
        client.answer(_sample_gateway_request())
    except TimeoutError as exc:
        assert "timed out" in str(exc)
    else:
        raise AssertionError("Gateway timeouts should become TimeoutError")


def test_gateway_backed_assistant_falls_back_when_http_gateway_times_out():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    client = HttpAssistantGatewayClient(
        base_url="http://gateway.local",
        transport=httpx.MockTransport(handler),
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
    assert response.response_source == "deterministic_fallback"
    assert response.fallback_reason == "gateway_timeout"


def test_http_assistant_gateway_client_raises_on_http_error():
    client = HttpAssistantGatewayClient(
        base_url="http://gateway.local",
        transport=httpx.MockTransport(lambda request: httpx.Response(500, request=request)),
    )

    try:
        client.answer(_sample_gateway_request())
    except AssistantGatewayError as exc:
        assert "HTTP 500" in str(exc)
    else:
        raise AssertionError("HTTP errors should become AssistantGatewayError")


def test_gateway_provider_unreachable_keeps_provider_metadata():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            502,
            json={
                "detail": {
                    "error": "Ollama request failed. Check SMAI_OLLAMA_BASE_URL.",
                    "provider": "ollama",
                    "code": "provider_unreachable",
                    "retryable": True,
                }
            },
            request=request,
        )

    client = HttpAssistantGatewayClient(
        base_url="http://gateway.local",
        transport=httpx.MockTransport(handler),
    )
    service = GatewayBackedAssistantService(client)

    response = service.answer(
        AssistantRequest(
            question="AI予測インサイトをどう読む？",
            report_context=_sample_report_context(),
        )
    )

    assert response.response_source == "deterministic_fallback"
    assert response.fallback_reason == "provider_unavailable"
    assert response.gateway_error_type == "provider_error"
    assert response.gateway_url == "http://gateway.local/api/v1/context-answer"
    assert response.http_status == 502
    assert response.provider_error_type == "provider_unreachable"
    assert "SMAI_OLLAMA_BASE_URL" in str(response.provider_error_message)


def test_http_assistant_gateway_diagnose_reports_missing_model():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://gateway.local/models"
        return httpx.Response(
            200,
            json={
                "provider": "ollama",
                "base_url": "http://localhost:11434",
                "default_profile": "notebook_dev",
                "default_model": "qwen3:1.7b",
                "installed_models": ["qwen3:8b"],
                "configured_model_installed": False,
                "install_hint": "Please run: ollama pull qwen3:1.7b",
            },
            request=request,
        )

    client = HttpAssistantGatewayClient(
        base_url="http://gateway.local",
        model="qwen3:1.7b",
        preferred_profile="notebook_dev",
        transport=httpx.MockTransport(handler),
    )

    diagnostic = client.diagnose()

    assert diagnostic.status == "model_missing"
    assert diagnostic.model == "qwen3:1.7b"
    assert diagnostic.profile == "notebook_dev"
    assert diagnostic.provider_error_type == "model_not_found"
    assert diagnostic.installed_models == ("qwen3:8b",)


def test_http_assistant_gateway_diagnose_preserves_selected_available_model():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "provider": "ollama",
                "base_url": "http://localhost:11434",
                "default_profile": "notebook_dev",
                "default_model": "qwen3:1.7b",
                "installed_models": ["qwen3:1.7b", "qwen3:8b"],
                "configured_model_installed": True,
            },
            request=request,
        )

    client = HttpAssistantGatewayClient(
        base_url="http://gateway.local",
        model="qwen3:8b",
        preferred_profile="desktop_fast",
        transport=httpx.MockTransport(handler),
    )

    diagnostic = client.diagnose()

    assert diagnostic.status == "ready"
    assert diagnostic.model == "qwen3:8b"


def test_assistant_service_factory_uses_template_when_gateway_disabled():
    service = create_assistant_service_from_settings(Settings())

    assert isinstance(service, TemplateAssistantService)


def test_assistant_service_factory_uses_gateway_when_enabled():
    settings = Settings.model_validate(
        {
            "assistant": {
                "gateway": {
                    "enabled": True,
                    "base_url": "http://gateway.local",
                    "context_answer_path": "/api/v1/context-answer",
                    "timeout_seconds": 2.5,
                    "model": "qwen3:8b",
                    "execution_mode": "light",
                    "environment_profile": "notebook",
                }
            }
        }
    )

    client = create_assistant_gateway_client_from_settings(
        settings,
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
    )
    service = create_assistant_service_from_settings(
        settings,
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
    )

    assert isinstance(client, HttpAssistantGatewayClient)
    assert client.context_answer_url == "http://gateway.local/api/v1/context-answer"
    assert client.model == "qwen3:8b"
    assert client.execution_mode == "light"
    assert client.environment_profile == "notebook"
    assert isinstance(service, GatewayBackedAssistantService)
