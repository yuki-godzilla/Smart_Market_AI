from __future__ import annotations

from datetime import UTC, datetime, timedelta

from backend.notifications.marketdata_measurements import (
    FAVORITE_DAILY_MAX_AGE,
    FAVORITE_MOVE_MAX_AGE,
    market_data_measurement_from_snapshot,
    select_favorite_daily_measurements,
    select_favorite_move_measurements,
)


def _snapshot(
    *,
    change: object = 5.4,
    price: object | None = None,
    observed_at: datetime | None = None,
    status: str = "ok",
) -> dict[str, object]:
    observation = observed_at or datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    return {
        "status": status,
        "price": price,
        "price_change_1d": change,
        "last_price_at": observation.isoformat(),
        "last_snapshot_at": observation.isoformat(),
        "source": "manual_watchlist_refresh",
    }


def test_marketdata_measurement_requires_an_ok_finite_timestamped_snapshot() -> None:
    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)

    measurement = market_data_measurement_from_snapshot("nvda", _snapshot(observed_at=now))

    assert measurement is not None
    assert measurement.symbol == "NVDA"
    assert measurement.change_1d_pct == 5.4
    assert (
        market_data_measurement_from_snapshot(
            "NVDA", _snapshot(change=None, price=120.5, observed_at=now)
        )
        is not None
    )
    assert market_data_measurement_from_snapshot("NVDA", _snapshot(change="nan")) is None
    assert market_data_measurement_from_snapshot("NVDA", _snapshot(status="failed")) is None
    assert (
        market_data_measurement_from_snapshot(
            "NVDA", {"status": "ok", "price_change_1d": 5.4, "last_price_at": "invalid"}
        )
        is None
    )


def test_measured_favorite_moves_require_fresh_material_data_and_are_order_stable() -> None:
    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    snapshots = {
        "NVDA": _snapshot(change=5.4, observed_at=now),
        "TSLA": _snapshot(change=-6.1, observed_at=now - timedelta(minutes=30)),
        "OLD": _snapshot(
            change=9.0, observed_at=now - FAVORITE_MOVE_MAX_AGE - timedelta(seconds=1)
        ),
        "BAD": _snapshot(change=7.0, observed_at=now, status="failed"),
    }

    result = select_favorite_move_measurements(set(snapshots), snapshots, now=now)
    reversed_result = select_favorite_move_measurements(
        set(reversed(tuple(snapshots))), dict(reversed(tuple(snapshots.items()))), now=now
    )

    assert [(item.symbol, item.change_1d_pct) for item in result.moves] == [
        ("TSLA", -6.1),
        ("NVDA", 5.4),
    ]
    assert result.eligible_count == 2
    assert result.dedupe_token == reversed_result.dedupe_token


def test_measured_favorite_moves_report_safe_skip_reasons() -> None:
    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)

    assert select_favorite_move_measurements(set(), {}, now=now).reason == "no_favorites"
    assert (
        select_favorite_move_measurements(
            {"NVDA"}, {"NVDA": _snapshot(observed_at=now - timedelta(hours=2))}, now=now
        ).reason
        == "no_fresh_marketdata_measurement"
    )
    assert (
        select_favorite_move_measurements(
            {"NVDA"}, {"NVDA": _snapshot(change=1.0, observed_at=now)}, now=now
        ).reason
        == "no_material_favorite_move"
    )


def test_measured_favorite_daily_coverage_accepts_price_or_change_and_skips_all_stale() -> None:
    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    snapshots = {
        "NVDA": _snapshot(price=120.5, change=None, observed_at=now),
        "7203.T": _snapshot(change=1.2, observed_at=now - timedelta(hours=24)),
        "OLD": _snapshot(
            price=99.0,
            observed_at=now - FAVORITE_DAILY_MAX_AGE - timedelta(seconds=1),
        ),
        "BAD": _snapshot(price=10.0, observed_at=now, status="failed"),
    }

    result = select_favorite_daily_measurements(set(snapshots), snapshots, now=now)

    assert result.favorite_count == 4
    assert result.coverage_count == 2
    assert [item.symbol for item in result.measurements] == ["7203.T", "NVDA"]
    assert (
        select_favorite_daily_measurements({"OLD"}, {"OLD": snapshots["OLD"]}, now=now).reason
        == "no_fresh_marketdata_measurement"
    )
