from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from backend.core.data_contracts import Bar, Symbol
from backend.news import (
    NewsCategoryLane,
    NewsDashboardSnapshot,
    NewsHeadlineCard,
    RadarCandidate,
    RadarCandidateProvenance,
    build_radar_market_snapshot,
)
from backend.news.radar_market import RADAR_MARKET_MAX_SYMBOLS, radar_market_candidates
from ui.views.news import (
    _radar_market_news_context_by_category,
    radar_market_heatmap_display_groups,
    radar_market_heatmap_groups,
    radar_market_heatmap_html,
    radar_market_snapshot_needs_refresh,
    radar_market_treemap_rectangles,
)


def _candidate(
    symbol: str,
    *,
    provenance: RadarCandidateProvenance = "direct_mention",
    investigation: bool = True,
    categories: list[str] | None = None,
) -> RadarCandidate:
    return RadarCandidate(
        candidate_id=f"radar:{provenance}:{symbol}",
        symbol=symbol,
        display_name=f"Name {symbol}",
        provenance=provenance,
        categories=categories or ["半導体・AI"],
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


def test_radar_market_candidate_request_keeps_the_wider_bounded_set():
    candidates = [_candidate(f"S{index:02d}") for index in range(31)]

    selected = radar_market_candidates(candidates)

    assert RADAR_MARKET_MAX_SYMBOLS == 30
    assert len(selected) == 30
    expected_symbols = [f"S{index:02d}" for index in range(30)]
    assert [candidate.symbol for candidate in selected] == expected_symbols


def test_radar_market_candidate_request_keeps_a_less_common_news_category_at_the_cap():
    candidates = [
        *[_candidate(f"TECH{index:02d}", categories=["半導体・AI"]) for index in range(30)],
        _candidate("ENERGY", categories=["エネルギー"]),
    ]

    selected = radar_market_candidates(candidates)

    assert len(selected) == RADAR_MARKET_MAX_SYMBOLS
    assert "ENERGY" in {candidate.symbol for candidate in selected}
    assert (
        len({candidate.symbol for candidate in selected if candidate.symbol.startswith("TECH")})
        == 29
    )


def test_radar_market_snapshot_carries_sector_industry_and_pickup_context():
    candidate = _candidate("AAA")
    candidate.confirmation_priority = 88
    candidate.watchlist_match = True
    snapshot = build_radar_market_snapshot(
        [candidate],
        _bars("AAA", ["100", "103"]),
        provider="fixture",
        lookback_sessions=1,
        symbol_metadata_by_symbol={
            "aaa": {
                "sector": "technology",
                "industry_gics": "Semiconductors",
            }
        },
    )

    tile = snapshot.tiles[0]
    assert tile.sector == "technology"
    assert tile.industry == "Semiconductors"
    assert tile.news_categories == ["半導体・AI"]
    assert tile.confirmation_priority == 88
    assert tile.watchlist_match is True


def test_radar_market_groups_tiles_by_sector_industry_and_each_news_category():
    candidate = _candidate("AAA")
    candidate.categories = ["半導体・AI", "決算・業績修正"]
    snapshot = build_radar_market_snapshot(
        [candidate],
        _bars("AAA", ["100", "103"]),
        provider="fixture",
        lookback_sessions=1,
        symbol_metadata_by_symbol={"AAA": {"sector": "technology", "tse_33_industry": "電気機器"}},
    )

    assert [label for label, _ in radar_market_heatmap_groups(snapshot, grouping="sector")] == [
        "テクノロジー"
    ]
    assert [label for label, _ in radar_market_heatmap_groups(snapshot, grouping="industry")] == [
        "電気機器"
    ]
    assert {label for label, _ in radar_market_heatmap_groups(snapshot, grouping="news")} == {
        "半導体・AI",
        "決算・業績修正",
    }


def test_radar_market_display_groups_keep_sparse_sector_cards_distinct_for_broader_comparison():
    candidates = [_candidate(symbol) for symbol in ("AAA", "AAB", "AAC", "BBB", "CCC", "DDD")]
    bars = [
        bar
        for index, candidate in enumerate(candidates)
        for bar in _bars(candidate.symbol, ["100", str(102 + index)])
    ]
    snapshot = build_radar_market_snapshot(
        candidates,
        bars,
        provider="fixture",
        lookback_sessions=1,
        symbol_metadata_by_symbol={
            "AAA": {"sector": "technology"},
            "AAB": {"sector": "technology"},
            "AAC": {"sector": "technology"},
            "BBB": {"sector": "financial"},
            "CCC": {"sector": "real_estate"},
            "DDD": {"sector": "consumer"},
        },
    )

    display_groups = radar_market_heatmap_display_groups(snapshot, grouping="sector")
    display_by_label = {
        label: (tiles, grouped_labels) for label, tiles, grouped_labels in display_groups
    }
    html_text = radar_market_heatmap_html(snapshot, grouping="sector")

    assert len(display_by_label["テクノロジー"][0]) == 3
    assert [tile.symbol for tile in display_by_label["消費財・サービス"][0]] == ["DDD"]
    assert [tile.symbol for tile in display_by_label["不動産"][0]] == ["CCC"]
    assert [tile.symbol for tile in display_by_label["金融"][0]] == ["BBB"]
    assert all(grouped_labels == [] for _, grouped_labels in display_by_label.values())
    assert "少数セクター" not in html_text
    assert "分類 4 · 実測 6銘柄を分類ごとに表示" in html_text


def test_radar_market_snapshot_refreshes_on_entry_when_missing_stale_or_period_changes():
    now = datetime(2026, 7, 3, 10, 0, tzinfo=UTC)
    snapshot = build_radar_market_snapshot(
        [_candidate("AAA")],
        _bars("AAA", ["100", "103"]),
        provider="fixture",
        lookback_sessions=20,
        generated_at=now - timedelta(minutes=14),
    )

    assert not radar_market_snapshot_needs_refresh(snapshot, lookback_sessions=20, now=now)
    assert radar_market_snapshot_needs_refresh(snapshot, lookback_sessions=5, now=now)
    assert radar_market_snapshot_needs_refresh(
        snapshot.model_copy(update={"generated_at": now - timedelta(minutes=15)}),
        lookback_sessions=20,
        now=now,
    )
    assert radar_market_snapshot_needs_refresh(None, lookback_sessions=20, now=now)


def test_radar_market_heatmap_keeps_area_proportional_and_shows_exact_direction():
    snapshot = build_radar_market_snapshot(
        [_candidate("AAA"), _candidate("BBB")],
        [*_bars("AAA", ["100", "108"]), *_bars("BBB", ["100", "98"])],
        provider="fixture",
        lookback_sessions=1,
    )

    rectangles = radar_market_treemap_rectangles(snapshot.tiles)
    areas = {tile.symbol: width * height for tile, _, _, width, height in rectangles}
    html_text = radar_market_heatmap_html(snapshot, grouping="news")

    assert areas["AAA"] > areas["BBB"]
    assert "+8.00%" in html_text
    assert "-2.00%" in html_text
    assert "▲ 上昇" in html_text
    assert "▼ 下落" in html_text
    assert "面積: 騰落幅" in html_text
    assert "取得元: fixture" in html_text
    assert "半導体・AI" in html_text
    assert "本文 · 根拠1件" in html_text
    assert "smai_page=cockpit" in html_text
    assert "先に確認" in html_text


def test_radar_market_treemap_uses_short_edge_to_avoid_full_width_tile_strips():
    candidates = [_candidate(symbol) for symbol in ("AAA", "BBB", "CCC", "DDD", "EEE", "FFF")]
    bars = [
        *_bars("AAA", ["100", "110"]),
        *_bars("BBB", ["100", "91"]),
        *_bars("CCC", ["100", "102"]),
        *_bars("DDD", ["100", "99.4"]),
        *_bars("EEE", ["100", "100.1"]),
        *_bars("FFF", ["100", "99.9"]),
    ]
    snapshot = build_radar_market_snapshot(
        candidates,
        bars,
        provider="fixture",
        lookback_sessions=1,
    )

    rectangles = radar_market_treemap_rectangles(snapshot.tiles)
    layout = {tile.symbol: (x, y, width, height) for tile, x, y, width, height in rectangles}
    total_area = sum(width * height for _, _, _, width, height in rectangles)

    # A wide canvas should partition the largest tiles into side-by-side
    # columns.  The previous orientation created a hard-to-scan stack of
    # full-width ribbons for this common 20-session return distribution.
    assert layout["AAA"][2] < 100.0
    assert layout["BBB"][0] > 0.0
    assert total_area == pytest.approx(100.0 * 56.0)


def test_radar_market_heatmap_marks_direction_and_value_as_one_readable_chip():
    snapshot = build_radar_market_snapshot(
        [_candidate("AAA"), _candidate("BBB")],
        [*_bars("AAA", ["100", "108"]), *_bars("BBB", ["100", "98"])],
        provider="fixture",
        lookback_sessions=1,
    )

    html_text = radar_market_heatmap_html(snapshot, grouping="news")

    assert "investment-market-heatmap-change" in html_text
    assert "investment-market-heatmap-change-direction" in html_text
    assert 'investment-market-heatmap-change-word">上昇' in html_text
    assert 'investment-market-heatmap-change-value">+8.00%' in html_text
    assert 'investment-market-heatmap-change-word">下落' in html_text
    assert 'investment-market-heatmap-change-value">-2.00%' in html_text
    assert 'title="Name AAA (AAA) · 上昇 +8.00%"' in html_text


def test_radar_market_news_groups_show_a_compact_clickable_source_card():
    candidate = _candidate("AAA")
    source_card = NewsHeadlineCard(
        title="半導体需要に関する決算ニュース",
        url="https://example.test/articles/semiconductor-results",
        source_name="Fixture News",
        source_type="news",
        published_at=datetime(2026, 7, 3, 10, 0, tzinfo=UTC),
        category="半導体・AI",
        material_type="earnings",
    )
    news_snapshot = NewsDashboardSnapshot(
        generated_at=datetime(2026, 7, 3, tzinfo=UTC),
        category_lanes=[NewsCategoryLane(category="半導体・AI", headlines=[source_card])],
    )
    market_snapshot = build_radar_market_snapshot(
        [candidate],
        _bars("AAA", ["100", "108"]),
        provider="fixture",
        lookback_sessions=1,
    )

    contexts = _radar_market_news_context_by_category(news_snapshot)
    news_html = radar_market_heatmap_html(
        market_snapshot,
        grouping="news",
        news_context_by_category=contexts,
    )
    sector_html = radar_market_heatmap_html(
        market_snapshot,
        grouping="sector",
        news_context_by_category=contexts,
    )

    assert contexts == {"半導体・AI": source_card}
    assert 'class="investment-market-news-context is-link"' in news_html
    assert 'href="https://example.test/articles/semiconductor-results"' in news_html
    assert 'target="_blank" rel="noopener noreferrer"' in news_html
    assert "根拠ニュース" in news_html
    assert "半導体需要に関する決算ニュース" in news_html
    assert "元記事を開く ↗" in news_html
    assert news_html.index("investment-market-news-context") < news_html.index(
        "investment-market-heatmap-canvas"
    )
    assert "investment-market-news-context" not in sector_html


def test_radar_market_news_group_expands_through_twelve_tiles_before_overflow():
    candidates = [_candidate(f"S{index:02d}") for index in range(10)]
    bars = [bar for index in range(10) for bar in _bars(f"S{index:02d}", ["100", str(101 + index)])]
    snapshot = build_radar_market_snapshot(
        candidates,
        bars,
        provider="fixture",
        lookback_sessions=1,
    )

    html_text = radar_market_heatmap_html(snapshot, grouping="news")

    assert "全10銘柄 · 上昇10 / 下落0" in html_text
    assert "investment-market-heatmap-group dense" in html_text
    assert html_text.count('class="investment-market-heatmap-tile ') == 10
    assert "あと" not in html_text


def test_radar_market_news_group_exposes_overflow_after_readable_dynamic_limit():
    candidates = [_candidate(f"S{index:02d}") for index in range(15)]
    bars = [bar for index in range(15) for bar in _bars(f"S{index:02d}", ["100", str(101 + index)])]
    snapshot = build_radar_market_snapshot(
        candidates,
        bars,
        provider="fixture",
        lookback_sessions=1,
    )

    html_text = radar_market_heatmap_html(snapshot, grouping="news")

    assert "表示12 / 該当15銘柄" in html_text
    assert "investment-market-heatmap-group dense" in html_text
    assert html_text.count('class="investment-market-heatmap-tile ') == 12
    assert "あと3銘柄を見る" in html_text
    assert 'class="investment-market-heatmap-overflow-item"' in html_text
