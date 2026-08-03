"""Validated, read-only market-data measurements for notification inputs.

This module deliberately consumes the persisted Watchlist snapshot format without
importing Streamlit/UI code.  It never fetches a provider, writes a cache, or
derives Ranking, Forecast, or Score values.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Mapping

FAVORITE_MOVE_THRESHOLD_PCT = 5.0
FAVORITE_MOVE_MAX_AGE = timedelta(minutes=90)
FAVORITE_DAILY_MAX_AGE = timedelta(hours=36)


@dataclass(frozen=True, slots=True)
class MarketDataMeasurement:
    """One usable, timestamped price observation from a Watchlist snapshot."""

    symbol: str
    price: float | None
    change_1d_pct: float | None
    price_observed_at: datetime
    snapshot_recorded_at: datetime | None
    source: str | None


@dataclass(frozen=True, slots=True)
class FavoriteMoveMeasurement:
    """The price-change fields required by the material-move notification."""

    symbol: str
    change_1d_pct: float
    price_observed_at: datetime


@dataclass(frozen=True, slots=True)
class FavoriteMoveMeasurements:
    """The bounded measured moves eligible for one notification evaluation."""

    moves: tuple[FavoriteMoveMeasurement, ...]
    eligible_count: int
    reason: str = "ok"

    @property
    def dedupe_token(self) -> str | None:
        """Return a stable token for the exact set of observed material moves."""

        if not self.moves:
            return None
        components = [
            f"{item.symbol}:{item.change_1d_pct:.4f}:{item.price_observed_at.isoformat()}"
            for item in sorted(self.moves, key=lambda item: item.symbol)
        ]
        return hashlib.sha256("|".join(components).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class FavoriteDailyMeasurements:
    """Fresh market-data coverage for one user's daily Favorite report."""

    measurements: tuple[MarketDataMeasurement, ...]
    favorite_count: int
    reason: str = "ok"

    @property
    def coverage_count(self) -> int:
        return len(self.measurements)


def select_favorite_move_measurements(
    favorite_symbols: set[str],
    snapshots: Mapping[str, Mapping[str, object]],
    *,
    now: datetime,
    max_age: timedelta = FAVORITE_MOVE_MAX_AGE,
) -> FavoriteMoveMeasurements:
    """Select fresh, material favorite moves without trusting malformed snapshots."""

    if not favorite_symbols:
        return FavoriteMoveMeasurements((), 0, "no_favorites")
    current = _as_utc(now)
    measurements: list[FavoriteMoveMeasurement] = []
    fresh_count = 0
    for symbol in sorted(favorite_symbols):
        snapshot = snapshots.get(symbol)
        if snapshot is None:
            continue
        measurement = market_data_measurement_from_snapshot(symbol, snapshot)
        if measurement is None or not _is_fresh(measurement.price_observed_at, current, max_age):
            continue
        fresh_count += 1
        if (
            measurement.change_1d_pct is not None
            and abs(measurement.change_1d_pct) >= FAVORITE_MOVE_THRESHOLD_PCT
        ):
            measurements.append(
                FavoriteMoveMeasurement(
                    measurement.symbol,
                    measurement.change_1d_pct,
                    measurement.price_observed_at,
                )
            )
    if not fresh_count:
        return FavoriteMoveMeasurements((), 0, "no_fresh_marketdata_measurement")
    if not measurements:
        return FavoriteMoveMeasurements((), fresh_count, "no_material_favorite_move")
    measurements.sort(key=lambda item: (-abs(item.change_1d_pct), item.symbol))
    return FavoriteMoveMeasurements(tuple(measurements), fresh_count)


def select_favorite_daily_measurements(
    favorite_symbols: set[str],
    snapshots: Mapping[str, Mapping[str, object]],
    *,
    now: datetime,
    max_age: timedelta = FAVORITE_DAILY_MAX_AGE,
) -> FavoriteDailyMeasurements:
    """Return fresh, bounded daily-report coverage without inferring market sessions."""

    if not favorite_symbols:
        return FavoriteDailyMeasurements((), 0, "no_favorites")
    current = _as_utc(now)
    measurements: list[MarketDataMeasurement] = []
    for symbol in sorted(favorite_symbols):
        snapshot = snapshots.get(symbol)
        if snapshot is None:
            continue
        measurement = market_data_measurement_from_snapshot(symbol, snapshot)
        if measurement is not None and _is_fresh(measurement.price_observed_at, current, max_age):
            measurements.append(measurement)
    if not measurements:
        return FavoriteDailyMeasurements(
            (), len(favorite_symbols), "no_fresh_marketdata_measurement"
        )
    return FavoriteDailyMeasurements(tuple(measurements), len(favorite_symbols))


def market_data_measurement_from_snapshot(
    symbol: str,
    snapshot: Mapping[str, object],
) -> MarketDataMeasurement | None:
    """Parse the trusted minimum fields needed for a market-data notification."""

    if str(snapshot.get("status") or "").strip().casefold() != "ok":
        return None
    normalized_symbol = _normalized_symbol(symbol)
    price = _finite_float(snapshot.get("price"))
    change_1d_pct = _finite_float(snapshot.get("price_change_1d"))
    price_observed_at = _parse_timestamp(snapshot.get("last_price_at"))
    if (
        not normalized_symbol
        or (price is None and change_1d_pct is None)
        or price_observed_at is None
    ):
        return None
    source = str(snapshot.get("source") or "").strip() or None
    return MarketDataMeasurement(
        symbol=normalized_symbol,
        price=price,
        change_1d_pct=change_1d_pct,
        price_observed_at=price_observed_at,
        snapshot_recorded_at=_parse_timestamp(snapshot.get("last_snapshot_at")),
        source=source,
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _is_fresh(observed_at: datetime, now: datetime, max_age: timedelta) -> bool:
    age = now - observed_at
    return timedelta(0) <= age <= max_age


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def _normalized_symbol(value: object) -> str:
    symbol = str(value or "").strip().upper()
    return symbol[:32] if symbol else ""


def _finite_float(value: object) -> float | None:
    try:
        numeric = float(str(value))
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None
