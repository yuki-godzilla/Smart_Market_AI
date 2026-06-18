from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

import httpx
from pydantic import ValidationError

from backend.llm_factor.live_contracts import (
    LLMFactorEnvironmentProfile,
    LLMFactorExecutionMode,
    LLMFactorGenerationRequest,
    LLMFactorGenerationResponse,
    LLMFactorProfileName,
)

DEFAULT_LLM_FACTOR_GATEWAY_PATH = "/api/v1/llm-factor/generate"


class LLMFactorGatewayError(Exception):
    """Base error for optional external LLM Factor Gateway calls."""

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
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.gateway_error_type = gateway_error_type
        self.gateway_url = gateway_url
        self.http_status = http_status
        self.gateway_error_message = gateway_error_message
        self.provider_error_type = provider_error_type
        self.provider_error_message = provider_error_message
        self.retryable = retryable


class LLMFactorGatewayTimeoutError(LLMFactorGatewayError):
    """Raised when the LLM Factor Gateway request times out."""

    def __init__(self, message: str, *, gateway_url: str, timeout_sec: float) -> None:
        super().__init__(
            message,
            gateway_error_type="gateway_timeout",
            gateway_url=gateway_url,
            gateway_error_message=f"timeout_sec={timeout_sec}",
            retryable=True,
        )
        self.timeout_sec = timeout_sec


class LLMFactorGatewayClient(Protocol):
    def generate(self, request: LLMFactorGenerationRequest) -> LLMFactorGenerationResponse:
        """Generate an LLM Factor response for one symbol."""


class HttpLLMFactorGatewayClient:
    """HTTP client for the optional smai-ai-gateway LLM Factor endpoint."""

    def __init__(
        self,
        *,
        base_url: str,
        endpoint_path: str = DEFAULT_LLM_FACTOR_GATEWAY_PATH,
        timeout_seconds: float = 90.0,
        model: str | None = None,
        execution_mode: LLMFactorExecutionMode = "auto",
        environment_profile: LLMFactorEnvironmentProfile = "notebook",
        preferred_profile: LLMFactorProfileName | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.endpoint_path = "/" + endpoint_path.strip("/")
        self.timeout_seconds = timeout_seconds
        self.model = model
        self.execution_mode = execution_mode
        self.environment_profile = environment_profile
        self.preferred_profile = preferred_profile
        self.transport = transport

    @property
    def generate_url(self) -> str:
        return f"{self.base_url}{self.endpoint_path}"

    def generate(self, request: LLMFactorGenerationRequest) -> LLMFactorGenerationResponse:
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
                response = client.post(self.generate_url, json=payload)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise LLMFactorGatewayTimeoutError(
                "LLM Factor Gateway request timed out",
                gateway_url=self.generate_url,
                timeout_sec=self.timeout_seconds,
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise _gateway_error_from_http_response(
                exc.response,
                gateway_url=self.generate_url,
            ) from exc
        except httpx.RequestError as exc:
            raise LLMFactorGatewayError(
                "LLM Factor Gateway request failed",
                gateway_error_type=_request_error_type(exc),
                gateway_url=self.generate_url,
                gateway_error_message=str(exc),
                retryable=True,
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise LLMFactorGatewayError(
                "LLM Factor Gateway returned non-JSON response",
                gateway_error_type="invalid_gateway_response",
                gateway_url=self.generate_url,
            ) from exc
        if not isinstance(payload, Mapping):
            raise LLMFactorGatewayError(
                "LLM Factor Gateway returned an invalid response shape",
                gateway_error_type="invalid_gateway_response",
                gateway_url=self.generate_url,
            )
        try:
            return LLMFactorGenerationResponse.model_validate(payload)
        except ValidationError as exc:
            raise LLMFactorGatewayError(
                "LLM Factor Gateway response failed validation",
                gateway_error_type="invalid_gateway_response",
                gateway_url=self.generate_url,
                gateway_error_message=str(exc),
            ) from exc


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
) -> LLMFactorGatewayError:
    status_code = response.status_code
    detail = _gateway_http_detail(response)
    code = _detail_text(detail, "code")
    error_message = _detail_text(detail, "error") or response.text.strip()
    retryable = _detail_bool(detail, "retryable")
    provider = _detail_text(detail, "provider")
    if code or provider:
        return LLMFactorGatewayError(
            f"LLM Factor Gateway provider error: {code or 'provider_error'}",
            gateway_error_type="provider_error",
            gateway_url=gateway_url,
            http_status=status_code,
            gateway_error_message=f"HTTP {status_code}",
            provider_error_type=code or "provider_error",
            provider_error_message=error_message,
            retryable=retryable,
        )
    message = f"LLM Factor Gateway returned HTTP {status_code}"
    if error_message:
        message = f"{message}: {error_message}"
    return LLMFactorGatewayError(
        message,
        gateway_error_type="gateway_http_error",
        gateway_url=gateway_url,
        http_status=status_code,
        gateway_error_message=error_message or message,
        retryable=retryable,
    )


def _gateway_http_detail(response: httpx.Response) -> Mapping[str, object]:
    try:
        body = response.json()
    except ValueError:
        return {}
    if isinstance(body, Mapping):
        detail = body.get("detail")
        if isinstance(detail, Mapping):
            return detail
        return body
    return {}


def _detail_text(detail: Mapping[str, object], key: str) -> str | None:
    value = detail.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _detail_bool(detail: Mapping[str, object], key: str) -> bool:
    return bool(detail.get(key))
