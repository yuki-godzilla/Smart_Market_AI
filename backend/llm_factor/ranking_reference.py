from __future__ import annotations

from datetime import UTC, date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Literal, Mapping

from pydantic import Field

from backend.core.data_contracts import StrictBaseModel
from backend.llm_factor.cache import (
    LLM_FACTOR_CACHE_DIR,
    find_llm_factor_cache_entry,
    llm_factor_cache_key,
)
from backend.llm_factor.contracts import (
    LLM_FACTOR_FAKE_MODEL_NAME,
    LLM_FACTOR_PROMPT_VERSION,
    EvidenceSource,
    LLMFactorResult,
)
from backend.llm_factor.service import (
    FakeLLMFactorService,
    normalized_evidence_sources_for_factor,
    source_hash_for_evidence,
)

DEFAULT_LLM_FACTOR_RANKING_REFERENCE_MAX_CANDIDATES = 100

LLMFactorRankingReferenceSourceType = Literal["cache", "deterministic_fake", "unavailable"]


class LLMFactorRankingReference(StrictBaseModel):
    """Reference-only LLM material scores attached after ranking is fixed."""

    bullish_score: Decimal | None = Field(default=None, ge=0, le=100)
    bearish_score: Decimal | None = Field(default=None, ge=0, le=100)
    confidence_score: Decimal | None = Field(default=None, ge=0, le=100)
    freshness_score: Decimal | None = Field(default=None, ge=0, le=100)
    evidence_quality_score: Decimal | None = Field(default=None, ge=0, le=100)
    source_count: int | None = Field(default=None, ge=0)
    result_id: str | None = Field(default=None, min_length=1)
    source_type: LLMFactorRankingReferenceSourceType
    is_reference_only: bool = True
    warning: str | None = Field(default=None, min_length=1)


def build_llm_factor_references_for_ranking_items(
    ranking_items: Iterable[Mapping[str, object]],
    *,
    as_of_date: date,
    cache_dir: Path | str = LLM_FACTOR_CACHE_DIR,
    fake_service: FakeLLMFactorService | None = None,
    max_candidates: int | None = DEFAULT_LLM_FACTOR_RANKING_REFERENCE_MAX_CANDIDATES,
    now: datetime | None = None,
) -> dict[str, LLMFactorRankingReference]:
    """Build reference-only LLM factor rows for already displayed ranking items.

    The function intentionally receives the already selected/displayed items, keeps
    their existing score/rank order out of scope, and never calls external LLM/news
    providers. Cache hits are reused; cache misses fall back to deterministic fake
    scores without writing a new ranking cache entry.
    """

    service = fake_service or FakeLLMFactorService()
    limit = max_candidates if max_candidates is not None else None
    references: dict[str, LLMFactorRankingReference] = {}
    for index, item in enumerate(ranking_items):
        if limit is not None and index >= max(0, limit):
            break
        key = llm_factor_ranking_candidate_key(item)
        ticker = _ranking_item_symbol(item)
        if not key or not ticker:
            continue
        references[key] = build_llm_factor_reference_for_ranking_item(
            ticker=ticker,
            as_of_date=as_of_date,
            cache_dir=cache_dir,
            fake_service=service,
            now=now,
        )
    return references


def attach_llm_factor_references_to_ranking_items(
    ranking_items: Iterable[Mapping[str, object]],
    *,
    as_of_date: date,
    cache_dir: Path | str = LLM_FACTOR_CACHE_DIR,
    fake_service: FakeLLMFactorService | None = None,
    max_candidates: int | None = DEFAULT_LLM_FACTOR_RANKING_REFERENCE_MAX_CANDIDATES,
    now: datetime | None = None,
) -> list[dict[str, object]]:
    """Return ranking items with optional llm_factor_reference, preserving order."""

    items = [dict(item) for item in ranking_items]
    references = build_llm_factor_references_for_ranking_items(
        items,
        as_of_date=as_of_date,
        cache_dir=cache_dir,
        fake_service=fake_service,
        max_candidates=max_candidates,
        now=now,
    )
    enriched: list[dict[str, object]] = []
    for item in items:
        key = llm_factor_ranking_candidate_key(item)
        if key in references:
            enriched.append({**item, "llm_factor_reference": references[key]})
        else:
            enriched.append(item)
    return enriched


def build_llm_factor_reference_for_ranking_item(
    *,
    ticker: str,
    as_of_date: date,
    cache_dir: Path | str = LLM_FACTOR_CACHE_DIR,
    fake_service: FakeLLMFactorService | None = None,
    evidence_sources: Iterable[EvidenceSource] = (),
    now: datetime | None = None,
) -> LLMFactorRankingReference:
    """Build one reference row from cache or deterministic fake fallback."""

    normalized_ticker = ticker.strip().upper()
    if not normalized_ticker:
        return _unavailable_reference("銘柄コードが空のため、LLM材料参考値を表示できません。")

    service = fake_service or FakeLLMFactorService()
    sources = list(evidence_sources)
    cache_sources = normalized_evidence_sources_for_factor(
        ticker=normalized_ticker,
        as_of=as_of_date,
        evidence_sources=sources,
    )
    source_hash = source_hash_for_evidence(cache_sources)
    cache_key = llm_factor_cache_key(
        ticker=normalized_ticker,
        as_of=as_of_date,
        source_hash=source_hash,
        model_name=LLM_FACTOR_FAKE_MODEL_NAME,
        prompt_version=LLM_FACTOR_PROMPT_VERSION,
    )

    try:
        lookup = find_llm_factor_cache_entry(
            cache_key=cache_key,
            now=now,
            cache_dir=cache_dir,
        )
        if lookup.cache_hit and lookup.entry is not None:
            return _reference_from_result(lookup.entry.result, source_type="cache")

        result = service.build_reference_result(
            ticker=normalized_ticker,
            as_of=as_of_date,
            evidence_sources=sources,
            generated_at=_deterministic_ranking_generated_at(as_of_date),
        )
        warning = "cache miss のため deterministic fake service による参考値です。"
        if lookup.status in {"expired", "invalid"}:
            warning = f"cache {lookup.status} のため deterministic fake service による参考値です。"
        return _reference_from_result(
            result,
            source_type="deterministic_fake",
            warning=warning,
        )
    except Exception as exc:
        return _unavailable_reference(f"LLM材料参考値を取得できませんでした: {type(exc).__name__}")


def llm_factor_ranking_candidate_key(item: Mapping[str, object]) -> str:
    """Return the stable key used to map display rows back to LLM references."""

    candidate_id = _item_text(item, "candidate_id", "候補ID")
    if candidate_id:
        return f"id:{candidate_id.upper()}"

    symbol = _ranking_item_symbol(item)
    if not symbol:
        return ""
    market = _item_text(item, "market", "市場", "exchange", "取引所")
    if market:
        return f"{symbol}|{market.upper()}"
    return symbol


def _reference_from_result(
    result: LLMFactorResult,
    *,
    source_type: LLMFactorRankingReferenceSourceType,
    warning: str | None = None,
) -> LLMFactorRankingReference:
    return LLMFactorRankingReference(
        bullish_score=result.llm_bullish_score,
        bearish_score=result.llm_bearish_score,
        confidence_score=result.llm_confidence_score,
        freshness_score=result.llm_freshness_score,
        evidence_quality_score=result.llm_evidence_quality_score,
        source_count=len(result.evidence_sources),
        result_id=_result_id(result),
        source_type=source_type,
        is_reference_only=True,
        warning=warning,
    )


def _unavailable_reference(warning: str) -> LLMFactorRankingReference:
    return LLMFactorRankingReference(
        source_type="unavailable",
        is_reference_only=True,
        warning=warning,
    )


def _result_id(result: LLMFactorResult) -> str:
    return f"{result.ticker.strip().upper()}:{result.source_hash[:12]}"


def _ranking_item_symbol(item: Mapping[str, object]) -> str:
    return _item_text(item, "symbol", "ticker", "銘柄", "コード").upper()


def _item_text(item: Mapping[str, object], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _deterministic_ranking_generated_at(as_of_date: date) -> datetime:
    return datetime.combine(as_of_date, time.min, tzinfo=UTC)
