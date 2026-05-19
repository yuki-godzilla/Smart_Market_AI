from __future__ import annotations

import asyncio
import json
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Callable, cast

import altair as alt
import pandas as pd
import streamlit as st

from backend.core.config import get_settings
from backend.core.data_contracts import Bar, DailySnapshot, DataQuality, FeatureSnapshot, Quote
from backend.core.errors import AppError
from backend.forecast import forecast_model_display_name, summarize_forecast_evaluations
from backend.marketdata import create_market_data_provider_adapter
from backend.marketdata.feature_builder import build_daily_snapshots_from_market_data
from backend.scoring import InvestmentScoringService
from backend.screening import ScreeningService
from ui.components.sidemenu import (
    SIDEMENU_PAGE_COCKPIT,
    SIDEMENU_PAGE_RANKING,
    SIDEMENU_PAGE_REBALANCE,
    render_sidemenu,
)
from ui.ranking import (
    LIVE_MARKET_DATA_PROVIDERS,
    MAX_RANKING_BUILD_CACHE_ENTRIES,
    MAX_RANKING_CONCURRENT_FETCHES,
    RANKING_COMPLEXITY_LABELS,
    RANKING_CURRENCY_LABELS,
    RANKING_DIVIDEND_LABELS,
    RANKING_INDEX_FAMILY_LABELS,
    RANKING_MARKET_CAP_LABELS,
    RANKING_MVP_PRODUCT_TYPE_LABELS,
    RANKING_MVP_REGION_LABELS,
    RANKING_NISA_ELIGIBILITY_LABELS,
    RANKING_PERIOD_PRESETS,
    RANKING_PURPOSE_LABELS,
    RANKING_THEME_LABELS,
    apply_ranking_weight_preset,
    filter_symbol_universe_rows,
    live_ranking_symbol_warning_message,
    rank_investment_score_rows,
    ranking_build_cache_key,
    ranking_deep_dive_default_symbol,
    ranking_detail_filters_for_category,
    ranking_filter_signature,
    ranking_no_bars_error_row,
    ranking_period_dates,
    ranking_period_label,
    ranking_product_type_label,
    ranking_provider_error_rows,
    ranking_purpose_label,
    ranking_region_label,
    ranking_symbol_chunks,
    ranking_symbol_options,
    ranking_symbols_state_key,
    ranking_weight_preset_for_purpose,
    ranking_weight_preset_label,
    symbol_candidate_labels,
    symbol_universe_rows,
)
from ui.ranking_state import (
    clear_ranking_filter_state,
    ensure_ranking_selection_widget_state,
    sync_ranking_selection_state,
)
from ui.ranking_state import (
    ranking_filter_bool as _ranking_filter_bool,
)
from ui.ranking_state import (
    ranking_filter_value as _ranking_filter_value,
)
from ui.rebalance_app import (
    MarketDataPreview,
    _available_forecast_evaluations,
    build_market_data_preview,
    forecast_chart_rows,
    forecast_consensus_rows_for_bars,
    forecast_metric_csv_download,
    forecast_metric_json_download,
    forecast_metric_rows_for_bars,
    forecast_reference_period,
    investment_score_csv_download,
    investment_score_json_download,
    investment_score_rows,
    runtime_settings_summary,
    screening_score_csv_download,
    screening_score_json_download,
    symbol_name,
    symbol_reference_rows,
    yfinance_search_symbol_rows,
)
from ui.state import (
    MARKET_DATA_FORECAST_DAYS_STATE_KEY,
    MARKET_DATA_PREVIEW_STATE_KEY,
    MARKET_DATA_RANKING_BUILD_CACHE_STATE_KEY,
    MARKET_DATA_RANKING_DEEP_DIVE_SOURCE_STATE_KEY,
    MARKET_DATA_RANKING_ERROR_STATE_KEY,
    MARKET_DATA_RANKING_SELECTED_LABELS_STATE_KEY,
    MARKET_DATA_RANKING_SOURCE_STATE_KEY,
    MARKET_DATA_RANKING_STATE_KEY,
    MARKET_DATA_STATUS_STATE_KEY,
    MARKET_DATA_TOAST_STATE_KEY,
)
from ui.views.common import (
    _optional_decimal_from_text,
    _render_table,
    _single_date_from_input,
    default_as_of_date,
)
from ui.views.rebalance import (
    REBALANCE_REQUEST_STATE_KEY,
    REBALANCE_RESULT_STATE_KEY,
    allocation_chart_frame,
    rebalance_flow_rows,
    rebalance_result_from_state,
    render_rebalance_page,
    risk_breach_display_rows,
    risk_breach_message,
)
from ui.views.settings import render_settings_page

__all__ = [
    "REBALANCE_REQUEST_STATE_KEY",
    "REBALANCE_RESULT_STATE_KEY",
    "allocation_chart_frame",
    "default_as_of_date",
    "rebalance_flow_rows",
    "rebalance_result_from_state",
    "risk_breach_display_rows",
    "risk_breach_message",
]

MARKET_DATA_PROVIDER_OPTIONS = ["yahoo", "csv", "mock"]
MARKET_DATA_PROVIDER_WIDGET_KEY = "market_data_provider_live_first"
MARKET_DATA_RANKING_PROVIDER_WIDGET_KEY = "market_data_ranking_provider_live_first"

FORECAST_ACTUAL_LABEL = "実績価格"
MARKET_DATA_MODE_COCKPIT = "cockpit"
MARKET_DATA_MODE_RANKING = "ranking"
MARKET_DATA_MODE_LABELS = {
    MARKET_DATA_MODE_COCKPIT: "銘柄コックピット",
    MARKET_DATA_MODE_RANKING: "銘柄ランキング",
}


def main() -> None:
    st.set_page_config(page_title="Smart Market AI", layout="wide")
    st.title("Smart Market AI")

    selected_page = render_sidemenu(runtime_settings_summary())
    if selected_page == SIDEMENU_PAGE_COCKPIT:
        _render_market_data_cockpit()
    elif selected_page == SIDEMENU_PAGE_RANKING:
        _render_market_data_ranking()
    elif selected_page == SIDEMENU_PAGE_REBALANCE:
        render_rebalance_page()
    else:
        render_settings_page()


def default_market_data_start_date() -> date:
    return default_market_data_end_date() - timedelta(days=7)


def default_market_data_end_date() -> date:
    return date.today()


def default_forecast_horizon_days(start: date, end: date) -> int:
    """Choose a compact forecast horizon from the displayed chart period."""

    if end < start:
        raise ValueError("End must be on or after Start")
    display_days = (end - start).days + 1
    return max(1, min(30, round(display_days / 10)))


def _provider_option_index(provider: str) -> int:
    try:
        return MARKET_DATA_PROVIDER_OPTIONS.index(provider)
    except ValueError:
        return 0


def default_market_data_provider() -> str:
    return "yahoo"


def _symbol_from_candidate(label: str) -> str | None:
    if not label:
        return None
    return label.split(" - ", 1)[0]


def _name_from_candidate(label: str) -> str | None:
    if " - " not in label:
        return None
    return label.split(" - ", 1)[1]


def _ranking_symbols_from_selected_labels(selected_labels: list[str]) -> list[str]:
    return [symbol for label in selected_labels if (symbol := _symbol_from_candidate(label))]


def _ranking_source_key_for_selection(
    *,
    provider: str,
    selected_labels: list[str],
    start: date,
    end: date,
) -> str:
    ranking_symbols = _ranking_symbols_from_selected_labels(selected_labels)
    if not ranking_symbols:
        return ""
    return ranking_build_cache_key(
        provider=provider,
        symbols=ranking_symbols,
        start=start,
        end=end,
    )


def _ranking_result_matches_current_selection(
    stored_source: str,
    *,
    provider: str,
    selected_labels: list[str],
    start: date,
    end: date,
) -> bool:
    current_source = _ranking_source_key_for_selection(
        provider=provider,
        selected_labels=selected_labels,
        start=start,
        end=end,
    )
    return bool(current_source) and stored_source == current_source


def _selectbox_index(options: list[str], value: str) -> int:
    return options.index(value) if value in options else 0


def _ensure_selectbox_state_value(key: str, options: list[str]) -> None:
    if key in st.session_state and st.session_state.get(key) not in options:
        st.session_state[key] = options[0]


def _render_metric_range_filter(
    label: str,
    *,
    enabled_key: str,
    min_key: str,
    max_key: str,
    min_default: str,
    max_default: str,
    min_value: float = 0.0,
    max_value: float = 100.0,
    step: float = 0.1,
) -> None:
    col_enabled, col_min, col_max = st.columns([1.0, 1.0, 1.0])
    with col_enabled:
        enabled = st.checkbox(
            label,
            value=_ranking_filter_bool(enabled_key, False),
            key=enabled_key,
        )
    with col_min:
        st.number_input(
            "下限",
            min_value=min_value,
            max_value=max_value,
            value=float(_ranking_filter_value(min_key, min_default)),
            step=step,
            key=min_key,
            disabled=not enabled,
        )
    with col_max:
        st.number_input(
            "上限",
            min_value=min_value,
            max_value=max_value,
            value=float(_ranking_filter_value(max_key, max_default)),
            step=step,
            key=max_key,
            disabled=not enabled,
        )


def _render_detail_selectbox(
    label: str,
    *,
    options: list[str],
    key: str,
    format_func: Callable[[str], str],
    help_text: str | None = None,
) -> None:
    st.selectbox(
        label,
        options,
        index=_selectbox_index(options, _ranking_filter_value(key, options[0])),
        key=key,
        format_func=format_func,
        help=help_text,
    )


def _render_metric_filter_grid(
    filters: list[tuple[str, dict[str, object]]],
    *,
    columns_per_row: int = 2,
) -> None:
    for start_index in range(0, len(filters), columns_per_row):
        row_filters = filters[start_index : start_index + columns_per_row]
        columns = st.columns(columns_per_row)
        for column, (label, kwargs) in zip(columns, row_filters, strict=False):
            with column:
                _render_metric_range_filter(label, **kwargs)


def ranking_comparison_summary(
    *,
    start: date,
    end: date,
    candidate_count: int,
    selected_count: int,
) -> dict[str, str]:
    if candidate_count <= 0:
        status = "候補なし"
        selected = "0件"
    elif selected_count <= 0:
        status = "未選択"
        selected = f"0 / {candidate_count}件"
    elif selected_count >= candidate_count:
        status = "全候補を比較"
        selected = f"{candidate_count} / {candidate_count}件"
    else:
        status = "一部を比較"
        selected = f"{selected_count} / {candidate_count}件"
    return {
        "period": f"{start.isoformat()} 〜 {end.isoformat()}",
        "candidate": f"{max(candidate_count, 0)}件",
        "selected": selected,
        "status": status,
        "inline": (
            f"取得期間: {start.isoformat()} 〜 {end.isoformat()} / "
            f"候補: {max(candidate_count, 0)}件 / 選択: {selected}（{status}）"
        ),
    }


def _render_ranking_filter_panel() -> None:
    has_ranking_result = bool(st.session_state.get(MARKET_DATA_RANKING_STATE_KEY))
    region = _ranking_filter_value("market_data_ranking_region", "japan")
    product_type = _ranking_filter_value("market_data_ranking_product_type", "stock")
    detail_filters = set(ranking_detail_filters_for_category(region, product_type))
    with st.expander("詳細条件", expanded=not has_ranking_result):
        st.caption("ここは候補を絞る条件です。上の並べ替え設定とは別に使います。")

        st.markdown("**属性条件**")
        columns = st.columns(4)
        column_index = 0

        def next_column():
            nonlocal column_index
            column = columns[column_index % len(columns)]
            column_index += 1
            return column

        if "industry_or_sector" in detail_filters:
            with next_column():
                _render_detail_selectbox(
                    "業種/テーマ",
                    options=list(RANKING_THEME_LABELS),
                    key="market_data_ranking_theme",
                    format_func=lambda value: RANKING_THEME_LABELS[value],
                )
        if "market_cap" in detail_filters:
            with next_column():
                _render_detail_selectbox(
                    "時価総額",
                    options=list(RANKING_MARKET_CAP_LABELS),
                    key="market_data_ranking_market_cap",
                    format_func=lambda value: RANKING_MARKET_CAP_LABELS[value],
                )
        if "nisa_eligibility" in detail_filters:
            with next_column():
                _render_detail_selectbox(
                    "NISA",
                    options=list(RANKING_NISA_ELIGIBILITY_LABELS),
                    key="market_data_ranking_nisa",
                    format_func=lambda value: RANKING_NISA_ELIGIBILITY_LABELS[value],
                )
        if "benchmark_index" in detail_filters:
            with next_column():
                _render_detail_selectbox(
                    "連動指数",
                    options=list(RANKING_INDEX_FAMILY_LABELS),
                    key="market_data_ranking_index_family",
                    format_func=lambda value: RANKING_INDEX_FAMILY_LABELS[value],
                )
        if "expense_ratio" in detail_filters:
            with next_column():
                st.number_input(
                    "信託報酬/経費率(%)以下",
                    min_value=0.0,
                    max_value=2.0,
                    value=float(_ranking_filter_value("market_data_ranking_max_expense", "1.00")),
                    step=0.01,
                    key="market_data_ranking_max_expense",
                )
        if "complexity" in detail_filters:
            with next_column():
                _render_detail_selectbox(
                    "複雑さ",
                    options=list(RANKING_COMPLEXITY_LABELS),
                    key="market_data_ranking_complexity",
                    format_func=lambda value: RANKING_COMPLEXITY_LABELS[value],
                )
        if "dividend_yield" in detail_filters:
            with next_column():
                _render_detail_selectbox(
                    "配当カテゴリ",
                    options=list(RANKING_DIVIDEND_LABELS),
                    key="market_data_ranking_dividend",
                    format_func=lambda value: RANKING_DIVIDEND_LABELS[value],
                )
        with next_column():
            _render_detail_selectbox(
                "通貨",
                options=list(RANKING_CURRENCY_LABELS),
                key="market_data_ranking_currency",
                format_func=lambda value: RANKING_CURRENCY_LABELS[value],
            )

        metric_filters: list[tuple[str, dict[str, object]]] = []
        if "dividend_yield" in detail_filters:
            metric_filters.append(
                (
                    "配当利回り(%)",
                    {
                        "enabled_key": "market_data_ranking_dividend_enabled",
                        "min_key": "market_data_ranking_min_dividend",
                        "max_key": "market_data_ranking_dividend_max",
                        "min_default": "3.0",
                        "max_default": "10.0",
                        "max_value": 15.0,
                    },
                )
            )
        if "per" in detail_filters:
            metric_filters.append(
                (
                    "PER",
                    {
                        "enabled_key": "market_data_ranking_per_enabled",
                        "min_key": "market_data_ranking_per_min",
                        "max_key": "market_data_ranking_per_max",
                        "min_default": "2.0",
                        "max_default": "20.0",
                        "max_value": 80.0,
                    },
                )
            )
        if "pbr" in detail_filters:
            metric_filters.append(
                (
                    "PBR",
                    {
                        "enabled_key": "market_data_ranking_pbr_enabled",
                        "min_key": "market_data_ranking_pbr_min",
                        "max_key": "market_data_ranking_pbr_max",
                        "min_default": "0.5",
                        "max_default": "2.0",
                        "max_value": 20.0,
                    },
                )
            )
        if "roe" in detail_filters:
            metric_filters.append(
                (
                    "ROE(%)",
                    {
                        "enabled_key": "market_data_ranking_roe_enabled",
                        "min_key": "market_data_ranking_roe_min",
                        "max_key": "market_data_ranking_roe_max",
                        "min_default": "8.0",
                        "max_default": "30.0",
                        "max_value": 60.0,
                    },
                )
            )
        if metric_filters:
            st.markdown("**数値条件**")
            _render_metric_filter_grid(metric_filters)

        st.markdown("**キーワード検索**")
        col_keyword, col_clear = st.columns([3.0, 0.8])
        with col_keyword:
            st.text_input(
                "キーワード",
                value=_ranking_filter_value("market_data_ranking_symbol_query", ""),
                key="market_data_ranking_symbol_query",
                placeholder="ticker or company name",
            )
        with col_clear:
            st.button("クリアする", on_click=clear_ranking_filter_state)


def merged_symbol_candidate_rows(
    reference_rows: list[dict[str, str]],
    live_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Merge representative and live-search symbol candidates without duplicates."""

    merged: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in [*reference_rows, *live_rows]:
        symbol = row.get("symbol", "").strip()
        name = row.get("name", "").strip() or symbol
        normalized_symbol = symbol.upper()
        if not normalized_symbol or normalized_symbol in seen:
            continue
        seen.add(normalized_symbol)
        merged.append({"symbol": symbol, "name": name})
    return merged


def _render_market_data_preview() -> None:
    _render_market_data_cockpit()


def _render_market_data_cockpit() -> None:
    st.subheader("銘柄コックピット")
    st.caption("1銘柄の価格、予測、Investment Score、注意点を確認します。")
    symbol_options = symbol_reference_rows()
    col_provider, col_search, col_symbol, col_name, col_start, col_end = st.columns(
        [1.0, 1.3, 1.7, 1.4, 1.0, 1.0]
    )
    with col_provider:
        provider = cast(
            str,
            st.selectbox(
                "Provider",
                MARKET_DATA_PROVIDER_OPTIONS,
                index=_provider_option_index(default_market_data_provider()),
                key=MARKET_DATA_PROVIDER_WIDGET_KEY,
            ),
        )
        if provider in LIVE_MARKET_DATA_PROVIDERS:
            st.caption("Yahoo live data を取得します。")
    with col_search:
        symbol_query = st.text_input(
            "Symbol search",
            value="",
            key="market_data_symbol_search",
            placeholder="ticker or company name",
        )
    with col_symbol:
        live_symbol_options = (
            yfinance_search_symbol_rows(symbol_query) if symbol_query.strip() else []
        )
        candidate_rows = merged_symbol_candidate_rows(symbol_options, live_symbol_options)
        symbol_option_labels = symbol_candidate_labels(candidate_rows, symbol_query)
        if not symbol_option_labels:
            symbol_option_labels = symbol_candidate_labels(symbol_options)
        symbol_candidate = cast(
            str,
            st.selectbox(
                "Symbol",
                symbol_option_labels,
                index=min(1, len(symbol_option_labels) - 1),
                key="market_data_symbol_candidate",
                placeholder="ticker or company name",
            ),
        )
    symbol = _symbol_from_candidate(symbol_candidate) or "AAPL"
    with col_name:
        company_name = symbol_name(symbol) or _name_from_candidate(symbol_candidate) or "名称未登録"
        st.text_input("Name", value=company_name, disabled=True, key="market_data_symbol_name")
    with col_start:
        start = st.date_input(
            "Start",
            value=default_market_data_start_date(),
            key="market_data_start",
        )
    with col_end:
        end = st.date_input("End", value=default_market_data_end_date(), key="market_data_end")

    with st.expander("銘柄候補", expanded=False):
        st.dataframe(symbol_options, hide_index=True, use_container_width=True)

    if st.button("Fetch market data", key="fetch_market_data"):
        try:
            start_date = _single_date_from_input(start)
            end_date = _single_date_from_input(end)
            forecast_horizon_days = default_forecast_horizon_days(start_date, end_date)
            st.session_state[MARKET_DATA_FORECAST_DAYS_STATE_KEY] = forecast_horizon_days
            preview = asyncio.run(
                build_market_data_preview(
                    symbol=symbol.strip(),
                    start=start_date,
                    end=end_date,
                    provider_override=provider,
                    forecast_horizon_days=forecast_horizon_days,
                )
            )
        except ValueError as exc:
            st.error(str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            st.error(str(exc))
            return

        st.session_state[MARKET_DATA_PREVIEW_STATE_KEY] = preview
        st.session_state[MARKET_DATA_STATUS_STATE_KEY] = preview.status
        if preview.status == "OK":
            st.session_state[MARKET_DATA_TOAST_STATE_KEY] = "データを取得しました。"

    stored_preview = _market_data_preview_from_state()
    if stored_preview is None:
        return

    toast_message = st.session_state.pop(MARKET_DATA_TOAST_STATE_KEY, None)
    if toast_message:
        st.toast(str(toast_message), icon="✅")

    if st.session_state.get(MARKET_DATA_STATUS_STATE_KEY) != "OK":
        st.error("価格データを取得できませんでした。")
        _render_provider_error_summary(stored_preview.error_rows)
        return

    _render_market_data_preview_result(stored_preview)


def _render_market_data_ranking() -> None:
    st.subheader("銘柄ランキング")
    st.caption("複数銘柄を比較し、深掘り候補を整理します。売買推奨ではありません。")
    symbol_options = symbol_universe_rows()
    purpose = "all"

    col_region, col_product, col_purpose = st.columns(3)
    with col_region:
        region_options = list(RANKING_MVP_REGION_LABELS)
        _ensure_selectbox_state_value("market_data_ranking_region", region_options)
        region = cast(
            str,
            st.selectbox(
                "地域",
                region_options,
                index=_selectbox_index(
                    region_options,
                    _ranking_filter_value("market_data_ranking_region", "japan"),
                ),
                key="market_data_ranking_region",
                format_func=ranking_region_label,
            ),
        )
    with col_product:
        product_options = list(RANKING_MVP_PRODUCT_TYPE_LABELS)
        _ensure_selectbox_state_value("market_data_ranking_product_type", product_options)
        product_type = cast(
            str,
            st.selectbox(
                "商品",
                product_options,
                index=_selectbox_index(
                    product_options,
                    _ranking_filter_value("market_data_ranking_product_type", "stock"),
                ),
                key="market_data_ranking_product_type",
                format_func=ranking_product_type_label,
            ),
        )
    with col_purpose:
        purpose_options = list(RANKING_PURPOSE_LABELS)
        _ensure_selectbox_state_value("market_data_ranking_purpose", purpose_options)
        ranking_purpose = cast(
            str,
            st.selectbox(
                "重視して並べ替え",
                purpose_options,
                index=_selectbox_index(
                    purpose_options,
                    _ranking_filter_value("market_data_ranking_purpose", "dividend"),
                ),
                key="market_data_ranking_purpose",
                format_func=ranking_purpose_label,
                help="候補は絞らず、スコアの表示順に使います。",
            ),
        )
        st.caption("候補は絞らず、表示順に使います。")

    weight_preset = ranking_weight_preset_for_purpose(ranking_purpose)

    col_provider, col_period = st.columns([1.0, 1.0])
    with col_provider:
        provider = cast(
            str,
            st.selectbox(
                "Provider",
                MARKET_DATA_PROVIDER_OPTIONS,
                index=_provider_option_index(default_market_data_provider()),
                key=MARKET_DATA_RANKING_PROVIDER_WIDGET_KEY,
            ),
        )
        if provider in LIVE_MARKET_DATA_PROVIDERS:
            st.caption("Yahoo live data でランキングを作成します。")
    with col_period:
        st.selectbox(
            "取得期間",
            list(RANKING_PERIOD_PRESETS),
            index=list(RANKING_PERIOD_PRESETS).index(
                _ranking_filter_value("market_data_ranking_period", "short")
            ),
            key="market_data_ranking_period",
            format_func=ranking_period_label,
        )
    st.caption(
        f"並べ替え: {ranking_purpose_label(ranking_purpose)} / "
        f"表示順: {ranking_weight_preset_label(weight_preset)}"
    )
    _render_ranking_filter_panel()

    period_preset = _ranking_filter_value("market_data_ranking_period", "short")
    market = "all"
    asset_type = "all"
    currency = _ranking_filter_value("market_data_ranking_currency", "all")
    dividend_category = _ranking_filter_value("market_data_ranking_dividend", "all")
    min_dividend_yield_pct = _ranking_filter_value("market_data_ranking_min_dividend", "0.0")
    market_cap_tier = _ranking_filter_value("market_data_ranking_market_cap", "all")
    index_family = _ranking_filter_value("market_data_ranking_index_family", "all")
    max_expense_ratio_pct = _ranking_filter_value("market_data_ranking_max_expense", "1.00")
    complexity = _ranking_filter_value("market_data_ranking_complexity", "standard")
    nisa_eligibility = _ranking_filter_value("market_data_ranking_nisa", "all")
    risk_band = "all"
    theme = _ranking_filter_value("market_data_ranking_theme", "all")
    symbol_query = _ranking_filter_value("market_data_ranking_symbol_query", "")
    per_enabled = _ranking_filter_bool("market_data_ranking_per_enabled", False)
    per_min = _ranking_filter_value("market_data_ranking_per_min", "2.0")
    per_max = _ranking_filter_value("market_data_ranking_per_max", "20.0")
    pbr_enabled = _ranking_filter_bool("market_data_ranking_pbr_enabled", False)
    pbr_min = _ranking_filter_value("market_data_ranking_pbr_min", "0.5")
    pbr_max = _ranking_filter_value("market_data_ranking_pbr_max", "2.0")
    dividend_yield_enabled = _ranking_filter_bool("market_data_ranking_dividend_enabled", False)
    dividend_yield_max_pct = _ranking_filter_value("market_data_ranking_dividend_max", "10.0")
    roe_enabled = _ranking_filter_bool("market_data_ranking_roe_enabled", False)
    roe_min_pct = _ranking_filter_value("market_data_ranking_roe_min", "8.0")
    roe_max_pct = _ranking_filter_value("market_data_ranking_roe_max", "30.0")
    consensus_enabled = _ranking_filter_bool("market_data_ranking_consensus_enabled", False)
    consensus_min = _ranking_filter_value("market_data_ranking_consensus_min", "2.5")
    consensus_max = _ranking_filter_value("market_data_ranking_consensus_max", "5.0")
    filtered_symbol_rows = filter_symbol_universe_rows(
        symbol_options,
        region=region,
        product_type=product_type,
        ranking_purpose=ranking_purpose,
        purpose=purpose,
        market=market,
        asset_type=asset_type,
        currency=currency,
        dividend_category=dividend_category,
        min_dividend_yield_pct=min_dividend_yield_pct,
        market_cap_tier=market_cap_tier,
        index_family=index_family,
        max_expense_ratio_pct=max_expense_ratio_pct,
        complexity=complexity,
        nisa_eligibility=nisa_eligibility,
        risk_band=risk_band,
        theme=theme,
        query=symbol_query,
        per_enabled=per_enabled,
        per_min=per_min,
        per_max=per_max,
        pbr_enabled=pbr_enabled,
        pbr_min=pbr_min,
        pbr_max=pbr_max,
        dividend_yield_enabled=dividend_yield_enabled,
        dividend_yield_max_pct=dividend_yield_max_pct,
        roe_enabled=roe_enabled,
        roe_min_pct=roe_min_pct,
        roe_max_pct=roe_max_pct,
        consensus_enabled=consensus_enabled,
        consensus_min=consensus_min,
        consensus_max=consensus_max,
        limit=len(symbol_options),
    )
    labels = symbol_candidate_labels(filtered_symbol_rows)
    filter_signature = ranking_filter_signature(
        region=region,
        product_type=product_type,
        ranking_purpose=ranking_purpose,
        purpose=purpose,
        period_preset=period_preset,
        market=market,
        asset_type=asset_type,
        currency=currency,
        dividend_category=dividend_category,
        min_dividend_yield_pct=min_dividend_yield_pct,
        market_cap_tier=market_cap_tier,
        index_family=index_family,
        max_expense_ratio_pct=max_expense_ratio_pct,
        complexity=complexity,
        nisa_eligibility=nisa_eligibility,
        risk_band=risk_band,
        theme=theme,
        query=symbol_query,
        per_enabled=per_enabled,
        per_min=per_min,
        per_max=per_max,
        pbr_enabled=pbr_enabled,
        pbr_min=pbr_min,
        pbr_max=pbr_max,
        dividend_yield_enabled=dividend_yield_enabled,
        dividend_yield_max_pct=dividend_yield_max_pct,
        roe_enabled=roe_enabled,
        roe_min_pct=roe_min_pct,
        roe_max_pct=roe_max_pct,
        consensus_enabled=consensus_enabled,
        consensus_min=consensus_min,
        consensus_max=consensus_max,
        limit=0,
    )
    selection_key = ranking_symbols_state_key(filter_signature)
    stored_selected_labels = cast(
        list[str],
        st.session_state.get(MARKET_DATA_RANKING_SELECTED_LABELS_STATE_KEY, []),
    )
    ensure_ranking_selection_widget_state(
        selection_key=selection_key,
        labels=labels,
        stored_selected_labels=stored_selected_labels,
    )
    selected_labels_for_summary = cast(list[str], st.session_state.get(selection_key, []))
    end_date = default_market_data_end_date()
    start_date, end_date = ranking_period_dates(period_preset, end_date)
    comparison_summary = ranking_comparison_summary(
        start=start_date,
        end=end_date,
        candidate_count=len(filtered_symbol_rows),
        selected_count=len(selected_labels_for_summary),
    )
    st.caption(comparison_summary["inline"])

    expander_label = f"比較する銘柄を確認・変更（{comparison_summary['selected']}）"
    with st.expander(expander_label, expanded=False):
        st.caption("候補は初期状態ですべて選択されています。変更する場合だけ開いてください。")
        selected_labels = cast(
            list[str],
            st.multiselect(
                "比較する銘柄",
                labels,
                key=selection_key,
            ),
        )
    ranking_symbols = _ranking_symbols_from_selected_labels(selected_labels)
    current_ranking_source = _ranking_source_key_for_selection(
        provider=provider,
        selected_labels=selected_labels,
        start=start_date,
        end=end_date,
    )
    warning_message = live_ranking_symbol_warning_message(provider, len(ranking_symbols))
    if warning_message is not None:
        st.warning(warning_message)
    if not labels:
        st.warning("この条件に合う候補がありません。候補条件を広げてください。")

    if st.button(
        "ランキング作成",
        key="build_market_data_ranking",
    ):
        sync_ranking_selection_state(selection_key, selected_labels)
        if not ranking_symbols:
            st.error("Ranking symbols を1件以上選んでください。")
            return
        cache_key = current_ranking_source
        cached_result = get_cached_ranking_build(cache_key)
        if cached_result is None:
            progress_bar = st.progress(0.0)
            progress_status = st.empty()

            def update_progress(message: str, ratio: float) -> None:
                progress_status.caption(message)
                progress_bar.progress(max(0.0, min(1.0, ratio)))

            rows, error_rows = asyncio.run(
                _build_market_data_ranking_rows(
                    ranking_symbols,
                    start=start_date,
                    end=end_date,
                    provider=provider,
                    progress_callback=update_progress,
                )
            )
            update_progress("ランキング作成が完了しました。", 1.0)
            set_cached_ranking_build(cache_key, rows=rows, error_rows=error_rows)
        else:
            rows, error_rows = cached_result
            st.caption("同じ条件の取得済みデータを再利用しました。")
        st.session_state[MARKET_DATA_RANKING_STATE_KEY] = rows
        st.session_state[MARKET_DATA_RANKING_ERROR_STATE_KEY] = error_rows
        st.session_state[MARKET_DATA_RANKING_SOURCE_STATE_KEY] = cache_key

    rows = st.session_state.get(MARKET_DATA_RANKING_STATE_KEY, [])
    error_rows = st.session_state.get(MARKET_DATA_RANKING_ERROR_STATE_KEY, [])
    ranking_source = str(st.session_state.get(MARKET_DATA_RANKING_SOURCE_STATE_KEY, ""))
    is_current_ranking_result = _ranking_result_matches_current_selection(
        ranking_source,
        provider=provider,
        selected_labels=selected_labels,
        start=start_date,
        end=end_date,
    )
    if (rows or error_rows) and not is_current_ranking_result:
        st.info("条件が変わりました。ランキング作成で結果を更新してください。")
    elif rows:
        ranked_rows = apply_ranking_weight_preset(
            cast(list[dict[str, str]], rows),
            weight_preset,
        )
        display_rows = investment_score_display_rows(ranked_rows)
        st.markdown("#### ランキング結果")
        st.caption(
            f"並べ替え: {ranking_purpose_label(ranking_purpose)} / "
            f"表示順: {ranking_weight_preset_label(weight_preset)}。"
            "上位の銘柄ほど、今回の条件では深掘り候補として見やすい順です。"
        )
        _render_table(display_rows, "No ranking rows.")
        _render_ranking_error_rows(cast(list[dict[str, str]], error_rows))
        deep_dive_symbols = ranking_symbol_options(ranked_rows)
        if deep_dive_symbols:
            deep_dive_source = f"{ranking_source}|{weight_preset}"
            default_deep_dive_symbol = ranking_deep_dive_default_symbol(
                ranked_rows,
                current_symbol=cast(
                    str | None,
                    st.session_state.get("market_data_ranking_deep_dive_symbol"),
                ),
                source_key=deep_dive_source,
                current_source_key=cast(
                    str | None,
                    st.session_state.get(MARKET_DATA_RANKING_DEEP_DIVE_SOURCE_STATE_KEY),
                ),
            )
            if default_deep_dive_symbol is not None:
                st.session_state["market_data_ranking_deep_dive_symbol"] = default_deep_dive_symbol
                st.session_state[MARKET_DATA_RANKING_DEEP_DIVE_SOURCE_STATE_KEY] = deep_dive_source
            st.markdown("#### 深掘り")
            st.caption(
                "気になる銘柄を1つ選び、銘柄コックピットで価格・予測・スコア理由を確認します。"
            )
            selected_symbol = cast(
                str,
                st.selectbox(
                    "深掘りする銘柄",
                    deep_dive_symbols,
                    format_func=symbol_candidate_label,
                    key="market_data_ranking_deep_dive_symbol",
                ),
            )
            st.button(
                "銘柄コックピットで確認",
                key="market_data_ranking_open_cockpit",
                on_click=_select_ranking_symbol_for_cockpit,
                args=(selected_symbol, provider),
            )
        col_json, col_csv = st.columns(2)
        col_json.download_button(
            "Download ranking JSON",
            data=investment_score_json_download(ranked_rows),
            file_name="investment_score_ranking.json",
            mime="application/json",
        )
        col_csv.download_button(
            "Download ranking CSV",
            data=investment_score_csv_download(ranked_rows),
            file_name="investment_score_ranking.csv",
            mime="text/csv",
        )
    elif error_rows:
        st.warning("ランキング対象の価格データを取得できませんでした。")
        _render_ranking_error_rows(cast(list[dict[str, str]], error_rows))
    else:
        st.info("銘柄を選んで ranking を作成してください。")


def _render_ranking_error_rows(error_rows: list[dict[str, str]]) -> None:
    if not error_rows:
        return

    st.warning(
        f"{len(error_rows)}件の銘柄は価格データを取得できなかったため、ランキングから除外しました。"
    )
    with st.expander("取得できなかった銘柄"):
        _render_table(provider_error_summary_rows(error_rows), "No ranking errors.")
        details_rows = [
            format_provider_error_details(row)
            for row in error_rows
            if format_provider_error_details(row)
        ]
        if details_rows:
            st.caption("診断情報")
            for details in details_rows:
                st.code(details, language="json")


async def _build_market_data_ranking_rows(
    symbols: list[str],
    *,
    start: date,
    end: date,
    provider: str,
    progress_callback: RankingProgressCallback | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    try:
        return await _build_market_data_ranking_rows_fast(
            symbols,
            start=start,
            end=end,
            provider=provider,
            progress_callback=progress_callback,
        )
    except AppError as exc:
        if provider in LIVE_MARKET_DATA_PROVIDERS:
            _report_ranking_progress(
                progress_callback,
                "Yahoo live data の一括取得に失敗しました。",
                1.0,
            )
            return [], ranking_provider_error_rows(provider, symbols, exc)
        return await _build_market_data_ranking_rows_from_previews(
            symbols,
            start=start,
            end=end,
            provider=provider,
            progress_callback=progress_callback,
        )


async def _build_market_data_ranking_rows_fast(
    symbols: list[str],
    *,
    start: date,
    end: date,
    provider: str,
    progress_callback: RankingProgressCallback | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    _report_ranking_progress(progress_callback, "ランキング用データの準備を開始しています。", 0.05)
    settings = get_settings()
    dataaccess_cfg = settings.dataaccess
    if provider:
        dataaccess_cfg = dataaccess_cfg.model_copy(
            update={
                "provider": provider,
                "allow_external_providers": provider == "yahoo"
                or dataaccess_cfg.allow_external_providers,
            }
        )
    adapter = create_market_data_provider_adapter(dataaccess_cfg)
    start_dt = datetime.combine(start, time.min, tzinfo=UTC)
    end_dt = datetime.combine(end, time.max, tzinfo=UTC)
    feature_start = min(start, end - timedelta(days=90))
    feature_start_dt = datetime.combine(feature_start, time.min, tzinfo=UTC)
    bars: list[Bar] = []
    symbol_chunks = ranking_symbol_chunks(symbols)
    for index, symbol_chunk in enumerate(symbol_chunks, start=1):
        _report_ranking_progress(
            progress_callback,
            f"価格データをまとめて取得しています ({index}/{len(symbol_chunks)})。",
            0.1 + (0.35 * (index - 1) / len(symbol_chunks)),
        )
        bars.extend(await adapter.fetch_ohlcv(symbol_chunk, start=feature_start_dt, end=end_dt))
    _report_ranking_progress(progress_callback, "価格データを整理しています。", 0.45)
    bars_by_symbol = _ranking_bars_by_symbol(symbols, bars)

    available_symbols: list[str] = []
    quotes: list[Quote] = []
    error_rows: list[dict[str, str]] = []
    for symbol in symbols:
        symbol_bars = bars_by_symbol[symbol]
        if not symbol_bars:
            error_rows.append(
                ranking_no_bars_error_row(
                    provider=provider,
                    symbol=symbol,
                    display_start=start,
                    display_end=end,
                    fetch_start=feature_start_dt,
                    fetch_end=end_dt,
                )
            )
            continue
        latest = symbol_bars[-1]
        available_symbols.append(symbol)
        quotes.append(
            Quote(
                symbol=latest.symbol,
                bid=None,
                ask=None,
                last=latest.close,
                ts=latest.ts,
            )
        )

    if not available_symbols:
        _report_ranking_progress(progress_callback, "ランキング対象の価格データがありません。", 1.0)
        return [], error_rows

    _report_ranking_progress(progress_callback, "ファンダメンタル情報を取得しています。", 0.55)
    fundamentals = await adapter.fetch_fundamentals(available_symbols, as_of=end)
    _report_ranking_progress(progress_callback, "スクリーニング用特徴量を作成しています。", 0.65)
    feature_rows = build_daily_snapshots_from_market_data(
        symbols=available_symbols,
        as_of=end,
        quotes=quotes,
        fundamentals=fundamentals,
        bars=bars,
        cfg=settings.feature_builder,
    )
    feature_snapshot = FeatureSnapshot(
        as_of=end,
        provider=adapter.healthcheck().get("provider", provider),
        rows=feature_rows,
        missing_summary=_feature_missing_summary(feature_rows),
        quality_summary=_feature_quality_summary(feature_rows),
    )
    forecast_horizon_days = default_forecast_horizon_days(start, end)
    forecast_consensus_by_symbol = {}
    for index, symbol in enumerate(available_symbols, start=1):
        period_bars = [bar for bar in bars_by_symbol[symbol] if start_dt <= bar.ts <= end_dt]
        forecast_consensus = summarize_forecast_evaluations(
            _available_forecast_evaluations(
                period_bars,
                horizon_days=forecast_horizon_days,
            )
        )
        if forecast_consensus is not None:
            forecast_consensus_by_symbol[forecast_consensus.symbol] = forecast_consensus
        progress = 0.65 + (0.2 * index / len(available_symbols))
        _report_ranking_progress(
            progress_callback,
            f"予測一致を計算しています ({index}/{len(available_symbols)})。",
            progress,
        )

    _report_ranking_progress(progress_callback, "総合スコアを計算しています。", 0.9)
    screening_scores = ScreeningService().score(
        feature_snapshot,
        forecast_consensus_by_symbol=forecast_consensus_by_symbol,
    )
    investment_scores = InvestmentScoringService(weights=settings.scoring.weights).score(
        screening_scores,
        forecast_consensus_by_symbol=forecast_consensus_by_symbol,
    )
    ranked_rows = rank_investment_score_rows(investment_score_rows(investment_scores))
    _report_ranking_progress(progress_callback, "ランキングを並べ替えています。", 0.98)
    return ranked_rows, error_rows


def _ranking_bars_by_symbol(
    symbols: list[str],
    bars: list[Bar],
) -> dict[str, list[Bar]]:
    grouped: dict[str, list[Bar]] = {symbol: [] for symbol in symbols}
    for bar in bars:
        if bar.symbol.raw in grouped:
            grouped[bar.symbol.raw].append(bar)
    for symbol_bars in grouped.values():
        symbol_bars.sort(key=lambda bar: bar.ts)
    return grouped


RankingProgressCallback = Callable[[str, float], None]


def _report_ranking_progress(
    progress_callback: RankingProgressCallback | None,
    message: str,
    ratio: float,
) -> None:
    if progress_callback is not None:
        progress_callback(message, ratio)


def _ranking_build_cache() -> dict[str, dict[str, list[dict[str, str]]]]:
    cache = st.session_state.setdefault(MARKET_DATA_RANKING_BUILD_CACHE_STATE_KEY, {})
    if isinstance(cache, dict):
        return cast(dict[str, dict[str, list[dict[str, str]]]], cache)
    st.session_state[MARKET_DATA_RANKING_BUILD_CACHE_STATE_KEY] = {}
    return {}


def get_cached_ranking_build(
    cache_key: str,
) -> tuple[list[dict[str, str]], list[dict[str, str]]] | None:
    cached = _ranking_build_cache().get(cache_key)
    if cached is None:
        return None
    return cached.get("rows", []), cached.get("error_rows", [])


def set_cached_ranking_build(
    cache_key: str,
    *,
    rows: list[dict[str, str]],
    error_rows: list[dict[str, str]],
) -> None:
    cache = _ranking_build_cache()
    if cache_key in cache:
        cache.pop(cache_key)
    cache[cache_key] = {"rows": rows, "error_rows": error_rows}
    while len(cache) > MAX_RANKING_BUILD_CACHE_ENTRIES:
        oldest_key = next(iter(cache))
        cache.pop(oldest_key)


def _feature_missing_summary(rows: list[DailySnapshot]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for row in rows:
        for feature, is_missing in row.missing.items():
            if is_missing:
                summary[feature] = summary.get(feature, 0) + 1
    return summary


def _feature_quality_summary(rows: list[DailySnapshot]) -> dict[DataQuality, int]:
    summary: dict[DataQuality, int] = {}
    for row in rows:
        summary[row.data_quality] = summary.get(row.data_quality, 0) + 1
    return summary


async def _build_market_data_ranking_rows_from_previews(
    symbols: list[str],
    *,
    start: date,
    end: date,
    provider: str,
    progress_callback: RankingProgressCallback | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    rows: list[dict[str, str]] = []
    error_rows: list[dict[str, str]] = []
    forecast_horizon_days = default_forecast_horizon_days(start, end)
    semaphore = asyncio.Semaphore(MAX_RANKING_CONCURRENT_FETCHES)
    _report_ranking_progress(
        progress_callback,
        "銘柄別の取得に切り替えてランキングを作成しています。",
        0.05,
    )

    async def build_symbol_preview(
        symbol: str,
    ) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        async with semaphore:
            preview = await build_market_data_preview(
                symbol=symbol,
                start=start,
                end=end,
                provider_override=provider,
                forecast_horizon_days=forecast_horizon_days,
            )
        return preview.investment_score_rows, [
            {"symbol": symbol, **error_row} for error_row in preview.error_rows
        ]

    tasks = [asyncio.create_task(build_symbol_preview(symbol)) for symbol in symbols]
    for completed_count, task in enumerate(asyncio.as_completed(tasks), start=1):
        preview_rows, preview_error_rows = await task
        rows.extend(preview_rows)
        error_rows.extend(preview_error_rows)
        _report_ranking_progress(
            progress_callback,
            f"銘柄別に取得しています ({completed_count}/{len(symbols)})。",
            0.1 + (0.85 * completed_count / len(symbols)),
        )
    _report_ranking_progress(progress_callback, "ランキングを並べ替えています。", 0.98)
    return rank_investment_score_rows(rows), error_rows


def _select_ranking_symbol_for_cockpit(symbol: str, provider: str) -> None:
    st.session_state["sidemenu_page"] = SIDEMENU_PAGE_COCKPIT
    st.session_state["market_data_mode"] = MARKET_DATA_MODE_COCKPIT
    st.session_state[MARKET_DATA_PROVIDER_WIDGET_KEY] = provider
    st.session_state["market_data_symbol_candidate"] = symbol_candidate_label(symbol)
    st.session_state.pop(MARKET_DATA_PREVIEW_STATE_KEY, None)
    st.session_state.pop(MARKET_DATA_STATUS_STATE_KEY, None)


def symbol_candidate_label(symbol: str) -> str:
    name = symbol_name(symbol)
    if name:
        return f"{symbol} - {name}"
    return symbol


def _market_data_preview_from_state() -> MarketDataPreview | None:
    preview = st.session_state.get(MARKET_DATA_PREVIEW_STATE_KEY)
    if isinstance(preview, MarketDataPreview):
        return preview
    return None


def _render_market_data_preview_result(preview: MarketDataPreview) -> None:
    symbol_label = _market_data_preview_symbol_label(preview)
    forecast_horizon_days = _render_market_data_cockpit_header(preview, symbol_label)
    forecast_rows = forecast_chart_rows(preview.bars, horizon_days=forecast_horizon_days)
    consensus_rows = forecast_consensus_rows_for_bars(
        preview.bars,
        horizon_days=forecast_horizon_days,
    )
    metric_rows = forecast_metric_rows_for_bars(preview.bars, horizon_days=forecast_horizon_days)

    st.subheader("価格・予測チャート")
    _render_target_symbol_caption(symbol_label)
    for index, message in enumerate(forecast_chart_summary(consensus_rows, metric_rows)):
        if index == 0:
            st.info(message)
        else:
            st.caption(message)
    chart_currency = preview.bars[0].symbol.currency if preview.bars else ""
    _render_market_chart(
        forecast_rows,
        currency=chart_currency,
        title="実績価格と予測",
    )
    st.caption("縦の点線は、実績価格から予測表示へ切り替わる位置です。")
    _render_investment_score_section(preview, symbol_label)

    with st.expander("Forecast details"):
        for index, message in enumerate(forecast_metric_summary(metric_rows)):
            if index == 0:
                st.info(message)
            else:
                st.caption(message)
        st.subheader("Forecast Summary")
        _render_target_symbol_caption(symbol_label)
        _render_table(forecast_consensus_display_rows(consensus_rows), "No forecast summary.")
        st.subheader("Forecast Metrics")
        _render_target_symbol_caption(symbol_label)
        _render_table(forecast_metric_display_rows(metric_rows), "No forecast metrics.")
        if metric_rows:
            col_json, col_csv = st.columns(2)
            col_json.download_button(
                "Download forecast JSON",
                data=forecast_metric_json_download(metric_rows),
                file_name="forecast_metrics.json",
                mime="application/json",
            )
            col_csv.download_button(
                "Download forecast CSV",
                data=forecast_metric_csv_download(metric_rows),
                file_name="forecast_metrics.csv",
                mime="text/csv",
            )

    with st.expander("Screening Score"):
        _render_target_symbol_caption(symbol_label)
        _render_table(preview.screening_rows, "No screening score rows.")
        if preview.screening_rows:
            col_json, col_csv = st.columns(2)
            col_json.download_button(
                "Download screening JSON",
                data=screening_score_json_download(preview.screening_rows),
                file_name="screening_score.json",
                mime="application/json",
            )
            col_csv.download_button(
                "Download screening CSV",
                data=screening_score_csv_download(preview.screening_rows),
                file_name="screening_score.csv",
                mime="text/csv",
            )

    with st.expander("Provider / Quote / OHLCV"):
        st.subheader("Provider")
        _render_target_symbol_caption(symbol_label)
        _render_table(preview.provider_rows, "No provider metadata.")

        st.subheader("Quote")
        _render_target_symbol_caption(symbol_label)
        _render_table(preview.quote_rows, "No quote rows.")

        st.subheader("OHLCV Summary")
        _render_target_symbol_caption(symbol_label)
        _render_table(preview.ohlcv_rows, "No OHLCV rows.")

    with st.expander("FX / Feature Snapshot"):
        st.subheader("FX")
        _render_table(preview.fx_rows, "No FX rows.")

        st.subheader("Feature Snapshot")
        _render_target_symbol_caption(symbol_label)
        _render_table(preview.feature_rows, "No feature snapshot rows.")

    if preview.error_rows:
        st.subheader("補助データの取得警告")
        _render_provider_error_summary(preview.error_rows)


def _render_market_data_cockpit_header(
    preview: MarketDataPreview,
    symbol_label: str,
) -> int:
    st.subheader("銘柄コックピット")
    metadata_col, horizon_col = st.columns([4.0, 1.0])
    provider_name = _metadata_value(preview.provider_rows, "provider") or "unknown"
    as_of = _market_data_as_of(preview)
    with horizon_col:
        forecast_horizon_days = cast(
            int,
            st.number_input(
                "Forecast days",
                min_value=1,
                max_value=30,
                step=1,
                key=MARKET_DATA_FORECAST_DAYS_STATE_KEY,
                help="取得済みデータを使ってチャートと指標だけを再計算します。",
            ),
        )
    reference_period = forecast_reference_period(preview.bars, horizon_days=forecast_horizon_days)
    with metadata_col:
        st.caption(
            f"対象: {symbol_label} / Provider: {provider_name} / "
            f"基準日: {as_of or '未取得'} / 参照期間: {reference_period}日"
        )
    return forecast_horizon_days


def _render_investment_score_section(preview: MarketDataPreview, symbol_label: str) -> None:
    rows = investment_score_display_rows(preview.investment_score_rows)
    if not rows:
        st.info("No investment score rows.")
        return

    row = rows[0]
    score_col, band_col, forecast_col, quality_col, risk_col = st.columns(5)
    score_col.metric("総合スコア", row.get("総合スコア", ""))
    band_col.metric("見方", row.get("見方", ""))
    forecast_col.metric("予測一致", row.get("予測一致", ""))
    quality_col.metric("データ品質", row.get("データ品質", ""))
    risk_col.metric("Risk", row.get("Risk", ""))

    warning = row.get("注意点", "")
    if warning:
        st.warning(warning)
    else:
        st.info("大きな注意点はありません。スコアの内訳も確認してください。")
    for line in investment_score_summary_lines(row):
        st.caption(line)
    _render_score_breakdown_chart(score_component_rows(row))

    with st.expander("Investment Score details / downloads"):
        _render_target_symbol_caption(symbol_label)
        _render_table(rows, "No investment score rows.")
        col_json, col_csv = st.columns(2)
        col_json.download_button(
            "Download investment score JSON",
            data=investment_score_json_download(preview.investment_score_rows),
            file_name="investment_score.json",
            mime="application/json",
        )
        col_csv.download_button(
            "Download investment score CSV",
            data=investment_score_csv_download(preview.investment_score_rows),
            file_name="investment_score.csv",
            mime="text/csv",
        )


def investment_score_summary_lines(row: dict[str, str]) -> list[str]:
    lines = [
        f"{row.get('銘柄', 'この銘柄')} は「{row.get('見方', '要確認')}」として確認できます。",
    ]
    warning = row.get("注意点", "")
    if warning:
        lines.append(f"注意点: {warning}。")
    else:
        lines.append("大きな注意点はありません。")
    note = row.get("補足", "")
    if note:
        lines.append(note)
    return lines[:3]


def score_component_rows(row: dict[str, str]) -> list[dict[str, str]]:
    return [
        {"要素": "Screening", "スコア": row.get("Screening", "")},
        {"要素": "Forecast", "スコア": row.get("予測一致", "")},
        {"要素": "Risk", "スコア": row.get("Risk", "")},
        {"要素": "Data Quality", "スコア": row.get("データ品質", "")},
    ]


def _render_score_breakdown_chart(rows: list[dict[str, str]]) -> None:
    frame = pd.DataFrame(rows)
    frame["score"] = pd.to_numeric(frame["スコア"], errors="coerce")
    frame = frame.dropna(subset=["score"])
    if frame.empty:
        return
    chart = (
        alt.Chart(frame)
        .mark_bar(cornerRadius=4)
        .encode(
            x=alt.X("score:Q", title="Score", scale=alt.Scale(domain=[0, 100])),
            y=alt.Y("要素:N", title=None, sort=None),
            color=alt.Color("要素:N", legend=None),
            tooltip=[
                alt.Tooltip("要素:N", title="要素"),
                alt.Tooltip("score:Q", title="スコア"),
            ],
        )
        .properties(height=150)
    )
    st.altair_chart(chart, use_container_width=True)


def _render_market_chart(
    rows: list[dict[str, str]],
    *,
    currency: str = "",
    title: str = "",
) -> None:
    if not rows:
        st.info("No chart rows.")
        return
    y_axis_title = f"終値 ({currency})" if currency else "終値"
    chart_data = market_chart_long_frame(rows)
    boundary_data = forecast_boundary_frame(rows)
    legend_data = chart_data[["series_label", "line_label"]].drop_duplicates().copy()
    line_type_legend_data = pd.DataFrame(
        [
            {"line_label": "実績", "description": "実線: 実績価格"},
            {"line_label": "予測", "description": "破線: 予測モデル"},
        ]
    )
    disabled_series = alt.selection_point(
        fields=["series_label"],
        on="click",
        toggle="true",
        empty=False,
    )
    chart = (
        alt.Chart(chart_data)
        .mark_line(point=True)
        .encode(
            x=alt.X("date:T", title="Date", axis=alt.Axis(format="%m/%d", labelAngle=0)),
            y=alt.Y("value:Q", title=y_axis_title, scale=alt.Scale(zero=False)),
            color=alt.Color(
                "series_label:N",
                title="価格・モデル",
                legend=None,
            ),
            strokeDash=alt.StrokeDash(
                "line_label:N",
                title="実績/予測",
                scale=alt.Scale(domain=["実績", "予測"], range=[[1, 0], [6, 4]]),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("date:T", title="日付"),
                alt.Tooltip("series_label:N", title="価格・モデル"),
                alt.Tooltip("value:Q", title="終値"),
                alt.Tooltip("line_label:N", title="実績/予測"),
            ],
            opacity=alt.condition(disabled_series, alt.value(0.18), alt.value(1.0)),
        )
        .properties(height=540, width=1400)
    )
    if not boundary_data.empty:
        boundary_rule = (
            alt.Chart(boundary_data)
            .mark_rule(color="#f59e0b", opacity=0.65, strokeDash=[4, 4])
            .encode(x="date:T")
        )
        chart = chart + boundary_rule
    series_legend_base = alt.Chart(legend_data).encode(
        y=alt.Y("series_label:N", title=None, axis=None, sort=None),
        color=alt.Color("series_label:N", title="価格・モデル", legend=None),
        opacity=alt.condition(disabled_series, alt.value(0.25), alt.value(1.0)),
        tooltip=[
            alt.Tooltip("series_label:N", title="価格・モデル"),
            alt.Tooltip("line_label:N", title="実績/予測"),
        ],
    )
    series_legend = series_legend_base.mark_point(filled=True, size=95).encode(
        x=alt.value(12)
    ) + series_legend_base.mark_text(align="left", baseline="middle", dx=16, fontSize=12).encode(
        x=alt.value(12),
        text="series_label:N",
    )
    line_type_legend_base = alt.Chart(line_type_legend_data).encode(
        y=alt.Y("description:N", title=None, axis=None, sort=None),
        strokeDash=alt.StrokeDash(
            "line_label:N",
            scale=alt.Scale(domain=["実績", "予測"], range=[[1, 0], [6, 4]]),
            legend=None,
        ),
    )
    line_type_legend = line_type_legend_base.mark_rule(color="#c9d1dc", strokeWidth=2).encode(
        x=alt.value(12),
        x2=alt.value(46),
    ) + line_type_legend_base.mark_text(
        align="left",
        baseline="middle",
        dx=52,
        fontSize=12,
        color="#c9d1dc",
    ).encode(
        x=alt.value(12),
        text="description:N",
    )
    legend = alt.vconcat(
        series_legend.properties(title="価格・モデル", height=190, width=190),
        line_type_legend.properties(title="実績/予測", height=60, width=190),
        spacing=10,
    )
    combined_chart = (
        alt.hconcat(chart, legend, spacing=10)
        .add_params(disabled_series)
        .resolve_scale(color="shared")
        .configure(background="#090d14")
        .configure_view(fill="#101722", stroke="#344155")
        .configure_axis(
            domainColor="#3b4556",
            gridColor="#2b3646",
            labelColor="#c9d1dc",
            titleColor="#c9d1dc",
            tickColor="#3b4556",
        )
        .configure_title(color="#e5edf7", fontSize=13, anchor="start", offset=8)
        .properties(title=title or None)
    )
    st.altair_chart(
        combined_chart,
        use_container_width=True,
    )


def _render_provider_error_summary(rows: list[dict[str, str]]) -> None:
    if not rows:
        st.warning(
            "Provider から詳細なエラー情報が返りませんでした。設定、銘柄、取得期間を確認してください。"
        )
        return

    for row in provider_error_summary_rows(rows):
        st.warning(f"{row['コード']}: {row['内容']}")
        st.caption(row["次の確認"])

    with st.expander("診断情報", expanded=False):
        st.dataframe(
            provider_error_summary_rows(rows),
            hide_index=True,
            use_container_width=True,
        )
        for row in rows:
            details = format_provider_error_details(row)
            if details:
                st.code(details, language="json")


def provider_error_summary_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [_provider_error_summary_row(row) for row in rows]


def _provider_error_summary_row(row: dict[str, str]) -> dict[str, str]:
    details = _provider_error_details(row)
    request = _provider_error_request(details)
    provider = str(details.get("provider") or row.get("provider") or "")
    symbol = str(request.get("symbol") or row.get("symbol") or "")

    return {
        "コード": row.get("code", "ERROR"),
        "Provider": provider or "-",
        "Symbol": symbol or "-",
        "内容": row.get("message", "Provider request failed"),
        "次の確認": _provider_error_next_action(provider, details, request),
    }


def _provider_error_details(row: dict[str, str]) -> dict[str, object]:
    details = row.get("details", "")
    if not details:
        return {}
    try:
        parsed = json.loads(details)
    except json.JSONDecodeError:
        return {"raw": details}
    if isinstance(parsed, dict):
        return parsed
    return {"raw": parsed}


def _provider_error_request(details: dict[str, object]) -> dict[str, object]:
    request = details.get("request")
    if isinstance(request, dict):
        return request
    return {}


def _provider_error_next_action(
    provider: str,
    details: dict[str, object],
    request: dict[str, object],
) -> str:
    request_error = str(request.get("error", ""))
    provider_label = provider or "外部 provider"

    if "curl: (28)" in request_error or "Resolving timed out" in request_error:
        return (
            f"{provider_label} への外部通信がタイムアウトしています。"
            "ネットワーク/DNS を確認し、時間をおいて再実行してください。"
            "ランキングでは銘柄数や取得期間を絞ると安定しやすくなります。"
        )
    if details.get("reason") == "no_ohlcv_rows":
        return (
            "価格データが返っていないため、ランキングから除外しています。"
            f"{provider_label} 側の提供状況、銘柄コード、取得期間を確認してください。"
        )
    if details.get("requires_external_opt_in") or provider in {"yahoo", "polygon"}:
        return (
            f"{provider_label} は live provider です。"
            "銘柄コード、取得期間、Yahoo 側の提供状況を確認し、必要に応じて再実行してください。"
        )
    return "Provider 設定、銘柄、取得期間を確認して再実行してください。"


def format_provider_error_details(row: dict[str, str]) -> str:
    details = _provider_error_details(row)
    if not details:
        return ""
    return json.dumps(details, ensure_ascii=False, indent=2, sort_keys=True)


def market_chart_frame(rows: list[dict[str, str]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows).set_index("ts")
    frame.index = pd.to_datetime(frame.index).date
    for column in frame.columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def market_chart_long_frame(rows: list[dict[str, str]]) -> pd.DataFrame:
    frame = market_chart_frame(rows).reset_index(names="date")
    long_frame = frame.melt(id_vars="date", var_name="series", value_name="value")
    long_frame = long_frame.dropna(subset=["value"])
    long_frame["line_type"] = long_frame["series"].map(
        lambda series: "actual" if series == "close" else "forecast"
    )
    long_frame["line_label"] = long_frame["line_type"].map(
        lambda line_type: "実績" if line_type == "actual" else "予測"
    )
    long_frame["series_label"] = long_frame["series"].map(_forecast_series_label)
    return long_frame


def forecast_boundary_frame(rows: list[dict[str, str]]) -> pd.DataFrame:
    frame = market_chart_frame(rows).reset_index(names="date")
    actual_rows = frame.dropna(subset=["close"])
    if actual_rows.empty:
        return pd.DataFrame(columns=["date"])
    latest_actual_date = actual_rows["date"].max()
    return pd.DataFrame([{"date": latest_actual_date}])


def forecast_metric_display_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "モデル": _forecast_series_label(row.get("model", "")),
            "銘柄": row.get("symbol", ""),
            "予測日数": row.get("horizon_days", ""),
            "予測終値": row.get("forecast_close", ""),
            "MAE(小さいほど良い)": row.get("mae", ""),
            "RMSE(小さいほど良い)": row.get("rmse", ""),
            "方向一致率(高いほど良い)": row.get("direction_accuracy", ""),
            "評価サンプル数": row.get("sample_count", ""),
        }
        for row in rows
    ]


def forecast_chart_summary(
    consensus_rows: list[dict[str, str]],
    metric_rows: list[dict[str, str]],
) -> list[str]:
    if not consensus_rows:
        return ["予測を表示するには、もう少し価格データが必要です。"]

    row = consensus_rows[0]
    agreement = _forecast_agreement_label(row.get("agreement", ""))
    range_pct = row.get("forecast_range_pct") or "未計算"
    model_count = row.get("model_count") or "0"
    messages = [
        f"{model_count} つの予測モデルの見方は「{agreement}」です。予測の開きは {range_pct} です。",
        "実線はこれまでの価格、点線はモデルごとの予測です。点線同士が近いほど、モデルの見方が近い状態です。",
    ]
    metric_messages = forecast_metric_summary(metric_rows)
    if metric_messages:
        messages.append(metric_messages[0])
    return messages


def forecast_consensus_display_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "銘柄": row.get("symbol", ""),
            "予測日数": row.get("horizon_days", ""),
            "モデル数": row.get("model_count", ""),
            "平均予測": row.get("ensemble_forecast_close", ""),
            "中央値予測": row.get("median_forecast_close", ""),
            "予測下限": row.get("min_forecast_close", ""),
            "予測上限": row.get("max_forecast_close", ""),
            "予測の開き": row.get("forecast_range", ""),
            "予測の開き(%)": row.get("forecast_range_pct", ""),
            "モデル一致度": _forecast_agreement_label(row.get("agreement", "")),
        }
        for row in rows
    ]


def investment_score_display_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "順位": row.get("rank", ""),
            "銘柄": row.get("symbol", ""),
            "銘柄名": symbol_name(row.get("symbol", "")) or "",
            "総合スコア": row.get("total_score", ""),
            "見方": _investment_score_band_label(row.get("score_band", "")),
            "Screening": row.get("screening_score", ""),
            "予測一致": row.get("forecast_agreement_score", ""),
            "データ品質": row.get("data_quality_score", ""),
            "Risk": row.get("risk_signal_score", "") or "未接続",
            "注意点": _investment_warning_label(row.get("warnings", "")),
            "補足": row.get("note", ""),
        }
        for row in rows
    ]


def forecast_metric_summary(rows: list[dict[str, str]]) -> list[str]:
    candidates: list[tuple[Decimal, dict[str, str]]] = []
    for row in rows:
        rmse = _optional_decimal_from_text(row.get("rmse", ""))
        sample_count = _int_from_text(row.get("sample_count", ""))
        if rmse is None or sample_count <= 0:
            continue
        candidates.append((rmse, row))

    if not candidates:
        return [
            "予測評価に必要なサンプルがまだ不足しています。日付範囲を広げるとモデル比較が安定します。"
        ]

    best_rmse, best_row = min(candidates, key=lambda item: item[0])
    best_label = _forecast_series_label(best_row.get("model", ""))
    direction = best_row.get("direction_accuracy") or "未計算"
    return [
        (
            f"今回の比較では「{best_label}」が RMSE {best_rmse} で最も誤差が小さいです。"
            f"方向一致率は {direction} です。"
        ),
        "誤差と方向一致率で、モデルの当たりやすさを比べます。",
    ]


def _forecast_series_label(series: str) -> str:
    if series == "close":
        return FORECAST_ACTUAL_LABEL
    return forecast_model_display_name(series)


def _forecast_agreement_label(value: str) -> str:
    labels = {
        "HIGH": "高い",
        "MEDIUM": "中くらい",
        "LOW": "低い",
        "UNKNOWN": "未判定",
    }
    return labels.get(value, value)


def _investment_score_band_label(value: str) -> str:
    labels = {
        "STRONG": "強め",
        "BALANCED": "バランス型",
        "CAUTION": "注意して確認",
        "REVIEW": "要確認",
    }
    return labels.get(value, value)


def _investment_warning_label(value: str) -> str:
    if not value:
        return ""
    labels = {
        "data_quality:warn": "データ品質に注意",
        "data_quality:block": "データ不足が大きい",
        "model_disagreement:high": "モデルの見方が割れています",
        "model_count:insufficient": "予測モデル数が少なめです",
    }
    return ", ".join(labels.get(item.strip(), item.strip()) for item in value.split(","))


def _int_from_text(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return 0


def _metadata_value(rows: list[dict[str, str]], field: str) -> str:
    for row in rows:
        if row.get("field") == field:
            return row.get("value", "")
    return ""


def _market_data_as_of(preview: MarketDataPreview) -> str:
    if preview.bars:
        return preview.bars[-1].ts.date().isoformat()
    for row in preview.ohlcv_rows:
        last_ts = row.get("last_ts", "")
        if last_ts:
            return last_ts[:10]
    for row in preview.quote_rows:
        ts = row.get("ts", "")
        if ts:
            return ts[:10]
    return ""


def _market_data_preview_symbol_label(preview: MarketDataPreview) -> str:
    symbol = _market_data_preview_symbol(preview)
    if not symbol:
        return "selected symbol"
    name = symbol_name(symbol)
    if name:
        return f"{symbol} - {name}"
    return symbol


def _market_data_preview_symbol(preview: MarketDataPreview) -> str:
    if preview.bars:
        return preview.bars[0].symbol.raw
    for rows in (
        getattr(preview, "investment_score_rows", []),
        preview.screening_rows,
        preview.ohlcv_rows,
        preview.quote_rows,
        preview.feature_rows,
    ):
        for row in rows:
            symbol = row.get("symbol", "").strip()
            if symbol:
                return symbol
    return ""


def _render_target_symbol_caption(symbol_label: str) -> None:
    st.caption(f"対象: {symbol_label}")


if __name__ == "__main__":
    main()
