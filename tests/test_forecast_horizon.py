from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from backend.core.data_contracts import Bar, Symbol
from backend.forecast import determine_forecast_horizon


def test_period_policy_uses_trading_observations_and_has_no_sixty_day_cap():
    one_year = determine_forecast_horizon(
        start=date(2026, 1, 1),
        end=date(2026, 12, 31),
    )
    five_years = determine_forecast_horizon(
        start=date(2021, 1, 1),
        end=date(2026, 12, 31),
    )
    twenty_years = determine_forecast_horizon(
        start=date(2007, 1, 1),
        end=date(2026, 12, 31),
    )

    assert one_year.horizon_days == 20
    assert five_years.horizon_days == 120
    assert twenty_years.horizon_days == 400
    assert five_years.horizon_days > 60
    assert twenty_years.horizon_days > five_years.horizon_days
    assert five_years.estimated_independent_windows >= 12


def test_observed_data_coverage_conservatively_shortens_horizon():
    start = date(2026, 1, 1)
    end = date(2026, 12, 31)
    complete = determine_forecast_horizon(start=start, end=end)
    sparse_bars = _weekday_bars(start, end)[::2]

    sparse = determine_forecast_horizon(start=start, end=end, bars=sparse_bars)

    assert complete.horizon_days == 20
    assert sparse.basis == "observed_bars"
    assert sparse.coverage_ratio < Decimal("0.60")
    assert sparse.horizon_days < complete.horizon_days
    assert any("coverage" in warning for warning in sparse.warnings)


def test_observed_bar_policy_deduplicates_dates_and_detects_calendar_assets():
    start = date(2026, 1, 1)
    bars = _calendar_bars(start, 120)
    bars.append(bars[-1])

    decision = determine_forecast_horizon(
        start=start,
        end=bars[-1].ts.date(),
        bars=bars,
    )

    assert decision.cadence == "calendar_daily"
    assert decision.observed_points == 120
    assert decision.horizon_days == 10
    assert any("重複価格1件" in warning for warning in decision.warnings)


def test_horizon_policy_rejects_invalid_boundaries_and_unsafe_window_count():
    with pytest.raises(ValueError, match="End"):
        determine_forecast_horizon(
            start=date(2026, 2, 1),
            end=date(2026, 1, 1),
        )
    with pytest.raises(ValueError, match="at least 6"):
        determine_forecast_horizon(
            start=date(2026, 1, 1),
            end=date(2026, 2, 1),
            target_independent_windows=5,
        )


def _weekday_bars(start: date, end: date) -> list[Bar]:
    bars: list[Bar] = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            bars.append(_bar_at(current, len(bars)))
        current += timedelta(days=1)
    return bars


def _calendar_bars(start: date, count: int) -> list[Bar]:
    return [_bar_at(start + timedelta(days=index), index) for index in range(count)]


def _bar_at(value: date, index: int) -> Bar:
    close = Decimal("100") + Decimal(index) / Decimal("10")
    return Bar(
        symbol=Symbol(raw="TEST", exchange="TEST", code="TEST", currency="USD"),
        ts=datetime(value.year, value.month, value.day, tzinfo=UTC),
        open=close,
        high=close + Decimal("1"),
        low=close - Decimal("1"),
        close=close,
        volume=Decimal("1000"),
        interval="1d",
        provider="fixture",
    )
