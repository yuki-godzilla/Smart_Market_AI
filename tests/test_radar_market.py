from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backend.core.data_contracts import Bar, Symbol
from backend.news import RadarCandidate, RadarCandidateProvenance, build_radar_market_snapshot
from ui.views.news import radar_market_heatmap_html, radar_market_treemap_rectangles


def _candidate(
    symbol: str,
    *,
    provenance: RadarCandidateProvenance = "direct_mention",
    investigation: bool = True,
) -> RadarCandidate:
    return RadarCandidate(
        candidate_id=f"radar:{provenance}:{symbol}",
        symbol=symbol,
        display_name=f"Name {symbol}",
        provenance=provenance,
        categories=["半導体・AI"],
        evidence_ids=[f"evidence-{symbol}"],
        directness=1.0,
        confirmation_priority=70,
        is_investigation_candidate=investigation,
    )


def _bars(symbol_text: str, closes: list[str]) -> list[Bar]:
    symbol = Symbol(
        raw=symbol_text,
        exchange="NASDAQ",
        code=symbol_text,
        currency="USD",
    )
    start = datetime(2026, 7, 1, tzinfo=UTC)
    return [
        Bar(
            symbol=symbol,
            ts=start + timedelta(days=index),
            open=Decimal(close),
            high=Decimal(close),
            low=Decimal(close),
            close=Decimal(close),
            volume=Decimal("1000"),
            interval="1d",
            provider="fixture",
        )
        for index, close in enumerate(closes)
    ]


def test_radar_market_snapshot_uses_verified_session_return_and_excludes_macro():
    candidates = [
        _candidate("AAA"),
        _candidate("BBB", provenance="inferred_candidate"),
        _candidate("SPY", provenance="macro_proxy", investigation=False),
    ]
    bars = [*_bars("AAA", ["100", "105"]), *_bars("BBB", ["100", "97"])]

    snapshot = build_radar_market_snapshot(
        candidates,
        bars,
        provider="fixture",
        lookback_sessions=1,
        generated_at=datetime(2026, 7, 3, tzinfo=UTC),
    )

    assert snapshot.requested_count == 2
    assert [tile.symbol for tile in snapshot.tiles] == ["AAA", "BBB"]
    assert snapshot.tiles[0].change_pct == 5.0
    assert snapshot.tiles[1].change_pct == -3.0
    assert snapshot.unavailable_symbols == []


def test_radar_market_snapshot_marks_missing_history_unavailable_without_neutral_tile():
    snapshot = build_radar_market_snapshot(
        [_candidate("AAA"), _candidate("BBB")],
        _bars("AAA", ["100", "101", "102", "103", "104", "110"]),
        provider="fixture",
        lookback_sessions=5,
    )

    assert [tile.symbol for tile in snapshot.tiles] == ["AAA"]
    assert snapshot.tiles[0].change_pct == 10.0
    assert snapshot.unavailable_symbols == ["BBB"]


def test_radar_market_heatmap_keeps_area_proportional_and_shows_exact_direction():
    snapshot = build_radar_market_snapshot(
        [_candidate("AAA"), _candidate("BBB")],
        [*_bars("AAA", ["100", "108"]), *_bars("BBB", ["100", "98"])],
        provider="fixture",
        lookback_sessions=1,
    )

    rectangles = radar_market_treemap_rectangles(snapshot.tiles)
    areas = {tile.symbol: width * height for tile, _, _, width, height in rectangles}
    html_text = radar_market_heatmap_html(snapshot)

    assert areas["AAA"] > areas["BBB"]
    assert "+8.00%" in html_text
    assert "-2.00%" in html_text
    assert "▲ 上昇" in html_text
    assert "▼ 下落" in html_text
    assert "面積: 変動の大きさ" in html_text
    assert "取得元: fixture" in html_text
