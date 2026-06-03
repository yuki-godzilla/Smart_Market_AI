from datetime import UTC, datetime

from backend.news import NewsUpdateStatus, build_demo_news_dashboard_snapshot
from ui.views.news import (
    news_dashboard_handoff_symbols,
    news_dashboard_heatmap_frame,
    news_dashboard_status_items,
    news_headline_card_html,
)


def test_news_dashboard_status_items_distinguish_demo_and_cache():
    snapshot = build_demo_news_dashboard_snapshot(
        now=datetime(2026, 6, 4, 10, 0, tzinfo=UTC),
    )
    items = news_dashboard_status_items(
        snapshot,
        NewsUpdateStatus(cache_file_size_bytes=2048),
        using_demo=False,
    )

    assert items[0]["label"] == "表示ニュース"
    assert items[2]["value"] == "最新"
    assert items[3]["value"] == "キャッシュ"
    assert items[3]["caption"] == "2.0KB"


def test_news_dashboard_heatmap_frame_is_user_facing():
    snapshot = build_demo_news_dashboard_snapshot(
        now=datetime(2026, 6, 4, 10, 0, tzinfo=UTC),
    )
    frame = news_dashboard_heatmap_frame(snapshot)

    assert not frame.empty
    assert {"カテゴリ", "地域", "加熱度", "ニュース件数", "主な材料"}.issubset(set(frame.columns))
    assert frame["加熱度"].min() >= 0


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


def test_news_dashboard_handoff_symbols_are_unique_in_display_order():
    snapshot = build_demo_news_dashboard_snapshot(
        now=datetime(2026, 6, 4, 10, 0, tzinfo=UTC),
    )
    symbols = news_dashboard_handoff_symbols(snapshot)

    assert symbols
    assert len(symbols) == len(set(symbols))
    assert "NVDA" in symbols
