from __future__ import annotations

from ui.components import sidemenu


def test_sidemenu_scroll_bridge_targets_streamlit_main_container():
    markup = sidemenu.sidemenu_scroll_to_top_html()

    assert "section.stAppViewMain" in markup
    assert "scrollTo({ top: 0, left: 0" in markup


def test_sidemenu_scroll_reset_runs_only_when_page_changes(monkeypatch):
    session_state: dict[str, object] = {}
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(sidemenu.st, "session_state", session_state)
    monkeypatch.setattr(
        sidemenu.components,
        "html",
        lambda body, **kwargs: calls.append({"body": body, **kwargs}),
    )

    sidemenu.render_sidemenu_scroll_reset(sidemenu.SIDEMENU_PAGE_COCKPIT)
    sidemenu.render_sidemenu_scroll_reset(sidemenu.SIDEMENU_PAGE_COCKPIT)
    assert calls == []

    sidemenu.render_sidemenu_scroll_reset(sidemenu.SIDEMENU_PAGE_RANKING)

    assert len(calls) == 1
    assert calls[0]["height"] == 0
    assert calls[0]["width"] == 0
    assert session_state[sidemenu.SIDEMENU_RENDERED_PAGE_STATE_KEY] == "ranking"
