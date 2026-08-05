from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
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
    LLMFactorEvidenceSelection,
    LLMFactorResult,
    LLMFactorServiceResult,
)
from backend.llm_factor.gateway_adapter import (
    HttpLLMFactorGatewayClient,
    LLMFactorGatewayClient,
    LLMFactorGatewayError,
)
from backend.llm_factor.service import (
    CachedLLMFactorService,
    evidence_confidence_cap,
    select_evidence_sources_for_factor,
)
from backend.llm_factor.validation import (
    LLMFactorLiveValidationError,
    llm_factor_result_from_gateway_response,
)

_LIVE_FALLBACK_WARNING = "LLM Factor live生成に失敗したため、ローカル参考表示に切り替えました。"
_LIVE_DISABLED_WARNING = "LLM Factor live生成は設定で無効のため、ローカル参考表示を使っています。"
_FALLBACK_REASON_MESSAGES = {
    "disabled": "LLM Factor live生成は設定で無効です。",
    "gateway_unavailable": "LLM Gatewayに接続できませんでした。",
    "gateway_timeout": "LLM Gatewayへの接続がタイムアウトしました。",
    "gateway_http_error": "LLM GatewayがHTTPエラーを返しました。",
    "malformed_json": "LLM Gatewayの応答がJSONとして読めませんでした。",
    "validation_error": "LLM応答の検証に失敗しました。",
    "wrong_symbol": "LLM応答の銘柄がリクエストと一致しませんでした。",
    "unknown_evidence": "LLM応答に未提供の出典IDが含まれていました。",
    "stale_source": "LLM応答に古い、または未来日付の出典が含まれていました。",
    "cache_miss": "LLM Factor cacheが見つかりませんでした。",
    "cache_corrupt": "LLM Factor cacheを読み取れませんでした。",
    "provider_error": "LLM provider側でエラーが発生しました。",
    "insufficient_evidence": "対象銘柄に紐づく根拠が不足しています。",
}


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
        selection = select_evidence_sources_for_factor(
            ticker=ticker,
            evidence_sources=evidence_sources,
            company_name=company_name,
        )
        selected_sources = selection.sources
        if not selected_sources:
            return self._fallback_result(
                ticker=ticker,
                as_of=as_of,
                evidence_sources=evidence_sources,
                company_name=company_name,
                now=now_utc,
                reason="insufficient_evidence",
            )
        request = build_llm_factor_generation_request(
            ticker=ticker,
            as_of=as_of,
            evidence_sources=selected_sources,
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
                fallback_sources=selected_sources,
            )
            confidence_cap = evidence_confidence_cap(selected_sources)
            calibration_warnings = _evidence_selection_warnings(selection.summary)
            result = result.model_copy(
                update={
                    "evidence_selection": selection.summary,
                    "llm_confidence_score": min(
                        result.llm_confidence_score,
                        confidence_cap,
                    ),
                    "llm_catalyst_score": min(
                        result.llm_catalyst_score,
                        min(Decimal("85"), confidence_cap + Decimal("10")),
                    ),
                    "warnings": _dedupe([*result.warnings, *calibration_warnings]),
                }
            )
        except (LLMFactorGatewayError, LLMFactorLiveValidationError) as exc:
            return self._fallback_result(
                ticker=ticker,
                as_of=as_of,
                evidence_sources=evidence_sources,
                company_name=company_name,
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
        company_name: str | None,
        now: datetime,
        reason: str,
    ) -> LLMFactorServiceResult:
        fallback = self.fallback_service.build_reference_result(
            ticker=ticker,
            as_of=as_of,
            evidence_sources=evidence_sources,
            company_name=company_name,
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
                        _fallback_reason_message(reason),
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
            company_name=company_name,
            now=now,
        )
        result = fallback.result.model_copy(
            update={
                "gateway_status": "fallback",
                "fallback_reason": "disabled",
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
        return _normalize_fallback_reason(exc.provider_error_type or exc.gateway_error_type)
    if isinstance(exc, LLMFactorLiveValidationError):
        return _normalize_fallback_reason(exc.reason)
    return _normalize_fallback_reason(str(exc) or type(exc).__name__)


def _normalize_fallback_reason(reason: str | None) -> str:
    normalized = (reason or "").strip().lower()
    if normalized in _FALLBACK_REASON_MESSAGES:
        return normalized
    if normalized in {"live_disabled", "execution_mode_off", "gateway_fallback"}:
        return "disabled"
    if normalized in {"connection_refused", "connection_error", "request_error"}:
        return "gateway_unavailable"
    if normalized == "timeout":
        return "gateway_timeout"
    if normalized in {"invalid_gateway_response", "response_validation_failure"}:
        return "validation_error"
    if normalized in {"symbol_mismatch", "wrong_ticker"}:
        return "wrong_symbol"
    if normalized.startswith("unknown_evidence_ids"):
        return "unknown_evidence"
    if normalized.startswith("provider_") or normalized in {"model_not_found", "ollama_error"}:
        return "provider_error"
    if normalized in {"insufficient_evidence", "no_relevant_evidence"}:
        return "insufficient_evidence"
    return "validation_error"


def _fallback_reason_message(reason: str) -> str:
    return _FALLBACK_REASON_MESSAGES.get(reason, _FALLBACK_REASON_MESSAGES["validation_error"])


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


def _evidence_selection_warnings(summary: LLMFactorEvidenceSelection) -> list[str]:
    warnings: list[str] = []
    if summary.unrelated_count:
        warnings.append(
            f"対象銘柄との関連を確認できない根拠 {summary.unrelated_count}件を除外しました。"
        )
    if summary.duplicate_count:
        warnings.append(f"重複と判定した根拠 {summary.duplicate_count}件を除外しました。")
    if summary.retained_count and summary.official_count == 0:
        warnings.append("公式開示を根拠として確認できないため、確信度を控えめにしています。")
    elif summary.retained_count and summary.primary_disclosure_count == 0:
        warnings.append("TDnet・EDINETなどの一次開示が少ないため、補助情報として確認してください。")
    return warnings


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
