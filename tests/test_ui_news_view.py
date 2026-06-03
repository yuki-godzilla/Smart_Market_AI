from datetime import UTC, datetime

from backend.news import NewsUpdateStatus, build_demo_news_dashboard_snapshot
from ui.views.news import (
    news_dashboard_handoff_symbols,
    news_dashboard_heatmap_frame,
    news_dashboard_status_items,
    news_dashboard_unique_headline_count,
    news_headline_card_html,
    news_symbol_handoff_label,
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
    assert items[0]["value"] == "8件"
    assert items[0]["caption"] == "重複を除いた見出し数"
    assert items[2]["value"] == "最新"
    assert items[3]["value"] == "キャッシュ"
    assert items[3]["caption"] == "2.0KB"


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
