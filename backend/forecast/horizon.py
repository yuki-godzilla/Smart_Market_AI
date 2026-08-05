from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from math import floor, sqrt
from typing import Literal, Sequence

from backend.core.data_contracts import Bar

MIN_FORECAST_HORIZON_DAYS = 1
TARGET_INDEPENDENT_FORECAST_WINDOWS = 12

# Compatibility surface for adapter metadata. ``range`` has constant memory and removes
# the former product-level 60-day ceiling; actual feasibility is decided from local history.
OPEN_ENDED_FORECAST_HORIZONS = range(MIN_FORECAST_HORIZON_DAYS, sys.maxsize)

ForecastHorizonBasis = Literal["observed_bars", "requested_period"]
ForecastObservationCadence = Literal["business_daily", "calendar_daily"]


@dataclass(frozen=True)
class ForecastHorizonDecision:
    """Auditable result of the deterministic acquisition-period horizon policy."""

    horizon_days: int
    basis: ForecastHorizonBasis
    cadence: ForecastObservationCadence
    observed_points: int
    expected_points: int
    coverage_ratio: Decimal
    effective_points: int
    target_independent_windows: int
    estimated_independent_windows: int
    rounding_step_days: int
    warnings: tuple[str, ...] = ()

    @property
    def summary_ja(self) -> str:
        basis_label = "取得済み価格" if self.basis == "observed_bars" else "指定取得期間"
        return (
            f"{basis_label}{self.observed_points}点、coverage "
            f"{self.coverage_ratio * Decimal('100'):.1f}%から"
            f"{self.horizon_days}営業日相当を自動選択"
        )


def determine_forecast_horizon(
    *,
    start: date,
    end: date,
    bars: Sequence[Bar] | None = None,
    target_independent_windows: int = TARGET_INDEPENDENT_FORECAST_WINDOWS,
) -> ForecastHorizonDecision:
    """Choose a stable horizon from usable observations without a fixed day ceiling.

    The policy reserves roughly ``target_independent_windows`` non-overlapping target
    windows. Observed data coverage reduces the effective history, and bucketed downward
    rounding prevents a missing or newly arrived bar from changing the horizon every day.
    """

    if end < start:
        raise ValueError("End must be on or after Start")
    if target_independent_windows < 6:
        raise ValueError("target_independent_windows must be at least 6")

    observed_dates, duplicate_count = _observed_dates(bars or (), start=start, end=end)
    if observed_dates:
        cadence = _cadence_for_dates(observed_dates)
        expected_points = _expected_observations(start, end, cadence=cadence)
        observed_points = len(observed_dates)
        basis: ForecastHorizonBasis = "observed_bars"
    else:
        cadence = "business_daily"
        expected_points = _expected_observations(start, end, cadence=cadence)
        observed_points = expected_points
        basis = "requested_period"

    expected_points = max(1, expected_points)
    observed_points = max(1, observed_points)
    raw_coverage = min(1.0, observed_points / expected_points)
    effective_points = max(1, floor(observed_points * sqrt(raw_coverage)))
    raw_horizon = max(MIN_FORECAST_HORIZON_DAYS, effective_points // target_independent_windows)
    rounding_step_days = _rounding_step(raw_horizon)
    horizon_days = max(
        MIN_FORECAST_HORIZON_DAYS,
        (raw_horizon // rounding_step_days) * rounding_step_days,
    )
    estimated_windows = max(1, effective_points // horizon_days)

    warnings: list[str] = []
    if raw_coverage < 0.80:
        warnings.append("取得期間の価格coverageが80%未満のため、予測期間を保守的に短縮しました。")
    if duplicate_count:
        warnings.append(f"同一日付の重複価格{duplicate_count}件を予測期間の算出から除外しました。")
    if effective_points < 24:
        warnings.append("取得履歴が短いため、予測期間と検証可能性は限定的です。")
    if horizon_days > 60:
        warnings.append(
            "60営業日を超える予測は固定上限外ですが、従来の20日・60日監査とは別に"
            "長期horizonとして不確実性を確認してください。"
        )

    return ForecastHorizonDecision(
        horizon_days=horizon_days,
        basis=basis,
        cadence=cadence,
        observed_points=observed_points,
        expected_points=expected_points,
        coverage_ratio=_decimal_ratio(raw_coverage),
        effective_points=effective_points,
        target_independent_windows=target_independent_windows,
        estimated_independent_windows=estimated_windows,
        rounding_step_days=rounding_step_days,
        warnings=tuple(warnings),
    )


def _observed_dates(
    bars: Sequence[Bar],
    *,
    start: date,
    end: date,
) -> tuple[tuple[date, ...], int]:
    dates = [bar.ts.date() for bar in bars if start <= bar.ts.date() <= end]
    unique_dates = tuple(sorted(set(dates)))
    return unique_dates, len(dates) - len(unique_dates)


def _cadence_for_dates(observed_dates: Sequence[date]) -> ForecastObservationCadence:
    weekend_count = sum(1 for value in observed_dates if value.weekday() >= 5)
    if weekend_count >= max(2, len(observed_dates) // 20):
        return "calendar_daily"
    return "business_daily"


def _expected_observations(
    start: date,
    end: date,
    *,
    cadence: ForecastObservationCadence,
) -> int:
    total_days = (end - start).days + 1
    if cadence == "calendar_daily":
        return total_days
    full_weeks, remainder = divmod(total_days, 7)
    business_days = full_weeks * 5
    for offset in range(remainder):
        if (start.weekday() + offset) % 7 < 5:
            business_days += 1
    return max(1, business_days)


def _rounding_step(raw_horizon: int) -> int:
    if raw_horizon < 10:
        return 1
    if raw_horizon < 60:
        return 5
    if raw_horizon < 120:
        return 10
    if raw_horizon < 260:
        return 20
    if raw_horizon < 520:
        return 40
    return 60


def _decimal_ratio(value: float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
