from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime

from pydantic import Field

from backend.core.data_contracts import Bar, StrictBaseModel
from backend.news.contracts import RadarCandidate, RadarCandidateProvenance

RADAR_MARKET_MAX_SYMBOLS = 24
RADAR_MARKET_LOOKBACK_SESSIONS = (1, 5, 20)


class RadarMarketTile(StrictBaseModel):
    """One verified price-movement tile for the Investment Radar."""

    symbol: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    change_pct: float
    magnitude_pct: float = Field(ge=0.0)
    latest_close: float = Field(ge=0.0)
    as_of: datetime
    evidence_count: int = Field(default=0, ge=0)
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
    """Select a bounded, stable set of symbol candidates for a live price check."""

    selected: list[RadarCandidate] = []
    seen: set[str] = set()
    for candidate in candidates:
        symbol = candidate.symbol.strip().upper()
        if (
            not candidate.is_investigation_candidate
            or candidate.provenance == "macro_proxy"
            or symbol in seen
        ):
            continue
        selected.append(candidate)
        seen.add(symbol)
        if len(selected) >= max(1, limit):
            break
    return selected


def build_radar_market_snapshot(
    candidates: Sequence[RadarCandidate],
    bars: Sequence[Bar],
    *,
    provider: str,
    lookback_sessions: int,
    generated_at: datetime | None = None,
    limit: int = RADAR_MARKET_MAX_SYMBOLS,
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
    for candidate in selected:
        symbol = candidate.symbol.strip().upper()
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
                change_pct=round(change_pct, 4),
                magnitude_pct=round(abs(change_pct), 4),
                latest_close=latest_close,
                as_of=latest.ts,
                evidence_count=len(candidate.evidence_ids),
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
