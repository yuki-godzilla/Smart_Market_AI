from datetime import UTC, datetime

from streamlit.testing.v1 import AppTest

from backend.news import NewsUpdateStatus, build_demo_news_dashboard_snapshot
from ui.views.news import news_dashboard_status_items


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


def test_investment_news_page_renders_with_streamlit_app(monkeypatch):
    monkeypatch.setenv("SMAI_SYMBOL_BACKGROUND_REFRESH_DELAY_SCALE", "0")
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
    assert "ニュース表示の状態" in page_text
    assert "表示データ" in page_text
    assert "キャッシュサイズ" in page_text
    assert "投資レーダー" in page_text
    assert "市場ニュースヘッドライン" in page_text
    assert "投資ヒートマップ" in page_text
    assert "カテゴリ別ニュースレーン" in page_text
    assert "表示中ニュース" not in page_text
    assert "データ状態" not in page_text
    assert "ニュース表示を更新" in button_labels
