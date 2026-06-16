from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from time import perf_counter
from typing import Literal, Protocol

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

GatewayDiagnosticStatus = Literal[
    "unchecked",
    "ready",
    "gateway_unavailable",
    "gateway_timeout",
    "provider_unavailable",
    "model_missing",
    "gateway_error",
]

_PROVIDER_FALLBACK_REASON_MAP = {
    "provider_unreachable": "provider_unavailable",
    "provider_timeout": "provider_timeout",
    "model_not_found": "model_not_found",
}


@dataclass(frozen=True)
class AssistantGatewayDiagnostic:
    """Lightweight Gateway/Ollama readiness result for UI diagnostics."""

    status: GatewayDiagnosticStatus
    message: str
    gateway_url: str
    provider: str | None = None
    model: str | None = None
    profile: str | None = None
    ollama_base_url: str | None = None
    http_status: int | None = None
    gateway_error_type: str | None = None
    gateway_error_message: str | None = None
    provider_error_type: str | None = None
    provider_error_message: str | None = None
    installed_models: tuple[str, ...] = ()


def _estimated_context_tokens(request: AssistantGatewayRequest) -> int:
    return max(1, len(request.context.model_dump_json()) // 4)


class AssistantGatewayError(Exception):
    """Base error for optional external assistant gateway calls."""

    def __init__(
        self,
        message: str,
        *,
        gateway_error_type: str = "gateway_error",
        gateway_url: str | None = None,
        http_status: int | None = None,
        gateway_error_message: str | None = None,
        provider_error_type: str | None = None,
        provider_error_message: str | None = None,
        retryable: bool | None = None,
    ) -> None:
        super().__init__(message)
        self.gateway_error_type = gateway_error_type
        self.gateway_url = gateway_url
        self.http_status = http_status
        self.gateway_error_message = gateway_error_message or message
        self.provider_error_type = provider_error_type
        self.provider_error_message = provider_error_message
        self.retryable = retryable


class AssistantGatewayTimeoutError(TimeoutError):
    """Timeout while reaching the optional external assistant gateway."""

    def __init__(
        self,
        message: str,
        *,
        gateway_url: str | None = None,
        timeout_sec: float | None = None,
    ) -> None:
        super().__init__(message)
        self.gateway_url = gateway_url
        self.gateway_error_type = "gateway_timeout"
        self.gateway_error_message = message
        self.timeout_sec = timeout_sec


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

    @property
    def models_url(self) -> str:
        return f"{self.base_url}/models"

    def diagnose(self, *, timeout_seconds: float = 1.5) -> AssistantGatewayDiagnostic:
        """Check Gateway reachability plus Ollama/model readiness."""

        try:
            with httpx.Client(timeout=timeout_seconds, transport=self.transport) as client:
                response = client.get(self.models_url)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            return AssistantGatewayDiagnostic(
                status="gateway_timeout",
                message="smai-ai-gateway の応答がタイムアウトしました。",
                gateway_url=self.models_url,
                gateway_error_type="gateway_timeout",
                gateway_error_message=str(exc),
                model=self.model,
                profile=self.preferred_profile,
            )
        except httpx.HTTPStatusError as exc:
            gateway_error = _gateway_error_from_http_response(
                exc.response,
                gateway_url=self.models_url,
            )
            return _diagnostic_from_gateway_error(
                gateway_error,
                model=self.model,
                profile=self.preferred_profile,
            )
        except httpx.RequestError as exc:
            error_type = _request_error_type(exc)
            return AssistantGatewayDiagnostic(
                status="gateway_unavailable",
                message="smai-ai-gateway に接続できません。",
                gateway_url=self.models_url,
                gateway_error_type=error_type,
                gateway_error_message=str(exc),
                model=self.model,
                profile=self.preferred_profile,
            )

        try:
            payload = response.json()
        except ValueError:
            return AssistantGatewayDiagnostic(
                status="gateway_error",
                message="smai-ai-gateway の /models がJSON以外を返しました。",
                gateway_url=self.models_url,
                gateway_error_type="invalid_gateway_response",
                model=self.model,
                profile=self.preferred_profile,
            )
        if not isinstance(payload, Mapping):
            return AssistantGatewayDiagnostic(
                status="gateway_error",
                message="smai-ai-gateway の /models 応答形式が不正です。",
                gateway_url=self.models_url,
                gateway_error_type="invalid_gateway_response",
                model=self.model,
                profile=self.preferred_profile,
            )
        installed_models = _installed_models_from_models_payload(payload)
        configured_model = str(payload.get("default_model") or self.model or "").strip() or None
        configured_installed = bool(payload.get("configured_model_installed"))
        provider = str(payload.get("provider") or "").strip() or None
        profile = (
            str(payload.get("default_profile") or self.preferred_profile or "").strip() or None
        )
        ollama_base_url = str(payload.get("base_url") or "").strip() or None
        if not configured_installed:
            return AssistantGatewayDiagnostic(
                status="model_missing",
                message=f"{configured_model or '設定中モデル'} がOllamaに存在しません。",
                gateway_url=self.models_url,
                provider=provider,
                model=configured_model,
                profile=profile,
                ollama_base_url=ollama_base_url,
                provider_error_type="model_not_found",
                provider_error_message=str(payload.get("install_hint") or "").strip() or None,
                installed_models=installed_models,
            )
        return AssistantGatewayDiagnostic(
            status="ready",
            message="smai-ai-gateway と Ollama model は利用可能です。",
            gateway_url=self.models_url,
            provider=provider,
            model=configured_model,
            profile=profile,
            ollama_base_url=ollama_base_url,
            installed_models=installed_models,
        )

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
            raise AssistantGatewayTimeoutError(
                "Assistant Gateway request timed out",
                gateway_url=self.context_answer_url,
                timeout_sec=self.timeout_seconds,
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise _gateway_error_from_http_response(
                exc.response,
                gateway_url=self.context_answer_url,
            ) from exc
        except httpx.RequestError as exc:
            raise AssistantGatewayError(
                "Assistant Gateway request failed",
                gateway_error_type=_request_error_type(exc),
                gateway_url=self.context_answer_url,
                gateway_error_message=str(exc),
            ) from exc

        try:
            response_payload = response.json()
        except ValueError as exc:
            raise AssistantGatewayError(
                "Assistant Gateway returned non-JSON response",
                gateway_error_type="invalid_gateway_response",
                gateway_url=self.context_answer_url,
            ) from exc
        if not isinstance(response_payload, Mapping):
            raise AssistantGatewayError(
                "Assistant Gateway returned an invalid response shape",
                gateway_error_type="invalid_gateway_response",
                gateway_url=self.context_answer_url,
            )
        return AssistantGatewayResponse.model_validate(response_payload)


def _installed_models_from_models_payload(payload: Mapping[str, object]) -> tuple[str, ...]:
    raw_models = payload.get("installed_models")
    if not isinstance(raw_models, list):
        return ()
    return tuple(str(item).strip() for item in raw_models if str(item).strip())


def _request_error_type(exc: httpx.RequestError) -> str:
    message = str(exc).lower()
    if "connection refused" in message or "actively refused" in message:
        return "connection_refused"
    if isinstance(exc, httpx.ConnectError):
        return "connection_error"
    return "request_error"


def _gateway_error_from_http_response(
    response: httpx.Response,
    *,
    gateway_url: str,
) -> AssistantGatewayError:
    status_code = response.status_code
    detail = _gateway_http_detail(response)
    code = _detail_text(detail, "code")
    error_message = _detail_text(detail, "error") or response.text.strip()
    retryable = _detail_bool(detail, "retryable")
    provider = _detail_text(detail, "provider")
    if code in _PROVIDER_FALLBACK_REASON_MAP or provider:
        return AssistantGatewayError(
            f"Assistant Gateway provider error: {code or 'provider_error'}",
            gateway_error_type="provider_error",
            gateway_url=gateway_url,
            http_status=status_code,
            gateway_error_message=f"HTTP {status_code}",
            provider_error_type=code or "provider_error",
            provider_error_message=error_message,
            retryable=retryable,
        )
    message = f"Assistant Gateway returned HTTP {status_code}"
    if error_message:
        message = f"{message}: {error_message}"
    return AssistantGatewayError(
        message,
        gateway_error_type="gateway_http_error",
        gateway_url=gateway_url,
        http_status=status_code,
        gateway_error_message=error_message or message,
        retryable=retryable,
    )


def _gateway_http_detail(response: httpx.Response) -> Mapping[str, object]:
    try:
        payload = response.json()
    except ValueError:
        return {}
    if not isinstance(payload, Mapping):
        return {}
    detail = payload.get("detail")
    if isinstance(detail, Mapping):
        return detail
    if isinstance(detail, str) and detail.strip():
        return {"error": detail.strip()}
    return payload


def _detail_text(detail: Mapping[str, object], key: str) -> str | None:
    value = detail.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _detail_bool(detail: Mapping[str, object], key: str) -> bool | None:
    value = detail.get(key)
    if isinstance(value, bool):
        return value
    return None


def _diagnostic_from_gateway_error(
    error: AssistantGatewayError,
    *,
    model: str | None,
    profile: str | None,
) -> AssistantGatewayDiagnostic:
    if error.provider_error_type == "model_not_found":
        return AssistantGatewayDiagnostic(
            status="model_missing",
            message="設定中のOllama modelが見つかりません。",
            gateway_url=error.gateway_url or "",
            http_status=error.http_status,
            gateway_error_type=error.gateway_error_type,
            gateway_error_message=error.gateway_error_message,
            provider_error_type=error.provider_error_type,
            provider_error_message=error.provider_error_message,
            model=model,
            profile=profile,
        )
    if error.provider_error_type:
        return AssistantGatewayDiagnostic(
            status="provider_unavailable",
            message="smai-ai-gateway は応答しましたが、Ollama provider に接続できません。",
            gateway_url=error.gateway_url or "",
            http_status=error.http_status,
            gateway_error_type=error.gateway_error_type,
            gateway_error_message=error.gateway_error_message,
            provider_error_type=error.provider_error_type,
            provider_error_message=error.provider_error_message,
            model=model,
            profile=profile,
        )
    return AssistantGatewayDiagnostic(
        status="gateway_error",
        message="smai-ai-gateway は応答しましたが、正常応答ではありません。",
        gateway_url=error.gateway_url or "",
        http_status=error.http_status,
        gateway_error_type=error.gateway_error_type,
        gateway_error_message=error.gateway_error_message,
        model=model,
        profile=profile,
    )


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
                gateway_error=exc,
                gateway_url=getattr(self.gateway_client, "context_answer_url", None),
            )
        except TimeoutError as exc:
            return _fallback_response(
                fallback_response,
                request_id=gateway_request.request_id,
                started=started,
                reason="gateway_timeout",
                timeout_sec=timeout_sec,
                context_tokens_estimate=context_tokens_estimate,
                prompt_chars=prompt_chars,
                timeout_error=exc,
                gateway_url=getattr(self.gateway_client, "context_answer_url", None),
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
                gateway_url=getattr(self.gateway_client, "context_answer_url", None),
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
        fallback_reason=_normalize_gateway_fallback_reason(response.fallback_reason),
        provider_error_type=_provider_error_type_from_gateway_response(response),
        provider_error_message=_provider_error_message_from_gateway_response(response),
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
    gateway_error: AssistantGatewayError | None = None,
    timeout_error: TimeoutError | None = None,
    gateway_url: str | None = None,
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
    error_updates = _fallback_error_updates(
        reason=reason,
        gateway_error=gateway_error,
        timeout_error=timeout_error,
        gateway_url=gateway_url,
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
            **error_updates,
        }
    )


def _gateway_error_reason(exc: AssistantGatewayError) -> str:
    if exc.provider_error_type:
        return _PROVIDER_FALLBACK_REASON_MAP.get(
            exc.provider_error_type,
            "provider_unavailable",
        )
    if exc.gateway_error_type == "gateway_http_error":
        return "gateway_http_error"
    return "gateway_unavailable"


def _fallback_error_updates(
    *,
    reason: str,
    gateway_error: AssistantGatewayError | None,
    timeout_error: TimeoutError | None,
    gateway_url: str | None,
) -> dict[str, object]:
    if gateway_error is not None:
        return {
            "gateway_error_type": gateway_error.gateway_error_type,
            "gateway_error_message": gateway_error.gateway_error_message,
            "gateway_url": gateway_error.gateway_url or gateway_url,
            "http_status": gateway_error.http_status,
            "provider_error_type": gateway_error.provider_error_type,
            "provider_error_message": gateway_error.provider_error_message,
        }
    if timeout_error is not None:
        return {
            "gateway_error_type": getattr(timeout_error, "gateway_error_type", reason),
            "gateway_error_message": getattr(
                timeout_error,
                "gateway_error_message",
                str(timeout_error),
            ),
            "gateway_url": getattr(timeout_error, "gateway_url", gateway_url),
        }
    if gateway_url:
        return {
            "gateway_error_type": reason,
            "gateway_url": gateway_url,
        }
    return {}


def _normalize_gateway_fallback_reason(reason: str | None) -> str | None:
    if reason is None:
        return None
    return _PROVIDER_FALLBACK_REASON_MAP.get(reason, reason)


def _provider_error_type_from_gateway_response(
    response: AssistantGatewayResponse,
) -> str | None:
    reason = response.fallback_reason
    if response.gateway_status == "ok" or reason is None:
        return None
    return reason if reason in _PROVIDER_FALLBACK_REASON_MAP else None


def _provider_error_message_from_gateway_response(
    response: AssistantGatewayResponse,
) -> str | None:
    if _provider_error_type_from_gateway_response(response) is None:
        return None
    if response.safety_notes:
        return response.safety_notes[-1]
    return response.fallback_reason


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
