import inspect

from ui.app import (
    _favorite_table_rows,
    _render_my_watchlist_page,
    favorite_prioritized_symbol_candidate_labels,
    favorite_symbol_candidate_display_label,
    ranking_favorite_event_token_from_aggrid_response,
)
from ui.styles import SMAI_GLOBAL_CSS


def test_favorite_table_rows_keep_daily_columns_and_hide_internal_fields():
    table_rows = _favorite_table_rows(
        [
            {
                "symbol": "9432.T",
                "name": "NTT",
                "price": "144.3円",
                "price_change_1d": "0.35",
                "price_change_5d": "-0.07",
                "price_change_1m": "-3.48",
                "ai_score": "68.63",
                "upside": "44.36",
                "downside": "57.39",
                "status_label": "横ばい",
                "refresh_label": "要確認",
                "last_checked_at": "2026/06/28 06:39",
                "checkpoint": "次の材料や価格変化を確認",
                "snapshot_status": "ok",
                "radar_priority": "55",
                "refresh_error": "",
            }
        ]
    )

    assert list(table_rows[0]) == [
        "ウォッチ",
        "銘柄",
        "銘柄名",
        "価格",
        "1日",
        "5日",
        "1か月",
        "AI総合",
        "上昇気配",
        "下振れ警戒",
        "状態",
        "更新",
        "最終確認",
        "確認ポイント",
    ]
    assert table_rows[0]["1日"] == "+0.35%"
    assert "snapshot状態" not in table_rows[0]
    assert "Radar優先度" not in table_rows[0]
    assert "前回エラー" not in table_rows[0]


def test_ranking_favorite_event_token_distinguishes_repeat_clicks():
    first_click = {
        "eventData": {
            "streamlitRerunEventTriggerName": "cellClicked",
            "rowIndex": 2,
            "event": {"timeStamp": 1001},
        }
    }
    second_click = {
        "eventData": {
            "streamlitRerunEventTriggerName": "cellClicked",
            "rowIndex": 2,
            "event": {"timeStamp": 1002},
        }
    }

    first_token = ranking_favorite_event_token_from_aggrid_response(first_click, "7203.T")
    assert first_token == "cellClicked|favorite|7203.T|2|1001"
    assert (
        ranking_favorite_event_token_from_aggrid_response(first_click, "7203.T")
        == first_token
    )
    assert (
        ranking_favorite_event_token_from_aggrid_response(second_click, "7203.T")
        != first_token
    )
    assert ranking_favorite_event_token_from_aggrid_response(first_click, None) is None


def test_watchlist_page_keeps_refresh_in_header_and_removes_radar_actions():
    source = inspect.getsource(_render_my_watchlist_page)

    assert "smai-watchlist-header-refresh-anchor" in source
    assert "↻ ウォッチリストを更新" in source
    assert "_render_my_radar_summary" not in source
    assert "投資レーダーで関連ニュースを見る" not in source


def test_favorite_active_state_and_watchlist_refresh_have_emphasis_styles():
    assert "color: #FBBF24 !important;" in SMAI_GLOBAL_CSS
    assert "color: #FCD34D !important;" in SMAI_GLOBAL_CSS
    assert ".smai-watchlist-header-refresh-anchor" in SMAI_GLOBAL_CSS


def test_cockpit_symbol_candidates_prioritize_and_mark_favorites():
    rows = [
        {"symbol": "7203.T", "name": "Toyota Motor"},
        {"symbol": "9983.T", "name": "Fast Retailing"},
        {"symbol": "6758.T", "name": "Sony Group"},
    ]
    favorites = {"6758.t", "9983.T"}

    labels = favorite_prioritized_symbol_candidate_labels(rows, favorites)

    assert labels == [
        "9983.T - Fast Retailing",
        "6758.T - Sony Group",
        "7203.T - Toyota Motor",
    ]
    assert (
        favorite_symbol_candidate_display_label(labels[0], favorites)
        == "★ 9983.T - Fast Retailing"
    )
    assert favorite_symbol_candidate_display_label(labels[-1], favorites) == labels[-1]
