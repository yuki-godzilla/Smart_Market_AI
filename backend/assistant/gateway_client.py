from __future__ import annotations

import logging
from collections.abc import Mapping
from time import perf_counter
from typing import Protocol

import httpx
from pydantic import ValidationError

from backend.assistant.gateway_contracts import (
    AssistantGatewayMessage,
    AssistantGatewayReferencedSection,
    AssistantGatewayRequest,
    AssistantGatewayResponse,
    build_assistant_context_bundle,
    build_assistant_gateway_request,
)
from backend.assistant.response_sanitizer import (
    sanitize_presentation_items,
    sanitize_presentation_text,
)
from backend.assistant.service import (
    AssistantCitation,
    AssistantRequest,
    AssistantResponse,
    TemplateAssistantService,
)
from backend.core.config import Settings, get_settings
from backend.reporting import (
    DecisionReportContext,
    build_decision_report_context,
    build_report_section,
)

LOGGER = logging.getLogger(__name__)


def _estimated_context_tokens(request: AssistantGatewayRequest) -> int:
    return max(1, len(request.context.model_dump_json()) // 4)


class AssistantGatewayError(Exception):
    """Base error for optional external assistant gateway calls."""


class AssistantAnswerService(Protocol):
    """Assistant service boundary shared by deterministic and Gateway-backed services."""

    def answer(self, request: AssistantRequest) -> AssistantResponse:
        """Return a user-facing assistant response."""


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


class HttpAssistantGatewayClient:
    """HTTP client for the optional standalone SMAI AI Gateway."""

    def __init__(
        self,
        *,
        base_url: str,
        context_answer_path: str = "/api/v1/context-answer",
        timeout_seconds: float = 10.0,
        model: str | None = None,
        execution_mode: str = "auto",
        environment_profile: str = "notebook",
        preferred_profile: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.context_answer_path = "/" + context_answer_path.strip("/")
        self.timeout_seconds = timeout_seconds
        self.model = model
        self.execution_mode = execution_mode
        self.environment_profile = environment_profile
        self.preferred_profile = preferred_profile
        self.transport = transport

    @property
    def context_answer_url(self) -> str:
        return f"{self.base_url}{self.context_answer_path}"

    def answer(self, request: AssistantGatewayRequest) -> AssistantGatewayResponse:
        payload = request.model_dump(mode="json")
        if self.model:
            payload["model"] = self.model
        payload["execution_mode"] = self.execution_mode
        payload["environment_profile"] = self.environment_profile
        if self.preferred_profile:
            payload["preferred_profile"] = self.preferred_profile

        try:
            with httpx.Client(
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = client.post(self.context_answer_url, json=payload)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise TimeoutError("Assistant Gateway request timed out") from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            raise AssistantGatewayError(f"Assistant Gateway returned HTTP {status_code}") from exc
        except httpx.RequestError as exc:
            raise AssistantGatewayError("Assistant Gateway request failed") from exc

        try:
            response_payload = response.json()
        except ValueError as exc:
            raise AssistantGatewayError("Assistant Gateway returned non-JSON response") from exc
        if not isinstance(response_payload, Mapping):
            raise AssistantGatewayError("Assistant Gateway returned an invalid response shape")
        return AssistantGatewayResponse.model_validate(response_payload)


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

        started = perf_counter()
        report_context = request.report_context or _minimal_assistant_report_context()
        context_bundle = build_assistant_context_bundle(report_context)
        gateway_request = build_assistant_gateway_request(
            question=request.question,
            context=context_bundle,
            task="chat" if request.message_history else "explain",
            task_type=request.gateway_task_type,
            conversation_id=request.conversation_id,
            message_history=[
                AssistantGatewayMessage(role=item.role, content=item.content)
                for item in request.message_history
            ],
            active_context_id=request.active_context_id,
            referenced_context_ids=request.referenced_context_ids,
        )
        context_tokens_estimate = _estimated_context_tokens(gateway_request)
        prompt_chars = len(request.question.strip()) + len(
            gateway_request.context.model_dump_json()
        )
        timeout_sec = getattr(self.gateway_client, "timeout_seconds", None)
        LOGGER.info(
            "[assistant.request.start] request_id=%s intent_task=%s "
            "timeout_sec=%s prompt_chars=%s context_tokens_estimate=%s",
            gateway_request.request_id,
            request.gateway_task_type,
            timeout_sec,
            prompt_chars,
            context_tokens_estimate,
        )
        try:
            raw_response = self.gateway_client.answer(gateway_request)
            gateway_response = _coerce_gateway_response(raw_response)
        except AssistantGatewayError as exc:
            return _fallback_response(
                fallback_response,
                request_id=gateway_request.request_id,
                started=started,
                reason=_gateway_error_reason(exc),
                timeout_sec=timeout_sec,
                context_tokens_estimate=context_tokens_estimate,
                prompt_chars=prompt_chars,
            )
        except TimeoutError:
            return _fallback_response(
                fallback_response,
                request_id=gateway_request.request_id,
                started=started,
                reason="gateway_timeout",
                timeout_sec=timeout_sec,
                context_tokens_estimate=context_tokens_estimate,
                prompt_chars=prompt_chars,
            )
        except (ValidationError, ValueError):
            return _fallback_response(
                fallback_response,
                request_id=gateway_request.request_id,
                started=started,
                reason="response_validation_failure",
                timeout_sec=timeout_sec,
                context_tokens_estimate=context_tokens_estimate,
                prompt_chars=prompt_chars,
            )

        if not gateway_response.answer.strip():
            return _fallback_response(
                fallback_response,
                request_id=gateway_request.request_id,
                started=started,
                reason="empty_llm_answer",
                timeout_sec=timeout_sec,
                context_tokens_estimate=context_tokens_estimate,
                prompt_chars=prompt_chars,
            )

        return _assistant_response_from_gateway_response(
            gateway_response,
            fallback_response=fallback_response,
            request_id=gateway_request.request_id,
        )


def _minimal_assistant_report_context() -> DecisionReportContext:
    section = build_report_section(
        title="SMAIアシスタント / 最小文脈",
        source_kind="manual",
        summary={
            "screen": "SMAIアシスタント",
            "assistant_name": "SMAIナビ",
            "price": "false",
            "forecast": "false",
            "news": "false",
            "research": "false",
            "decision_report": "false",
        },
        notes=[
            "画面固有の銘柄、価格、AI予測、ニュース、根拠資料は渡していません。",
        ],
    )
    return build_decision_report_context(
        title="SMAI Assistant Minimal Context",
        sections=[section],
        tags=["assistant", "minimal"],
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
    request_id: str,
) -> AssistantResponse:
    is_fallback = (
        response.gateway_status != "ok"
        or response.profile == "fallback"
        or response.provider == "deterministic"
    )
    LOGGER.info(
        "[assistant.gateway.result] request_id=%s status=%s response_source=%s "
        "provider=%s model=%s profile=%s elapsed_ms=%s timeout_sec=%s "
        "fallback_reason=%s",
        response.request_id or request_id,
        response.gateway_status,
        "deterministic_fallback" if is_fallback else "llm",
        response.provider,
        response.model,
        response.profile,
        response.elapsed_ms,
        response.timeout_sec,
        response.fallback_reason,
    )
    return AssistantResponse(
        intent=fallback_response.intent,
        answer=sanitize_presentation_text(response.answer) or fallback_response.answer,
        reasons=sanitize_presentation_items(response.materials, limit=8),
        cautions=sanitize_presentation_items(response.cautions, limit=8),
        next_checkpoints=sanitize_presentation_items(response.next_checkpoints, limit=6),
        citations=[_citation_from_gateway_reference(item) for item in response.referenced_sections],
        response_source="deterministic_fallback" if is_fallback else "llm",
        model=response.model,
        provider=response.provider,
        profile=response.profile,
        latency_ms=response.elapsed_ms,
        gateway_status=response.gateway_status,
        fallback_reason=response.fallback_reason,
        request_id=response.request_id or request_id,
        timeout_sec=response.timeout_sec,
        context_tokens_estimate=response.context_tokens_estimate,
        prompt_chars=response.prompt_chars,
        response_chars=response.response_chars,
        tool_execution_ms=response.tool_execution_ms,
        llm_generation_ms=response.llm_generation_ms,
        total_elapsed_ms=response.total_elapsed_ms,
    )


def _fallback_response(
    fallback_response: AssistantResponse,
    *,
    request_id: str,
    started: float,
    reason: str,
    timeout_sec: float | None,
    context_tokens_estimate: int,
    prompt_chars: int,
) -> AssistantResponse:
    latency_ms = int((perf_counter() - started) * 1000)
    LOGGER.warning(
        "[assistant.gateway.result] request_id=%s status=fallback reason=%s "
        "elapsed_ms=%s timeout_sec=%s prompt_chars=%s context_tokens_estimate=%s",
        request_id,
        reason,
        latency_ms,
        timeout_sec,
        prompt_chars,
        context_tokens_estimate,
    )
    return fallback_response.model_copy(
        update={
            "response_source": "deterministic_fallback",
            "profile": "fallback",
            "latency_ms": latency_ms,
            "gateway_status": "error",
            "fallback_reason": reason,
            "request_id": request_id,
            "timeout_sec": timeout_sec,
            "context_tokens_estimate": context_tokens_estimate,
            "prompt_chars": prompt_chars,
            "response_chars": len(fallback_response.answer),
            "tool_execution_ms": 0,
            "llm_generation_ms": 0,
            "total_elapsed_ms": latency_ms,
        }
    )


def _gateway_error_reason(exc: AssistantGatewayError) -> str:
    message = str(exc).lower()
    if "http 404" in message:
        return "model_unavailable"
    if "http" in message:
        return "gateway_http_error"
    return "gateway_unavailable"


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
        profile=request.preferred_profile or "assistant_fast",
        elapsed_ms=0,
        gateway_status="ok",
        request_id=request.request_id,
        timeout_sec=0,
        context_tokens_estimate=_estimated_context_tokens(request),
        prompt_chars=len(request.user_question) + len(request.context.model_dump_json()),
        response_chars=22,
        tool_execution_ms=0,
        llm_generation_ms=0,
        total_elapsed_ms=0,
    )


def create_assistant_gateway_client_from_settings(
    settings: Settings | None = None,
    *,
    transport: httpx.BaseTransport | None = None,
) -> AssistantGatewayClient | None:
    """Create an optional real Gateway client from application settings."""

    resolved_settings = settings or get_settings()
    gateway = resolved_settings.assistant.gateway
    if not gateway.enabled:
        return None
    return HttpAssistantGatewayClient(
        base_url=gateway.base_url,
        context_answer_path=gateway.context_answer_path,
        timeout_seconds=gateway.timeout_seconds,
        model=gateway.model,
        execution_mode=gateway.execution_mode,
        environment_profile=gateway.environment_profile,
        preferred_profile=gateway.preferred_profile,
        transport=transport,
    )


def create_assistant_service_from_settings(
    settings: Settings | None = None,
    *,
    transport: httpx.BaseTransport | None = None,
    fallback_service: TemplateAssistantService | None = None,
) -> AssistantAnswerService:
    """Return the configured assistant service with deterministic fallback."""

    fallback = fallback_service or TemplateAssistantService()
    gateway_client = create_assistant_gateway_client_from_settings(
        settings,
        transport=transport,
    )
    if gateway_client is None:
        return fallback
    return GatewayBackedAssistantService(
        gateway_client,
        fallback_service=fallback,
    )
