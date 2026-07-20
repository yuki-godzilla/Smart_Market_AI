"""Point-in-time event evidence and market-feedback source memory.

This module is evaluation-only.  It creates the causal boundary required to
test LLM-derived event features without allowing future documents or immature
market labels into retrieval, training, or source-reliability updates.
"""

from __future__ import annotations

import re
from bisect import bisect_left
from collections import Counter
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable, Literal, Mapping, Self
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import numpy as np
from pydantic import ConfigDict, Field, model_validator

from backend.core.data_contracts import Bar, StrictBaseModel

POINT_IN_TIME_EVENT_SCHEMA_VERSION = "point-in-time-event-v1"
DEFAULT_MAX_RETRIEVAL_CANDIDATES = 20
DEFAULT_MAX_READER_EVIDENCE = 5
DEFAULT_MAX_PEER_EVIDENCE_RATIO = Decimal("0.20")

EventType = Literal[
    "earnings_guidance",
    "legal_regulatory",
    "capital_transactions",
    "management_operations",
    "other_mixed",
]
ImpactLabel = Literal[-1, 0, 1]
SourceMemoryKey = tuple[str, EventType, int]

_EVENT_CUES: dict[EventType, tuple[str, ...]] = {
    "earnings_guidance": (
        "earnings",
        "revenue",
        "profit",
        "guidance",
        "forecast",
        "dividend",
        "決算",
        "業績",
        "売上",
        "利益",
        "上方修正",
        "下方修正",
        "配当",
    ),
    "legal_regulatory": (
        "lawsuit",
        "litigation",
        "investigation",
        "regulatory",
        "regulation",
        "fine",
        "recall",
        "訴訟",
        "調査",
        "規制",
        "行政処分",
        "リコール",
    ),
    "capital_transactions": (
        "acquisition",
        "merger",
        "buyback",
        "offering",
        "financing",
        "share issuance",
        "tender offer",
        "買収",
        "合併",
        "自社株買い",
        "増資",
        "資金調達",
        "公開買付",
    ),
    "management_operations": (
        " ceo ",
        " cfo ",
        "director",
        "appointment",
        "resignation",
        "restructuring",
        "plant",
        "contract",
        "代表取締役",
        "社長",
        "役員",
        "就任",
        "辞任",
        "組織再編",
        "工場",
        "契約",
    ),
    "other_mixed": (),
}
_TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "source",
}


class PointInTimeEventAnchor(StrictBaseModel):
    """A material event assigned to the first usable market decision time."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    schema_version: str = POINT_IN_TIME_EVENT_SCHEMA_VERSION
    event_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    occurred_at: datetime
    decision_at: datetime
    headline: str = Field(min_length=1)
    summary: str | None = Field(default=None, min_length=1)
    source_url: str | None = Field(default=None, min_length=1)
    event_type: EventType

    @model_validator(mode="after")
    def validate_timestamps(self) -> Self:
        _require_aware(self.occurred_at, "occurred_at")
        _require_aware(self.decision_at, "decision_at")
        if self.decision_at < self.occurred_at:
            raise ValueError("decision_at must not precede occurred_at")
        return self


class PointInTimeEvidence(StrictBaseModel):
    """Archived evidence with the timestamp at which it became observable."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    evidence_id: str = Field(min_length=1)
    symbol: str | None = Field(default=None, min_length=1)
    source_family: str = Field(min_length=1)
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    published_at: datetime
    available_at: datetime
    archived_at: datetime
    static_relevance: Decimal = Field(ge=0, le=1)
    is_peer_context: bool = False

    @model_validator(mode="after")
    def validate_timestamps(self) -> Self:
        _require_aware(self.published_at, "published_at")
        _require_aware(self.available_at, "available_at")
        _require_aware(self.archived_at, "archived_at")
        if self.available_at < self.published_at:
            raise ValueError("available_at must not precede published_at")
        if self.archived_at < self.available_at:
            raise ValueError("archived_at must not precede available_at")
        return self


class PointInTimeEvidenceAudit(StrictBaseModel):
    """Counts explaining every exclusion from a point-in-time evidence pool."""

    input_count: int = Field(ge=0)
    retained_count: int = Field(ge=0)
    future_count: int = Field(ge=0)
    archive_late_count: int = Field(ge=0)
    anchor_duplicate_count: int = Field(ge=0)
    duplicate_count: int = Field(ge=0)
    unrelated_count: int = Field(ge=0)
    peer_cap_count: int = Field(ge=0)
    candidate_limit_count: int = Field(ge=0)


class PointInTimeEvidenceSelection(StrictBaseModel):
    """Causally valid candidates retained before Source Memory reranking."""

    event_id: str = Field(min_length=1)
    decision_at: datetime
    candidates: list[PointInTimeEvidence]
    audit: PointInTimeEvidenceAudit


class MarketResidualImpactLabel(StrictBaseModel):
    """Realized event impact after removing a causal horizon market model."""

    event_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    horizon_days: int = Field(ge=1)
    origin_at: datetime
    target_at: datetime
    fit_window_end_at: datetime
    fit_sample_count: int = Field(ge=3)
    alpha: Decimal
    beta: Decimal
    residual_sigma: Decimal = Field(gt=0)
    stock_return: Decimal
    benchmark_return: Decimal
    residual_return: Decimal
    standardized_residual: Decimal
    label: ImpactLabel


class SourceMemoryCell(StrictBaseModel):
    """Fractional Beta-Bernoulli evidence utility for one causal cell."""

    source_family: str = Field(min_length=1)
    event_type: EventType
    horizon_days: int = Field(ge=1)
    positive_mass: Decimal = Field(default=Decimal("0"), ge=0)
    negative_mass: Decimal = Field(default=Decimal("0"), ge=0)


class SourceMemoryConfig(StrictBaseModel):
    """Bounded defaults from the point-in-time Financial RAG evaluation."""

    shrinkage_kappa: Decimal = Field(default=Decimal("30"), gt=0)
    utility_clip: Decimal = Field(default=Decimal("0.20"), gt=0, le=Decimal("0.50"))
    rerank_lambda: Decimal = Field(default=Decimal("0.30"), ge=0, le=1)
    max_reader_evidence: int = Field(default=DEFAULT_MAX_READER_EVIDENCE, ge=1, le=20)

    @model_validator(mode="after")
    def validate_maximum_adjustment(self) -> Self:
        if self.rerank_lambda * self.utility_clip > Decimal("0.06"):
            raise ValueError("Source Memory adjustment must not exceed 0.06")
        return self


class SourceMemoryFeedback(StrictBaseModel):
    """A prediction whose market-residual target has become observable."""

    event_id: str = Field(min_length=1)
    event_type: EventType
    horizon_days: int = Field(ge=1)
    target_at: datetime
    predicted_label: ImpactLabel
    actual_label: ImpactLabel
    cited_evidence_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_target_at(self) -> Self:
        _require_aware(self.target_at, "target_at")
        return self


class SourceMemoryUpdateResult(StrictBaseModel):
    """Auditable result of a non-mutating Source Memory update."""

    applied: bool
    reason: str = Field(min_length=1)
    updated_cells: list[SourceMemoryCell] = Field(default_factory=list)
    valid_evidence_ids: list[str] = Field(default_factory=list)
    ignored_evidence_ids: list[str] = Field(default_factory=list)
    class_weight: Decimal = Field(gt=0)


class SourceMemoryRerankItem(StrictBaseModel):
    """Evidence score after a bounded, reliability-shrunk memory adjustment."""

    evidence: PointInTimeEvidence
    posterior_utility: Decimal = Field(ge=0, le=1)
    reliability: Decimal = Field(ge=0, le=1)
    memory_adjustment: Decimal
    reranked_score: Decimal


def classify_event_type(headline: str, summary: str | None = None) -> EventType:
    """Classify from anchor text only; ties and no matches remain other/mixed."""

    text = f" {headline} {summary or ''} ".casefold()
    counts = {
        event_type: sum(text.count(cue.casefold()) for cue in cues)
        for event_type, cues in _EVENT_CUES.items()
        if event_type != "other_mixed"
    }
    highest = max(counts.values(), default=0)
    winners = [event_type for event_type, count in counts.items() if count == highest]
    if highest == 0 or len(winners) != 1:
        return "other_mixed"
    return winners[0]


def assign_to_next_decision_time(
    occurred_at: datetime,
    decision_times: Iterable[datetime],
) -> datetime:
    """Map an event to the first supplied tradable decision time at or after it."""

    _require_aware(occurred_at, "occurred_at")
    selected = sorted(set(decision_times))
    if not selected:
        raise ValueError("decision_times must not be empty")
    for decision_at in selected:
        _require_aware(decision_at, "decision_times")
    index = bisect_left(selected, occurred_at)
    if index == len(selected):
        raise ValueError("no decision time is available after the event")
    return selected[index]


def select_point_in_time_evidence(
    event: PointInTimeEventAnchor,
    evidence: Iterable[PointInTimeEvidence],
    *,
    max_candidates: int = DEFAULT_MAX_RETRIEVAL_CANDIDATES,
    max_peer_ratio: Decimal = DEFAULT_MAX_PEER_EVIDENCE_RATIO,
) -> PointInTimeEvidenceSelection:
    """Remove future, late-archive, duplicate, and excess peer evidence."""

    if max_candidates < 1:
        raise ValueError("max_candidates must be positive")
    if max_peer_ratio < 0 or max_peer_ratio > 1:
        raise ValueError("max_peer_ratio must be between 0 and 1")
    supplied = list(evidence)
    counters: Counter[str] = Counter()
    anchor_url = _normalized_url(event.source_url) if event.source_url else None
    anchor_title = _normalized_text(event.headline)
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    eligible: list[PointInTimeEvidence] = []
    for item in sorted(supplied, key=_evidence_sort_key):
        if item.available_at > event.decision_at:
            counters["future"] += 1
            continue
        if item.archived_at > event.decision_at:
            counters["archive_late"] += 1
            continue
        normalized_url = _normalized_url(item.source_url)
        normalized_title = _normalized_text(item.title)
        if (anchor_url and normalized_url == anchor_url) or normalized_title == anchor_title:
            counters["anchor_duplicate"] += 1
            continue
        if item.symbol != event.symbol and not item.is_peer_context:
            counters["unrelated"] += 1
            continue
        if normalized_url in seen_urls or normalized_title in seen_titles:
            counters["duplicate"] += 1
            continue
        seen_urls.add(normalized_url)
        seen_titles.add(normalized_title)
        eligible.append(item)

    direct_capacity = min(
        max_candidates,
        sum(not item.is_peer_context for item in eligible),
    )
    if max_peer_ratio == 1:
        peer_limit = max_candidates - direct_capacity
    elif max_peer_ratio == 0:
        peer_limit = 0
    else:
        peer_limit = min(
            max_candidates - direct_capacity,
            int(max_peer_ratio * Decimal(direct_capacity) / (Decimal("1") - max_peer_ratio)),
        )
    retained: list[PointInTimeEvidence] = []
    retained_peers = 0
    for item in eligible:
        if item.is_peer_context:
            if retained_peers >= peer_limit:
                counters["peer_cap"] += 1
                continue
            retained_peers += 1
        if len(retained) >= max_candidates:
            counters["candidate_limit"] += 1
            continue
        retained.append(item)
    if retained:
        retained_peer_count = sum(item.is_peer_context for item in retained)
        if Decimal(retained_peer_count) / Decimal(len(retained)) > max_peer_ratio:
            raise RuntimeError("retained peer evidence exceeds the configured ratio")
    audit = PointInTimeEvidenceAudit(
        input_count=len(supplied),
        retained_count=len(retained),
        future_count=counters["future"],
        archive_late_count=counters["archive_late"],
        anchor_duplicate_count=counters["anchor_duplicate"],
        duplicate_count=counters["duplicate"],
        unrelated_count=counters["unrelated"],
        peer_cap_count=counters["peer_cap"],
        candidate_limit_count=counters["candidate_limit"],
    )
    return PointInTimeEvidenceSelection(
        event_id=event.event_id,
        decision_at=event.decision_at,
        candidates=retained,
        audit=audit,
    )


def compute_market_residual_impact_label(
    event: PointInTimeEventAnchor,
    stock_bars: Iterable[Bar],
    benchmark_bars: Iterable[Bar],
    *,
    horizon_days: int,
    as_of: datetime,
    lookback_days: int = 252,
    embargo_days: int = 20,
    min_fit_samples: int = 120,
) -> MarketResidualImpactLabel | None:
    """Build a matured, standardized residual label with a causal market fit."""

    _require_aware(as_of, "as_of")
    if horizon_days < 1 or lookback_days < 1 or embargo_days < 0 or min_fit_samples < 3:
        raise ValueError("invalid market residual label parameters")
    stock = {bar.ts: bar for bar in stock_bars if bar.close > 0}
    market = {bar.ts: bar for bar in benchmark_bars if bar.close > 0}
    timestamps = sorted(stock.keys() & market.keys())
    if event.decision_at not in stock or event.decision_at not in market:
        raise ValueError("event decision_at must match an aligned stock and benchmark bar")
    origin_index = timestamps.index(event.decision_at)
    target_index = origin_index + horizon_days
    if target_index >= len(timestamps):
        return None
    target_at = timestamps[target_index]
    if target_at > as_of:
        return None
    fit_end_index = origin_index - embargo_days
    if fit_end_index < horizon_days:
        raise ValueError("insufficient history before the embargo window")
    first_end_index = max(horizon_days, fit_end_index - lookback_days + 1)
    end_indices = list(range(first_end_index, fit_end_index + 1))
    if len(end_indices) < min_fit_samples:
        raise ValueError("insufficient market-model fit samples")

    stock_returns = np.asarray(
        [
            _period_return(
                stock[timestamps[index - horizon_days]].close, stock[timestamps[index]].close
            )
            for index in end_indices
        ],
        dtype=np.float64,
    )
    market_returns = np.asarray(
        [
            _period_return(
                market[timestamps[index - horizon_days]].close,
                market[timestamps[index]].close,
            )
            for index in end_indices
        ],
        dtype=np.float64,
    )
    design = np.column_stack((np.ones(len(end_indices), dtype=np.float64), market_returns))
    coefficients, *_unused = np.linalg.lstsq(design, stock_returns, rcond=None)
    alpha, beta = coefficients
    fit_residuals = stock_returns - design @ coefficients
    degrees_of_freedom = len(end_indices) - 2
    sigma = float(np.sqrt(np.sum(fit_residuals**2) / degrees_of_freedom))
    if not np.isfinite(sigma) or sigma <= 1e-12:
        raise ValueError("market-model residual sigma is not usable")

    stock_return = _period_return(stock[timestamps[origin_index]].close, stock[target_at].close)
    benchmark_return = _period_return(
        market[timestamps[origin_index]].close,
        market[target_at].close,
    )
    residual = stock_return - (float(alpha) + float(beta) * benchmark_return)
    standardized = residual / sigma
    label: ImpactLabel = 1 if standardized > 1 else -1 if standardized < -1 else 0
    return MarketResidualImpactLabel(
        event_id=event.event_id,
        symbol=event.symbol,
        horizon_days=horizon_days,
        origin_at=event.decision_at,
        target_at=target_at,
        fit_window_end_at=timestamps[fit_end_index],
        fit_sample_count=len(end_indices),
        alpha=_decimal(alpha),
        beta=_decimal(beta),
        residual_sigma=_decimal(sigma),
        stock_return=_decimal(stock_return),
        benchmark_return=_decimal(benchmark_return),
        residual_return=_decimal(residual),
        standardized_residual=_decimal(standardized),
        label=label,
    )


def update_source_memory(
    cells: Mapping[SourceMemoryKey, SourceMemoryCell],
    feedback: SourceMemoryFeedback,
    evidence_by_id: Mapping[str, PointInTimeEvidence],
    *,
    valid_evidence_ids: Iterable[str],
    as_of: datetime,
    class_proportions: Mapping[int, Decimal] | None = None,
) -> tuple[dict[SourceMemoryKey, SourceMemoryCell], SourceMemoryUpdateResult]:
    """Apply matured feedback to copied cells; invalid citations never update memory."""

    _require_aware(as_of, "as_of")
    copied = {key: cell.model_copy(deep=True) for key, cell in cells.items()}
    class_weight = _class_weight(feedback.actual_label, class_proportions)
    if feedback.target_at > as_of:
        return copied, SourceMemoryUpdateResult(
            applied=False,
            reason="target_not_matured",
            class_weight=class_weight,
        )
    allowed = set(valid_evidence_ids)
    cited = list(dict.fromkeys(feedback.cited_evidence_ids))
    valid = [
        evidence_id
        for evidence_id in cited
        if evidence_id in allowed and evidence_id in evidence_by_id
    ]
    ignored = [evidence_id for evidence_id in cited if evidence_id not in valid]
    families = sorted({evidence_by_id[evidence_id].source_family for evidence_id in valid})
    if not families:
        return copied, SourceMemoryUpdateResult(
            applied=False,
            reason="no_valid_citations",
            valid_evidence_ids=valid,
            ignored_evidence_ids=ignored,
            class_weight=class_weight,
        )
    credit = class_weight / Decimal(len(families))
    correct = feedback.predicted_label == feedback.actual_label
    updated: list[SourceMemoryCell] = []
    for family in families:
        key: SourceMemoryKey = (family, feedback.event_type, feedback.horizon_days)
        current = copied.get(
            key,
            SourceMemoryCell(
                source_family=family,
                event_type=feedback.event_type,
                horizon_days=feedback.horizon_days,
            ),
        )
        values = (
            {"positive_mass": current.positive_mass + credit}
            if correct
            else {"negative_mass": current.negative_mass + credit}
        )
        revised = current.model_copy(update=values)
        copied[key] = revised
        updated.append(revised)
    return copied, SourceMemoryUpdateResult(
        applied=True,
        reason="feedback_applied",
        updated_cells=updated,
        valid_evidence_ids=valid,
        ignored_evidence_ids=ignored,
        class_weight=class_weight,
    )


def rerank_with_source_memory(
    evidence: Iterable[PointInTimeEvidence],
    cells: Mapping[SourceMemoryKey, SourceMemoryCell],
    *,
    event_type: EventType,
    horizon_days: int,
    config: SourceMemoryConfig | None = None,
) -> list[SourceMemoryRerankItem]:
    """Apply a bounded memory term and return only the reader-sized evidence set."""

    selected_config = config or SourceMemoryConfig()
    ranked: list[SourceMemoryRerankItem] = []
    for item in evidence:
        key: SourceMemoryKey = (item.source_family, event_type, horizon_days)
        cell = cells.get(
            key,
            SourceMemoryCell(
                source_family=item.source_family,
                event_type=event_type,
                horizon_days=horizon_days,
            ),
        )
        sample_mass = cell.positive_mass + cell.negative_mass
        utility = (cell.positive_mass + Decimal("1")) / (sample_mass + Decimal("2"))
        reliability = sample_mass / (sample_mass + selected_config.shrinkage_kappa)
        shrunk = reliability * (utility - Decimal("0.5"))
        clipped = max(
            -selected_config.utility_clip,
            min(selected_config.utility_clip, shrunk),
        )
        adjustment = selected_config.rerank_lambda * clipped
        ranked.append(
            SourceMemoryRerankItem(
                evidence=item,
                posterior_utility=_metric(utility),
                reliability=_metric(reliability),
                memory_adjustment=_metric(adjustment),
                reranked_score=_metric(item.static_relevance + adjustment),
            )
        )
    ranked.sort(key=lambda item: (-item.reranked_score, item.evidence.evidence_id))
    return ranked[: selected_config.max_reader_evidence]


def _class_weight(
    actual_label: ImpactLabel,
    class_proportions: Mapping[int, Decimal] | None,
) -> Decimal:
    if class_proportions is None:
        return Decimal("1")
    if set(class_proportions) != {-1, 0, 1}:
        raise ValueError("class proportions must contain -1, 0, and 1")
    if any(value <= 0 or value > 1 for value in class_proportions.values()):
        raise ValueError("class proportions must be positive probabilities")
    if sum(class_proportions.values(), Decimal("0")) != Decimal("1"):
        raise ValueError("class proportions must sum to 1")
    proportion = class_proportions.get(actual_label)
    if proportion is None or proportion <= 0 or proportion > 1:
        raise ValueError("class proportions must contain a positive probability for the label")
    return Decimal("1") / (Decimal("3") * proportion)


def _evidence_sort_key(item: PointInTimeEvidence) -> tuple[Decimal, datetime, str]:
    return (-item.static_relevance, item.available_at, item.evidence_id)


def _normalized_url(value: str) -> str:
    parts = urlsplit(value.strip())
    query = [
        (key, item)
        for key, item in parse_qsl(parts.query, keep_blank_values=True)
        if not key.casefold().startswith("utm_") and key.casefold() not in _TRACKING_QUERY_KEYS
    ]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(
        (parts.scheme.casefold(), parts.netloc.casefold(), path, urlencode(sorted(query)), "")
    )


def _normalized_text(value: str) -> str:
    return re.sub(r"[^\w]+", "", value.casefold(), flags=re.UNICODE)


def _period_return(start: Decimal, end: Decimal) -> float:
    if start <= 0:
        raise ValueError("return start price must be positive")
    return float(end / start - Decimal("1"))


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _decimal(value: float | np.floating) -> Decimal:
    return Decimal(str(float(value))).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


def _metric(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
