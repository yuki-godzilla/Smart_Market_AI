from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx

from backend.assistant import (
    AssistantGatewayError,
    AssistantGatewayTimeoutError,
    HttpAssistantGatewayClient,
)
from backend.core.config import CockpitInterpretationConfig, Settings, get_settings

from .cache import (
    COCKPIT_INTERPRETATION_CACHE_DIR,
    DEFAULT_COCKPIT_INTERPRETATION_CACHE_TTL_SECONDS,
    cockpit_interpretation_cache_expires_at,
    cockpit_interpretation_cache_key,
    find_cockpit_interpretation_cache_entry,
    save_cockpit_interpretation_cache_entry,
)
from .fallback import build_deterministic_cockpit_interpretation
from .gateway_adapter import CockpitInterpretationGatewayAdapter
from .models import (
    COCKPIT_INTERPRETATION_PROMPT_VERSION,
    COCKPIT_INTERPRETATION_SCHEMA_VERSION,
    CockpitInterpretationCacheMetadata,
    CockpitInterpretationContext,
    CockpitInterpretationFallbackReason,
    CockpitInterpretationServiceResult,
)
from .validation import (
    CockpitInterpretationValidationError,
    cockpit_interpretation_from_gateway_response,
)


class CockpitInterpretationService:
    def __init__(
        self,
        gateway_adapter: CockpitInterpretationGatewayAdapter,
        *,
        config: CockpitInterpretationConfig,
        cache_dir: Path | str = COCKPIT_INTERPRETATION_CACHE_DIR,
        ttl_seconds: int = DEFAULT_COCKPIT_INTERPRETATION_CACHE_TTL_SECONDS,
    ) -> None:
        self.gateway_adapter = gateway_adapter
        self.config = config
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_seconds

    def interpret(
        self,
        context: CockpitInterpretationContext,
        *,
        now: datetime | None = None,
    ) -> CockpitInterpretationServiceResult:
        now_utc = _ensure_utc(now or datetime.now(UTC))
        cache_key = _cache_key(context, self.config)
        if self.config.cache_enabled:
            status, cached, expires_at = find_cockpit_interpretation_cache_entry(
                cache_key=cache_key,
                now=now_utc,
                cache_dir=self.cache_dir,
            )
            if cached is not None:
                return CockpitInterpretationServiceResult(
                    result=cached,
                    cache=_cache_metadata(
                        status="hit",
                        cache_hit=True,
                        cache_key=cache_key,
                        context_hash=context.context_hash,
                        model=cached.model,
                        generated_at=cached.generated_at,
                        expires_at=expires_at,
                    ),
                )
        else:
            status = "miss"

        try:
            response = self.gateway_adapter.generate(context)
            result = cockpit_interpretation_from_gateway_response(
                response,
                context=context,
                generated_at=now_utc,
            )
        except (
            AssistantGatewayError,
            AssistantGatewayTimeoutError,
            CockpitInterpretationValidationError,
            TimeoutError,
            ValueError,
        ) as exc:
            reason = _fallback_reason(exc)
            result = build_deterministic_cockpit_interpretation(
                context,
                status=(
                    "validation_error"
                    if reason in {"validation_error", "policy_violation"}
                    else "fallback"
                ),
                fallback_reason=reason,
                generated_at=now_utc,
            )
            return CockpitInterpretationServiceResult(
                result=result,
                cache=_cache_metadata(
                    status="invalid" if status == "invalid" else "miss",
                    cache_hit=False,
                    cache_key=cache_key,
                    context_hash=context.context_hash,
                    model=result.model,
                    generated_at=result.generated_at,
                    expires_at=None,
                ),
            )

        expires_at = cockpit_interpretation_cache_expires_at(
            now=now_utc,
            ttl_seconds=self.ttl_seconds,
        )
        if self.config.cache_enabled:
            try:
                save_cockpit_interpretation_cache_entry(
                    result,
                    cache_key=cache_key,
                    expires_at=expires_at,
                    cache_dir=self.cache_dir,
                )
            except OSError:
                pass
        return CockpitInterpretationServiceResult(
            result=result,
            cache=_cache_metadata(
                status="miss",
                cache_hit=False,
                cache_key=cache_key,
                context_hash=context.context_hash,
                model=result.model,
                generated_at=result.generated_at,
                expires_at=expires_at,
            ),
        )


def build_cockpit_interpretation_from_settings(
    context: CockpitInterpretationContext,
    *,
    settings: Settings | None = None,
    transport: httpx.BaseTransport | None = None,
    cache_dir: Path | str = COCKPIT_INTERPRETATION_CACHE_DIR,
    now: datetime | None = None,
) -> CockpitInterpretationServiceResult:
    resolved_settings = settings or get_settings()
    config = resolved_settings.llm_interpretation.cockpit
    now_utc = _ensure_utc(now or datetime.now(UTC))
    cache_key = _cache_key(context, config)
    if not config.enabled:
        result = build_deterministic_cockpit_interpretation(
            context,
            status="disabled",
            fallback_reason="disabled",
            generated_at=now_utc,
        )
        return CockpitInterpretationServiceResult(
            result=result,
            cache=_cache_metadata(
                status="disabled",
                cache_hit=False,
                cache_key=cache_key,
                context_hash=context.context_hash,
                model=result.model,
                generated_at=result.generated_at,
                expires_at=None,
            ),
        )

    client = HttpAssistantGatewayClient(
        base_url=config.base_url,
        context_answer_path=config.context_answer_path,
        timeout_seconds=config.timeout_seconds,
        model=config.model,
        execution_mode=config.execution_mode,
        environment_profile=config.environment_profile,
        preferred_profile=config.preferred_profile,
        transport=transport,
    )
    adapter = CockpitInterpretationGatewayAdapter(
        client,
        execution_mode=config.execution_mode,
        environment_profile=config.environment_profile,
        preferred_profile=config.preferred_profile,
    )
    return CockpitInterpretationService(
        adapter,
        config=config,
        cache_dir=cache_dir,
    ).interpret(context, now=now_utc)


def _cache_key(
    context: CockpitInterpretationContext,
    config: CockpitInterpretationConfig,
) -> str:
    return cockpit_interpretation_cache_key(
        symbol=context.symbol,
        as_of=context.as_of.isoformat(),
        context_hash=context.context_hash,
        prompt_version=config.prompt_version or COCKPIT_INTERPRETATION_PROMPT_VERSION,
        schema_version=config.schema_version or COCKPIT_INTERPRETATION_SCHEMA_VERSION,
        model=config.model,
        gateway_profile=config.preferred_profile,
    )


def _fallback_reason(exc: Exception) -> CockpitInterpretationFallbackReason:
    if isinstance(exc, CockpitInterpretationValidationError):
        return _normalize_reason(exc.reason)
    if isinstance(exc, AssistantGatewayTimeoutError) or isinstance(exc, TimeoutError):
        return "gateway_timeout"
    if isinstance(exc, AssistantGatewayError):
        if exc.provider_error_type:
            return "provider_error"
        if exc.gateway_error_type == "gateway_http_error":
            return "gateway_http_error"
        if exc.gateway_error_type == "invalid_gateway_response":
            return "malformed_json"
        return "gateway_unavailable"
    return "validation_error"


def _normalize_reason(reason: str | None) -> CockpitInterpretationFallbackReason:
    normalized = (reason or "").strip().lower()
    allowed = {
        "disabled",
        "gateway_unavailable",
        "gateway_timeout",
        "gateway_http_error",
        "malformed_json",
        "validation_error",
        "wrong_symbol",
        "unknown_evidence",
        "policy_violation",
        "cache_miss",
        "cache_corrupt",
        "provider_error",
    }
    return normalized if normalized in allowed else "validation_error"  # type: ignore[return-value]


def _cache_metadata(
    *,
    status: str,
    cache_hit: bool,
    cache_key: str,
    context_hash: str,
    model: str | None,
    generated_at: datetime | None,
    expires_at: datetime | None,
) -> CockpitInterpretationCacheMetadata:
    return CockpitInterpretationCacheMetadata(
        status=status,  # type: ignore[arg-type]
        cache_hit=cache_hit,
        cache_key=cache_key,
        context_hash=context_hash,
        model=model,
        prompt_version=COCKPIT_INTERPRETATION_PROMPT_VERSION,
        generated_at=generated_at,
        expires_at=expires_at,
    )


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
