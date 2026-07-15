from datetime import UTC, datetime
from types import SimpleNamespace

import pandas as pd

from backend.news import (
    NewsDashboardSnapshot,
    NewsHeadlineCard,
    NewsHeatmapCell,
    build_demo_news_dashboard_snapshot,
    build_news_dashboard_snapshot,
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


def test_news_headline_dedupe_key_accepts_pre_publication_helper(monkeypatch):
    card = NewsHeadlineCard(
        title="Streamlit partial reload",
        source_type="news",
        category="半導体・AI",
        material_type="theme",
        url="https://example.com/article?source=rss",
    )
    monkeypatch.setattr(
        news_module.news_sources,
        "_headline_dedupe_key",
        lambda _: "legacy-key",
        raising=False,
    )
    monkeypatch.delattr(news_module.news_sources, "news_headline_dedupe_key")

    assert news_module._news_headline_dedupe_key(card) == "legacy-key"


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
    assert frame["値動き"].isna().all()
    assert frame["取引量"].isna().all()
    assert set(frame["市場指標"]) == {"ニュース代理"}
    assert set(frame["値動き表示"]) == {"方向未確認"}
    assert set(frame["取引量目安"]) == {"ニュース集計"}


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
    assert pd.isna(frame.loc[0, "値動き"])
    assert pd.isna(frame.loc[0, "取引量"])
    assert frame.loc[0, "値動きスコア"] == 0.0
    assert frame.loc[0, "取引量スコア"] == 1.0
    assert frame.loc[0, "値動き表示"] == "方向未確認"
    assert frame.loc[0, "取引量目安"] == "ニュース集計"


def test_news_dashboard_heatmap_frame_only_uses_verified_market_metrics():
    snapshot = NewsDashboardSnapshot(
        generated_at=datetime(2026, 6, 4, 10, 0, tzinfo=UTC),
        heatmap_cells=[
            NewsHeatmapCell(
                category="市場データあり",
                market_metric_source="market_measured",
                price_change_pct=-1.2,
                volume_activity_score=1.8,
                news_count=2,
                risk_count=1,
                positive_count=1,
                official_source_count=0,
                freshness_ratio=0.5,
                heat_score=2.5,
                dominant_material_type="earnings",
            ),
            NewsHeatmapCell(
                category="ニュース代理",
                market_metric_source="news_proxy",
                price_change_pct=3.6,
                volume_activity_score=2.2,
                news_count=2,
                risk_count=0,
                positive_count=2,
                official_source_count=0,
                freshness_ratio=0.5,
                heat_score=2.0,
                dominant_material_type="risk",
            ),
        ],
    )

    frame = news_dashboard_heatmap_frame(snapshot).set_index("投資カテゴリ")

    assert frame.loc["市場データあり", "市場指標"] == "市場データ"
    assert frame.loc["市場データあり", "値動き"] == -1.2
    assert frame.loc["市場データあり", "値動き表示"] == "-1.2%"
    assert frame.loc["ニュース代理", "市場指標"] == "ニュース代理"
    assert pd.isna(frame.loc["ニュース代理", "値動き"])
    assert frame.loc["ニュース代理", "値動き表示"] == "方向未確認"


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
    assert "investment-stock-heatmap-tile" in html_text
    assert f"{len(groups)}カテゴリ" in html_text
    assert "8セクター" not in html_text
    tile_symbols = {tile["symbol"] for group in groups for tile in group["tiles"]}
    tile_count = sum(len(group["tiles"]) for group in groups)
    evidence_symbols = {
        symbol
        for lane in snapshot.category_lanes
        for card in lane.headlines
        for symbol_group in news_card_symbol_handoff_groups(card)
        for symbol in symbol_group[1]
    }
    assert f"{tile_count}銘柄タイル" in html_text
    assert tile_symbols
    assert tile_symbols <= evidence_symbols
    assert "面積は重複を除いた根拠記事数" in html_text
    assert "面積: 根拠記事数" in html_text
    assert "色: 古い→最新" in html_text
    assert "タイルの価格方向: 未確認" in html_text
    assert "カテゴリ市場データ: 下落" not in html_text
    assert "investment-stock-heatmap-click" in html_text
    assert '<a class="investment-stock-heatmap-tile' in html_text
    assert 'href="?smai_page=cockpit&amp;smai_symbol=NVDA"' in html_text
    assert 'target="_self"' in html_text
    assert 'target="_blank"' not in html_text
    assert "count-" in html_text
    assert "NVDA" in html_text
    assert "TSM" in html_text
    assert "NVDA / NVIDIA" in html_text
    assert "6857.T / アドバンテスト" in html_text
    assert html_text.index("investment-stock-heatmap-name") < html_text.index(
        "investment-stock-heatmap-symbol"
    )
    assert "未取得" not in html_text


def test_news_proxy_tiles_do_not_turn_material_taxonomy_into_price_direction():
    snapshot = build_news_dashboard_snapshot(
        [
            NewsHeadlineCard(
                title="業績見通しを下方修正",
                source_type="news",
                category="決算・業績修正",
                material_type="earnings",
                freshness_status="latest",
                related_symbols=["3457.T"],
            ),
            NewsHeadlineCard(
                title="規制リスクを確認",
                source_type="news",
                category="政策・規制",
                material_type="risk",
                freshness_status="latest",
                related_symbols=["7203.T"],
            ),
        ],
        generated_at=datetime(2026, 6, 4, 10, 0, tzinfo=UTC),
    )

    groups = news_dashboard_stock_heatmap_groups(snapshot)
    tiles = [tile for group in groups for tile in group["tiles"]]
    html_text = news_dashboard_stock_heatmap_html(snapshot)

    assert {group["metric_source"] for group in groups} == {"ニュース代理"}
    assert {group["summary_label"] for group in groups} == {"方向未確認 / ニュース上の注目度"}
    assert tiles
    assert {tile["change"] for tile in tiles} == {0.0}
    assert {tile["change_label"] for tile in tiles} == {"方向未確認"}
    assert {tile["tone"] for tile in tiles} == {"neutral"}
    assert {tile["relationship"] for tile in tiles} == {"direct"}
    assert {tile["factors_label"] for tile in tiles} == {"根拠1件"}
    assert "本文に出た" in html_text
    assert "タイルの価格方向: 未確認" in html_text
    assert "好材料" not in html_text
    assert "注意材料" not in html_text


def test_category_market_metrics_stay_in_the_header_not_on_symbol_tiles():
    snapshot = build_news_dashboard_snapshot(
        [
            NewsHeadlineCard(
                title="市場データを持つテーマ",
                source_type="news",
                category="半導体・AI",
                material_type="theme",
                freshness_status="latest",
                related_symbols=["NVDA", "TSM"],
            )
        ],
        generated_at=datetime(2026, 6, 4, 10, 0, tzinfo=UTC),
    )
    measured_cell = snapshot.heatmap_cells[0].model_copy(
        update={
            "market_metric_source": "market_measured",
            "price_change_pct": -1.2,
            "volume_activity_score": 1.8,
        }
    )
    measured_snapshot = snapshot.model_copy(update={"heatmap_cells": [measured_cell]})

    group = news_dashboard_stock_heatmap_groups(measured_snapshot)[0]
    tiles = group["tiles"]
    html_text = news_dashboard_stock_heatmap_html(measured_snapshot)

    assert group["summary_label"] == "-1.2% / カテゴリの市場指標"
    assert {tile["change"] for tile in tiles} == {0.0}
    assert {tile["change_label"] for tile in tiles} == {"方向未確認"}
    assert {tile["tone"] for tile in tiles} == {"neutral"}
    assert "カテゴリ市場データ" in html_text
    assert "カテゴリ市場データ: 下落" not in html_text
    assert "カテゴリ市場データは見出しのみ" in html_text
    assert "investment-stock-heatmap-group-trend" in html_text


def test_theme_map_excludes_unbacked_seed_symbols_and_macro_only_groups():
    direct_and_inferred_snapshot = build_news_dashboard_snapshot(
        [
            NewsHeadlineCard(
                title="個別根拠だけを持つ半導体テーマ",
                source_type="news",
                category="半導体・AI",
                material_type="theme",
                freshness_status="latest",
                related_symbols=["3457.T"],
                inferred_symbols=["7203.T"],
            )
        ],
        generated_at=datetime(2026, 6, 4, 10, 0, tzinfo=UTC),
    )
    macro_only_snapshot = build_news_dashboard_snapshot(
        [
            NewsHeadlineCard(
                title="市場背景だけを持つ為替テーマ",
                source_type="news",
                category="為替・金利",
                material_type="macro",
                freshness_status="latest",
                macro_proxy_symbols=["USDJPY", "US10Y"],
            )
        ],
        generated_at=datetime(2026, 6, 4, 10, 0, tzinfo=UTC),
    )

    direct_and_inferred_tiles = {
        tile["symbol"]
        for group in news_dashboard_stock_heatmap_groups(direct_and_inferred_snapshot)
        for tile in group["tiles"]
    }

    assert direct_and_inferred_tiles == {"3457.T", "7203.T"}
    direct_and_inferred_details = {
        tile["symbol"]: tile["relationship"]
        for group in news_dashboard_stock_heatmap_groups(direct_and_inferred_snapshot)
        for tile in group["tiles"]
    }
    assert direct_and_inferred_details == {"3457.T": "direct", "7203.T": "inferred"}
    assert news_dashboard_stock_heatmap_groups(macro_only_snapshot) == []
    assert news_dashboard_stock_heatmap_html(macro_only_snapshot) == ""


def test_theme_map_area_uses_deduplicated_news_evidence_not_company_size():
    snapshot = build_news_dashboard_snapshot(
        [
            NewsHeadlineCard(
                title="半導体の根拠記事A",
                url="https://example.test/a",
                source_name="Source A",
                source_type="news",
                category="半導体・AI",
                material_type="theme",
                freshness_status="latest",
                related_symbols=["NVDA"],
            ),
            NewsHeadlineCard(
                title="半導体の根拠記事A",
                url="https://example.test/a",
                source_name="Source A",
                source_type="news",
                category="半導体・AI",
                material_type="theme",
                freshness_status="latest",
                related_symbols=["NVDA"],
            ),
            NewsHeadlineCard(
                title="半導体の根拠記事B",
                url="https://example.test/b",
                source_name="Source B",
                source_type="news",
                category="半導体・AI",
                material_type="theme",
                freshness_status="recent",
                related_symbols=["NVDA"],
            ),
            NewsHeadlineCard(
                title="半導体の根拠記事C",
                url="https://example.test/c",
                source_name="Source C",
                source_type="news",
                category="半導体・AI",
                material_type="theme",
                freshness_status="latest",
                related_symbols=["TSM"],
            ),
            NewsHeadlineCard(
                title="半導体の根拠記事A（追跡URL違い）",
                url="https://example.test/a?utm_source=duplicate",
                source_name="Source A mirror",
                source_type="news",
                category="半導体・AI",
                material_type="theme",
                freshness_status="latest",
                related_symbols=["NVDA"],
            ),
        ],
        generated_at=datetime(2026, 6, 4, 10, 0, tzinfo=UTC),
    )

    tiles = {
        tile["symbol"]: tile
        for group in news_dashboard_stock_heatmap_groups(snapshot)
        for tile in group["tiles"]
    }

    assert tiles["NVDA"]["evidence_count"] == 2
    assert tiles["NVDA"]["source_count"] == 2
    assert tiles["NVDA"]["area_score"] > tiles["TSM"]["area_score"]
    assert tiles["NVDA"]["factors_label"] == "根拠2件・独立出典2件"
    assert news_module._stock_heatmap_area_score(evidence_count=2, source_count=1) == 2.0
    assert news_module._stock_heatmap_area_score(evidence_count=2, source_count=3) == 2.0


def test_theme_map_fills_visible_slots_after_skipping_macro_only_category():
    snapshot = build_news_dashboard_snapshot(
        [
            NewsHeadlineCard(
                title="為替の市場背景A",
                source_type="news",
                category="為替・金利",
                material_type="macro",
                freshness_status="latest",
                macro_proxy_symbols=["USDJPY"],
            ),
            NewsHeadlineCard(
                title="為替の市場背景B",
                source_type="news",
                category="為替・金利",
                material_type="macro",
                freshness_status="latest",
                macro_proxy_symbols=["US10Y"],
            ),
            NewsHeadlineCard(
                title="半導体の個別根拠",
                source_type="news",
                category="半導体・AI",
                material_type="theme",
                freshness_status="latest",
                related_symbols=["NVDA"],
            ),
        ],
        generated_at=datetime(2026, 6, 4, 10, 0, tzinfo=UTC),
    )

    groups = news_dashboard_stock_heatmap_groups(snapshot, max_groups=1)

    assert len(groups) == 1
    assert groups[0]["category"] == "半導体・AI"


def test_theme_map_compact_view_keeps_three_themes_and_labels_remaining_themes():
    snapshot = build_demo_news_dashboard_snapshot(
        now=datetime(2026, 6, 4, 10, 0, tzinfo=UTC),
    )

    html_text = news_dashboard_stock_heatmap_html(
        snapshot,
        max_groups=3,
        max_tiles_per_group=3,
    )

    assert "表示: 3カテゴリ / 9銘柄タイル" in html_text
    assert "investment-stock-heatmap-more" in html_text
    assert "ほか " in html_text


def test_theme_map_expanded_view_starts_after_compact_groups():
    snapshot = build_demo_news_dashboard_snapshot(
        now=datetime(2026, 6, 4, 10, 0, tzinfo=UTC),
    )
    groups = news_dashboard_stock_heatmap_groups(snapshot, max_tiles_per_group=3)

    expanded_html = news_dashboard_stock_heatmap_html(
        snapshot,
        max_groups=999,
        max_tiles_per_group=3,
        include_topline=False,
        start_group=3,
    )

    assert len(groups) > 3
    assert f">{groups[0]['category']}<" not in expanded_html
    assert f">{groups[3]['category']}<" in expanded_html


def test_material_taxonomy_does_not_assign_news_card_direction_colors():
    cards = (
        NewsHeadlineCard(
            title="前期経常を一転65％減益に下方修正",
            source_type="news",
            category="決算・業績修正",
            material_type="earnings",
            freshness_status="latest",
        ),
        NewsHeadlineCard(
            title="規制リスクの見直しを確認",
            source_type="news",
            category="政策・規制",
            material_type="risk",
            freshness_status="latest",
        ),
        NewsHeadlineCard(
            title="株主還元方針を更新",
            source_type="news",
            category="配当・株主還元",
            material_type="shareholder_return",
            freshness_status="latest",
        ),
    )

    for card in cards:
        markup = news_headline_card_html(card)
        assert "investment-news-card news" in markup
        assert "investment-news-card positive" not in markup
        assert "investment-news-card risk" not in markup


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

    assert spans
    assert all(tile["area_score"] > 0 for tile in tiles)
    assert all("根拠" in tile["factors_label"] for tile in tiles)
    assert all(tile["evidence_count"] >= 1 for tile in tiles)
    assert all(tile["source_count"] >= 1 for tile in tiles)
    assert {tile["relationship"] for tile in tiles} <= {"direct", "inferred"}
    assert {tile["color_style"] for tile in tiles} == {""}
    assert "freshness-" in html_text
    assert "investment-stock-heatmap-factors" in html_text
    assert "investment-stock-heatmap-evidence" in html_text
    assert "面積根拠:" in html_text
    assert 'style="grid-column: span ' in html_text


def test_news_dashboard_stock_heatmap_small_tiles_keep_company_name_and_symbol():
    snapshot = build_demo_news_dashboard_snapshot(
        now=datetime(2026, 6, 4, 10, 0, tzinfo=UTC),
    )

    groups = news_dashboard_stock_heatmap_groups(snapshot)
    small_tile = next(
        tile for group in groups for tile in group["tiles"] if tile["size"] in {"compact", "minor"}
    )
    html_text = news_module._stock_heatmap_tile_html(small_tile)

    assert "text-safe" in html_text
    assert f'>{small_tile["name"]}</span>' in html_text
    assert str(small_tile["relationship_label"]) in html_text
    assert "investment-stock-heatmap-symbol" in html_text
    assert "investment-stock-heatmap-factors" in html_text
    assert "面積根拠:" in html_text
    assert "aria-label=" in html_text


def test_news_dashboard_stock_heatmap_shows_traceable_evidence_factors_on_large_tiles():
    large_tile = news_module._stock_heatmap_tile(
        "NVDA",
        {
            "値動きスコア": 1.2,
            "市場指標": "市場データ",
            "鮮度比率": 100.0,
        },
        tile_index=0,
        symbol_score=20.0,
        evidence_detail={
            "evidence_count": 5,
            "source_count": 3,
            "freshness_rank": 3,
            "relationship": "direct",
        },
    )

    assert large_tile["size"] in {"hero", "major"}
    html_text = news_module._stock_heatmap_tile_html(large_tile)

    assert html_text.count("investment-stock-heatmap-factors") == 1
    assert str(large_tile["factors_label"]) in html_text
    assert "根拠5件・独立出典3件" in html_text


def test_radar_candidate_lane_limits_initial_items_without_changing_order():
    candidates = list(range(19))

    initial_items, initial_hidden_count = news_module.radar_candidate_lane_visible_items(
        candidates,
        expanded=False,
    )
    expanded_items, expanded_hidden_count = news_module.radar_candidate_lane_visible_items(
        candidates,
        expanded=True,
    )

    assert initial_items == [0, 1, 2, 3]
    assert initial_hidden_count == 15
    assert expanded_items == candidates
    assert expanded_hidden_count == 0


def test_radar_confirmation_triage_frame_keeps_provenance_and_confirmation_order_separate():
    snapshot = build_demo_news_dashboard_snapshot(
        now=datetime(2026, 6, 4, 10, 0, tzinfo=UTC),
    )
    candidate_map = news_module.build_radar_candidate_map(snapshot)

    frame = news_module.news_radar_confirmation_triage_frame(candidate_map.candidates)

    assert list(frame.columns) == ["確認の順番", "候補由来", "件数", "候補"]
    assert len(frame) == 9
    assert frame["件数"].sum() == len(candidate_map.candidates)
    assert set(frame["確認の順番"]) == {"先に確認", "次に確認", "必要に応じて"}
    assert set(frame["候補由来"]) == {"本文に出た銘柄", "SMAI推測候補", "市場背景の確認"}


def test_radar_candidate_footer_keeps_a_bounded_cockpit_only_handoff():
    snapshot = build_demo_news_dashboard_snapshot(
        now=datetime(2026, 6, 4, 10, 0, tzinfo=UTC),
    )
    candidates = [
        candidate
        for candidate in news_module.build_radar_candidate_map(snapshot).candidates
        if candidate.is_investigation_candidate
    ]
    news_module.st.session_state.clear()

    html_text = news_module._radar_candidate_footer_html(candidates[:2])

    assert html_text.count("investment-radar-candidate-footer-item") == 2
    assert "smai_page=cockpit" in html_text
    assert "本文言及" in html_text or "テーマ関連" in html_text
    assert "確認の順番" not in html_text
    assert "根拠" in html_text


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


def test_radar_transient_state_resets_when_active_user_changes(monkeypatch):
    active_user = {"id": "user_a"}
    session_state = {
        news_module.NEWS_RADAR_SESSION_OWNER_STATE_KEY: "user_a",
        news_module.NEWS_RADAR_CANDIDATE_STATE_KEY: "radar:direct_mention:NVDA",
        news_module.NEWS_RADAR_CANDIDATE_DIALOG_REQUEST_STATE_KEY: "radar:direct_mention:NVDA",
        news_module.NEWS_RADAR_EVIDENCE_BUNDLES_STATE_KEY: {"radar:direct_mention:NVDA": {}},
        news_module.NEWS_RADAR_INTERPRETATIONS_STATE_KEY: {"radar:direct_mention:NVDA": {}},
        "investment_radar_candidate_lane_expanded_direct_mention": True,
        "investment_radar_candidate_markets": ["米国"],
        "investment_news_filter_categories": ["半導体・AI"],
        news_module.NEWS_DASHBOARD_WATCHLIST_STATE_KEY: "NVDA",
        "unrelated_state": "keep",
    }
    monkeypatch.setattr(news_module.st, "session_state", session_state)
    monkeypatch.setattr(news_module, "current_user_id", lambda: active_user["id"])

    news_module._ensure_news_radar_user_scope()

    assert session_state[news_module.NEWS_RADAR_EVIDENCE_BUNDLES_STATE_KEY]
    assert session_state[news_module.NEWS_RADAR_INTERPRETATIONS_STATE_KEY]

    active_user["id"] = "user_b"
    news_module._ensure_news_radar_user_scope()

    assert session_state[news_module.NEWS_RADAR_SESSION_OWNER_STATE_KEY] == "user_b"
    assert "unrelated_state" in session_state
    assert all(
        key == news_module.NEWS_RADAR_SESSION_OWNER_STATE_KEY
        or not (key.startswith("investment_radar_") or key.startswith("investment_news_filter_"))
        for key in session_state
    )
    assert news_module.NEWS_DASHBOARD_WATCHLIST_STATE_KEY not in session_state


def test_rerun_with_radar_candidate_detail_requeues_explicit_dialog_request(monkeypatch):
    session_state: dict[str, object] = {}
    rerun_calls: list[bool] = []
    monkeypatch.setattr(news_module.st, "session_state", session_state)
    monkeypatch.setattr(news_module.st, "rerun", lambda: rerun_calls.append(True))

    news_module._rerun_with_radar_candidate_detail("radar:direct_mention:NVDA")

    assert session_state[news_module.NEWS_RADAR_CANDIDATE_STATE_KEY] == "radar:direct_mention:NVDA"
    assert (
        session_state[news_module.NEWS_RADAR_CANDIDATE_DIALOG_REQUEST_STATE_KEY]
        == "radar:direct_mention:NVDA"
    )
    assert rerun_calls == [True]


def test_radar_priority_reason_rows_support_a_candidate_from_the_previous_contract():
    legacy_candidate = SimpleNamespace(
        confirmation_priority=80,
        watchlist_match=True,
        evidence=[
            SimpleNamespace(freshness_status="latest", material_type="earnings"),
            SimpleNamespace(freshness_status="recent", material_type="theme"),
        ],
    )

    assert news_module._radar_candidate_priority_reason_rows(legacy_candidate) == [
        ("freshness", "latest", 40),
        ("evidence_breadth", "2", 16),
        ("material_type", "earnings", 10),
        ("watchlist_match", "watchlist_match", 14),
    ]


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
    assert "HEADLINE FLOW" in html_text
    assert "2件を自動ハイライト" in html_text
    assert "最新公開 未確認" in html_text
    assert "--investment-news-flow-delay:0s" in html_text
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
    assert "--investment-news-flow-delay:9s" in html_text


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
