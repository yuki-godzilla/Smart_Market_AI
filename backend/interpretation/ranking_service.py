from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx

from backend.assistant import (
    AssistantGatewayError,
    AssistantGatewayTimeoutError,
    HttpAssistantGatewayClient,
)
from backend.core.config import RankingInterpretationConfig, Settings, get_settings

from .ranking_cache import (
    RANKING_INTERPRETATION_CACHE_DIR,
    find_ranking_interpretation_cache_entry,
    ranking_interpretation_cache_expires_at,
    ranking_interpretation_cache_key,
    save_ranking_interpretation_cache_entry,
)
from .ranking_fallback import build_deterministic_ranking_interpretation
from .ranking_gateway import RankingInterpretationGatewayAdapter
from .ranking_models import (
    RANKING_INTERPRETATION_PROMPT_VERSION,
    RANKING_INTERPRETATION_SCHEMA_VERSION,
    RankingInterpretationCacheMetadata,
    RankingInterpretationContext,
    RankingInterpretationFallbackReason,
    RankingInterpretationServiceResult,
)
from .ranking_validation import (
    RankingInterpretationValidationError,
    ranking_interpretation_from_gateway_response,
)


class RankingInterpretationService:
    def __init__(
        self,
        gateway_adapter: RankingInterpretationGatewayAdapter,
        *,
        config: RankingInterpretationConfig,
        cache_dir: Path | str = RANKING_INTERPRETATION_CACHE_DIR,
    ) -> None:
        self.gateway_adapter = gateway_adapter
        self.config = config
        self.cache_dir = cache_dir

    def interpret(
        self,
        context: RankingInterpretationContext,
        *,
        now: datetime | None = None,
    ) -> RankingInterpretationServiceResult:
        now_utc = _ensure_utc(now or datetime.now(UTC))
        cache_key = _cache_key(context, self.config)
        cache_status, cached_result = self._cached_result(
            context,
            now=now_utc,
            cache_key=cache_key,
        )
        if cached_result is not None:
            return cached_result

        try:
            response = self.gateway_adapter.generate(context)
            result = ranking_interpretation_from_gateway_response(
                response,
                context=context,
                generated_at=now_utc,
                prompt_version=self.config.prompt_version,
                schema_version=self.config.schema_version,
            )
        except (
            AssistantGatewayError,
            AssistantGatewayTimeoutError,
            RankingInterpretationValidationError,
            TimeoutError,
            ValueError,
        ) as exc:
            reason = _fallback_reason(exc)
            result = build_deterministic_ranking_interpretation(
                context,
                status="validation_error" if reason in _VALIDATION_REASONS else "fallback",
                fallback_reason=reason,
                generated_at=now_utc,
                prompt_version=self.config.prompt_version,
                schema_version=self.config.schema_version,
            )
            return RankingInterpretationServiceResult(
                result=result,
                cache=_cache_metadata(
                    status="invalid" if cache_status == "invalid" else "miss",
                    cache_hit=False,
                    cache_key=cache_key,
                    generated_at=result.generated_at,
                    expires_at=None,
                ),
            )

        expires_at = ranking_interpretation_cache_expires_at(
            now=now_utc,
            ttl_seconds=self.config.cache_ttl_seconds,
        )
        if self.config.cache_enabled:
            try:
                save_ranking_interpretation_cache_entry(
                    result,
                    cache_key=cache_key,
                    expires_at=expires_at,
                    cache_dir=self.cache_dir,
                )
            except OSError:
                pass
        return RankingInterpretationServiceResult(
            result=result,
            cache=_cache_metadata(
                status="miss" if self.config.cache_enabled else "disabled",
                cache_hit=False,
                cache_key=cache_key,
                generated_at=result.generated_at,
                expires_at=expires_at if self.config.cache_enabled else None,
            ),
        )

    def _cached_result(
        self,
        context: RankingInterpretationContext,
        *,
        now: datetime,
        cache_key: str,
    ) -> tuple[str, RankingInterpretationServiceResult | None]:
        if not self.config.cache_enabled:
            return "disabled", None
        status, cached, expires_at = find_ranking_interpretation_cache_entry(
            cache_key=cache_key,
            now=now,
            cache_dir=self.cache_dir,
        )
        if cached is None or cached.context_hash != context.context_hash:
            return status, None
        return status, RankingInterpretationServiceResult(
            result=cached,
            cache=_cache_metadata(
                status="hit",
                cache_hit=True,
                cache_key=cache_key,
                generated_at=cached.generated_at,
                expires_at=expires_at,
            ),
        )


def build_ranking_interpretation_from_settings(
    context: RankingInterpretationContext,
    *,
    settings: Settings | None = None,
    transport: httpx.BaseTransport | None = None,
    cache_dir: Path | str = RANKING_INTERPRETATION_CACHE_DIR,
    now: datetime | None = None,
) -> RankingInterpretationServiceResult:
    resolved_settings = settings or get_settings()
    config = resolved_settings.llm_interpretation.ranking
    now_utc = _ensure_utc(now or datetime.now(UTC))
    cache_key = _cache_key(context, config)
    if not config.enabled or config.execution_mode == "off":
        result = build_deterministic_ranking_interpretation(
            context,
            status="disabled",
            fallback_reason="disabled",
            generated_at=now_utc,
            prompt_version=config.prompt_version,
            schema_version=config.schema_version,
        )
        return RankingInterpretationServiceResult(
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
    adapter = RankingInterpretationGatewayAdapter(
        client,
        execution_mode=config.execution_mode,
        environment_profile=config.environment_profile,
        preferred_profile=config.preferred_profile,
    )
    return RankingInterpretationService(adapter, config=config, cache_dir=cache_dir).interpret(
        context,
        now=now_utc,
    )


_VALIDATION_REASONS = {
    "malformed_json",
    "validation_error",
    "wrong_context",
    "wrong_candidate",
    "duplicate_candidate",
    "unknown_evidence",
    "unsupported_number",
    "unsupported_date",
    "policy_violation",
}


def _cache_key(
    context: RankingInterpretationContext,
    config: RankingInterpretationConfig,
) -> str:
    return ranking_interpretation_cache_key(
        ranking_context_id=context.ranking_context_id,
        as_of=context.as_of.isoformat(),
        context_hash=context.context_hash,
        prompt_version=config.prompt_version or RANKING_INTERPRETATION_PROMPT_VERSION,
        schema_version=config.schema_version or RANKING_INTERPRETATION_SCHEMA_VERSION,
        model=config.model,
        gateway_profile=config.preferred_profile,
    )


def _fallback_reason(exc: Exception) -> RankingInterpretationFallbackReason:
    if isinstance(exc, RankingInterpretationValidationError):
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


def _normalize_reason(reason: str | None) -> RankingInterpretationFallbackReason:
    normalized = (reason or "").strip().lower()
    aliases = {
        "provider_timeout": "gateway_timeout",
        "response_validation_failure": "malformed_json",
    }
    normalized = aliases.get(normalized, normalized)
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
) -> RankingInterpretationCacheMetadata:
    return RankingInterpretationCacheMetadata(
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
