from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

from pydantic import Field

from backend.core.data_contracts import Bar, StrictBaseModel
from backend.news.contracts import RadarCandidate, RadarCandidateProvenance

# Keep the live request bounded, while allowing the grouped map to retain
# enough context when wide layouts distribute candidates across many sectors.
RADAR_MARKET_MAX_SYMBOLS = 30
RADAR_MARKET_LOOKBACK_SESSIONS = (1, 5, 20)
SMAI_RADAR_MARKET_REVISION = "2026-07-15-dynamic-density-v3"


class RadarMarketTile(StrictBaseModel):
    """One verified price-movement tile for the Investment Radar."""

    symbol: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    sector: str = Field(default="未分類", min_length=1)
    industry: str = Field(default="未分類", min_length=1)
    news_categories: list[str] = Field(default_factory=list)
    change_pct: float
    magnitude_pct: float = Field(ge=0.0)
    latest_close: float = Field(ge=0.0)
    as_of: datetime
    evidence_count: int = Field(default=0, ge=0)
    confirmation_priority: int = Field(default=0, ge=0, le=100)
    watchlist_match: bool = False
    provenance: RadarCandidateProvenance


class RadarMarketSnapshot(StrictBaseModel):
    """Bounded market-data result produced only after an explicit refresh."""

    generated_at: datetime
    provider: str = Field(min_length=1)
    lookback_sessions: int = Field(ge=1, le=20)
    requested_count: int = Field(ge=0)
    tiles: list[RadarMarketTile] = Field(default_factory=list)
    unavailable_symbols: list[str] = Field(default_factory=list)


def radar_market_candidates(
    candidates: Sequence[RadarCandidate],
    *,
    limit: int = RADAR_MARKET_MAX_SYMBOLS,
) -> list[RadarCandidate]:
    """Select a bounded, category-balanced set for a live price check.

    The map may display only a bounded set of price requests.  When the news
    evidence has more candidates than that cap, preserve the existing candidate
    priority inside each category while giving less-represented categories a
    chance to appear.  This keeps one high-volume news theme from consuming the
    entire sector / industry / news comparison surface.
    """

    eligible: list[RadarCandidate] = []
    seen: set[str] = set()
    for candidate in candidates:
        symbol = candidate.symbol.strip().upper()
        if (
            not candidate.is_investigation_candidate
            or candidate.provenance == "macro_proxy"
            or symbol in seen
        ):
            continue
        eligible.append(candidate)
        seen.add(symbol)
    if len(eligible) <= max(1, limit):
        return eligible

    selected: list[RadarCandidate] = []
    category_counts: dict[str, int] = {}
    remaining = list(enumerate(eligible))
    while remaining and len(selected) < max(1, limit):
        remaining_index, (_, candidate) = min(
            enumerate(remaining),
            key=lambda item: _radar_market_candidate_selection_key(
                item[1][1],
                category_counts=category_counts,
                original_index=item[1][0],
            ),
        )
        _, candidate = remaining.pop(remaining_index)
        selected.append(candidate)
        for category in _radar_market_candidate_categories(candidate):
            category_counts[category] = category_counts.get(category, 0) + 1
    return selected


def _radar_market_candidate_selection_key(
    candidate: RadarCandidate,
    *,
    category_counts: Mapping[str, int],
    original_index: int,
) -> tuple[int, int, int]:
    categories = _radar_market_candidate_categories(candidate)
    counts = [category_counts.get(category, 0) for category in categories]
    return (min(counts), sum(counts), original_index)


def _radar_market_candidate_categories(candidate: RadarCandidate) -> tuple[str, ...]:
    categories = tuple(
        dict.fromkeys(category.strip() for category in candidate.categories if category.strip())
    )
    return categories or ("その他",)


def build_radar_market_snapshot(
    candidates: Sequence[RadarCandidate],
    bars: Sequence[Bar],
    *,
    provider: str,
    lookback_sessions: int,
    generated_at: datetime | None = None,
    limit: int = RADAR_MARKET_MAX_SYMBOLS,
    symbol_metadata_by_symbol: Mapping[str, Mapping[str, object]] | None = None,
) -> RadarMarketSnapshot:
    """Build price tiles without inventing a direction for missing market data."""

    if lookback_sessions not in RADAR_MARKET_LOOKBACK_SESSIONS:
        raise ValueError("lookback_sessions must be one of 1, 5, or 20")
    selected = radar_market_candidates(candidates, limit=limit)
    bars_by_symbol: dict[str, list[Bar]] = defaultdict(list)
    for bar in bars:
        bars_by_symbol[bar.symbol.raw.strip().upper()].append(bar)
    tiles: list[RadarMarketTile] = []
    unavailable: list[str] = []
    metadata_lookup = {
        symbol.strip().upper(): metadata
        for symbol, metadata in (symbol_metadata_by_symbol or {}).items()
    }
    for candidate in selected:
        symbol = candidate.symbol.strip().upper()
        metadata = metadata_lookup.get(symbol, {})
        symbol_bars = sorted(bars_by_symbol.get(symbol, []), key=lambda item: item.ts)
        required_count = lookback_sessions + 1
        if len(symbol_bars) < required_count:
            unavailable.append(candidate.symbol)
            continue
        previous_close = float(symbol_bars[-required_count].close)
        latest = symbol_bars[-1]
        latest_close = float(latest.close)
        if previous_close <= 0:
            unavailable.append(candidate.symbol)
            continue
        change_pct = ((latest_close / previous_close) - 1.0) * 100.0
        tiles.append(
            RadarMarketTile(
                symbol=candidate.symbol,
                display_name=candidate.display_name or candidate.symbol,
                category=candidate.categories[0] if candidate.categories else "その他",
                sector=_metadata_group(metadata, "sector"),
                industry=_industry_group(metadata),
                news_categories=candidate.categories,
                change_pct=round(change_pct, 4),
                magnitude_pct=round(abs(change_pct), 4),
                latest_close=latest_close,
                as_of=latest.ts,
                evidence_count=len(candidate.evidence_ids),
                confirmation_priority=candidate.confirmation_priority,
                watchlist_match=candidate.watchlist_match,
                provenance=candidate.provenance,
            )
        )
    tiles.sort(key=lambda item: (-item.magnitude_pct, item.symbol))
    return RadarMarketSnapshot(
        generated_at=generated_at or datetime.now(UTC),
        provider=provider,
        lookback_sessions=lookback_sessions,
        requested_count=len(selected),
        tiles=tiles,
        unavailable_symbols=unavailable,
    )


def _industry_group(metadata: Mapping[str, object]) -> str:
    """Return the most specific local industry label available for grouping."""

    for key in (
        "tse_33_industry",
        "industry_gics",
        "subindustry_gics",
        "topix_17",
        "theme",
    ):
        value = _metadata_group(metadata, key, default="")
        if value:
            return value
    return _metadata_group(metadata, "sector")


def _metadata_group(
    metadata: Mapping[str, object],
    key: str,
    *,
    default: str = "未分類",
) -> str:
    value = str(metadata.get(key) or "").strip()
    return value or default
