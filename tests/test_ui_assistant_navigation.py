from ui import app as app_module
from ui.app import _apply_navigation_query_params


def test_navigation_query_params_open_cockpit_without_symbol(monkeypatch):
    session_state: dict[str, object] = {
        "market_data_preview": object(),
        "market_data_status_message": "old",
    }
    query_params = {"smai_page": ["cockpit"]}
    monkeypatch.setattr(app_module.st, "session_state", session_state)
    monkeypatch.setattr(app_module.st, "query_params", query_params, raising=False)

    _apply_navigation_query_params()

    assert session_state["sidemenu_page"] == "cockpit"
    assert "market_data_preview" in session_state
    assert "market_data_status_message" in session_state
    assert query_params == {}


def test_navigation_query_params_open_ranking_from_assistant(monkeypatch):
    session_state: dict[str, object] = {}
    query_params = {"smai_page": ["ranking"]}
    monkeypatch.setattr(app_module.st, "session_state", session_state)
    monkeypatch.setattr(app_module.st, "query_params", query_params, raising=False)

    _apply_navigation_query_params()

    assert session_state["sidemenu_page"] == "ranking"
    assert query_params == {}
