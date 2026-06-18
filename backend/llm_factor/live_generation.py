from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import httpx

from backend.core.config import LLMFactorLiveConfig, Settings, get_settings
from backend.llm_factor.cache import (
    DEFAULT_LLM_FACTOR_CACHE_TTL_SECONDS,
    LLM_FACTOR_CACHE_DIR,
    build_llm_factor_cache_entry,
    find_llm_factor_cache_entry,
    llm_factor_cache_expires_at,
    llm_factor_cache_key,
    save_llm_factor_cache_entry,
)
from backend.llm_factor.context_builder import (
    build_llm_factor_generation_request,
    llm_factor_context_hash,
)
from backend.llm_factor.contracts import (
    EvidenceSource,
    LLMFactorCacheMetadata,
    LLMFactorCacheStatus,
    LLMFactorResult,
    LLMFactorServiceResult,
)
from backend.llm_factor.gateway_adapter import (
    HttpLLMFactorGatewayClient,
    LLMFactorGatewayClient,
    LLMFactorGatewayError,
)
from backend.llm_factor.service import CachedLLMFactorService
from backend.llm_factor.validation import (
    LLMFactorLiveValidationError,
    llm_factor_result_from_gateway_response,
)

_LIVE_FALLBACK_WARNING = "LLM Factor live生成に失敗したため、ローカル参考表示に切り替えました。"
_LIVE_DISABLED_WARNING = "LLM Factor live生成は設定で無効のため、ローカル参考表示を使っています。"


class LiveLLMFactorGenerationService:
    """Cache-aware live LLM Factor generation with deterministic fallback."""

    def __init__(
        self,
        gateway_client: LLMFactorGatewayClient,
        *,
        config: LLMFactorLiveConfig,
        fallback_service: CachedLLMFactorService | None = None,
        cache_dir: Path | str = LLM_FACTOR_CACHE_DIR,
        ttl_seconds: int = DEFAULT_LLM_FACTOR_CACHE_TTL_SECONDS,
    ) -> None:
        self.gateway_client = gateway_client
        self.config = config
        self.fallback_service = fallback_service or CachedLLMFactorService(
            cache_dir=cache_dir,
            ttl_seconds=ttl_seconds,
        )
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_seconds

    def build_reference_result(
        self,
        *,
        ticker: str,
        as_of: date,
        evidence_sources: list[EvidenceSource],
        company_name: str | None = None,
        now: datetime | None = None,
    ) -> LLMFactorServiceResult:
        now_utc = _ensure_utc(now or datetime.now(UTC))
        request = build_llm_factor_generation_request(
            ticker=ticker,
            as_of=as_of,
            evidence_sources=evidence_sources,
            company_name=company_name,
            prompt_version=self.config.prompt_version,
            response_schema_version=self.config.response_schema_version,
            max_evidence_items=self.config.max_evidence_items,
            max_text_chars=self.config.max_context_text_chars,
        )
        context_hash = llm_factor_context_hash(request)
        cache_key = llm_factor_cache_key(
            ticker=ticker,
            as_of=as_of,
            source_hash=context_hash,
            model_name=self.config.model or self.config.preferred_profile or "gateway",
            prompt_version=self.config.prompt_version,
            schema_version=self.config.response_schema_version,
            gateway_profile=self.config.preferred_profile,
        )
        if self.config.cache_enabled:
            lookup = find_llm_factor_cache_entry(
                cache_key=cache_key,
                now=now_utc,
                cache_dir=self.cache_dir,
            )
            if lookup.cache_hit and lookup.entry is not None:
                return LLMFactorServiceResult(
                    result=lookup.entry.result,
                    cache=_cache_metadata(
                        status=lookup.status,
                        cache_hit=True,
                        cache_key=cache_key,
                        result=lookup.entry.result,
                        expires_at=lookup.entry.expires_at,
                    ),
                )
        else:
            lookup = None

        try:
            response = self.gateway_client.generate(request)
            result = llm_factor_result_from_gateway_response(
                response,
                request=request,
                context_hash=context_hash,
                fallback_sources=evidence_sources,
            )
        except (LLMFactorGatewayError, LLMFactorLiveValidationError) as exc:
            return self._fallback_result(
                ticker=ticker,
                as_of=as_of,
                evidence_sources=evidence_sources,
                now=now_utc,
                reason=_fallback_reason(exc),
            )

        expires_at = llm_factor_cache_expires_at(now=now_utc, ttl_seconds=self.ttl_seconds)
        if self.config.cache_enabled:
            entry = build_llm_factor_cache_entry(
                result,
                cache_key=cache_key,
                expires_at=expires_at,
            )
            try:
                save_llm_factor_cache_entry(entry, cache_dir=self.cache_dir)
            except OSError:
                pass
        status: LLMFactorCacheStatus = lookup.status if lookup is not None else "miss"
        return LLMFactorServiceResult(
            result=result,
            cache=_cache_metadata(
                status=status,
                cache_hit=False,
                cache_key=cache_key,
                result=result,
                expires_at=expires_at,
            ),
        )

    def _fallback_result(
        self,
        *,
        ticker: str,
        as_of: date,
        evidence_sources: list[EvidenceSource],
        now: datetime,
        reason: str,
    ) -> LLMFactorServiceResult:
        fallback = self.fallback_service.build_reference_result(
            ticker=ticker,
            as_of=as_of,
            evidence_sources=evidence_sources,
            now=now,
        )
        result = fallback.result.model_copy(
            update={
                "provider": "deterministic",
                "gateway_status": "fallback",
                "fallback_reason": reason,
                "warnings": _dedupe(
                    [
                        *fallback.result.warnings,
                        _LIVE_FALLBACK_WARNING,
                        reason,
                    ]
                ),
            }
        )
        return LLMFactorServiceResult(result=result, cache=fallback.cache)


def build_llm_factor_reference_result_from_settings(
    *,
    ticker: str,
    as_of: date,
    evidence_sources: list[EvidenceSource],
    company_name: str | None = None,
    settings: Settings | None = None,
    transport: httpx.BaseTransport | None = None,
    cache_dir: Path | str = LLM_FACTOR_CACHE_DIR,
    now: datetime | None = None,
) -> LLMFactorServiceResult:
    """Build a Cockpit LLM Factor result from settings, preserving deterministic default."""

    resolved_settings = settings or get_settings()
    config = resolved_settings.llm_factor.live
    if not config.enabled:
        fallback = CachedLLMFactorService(cache_dir=cache_dir).build_reference_result(
            ticker=ticker,
            as_of=as_of,
            evidence_sources=evidence_sources,
            now=now,
        )
        result = fallback.result.model_copy(
            update={
                "gateway_status": "fallback",
                "fallback_reason": "live_disabled",
                "warnings": _dedupe([*fallback.result.warnings, _LIVE_DISABLED_WARNING]),
            }
        )
        return LLMFactorServiceResult(result=result, cache=fallback.cache)

    client = HttpLLMFactorGatewayClient(
        base_url=config.base_url,
        endpoint_path=config.endpoint_path,
        timeout_seconds=config.timeout_seconds,
        model=config.model,
        execution_mode=config.execution_mode,
        environment_profile=config.environment_profile,
        preferred_profile=config.preferred_profile,
        transport=transport,
    )
    return LiveLLMFactorGenerationService(
        client,
        config=config,
        cache_dir=cache_dir,
    ).build_reference_result(
        ticker=ticker,
        as_of=as_of,
        evidence_sources=evidence_sources,
        company_name=company_name,
        now=now,
    )


def _fallback_reason(exc: Exception) -> str:
    if isinstance(exc, LLMFactorGatewayError):
        return exc.provider_error_type or exc.gateway_error_type
    return str(exc) or type(exc).__name__


def _cache_metadata(
    *,
    status: LLMFactorCacheStatus,
    cache_hit: bool,
    cache_key: str,
    result: LLMFactorResult,
    expires_at: datetime,
) -> LLMFactorCacheMetadata:
    return LLMFactorCacheMetadata(
        status=status,
        cache_hit=cache_hit,
        cache_key=cache_key,
        source_hash=result.source_hash,
        model_name=result.model_name,
        prompt_version=result.prompt_version,
        generated_at=result.generated_at,
        expires_at=expires_at,
    )


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
