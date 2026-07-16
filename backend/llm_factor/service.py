from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Iterable

from pydantic import ValidationError

from backend.llm_factor.cache import (
    DEFAULT_LLM_FACTOR_CACHE_TTL_SECONDS,
    LLM_FACTOR_CACHE_DIR,
    build_llm_factor_cache_entry,
    find_llm_factor_cache_entry,
    llm_factor_cache_expires_at,
    llm_factor_cache_key,
    save_llm_factor_cache_entry,
)
from backend.llm_factor.contracts import (
    LLM_FACTOR_FAKE_MODEL_NAME,
    LLM_FACTOR_PROMPT_VERSION,
    BearishFactor,
    BullishFactor,
    EvidenceSource,
    LLMFactorCacheMetadata,
    LLMFactorCacheStatus,
    LLMFactorEvidenceSelection,
    LLMFactorResult,
    LLMFactorServiceResult,
)

_DEFAULT_DISCLAIMER = "本結果は投資判断材料の整理であり、売買推奨ではありません。"
_NO_LLM_WARNING = "LLM実行はまだ接続していないため、SMAIのローカル規則で参考表示しています。"
_NO_SOURCE_WARNING = (
    "出典付きのニュース・IR・Research情報が少ないため、LLM材料分析の信頼度を低くしています。"
)
_NO_OFFICIAL_SOURCE_WARNING = (
    "公式開示を根拠として確認できないため、AI材料分析の確信度を控えめにしています。"
)
_NO_PRIMARY_DISCLOSURE_WARNING = (
    "TDnet・EDINETなどの一次開示が少ないため、AI材料分析は補助情報として確認してください。"
)

_BULLISH_KEYWORDS = (
    "増配",
    "自社株買",
    "上方修正",
    "好決算",
    "成長",
    "新製品",
    "契約",
    "受注",
    "還元",
    "半導体",
    "AI",
    "データセンター",
)
_BEARISH_KEYWORDS = (
    "下方修正",
    "減益",
    "訴訟",
    "規制",
    "競争",
    "逆風",
    "為替",
    "原材料",
    "リスク",
    "警戒",
)
_THEME_KEYWORDS = (
    "AI",
    "半導体",
    "防衛",
    "データセンター",
    "EV",
    "インバウンド",
    "高配当",
    "円安",
)


class LLMFactorValidationError(ValueError):
    """Raised when an LLM factor provider response cannot be validated."""


class FakeLLMFactorService:
    """Deterministic no-network LLM Factor service used before real LLM wiring."""

    def build_reference_result(
        self,
        *,
        ticker: str,
        as_of: date,
        evidence_sources: Iterable[EvidenceSource] = (),
        company_name: str | None = None,
        generated_at: datetime | None = None,
    ) -> LLMFactorResult:
        generated_at = generated_at or datetime.now(UTC)
        selection = select_evidence_sources_for_factor(
            ticker=ticker,
            evidence_sources=evidence_sources,
            company_name=company_name,
        )
        sources = selection.sources
        has_source_backing = bool(sources)
        warnings = [_NO_LLM_WARNING]
        if not sources:
            sources = normalized_evidence_sources_for_factor(
                ticker=ticker,
                as_of=as_of,
                evidence_sources=sources,
            )
            warnings.append(_NO_SOURCE_WARNING)
        warnings.extend(_evidence_selection_warnings(selection.summary))

        source_hash = source_hash_for_evidence(sources)
        evidence_quality = _evidence_quality_score(sources)
        freshness = _freshness_score(sources, as_of=as_of)
        confidence = _confidence_score(
            evidence_quality=evidence_quality,
            freshness=freshness,
        )
        confidence = min(
            confidence,
            evidence_confidence_cap(sources, has_source_backing=has_source_backing),
            Decimal("75"),
        )
        bullish_factors = _bullish_factors_from_sources(sources, confidence=confidence)
        bearish_factors = _bearish_factors_from_sources(sources, confidence=confidence)
        bullish_score = _material_score(bullish_factors, base=Decimal("50"))
        bearish_score = _material_score(bearish_factors, base=Decimal("42"))
        catalyst_score = _catalyst_score(sources, bullish_factors, bearish_factors)
        risk_score = _risk_score(sources, bearish_factors)
        theme_score = _theme_score(sources)

        return LLMFactorResult(
            ticker=ticker,
            as_of=as_of,
            generated_at=generated_at,
            model_name=LLM_FACTOR_FAKE_MODEL_NAME,
            prompt_version=LLM_FACTOR_PROMPT_VERSION,
            source_hash=source_hash,
            llm_bullish_score=bullish_score,
            llm_bearish_score=bearish_score,
            llm_catalyst_score=catalyst_score,
            llm_risk_score=risk_score,
            llm_theme_score=theme_score,
            llm_freshness_score=freshness,
            llm_evidence_quality_score=evidence_quality,
            llm_confidence_score=confidence,
            bullish_factors=bullish_factors[:3],
            bearish_factors=bearish_factors[:3],
            evidence_sources=sources,
            evidence_selection=selection.summary.model_copy(
                update={"fallback_used": not has_source_backing}
            ),
            summary=_summary_text(
                bullish_score=bullish_score,
                bearish_score=bearish_score,
                confidence=confidence,
            ),
            disclaimer=_DEFAULT_DISCLAIMER,
            warnings=warnings,
        )

    def parse_provider_json(
        self,
        raw_json: str,
        *,
        ticker: str,
        as_of: date,
        fallback_sources: Iterable[EvidenceSource] = (),
        company_name: str | None = None,
        generated_at: datetime | None = None,
    ) -> LLMFactorResult:
        """Validate provider JSON and return a conservative fallback on invalid output."""

        try:
            payload = json.loads(raw_json)
            return LLMFactorResult.model_validate(payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            result = self.build_reference_result(
                ticker=ticker,
                as_of=as_of,
                evidence_sources=fallback_sources,
                company_name=company_name,
                generated_at=generated_at,
            )
            return result.model_copy(
                update={
                    "llm_confidence_score": min(
                        result.llm_confidence_score,
                        Decimal("20"),
                    ),
                    "warnings": [
                        *result.warnings,
                        f"LLM応答を検証できなかったため、参考表示に切り替えました: {type(exc).__name__}",
                    ],
                }
            )


class CachedLLMFactorService:
    """Cache-aware LLM Factor service used by UI/reference flows."""

    def __init__(
        self,
        *,
        base_service: FakeLLMFactorService | None = None,
        cache_dir: Path | str = LLM_FACTOR_CACHE_DIR,
        ttl_seconds: int = DEFAULT_LLM_FACTOR_CACHE_TTL_SECONDS,
    ) -> None:
        self.base_service = base_service or FakeLLMFactorService()
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_seconds

    def build_reference_result(
        self,
        *,
        ticker: str,
        as_of: date,
        evidence_sources: Iterable[EvidenceSource] = (),
        company_name: str | None = None,
        now: datetime | None = None,
    ) -> LLMFactorServiceResult:
        now_utc = _ensure_utc(now or datetime.now(UTC))
        raw_sources = list(evidence_sources)
        selection = select_evidence_sources_for_factor(
            ticker=ticker,
            evidence_sources=raw_sources,
            company_name=company_name,
        )
        cache_sources = normalized_evidence_sources_for_factor(
            ticker=ticker,
            as_of=as_of,
            evidence_sources=selection.sources,
        )
        cache_input_sources = raw_sources or cache_sources
        source_hash = source_hash_for_evidence(cache_input_sources)
        cache_key = llm_factor_cache_key(
            ticker=ticker,
            as_of=as_of,
            source_hash=source_hash,
            model_name=LLM_FACTOR_FAKE_MODEL_NAME,
            prompt_version=LLM_FACTOR_PROMPT_VERSION,
        )
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

        result = self.base_service.build_reference_result(
            ticker=ticker,
            as_of=as_of,
            evidence_sources=raw_sources,
            company_name=company_name,
            generated_at=now_utc,
        )
        expires_at = llm_factor_cache_expires_at(now=now_utc, ttl_seconds=self.ttl_seconds)
        entry = build_llm_factor_cache_entry(
            result,
            cache_key=cache_key,
            expires_at=expires_at,
        )
        try:
            save_llm_factor_cache_entry(entry, cache_dir=self.cache_dir)
        except OSError:
            pass
        return LLMFactorServiceResult(
            result=result,
            cache=_cache_metadata(
                status=lookup.status,
                cache_hit=False,
                cache_key=cache_key,
                result=result,
                expires_at=expires_at,
            ),
        )


def source_hash_for_evidence(sources: Iterable[EvidenceSource]) -> str:
    payload = [
        {
            "title": source.title,
            "source_type": source.source_type,
            "source_url": source.source_url,
            "source_date": source.source_date.isoformat(),
            "provider": source.provider or "",
        }
        for source in sources
    ]
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def normalized_evidence_sources_for_factor(
    *,
    ticker: str,
    as_of: date,
    evidence_sources: Iterable[EvidenceSource],
) -> list[EvidenceSource]:
    sources = list(evidence_sources)
    if sources:
        return sources
    return [_fallback_evidence_source(ticker=ticker, as_of=as_of)]


class _EvidenceSelection:
    """Internal pairing of retained evidence and its UI-safe audit summary."""

    def __init__(self, sources: list[EvidenceSource], summary: LLMFactorEvidenceSelection) -> None:
        self.sources = sources
        self.summary = summary


def select_evidence_sources_for_factor(
    *,
    ticker: str,
    evidence_sources: Iterable[EvidenceSource],
    company_name: str | None = None,
) -> _EvidenceSelection:
    """Retain entity-matched, non-duplicate sources for qualitative analysis.

    A company name activates strict entity matching.  Callers without a company
    identity retain their supplied sources because relevance cannot be judged
    safely from a ticker alone in all markets.  Cockpit and live generation
    always provide the company identity.
    """

    candidates = list(evidence_sources)
    retained: list[EvidenceSource] = []
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    duplicate_count = 0
    unrelated_count = 0
    strict_matching = bool(str(company_name or "").strip())
    for source in candidates:
        if strict_matching and not _source_matches_entity(
            source,
            ticker=ticker,
            company_name=company_name or "",
        ):
            unrelated_count += 1
            continue
        canonical_url = _canonical_source_url(source.source_url)
        canonical_title = _canonical_source_title(source.title)
        is_duplicate = (bool(canonical_url) and canonical_url in seen_urls) or (
            len(canonical_title) >= 12 and canonical_title in seen_titles
        )
        if is_duplicate:
            duplicate_count += 1
            continue
        if canonical_url:
            seen_urls.add(canonical_url)
        if len(canonical_title) >= 12:
            seen_titles.add(canonical_title)
        retained.append(source)

    official_count = sum(1 for source in retained if _is_official_source(source))
    primary_disclosure_count = sum(
        1 for source in retained if source.source_type in {"tdnet", "edinet"}
    )
    return _EvidenceSelection(
        sources=retained,
        summary=LLMFactorEvidenceSelection(
            input_count=len(candidates),
            retained_count=len(retained),
            duplicate_count=duplicate_count,
            unrelated_count=unrelated_count,
            official_count=official_count,
            primary_disclosure_count=primary_disclosure_count,
        ),
    )


def evidence_confidence_cap(
    sources: Iterable[EvidenceSource],
    *,
    has_source_backing: bool = True,
) -> Decimal:
    """Return an evidence-based upper bound for an AI confidence score."""

    source_list = [source for source in sources if source.source_type != "local_reference"]
    if not has_source_backing or not source_list:
        return Decimal("30")
    official_count = sum(1 for source in source_list if _is_official_source(source))
    primary_disclosure_count = sum(
        1 for source in source_list if source.source_type in {"tdnet", "edinet"}
    )
    if official_count == 0:
        return Decimal("60")
    if primary_disclosure_count == 0:
        return Decimal("70")
    if len(source_list) < 3:
        return Decimal("75")
    return Decimal("85")


def _evidence_selection_warnings(summary: LLMFactorEvidenceSelection) -> list[str]:
    warnings: list[str] = []
    if summary.unrelated_count:
        warnings.append(
            f"対象銘柄との関連を確認できない根拠 {summary.unrelated_count}件を除外しました。"
        )
    if summary.duplicate_count:
        warnings.append(f"重複と判定した根拠 {summary.duplicate_count}件を除外しました。")
    if summary.retained_count and summary.official_count == 0:
        warnings.append(_NO_OFFICIAL_SOURCE_WARNING)
    elif summary.retained_count and summary.primary_disclosure_count == 0:
        warnings.append(_NO_PRIMARY_DISCLOSURE_WARNING)
    return warnings


def _source_matches_entity(
    source: EvidenceSource,
    *,
    ticker: str,
    company_name: str,
) -> bool:
    if source.source_type == "local_reference":
        return True
    # ``smai://research-evidence/<ticker>/...`` is an internal locator, not a
    # publisher URL.  It carries the selected ticker for storage purposes, so
    # treating it as entity evidence would incorrectly retain any unrelated
    # research chunk (for example, an unrelated news headline returned by a
    # broad search query).
    source_url = "" if source.source_url.startswith("smai://") else source.source_url
    haystack = _normalise_match_text(
        " ".join([source.title, source.summary or "", source_url, source.provider or ""])
    )
    ticker_tokens = {
        _normalise_match_text(ticker),
        _normalise_match_text(ticker.split(".", maxsplit=1)[0]),
    }
    if any(token and token in haystack for token in ticker_tokens):
        return True
    company_token = _company_match_token(company_name)
    return bool(company_token and company_token in haystack)


def _company_match_token(company_name: str) -> str:
    normalized = _normalise_match_text(company_name)
    normalized = re.sub(
        r"(corporation|corp|company|co|ltd|limited|inc|plc|holdings|group|株式会社|株式|会社)$",
        "",
        normalized,
    )
    return normalized


def _normalise_match_text(value: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKC", value).lower()
        if character.isalnum()
    )


def _canonical_source_title(value: str) -> str:
    return _normalise_match_text(value)


def _canonical_source_url(value: str) -> str:
    normalized = value.strip().lower().split("#", maxsplit=1)[0]
    if "?" not in normalized:
        return normalized.rstrip("/")
    base, raw_query = normalized.split("?", maxsplit=1)
    retained_query = [
        item
        for item in raw_query.split("&")
        if item and not item.startswith(("utm_", "ref=", "source="))
    ]
    suffix = f"?{'&'.join(sorted(retained_query))}" if retained_query else ""
    return f"{base.rstrip('/')}{suffix}"


def _is_official_source(source: EvidenceSource) -> bool:
    return source.source_type in {"tdnet", "edinet", "company_ir"}


def _fallback_evidence_source(*, ticker: str, as_of: date) -> EvidenceSource:
    return EvidenceSource(
        title="SMAIローカル参考表示",
        source_type="local_reference",
        source_url=f"smai://llm-factor/reference/{ticker}",
        source_date=as_of,
        provider="smai",
        summary="LLM材料分析のUIとschemaを確認するためのローカル参考情報です。",
        reliability_score=Decimal("25"),
    )


def _evidence_quality_score(sources: list[EvidenceSource]) -> Decimal:
    if not sources:
        return Decimal("20")
    reliability_avg = sum(source.reliability_score for source in sources) / Decimal(len(sources))
    source_bonus = min(Decimal("20"), Decimal(len(sources) * 5))
    official_bonus = (
        Decimal("10")
        if any(source.source_type in {"tdnet", "edinet", "company_ir"} for source in sources)
        else Decimal("0")
    )
    return _clamp_score(reliability_avg + source_bonus + official_bonus)


def _freshness_score(sources: list[EvidenceSource], *, as_of: date) -> Decimal:
    if not sources:
        return Decimal("20")
    newest_days = min(abs((as_of - source.source_date).days) for source in sources)
    if newest_days <= 7:
        return Decimal("90")
    if newest_days <= 30:
        return Decimal("75")
    if newest_days <= 90:
        return Decimal("55")
    if newest_days <= 365:
        return Decimal("40")
    return Decimal("25")


def _confidence_score(*, evidence_quality: Decimal, freshness: Decimal) -> Decimal:
    return _clamp_score((evidence_quality * Decimal("0.65")) + (freshness * Decimal("0.35")))


def _bullish_factors_from_sources(
    sources: list[EvidenceSource],
    *,
    confidence: Decimal,
) -> list[BullishFactor]:
    factors: list[BullishFactor] = []
    for source in sources:
        if source.source_type == "local_reference":
            continue
        text = f"{source.title} {source.summary or ''}"
        if not _contains_any(text, _BULLISH_KEYWORDS):
            continue
        factors.append(
            BullishFactor(
                title=_factor_title(source.title, fallback="上昇材料候補"),
                score=_clamp_score(Decimal("55") + confidence * Decimal("0.25")),
                reason="出典タイトルと要約に、上昇材料として確認したい語句が含まれます。",
                source_url=source.source_url,
                source_date=source.source_date,
                source_type=source.source_type,
            )
        )
    return factors


def _bearish_factors_from_sources(
    sources: list[EvidenceSource],
    *,
    confidence: Decimal,
) -> list[BearishFactor]:
    factors: list[BearishFactor] = []
    for source in sources:
        if source.source_type == "local_reference":
            continue
        text = f"{source.title} {source.summary or ''}"
        if not _contains_any(text, _BEARISH_KEYWORDS):
            continue
        factors.append(
            BearishFactor(
                title=_factor_title(source.title, fallback="注意材料候補"),
                score=_clamp_score(Decimal("50") + confidence * Decimal("0.20")),
                reason="出典タイトルと要約に、注意材料として確認したい語句が含まれます。",
                source_url=source.source_url,
                source_date=source.source_date,
                source_type=source.source_type,
            )
        )
    return factors


def _material_score(
    factors: list[BullishFactor] | list[BearishFactor],
    *,
    base: Decimal,
) -> Decimal:
    if not factors:
        return base
    factor_avg = sum(factor.score for factor in factors) / Decimal(len(factors))
    return _clamp_score((base * Decimal("0.35")) + (factor_avg * Decimal("0.65")))


def _catalyst_score(
    sources: list[EvidenceSource],
    bullish_factors: list[BullishFactor],
    bearish_factors: list[BearishFactor],
) -> Decimal:
    official_count = sum(
        1 for source in sources if source.source_type in {"tdnet", "edinet", "company_ir"}
    )
    factor_count = len(bullish_factors) + len(bearish_factors)
    return _clamp_score(Decimal("38") + Decimal(official_count * 12) + Decimal(factor_count * 6))


def _risk_score(
    sources: list[EvidenceSource],
    bearish_factors: list[BearishFactor],
) -> Decimal:
    if bearish_factors:
        return _material_score(bearish_factors, base=Decimal("45"))
    if any(source.source_type == "local_reference" for source in sources):
        return Decimal("45")
    return Decimal("38")


def _theme_score(sources: list[EvidenceSource]) -> Decimal:
    text = " ".join(f"{source.title} {source.summary or ''}" for source in sources)
    match_count = sum(1 for keyword in _THEME_KEYWORDS if keyword in text)
    return _clamp_score(Decimal("45") + Decimal(match_count * 8))


def _summary_text(
    *,
    bullish_score: Decimal,
    bearish_score: Decimal,
    confidence: Decimal,
) -> str:
    if confidence < Decimal("35"):
        return "定性材料の出典がまだ少ないため、AI材料分析は低信頼の参考表示です。"
    if bullish_score > bearish_score + Decimal("15"):
        return "定性材料は上昇材料寄りですが、出典と日付を確認して読みます。"
    if bearish_score > bullish_score + Decimal("15"):
        return "定性材料は注意材料寄りです。リスク要因と公式開示を確認します。"
    return "定性材料は強弱が混在しています。上昇材料と注意材料を分けて確認します。"


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _factor_title(title: str, *, fallback: str) -> str:
    cleaned = title.strip()
    if not cleaned:
        return fallback
    return cleaned[:48]


def _clamp_score(value: Decimal) -> Decimal:
    return max(
        Decimal("0"),
        min(Decimal("100"), value.quantize(Decimal("1"))),
    )


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


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
