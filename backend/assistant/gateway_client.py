from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from pydantic import ValidationError

from backend.assistant.gateway_contracts import (
    AssistantGatewayReferencedSection,
    AssistantGatewayRequest,
    AssistantGatewayResponse,
    build_assistant_context_bundle,
    build_assistant_gateway_request,
)
from backend.assistant.service import (
    AssistantCitation,
    AssistantRequest,
    AssistantResponse,
    TemplateAssistantService,
)


class AssistantGatewayError(Exception):
    """Base error for optional external assistant gateway calls."""


class AssistantGatewayClient(Protocol):
    """Provider-neutral client boundary for the future external LLM Gateway."""

    def answer(
        self,
        request: AssistantGatewayRequest,
    ) -> AssistantGatewayResponse | Mapping[str, object]:
        """Return a Gateway response or a raw payload that can be schema-validated."""


class MockAssistantGatewayClient:
    """Network-free mock used by tests and local wiring before a real Gateway exists."""

    def __init__(
        self,
        *,
        response: AssistantGatewayResponse | Mapping[str, object] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.requests: list[AssistantGatewayRequest] = []

    def answer(
        self,
        request: AssistantGatewayRequest,
    ) -> AssistantGatewayResponse | Mapping[str, object]:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        if self.response is not None:
            return self.response
        return _default_mock_gateway_response(request)


class GatewayBackedAssistantService:
    """Assistant service that prefers Gateway output and falls back deterministically."""

    def __init__(
        self,
        gateway_client: AssistantGatewayClient,
        *,
        fallback_service: TemplateAssistantService | None = None,
    ) -> None:
        self.gateway_client = gateway_client
        self.fallback_service = fallback_service or TemplateAssistantService()

    def answer(self, request: AssistantRequest) -> AssistantResponse:
        fallback_response = self.fallback_service.answer(request)
        if request.report_context is None:
            return fallback_response

        context_bundle = build_assistant_context_bundle(request.report_context)
        gateway_request = build_assistant_gateway_request(
            question=request.question,
            context=context_bundle,
        )
        try:
            raw_response = self.gateway_client.answer(gateway_request)
            gateway_response = _coerce_gateway_response(raw_response)
        except (AssistantGatewayError, TimeoutError, ValidationError, ValueError):
            return fallback_response

        if not gateway_response.answer.strip():
            return fallback_response

        return _assistant_response_from_gateway_response(
            gateway_response,
            fallback_response=fallback_response,
        )


def _coerce_gateway_response(
    response: AssistantGatewayResponse | Mapping[str, object],
) -> AssistantGatewayResponse:
    if isinstance(response, AssistantGatewayResponse):
        return response
    return AssistantGatewayResponse.model_validate(response)


def _assistant_response_from_gateway_response(
    response: AssistantGatewayResponse,
    *,
    fallback_response: AssistantResponse,
) -> AssistantResponse:
    return AssistantResponse(
        intent=fallback_response.intent,
        answer=response.answer.strip(),
        reasons=response.materials,
        cautions=[*response.cautions, *response.safety_notes],
        next_checkpoints=response.next_checkpoints,
        citations=[_citation_from_gateway_reference(item) for item in response.referenced_sections],
    )


def _citation_from_gateway_reference(
    reference: AssistantGatewayReferencedSection,
) -> AssistantCitation:
    return AssistantCitation(
        section_title=reference.title,
        source_kind=reference.source_kind,
    )


def _default_mock_gateway_response(request: AssistantGatewayRequest) -> AssistantGatewayResponse:
    first_section = request.context.sections[0]
    return AssistantGatewayResponse(
        answer=("Gateway mock response: " "見る材料、注意点、次に確認することを整理します。"),
        materials=[first_section.title, *first_section.included_fields[:3]],
        cautions=[
            "これはMock応答であり、外部LLMや投資助言ではありません。",
            *request.context.privacy_notes[:1],
        ],
        next_checkpoints=[
            "Gateway接続前はdeterministic fallbackと同じ安全境界で確認します。",
        ],
        referenced_sections=[
            AssistantGatewayReferencedSection(
                section_id=first_section.section_id,
                title=first_section.title,
                source_kind=first_section.source_kind,
            )
        ],
        confidence="low",
        safety_notes=[
            "スコア、ランキング、予測値は変更していません。",
        ],
        provider="mock",
        model="mock-assistant-gateway",
        elapsed_ms=0,
    )
