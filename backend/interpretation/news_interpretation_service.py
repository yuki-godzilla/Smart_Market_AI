from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

import httpx

from backend.assistant import (
    AssistantGatewayError,
    AssistantGatewayTimeoutError,
    HttpAssistantGatewayClient,
)
from backend.core.config import Settings, get_settings
from backend.core.news_interpretation_config import NewsInterpretationConfig

from .news_interpretation_cache import (
    find_news_interpretation_cache_entry,
    news_interpretation_cache_expires_at,
    news_interpretation_cache_key,
    save_news_interpretation_cache_entry,
)
from .news_interpretation_fallback import build_deterministic_news_interpretation
from .news_interpretation_gateway import NewsInterpretationGatewayAdapter
from .news_interpretation_models import (
    NEWS_INTERPRETATION_PROMPT_VERSION,
    NEWS_INTERPRETATION_SCHEMA_VERSION,
    NewsInterpretationCacheMetadata,
    NewsInterpretationContext,
    NewsInterpretationFallbackReason,
    NewsInterpretationResult,
    NewsInterpretationServiceResult,
)
from .news_interpretation_validation import (
    NewsInterpretationValidationError,
    news_interpretation_from_gateway_response,
)

_VALIDATION_REASONS = {
    "malformed_json",
    "validation_error",
    "wrong_context",
    "wrong_material",
    "wrong_sector",
    "wrong_candidate",
    "unknown_evidence",
    "unsupported_number",
    "unsupported_date",
    "policy_violation",
}


class NewsInterpretationService:
    def __init__(
        self,
        gateway_adapter: NewsInterpretationGatewayAdapter,
        *,
        config: NewsInterpretationConfig,
        user_id: str,
        cache_file: Path | None = None,
    ) -> None:
        self.gateway_adapter = gateway_adapter
        self.config = config
        self.user_id = user_id.strip() or "default"
        self.cache_file = None if self.user_id == "default" else cache_file

    def interpret(
        self, context: NewsInterpretationContext, *, now: datetime | None = None
    ) -> NewsInterpretationServiceResult:
        now_utc = _utc(now or datetime.now(UTC))
        key = _key(context, self.config, user_id=self.user_id)
        if self.config.cache_enabled and self.cache_file is not None:
            status, cached, expires = find_news_interpretation_cache_entry(
                cache_key=key, cache_file=self.cache_file, now=now_utc
            )
            if cached is not None and cached.context_hash == context.context_hash:
                return NewsInterpretationServiceResult(
                    result=cached, cache=_metadata("hit", True, key, cached.generated_at, expires)
                )
        else:
            status = "disabled"
        try:
            response = self.gateway_adapter.generate(context)
            result = news_interpretation_from_gateway_response(
                response,
                context=context,
                generated_at=now_utc,
                prompt_version=self.config.prompt_version,
                schema_version=self.config.schema_version,
            )
        except (
            AssistantGatewayError,
            AssistantGatewayTimeoutError,
            NewsInterpretationValidationError,
            TimeoutError,
            ValueError,
        ) as exc:
            reason = _reason(exc)
            fallback = build_deterministic_news_interpretation(
                context,
                status="validation_error" if reason in _VALIDATION_REASONS else "fallback",
                fallback_reason=reason,
                generated_at=now_utc,
                prompt_version=self.config.prompt_version,
                schema_version=self.config.schema_version,
            )
            return NewsInterpretationServiceResult(
                result=fallback,
                cache=_metadata(
                    "invalid" if status == "invalid" else "miss",
                    False,
                    key,
                    fallback.generated_at,
                    None,
                ),
            )
        return self._persist(result, now=now_utc, cache_key=key)

    def _persist(
        self, result: NewsInterpretationResult, *, now: datetime, cache_key: str
    ) -> NewsInterpretationServiceResult:
        expires = news_interpretation_cache_expires_at(
            now=now, ttl_seconds=self.config.cache_ttl_seconds
        )
        cache_enabled = self.config.cache_enabled and self.cache_file is not None
        if cache_enabled and self.cache_file is not None:
            try:
                save_news_interpretation_cache_entry(
                    result, cache_key=cache_key, cache_file=self.cache_file, expires_at=expires
                )
            except OSError:
                result = result.model_copy(
                    update={
                        "warnings": list(
                            dict.fromkeys(
                                [
                                    *result.warnings,
                                    "profile cacheへ保存できませんでした。live結果は現在のsessionだけで表示します。",
                                ]
                            )
                        )
                    }
                )
                return NewsInterpretationServiceResult(
                    result=result,
                    cache=_metadata("invalid", False, cache_key, result.generated_at, None),
                )
        return NewsInterpretationServiceResult(
            result=result,
            cache=_metadata(
                "miss" if cache_enabled else "disabled",
                False,
                cache_key,
                result.generated_at,
                expires if cache_enabled else None,
            ),
        )


def build_news_interpretation_from_settings(
    context: NewsInterpretationContext,
    *,
    user_id: str,
    cache_file: Path | None = None,
    settings: Settings | None = None,
    transport: httpx.BaseTransport | None = None,
    now: datetime | None = None,
) -> NewsInterpretationServiceResult:
    resolved = settings or get_settings()
    config = resolved.llm_interpretation.news
    now_utc = _utc(now or datetime.now(UTC))
    key = _key(context, config, user_id=user_id)
    if not config.enabled or config.execution_mode == "off":
        result = build_deterministic_news_interpretation(
            context,
            status="disabled",
            fallback_reason="disabled",
            generated_at=now_utc,
            prompt_version=config.prompt_version,
            schema_version=config.schema_version,
        )
        return NewsInterpretationServiceResult(
            result=result, cache=_metadata("disabled", False, key, result.generated_at, None)
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
    adapter = NewsInterpretationGatewayAdapter(
        client,
        execution_mode=config.execution_mode,
        environment_profile=config.environment_profile,
        preferred_profile=config.preferred_profile,
    )
    return NewsInterpretationService(
        adapter, config=config, user_id=user_id, cache_file=cache_file
    ).interpret(context, now=now_utc)


def _key(
    context: NewsInterpretationContext, config: NewsInterpretationConfig, *, user_id: str
) -> str:
    return news_interpretation_cache_key(
        user_id=user_id,
        news_context_id=context.news_context_id,
        as_of=context.as_of.isoformat(),
        context_hash=context.context_hash,
        prompt_version=config.prompt_version or NEWS_INTERPRETATION_PROMPT_VERSION,
        schema_version=config.schema_version or NEWS_INTERPRETATION_SCHEMA_VERSION,
        model=config.model,
        gateway_profile=config.preferred_profile,
    )


def _reason(exc: Exception) -> NewsInterpretationFallbackReason:
    if isinstance(exc, NewsInterpretationValidationError):
        return exc.reason if exc.reason in _VALIDATION_REASONS else "validation_error"  # type: ignore[return-value]
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


def _metadata(
    status: str, hit: bool, key: str, generated_at: datetime | None, expires_at: datetime | None
) -> NewsInterpretationCacheMetadata:
    return NewsInterpretationCacheMetadata(
        status=cast(Literal["hit", "miss", "disabled", "invalid"], status),
        cache_hit=hit,
        cache_key=key,
        generated_at=generated_at,
        expires_at=expires_at,
    )


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
