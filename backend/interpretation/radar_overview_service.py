from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx

from backend.assistant import (
    AssistantGatewayError,
    AssistantGatewayTimeoutError,
    HttpAssistantGatewayClient,
)
from backend.core.config import RadarOverviewInterpretationConfig, Settings, get_settings

from .radar_overview_cache import (
    find_radar_overview_interpretation_cache_entry,
    radar_overview_interpretation_cache_expires_at,
    radar_overview_interpretation_cache_key,
    save_radar_overview_interpretation_cache_entry,
)
from .radar_overview_fallback import build_deterministic_radar_overview_interpretation
from .radar_overview_gateway import RadarOverviewInterpretationGatewayAdapter
from .radar_overview_models import (
    RADAR_OVERVIEW_INTERPRETATION_PROMPT_VERSION,
    RADAR_OVERVIEW_INTERPRETATION_SCHEMA_VERSION,
    RadarOverviewInterpretationCacheMetadata,
    RadarOverviewInterpretationContext,
    RadarOverviewInterpretationFallbackReason,
    RadarOverviewInterpretationResult,
    RadarOverviewInterpretationServiceResult,
)
from .radar_overview_validation import (
    RadarOverviewInterpretationValidationError,
    radar_overview_interpretation_from_gateway_response,
)


class RadarOverviewInterpretationService:
    def __init__(
        self,
        gateway_adapter: RadarOverviewInterpretationGatewayAdapter,
        *,
        config: RadarOverviewInterpretationConfig,
        user_id: str,
        cache_file: Path | None = None,
    ) -> None:
        self.gateway_adapter = gateway_adapter
        self.config = config
        self.user_id = user_id.strip() or "default"
        self.cache_file = None if self.user_id == "default" else cache_file

    def interpret(
        self,
        context: RadarOverviewInterpretationContext,
        *,
        now: datetime | None = None,
    ) -> RadarOverviewInterpretationServiceResult:
        now_utc = _ensure_utc(now or datetime.now(UTC))
        cache_key = _cache_key(context, self.config, user_id=self.user_id)
        cache_status, cached_result = self._cached_result(
            context,
            now=now_utc,
            cache_key=cache_key,
        )
        if cached_result is not None:
            return cached_result
        try:
            result = self._generate_live_result(context, now=now_utc)
        except (
            AssistantGatewayError,
            AssistantGatewayTimeoutError,
            RadarOverviewInterpretationValidationError,
            TimeoutError,
            ValueError,
        ) as exc:
            return self._fallback_result(
                context,
                error=exc,
                now=now_utc,
                cache_key=cache_key,
                cache_status=cache_status,
            )
        return self._persist_live_result(
            result,
            now=now_utc,
            cache_key=cache_key,
            cache_status=cache_status,
        )

    def _generate_live_result(
        self,
        context: RadarOverviewInterpretationContext,
        *,
        now: datetime,
    ) -> RadarOverviewInterpretationResult:
        response = self.gateway_adapter.generate(context)
        return radar_overview_interpretation_from_gateway_response(
            response,
            context=context,
            generated_at=now,
            prompt_version=self.config.prompt_version,
            schema_version=self.config.schema_version,
        )

    def _fallback_result(
        self,
        context: RadarOverviewInterpretationContext,
        *,
        error: Exception,
        now: datetime,
        cache_key: str,
        cache_status: str,
    ) -> RadarOverviewInterpretationServiceResult:
        reason = _fallback_reason(error)
        result = build_deterministic_radar_overview_interpretation(
            context,
            status="validation_error" if reason in _VALIDATION_REASONS else "fallback",
            fallback_reason=reason,
            generated_at=now,
            prompt_version=self.config.prompt_version,
            schema_version=self.config.schema_version,
        )
        return RadarOverviewInterpretationServiceResult(
            result=result,
            cache=_cache_metadata(
                status="invalid" if cache_status == "invalid" else "miss",
                cache_hit=False,
                cache_key=cache_key,
                generated_at=result.generated_at,
                expires_at=None,
            ),
        )

    def _persist_live_result(
        self,
        result: RadarOverviewInterpretationResult,
        *,
        now: datetime,
        cache_key: str,
        cache_status: str,
    ) -> RadarOverviewInterpretationServiceResult:
        expires_at = radar_overview_interpretation_cache_expires_at(
            now=now,
            ttl_seconds=self.config.cache_ttl_seconds,
        )
        cache_enabled = self.config.cache_enabled and self.cache_file is not None
        cache_write_failed = False
        if cache_enabled and self.cache_file is not None:
            try:
                save_radar_overview_interpretation_cache_entry(
                    result,
                    cache_key=cache_key,
                    cache_file=self.cache_file,
                    expires_at=expires_at,
                )
            except OSError:
                cache_write_failed = True
                result = result.model_copy(
                    update={
                        "warnings": _dedupe(
                            [
                                *result.warnings,
                                "profile cacheへ保存できませんでした。live結果は現在のsessionだけで表示します。",
                            ]
                        )
                    }
                )
        if cache_status == "invalid" and not cache_write_failed:
            result = result.model_copy(
                update={
                    "warnings": _dedupe(
                        [
                            *result.warnings,
                            "既存のprofile cacheを読み込めなかったため、live結果を再生成しました。",
                        ]
                    )
                }
            )
        return RadarOverviewInterpretationServiceResult(
            result=result,
            cache=_cache_metadata(
                status=(
                    "invalid"
                    if cache_write_failed or cache_status == "invalid"
                    else ("miss" if cache_enabled else "disabled")
                ),
                cache_hit=False,
                cache_key=cache_key,
                generated_at=result.generated_at,
                expires_at=expires_at if cache_enabled and not cache_write_failed else None,
            ),
        )

    def _cached_result(
        self,
        context: RadarOverviewInterpretationContext,
        *,
        now: datetime,
        cache_key: str,
    ) -> tuple[str, RadarOverviewInterpretationServiceResult | None]:
        if not self.config.cache_enabled or self.cache_file is None:
            return "disabled", None
        status, cached, expires_at = find_radar_overview_interpretation_cache_entry(
            cache_key=cache_key,
            cache_file=self.cache_file,
            now=now,
        )
        if cached is None or cached.context_hash != context.context_hash:
            return status, None
        return status, RadarOverviewInterpretationServiceResult(
            result=cached,
            cache=_cache_metadata(
                status="hit",
                cache_hit=True,
                cache_key=cache_key,
                generated_at=cached.generated_at,
                expires_at=expires_at,
            ),
        )


def build_radar_overview_interpretation_from_settings(
    context: RadarOverviewInterpretationContext,
    *,
    user_id: str,
    cache_file: Path | None = None,
    settings: Settings | None = None,
    transport: httpx.BaseTransport | None = None,
    now: datetime | None = None,
) -> RadarOverviewInterpretationServiceResult:
    resolved_settings = settings or get_settings()
    config = resolved_settings.llm_interpretation.radar_overview
    now_utc = _ensure_utc(now or datetime.now(UTC))
    cache_key = _cache_key(context, config, user_id=user_id)
    if not config.enabled or config.execution_mode == "off":
        result = build_deterministic_radar_overview_interpretation(
            context,
            status="disabled",
            fallback_reason="disabled",
            generated_at=now_utc,
            prompt_version=config.prompt_version,
            schema_version=config.schema_version,
        )
        return RadarOverviewInterpretationServiceResult(
            result=result,
            cache=_cache_metadata(
                status="disabled",
                cache_hit=False,
                cache_key=cache_key,
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
    adapter = RadarOverviewInterpretationGatewayAdapter(
        client,
        execution_mode=config.execution_mode,
        environment_profile=config.environment_profile,
        preferred_profile=config.preferred_profile,
    )
    return RadarOverviewInterpretationService(
        adapter,
        config=config,
        user_id=user_id,
        cache_file=cache_file,
    ).interpret(context, now=now_utc)


_VALIDATION_REASONS = {
    "malformed_json",
    "validation_error",
    "wrong_context",
    "wrong_candidate",
    "wrong_theme",
    "wrong_sector",
    "duplicate_candidate",
    "unknown_evidence",
    "unsupported_number",
    "unsupported_date",
    "policy_violation",
}


def _cache_key(
    context: RadarOverviewInterpretationContext,
    config: RadarOverviewInterpretationConfig,
    *,
    user_id: str,
) -> str:
    return radar_overview_interpretation_cache_key(
        user_id=user_id,
        radar_context_id=context.radar_context_id,
        as_of=context.as_of.isoformat(),
        context_hash=context.context_hash,
        prompt_version=config.prompt_version or RADAR_OVERVIEW_INTERPRETATION_PROMPT_VERSION,
        schema_version=config.schema_version or RADAR_OVERVIEW_INTERPRETATION_SCHEMA_VERSION,
        model=config.model,
        gateway_profile=config.preferred_profile,
    )


def _fallback_reason(exc: Exception) -> RadarOverviewInterpretationFallbackReason:
    if isinstance(exc, RadarOverviewInterpretationValidationError):
        return _normalize_reason(exc.reason)
    if isinstance(exc, (AssistantGatewayTimeoutError, TimeoutError)):
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


def _normalize_reason(reason: str | None) -> RadarOverviewInterpretationFallbackReason:
    normalized = (reason or "").strip().lower()
    normalized = {
        "provider_timeout": "gateway_timeout",
        "response_validation_failure": "malformed_json",
    }.get(normalized, normalized)
    allowed = {
        *_VALIDATION_REASONS,
        "disabled",
        "gateway_unavailable",
        "gateway_timeout",
        "gateway_http_error",
        "cache_corrupt",
        "provider_error",
    }
    return normalized if normalized in allowed else "validation_error"  # type: ignore[return-value]


def _cache_metadata(
    *,
    status: str,
    cache_hit: bool,
    cache_key: str,
    generated_at: datetime | None,
    expires_at: datetime | None,
) -> RadarOverviewInterpretationCacheMetadata:
    return RadarOverviewInterpretationCacheMetadata(
        status=status,  # type: ignore[arg-type]
        cache_hit=cache_hit,
        cache_key=cache_key,
        generated_at=generated_at,
        expires_at=expires_at,
    )


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(item.strip() for item in values if item.strip()))
