import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from backend.core.data_contracts import Bar, Symbol
from ui.favorites import FavoriteStock
from ui.watchlist_snapshots import (
    WatchlistSnapshot,
    build_watchlist_snapshot_for_symbol,
    classify_watchlist_trend,
    get_watchlist_snapshot,
    load_watchlist_snapshots,
    mark_watchlist_snapshot_failed,
    prune_snapshots_for_removed_favorites,
    remove_watchlist_snapshot,
    save_watchlist_snapshots,
    update_watchlist_snapshot_status,
    upsert_watchlist_snapshot,
)


def test_snapshot_store_round_trip_update_remove_and_prune(tmp_path):
    path = tmp_path / "watchlist_snapshots.json"
    snapshot = WatchlistSnapshot(
        symbol="7203.t",
        name="トヨタ自動車",
        price=3120.0,
        status="ok",
    )

    saved = upsert_watchlist_snapshot(snapshot, path)
    assert saved.symbol == "7203.T"
    assert get_watchlist_snapshot(" 7203.t ", path).name == "トヨタ自動車"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert payload["snapshots"]["7203.T"]["name"] == "トヨタ自動車"

    updated = upsert_watchlist_snapshot(
        WatchlistSnapshot(symbol="7203.T", ai_score=74.0),
        path,
    )
    assert updated.price == 3120.0
    assert updated.ai_score == 74.0
    assert (
        update_watchlist_snapshot_status(
            "7203.T",
            status="failed",
            error="timeout",
            path=path,
        ).price
        == 3120.0
    )

    save_watchlist_snapshots(
        {
            "7203.T": updated,
            "AAPL": WatchlistSnapshot(symbol="AAPL", price=200.0),
        },
        path,
    )
    assert prune_snapshots_for_removed_favorites({"7203.T"}, path) == 1
    assert remove_watchlist_snapshot("7203.T", path)
    assert load_watchlist_snapshots(path) == {}


def test_snapshot_store_missing_and_broken_json_are_safe(tmp_path):
    path = tmp_path / "watchlist_snapshots.json"
    assert load_watchlist_snapshots(path) == {}
    path.write_text("{broken", encoding="utf-8")
    assert load_watchlist_snapshots(path) == {}


@pytest.mark.parametrize(
    ("one_day", "five_day", "one_month", "expected"),
    [
        (1.2, 3.8, 7.4, ("up", "上昇傾向", "↗")),
        (0.1, 0.2, 0.8, ("short_up", "短期上昇", "↑")),
        (0.1, -0.2, 0.3, ("flat", "横ばい", "→")),
        (-1.4, -3.2, -5.6, ("down", "下落注意", "↘")),
        (-5.1, -1.0, -2.0, ("sharp_down", "急落警戒", "↓")),
        (None, "", float("nan"), ("missing", "未取得", "…")),
    ],
)
def test_classify_watchlist_trend(one_day, five_day, one_month, expected):
    assert (
        classify_watchlist_trend(
            price_change_1d=one_day,
            price_change_5d=five_day,
            price_change_1m=one_month,
        )
        == expected
    )


def test_build_snapshot_calculates_partial_returns_and_keeps_previous_data():
    start = datetime(2026, 5, 1, tzinfo=UTC)
    bars = [
        Bar(
            symbol=Symbol(code="AAPL", exchange="NASDAQ", raw="AAPL", currency="USD"),
            ts=start + timedelta(days=index),
            open=Decimal(str(100 + index)),
            high=Decimal(str(101 + index)),
            low=Decimal(str(99 + index)),
            close=Decimal(str(100 + index)),
            volume=1000,
            interval="1d",
            provider="mock",
        )
        for index in range(22)
    ]
    previous = WatchlistSnapshot(symbol="AAPL", ai_score=75.0, status="ok")

    snapshot = build_watchlist_snapshot_for_symbol(
        "aapl",
        favorite=FavoriteStock(symbol="AAPL", name="Apple"),
        row={
            "currency": "USD",
            "fx_rate_jpy": "150",
            "upside_score": "61",
            "downside_risk_score": "32",
        },
        bars=bars,
        previous=previous,
        now=datetime(2026, 6, 27, tzinfo=UTC),
        source="mock",
    )

    assert snapshot.price == 121.0
    assert snapshot.price_jpy == 18150.0
    assert snapshot.fx_rate_jpy == 150.0
    assert snapshot.price_change_1d == pytest.approx(0.8333, abs=0.0001)
    assert snapshot.price_change_5d == pytest.approx(4.3103, abs=0.0001)
    assert snapshot.price_change_1m == pytest.approx(19.802, abs=0.0001)
    assert snapshot.ai_score == 75.0
    assert snapshot.upside_score == 61.0
    assert snapshot.status == "ok"
    assert snapshot.trend_status == "up"

    failed = mark_watchlist_snapshot_failed(
        "AAPL",
        previous=snapshot,
        error="provider timeout",
    )
    assert failed.price == 121.0
    assert failed.status == "failed"
    assert failed.error == "provider timeout"
