from datetime import UTC, datetime

from streamlit.testing.v1 import AppTest

from backend.news import (
    NewsHeadlineCard,
    NewsUpdateStatus,
    build_demo_news_dashboard_snapshot,
    build_news_dashboard_snapshot,
)
from ui.views.news import (
    news_dashboard_filtered_snapshot,
    news_dashboard_status_items,
    parse_news_watchlist_symbols,
)


def test_news_dashboard_status_items_show_cache_and_freshness_context():
    snapshot = build_demo_news_dashboard_snapshot(now=datetime(2026, 6, 4, 10, 0, tzinfo=UTC))
    status = NewsUpdateStatus(
        last_attempt_at=datetime(2026, 6, 4, 10, 5, tzinfo=UTC),
        last_success_at=datetime(2026, 6, 4, 10, 5, tzinfo=UTC),
        cache_file_size_bytes=1536,
    )

    items = dict(
        news_dashboard_status_items(
            snapshot,
            status,
            uses_cached_snapshot=True,
        )
    )

    assert items["表示データ"] == "保存済みキャッシュ"
    assert items["最終取得成功"] != "未確認"
    assert items["ニュース件数"].endswith("件")
    assert items["キャッシュサイズ"] == "1.5 KB"
    assert items["更新状態"] == "前回更新成功"


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


def test_investment_news_page_renders_with_streamlit_app(monkeypatch):
    monkeypatch.setenv("SMAI_SYMBOL_BACKGROUND_REFRESH_DELAY_SCALE", "9999")
    monkeypatch.setenv("SMAI_NEWS_BACKGROUND_REFRESH_DELAY_SCALE", "9999")
    app = AppTest.from_file("ui/app.py", default_timeout=20)
    app.session_state["sidemenu_page"] = "news"

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
    assert "ニュース表示の状態" in page_text
    assert "表示データ" in page_text
    assert "キャッシュサイズ" in page_text
    assert "投資レーダー" in page_text
    assert "市場ニュースヘッドライン" in page_text
    assert "投資ヒートマップ" in page_text
    assert "カテゴリ別ニュースレーン" in page_text
    assert "表示中ニュース" in page_text
    assert "データ状態" not in page_text
    assert "ニュース表示を更新" in button_labels
    assert "Watchlist" in text_input_labels
    assert {"カテゴリ", "鮮度", "source"}.issubset(set(multiselect_labels))
    assert "関連銘柄" in selectbox_labels
    assert {"Watchlist一致を優先表示", "Watchlist一致だけ表示"}.issubset(set(checkbox_labels))
