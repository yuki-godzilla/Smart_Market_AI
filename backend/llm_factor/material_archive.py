"""Local point-in-time archive and bounded LLM material-risk shadow contract.

The archive stores source metadata, short summaries, hashes, and the first time SMAI
actually observed a document.  It does not pretend that material fetched today was
available in an older backtest and it never stores a generated price target.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Literal, Self

from pydantic import ConfigDict, Field, TypeAdapter, model_validator

from backend.core.data_contracts import StrictBaseModel
from backend.llm_factor.point_in_time import PointInTimeEvidence
from backend.news.contracts import NewsDashboardSnapshot, NewsHeadlineCard
from backend.research.external_contracts import ExternalResearchSourcePayload

MATERIAL_ARCHIVE_SCHEMA_VERSION = "point-in-time-material-archive-v1"
MATERIAL_RISK_SIGNAL_SCHEMA_VERSION = "llm-material-risk-shadow-v1"
DEFAULT_MATERIAL_ARCHIVE_PATH = Path("data/cache/point_in_time_material_archive_v1.json")

MaterialArchiveProvenance = Literal["live_observed", "provider_replay"]
MaterialConfidenceCap = Literal["medium", "low"]


class PointInTimeMaterialRecord(StrictBaseModel):
    """One locally observed news or IR item with a causal first-seen boundary."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    schema_version: str = MATERIAL_ARCHIVE_SCHEMA_VERSION
    record_id: str = Field(min_length=1)
    symbols: list[str] = Field(default_factory=list)
    source_family: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    published_at: datetime
    available_at: datetime
    first_archived_at: datetime
    last_seen_at: datetime
    observation_count: int = Field(default=1, ge=1)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    is_official_source: bool = False
    provenance: MaterialArchiveProvenance = "live_observed"

    @model_validator(mode="after")
    def validate_timestamps(self) -> Self:
        for field_name in (
            "published_at",
            "available_at",
            "first_archived_at",
            "last_seen_at",
        ):
            _require_aware(getattr(self, field_name), field_name)
        if self.available_at < self.published_at:
            raise ValueError("available_at must not precede published_at")
        if self.first_archived_at < self.available_at:
            raise ValueError("first_archived_at must not precede available_at")
        if self.last_seen_at < self.first_archived_at:
            raise ValueError("last_seen_at must not precede first_archived_at")
        normalized_symbols = _normalized_symbols(self.symbols)
        if normalized_symbols != self.symbols:
            raise ValueError("symbols must be normalized, unique, and sorted")
        return self


_ARCHIVE_LIST_ADAPTER = TypeAdapter(list[PointInTimeMaterialRecord])


class MaterialArchiveLoadResult(StrictBaseModel):
    """Safe archive read result that keeps corruption visible to operators."""

    records: list[PointInTimeMaterialRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class MaterialArchiveWriteResult(StrictBaseModel):
    """Counts from one atomic idempotent archive update."""

    path: str = Field(min_length=1)
    input_count: int = Field(ge=0)
    inserted_count: int = Field(ge=0)
    updated_count: int = Field(ge=0)
    total_count: int = Field(ge=0)


class LLMMaterialRiskSignal(StrictBaseModel):
    """Typed LLM output used only for confidence/range shadow evaluation."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    schema_version: str = MATERIAL_RISK_SIGNAL_SCHEMA_VERSION
    signal_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    horizon_days: int = Field(ge=1)
    decision_at: datetime
    generated_at: datetime
    provider: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    adverse_risk_score: Decimal = Field(ge=0, le=100)
    event_relevance_score: Decimal = Field(ge=0, le=100)
    evidence_confidence_score: Decimal = Field(ge=0, le=100)
    uncertainty_score: Decimal = Field(ge=0, le=100)
    predicted_impact_label: Literal[-1, 0, 1]
    cited_record_ids: list[str] = Field(min_length=1)
    rationale: str = Field(min_length=1, max_length=800)

    @model_validator(mode="after")
    def validate_causal_contract(self) -> Self:
        _require_aware(self.decision_at, "decision_at")
        _require_aware(self.generated_at, "generated_at")
        if self.generated_at < self.decision_at:
            raise ValueError("generated_at must not precede decision_at")
        if len(self.cited_record_ids) != len(set(self.cited_record_ids)):
            raise ValueError("cited_record_ids must be unique")
        return self


class LLMMaterialRiskShadowAdjustment(StrictBaseModel):
    """Bounded non-price adjustment proposed for offline comparison only."""

    applied: bool
    confidence_cap: MaterialConfidenceCap | None = None
    range_multiplier: Decimal = Field(default=Decimal("1.00"), ge=1, le=Decimal("1.25"))
    center_return_adjustment: Decimal = Decimal("0")
    valid_cited_record_ids: list[str] = Field(default_factory=list)
    ignored_cited_record_ids: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def keep_price_center_unchanged(self) -> Self:
        if self.center_return_adjustment != 0:
            raise ValueError("LLM material shadow adjustment must not change center return")
        return self


def material_records_from_news_snapshot(
    snapshot: NewsDashboardSnapshot,
    *,
    archived_at: datetime | None = None,
) -> list[PointInTimeMaterialRecord]:
    """Convert deduplicated live headline cards without inventing publication times."""

    observed_at = archived_at or snapshot.fetched_at or snapshot.generated_at
    _require_aware(observed_at, "archived_at")
    cards = _unique_news_cards(snapshot)
    return [
        record
        for card in cards
        if (record := material_record_from_news_card(card, archived_at=observed_at)) is not None
    ]


def material_record_from_news_card(
    card: NewsHeadlineCard,
    *,
    archived_at: datetime,
) -> PointInTimeMaterialRecord | None:
    """Build a causal record; undated or URL-less cards are not backtest evidence."""

    _require_aware(archived_at, "archived_at")
    if card.published_at is None or not card.url:
        return None
    published_at = _as_utc(card.published_at)
    first_archived_at = max(archived_at, published_at)
    symbols = _normalized_symbols(
        [*card.related_symbols, *card.inferred_symbols, *card.macro_proxy_symbols]
    )
    summary = _bounded_summary(card.summary or card.title)
    source_family = (card.source_name or card.source_type).strip().casefold().replace(" ", "_")
    return _record(
        symbols=symbols,
        source_family=source_family or "unknown_news",
        source_type=card.source_type,
        title=card.title,
        summary=summary,
        source_url=card.url,
        published_at=published_at,
        available_at=published_at,
        archived_at=first_archived_at,
        is_official_source=card.is_official_source,
        provenance="live_observed",
    )


def material_record_from_external_payload(
    payload: ExternalResearchSourcePayload,
    *,
    provenance: MaterialArchiveProvenance = "live_observed",
) -> PointInTimeMaterialRecord:
    """Archive external IR/research conservatively when only a publication date is known."""

    fetched_at = _as_utc(payload.fetched_at)
    published_at = (
        datetime.combine(payload.published_at, time.min, tzinfo=UTC)
        if payload.published_at is not None
        else fetched_at
    )
    # Date-only provider metadata cannot prove intraday availability.  Treat the
    # actual fetch time as the first usable decision boundary.
    available_at = fetched_at
    return _record(
        symbols=_normalized_symbols([payload.symbol]),
        source_family=payload.provider.strip().casefold(),
        source_type=payload.source_type,
        title=payload.title,
        summary=_bounded_summary(payload.content),
        source_url=payload.source_url,
        published_at=min(published_at, available_at),
        available_at=available_at,
        archived_at=fetched_at,
        is_official_source=payload.source_type in {"tdnet", "company_ir", "annual_report"},
        provenance=provenance,
    )


def load_material_archive(
    path: Path = DEFAULT_MATERIAL_ARCHIVE_PATH,
) -> MaterialArchiveLoadResult:
    """Load a local archive without turning corruption into an empty success."""

    if not path.exists():
        return MaterialArchiveLoadResult()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        records = _ARCHIVE_LIST_ADAPTER.validate_python(payload)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return MaterialArchiveLoadResult(
            warnings=[f"material archive could not be loaded: {type(exc).__name__}"],
        )
    return MaterialArchiveLoadResult(records=sorted(records, key=_record_sort_key))


def archive_material_records(
    records: Iterable[PointInTimeMaterialRecord],
    *,
    path: Path = DEFAULT_MATERIAL_ARCHIVE_PATH,
) -> MaterialArchiveWriteResult:
    """Merge records by stable ID and atomically replace the bounded metadata archive."""

    supplied = list(records)
    loaded = load_material_archive(path)
    if loaded.warnings:
        raise ValueError(loaded.warnings[0])
    merged = {record.record_id: record for record in loaded.records}
    inserted = 0
    updated = 0
    for record in supplied:
        current = merged.get(record.record_id)
        if current is None:
            merged[record.record_id] = record
            inserted += 1
            continue
        merged[record.record_id] = current.model_copy(
            update={
                "symbols": _normalized_symbols([*current.symbols, *record.symbols]),
                "first_archived_at": min(current.first_archived_at, record.first_archived_at),
                "last_seen_at": max(current.last_seen_at, record.last_seen_at),
                "observation_count": current.observation_count + 1,
            }
        )
        updated += 1
    ordered = sorted(merged.values(), key=_record_sort_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_text(
            json.dumps(
                [record.model_dump(mode="json") for record in ordered],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
            newline="\n",
        )
        _ARCHIVE_LIST_ADAPTER.validate_python(json.loads(temporary.read_text(encoding="utf-8")))
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return MaterialArchiveWriteResult(
        path=str(path),
        input_count=len(supplied),
        inserted_count=inserted,
        updated_count=updated,
        total_count=len(ordered),
    )


def point_in_time_evidence_from_material_record(
    record: PointInTimeMaterialRecord,
    *,
    symbol: str | None = None,
) -> PointInTimeEvidence:
    """Bridge archived metadata into the existing future/late-archive filter."""

    normalized_symbol = symbol.strip().upper() if symbol else None
    if normalized_symbol and normalized_symbol not in record.symbols:
        raise ValueError("requested symbol is not linked to the material record")
    return PointInTimeEvidence(
        evidence_id=record.record_id,
        symbol=normalized_symbol or (record.symbols[0] if len(record.symbols) == 1 else None),
        source_family=record.source_family,
        title=record.title,
        summary=record.summary,
        source_url=record.source_url,
        published_at=record.published_at,
        available_at=record.available_at,
        archived_at=record.first_archived_at,
        static_relevance=Decimal("0.80") if record.is_official_source else Decimal("0.60"),
    )


def build_material_risk_shadow_adjustment(
    signal: LLMMaterialRiskSignal,
    records: Iterable[PointInTimeMaterialRecord],
) -> LLMMaterialRiskShadowAdjustment:
    """Map a cited, fresh typed signal to bounded confidence/range changes only."""

    by_id = {record.record_id: record for record in records}
    valid = [
        record_id
        for record_id in signal.cited_record_ids
        if record_id in by_id
        and by_id[record_id].first_archived_at <= signal.decision_at
        and signal.symbol.strip().upper() in by_id[record_id].symbols
    ]
    ignored = [record_id for record_id in signal.cited_record_ids if record_id not in valid]
    if not valid:
        return LLMMaterialRiskShadowAdjustment(
            applied=False,
            valid_cited_record_ids=[],
            ignored_cited_record_ids=ignored,
            reasons=["decision時点で利用可能な銘柄一致citationがないためfallback"],
        )
    if signal.event_relevance_score < 60 or signal.evidence_confidence_score < 50:
        return LLMMaterialRiskShadowAdjustment(
            applied=False,
            valid_cited_record_ids=valid,
            ignored_cited_record_ids=ignored,
            reasons=["材料関連度または根拠信頼度がshadow適用gate未満"],
        )
    if signal.adverse_risk_score >= 80 or signal.uncertainty_score >= 80:
        return LLMMaterialRiskShadowAdjustment(
            applied=True,
            confidence_cap="low",
            range_multiplier=Decimal("1.25"),
            valid_cited_record_ids=valid,
            ignored_cited_record_ids=ignored,
            reasons=["強い悪材料または不確実性を検出したため信頼度上限とrangeを保守化"],
        )
    if signal.adverse_risk_score >= 65 or signal.uncertainty_score >= 65:
        return LLMMaterialRiskShadowAdjustment(
            applied=True,
            confidence_cap="medium",
            range_multiplier=Decimal("1.15"),
            valid_cited_record_ids=valid,
            ignored_cited_record_ids=ignored,
            reasons=["悪材料または不確実性を検出したためrangeを限定的に拡張"],
        )
    return LLMMaterialRiskShadowAdjustment(
        applied=False,
        valid_cited_record_ids=valid,
        ignored_cited_record_ids=ignored,
        reasons=["材料リスクが調整gate未満のため既存予測を維持"],
    )


def _record(
    *,
    symbols: list[str],
    source_family: str,
    source_type: str,
    title: str,
    summary: str,
    source_url: str,
    published_at: datetime,
    available_at: datetime,
    archived_at: datetime,
    is_official_source: bool,
    provenance: MaterialArchiveProvenance,
) -> PointInTimeMaterialRecord:
    canonical = "|".join(
        [source_url.strip(), published_at.isoformat(), title.strip(), ",".join(symbols)]
    )
    content = "\n".join([title.strip(), summary.strip(), source_url.strip()])
    return PointInTimeMaterialRecord(
        record_id=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        symbols=symbols,
        source_family=source_family or "unknown",
        source_type=source_type,
        title=title.strip(),
        summary=summary,
        source_url=source_url.strip(),
        published_at=published_at,
        available_at=available_at,
        first_archived_at=archived_at,
        last_seen_at=archived_at,
        content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        is_official_source=is_official_source,
        provenance=provenance,
    )


def _unique_news_cards(snapshot: NewsDashboardSnapshot) -> list[NewsHeadlineCard]:
    cards = [
        *snapshot.stream_headlines,
        *(card for lane in snapshot.category_lanes for card in lane.headlines),
    ]
    unique: dict[str, NewsHeadlineCard] = {}
    for card in cards:
        key = (card.url or card.title).strip().casefold()
        unique.setdefault(key, card)
    return list(unique.values())


def _normalized_symbols(values: Iterable[str]) -> list[str]:
    return sorted({value.strip().upper() for value in values if value and value.strip()})


def _bounded_summary(value: str, *, max_chars: int = 1200) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        return "要約なし"
    return (
        normalized if len(normalized) <= max_chars else normalized[: max_chars - 1].rstrip() + "…"
    )


def _as_utc(value: datetime) -> datetime:
    _require_aware(value, "datetime")
    return value.astimezone(UTC)


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _record_sort_key(record: PointInTimeMaterialRecord) -> tuple[datetime, str]:
    return (record.first_archived_at, record.record_id)
