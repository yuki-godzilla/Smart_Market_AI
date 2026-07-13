from datetime import UTC, datetime

from streamlit.testing.v1 import AppTest

from backend.news import (
    NewsDashboardSnapshot,
    NewsHeadlineCard,
    build_demo_news_dashboard_snapshot,
    build_news_dashboard_snapshot,
)
from ui import favorites, watchlist_snapshots
from ui.views.news import (
    NEWS_RADAR_CANDIDATE_STATE_KEY,
    _news_symbol_chip_preview_rows,
    combine_news_watchlist_symbols,
    news_dashboard_filtered_snapshot,
    news_dashboard_freshness_badge_html,
    parse_news_watchlist_symbols,
)


def test_news_dashboard_freshness_badge_keeps_header_context_compact():
    snapshot = build_demo_news_dashboard_snapshot(now=datetime(2026, 6, 4, 10, 0, tzinfo=UTC))

    badge_html = news_dashboard_freshness_badge_html(snapshot)

    assert "情報鮮度" in badge_html
    assert "最新" in badge_html
    assert "取得 2026-06-04 18:58 JST" in badge_html
    assert "取得時刻 2026-06-04 18:58 JST" in badge_html
    assert "表示データ" not in badge_html
    assert "キャッシュサイズ" not in badge_html
    assert "更新状態" not in badge_html


def test_news_dashboard_freshness_badge_shows_jst_date_rollover():
    snapshot = NewsDashboardSnapshot(
        generated_at=datetime(2026, 6, 4, 23, 13, tzinfo=UTC),
        fetched_at=datetime(2026, 6, 4, 23, 13, tzinfo=UTC),
        freshness_status="latest",
    )

    badge_html = news_dashboard_freshness_badge_html(snapshot)

    assert "取得 2026-06-05 08:13 JST" in badge_html
    assert "2026-06-04 23:13 UTC" not in badge_html


def test_news_dashboard_filtered_snapshot_filters_detail_conditions():
    snapshot = build_news_dashboard_snapshot(
        [
            NewsHeadlineCard(
                title="半導体AIニュース",
                source_type="news",
                source_name="Example Market",
                category="半導体・AI",
                region="グローバル",
                material_type="theme",
                published_at=datetime(2026, 6, 4, 9, 0, tzinfo=UTC),
                freshness_status="latest",
                related_symbols=["NVDA"],
                inferred_symbols=["TSM"],
            ),
            NewsHeadlineCard(
                title="銀行ニュース",
                source_type="news",
                source_name="Other Market",
                category="金融",
                region="日本",
                material_type="macro",
                published_at=datetime(2026, 6, 4, 8, 0, tzinfo=UTC),
                freshness_status="recent",
                related_symbols=[],
                inferred_symbols=["JPM"],
            ),
        ],
        generated_at=datetime(2026, 6, 4, 10, 0, tzinfo=UTC),
    )

    filtered = news_dashboard_filtered_snapshot(
        snapshot,
        categories=["半導体・AI"],
        freshness=["latest"],
        relation_filter="direct",
        sources=["Example Market"],
    )

    assert [card.title for card in filtered.stream_headlines] == ["半導体AIニュース"]
    assert [lane.category for lane in filtered.category_lanes] == ["半導体・AI"]
    assert {cell.category for cell in filtered.heatmap_cells} == {"半導体・AI"}


def test_news_dashboard_filtered_snapshot_prioritizes_watchlist_matches():
    snapshot = build_news_dashboard_snapshot(
        [
            NewsHeadlineCard(
                title="銀行ニュース",
                source_type="news",
                source_name="Other Market",
                category="金融",
                material_type="macro",
                freshness_status="recent",
                inferred_symbols=["JPM"],
            ),
            NewsHeadlineCard(
                title="半導体AIニュース",
                source_type="news",
                source_name="Example Market",
                category="半導体・AI",
                material_type="theme",
                freshness_status="latest",
                related_symbols=["NVDA"],
            ),
        ],
        generated_at=datetime(2026, 6, 4, 10, 0, tzinfo=UTC),
    )

    prioritized = news_dashboard_filtered_snapshot(
        snapshot,
        watchlist_symbols=["NVDA"],
        prioritize_watchlist=True,
    )
    only_watchlist = news_dashboard_filtered_snapshot(
        snapshot,
        watchlist_symbols=["JPM"],
        watchlist_only=True,
    )

    assert [card.title for card in prioritized.stream_headlines] == [
        "半導体AIニュース",
        "銀行ニュース",
    ]
    assert [card.title for card in only_watchlist.stream_headlines] == ["銀行ニュース"]


def test_parse_news_watchlist_symbols_accepts_common_separators():
    assert parse_news_watchlist_symbols(" nvda, 7203.t、gld;NVDA；qqq ") == [
        "NVDA",
        "7203.T",
        "GLD",
        "QQQ",
    ]


def test_combine_news_watchlist_symbols_keeps_source_compatibility():
    manual = ["7203.t", "NVDA"]
    favorites = ["nvda", "6857.T"]

    assert combine_news_watchlist_symbols(manual, favorites, source="manual_watchlist") == [
        "7203.T",
        "NVDA",
    ]
    assert combine_news_watchlist_symbols(manual, favorites, source="favorites_watchlist") == [
        "NVDA",
        "6857.T",
    ]
    assert combine_news_watchlist_symbols(manual, favorites, source="combined_watchlist") == [
        "NVDA",
        "6857.T",
        "7203.T",
    ]


def test_news_symbol_chip_rows_show_favorite_state_and_skip_missing_symbol(tmp_path, monkeypatch):
    monkeypatch.setattr(favorites, "FAVORITES_FILE_PATH", tmp_path / "favorites.json")

    rows = _news_symbol_chip_preview_rows(
        ["5932.T", ""],
        symbol_name_map={"5932.T": "三協立山"},
    )

    assert rows == [
        {
            "symbol": "5932.T",
            "label": "5932.T / 三協立山",
            "favorite_label": "☆ お気に入り",
        }
    ]

    favorites.add_favorite("5932.T", {"name": "三協立山", "source_screen": "news"})
    active_rows = _news_symbol_chip_preview_rows(
        ["5932.T"],
        symbol_name_map={"5932.T": "三協立山"},
    )
    assert active_rows[0]["favorite_label"] == "★ お気に入り中"

    favorites.remove_favorite("5932.T")
    inactive_rows = _news_symbol_chip_preview_rows(
        ["5932.T"],
        symbol_name_map={"5932.T": "三協立山"},
    )
    assert inactive_rows[0]["favorite_label"] == "☆ お気に入り"


def test_investment_news_page_renders_with_streamlit_app(monkeypatch):
    monkeypatch.setenv("SMAI_DISABLE_BACKGROUND_WORKERS", "1")
    app = AppTest.from_file("ui/app.py", default_timeout=20)
    app.session_state["sidemenu_page"] = "news"
    app.session_state["smai_current_user_id"] = "default"

    app.run()

    assert not app.exception
    page_text = "\n".join(
        str(element.value)
        for group in (
            app.caption,
            app.markdown,
            app.subheader,
            app.button,
        )
        for element in group
        if getattr(element, "value", None) is not None
    )
    button_labels = [str(getattr(element, "label", "")) for element in app.button]
    text_input_labels = [str(getattr(element, "label", "")) for element in app.text_input]
    multiselect_labels = [str(getattr(element, "label", "")) for element in app.multiselect]
    selectbox_labels = [str(getattr(element, "label", "")) for element in app.selectbox]
    checkbox_labels = [str(getattr(element, "label", "")) for element in app.checkbox]
    assert "情報鮮度" in page_text
    assert "ニュース表示の状態" not in page_text
    assert "表示データ" not in page_text
    assert "キャッシュサイズ" not in page_text
    assert "投資レーダー" in page_text
    assert "市場ニュースヘッドライン" in page_text
    assert "投資ヒートマップ" in page_text
    assert "ニュースからの確認候補" in page_text
    assert "追加候補マップ" not in page_text
    assert "本文に出た銘柄" in page_text
    assert "確認の順番" in page_text
    assert "市場確認指標は「確認候補を絞り込む」から追加できます" in page_text
    assert "カテゴリ別ニュースレーン" in page_text
    assert "表示中ニュース" in page_text
    assert "データ状態" not in page_text
    assert "ニュース表示を更新" in button_labels
    assert "根拠を確認（ローカルRAG）" in button_labels
    assert "Watchlist" in text_input_labels
    assert {"カテゴリ", "鮮度", "source"}.issubset(set(multiselect_labels))
    assert {"関連銘柄"}.issubset(set(selectbox_labels))
    assert "追加候補を選択" not in selectbox_labels
    assert {"Watchlist一致を優先表示", "Watchlist一致だけ表示"}.issubset(set(checkbox_labels))

    markdown_values = [str(element.value) for element in app.markdown]
    candidate_map_index = next(
        index for index, value in enumerate(markdown_values) if "ニュースからの確認候補" in value
    )
    heatmap_index = next(
        index for index, value in enumerate(markdown_values) if "投資ヒートマップ" in value
    )
    assert candidate_map_index < heatmap_index

    detail_button = next(button for button in app.button if button.label == "詳細を見る")
    detail_button.click().run()

    assert not app.exception
    assert str(app.session_state[NEWS_RADAR_CANDIDATE_STATE_KEY]).startswith("radar:")
    selected_text = "\n".join(
        str(element.value)
        for group in (app.caption, app.markdown)
        for element in group
        if getattr(element, "value", None) is not None
    )
    assert "選択中の候補" in selected_text
    assert "未実行（銘柄コックピットで確認）" in selected_text


def test_my_watchlist_page_renders_without_mascot_keyerror(tmp_path, monkeypatch):
    monkeypatch.setenv("SMAI_DISABLE_BACKGROUND_WORKERS", "1")
    monkeypatch.setattr(favorites, "FAVORITES_FILE_PATH", tmp_path / "favorites.json")
    monkeypatch.setattr(
        favorites,
        "profile_data_path",
        lambda filename, **_: tmp_path / filename,
    )
    monkeypatch.setattr(
        watchlist_snapshots,
        "WATCHLIST_SNAPSHOTS_FILE_PATH",
        tmp_path / "watchlist_snapshots.json",
    )
    monkeypatch.setattr(
        watchlist_snapshots,
        "profile_data_path",
        lambda filename, **_: tmp_path / filename,
    )
    app = AppTest.from_file("ui/app.py", default_timeout=20)
    app.session_state["sidemenu_page"] = "watchlist"
    app.session_state["smai_current_user_id"] = "local_user"

    app.run()

    assert not app.exception


def test_my_watchlist_page_renders_compact_controls_with_favorite(tmp_path, monkeypatch):
    monkeypatch.setenv("SMAI_DISABLE_BACKGROUND_WORKERS", "1")
    monkeypatch.setattr(favorites, "FAVORITES_FILE_PATH", tmp_path / "favorites.json")
    monkeypatch.setattr(
        favorites,
        "profile_data_path",
        lambda filename, **_: tmp_path / filename,
    )
    monkeypatch.setattr(
        watchlist_snapshots,
        "WATCHLIST_SNAPSHOTS_FILE_PATH",
        tmp_path / "watchlist_snapshots.json",
    )
    monkeypatch.setattr(
        watchlist_snapshots,
        "profile_data_path",
        lambda filename, **_: tmp_path / filename,
    )
    favorites.add_favorite(
        "5932.T",
        {
            "name": "三協立山",
            "market": "jp",
            "asset_type": "stock",
            "currency": "JPY",
            "source_screen": "news",
        },
    )
    app = AppTest.from_file("ui/app.py", default_timeout=20)
    app.session_state["sidemenu_page"] = "watchlist"
    app.session_state["smai_current_user_id"] = "local_user"

    app.run()

    assert not app.exception
    assert app.selectbox(key="watchlist_groups_view_mode").value == "グループ別"
    app.selectbox(key="watchlist_groups_view_mode").set_value("すべて").run()
    assert not app.exception
    assert "My Radarの判定理由を見る" not in {item.label for item in app.expander}
    assert "更新オプション" not in {item.label for item in app.expander}
    assert "判断メモを追加" not in {item.label for item in app.expander}
    assert {item.label for item in app.radio} >= {"表示フィルター", "表示形式"}
    assert {item.label for item in app.selectbox} >= {"並び順"}
    assert app.selectbox(key="market_data_watchlist_sort").value == "追加日が新しい順"
    assert "最大更新件数" not in {item.label for item in app.number_input}
    assert {item.label for item in app.button} >= {
        "↻ ウォッチリストを更新",
        "銘柄を詳しく見る",
        "Cockpit画面で確認",
    }
    assert "投資レーダーで関連ニュースを見る" not in {item.label for item in app.button}
    assert "AI調査" not in {item.label for item in app.button}
    assert "レポート" not in {item.label for item in app.button}

    app.button(key="watchlist_detail_5932.T").click().run()
    assert not app.exception
    assert "AI Research" in {item.label for item in app.tabs}

    app.radio(key="market_data_watchlist_filter").set_value("更新推奨").run()
    assert not app.exception
    assert any("表示中: 1件 / 全体 1件" in str(item.value) for item in app.caption)

    app.radio(key="market_data_watchlist_display_mode").set_value("テーブル表示").run()
    assert not app.exception
    assert len(app.dataframe) == 1
