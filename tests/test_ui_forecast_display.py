import asyncio
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pandas as pd

from backend.core.data_contracts import Bar, FundamentalSnapshot, Symbol
from backend.core.errors import DataSourceError
from backend.screening import ScreeningScore
from ui.app import (
    DEFAULT_MARKET_DATA_PERIOD_PRESET,
    MARKET_DATA_PERIOD_CUSTOM,
    MARKET_DATA_PERIOD_PRESETS,
    NO_SYMBOL_CANDIDATE_LABEL,
    RANKING_RESULT_GRID_CUSTOM_CSS,
    SYMBOL_DETAIL_DIALOG_CSS,
    _build_market_data_ranking_rows,
    _coerce_number_input_state,
    _current_or_default_symbol_labels,
    _ensure_selectbox_state_value,
    _market_data_preview_symbol_label,
    _name_from_candidate,
    _normalize_dividend_filter_state,
    _ranking_result_grid_height,
    _ranking_result_grid_key,
    _ranking_result_matches_current_selection,
    _ranking_result_table_base_key,
    _ranking_source_key_for_selection,
    _ranking_symbols_from_selected_labels,
    _render_market_chart,
    _symbol_from_candidate,
    build_cockpit_decision_report_context,
    build_ranking_decision_report_context,
    cockpit_detail_summary_rows,
    cockpit_filtered_symbol_rows,
    cockpit_investment_memo_rows,
    cockpit_period_evaluation_rows,
    decision_report_json_download,
    decision_report_markdown_download,
    default_forecast_horizon_days,
    default_market_data_provider,
    forecast_boundary_frame,
    forecast_chart_summary,
    forecast_consensus_display_rows,
    forecast_metric_display_rows,
    forecast_metric_summary,
    format_provider_error_details,
    get_cached_ranking_build,
    investment_score_display_rows,
    investment_score_summary_lines,
    market_chart_long_frame,
    market_data_period_dates,
    market_data_period_help,
    merged_symbol_candidate_rows,
    provider_error_summary_rows,
    ranking_comparison_summary,
    ranking_detail_event_token_from_aggrid_response,
    ranking_detail_symbol_from_aggrid_response,
    ranking_detail_symbol_to_open,
    ranking_investment_detail_rows,
    ranking_investment_note,
    ranking_result_aggrid_options,
    score_component_rows,
    selected_symbol_has_universe_detail,
    set_cached_ranking_build,
    symbol_candidate_label,
    symbol_detail_table_html,
    symbol_universe_data_info_rows,
    symbol_universe_detail_display_value,
    symbol_universe_detail_rows,
    symbol_universe_fund_detail_rows,
    symbol_universe_investment_metric_rows,
    symbol_universe_key_metric_rows,
    symbol_universe_nisa_display,
    symbol_universe_overview_rows,
)
from ui.ranking import (
    RANKING_BETA_RISK_LABELS,
    RANKING_BETA_RISK_STANDARD_OR_LOWER,
    RANKING_DIVIDEND_LABELS,
    RANKING_FETCH_LIMIT_BALANCED,
    RANKING_FETCH_LIMIT_FAST,
    RANKING_FETCH_LIMIT_PRESET,
    RANKING_FILTER_HELP_TEXTS,
    RANKING_INDEX_FAMILY_LABELS,
    RANKING_INVESTMENT_STYLE_METRICS,
    RANKING_MARKET_CAP_LABELS,
    RANKING_NISA_ELIGIBILITY_LABELS,
    RANKING_PRESET_ETF_CORE_COST,
    RANKING_PRESET_ETF_INCOME,
    RANKING_PRESET_MIN_VOLATILITY,
    RANKING_PRESET_MULTI_FACTOR,
    RANKING_PRESET_QUALITY_GROWTH,
    RANKING_PRESET_QUALITY_VALUE,
    RANKING_PRESET_SMALL_GROWTH,
    RANKING_PRESET_SUSTAINABLE_INCOME,
    RANKING_PURPOSE_ETF_CORE_COST,
    RANKING_PURPOSE_MULTI_FACTOR,
    RANKING_PURPOSE_QUALITY_GROWTH,
    RANKING_PURPOSE_SUSTAINABLE_INCOME,
    RANKING_THEME_LABELS,
    RANKING_WEIGHT_PRESETS,
    apply_ranking_weight_preset,
    filter_symbol_universe_rows,
    initial_ranking_selected_labels,
    limited_ranking_selected_labels,
    live_ranking_symbol_warning_message,
    normalize_dividend_filter_values,
    rank_investment_score_rows,
    ranking_build_cache_key,
    ranking_database_fit_score,
    ranking_deep_dive_default_symbol,
    ranking_detail_filters_for_category,
    ranking_filter_signature,
    ranking_metadata_confidence_score,
    ranking_no_bars_error_row,
    ranking_period_dates,
    ranking_period_label,
    ranking_provider_error_rows,
    ranking_purpose_help,
    ranking_symbol_chunks,
    ranking_symbol_options,
    ranking_symbols_state_key,
    ranking_weight_preset_for_purpose,
    ranking_weight_preset_label,
    symbol_candidate_labels,
    symbol_universe_rows,
    valid_ranking_selected_labels,
)
from ui.ranking_state import (
    apply_ranking_filter_state,
    clear_ranking_filter_state,
    current_ranking_filter_state,
    ensure_ranking_selection_widget_state,
    initial_ranking_selected_labels_for_key,
    persist_ranking_filter_state,
    sync_ranking_selection_state,
)
from ui.rebalance_app import (
    MarketDataPreview,
    forecast_consensus_rows_for_bars,
    forecast_metric_csv_download,
    forecast_metric_json_download,
    forecast_reference_period,
    investment_score_csv_download,
    screening_score_rows,
)
from ui.symbol_universe import symbol_universe_csv_rows


def test_default_forecast_horizon_days_uses_chart_period():
    assert default_forecast_horizon_days(date(2026, 5, 1), date(2026, 5, 7)) == 1
    assert default_forecast_horizon_days(date(2026, 5, 1), date(2026, 5, 30)) == 3
    assert default_forecast_horizon_days(date(2026, 1, 1), date(2026, 12, 31)) == 30


def test_market_data_period_dates_support_decision_review_presets():
    end = date(2026, 5, 23)

    assert DEFAULT_MARKET_DATA_PERIOD_PRESET == MARKET_DATA_PERIOD_CUSTOM
    assert next(iter(MARKET_DATA_PERIOD_PRESETS)) == MARKET_DATA_PERIOD_CUSTOM
    assert market_data_period_dates(MARKET_DATA_PERIOD_CUSTOM, end) == (
        date(2025, 5, 23),
        end,
    )
    assert market_data_period_dates("short_1w", end) == (date(2026, 5, 16), end)
    assert market_data_period_dates("short_1m", end) == (date(2026, 4, 23), end)
    assert market_data_period_dates("medium_3m", end) == (date(2026, 2, 23), end)
    assert market_data_period_dates("medium_6m", end) == (date(2025, 11, 23), end)
    assert market_data_period_dates("ytd", end) == (date(2026, 1, 1), end)
    assert market_data_period_dates("long_1y", end) == (date(2025, 5, 23), end)
    assert market_data_period_dates("long_3y", end) == (date(2023, 5, 23), end)
    assert market_data_period_dates("long_5y", end) == (date(2021, 5, 23), end)


def test_market_data_period_dates_clamp_month_end_and_leap_day():
    assert market_data_period_dates("short_1m", date(2026, 3, 31))[0] == date(
        2026,
        2,
        28,
    )
    assert market_data_period_dates("long_1y", date(2024, 2, 29))[0] == date(
        2023,
        2,
        28,
    )


def test_market_data_period_help_explains_review_basis():
    assert "任意の期間" in market_data_period_help(MARKET_DATA_PERIOD_CUSTOM)
    assert "決算" in market_data_period_help("medium_3m")
    assert "長期保有" in market_data_period_help("long_5y")
    assert "任意の期間" in market_data_period_help("unknown")


def test_market_data_provider_defaults_to_yahoo():
    assert default_market_data_provider() == "yahoo"


def test_symbol_from_candidate_extracts_ticker_or_custom():
    assert _symbol_from_candidate("") is None
    assert _symbol_from_candidate("9983.T - Fast Retailing") == "9983.T"


def test_selected_symbol_has_universe_detail_uses_local_master(monkeypatch):
    monkeypatch.setattr(
        "ui.app.symbol_universe_csv_rows",
        lambda: [{"symbol": "9983.T", "name": "Fast Retailing"}],
    )

    assert selected_symbol_has_universe_detail("9983.t")
    assert not selected_symbol_has_universe_detail("MSFT")


def test_ranking_symbols_from_selected_labels_extracts_fetch_symbols():
    assert _ranking_symbols_from_selected_labels(
        ["9983.T - Fast Retailing", "", "AAPL - Apple Inc."]
    ) == ["9983.T", "AAPL"]


def test_name_from_candidate_extracts_display_name():
    assert _name_from_candidate("9983.T - Fast Retailing") == "Fast Retailing"
    assert _name_from_candidate("AAPL") is None


def test_market_data_preview_symbol_label_uses_symbol_and_known_name():
    preview = SimpleNamespace(
        bars=[
            _bar("2026-05-10", symbol="9983.T"),
        ],
        screening_rows=[],
        ohlcv_rows=[],
        quote_rows=[],
        feature_rows=[],
    )

    assert _market_data_preview_symbol_label(preview) == "9983.T - Fast Retailing"


def test_market_data_preview_symbol_label_falls_back_to_rows():
    preview = SimpleNamespace(
        bars=[],
        screening_rows=[{"symbol": "CUSTOM"}],
        ohlcv_rows=[],
        quote_rows=[],
        feature_rows=[],
    )

    assert _market_data_preview_symbol_label(preview) == "CUSTOM"


def test_merged_symbol_candidate_rows_deduplicates_representative_first():
    rows = merged_symbol_candidate_rows(
        [{"symbol": "AAPL", "name": "Apple Inc."}],
        [
            {"symbol": "aapl", "name": "Apple"},
            {"symbol": "MSFT", "name": "Microsoft"},
        ],
    )

    assert rows == [
        {"symbol": "AAPL", "name": "Apple Inc."},
        {"symbol": "MSFT", "name": "Microsoft"},
    ]


def test_symbol_candidate_labels_filter_by_symbol_or_name():
    rows = [
        {"symbol": "9983.T", "name": "Fast Retailing"},
        {"symbol": "AAPL", "name": "Apple Inc."},
    ]

    assert symbol_candidate_labels(rows, "") == [
        "9983.T - Fast Retailing",
        "AAPL - Apple Inc.",
    ]
    assert symbol_candidate_labels(rows, "retail") == ["9983.T - Fast Retailing"]
    assert symbol_candidate_labels(rows, "AAPL") == ["AAPL - Apple Inc."]
    assert symbol_candidate_labels(rows, "missing") == []


def test_cockpit_filtered_symbol_rows_applies_preference_filters(monkeypatch):
    monkeypatch.setattr(
        "ui.app.st.session_state",
        {
            "market_data_cockpit_region": "japan",
            "market_data_cockpit_product_type": "stock",
            "market_data_cockpit_market_cap": "large",
            "market_data_cockpit_nisa": "eligible",
            "market_data_cockpit_per_enabled": True,
            "market_data_cockpit_per_min": "10",
            "market_data_cockpit_per_max": "30",
        },
    )
    rows = [
        {
            "symbol": "7203.T",
            "name": "Toyota",
            "market": "jp",
            "asset_type": "stock",
            "market_cap_tier": "large",
            "nisa_growth_eligible": "true",
            "per": "12",
        },
        {
            "symbol": "9983.T",
            "name": "Fast Retailing",
            "market": "jp",
            "asset_type": "stock",
            "market_cap_tier": "large",
            "nisa_growth_eligible": "true",
            "per": "45",
        },
        {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "market": "us",
            "asset_type": "stock",
            "market_cap_tier": "mega",
            "nisa_growth_eligible": "true",
            "per": "28",
        },
    ]

    assert [row["symbol"] for row in cockpit_filtered_symbol_rows(rows)] == ["7203.T"]


def test_coerce_number_input_state_recovers_string_values(monkeypatch):
    session_state: dict[str, object] = {"market_data_cockpit_per_min": "2.0"}
    monkeypatch.setattr("ui.app.st.session_state", session_state)

    assert _coerce_number_input_state("market_data_cockpit_per_min", "1.0") == 2.0
    assert session_state["market_data_cockpit_per_min"] == 2.0


def test_current_or_default_symbol_labels_uses_first_available_candidate():
    assert _current_or_default_symbol_labels([{"symbol": "9983.T", "name": "Fast Retailing"}]) == [
        "9983.T - Fast Retailing"
    ]
    assert _current_or_default_symbol_labels([]) == [NO_SYMBOL_CANDIDATE_LABEL]


def test_symbol_universe_detail_rows_show_column_labels_and_blank_values():
    assert symbol_universe_detail_rows(
        {
            "symbol": "7203.T",
            "name": "Toyota Motor",
            "dividend_yield_pct": "",
            "custom_field": "custom",
        }
    ) == [
        {"項目": "銘柄コード", "表示値": "7203.T", "CSV列": "symbol", "登録値": "7203.T"},
        {"項目": "銘柄名", "表示値": "Toyota Motor", "CSV列": "name", "登録値": "Toyota Motor"},
        {
            "項目": "配当利回り(%)",
            "表示値": "未登録",
            "CSV列": "dividend_yield_pct",
            "登録値": "-",
        },
        {"項目": "custom_field", "表示値": "custom", "CSV列": "custom_field", "登録値": "custom"},
    ]


def test_symbol_universe_detail_display_value_translates_internal_codes():
    row = {
        "broker": "sbi_securities",
        "metadata_source": "yahoo",
        "dividend_yield_pct": "2.840",
        "market_cap_tier": "large",
        "risk_band": "LOW",
        "yahoo_symbol": "",
    }

    assert symbol_universe_detail_display_value(row, "broker") == "SBI証券"
    assert symbol_universe_detail_display_value(row, "metadata_source") == "Yahoo Finance"
    assert symbol_universe_detail_display_value(row, "dividend_yield_pct") == "2.84%"
    assert symbol_universe_detail_display_value(row, "market_cap_tier").startswith("大型")
    assert symbol_universe_detail_display_value(row, "risk_band") == "低変動（β < 0.8目安）"
    assert symbol_universe_detail_display_value(row, "yahoo_symbol") == "表示銘柄と同じ"


def test_symbol_universe_overview_rows_use_user_friendly_values():
    row = {
        "market": "jp",
        "asset_type": "stock",
        "currency": "JPY",
        "broker": "sbi_securities",
        "tradability": "unknown",
        "nisa_category": "growth",
        "nisa_growth_eligible": "true",
        "nisa_tsumitate_eligible": "false",
        "investment_style": "lump_sum",
        "theme": "financial",
        "sector": "financial",
        "is_leveraged": "false",
        "is_inverse": "false",
    }

    rows = symbol_universe_overview_rows(row)

    assert {"項目": "取扱元", "内容": "SBI証券"} in rows
    assert {"項目": "NISA", "内容": "成長投資枠"} in rows
    assert {"項目": "投資スタイル", "内容": "一括投資向き"} in rows
    assert {"項目": "レバレッジ/インバース", "内容": "該当なし"} in rows


def test_symbol_universe_investment_and_fund_rows_are_sectioned():
    stock_row = {
        "dividend_yield_pct": "2.61",
        "dividend_category": "dividend",
        "per": "9.05",
        "pbr": "0.66",
        "roe_pct": "7.74",
        "market_cap_tier": "large",
        "risk_band": "LOW",
        "data_quality": "OK",
        "asset_type": "stock",
        "nisa_growth_eligible": "true",
    }
    etf_row = {
        "asset_type": "etf",
        "index_family": "sp500",
        "expense_ratio_pct": "0.09",
        "complexity": "beginner",
        "nisa_growth_eligible": "true",
    }

    assert {"項目": "配当利回り", "内容": "2.61%"} in symbol_universe_investment_metric_rows(
        stock_row
    )
    assert symbol_universe_fund_detail_rows(stock_row) == []
    assert {"項目": "連動指数", "内容": "S&P 500"} in symbol_universe_fund_detail_rows(etf_row)
    assert {"項目": "成長投資枠", "内容": "はい"} in symbol_universe_fund_detail_rows(etf_row)


def test_symbol_universe_nisa_display_combines_category_and_flags():
    assert (
        symbol_universe_nisa_display(
            {
                "nisa_category": "unknown",
                "nisa_growth_eligible": "true",
                "nisa_tsumitate_eligible": "false",
            }
        )
        == "成長投資枠"
    )


def test_symbol_universe_key_metric_rows_use_compact_values():
    rows = symbol_universe_key_metric_rows(
        {
            "asset_type": "stock",
            "nisa_category": "both",
            "dividend_yield_pct": "4.79",
            "market_cap_tier": "mid",
            "risk_band": "LOW",
            "nisa_growth_eligible": "true",
            "nisa_tsumitate_eligible": "true",
        }
    )

    assert {"項目": "NISA", "内容": "両枠"} in rows
    assert {"項目": "時価総額", "内容": "中型（JP 1,000億〜1兆円 / US $2B〜$10B）"} in rows
    assert {"項目": "配当利回り", "内容": "4.79%"} in rows


def test_symbol_universe_data_info_rows_explain_how_values_are_used():
    rows = symbol_universe_data_info_rows(
        {
            "metadata_source": "yahoo",
            "metadata_as_of": "2026-05-21",
            "metadata_updated_at": "2026-05-21T00:00:00+09:00",
            "yahoo_symbol": "",
        }
    )

    assert {
        "項目": "データ出所",
        "内容": "Yahoo Finance",
        "使い道": "指標や分類をどの情報源で補完したかを確認します。",
    } in rows
    assert rows[-1]["項目"] == "価格取得用ticker"
    assert rows[-1]["内容"] == "表示銘柄と同じ"
    assert "Yahoo取得時" in rows[-1]["使い道"]


def test_symbol_detail_dialog_css_expands_width_and_wraps_metric_values():
    assert "90vw" in SYMBOL_DETAIL_DIALOG_CSS
    assert "1100px" in SYMBOL_DETAIL_DIALOG_CSS
    assert '[data-testid="stMetricValue"]' in SYMBOL_DETAIL_DIALOG_CSS
    assert "overflow-wrap: anywhere" in SYMBOL_DETAIL_DIALOG_CSS
    assert ".symbol-detail-table" in SYMBOL_DETAIL_DIALOG_CSS
    assert "table-layout: fixed" in SYMBOL_DETAIL_DIALOG_CSS


def test_symbol_detail_table_html_wraps_and_escapes_long_text():
    markup = symbol_detail_table_html(
        [
            {
                "観点": "次の行動",
                "内容": "銘柄データとコックピットで価格トレンドを確認してください",
                "確認ポイント": "<script>売買推奨ではありません</script>",
            }
        ]
    )

    assert 'class="symbol-detail-table"' in markup
    assert "銘柄データとコックピット" in markup
    assert "<script>" not in markup
    assert "&lt;script&gt;" in markup


def test_ranking_result_aggrid_options_enable_single_row_click_selection():
    options = ranking_result_aggrid_options(
        [
            {
                "順位": "1",
                "銘柄": "8174.T",
                "銘柄名": "日本瓦斯",
                "総合スコア": "80.1",
                "補足": "深掘り候補です",
            }
        ]
    )

    assert options["rowSelection"] == "single"
    assert options["suppressRowClickSelection"] is False
    assert options["suppressCellFocus"] is True
    column_defs = {column["field"]: column for column in options["columnDefs"]}
    assert column_defs["順位"]["pinned"] == "left"
    assert column_defs["銘柄"]["pinned"] == "left"
    assert column_defs["補足"]["tooltipField"] == "補足"


def test_ranking_result_grid_custom_css_keeps_dark_table_readable():
    assert RANKING_RESULT_GRID_CUSTOM_CSS[".ag-root-wrapper"]["background-color"] == (
        "#121821 !important"
    )
    assert RANKING_RESULT_GRID_CUSTOM_CSS[".ag-header-cell-text"]["color"] == ("#e5edf7 !important")
    assert RANKING_RESULT_GRID_CUSTOM_CSS[".ag-row-even"]["background-color"] == (
        "#151d29 !important"
    )
    assert RANKING_RESULT_GRID_CUSTOM_CSS[".ag-row-odd"]["background-color"] == (
        "#111923 !important"
    )


def test_ranking_detail_symbol_from_aggrid_response_handles_dataframe_and_dict():
    selected_rows = pd.DataFrame([{"銘柄": "8174.T", "銘柄名": "日本瓦斯"}])
    response = SimpleNamespace(selected_rows=selected_rows)

    assert ranking_detail_symbol_from_aggrid_response(response) == "8174.T"
    assert ranking_detail_symbol_from_aggrid_response({"selected_rows": [{"銘柄": "5015.T"}]}) == (
        "5015.T"
    )
    assert (
        ranking_detail_symbol_from_aggrid_response({"eventData": {"data": {"銘柄": "9502.T"}}})
        == "9502.T"
    )
    assert ranking_detail_symbol_from_aggrid_response(SimpleNamespace(selected_rows=None)) is None
    assert ranking_detail_symbol_from_aggrid_response({"selected_rows": []}) is None


def test_ranking_detail_event_token_tracks_row_clicks():
    response = {
        "eventData": {
            "streamlitRerunEventTriggerName": "rowClicked",
            "rowIndex": 3,
            "event": {"timeStamp": 12345},
        }
    }

    assert ranking_detail_event_token_from_aggrid_response(response, "8174.T") == (
        "rowClicked|8174.T|3|12345"
    )
    assert ranking_detail_event_token_from_aggrid_response({}, "8174.T") == ("selection|8174.T")
    assert ranking_detail_event_token_from_aggrid_response(response, None) is None


def test_ranking_detail_symbol_to_open_only_changes_on_new_click_event():
    assert ranking_detail_symbol_to_open("8174.T", "event-1", None) == "8174.T"
    assert ranking_detail_symbol_to_open("8174.T", "event-1", "event-1") is None
    assert ranking_detail_symbol_to_open("8174.T", "event-2", "event-1") == "8174.T"
    assert ranking_detail_symbol_to_open(None, "event-2", "event-1") is None


def test_ranking_result_grid_key_and_height_are_stable():
    assert _ranking_result_grid_key("ranking") == "ranking_grid"
    assert _ranking_result_grid_height([{"銘柄": "8174.T"}]) == 150
    assert _ranking_result_grid_height([{"銘柄": str(index)} for index in range(20)]) == 520


def test_ranking_result_table_base_key_changes_with_result_source():
    assert _ranking_result_table_base_key("source-a", "balanced") == (
        _ranking_result_table_base_key("source-a", "balanced")
    )
    assert _ranking_result_table_base_key("source-a", "balanced") != (
        _ranking_result_table_base_key("source-b", "balanced")
    )


def test_symbol_universe_rows_adds_static_selection_metadata():
    rows = symbol_universe_rows(
        [
            {"symbol": "7203.T", "name": "Toyota Motor"},
            {"symbol": "SPY", "name": "SPDR S&P 500 ETF"},
        ]
    )

    assert rows[0]["market"] == "jp"
    assert rows[0]["currency"] == "JPY"
    assert rows[1]["asset_type"] == "etf"
    assert rows[1]["theme"] == "index"
    assert "installment" in rows[1]["tags"]


def test_symbol_universe_csv_rows_provide_extensible_selection_metadata():
    rows = symbol_universe_rows()
    row_by_symbol = {row["symbol"]: row for row in rows}

    assert len(symbol_universe_csv_rows()) >= 80
    assert row_by_symbol["7203.T"]["market"] == "jp"
    assert row_by_symbol["7203.T"]["currency"] == "JPY"
    assert row_by_symbol["AAPL"]["theme"] == "technology"
    assert "growth" in row_by_symbol["AAPL"]["tags"]
    assert row_by_symbol["SPY"]["asset_type"] == "etf"
    assert row_by_symbol["SPY"]["index_family"] == "sp500"
    assert row_by_symbol["AAPL"]["per"]
    assert row_by_symbol["AAPL"]["pbr"]
    assert row_by_symbol["AAPL"]["roe_pct"]
    assert row_by_symbol["AAPL"]["consensus_rating"]
    assert row_by_symbol["AAPL"]["risk_band"]


def test_filter_symbol_universe_rows_uses_fetch_before_conditions():
    rows = symbol_universe_rows(
        [
            {"symbol": "7203.T", "name": "Toyota Motor"},
            {"symbol": "AAPL", "name": "Apple Inc."},
            {"symbol": "SPY", "name": "SPDR S&P 500 ETF"},
            {"symbol": "NVDA", "name": "NVIDIA"},
        ]
    )

    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            purpose="installment",
            market="etf",
            asset_type="etf",
            currency="USD",
            theme="index",
        )
    ] == ["SPY"]
    assert [
        row["symbol"] for row in filter_symbol_universe_rows(rows, purpose="growth", limit=2)
    ] == ["AAPL", "NVDA"]
    assert [row["symbol"] for row in filter_symbol_universe_rows(rows, query="toyota")] == [
        "7203.T"
    ]


def test_filter_symbol_universe_rows_applies_ranking_universe_policy():
    rows = symbol_universe_rows(
        [
            {
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "asset_type": "stock",
                "broker": "sbi_securities",
                "tradability": "unknown",
                "is_sbi_supported": "true",
                "is_active": "true",
                "is_leveraged": "false",
                "is_inverse": "false",
            },
            {"symbol": "BADFX", "name": "FX Product", "asset_type": "fx"},
            {
                "symbol": "LEVER",
                "name": "Leveraged ETF",
                "asset_type": "etf",
                "is_leveraged": "true",
            },
            {
                "symbol": "UNTRAD",
                "name": "Unavailable Stock",
                "asset_type": "stock",
                "tradability": "not_tradable",
            },
            {
                "symbol": "NOSBI",
                "name": "Unsupported Stock",
                "asset_type": "stock",
                "is_sbi_supported": "false",
            },
        ]
    )

    assert [row["symbol"] for row in filter_symbol_universe_rows(rows)] == ["AAPL"]


def test_filter_symbol_universe_rows_finds_curated_dividend_candidates():
    rows = symbol_universe_rows(
        [
            {"symbol": "9432.T", "name": "Nippon Telegraph and Telephone"},
            {"symbol": "8058.T", "name": "Mitsubishi Corporation"},
            {"symbol": "NVDA", "name": "NVIDIA"},
        ]
    )

    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            purpose="dividend",
            market="jp",
            dividend_category="high_dividend",
        )
    ] == ["9432.T", "8058.T"]


def test_filter_symbol_universe_rows_finds_us_dividend_candidates():
    rows = symbol_universe_rows(
        [
            {"symbol": "AAPL", "name": "Apple Inc."},
            {"symbol": "PFE", "name": "Pfizer"},
            {"symbol": "NVDA", "name": "NVIDIA"},
        ]
    )

    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            purpose="dividend",
            market="us",
            asset_type="stock",
        )
    ] == ["AAPL", "PFE"]


def test_filter_symbol_universe_rows_filters_by_dividend_yield_database_value():
    rows = symbol_universe_rows(
        [
            {"symbol": "AAPL", "name": "Apple Inc."},
            {"symbol": "PFE", "name": "Pfizer"},
            {"symbol": "NVDA", "name": "NVIDIA"},
        ]
    )

    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            market="us",
            asset_type="stock",
            dividend_yield_enabled=True,
            min_dividend_yield_pct="3.0",
        )
    ] == ["PFE"]


def test_filter_symbol_universe_rows_uses_explicit_dividend_range_over_category():
    rows = symbol_universe_rows(
        [
            {
                "symbol": "RANGE",
                "name": "Range Match",
                "dividend_category": "dividend",
                "dividend_yield_pct": "4.0",
            },
            {
                "symbol": "CATEGORY",
                "name": "Category Only",
                "dividend_category": "high_dividend",
                "dividend_yield_pct": "2.5",
            },
        ]
    )

    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            dividend_category="high_dividend",
            dividend_yield_enabled=True,
            min_dividend_yield_pct="3.0",
            dividend_yield_max_pct="5.0",
        )
    ] == ["RANGE"]


def test_filter_symbol_universe_rows_ignores_dividend_range_when_disabled():
    rows = symbol_universe_rows(
        [
            {"symbol": "AAPL", "name": "Apple Inc."},
            {"symbol": "PFE", "name": "Pfizer"},
            {"symbol": "NVDA", "name": "NVIDIA"},
        ]
    )

    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            market="us",
            asset_type="stock",
            dividend_yield_enabled=False,
            min_dividend_yield_pct="3.0",
        )
    ] == ["AAPL", "PFE", "NVDA"]


def test_filter_symbol_universe_rows_filters_by_metric_ranges():
    rows = symbol_universe_rows(
        [
            {"symbol": "7203.T", "name": "Toyota Motor"},
            {"symbol": "AAPL", "name": "Apple Inc."},
            {"symbol": "PFE", "name": "Pfizer"},
        ]
    )

    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            per_enabled=True,
            per_min="2.0",
            per_max="20.0",
            pbr_enabled=True,
            pbr_min="0.5",
            pbr_max="3.0",
            dividend_yield_enabled=True,
            min_dividend_yield_pct="0.0",
            dividend_yield_max_pct="10.0",
            roe_enabled=True,
            roe_min_pct="8.0",
            roe_max_pct="30.0",
            consensus_enabled=True,
            consensus_min="2.5",
            consensus_max="5.0",
        )
    ] == ["7203.T", "PFE"]


def test_filter_symbol_universe_rows_filters_etf_database_values():
    rows = symbol_universe_rows(
        [
            {"symbol": "SPY", "name": "SPDR S&P 500 ETF"},
            {"symbol": "QQQ", "name": "Invesco QQQ Trust"},
            {"symbol": "VOO", "name": "Vanguard S&P 500 ETF"},
        ]
    )

    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            market="etf",
            asset_type="etf",
            index_family="sp500",
            max_expense_ratio_pct="0.05",
        )
    ] == ["VOO"]


def test_filter_symbol_universe_rows_filters_by_sector_theme_and_jpx_market_cap():
    rows = symbol_universe_rows(
        [
            {"symbol": "1301.T", "name": "極洋"},
            {"symbol": "1332.T", "name": "ニッスイ"},
            {"symbol": "1414.T", "name": "ショーボンドホールディングス"},
        ]
    )

    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            region="japan",
            product_type="stock",
            theme="industrial",
        )
    ] == ["1414.T"]
    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            region="japan",
            product_type="stock",
            market_cap_tier="small",
        )
    ] == ["1301.T"]
    assert "small" in RANKING_MARKET_CAP_LABELS
    assert "industrial" in RANKING_THEME_LABELS


def test_ranking_filter_labels_show_quantitative_thresholds():
    assert RANKING_MARKET_CAP_LABELS["mega"] == "超大型（JP 10兆円以上 / US $200B以上）"
    assert RANKING_MARKET_CAP_LABELS["small"] == "小型（JP 100億〜1,000億円 / US $300M〜$2B）"
    assert RANKING_DIVIDEND_LABELS["high_dividend"] == "配当利回り 3%以上"
    assert RANKING_DIVIDEND_LABELS["dividend"] == "配当利回り 0%超〜3%未満"
    assert "bond" in RANKING_THEME_LABELS
    assert "dividend" not in RANKING_THEME_LABELS
    assert "$200B/$10B/$2B/$300M" in RANKING_FILTER_HELP_TEXTS["market_cap"]
    assert "0%超〜3%未満" in RANKING_FILTER_HELP_TEXTS["dividend_category"]


def test_normalize_dividend_filter_values_keeps_conditions_mutually_exclusive():
    assert normalize_dividend_filter_values(
        dividend_category="high_dividend",
        dividend_yield_enabled=True,
        min_dividend_yield_pct="3.2",
        dividend_yield_max_pct="8.0",
    ) == ("all", "3.2", True, "8.0")
    assert normalize_dividend_filter_values(
        dividend_category="high_dividend",
        dividend_yield_enabled=False,
        min_dividend_yield_pct="3.2",
        dividend_yield_max_pct="8.0",
    ) == ("high_dividend", "0.0", False, "10.0")


def test_ranking_etf_filter_labels_cover_imported_index_families():
    assert {
        "bond",
        "commodity",
        "dividend",
        "dow_jones",
        "emerging",
        "msci_world",
        "reit",
        "sector",
        "topix",
        "nikkei225",
    } <= set(RANKING_INDEX_FAMILY_LABELS)


def test_filter_symbol_universe_rows_ignores_hidden_etf_filters_for_stock():
    rows = symbol_universe_rows(
        [
            {"symbol": "AAPL", "name": "Apple Inc."},
            {"symbol": "SPY", "name": "SPDR S&P 500 ETF"},
        ]
    )

    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            region="all",
            product_type="stock",
            index_family="sp500",
            max_expense_ratio_pct="0.05",
            complexity="beginner",
        )
    ] == ["AAPL"]


def test_filter_symbol_universe_rows_ignores_hidden_stock_filters_for_etf():
    rows = symbol_universe_rows(
        [
            {"symbol": "AAPL", "name": "Apple Inc."},
            {"symbol": "SPY", "name": "SPDR S&P 500 ETF"},
        ]
    )

    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            region="all",
            product_type="etf",
            theme="technology",
            market_cap_tier="large",
            per_enabled=True,
            per_min="2.0",
            per_max="3.0",
            pbr_enabled=True,
            pbr_min="0.5",
            pbr_max="0.6",
            roe_enabled=True,
            roe_min_pct="20.0",
            roe_max_pct="30.0",
        )
    ] == ["SPY"]


def test_filter_symbol_universe_rows_preserves_etf_region():
    rows = symbol_universe_rows(
        [
            {"symbol": "1306.T", "name": "NEXT FUNDS TOPIX ETF"},
            {"symbol": "VOO", "name": "Vanguard S&P 500 ETF"},
        ]
    )

    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            region="japan",
            product_type="etf",
        )
    ] == ["1306.T"]
    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            region="us",
            product_type="etf",
        )
    ] == ["VOO"]


def test_filter_symbol_universe_rows_filters_by_nisa_eligibility():
    rows = symbol_universe_rows(
        [
            {"symbol": "7203.T", "name": "Toyota Motor"},
            {"symbol": "6861.T", "name": "Keyence"},
            {"symbol": "TSLA", "name": "Tesla"},
            {"symbol": "VOO", "name": "Vanguard S&P 500 ETF"},
        ]
    )

    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            nisa_eligibility="growth",
        )
    ] == ["7203.T", "6861.T", "TSLA", "VOO"]


def test_filter_symbol_universe_rows_filters_nisa_non_eligible_etfs():
    rows = symbol_universe_rows(
        [
            {
                "symbol": "GROWTH",
                "name": "Growth ETF",
                "market": "us",
                "asset_type": "etf",
                "theme": "index",
                "nisa_category": "growth",
                "nisa_growth_eligible": "true",
                "nisa_tsumitate_eligible": "false",
            },
            {
                "symbol": "OUT",
                "name": "Non NISA ETF",
                "market": "us",
                "asset_type": "etf",
                "theme": "index",
                "nisa_category": "none",
                "nisa_growth_eligible": "false",
                "nisa_tsumitate_eligible": "false",
            },
        ]
    )

    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            region="us",
            product_type="etf",
            nisa_eligibility="none",
        )
    ] == ["OUT"]


def test_ranking_nisa_labels_match_stock_etf_scope():
    assert RANKING_NISA_ELIGIBILITY_LABELS == {
        "all": "指定なし（NISAで絞らない）",
        "eligible": "NISA対象のみ（成長投資枠）",
        "none": "NISA対象外のみ",
    }
    assert "growth" not in RANKING_NISA_ELIGIBILITY_LABELS
    assert "tsumitate" not in RANKING_NISA_ELIGIBILITY_LABELS
    assert "both" not in RANKING_NISA_ELIGIBILITY_LABELS


def test_selectbox_state_resets_legacy_nisa_choice_from_saved_filters(monkeypatch):
    for legacy_value in ("growth", "tsumitate", "both"):
        session_state = {
            "market_data_ranking_filters": {
                "market_data_ranking_nisa": legacy_value,
            }
        }
        monkeypatch.setattr("ui.app.st.session_state", session_state)

        _ensure_selectbox_state_value(
            "market_data_ranking_nisa",
            list(RANKING_NISA_ELIGIBILITY_LABELS),
        )

        assert session_state["market_data_ranking_nisa"] == "all"


def test_dividend_filter_state_prefers_explicit_range_when_both_saved(monkeypatch):
    session_state = {
        "market_data_ranking_filters": {
            "market_data_ranking_dividend": "high_dividend",
            "market_data_ranking_dividend_enabled": "true",
        }
    }
    monkeypatch.setattr("ui.app.st.session_state", session_state)

    _normalize_dividend_filter_state()

    assert session_state["market_data_ranking_dividend"] == "all"
    assert "market_data_ranking_dividend_enabled" not in session_state


def test_filter_symbol_universe_rows_excludes_commodity_etfs_from_mvp_ranking():
    rows = symbol_universe_rows([{"symbol": "1540.T", "name": "Japan Physical Gold ETF"}])

    assert filter_symbol_universe_rows(rows, product_type="etf") == []


def test_filter_symbol_universe_rows_excludes_mutual_funds_from_mvp_ranking():
    rows = symbol_universe_rows()

    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            product_type="mutual_fund",
        )
    ] == []
    assert all(row["asset_type"] != "mutual_fund" for row in filter_symbol_universe_rows(rows))


def test_filter_symbol_universe_rows_supports_internal_risk_metadata_filter():
    rows = symbol_universe_rows(
        [
            {"symbol": "7203.T", "name": "Toyota Motor", "risk_band": "LOW"},
            {"symbol": "AAPL", "name": "Apple Inc.", "risk_band": "MEDIUM"},
            {"symbol": "TM", "name": "Toyota Motor ADR"},
            {"symbol": "NVDA", "name": "NVIDIA", "risk_band": "HIGH"},
            {"symbol": "SPY", "name": "SPDR S&P 500 ETF", "risk_band": "MEDIUM"},
        ]
    )

    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            region="japan",
            product_type="stock",
            risk_band="LOW",
        )
    ] == ["7203.T"]
    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            region="us",
            product_type="stock",
            risk_band=RANKING_BETA_RISK_STANDARD_OR_LOWER,
        )
    ] == ["AAPL"]
    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            region="us",
            product_type="stock",
        )
    ] == ["AAPL", "NVDA"]
    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            region="us",
            product_type="etf",
        )
    ] == ["SPY"]
    assert (
        filter_symbol_universe_rows(
            rows,
            region="other_global",
            product_type="stock",
        )
        == []
    )


def test_ranking_detail_filters_change_by_region_and_product():
    japan_stock = ranking_detail_filters_for_category("japan", "stock")
    us_stock = ranking_detail_filters_for_category("us", "stock")
    etf = ranking_detail_filters_for_category("japan", "etf")
    mutual_fund = ranking_detail_filters_for_category("japan", "mutual_fund")

    assert "pbr" in japan_stock
    assert "risk_band" in japan_stock
    assert "risk_band" in us_stock
    assert "nisa_eligibility" in us_stock
    assert "benchmark_index" in etf
    assert "pbr" not in etf
    assert mutual_fund == []
    assert ranking_weight_preset_for_purpose("stability") == "stability_profile"
    assert "moving_average_signal" in RANKING_INVESTMENT_STYLE_METRICS["trend"]


def test_advanced_ranking_purposes_have_profiles_and_help_text():
    assert ranking_weight_preset_for_purpose(RANKING_PURPOSE_MULTI_FACTOR) == (
        "multi_factor_profile"
    )
    assert ranking_weight_preset_for_purpose(RANKING_PURPOSE_QUALITY_GROWTH) == (
        RANKING_PRESET_QUALITY_GROWTH
    )
    assert ranking_weight_preset_for_purpose(RANKING_PURPOSE_ETF_CORE_COST) == (
        RANKING_PRESET_ETF_CORE_COST
    )
    assert ranking_weight_preset_for_purpose(RANKING_PURPOSE_SUSTAINABLE_INCOME) == (
        RANKING_PRESET_SUSTAINABLE_INCOME
    )
    assert "ROE" in ranking_purpose_help(RANKING_PURPOSE_QUALITY_GROWTH)
    assert "減配リスク" in ranking_purpose_help(RANKING_PURPOSE_SUSTAINABLE_INCOME)
    assert "経費率" in ranking_purpose_help(RANKING_PURPOSE_ETF_CORE_COST)
    assert "roe" in RANKING_INVESTMENT_STYLE_METRICS[RANKING_PURPOSE_QUALITY_GROWTH]
    assert "expense_ratio" in RANKING_INVESTMENT_STYLE_METRICS[RANKING_PURPOSE_ETF_CORE_COST]


def test_beta_risk_filter_labels_explain_thresholds():
    assert RANKING_BETA_RISK_LABELS[RANKING_BETA_RISK_STANDARD_OR_LOWER] == ("標準以下（β <= 1.2）")
    assert "β 0.8未満" in RANKING_FILTER_HELP_TEXTS["risk_band"]
    assert "1.2超" in RANKING_FILTER_HELP_TEXTS["risk_band"]


def test_filter_symbol_universe_rows_searches_japanese_aliases():
    rows = symbol_universe_rows(
        [
            {"symbol": "7203.T", "name": "Toyota Motor"},
            {"symbol": "AAPL", "name": "Apple Inc."},
        ]
    )

    assert [row["symbol"] for row in filter_symbol_universe_rows(rows, query="トヨタ")] == [
        "7203.T"
    ]


def test_ranking_filter_signature_changes_when_conditions_change():
    base = ranking_filter_signature(
        region="us",
        product_type="stock",
        ranking_purpose="dividend",
        purpose="dividend",
        period_preset="short",
        market="us",
        asset_type="stock",
        currency="all",
        dividend_category="all",
        complexity="standard",
        theme="all",
        query="",
        limit=6,
    )
    changed = ranking_filter_signature(
        region="japan",
        product_type="stock",
        ranking_purpose="dividend",
        purpose="dividend",
        period_preset="short",
        market="jp",
        asset_type="stock",
        currency="all",
        dividend_category="all",
        complexity="standard",
        theme="all",
        query="",
        limit=6,
    )

    assert base != changed


def test_ranking_filter_signature_includes_ranking_classification():
    base = ranking_filter_signature(
        region="japan",
        product_type="stock",
        ranking_purpose="dividend",
        purpose="all",
        period_preset="short",
        market="all",
        asset_type="all",
        currency="all",
        dividend_category="all",
        complexity="standard",
        theme="all",
        query="",
        limit=6,
    )
    changed = ranking_filter_signature(
        region="japan",
        product_type="stock",
        ranking_purpose="growth",
        purpose="all",
        period_preset="short",
        market="all",
        asset_type="all",
        currency="all",
        dividend_category="all",
        complexity="standard",
        theme="all",
        query="",
        limit=6,
    )

    assert base != changed


def test_ranking_filter_signature_includes_investment_style():
    base = ranking_filter_signature(
        product_type="stock",
        ranking_purpose="dividend",
        purpose="all",
        period_preset="short",
        market="all",
        asset_type="all",
        currency="all",
        dividend_category="all",
        complexity="standard",
        theme="all",
        query="",
        limit=6,
    )
    changed = ranking_filter_signature(
        product_type="stock",
        ranking_purpose="trend",
        purpose="all",
        period_preset="short",
        market="all",
        asset_type="all",
        currency="all",
        dividend_category="all",
        complexity="standard",
        theme="all",
        query="",
        limit=6,
    )

    assert base != changed


def test_ranking_filter_signature_includes_nisa_filter():
    base = ranking_filter_signature(
        purpose="dividend",
        period_preset="short",
        market="us",
        asset_type="stock",
        currency="all",
        dividend_category="all",
        complexity="standard",
        nisa_eligibility="all",
        theme="all",
        query="",
        limit=6,
    )
    changed = ranking_filter_signature(
        purpose="dividend",
        period_preset="short",
        market="us",
        asset_type="stock",
        currency="all",
        dividend_category="all",
        complexity="standard",
        nisa_eligibility="growth",
        theme="all",
        query="",
        limit=6,
    )

    assert base != changed


def test_ranking_filter_signature_ignores_hidden_etf_filters_for_stock():
    base = ranking_filter_signature(
        region="all",
        product_type="stock",
        ranking_purpose="dividend",
        purpose="all",
        period_preset="short",
        market="all",
        asset_type="all",
        currency="all",
        dividend_category="all",
        index_family="all",
        max_expense_ratio_pct="1.00",
        complexity="standard",
        theme="all",
        query="",
        limit=0,
    )
    changed = ranking_filter_signature(
        region="all",
        product_type="stock",
        ranking_purpose="dividend",
        purpose="all",
        period_preset="short",
        market="all",
        asset_type="all",
        currency="all",
        dividend_category="all",
        index_family="sp500",
        max_expense_ratio_pct="0.05",
        complexity="beginner",
        theme="all",
        query="",
        limit=0,
    )

    assert base == changed


def test_ranking_filter_signature_ignores_hidden_stock_filters_for_etf():
    base = ranking_filter_signature(
        region="all",
        product_type="etf",
        ranking_purpose="dividend",
        purpose="all",
        period_preset="short",
        market="all",
        asset_type="all",
        currency="all",
        dividend_category="all",
        market_cap_tier="all",
        complexity="standard",
        theme="all",
        query="",
        limit=0,
    )
    changed = ranking_filter_signature(
        region="all",
        product_type="etf",
        ranking_purpose="dividend",
        purpose="all",
        period_preset="short",
        market="all",
        asset_type="all",
        currency="all",
        dividend_category="all",
        market_cap_tier="large",
        complexity="standard",
        theme="technology",
        query="",
        per_enabled=True,
        per_min="2.0",
        per_max="3.0",
        pbr_enabled=True,
        pbr_min="0.5",
        pbr_max="0.6",
        roe_enabled=True,
        roe_min_pct="20.0",
        roe_max_pct="30.0",
        limit=0,
    )

    assert base == changed


def test_ranking_filter_signature_ignores_period_preset():
    base = ranking_filter_signature(
        purpose="dividend",
        period_preset="short",
        market="us",
        asset_type="stock",
        currency="all",
        dividend_category="all",
        complexity="standard",
        theme="all",
        query="",
        limit=6,
    )
    changed = ranking_filter_signature(
        purpose="dividend",
        period_preset="long",
        market="us",
        asset_type="stock",
        currency="all",
        dividend_category="all",
        complexity="standard",
        theme="all",
        query="",
        limit=6,
    )

    assert base == changed


def test_ranking_filter_signature_normalizes_inactive_dividend_side():
    category_only = ranking_filter_signature(
        region="japan",
        product_type="stock",
        ranking_purpose="dividend",
        purpose="all",
        period_preset="short",
        market="all",
        asset_type="all",
        currency="all",
        dividend_category="high_dividend",
        min_dividend_yield_pct="3.2",
        dividend_yield_enabled=False,
        dividend_yield_max_pct="8.0",
        complexity="standard",
        theme="all",
        query="",
        limit=0,
    )
    explicit_range = ranking_filter_signature(
        region="japan",
        product_type="stock",
        ranking_purpose="dividend",
        purpose="all",
        period_preset="short",
        market="all",
        asset_type="all",
        currency="all",
        dividend_category="high_dividend",
        min_dividend_yield_pct="3.2",
        dividend_yield_enabled=True,
        dividend_yield_max_pct="8.0",
        complexity="standard",
        theme="all",
        query="",
        limit=0,
    )

    assert "high_dividend|0.0" in category_only
    assert "|all|3.2|" in explicit_range


def test_ranking_comparison_summary_shows_period_and_selection_status():
    assert ranking_comparison_summary(
        start=date(2026, 5, 11),
        end=date(2026, 5, 18),
        candidate_count=46,
        selected_count=46,
    ) == {
        "period": "2026-05-11 〜 2026-05-18",
        "candidate": "46件",
        "selected": "46 / 46件",
        "status": "全候補を比較",
        "inline": "取得期間: 2026-05-11 〜 2026-05-18 / 候補: 46件 / 選択: 46 / 46件（全候補を比較）",
    }
    assert (
        ranking_comparison_summary(
            start=date(2026, 5, 11),
            end=date(2026, 5, 18),
            candidate_count=46,
            selected_count=12,
        )["status"]
        == "一部を比較"
    )
    assert (
        ranking_comparison_summary(
            start=date(2026, 5, 11),
            end=date(2026, 5, 18),
            candidate_count=0,
            selected_count=0,
        )["status"]
        == "候補なし"
    )


def test_ranking_symbols_state_key_uses_filter_signature():
    signature = ranking_filter_signature(
        purpose="all",
        period_preset="short",
        market="jp",
        asset_type="stock",
        currency="JPY",
        dividend_category="all",
        complexity="standard",
        theme="all",
        query="toyota",
        limit=6,
    )

    assert ranking_symbols_state_key(signature) == f"market_data_ranking_symbols_{signature}"


def test_ranking_build_cache_key_ignores_weight_preset():
    first = ranking_build_cache_key(
        provider="yahoo",
        symbols=["AAPL", "MSFT"],
        start=date(2026, 5, 10),
        end=date(2026, 5, 17),
    )
    second = ranking_build_cache_key(
        provider="yahoo",
        symbols=["AAPL", "MSFT"],
        start=date(2026, 5, 10),
        end=date(2026, 5, 17),
    )

    assert first == second


def test_ranking_source_key_for_selection_matches_actual_fetch_symbols():
    source_key = _ranking_source_key_for_selection(
        provider="yahoo",
        selected_labels=["AAPL - Apple Inc.", "MSFT - Microsoft"],
        start=date(2026, 5, 10),
        end=date(2026, 5, 17),
    )

    assert source_key == ranking_build_cache_key(
        provider="yahoo",
        symbols=["AAPL", "MSFT"],
        start=date(2026, 5, 10),
        end=date(2026, 5, 17),
    )
    assert (
        _ranking_source_key_for_selection(
            provider="yahoo",
            selected_labels=[],
            start=date(2026, 5, 10),
            end=date(2026, 5, 17),
        )
        == ""
    )


def test_ranking_result_matches_current_selection_detects_stale_results():
    stored_source = ranking_build_cache_key(
        provider="yahoo",
        symbols=["AAPL"],
        start=date(2026, 5, 10),
        end=date(2026, 5, 17),
    )

    assert _ranking_result_matches_current_selection(
        stored_source,
        provider="yahoo",
        selected_labels=["AAPL - Apple Inc."],
        start=date(2026, 5, 10),
        end=date(2026, 5, 17),
    )
    assert not _ranking_result_matches_current_selection(
        stored_source,
        provider="yahoo",
        selected_labels=["MSFT - Microsoft"],
        start=date(2026, 5, 10),
        end=date(2026, 5, 17),
    )
    assert not _ranking_result_matches_current_selection(
        stored_source,
        provider="yahoo",
        selected_labels=[],
        start=date(2026, 5, 10),
        end=date(2026, 5, 17),
    )


def test_ranking_build_cache_reuses_rows_for_same_market_data_request(monkeypatch):
    session_state: dict[str, object] = {}
    monkeypatch.setattr("ui.app.st.session_state", session_state)
    cache_key = ranking_build_cache_key(
        provider="mock",
        symbols=["AAPL"],
        start=date(2026, 5, 10),
        end=date(2026, 5, 17),
    )
    rows = [{"symbol": "AAPL", "total_score": "70"}]
    error_rows = [{"symbol": "ERR", "message": "failed"}]

    set_cached_ranking_build(cache_key, rows=rows, error_rows=error_rows)

    assert get_cached_ranking_build(cache_key) == (rows, error_rows)
    assert get_cached_ranking_build("missing") is None


def test_ranking_filter_state_persists_modal_values_after_widget_cleanup(monkeypatch):
    session_state: dict[str, object] = {
        "market_data_ranking_min_dividend": "3.0",
        "market_data_ranking_market": "jp",
    }
    monkeypatch.setattr("ui.ranking_state.st.session_state", session_state)

    filters = persist_ranking_filter_state()
    session_state.pop("market_data_ranking_min_dividend")
    session_state.pop("market_data_ranking_market")

    assert filters["market_data_ranking_min_dividend"] == "3.0"
    assert current_ranking_filter_state()["market_data_ranking_min_dividend"] == "3.0"
    assert current_ranking_filter_state()["market_data_ranking_market"] == "jp"


def test_clear_ranking_filter_state_resets_visible_filters_and_result_state(monkeypatch):
    session_state: dict[str, object] = {
        "market_data_ranking_currency": "USD",
        "market_data_ranking_nisa": "growth",
        "market_data_ranking_symbol_query": "toyota",
        "market_data_ranking_rows": [{"symbol": "AAPL"}],
        "market_data_ranking_error_rows": [{"symbol": "ERR"}],
        "market_data_ranking_selected_labels": ["AAPL - Apple Inc."],
    }
    monkeypatch.setattr("ui.ranking_state.st.session_state", session_state)

    clear_ranking_filter_state()

    assert session_state["market_data_ranking_currency"] == "all"
    assert session_state["market_data_ranking_nisa"] == "all"
    assert session_state["market_data_ranking_symbol_query"] == ""
    assert "market_data_ranking_rows" not in session_state
    assert "market_data_ranking_error_rows" not in session_state
    assert "market_data_ranking_selected_labels" not in session_state


def test_valid_ranking_selected_labels_keeps_only_available_options():
    assert valid_ranking_selected_labels(
        ["7203.T - Toyota Motor", "OLD - Removed"],
        ["7203.T - Toyota Motor", "9983.T - Fast Retailing"],
    ) == ["7203.T - Toyota Motor"]


def test_initial_ranking_selected_labels_defaults_to_all_matching_candidates():
    labels = ["7203.T - Toyota Motor", "9983.T - Fast Retailing"]

    assert initial_ranking_selected_labels(labels, []) == labels
    assert initial_ranking_selected_labels(labels, ["7203.T - Toyota Motor"]) == [
        "7203.T - Toyota Motor"
    ]


def test_initial_ranking_selected_labels_for_new_filter_key_uses_all_candidates(monkeypatch):
    session_state: dict[str, object] = {}
    monkeypatch.setattr("ui.ranking_state.st.session_state", session_state)
    labels = ["7203.T - Toyota Motor", "9983.T - Fast Retailing"]

    assert (
        initial_ranking_selected_labels_for_key(
            selection_key="market_data_ranking_symbols_new",
            labels=labels,
            stored_selected_labels=["7203.T - Toyota Motor"],
        )
        == labels
    )


def test_initial_ranking_selected_labels_for_existing_key_keeps_user_selection(monkeypatch):
    session_state: dict[str, object] = {"market_data_ranking_symbols_existing": []}
    monkeypatch.setattr("ui.ranking_state.st.session_state", session_state)
    labels = ["7203.T - Toyota Motor", "9983.T - Fast Retailing"]

    assert initial_ranking_selected_labels_for_key(
        selection_key="market_data_ranking_symbols_existing",
        labels=labels,
        stored_selected_labels=["7203.T - Toyota Motor"],
    ) == ["7203.T - Toyota Motor"]


def test_ensure_ranking_selection_widget_state_initializes_new_key_with_all_candidates(
    monkeypatch,
):
    session_state: dict[str, object] = {}
    monkeypatch.setattr("ui.ranking_state.st.session_state", session_state)
    labels = ["7203.T - Toyota Motor", "9983.T - Fast Retailing"]

    ensure_ranking_selection_widget_state(
        selection_key="market_data_ranking_symbols_new",
        labels=labels,
        stored_selected_labels=[],
    )

    assert session_state["market_data_ranking_symbols_new"] == labels
    assert session_state["market_data_ranking_selected_labels"] == labels


def test_ensure_ranking_selection_widget_state_preserves_existing_user_selection(monkeypatch):
    session_state: dict[str, object] = {
        "market_data_ranking_symbols_existing": ["7203.T - Toyota Motor"]
    }
    monkeypatch.setattr("ui.ranking_state.st.session_state", session_state)

    ensure_ranking_selection_widget_state(
        selection_key="market_data_ranking_symbols_existing",
        labels=["7203.T - Toyota Motor", "9983.T - Fast Retailing"],
        stored_selected_labels=[],
    )

    assert session_state["market_data_ranking_symbols_existing"] == ["7203.T - Toyota Motor"]
    assert "market_data_ranking_selected_labels" not in session_state


def test_ensure_ranking_selection_widget_state_removes_stale_options(monkeypatch):
    session_state: dict[str, object] = {
        "market_data_ranking_symbols_existing": [
            "7203.T - Toyota Motor",
            "OLD - Removed",
        ]
    }
    monkeypatch.setattr("ui.ranking_state.st.session_state", session_state)

    ensure_ranking_selection_widget_state(
        selection_key="market_data_ranking_symbols_existing",
        labels=["7203.T - Toyota Motor", "9983.T - Fast Retailing"],
        stored_selected_labels=[],
    )

    assert session_state["market_data_ranking_symbols_existing"] == ["7203.T - Toyota Motor"]


def test_sync_ranking_selection_state_updates_widget_and_persistent_state(monkeypatch):
    session_state: dict[str, object] = {}
    monkeypatch.setattr("ui.ranking_state.st.session_state", session_state)

    sync_ranking_selection_state(
        "market_data_ranking_symbols_test",
        ["7203.T - Toyota Motor"],
        update_widget_state=True,
    )

    assert session_state["market_data_ranking_selected_labels"] == ["7203.T - Toyota Motor"]
    assert session_state["market_data_ranking_symbols_test"] == ["7203.T - Toyota Motor"]


def test_sync_ranking_selection_state_can_skip_widget_state(monkeypatch):
    session_state: dict[str, object] = {"market_data_ranking_symbols_test": ["OLD"]}
    monkeypatch.setattr("ui.ranking_state.st.session_state", session_state)

    sync_ranking_selection_state(
        "market_data_ranking_symbols_test",
        ["7203.T - Toyota Motor"],
    )

    assert session_state["market_data_ranking_selected_labels"] == ["7203.T - Toyota Motor"]
    assert session_state["market_data_ranking_symbols_test"] == ["OLD"]


def test_apply_ranking_filter_state_selects_filtered_candidates(monkeypatch):
    session_state = {
        "market_data_ranking_rows": [{"symbol": "OLD"}],
        "market_data_ranking_error_rows": [{"symbol": "ERR"}],
        "market_data_ranking_filter_dialog_open": True,
    }
    monkeypatch.setattr("ui.ranking_state.st.session_state", session_state)
    preview_rows = [
        {"symbol": "7203.T", "name": "Toyota Motor"},
        {"symbol": "9983.T", "name": "Fast Retailing"},
    ]
    signature = "all|short|jp|stock|JPY|all|0.0|all|all|1.00|standard|all||2"

    apply_ranking_filter_state(preview_rows, signature)

    assert session_state["market_data_ranking_filter_signature"] == signature
    assert session_state["market_data_ranking_selected_labels"] == [
        "7203.T - Toyota Motor",
        "9983.T - Fast Retailing",
    ]
    assert session_state[ranking_symbols_state_key(signature)] == [
        "7203.T - Toyota Motor",
        "9983.T - Fast Retailing",
    ]
    assert "market_data_ranking_rows" not in session_state
    assert "market_data_ranking_error_rows" not in session_state
    assert session_state["market_data_ranking_filter_dialog_open"] is False


def test_ranking_period_dates_use_beginner_presets():
    end = date(2026, 5, 17)

    assert ranking_period_label("short") == "短期: 1週間"
    assert ranking_period_dates("short", end) == (date(2026, 5, 10), end)
    assert ranking_period_dates("medium", end) == (date(2026, 4, 17), end)
    assert ranking_period_dates("long", end) == (date(2025, 5, 17), end)
    assert "短期は直近の値動き" in RANKING_FILTER_HELP_TEXTS["period"]
    assert "安定性" in RANKING_FILTER_HELP_TEXTS["period"]


def test_build_market_data_ranking_rows_fetches_symbols_concurrently(monkeypatch):
    async def fail_fast_path(*args, **kwargs):
        raise DataSourceError("batch unavailable")

    active_count = 0
    max_active_count = 0

    monkeypatch.setattr("ui.app._build_market_data_ranking_rows_fast", fail_fast_path)

    async def fake_build_market_data_preview(
        *,
        symbol,
        start,
        end,
        provider_override,
        forecast_horizon_days,
    ):
        nonlocal active_count, max_active_count
        active_count += 1
        max_active_count = max(max_active_count, active_count)
        await asyncio.sleep(0)
        active_count -= 1
        return SimpleNamespace(
            investment_score_rows=[
                {
                    "symbol": symbol,
                    "total_score": "70",
                    "screening_score": "70",
                    "forecast_agreement": "70",
                    "data_quality": "100",
                }
            ],
            error_rows=[],
        )

    monkeypatch.setattr(
        "ui.app.build_market_data_preview",
        fake_build_market_data_preview,
    )
    progress_messages: list[str] = []

    rows, error_rows = asyncio.run(
        _build_market_data_ranking_rows(
            ["7203.T", "9983.T", "6758.T"],
            start=date(2026, 5, 10),
            end=date(2026, 5, 17),
            provider="mock",
            progress_callback=lambda message, _ratio: progress_messages.append(message),
        )
    )

    assert [row["symbol"] for row in rows] == ["7203.T", "9983.T", "6758.T"]
    assert error_rows == []
    assert max_active_count > 1
    assert any("銘柄別に取得しています" in message for message in progress_messages)


def test_build_market_data_ranking_rows_does_not_retry_live_batch_failure(monkeypatch):
    async def fail_fast_path(*args, **kwargs):
        raise DataSourceError("batch unavailable", details={"provider": "yahoo"})

    async def fail_preview(*args, **kwargs):
        raise AssertionError("live provider failures should not retry per-symbol previews")

    monkeypatch.setattr("ui.app._build_market_data_ranking_rows_fast", fail_fast_path)
    monkeypatch.setattr("ui.app.build_market_data_preview", fail_preview)
    progress_messages: list[str] = []

    rows, error_rows = asyncio.run(
        _build_market_data_ranking_rows(
            ["7203.T", "9983.T"],
            start=date(2026, 5, 10),
            end=date(2026, 5, 17),
            provider="yahoo",
            progress_callback=lambda message, _ratio: progress_messages.append(message),
        )
    )

    assert rows == []
    assert error_rows == [
        {
            "symbol": "7203.T, 9983.T",
            "code": "APP-2000",
            "message": "batch unavailable",
            "details": '{"provider": "yahoo", "symbols": ["7203.T", "9983.T"]}',
        }
    ]
    assert progress_messages[-1] == "Yahoo live data の一括取得に失敗しました。"


def test_ranking_provider_error_rows_summarizes_many_symbols():
    rows = ranking_provider_error_rows(
        "yahoo",
        [f"SYM{i}" for i in range(10)],
        DataSourceError("failed", details={"request": {"operation": "fetch_ohlcv"}}),
    )

    assert rows[0]["symbol"] == "SYM0, SYM1, SYM2, SYM3, SYM4, SYM5, SYM6, SYM7, ... (+2)"
    details = json.loads(rows[0]["details"])
    assert details["provider"] == "yahoo"
    assert details["request"]["operation"] == "fetch_ohlcv"


def test_build_market_data_ranking_rows_uses_batch_fast_path(monkeypatch):
    class FakeBatchAdapter:
        def __init__(self) -> None:
            self.ohlcv_calls = 0
            self.fundamental_calls = 0

        async def fetch_ohlcv(self, symbols, start, end, interval="1d"):
            self.ohlcv_calls += 1
            bars = []
            for symbol in symbols:
                contract = Symbol(
                    raw=symbol,
                    exchange="NASDAQ",
                    code=symbol,
                    currency="USD",
                )
                for day in range(30):
                    close = Decimal("100") + Decimal(day)
                    bars.append(
                        Bar(
                            symbol=contract,
                            ts=datetime(2026, 4, day + 1, tzinfo=UTC),
                            open=close,
                            high=close + Decimal("1"),
                            low=close - Decimal("1"),
                            close=close,
                            volume=Decimal("1000000"),
                            interval=interval,
                            provider="fake",
                        )
                    )
            return bars

        async def fetch_fundamentals(self, symbols, as_of):
            self.fundamental_calls += 1
            return [
                FundamentalSnapshot(
                    symbol=symbol,
                    as_of=as_of,
                    provider="fake",
                    dividend_yield=Decimal("0.03"),
                    market_cap_jpy=Decimal("1000000000000"),
                )
                for symbol in symbols
            ]

        def healthcheck(self):
            return {"provider": "fake", "status": "ok"}

    adapter = FakeBatchAdapter()

    async def fail_preview(*args, **kwargs):
        raise AssertionError("slow preview path should not be used")

    monkeypatch.setattr(
        "ui.app.create_market_data_provider_adapter",
        lambda _: adapter,
    )
    monkeypatch.setattr("ui.app.build_market_data_preview", fail_preview)

    rows, error_rows = asyncio.run(
        _build_market_data_ranking_rows(
            ["AAA", "BBB"],
            start=date(2026, 4, 20),
            end=date(2026, 4, 30),
            provider="mock",
        )
    )

    assert adapter.ohlcv_calls == 1
    assert adapter.fundamental_calls == 1
    assert [row["symbol"] for row in rows] == ["AAA", "BBB"]
    assert error_rows == []


def test_build_market_data_ranking_rows_reports_no_bars_details(monkeypatch):
    class FakePartialBatchAdapter:
        async def fetch_ohlcv(self, symbols, start, end, interval="1d"):
            bars = []
            for symbol in symbols:
                if symbol == "MISSING":
                    continue
                contract = Symbol(raw=symbol, exchange="NASDAQ", code=symbol, currency="USD")
                for day in range(30):
                    close = Decimal("100") + Decimal(day)
                    bars.append(
                        Bar(
                            symbol=contract,
                            ts=datetime(2026, 4, day + 1, tzinfo=UTC),
                            open=close,
                            high=close + Decimal("1"),
                            low=close - Decimal("1"),
                            close=close,
                            volume=Decimal("1000000"),
                            interval=interval,
                            provider="fake",
                        )
                    )
            return bars

        async def fetch_fundamentals(self, symbols, as_of):
            return [
                FundamentalSnapshot(
                    symbol=symbol,
                    as_of=as_of,
                    provider="fake",
                    dividend_yield=Decimal("0.03"),
                    market_cap_jpy=Decimal("1000000000000"),
                )
                for symbol in symbols
            ]

        def healthcheck(self):
            return {"provider": "fake", "status": "ok"}

    monkeypatch.setattr(
        "ui.app.create_market_data_provider_adapter",
        lambda _: FakePartialBatchAdapter(),
    )

    rows, error_rows = asyncio.run(
        _build_market_data_ranking_rows(
            ["AAA", "MISSING"],
            start=date(2026, 4, 20),
            end=date(2026, 4, 30),
            provider="mock",
        )
    )

    assert [row["symbol"] for row in rows] == ["AAA"]
    assert error_rows[0]["symbol"] == "MISSING"
    assert error_rows[0]["code"] == "RANKING-NO-BARS"
    assert error_rows[0]["message"] == (
        "価格データを取得できなかったため、ランキングから除外しました。"
    )
    details = json.loads(error_rows[0]["details"])
    assert details["provider"] == "mock"
    assert details["symbol"] == "MISSING"
    assert details["request"]["display_start"] == "2026-04-20"
    assert details["request"]["display_end"] == "2026-04-30"
    assert details["request"]["operation"] == "ranking_fetch_ohlcv"
    assert details["reason"] == "no_ohlcv_rows"


def test_ranking_symbol_chunks_split_large_builds():
    symbols = [f"SYM{i}" for i in range(53)]

    chunks = ranking_symbol_chunks(symbols)

    assert [len(chunk) for chunk in chunks] == [10, 10, 10, 10, 10, 3]
    assert [symbol for chunk in chunks for symbol in chunk] == symbols


def test_live_ranking_symbol_warning_message_only_warns_for_large_live_requests():
    assert live_ranking_symbol_warning_message("mock", 80) is None
    assert live_ranking_symbol_warning_message("yahoo", 30) is None
    assert live_ranking_symbol_warning_message("yahoo", 31) == (
        "yahoo は外部通信のため、31 銘柄のランキング作成には時間がかかる場合があります。"
        "通信が不安定な場合は、取得期間を短くするか、比較する銘柄を絞って再実行してください。"
    )


def test_ranking_symbol_options_and_label_support_deep_dive():
    rows = [
        {"symbol": "AAPL", "total_score": "80"},
        {"symbol": "aapl", "total_score": "70"},
        {"symbol": "7203.T", "total_score": "60"},
        {"symbol": "", "total_score": "50"},
    ]

    assert ranking_symbol_options(rows) == ["AAPL", "7203.T"]
    assert symbol_candidate_label("AAPL") == "AAPL - Apple Inc."
    assert symbol_candidate_label("UNKNOWN") == "UNKNOWN"


def test_ranking_deep_dive_default_symbol_resets_for_new_result_source():
    rows = [
        {"symbol": "TOP", "total_score": "90"},
        {"symbol": "OLD", "total_score": "70"},
    ]

    assert (
        ranking_deep_dive_default_symbol(
            rows,
            current_symbol="OLD",
            source_key="new-ranking",
            current_source_key="old-ranking",
        )
        == "TOP"
    )
    assert (
        ranking_deep_dive_default_symbol(
            rows,
            current_symbol="OLD",
            source_key="same-ranking",
            current_source_key="same-ranking",
        )
        == "OLD"
    )
    assert (
        ranking_deep_dive_default_symbol(
            rows,
            current_symbol="REMOVED",
            source_key="same-ranking",
            current_source_key="same-ranking",
        )
        == "TOP"
    )


def test_forecast_reference_period_uses_horizon_and_bar_count():
    bars = [_bar(f"2026-05-{day:02d}") for day in range(1, 31)]

    assert forecast_reference_period(bars, horizon_days=1) == 3
    assert forecast_reference_period(bars, horizon_days=5) == 10
    assert forecast_reference_period(bars[:3], horizon_days=5) == 3


def test_forecast_consensus_rows_and_display_are_beginner_friendly():
    rows = forecast_consensus_rows_for_bars(
        [_bar(f"2026-05-{day:02d}", close=100 + day) for day in range(1, 8)]
    )

    assert rows == [
        {
            "symbol": "AAPL",
            "horizon_days": "1",
            "model_count": "3",
            "ensemble_forecast_close": "107.0096",
            "median_forecast_close": "107",
            "min_forecast_close": "106",
            "max_forecast_close": "108.0288",
            "forecast_range": "2.0288",
            "forecast_range_pct": "1.90%",
            "agreement": "MEDIUM",
        }
    ]
    assert forecast_consensus_display_rows(rows) == [
        {
            "銘柄": "AAPL",
            "予測日数": "1",
            "モデル数": "3",
            "平均予測": "107.0096",
            "中央値予測": "107",
            "予測下限": "106",
            "予測上限": "108.0288",
            "予測の開き": "2.0288",
            "予測の開き(%)": "1.90%",
            "モデル一致度": "中くらい",
        }
    ]


def test_forecast_chart_summary_explains_agreement_and_range():
    messages = forecast_chart_summary(
        [
            {
                "symbol": "AAPL",
                "horizon_days": "1",
                "model_count": "3",
                "forecast_range_pct": "1.90%",
                "agreement": "MEDIUM",
            }
        ],
        [
            {
                "model": "naive",
                "symbol": "AAPL",
                "horizon_days": "1",
                "forecast_close": "107",
                "mae": "1.23",
                "rmse": "1.50",
                "direction_accuracy": "50.00%",
                "sample_count": "6",
            }
        ],
    )

    assert messages[0] == "3 つの予測モデルの見方は「中くらい」です。予測の開きは 1.90% です。"
    assert messages[1] == (
        "実線はこれまでの価格、点線はモデルごとの予測です。"
        "点線同士が近いほど、モデルの見方が近い状態です。"
    )
    assert "予測: 直近値維持" in messages[2]


def test_investment_score_display_rows_are_beginner_friendly():
    rows = investment_score_display_rows(
        [
            {
                "rank": "1",
                "symbol": "AAPL",
                "total_score": "73",
                "score_band": "BALANCED",
                "screening_score": "80",
                "forecast_agreement_score": "40",
                "data_quality_score": "100",
                "risk_signal_score": "",
                "warnings": "model_disagreement:high",
                "note": "売買推奨ではなく、判断材料を整理したスコアです。",
            }
        ]
    )

    assert rows == [
        {
            "順位": "1",
            "銘柄": "AAPL",
            "銘柄名": "Apple Inc.",
            "総合スコア": "73",
            "見方": "バランス型",
            "DB適合": "",
            "Screening": "80",
            "予測一致": "40",
            "データ品質": "100",
            "DB信頼度": "",
            "Risk": "未接続",
            "注意点": "モデルの見方が割れています",
            "補足": rows[0]["補足"],
        }
    ]
    assert "モデルの見方が割れています" in rows[0]["補足"]


def test_investment_score_display_rows_reuses_symbol_universe_lookup(monkeypatch):
    calls = 0

    def fake_symbol_universe_rows() -> list[dict[str, str]]:
        nonlocal calls
        calls += 1
        return [{"symbol": "6857.T", "asset_type": "stock", "roe_pct": "25"}]

    monkeypatch.setattr("ui.app.symbol_universe_csv_rows", fake_symbol_universe_rows)

    rows = investment_score_display_rows(
        [
            {"symbol": "6857.T", "forecast_agreement_score": "90"},
            {"symbol": "9983.T", "forecast_agreement_score": "90"},
        ]
    )

    assert len(rows) == 2
    assert calls == 1


def test_ranking_investment_note_uses_scores_and_symbol_metadata(monkeypatch):
    monkeypatch.setattr(
        "ui.app.symbol_universe_csv_rows",
        lambda: [
            {
                "symbol": "6857.T",
                "asset_type": "stock",
                "per": "52.42",
                "pbr": "28.93",
                "roe_pct": "57.65",
                "dividend_yield_pct": "0.23",
            }
        ],
    )

    note = ranking_investment_note(
        {
            "symbol": "6857.T",
            "screening_score": "88",
            "forecast_agreement_score": "90",
            "data_quality_score": "100",
            "risk_signal_score": "60",
            "warnings": "",
        }
    )

    assert "予測一致" in note
    assert "データ品質" in note
    assert "PER/PBR" in note
    assert "成長期待" in note


def test_ranking_investment_detail_rows_adds_modal_guidance():
    rows = ranking_investment_detail_rows(
        {
            "総合スコア": "84.69",
            "予測一致": "90",
            "データ品質": "100",
            "Risk": "72.44",
            "注意点": "",
            "補足": "予測一致とデータ品質が強みの候補です。",
        },
        {
            "asset_type": "stock",
            "dividend_yield_pct": "0.23",
            "dividend_category": "dividend",
            "per": "52.42",
            "pbr": "28.93",
            "roe_pct": "57.65",
        },
    )

    assert rows[0]["観点"] == "ランキング上位理由"
    assert any(row["観点"] == "バリュエーション" and "PER" in row["内容"] for row in rows)
    assert rows[-1]["確認ポイント"] == "売買推奨ではなく、深掘り順と確認観点の整理です。"


def test_investment_score_summary_lines_explain_score_without_recommendation():
    lines = investment_score_summary_lines(
        {
            "銘柄": "AAPL",
            "見方": "バランス型",
            "注意点": "モデルの見方が割れています",
            "補足": "売買推奨ではなく、判断材料を整理したスコアです。",
        }
    )

    assert lines == [
        "AAPL は「バランス型」として確認できます。",
        "注意点: モデルの見方が割れています。",
        "売買推奨ではなく、判断材料を整理したスコアです。",
    ]


def test_score_component_rows_builds_cockpit_breakdown():
    assert score_component_rows(
        {
            "Screening": "80",
            "予測一致": "40",
            "Risk": "70",
            "データ品質": "100",
        }
    ) == [
        {"要素": "Screening", "スコア": "80"},
        {"要素": "Forecast", "スコア": "40"},
        {"要素": "Risk", "スコア": "70"},
        {"要素": "Data Quality", "スコア": "100"},
    ]


def test_cockpit_detail_summary_rows_lift_key_closed_details():
    preview = MarketDataPreview(
        status="ok",
        bars=[_bar("2026-05-01", close=100), _bar("2026-05-02", close=105)],
        provider_rows=[],
        quote_rows=[
            {
                "symbol": "AAPL",
                "exchange": "NASDAQ",
                "bid": "-",
                "ask": "-",
                "last": "105",
                "ts": "2026-05-02T00:00:00+00:00",
            }
        ],
        ohlcv_rows=[
            {
                "symbol": "AAPL",
                "bars": "2",
                "first_ts": "2026-05-01T00:00:00+00:00",
                "last_ts": "2026-05-02T00:00:00+00:00",
                "total_volume": "2000",
            }
        ],
        price_chart_rows=[],
        forecast_chart_rows=[],
        forecast_metric_rows=[],
        fx_rows=[],
        feature_rows=[
            {
                "return_1d": "5%",
                "momentum_5d": "8%",
                "drawdown_20d": "-3%",
                "data_completeness": "100%",
                "data_quality": "OK",
                "missing_summary": "なし",
            }
        ],
        investment_score_rows=[],
        screening_rows=[
            {
                "total_score": "82",
                "momentum_score": "75",
                "liquidity_score": "90",
                "risk_score": "70",
                "summary": "モメンタムと流動性が確認できます。",
            }
        ],
        error_rows=[],
    )

    rows = cockpit_detail_summary_rows(
        preview,
        [
            {
                "ensemble_forecast_close": "108",
                "min_forecast_close": "102",
                "max_forecast_close": "112",
                "forecast_range_pct": "9.5%",
            }
        ],
        [{"model": "moving_average", "rmse": "1.2", "sample_count": "5"}],
    )

    assert [row["観点"] for row in rows] == [
        "直近価格",
        "取得期間",
        "予測レンジ",
        "スクリーニング",
        "短期特徴量",
        "データ品質",
        "予測評価",
    ]
    assert "105" in rows[0]["内容"]
    assert "2本" in rows[1]["内容"]
    assert "9.5%" in rows[2]["内容"]
    assert rows[3]["確認ポイント"] == "モメンタムと流動性が確認できます。"


def test_cockpit_period_evaluation_rows_change_by_period_length():
    short_rows = cockpit_period_evaluation_rows(
        [_bar("2026-05-01", close=100), _bar("2026-05-08", close=108)]
    )
    long_rows = cockpit_period_evaluation_rows(
        [_bar("2023-05-01", close=100), _bar("2026-05-01", close=130)]
    )

    assert short_rows[0]["見方"] == "7日間 / 短期反応の確認"
    assert "ノイズ" in short_rows[0]["確認ポイント"]
    assert short_rows[1]["見方"] == "+8.0% / 上昇優位"
    assert short_rows[2]["見方"] == "期間レンジ内 100.0% / 高値圏"
    assert long_rows[0]["見方"] == "1096日間 / 長期耐性の確認"
    assert "複数決算期" in long_rows[0]["確認ポイント"]


def test_cockpit_investment_memo_rows_combines_score_master_and_price(monkeypatch):
    monkeypatch.setattr(
        "ui.app.symbol_universe_csv_rows",
        lambda: [
            {
                "symbol": "6857.T",
                "asset_type": "stock",
                "dividend_yield_pct": "0.23",
                "dividend_category": "dividend",
                "per": "52.42",
                "pbr": "28.93",
                "roe_pct": "57.65",
            }
        ],
    )
    preview = MarketDataPreview(
        status="ok",
        bars=[
            _bar("2026-05-01", close=100, symbol="6857.T"),
            _bar("2026-05-02", close=112, symbol="6857.T"),
        ],
        provider_rows=[],
        quote_rows=[],
        ohlcv_rows=[],
        price_chart_rows=[],
        forecast_chart_rows=[],
        forecast_metric_rows=[],
        fx_rows=[],
        feature_rows=[],
        investment_score_rows=[],
        screening_rows=[],
        error_rows=[],
    )

    rows = cockpit_investment_memo_rows(
        preview,
        {
            "銘柄": "6857.T",
            "総合スコア": "84.69",
            "見方": "強め",
            "Screening": "78.9",
            "予測一致": "90",
            "データ品質": "100",
            "Risk": "72.44",
            "注意点": "",
        },
    )

    assert [row["観点"] for row in rows] == [
        "スコア解釈",
        "主な注意点",
        "バリュエーション",
        "インカム",
        "価格トレンド",
        "次の確認",
    ]
    assert "ROEが高く" in rows[0]["評価"]
    assert "PER 52.42" in rows[2]["評価"]
    assert "配当利回り 0.23%" in rows[3]["評価"]
    assert "高値圏" in rows[4]["評価"]
    assert rows[0]["確認ポイント"] == "スコアは深掘り順の整理で、売買推奨ではありません。"


def test_cockpit_decision_report_context_includes_metadata_confidence(monkeypatch):
    monkeypatch.setattr(
        "ui.app.symbol_universe_csv_rows",
        lambda: [
            {
                "symbol": "6857.T",
                "name": "Advantest",
                "asset_type": "stock",
                "market": "jp",
                "currency": "JPY",
                "nisa_category": "growth",
                "investment_style": "lump_sum",
                "metadata_source": "yahoo",
                "metadata_as_of": "2026-05-22",
                "dividend_yield_pct": "0.22",
                "dividend_category": "low",
                "per": "52.42",
                "pbr": "28.93",
                "roe_pct": "57.65",
                "market_cap_tier": "mega",
            }
        ],
    )
    preview = MarketDataPreview(
        status="ok",
        bars=[
            _bar("2026-05-21", close=100, symbol="6857.T"),
            _bar("2026-05-22", close=101, symbol="6857.T"),
        ],
        provider_rows=[{"field": "provider", "value": "yahoo"}],
        quote_rows=[],
        ohlcv_rows=[],
        price_chart_rows=[],
        forecast_chart_rows=[],
        forecast_metric_rows=[],
        fx_rows=[],
        feature_rows=[],
        investment_score_rows=[
            {
                "symbol": "6857.T",
                "total_score": "84.69",
                "score_band": "strong",
                "screening_score": "78.9",
                "forecast_agreement_score": "90",
                "data_quality_score": "100",
                "risk_signal_score": "72.44",
            }
        ],
        screening_rows=[],
        error_rows=[],
    )

    context = build_cockpit_decision_report_context(preview)
    markdown = decision_report_markdown_download(context)
    payload = decision_report_json_download(context)

    assert context.title == "投資判断レポート - 6857.T"
    assert [section.title for section in context.sections] == [
        "データ取得状況と信頼性",
        "銘柄メタデータ",
        "スコア分解",
        "バリュエーション / インカム / リスク",
        "確認ポイント",
    ]
    assert "risk_band" in context.sections[0].summary["missing_fields"]
    assert "データ取得状況と信頼性" in markdown
    assert '"schema_version": "decision-report-context-v1"' in payload


def test_ranking_decision_report_context_limits_rows_and_uses_top_symbol(monkeypatch):
    monkeypatch.setattr(
        "ui.app.symbol_universe_csv_rows",
        lambda: [
            {
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "asset_type": "stock",
                "market": "us",
                "currency": "USD",
                "nisa_category": "growth",
                "investment_style": "lump_sum",
                "metadata_source": "yahoo",
                "metadata_as_of": "2026-05-22",
                "dividend_yield_pct": "0.5",
                "dividend_category": "low",
                "per": "28",
                "pbr": "5",
                "roe_pct": "22",
                "market_cap_tier": "mega",
                "risk_band": "standard",
            }
        ],
    )
    rows = [
        {
            "rank": str(index + 1),
            "symbol": "AAPL" if index == 0 else f"TEST{index}",
            "total_score": "80",
            "score_band": "strong",
            "screening_score": "70",
            "forecast_agreement_score": "90",
            "data_quality_score": "100",
            "risk_signal_score": "60",
            "note": "review candidate",
        }
        for index in range(25)
    ]

    context = build_ranking_decision_report_context(
        ranked_rows=rows,
        provider="yahoo",
        start=date(2026, 5, 1),
        end=date(2026, 5, 22),
        ranking_purpose="成長重視",
        weight_preset="予測一致重視",
        comparison_summary="候補: 25件",
    )

    ranking_section = next(
        section for section in context.sections if section.title == "ランキング文脈"
    )
    assert ranking_section.summary["reported_rows"] == "20 / 25"
    assert ranking_section.rows[0]["symbol"] == "AAPL"
    assert "note" not in ranking_section.rows[0]
    assert ranking_section.rows[0]["review_point"].startswith("スコアとデータ品質")
    assert "ランキング結果" in context.title


def test_rank_investment_score_rows_sorts_and_reassigns_rank():
    assert rank_investment_score_rows(
        [
            {"rank": "1", "symbol": "LOW", "total_score": "50"},
            {"rank": "1", "symbol": "HIGH", "total_score": "90"},
        ]
    ) == [
        {"rank": "1", "symbol": "HIGH", "total_score": "90"},
        {"rank": "2", "symbol": "LOW", "total_score": "50"},
    ]


def test_apply_ranking_weight_preset_reweights_and_sorts_rows():
    rows = apply_ranking_weight_preset(
        [
            {
                "rank": "1",
                "symbol": "QUALITY",
                "total_score": "70",
                "score_band": "BALANCED",
                "screening_score": "60",
                "forecast_agreement_score": "50",
                "data_quality_score": "100",
                "risk_signal_score": "60",
                "warnings": "",
            },
            {
                "rank": "2",
                "symbol": "FORECAST",
                "total_score": "70",
                "score_band": "BALANCED",
                "screening_score": "60",
                "forecast_agreement_score": "100",
                "data_quality_score": "50",
                "risk_signal_score": "60",
                "warnings": "",
            },
        ],
        "forecast",
        {
            "QUALITY": {
                "symbol": "QUALITY",
                "metadata_source": "curated_csv",
                "metadata_as_of": "2026-05-18",
                "asset_type": "stock",
                "nisa_category": "growth",
                "market_cap_tier": "large",
                "dividend_yield_pct": "1.2",
                "dividend_category": "dividend",
                "risk_band": "MEDIUM",
                "per": "18",
                "pbr": "1.4",
                "roe_pct": "12",
            },
            "FORECAST": {
                "symbol": "FORECAST",
                "metadata_source": "curated_csv",
                "metadata_as_of": "2026-05-18",
                "asset_type": "stock",
                "nisa_category": "growth",
                "market_cap_tier": "large",
                "dividend_yield_pct": "1.2",
                "dividend_category": "dividend",
                "risk_band": "MEDIUM",
                "per": "18",
                "pbr": "1.4",
                "roe_pct": "12",
            },
        },
    )

    assert rows[0]["symbol"] == "FORECAST"
    assert rows[0]["rank"] == "1"
    assert rows[0]["total_score"] == "75.75"
    assert rows[0]["score_band"] == "STRONG"
    assert rows[0]["database_fit_score"] == "85"
    assert rows[0]["metadata_confidence_score"] == "100"
    assert rows[0]["note"] == (
        "予測一致重視の条件に合いやすい候補です。売買推奨ではなく、根拠確認の優先順です。"
    )
    assert rows[1]["symbol"] == "QUALITY"
    assert ranking_weight_preset_label("forecast") == "予測一致重視"


def _ranking_score_row(symbol: str) -> dict[str, str]:
    return {
        "rank": "1",
        "symbol": symbol,
        "total_score": "50",
        "score_band": "BALANCED",
        "screening_score": "50",
        "forecast_agreement_score": "50",
        "data_quality_score": "50",
        "risk_signal_score": "50",
        "warnings": "",
    }


def _stock_symbol_metadata(
    symbol: str,
    *,
    dividend_yield_pct: str = "1.0",
    market_cap_tier: str = "large",
    per: str = "25",
    pbr: str = "2.5",
    roe_pct: str = "8",
    risk_band: str = "MEDIUM",
    nisa_category: str = "growth",
) -> dict[str, str]:
    return {
        "symbol": symbol,
        "metadata_source": "curated_csv",
        "metadata_as_of": "2026-05-18",
        "asset_type": "stock",
        "is_active": "true",
        "nisa_category": nisa_category,
        "market_cap_tier": market_cap_tier,
        "dividend_yield_pct": dividend_yield_pct,
        "dividend_category": (
            "high_dividend" if Decimal(dividend_yield_pct) >= Decimal("3") else "dividend"
        ),
        "risk_band": risk_band,
        "per": per,
        "pbr": pbr,
        "roe_pct": roe_pct,
    }


def _etf_symbol_metadata(
    symbol: str,
    *,
    dividend_yield_pct: str = "0",
    expense_ratio_pct: str = "0.50",
    complexity: str = "standard",
    index_family: str = "sp500",
    nisa_category: str = "growth",
) -> dict[str, str]:
    return {
        "symbol": symbol,
        "metadata_source": "curated_csv",
        "metadata_as_of": "2026-05-18",
        "asset_type": "etf",
        "is_active": "true",
        "nisa_category": nisa_category,
        "dividend_yield_pct": dividend_yield_pct,
        "dividend_category": (
            "high_dividend" if Decimal(dividend_yield_pct) >= Decimal("3") else "dividend"
        ),
        "risk_band": "MEDIUM",
        "index_family": index_family,
        "expense_ratio_pct": expense_ratio_pct,
        "complexity": complexity,
    }


def test_advanced_stock_ranking_profiles_change_order_by_metadata_fit():
    symbol_rows = {
        "GROWTH": _stock_symbol_metadata(
            "GROWTH", roe_pct="24", per="32", pbr="5", risk_band="HIGH"
        ),
        "VALUE": _stock_symbol_metadata(
            "VALUE", market_cap_tier="small", roe_pct="12", per="10", pbr="0.9", risk_band="MEDIUM"
        ),
        "INCOME": _stock_symbol_metadata(
            "INCOME",
            market_cap_tier="small",
            dividend_yield_pct="4.0",
            per="18",
            pbr="1.1",
            risk_band="MEDIUM",
        ),
        "LOWVOL": _stock_symbol_metadata(
            "LOWVOL", market_cap_tier="mega", dividend_yield_pct="2.0", risk_band="LOW"
        ),
        "SMALL": _stock_symbol_metadata(
            "SMALL", market_cap_tier="small", roe_pct="18", per="28", risk_band="MEDIUM"
        ),
    }
    rows = [_ranking_score_row(symbol) for symbol in symbol_rows]

    assert (
        apply_ranking_weight_preset(rows, RANKING_PRESET_QUALITY_GROWTH, symbol_rows)[0]["symbol"]
        == "GROWTH"
    )
    assert (
        apply_ranking_weight_preset(rows, RANKING_PRESET_QUALITY_VALUE, symbol_rows)[0]["symbol"]
        == "VALUE"
    )
    assert (
        apply_ranking_weight_preset(rows, RANKING_PRESET_SUSTAINABLE_INCOME, symbol_rows)[0][
            "symbol"
        ]
        == "INCOME"
    )
    assert (
        apply_ranking_weight_preset(rows, RANKING_PRESET_MIN_VOLATILITY, symbol_rows)[0]["symbol"]
        == "LOWVOL"
    )
    assert (
        apply_ranking_weight_preset(rows, RANKING_PRESET_SMALL_GROWTH, symbol_rows)[0]["symbol"]
        == "SMALL"
    )


def test_advanced_etf_ranking_profiles_change_order_by_cost_or_income():
    core_rows = {
        "CORE": _etf_symbol_metadata(
            "CORE", expense_ratio_pct="0.03", complexity="beginner", index_family="sp500"
        ),
        "COMPLEX": _etf_symbol_metadata(
            "COMPLEX",
            expense_ratio_pct="0.95",
            complexity="advanced",
            index_family="",
            nisa_category="none",
        ),
    }
    income_rows = {
        "ETF_INCOME": _etf_symbol_metadata(
            "ETF_INCOME", dividend_yield_pct="4.0", expense_ratio_pct="0.30"
        ),
        "ETF_WEAK": _etf_symbol_metadata(
            "ETF_WEAK",
            dividend_yield_pct="0",
            expense_ratio_pct="0.90",
            complexity="advanced",
            index_family="",
            nisa_category="none",
        ),
    }

    assert (
        apply_ranking_weight_preset(
            [_ranking_score_row(symbol) for symbol in core_rows],
            RANKING_PRESET_ETF_CORE_COST,
            core_rows,
        )[0]["symbol"]
        == "CORE"
    )
    assert (
        apply_ranking_weight_preset(
            [_ranking_score_row(symbol) for symbol in income_rows],
            RANKING_PRESET_ETF_INCOME,
            income_rows,
        )[0]["symbol"]
        == "ETF_INCOME"
    )


def test_ranking_weight_presets_are_normalized():
    for weights in RANKING_WEIGHT_PRESETS.values():
        assert sum(weights.values(), Decimal("0")) == Decimal("1.00")


def test_limited_ranking_selected_labels_prefers_database_fit_before_fetch():
    low_rows = [
        _stock_symbol_metadata(f"LOW{index}", roe_pct="4", per="45", pbr="5", risk_band="HIGH")
        for index in range(100)
    ]
    rows = [
        *low_rows,
        _stock_symbol_metadata("HIGH", roe_pct="24", per="30", pbr="4", risk_band="MEDIUM"),
    ]
    selected_labels = [f"LOW{index} - LOW{index}" for index in range(100)] + ["HIGH - HIGH"]

    limited = limited_ranking_selected_labels(
        selected_labels,
        rows,
        preset=RANKING_PRESET_QUALITY_GROWTH,
        limit_key=RANKING_FETCH_LIMIT_FAST,
    )
    assert len(limited) == 100
    assert limited[0] == "HIGH - HIGH"
    assert (
        limited_ranking_selected_labels(
            selected_labels,
            rows,
            preset=RANKING_PRESET_QUALITY_GROWTH,
            limit_key=RANKING_FETCH_LIMIT_BALANCED,
        )
        == selected_labels
    )


def test_ranking_fetch_limit_baseline_is_independent_from_sort_profile():
    assert RANKING_FETCH_LIMIT_PRESET == RANKING_PRESET_MULTI_FACTOR


def test_ranking_database_scores_use_symbol_metadata():
    high_dividend = {
        "symbol": "9434.T",
        "asset_type": "stock",
        "is_active": "true",
        "nisa_category": "growth",
        "dividend_yield_pct": "3.8",
        "pbr": "1.2",
        "risk_band": "MEDIUM",
        "metadata_source": "yahoo",
        "metadata_as_of": "2026-05-22",
        "market_cap_tier": "large",
        "dividend_category": "high_dividend",
        "per": "14",
        "roe_pct": "12",
    }

    assert ranking_database_fit_score(high_dividend, "income") == Decimal("100")
    assert ranking_metadata_confidence_score(high_dividend) == Decimal("100")


def test_investment_score_csv_download_accepts_ranking_metadata_scores():
    csv_text = investment_score_csv_download(
        [
            {
                "rank": "1",
                "symbol": "9434.T",
                "total_score": "82",
                "score_band": "STRONG",
                "screening_score": "75",
                "forecast_agreement_score": "70",
                "data_quality_score": "100",
                "database_fit_score": "95",
                "metadata_confidence_score": "100",
                "risk_signal_score": "60",
                "ranking_profile": "配当・インカム重視",
                "warnings": "",
                "note": "売買推奨ではなく、根拠確認の優先順です。",
            }
        ]
    )

    assert "database_fit_score" in csv_text
    assert "metadata_confidence_score" in csv_text
    assert "ranking_profile" in csv_text


def test_screening_score_rows_include_forecast_signal():
    rows = screening_score_rows(
        [
            ScreeningScore(
                rank=1,
                symbol="AAPL",
                total_score=Decimal("84.35"),
                momentum_score=Decimal("80"),
                liquidity_score=Decimal("100"),
                risk_score=Decimal("88"),
                data_quality_score=Decimal("100"),
                forecast_score=Decimal("45"),
                forecast_agreement="LOW",
                data_quality="OK",
                summary="AAPL は今回の条件では上位候補です。",
                forecast_reason="予測モデル同士の見方が割れています。",
                reason_labels=["予測モデル同士の見方が割れています。"],
                reasons=["forecast_agreement:low"],
            )
        ]
    )

    assert rows == [
        {
            "rank": "1",
            "symbol": "AAPL",
            "total_score": "84.35",
            "momentum_score": "80",
            "liquidity_score": "100",
            "risk_score": "88",
            "data_quality_score": "100",
            "forecast_score": "45",
            "forecast_agreement": "LOW",
            "data_quality": "OK",
            "summary": "AAPL は今回の条件では上位候補です。",
            "forecast_reason": "予測モデル同士の見方が割れています。",
            "reason_labels": "予測モデル同士の見方が割れています。",
            "reasons": "forecast_agreement:low",
        }
    ]


def test_market_chart_long_frame_adds_beginner_friendly_labels():
    frame = market_chart_long_frame(
        [
            {
                "ts": "2026-05-10T00:00:00+00:00",
                "close": "185",
                "naive": "",
            },
            {
                "ts": "2026-05-11T00:00:00+00:00",
                "close": "",
                "naive": "186.5",
            },
        ]
    )

    assert frame[["series", "line_label", "series_label"]].to_dict("records") == [
        {
            "series": "close",
            "line_label": "実績",
            "series_label": "実績価格",
        },
        {
            "series": "naive",
            "line_label": "予測",
            "series_label": "予測: 直近値維持",
        },
    ]


def test_provider_error_summary_rows_explain_yahoo_dns_timeout():
    row = {
        "code": "APP-2003",
        "message": "Yahoo market-data provider request failed",
        "details": json.dumps(
            {
                "provider": "yahoo",
                "request": {
                    "error": "Failed to perform, curl: (28) Resolving timed out after 5002 milliseconds.",
                    "operation": "fetch_quotes",
                    "symbol": "9983.T",
                },
                "requires_external_opt_in": True,
                "supported_providers": ["mock", "csv"],
            },
            ensure_ascii=False,
        ),
    }

    assert provider_error_summary_rows([row]) == [
        {
            "コード": "APP-2003",
            "Provider": "yahoo",
            "Symbol": "9983.T",
            "内容": "Yahoo market-data provider request failed",
            "次の確認": (
                "yahoo への外部通信がタイムアウトしています。"
                "ネットワーク/DNS を確認し、時間をおいて再実行してください。"
                "ランキングでは銘柄数や取得期間を絞ると安定しやすくなります。"
            ),
        }
    ]

    details = json.loads(format_provider_error_details(row))
    assert details["request"]["operation"] == "fetch_quotes"
    assert details["request"]["symbol"] == "9983.T"


def test_provider_error_summary_rows_explain_ranking_no_bars():
    row = ranking_no_bars_error_row(
        provider="yahoo",
        symbol="9613.T",
        display_start=date(2026, 5, 11),
        display_end=date(2026, 5, 18),
        fetch_start=datetime(2026, 2, 17, tzinfo=UTC),
        fetch_end=datetime(2026, 5, 18, 23, 59, 59, tzinfo=UTC),
    )

    assert provider_error_summary_rows([row]) == [
        {
            "コード": "RANKING-NO-BARS",
            "Provider": "yahoo",
            "Symbol": "9613.T",
            "内容": "価格データを取得できなかったため、ランキングから除外しました。",
            "次の確認": (
                "価格データが返っていないため、ランキングから除外しています。"
                "yahoo 側の提供状況、銘柄コード、取得期間を確認してください。"
            ),
        }
    ]

    details = json.loads(format_provider_error_details(row))
    assert details["reason"] == "no_ohlcv_rows"
    assert details["request"]["display_end"] == "2026-05-18"


def test_render_market_chart_uses_currency_axis_title_and_compact_width(monkeypatch):
    captured: dict[str, object] = {}

    def fake_altair_chart(chart: object, *, use_container_width: bool = False) -> None:
        captured["spec"] = chart.to_dict(validate=True)  # type: ignore[attr-defined]
        captured["use_container_width"] = use_container_width

    monkeypatch.setattr("ui.app.st.altair_chart", fake_altair_chart)
    monkeypatch.setattr("ui.app.st.info", lambda message: None)

    _render_market_chart(
        [
            {
                "ts": "2026-05-10T00:00:00+00:00",
                "close": "185",
                "naive": "",
            },
            {
                "ts": "2026-05-11T00:00:00+00:00",
                "close": "",
                "naive": "186.5",
            },
        ],
        currency="USD",
        title="Price and forecast",
    )

    spec = captured["spec"]
    chart_spec = spec["hconcat"][0]  # type: ignore[index]
    assert spec["title"] == "Price and forecast"
    assert chart_spec["width"] == 1400
    assert chart_spec["layer"][0]["encoding"]["y"]["title"] == "終値 (USD)"
    assert captured["use_container_width"] is True


def test_forecast_boundary_frame_marks_latest_actual_date():
    frame = forecast_boundary_frame(
        [
            {
                "ts": "2026-05-10T00:00:00+00:00",
                "close": "185",
                "naive": "",
            },
            {
                "ts": "2026-05-11T00:00:00+00:00",
                "close": "",
                "naive": "186.5",
            },
        ]
    )

    assert frame.to_dict("records") == [{"date": date(2026, 5, 10)}]


def test_forecast_metric_display_rows_and_summary_are_beginner_friendly():
    rows = [
        {
            "model": "naive",
            "symbol": "AAPL",
            "horizon_days": "10",
            "forecast_close": "221.32",
            "mae": "13.11",
            "rmse": "13.90",
            "direction_accuracy": "44.44%",
            "sample_count": "55",
        },
        {
            "model": "moving_average_3",
            "symbol": "AAPL",
            "horizon_days": "10",
            "forecast_close": "224.43",
            "mae": "13.68",
            "rmse": "14.14",
            "direction_accuracy": "46.29%",
            "sample_count": "55",
        },
    ]

    assert forecast_metric_display_rows(rows)[0] == {
        "モデル": "予測: 直近値維持",
        "銘柄": "AAPL",
        "予測日数": "10",
        "予測終値": "221.32",
        "MAE(小さいほど良い)": "13.11",
        "RMSE(小さいほど良い)": "13.90",
        "方向一致率(高いほど良い)": "44.44%",
        "評価サンプル数": "55",
    }
    summary = forecast_metric_summary(rows)
    assert "予測: 直近値維持" in summary[0]
    assert summary[1] == "誤差と方向一致率で、モデルの当たりやすさを比べます。"


def test_forecast_metric_downloads_are_stable_json_and_csv():
    rows = [
        {
            "model": "naive",
            "symbol": "AAPL",
            "horizon_days": "10",
            "forecast_close": "221.32",
            "mae": "13.11",
            "rmse": "13.90",
            "direction_accuracy": "44.44%",
            "sample_count": "55",
        }
    ]

    assert forecast_metric_json_download(rows) == (
        "[\n"
        "  {\n"
        '    "model": "naive",\n'
        '    "symbol": "AAPL",\n'
        '    "horizon_days": "10",\n'
        '    "forecast_close": "221.32",\n'
        '    "mae": "13.11",\n'
        '    "rmse": "13.90",\n'
        '    "direction_accuracy": "44.44%",\n'
        '    "sample_count": "55"\n'
        "  }\n"
        "]\n"
    )
    assert forecast_metric_csv_download(rows) == (
        "model,symbol,horizon_days,forecast_close,mae,rmse,direction_accuracy,sample_count\n"
        "naive,AAPL,10,221.32,13.11,13.90,44.44%,55\n"
    )


def _bar(ts: str, *, close: int = 100, symbol: str = "AAPL") -> Bar:
    return Bar(
        symbol=Symbol(raw=symbol, exchange="NASDAQ", code=symbol, currency="USD"),
        ts=datetime.fromisoformat(f"{ts}T00:00:00+00:00").astimezone(UTC),
        open=Decimal(str(close)),
        high=Decimal(str(close)),
        low=Decimal(str(close)),
        close=Decimal(str(close)),
        volume=Decimal("1000"),
        interval="1d",
        provider="test",
    )
