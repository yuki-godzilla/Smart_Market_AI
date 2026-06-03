from streamlit.testing.v1 import AppTest


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
    assert "投資レーダー" in page_text
    assert "マーケットニュースストリーム" in page_text
    assert "ニュース加熱テーマ" in page_text
    assert "カテゴリ別ニュースレーン" in page_text
    assert "ニュース表示を更新" in button_labels
