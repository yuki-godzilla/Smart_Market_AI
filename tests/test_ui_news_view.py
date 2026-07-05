from datetime import UTC, datetime
from types import SimpleNamespace

from backend.news import (
    NewsDashboardSnapshot,
    NewsHeadlineCard,
    build_demo_news_dashboard_snapshot,
)
from ui.views import news as news_module
from ui.views.news import (
    _news_ticker_html,
    news_card_market_proxy_symbols,
    news_card_symbol_handoff_groups,
    news_dashboard_cockpit_href,
    news_dashboard_handoff_symbols,
    news_dashboard_heatmap_frame,
    news_dashboard_heatmap_group_kind,
    news_dashboard_heatmap_group_kind_label,
    news_dashboard_lane_card_items,
    news_dashboard_stock_heatmap_groups,
    news_dashboard_stock_heatmap_html,
    news_dashboard_unique_headline_count,
    news_headline_card_html,
    news_symbol_handoff_label,
)


def test_news_dashboard_heatmap_frame_is_user_facing():
    snapshot = build_demo_news_dashboard_snapshot(
        now=datetime(2026, 6, 4, 10, 0, tzinfo=UTC),
    )
    frame = news_dashboard_heatmap_frame(snapshot)

    assert not frame.empty
    assert {
        "投資カテゴリ",
        "分野",
        "加熱度",
        "市場指標",
        "値動き",
        "値動き表示",
        "取引量",
        "取引量目安",
        "ニュース件数",
        "主な材料",
    }.issubset(set(frame.columns))
    assert frame["加熱度"].min() >= 0
    assert frame["値動き"].notna().any()
    assert frame["取引量"].notna().any()
    assert set(frame["市場指標"]) == {"市場データ"}


def test_news_dashboard_heatmap_frame_accepts_legacy_cells_without_market_metrics():
    snapshot = SimpleNamespace(
        heatmap_cells=[
            SimpleNamespace(
                category="旧キャッシュ",
                region="日本",
                heat_score=2.5,
                news_count=3,
                risk_count=1,
                positive_count=1,
                official_source_count=0,
                freshness_ratio=0.5,
                dominant_material_type="risk",
            )
        ]
    )

    frame = news_dashboard_heatmap_frame(snapshot)

    assert frame.loc[0, "投資カテゴリ"] == "旧キャッシュ"
    assert frame.loc[0, "市場指標"] == "ニュース代理"
    assert frame.loc[0, "値動きスコア"] < 0
    assert frame.loc[0, "取引量スコア"] > 1.0
    assert frame.loc[0, "値動き表示"].startswith("材料")


def test_news_dashboard_stock_heatmap_html_uses_classified_category_tiles():
    snapshot = build_demo_news_dashboard_snapshot(
        now=datetime(2026, 6, 4, 10, 0, tzinfo=UTC),
    )
    groups = news_dashboard_stock_heatmap_groups(snapshot)
    html_text = news_dashboard_stock_heatmap_html(snapshot)

    assert groups
    assert groups[0]["tiles"]
    assert "investment-stock-heatmap-board" in html_text
    assert "investment-stock-heatmap-group" in html_text
    assert "investment-stock-heatmap-group-main" in html_text
    assert "investment-stock-heatmap-group-score" in html_text
    assert "investment-stock-heatmap-group-sub" in html_text
    assert "investment-stock-heatmap-group-badge" in html_text
    assert "investment-stock-heatmap-group-kind" in html_text
    assert "investment-stock-heatmap-group-trend" in html_text
    assert "investment-stock-heatmap-tile" in html_text
    assert "8カテゴリ" in html_text
    assert "8セクター" not in html_text
    assert "64銘柄タイル" in html_text
    assert "色は値動き、面積は注目度の目安" in html_text
    assert "investment-stock-heatmap-click" in html_text
    assert '<a class="investment-stock-heatmap-tile' in html_text
    assert 'href="?smai_page=cockpit&amp;smai_symbol=NVDA"' in html_text
    assert 'target="_self"' in html_text
    assert 'target="_blank"' not in html_text
    assert "count-8" in html_text
    assert "NVDA" in html_text
    assert "TSM" in html_text
    assert "NVDA / NVIDIA" in html_text
    assert "6857.T / アドバンテスト" in html_text
    assert html_text.index("investment-stock-heatmap-name") < html_text.index(
        "investment-stock-heatmap-symbol"
    )
    assert "未取得" not in html_text


def test_news_dashboard_heatmap_group_kind_labels_cover_mixed_category_axes():
    expected = {
        "日本株": ("market", "市場"),
        "米国株": ("market", "市場"),
        "ETF": ("asset_class", "資産クラス"),
        "半導体・AI": ("theme", "テーマ"),
        "為替・金利": ("macro", "マクロ"),
        "決算・業績修正": ("event", "イベント"),
    }

    for category, (kind, label) in expected.items():
        assert news_dashboard_heatmap_group_kind(category) == kind
        assert news_dashboard_heatmap_group_kind_label(category) == label


def test_news_dashboard_stock_heatmap_tiles_use_dynamic_area_factors():
    snapshot = build_demo_news_dashboard_snapshot(
        now=datetime(2026, 6, 4, 10, 0, tzinfo=UTC),
    )

    groups = news_dashboard_stock_heatmap_groups(snapshot)
    tiles = [tile for group in groups for tile in group["tiles"]]
    spans = {(tile["span_cols"], tile["span_rows"]) for tile in tiles}
    html_text = news_dashboard_stock_heatmap_html(snapshot)

    assert len(spans) >= 3
    assert all(tile["area_score"] > 0 for tile in tiles)
    assert all("注目" in tile["factors_label"] for tile in tiles)
    assert all(not tile["factors_label"].startswith(tile["change_label"]) for tile in tiles)
    assert all(tile["color_style"].startswith("--heatmap-tile-bg") for tile in tiles)
    assert "investment-stock-heatmap-factors" in html_text
    assert "面積根拠:" in html_text
    assert "investment-stock-heatmap-group-trend" in html_text
    assert 'style="grid-column: span ' in html_text


def test_news_dashboard_stock_heatmap_small_tiles_only_show_symbol_and_change():
    snapshot = build_demo_news_dashboard_snapshot(
        now=datetime(2026, 6, 4, 10, 0, tzinfo=UTC),
    )

    groups = news_dashboard_stock_heatmap_groups(snapshot)
    small_tile = next(
        tile for group in groups for tile in group["tiles"] if tile["size"] in {"compact", "minor"}
    )
    html_text = news_module._stock_heatmap_tile_html(small_tile)

    assert "text-safe" in html_text
    assert f'>{small_tile["symbol"]}</span>' in html_text
    assert str(small_tile["change_label"]) in html_text
    assert "investment-stock-heatmap-symbol" not in html_text
    assert "investment-stock-heatmap-factors" not in html_text
    assert "面積根拠:" in html_text
    assert "aria-label=" in html_text


def test_news_dashboard_stock_heatmap_large_tile_keeps_one_auxiliary_line():
    snapshot = build_demo_news_dashboard_snapshot(
        now=datetime(2026, 6, 4, 10, 0, tzinfo=UTC),
    )

    groups = news_dashboard_stock_heatmap_groups(snapshot)
    large_tile = next(
        tile for group in groups for tile in group["tiles"] if tile["size"] in {"hero", "major"}
    )
    html_text = news_module._stock_heatmap_tile_html(large_tile)

    assert html_text.count("investment-stock-heatmap-factors") == 1
    assert str(large_tile["factors_label"]) in html_text


def test_news_dashboard_cockpit_href_normalizes_symbol_for_same_app_navigation():
    news_module.st.session_state.clear()
    assert news_dashboard_cockpit_href(" nvda ") == "?smai_page=cockpit&smai_symbol=NVDA"
    assert news_dashboard_cockpit_href("9432.t") == "?smai_page=cockpit&smai_symbol=9432.T"


def test_news_dashboard_cockpit_href_includes_safe_current_user(monkeypatch):
    session_state = {"smai_current_user_id": "local_user"}
    monkeypatch.setattr(news_module.st, "session_state", session_state)

    assert news_dashboard_cockpit_href(" nvda ") == (
        "?smai_start_profile=local_user&smai_page=cockpit&smai_symbol=NVDA"
    )

    session_state["smai_current_user_id"] = "../unsafe"
    assert news_dashboard_cockpit_href("9432.t") == "?smai_page=cockpit&smai_symbol=9432.T"


def test_news_headline_card_html_keeps_link_safe_and_hides_raw_url():
    snapshot = build_demo_news_dashboard_snapshot(
        now=datetime(2026, 6, 4, 10, 0, tzinfo=UTC),
    )
    card = snapshot.stream_headlines[0]
    html_text = news_headline_card_html(card, compact=True)

    assert 'target="_blank"' in html_text
    assert 'rel="noopener noreferrer"' in html_text
    assert "元記事を見る" in html_text
    assert card.url is not None
    assert card.url not in html_text.replace(f'href="{card.url}"', "")
    assert "銘柄コックピット" not in html_text
    assert html_text.count("<li>") == 1


def test_news_ticker_html_uses_paged_unique_headline_board():
    cards = [
        NewsHeadlineCard(
            title="長い市場ニュース見出しを折り返して表示できるようにするテスト",
            source_type="news",
            category="地政学・マクロリスク",
            material_type="risk",
        ),
        NewsHeadlineCard(
            title="半導体ニュース",
            source_type="news",
            category="半導体・AI",
            material_type="theme",
        ),
    ]

    html_text = _news_ticker_html(cards)

    assert html_text.count("investment-news-ticker-item") == 2
    assert "investment-news-board-page--0" in html_text
    assert "investment-news-board-nav" not in html_text
    assert "investment-news-ticker-title" in html_text
    assert "長い市場ニュース見出しを折り返して表示できるようにするテスト" in html_text


def test_news_ticker_html_groups_four_items_per_page_without_duplicates():
    cards = [
        NewsHeadlineCard(
            title=f"ニュース{index}",
            source_type="news",
            category="日本株",
            material_type="theme",
        )
        for index in range(5)
    ]

    html_text = _news_ticker_html(cards)

    assert html_text.count('class="investment-news-board-page ') == 2
    assert html_text.count("investment-news-ticker-item") == 5
    assert "investment-news-board-page-1" in html_text
    assert "investment-news-board-cycle" in html_text


def test_news_dashboard_handoff_symbols_are_unique_in_display_order():
    snapshot = build_demo_news_dashboard_snapshot(
        now=datetime(2026, 6, 4, 10, 0, tzinfo=UTC),
    )
    symbols = news_dashboard_handoff_symbols(snapshot)

    assert symbols
    assert len(symbols) == len(set(symbols))
    assert "NVDA" in symbols


def test_news_dashboard_handoff_symbols_include_inferred_after_direct():
    snapshot = NewsDashboardSnapshot(
        generated_at=datetime(2026, 6, 4, 10, 0, tzinfo=UTC),
        stream_headlines=[
            NewsHeadlineCard(
                title="Chip supply pressure continues",
                source_type="news",
                category="semiconductors",
                material_type="theme",
                related_symbols=["TSM"],
                inferred_symbols=["NVDA", "AMD"],
            )
        ],
    )

    assert news_dashboard_handoff_symbols(snapshot) == ["TSM", "NVDA", "AMD"]


def test_news_card_symbol_handoff_groups_prioritize_direct_and_fill_inferred():
    card = NewsHeadlineCard(
        title="Multiple company mentions",
        source_type="news",
        category="semiconductors",
        material_type="theme",
        related_symbols=["NVDA", "TSM", "ASML", "AMD", "AVGO"],
        inferred_symbols=["QQQ", "SPY", "6857.T", "8035.T"],
    )

    groups = news_card_symbol_handoff_groups(card)

    assert groups == [
        ("本文に出た銘柄", ["NVDA", "TSM", "ASML", "AMD", "AVGO"]),
        ("SMAI推測候補", ["QQQ", "SPY", "6857.T"]),
    ]


def test_news_card_symbol_handoff_groups_keep_direct_until_high_count():
    card = NewsHeadlineCard(
        title="Many direct company mentions",
        source_type="news",
        category="semiconductors",
        material_type="theme",
        related_symbols=[
            "NVDA",
            "TSM",
            "ASML",
            "AMD",
            "AVGO",
            "AAPL",
            "MSFT",
            "AMZN",
            "7203.T",
        ],
        inferred_symbols=["QQQ", "SPY"],
    )

    groups = news_card_symbol_handoff_groups(card)

    assert groups == [
        (
            "本文に出た銘柄",
            ["NVDA", "TSM", "ASML", "AMD", "AVGO", "AAPL", "MSFT", "AMZN"],
        )
    ]


def test_news_card_market_proxy_symbols_stay_out_of_cockpit_handoff_groups():
    card = NewsHeadlineCard(
        title="Rates and FX summary",
        source_type="news",
        category="為替・金利",
        material_type="macro",
        related_symbols=["JPM"],
        inferred_symbols=["BAC"],
        macro_proxy_symbols=["TLT", "SPY", "QQQ", "USDJPY", "US10Y", "JPM"],
    )

    assert news_card_market_proxy_symbols(card) == ["TLT", "SPY", "QQQ", "USDJPY", "US10Y"]
    assert news_card_symbol_handoff_groups(card) == [
        ("本文に出た銘柄", ["JPM"]),
        ("SMAI推測候補", ["BAC"]),
    ]


def test_news_dashboard_lane_card_items_keep_three_column_grid_reasonable():
    snapshot = build_demo_news_dashboard_snapshot(
        now=datetime(2026, 6, 4, 10, 0, tzinfo=UTC),
    )
    items = news_dashboard_lane_card_items(snapshot)

    assert len(items) == 5
    assert all(card.title for _, _, _, card in items)
    assert len({category for _, _, category, _ in items}) == 5
    assert not {card.title for _, _, _, card in items}.intersection(
        {card.title for card in snapshot.stream_headlines[:3]}
    )


def test_news_dashboard_lane_card_items_can_include_top_headlines_when_requested():
    snapshot = build_demo_news_dashboard_snapshot(
        now=datetime(2026, 6, 4, 10, 0, tzinfo=UTC),
    )
    items = news_dashboard_lane_card_items(snapshot, exclude_top_headlines=0)

    assert len(items) == 8


def test_news_dashboard_unique_headline_count_deduplicates_lanes():
    snapshot = build_demo_news_dashboard_snapshot(
        now=datetime(2026, 6, 4, 10, 0, tzinfo=UTC),
    )

    assert len(snapshot.stream_headlines) == 8
    assert sum(len(lane.headlines) for lane in snapshot.category_lanes) == 8
    assert news_dashboard_unique_headline_count(snapshot) == 8


def test_news_symbol_handoff_label_includes_known_company_name(monkeypatch):
    monkeypatch.setattr(
        "ui.views.news.symbol_name",
        lambda symbol: "NVIDIA Corporation" if symbol == "NVDA" else None,
    )

    assert news_symbol_handoff_label("nvda") == "NVDA / NVIDIA Corporation"


def test_news_symbol_handoff_label_falls_back_when_name_lookup_fails(monkeypatch):
    def raise_permission_error(symbol: str) -> str | None:
        raise PermissionError(symbol)

    monkeypatch.setattr("ui.views.news.symbol_name", raise_permission_error)

    assert news_symbol_handoff_label("7203.T") == "7203.T"
