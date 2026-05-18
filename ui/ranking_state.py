from __future__ import annotations

import streamlit as st

from ui.ranking import (
    RANKING_ASSET_TYPE_LABELS,
    RANKING_DIVIDEND_LABELS,
    RANKING_FILTER_DEFAULTS,
    RANKING_MARKET_LABELS,
    RANKING_METRIC_FILTER_DEFAULTS,
    RANKING_PRODUCT_TYPE_LABELS,
    RANKING_PURPOSE_LABELS,
    RANKING_REGION_LABELS,
    initial_ranking_selected_labels,
    ranking_filter_signature,
    ranking_symbols_state_key,
    symbol_candidate_labels,
)
from ui.state import (
    MARKET_DATA_RANKING_ERROR_STATE_KEY,
    MARKET_DATA_RANKING_FILTERS_STATE_KEY,
    MARKET_DATA_RANKING_SELECTED_LABELS_STATE_KEY,
    MARKET_DATA_RANKING_STATE_KEY,
    RANKING_FILTER_DIALOG_STATE_KEY,
)


def ranking_filter_value(key: str, default: str) -> str:
    stored_filters = st.session_state.get(MARKET_DATA_RANKING_FILTERS_STATE_KEY, {})
    if key in st.session_state:
        value = st.session_state.get(key, default)
    elif isinstance(stored_filters, dict) and key in stored_filters:
        value = stored_filters.get(key, default)
    else:
        value = default
    return str(value) if value is not None else default


def ranking_filter_bool(key: str, default: bool) -> bool:
    stored_filters = st.session_state.get(MARKET_DATA_RANKING_FILTERS_STATE_KEY, {})
    if key in st.session_state:
        value = st.session_state.get(key, default)
    elif isinstance(stored_filters, dict) and key in stored_filters:
        value = stored_filters.get(key, default)
    else:
        value = default
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes", "on"}


def current_ranking_filter_state() -> dict[str, str]:
    filters = {
        key: ranking_filter_value(key, default) for key, default in RANKING_FILTER_DEFAULTS.items()
    }
    for key, default in RANKING_METRIC_FILTER_DEFAULTS.items():
        if isinstance(default, bool):
            filters[key] = str(ranking_filter_bool(key, default))
        else:
            filters[key] = ranking_filter_value(key, default)
    return filters


def persist_ranking_filter_state() -> dict[str, str]:
    filters = current_ranking_filter_state()
    st.session_state[MARKET_DATA_RANKING_FILTERS_STATE_KEY] = filters
    return filters


def ranking_filter_summary() -> str:
    region = RANKING_REGION_LABELS.get(
        ranking_filter_value("market_data_ranking_region", "japan"),
        "国内",
    )
    product_type = RANKING_PRODUCT_TYPE_LABELS.get(
        ranking_filter_value("market_data_ranking_product_type", "stock"),
        "株式",
    )
    ranking_purpose = RANKING_PURPOSE_LABELS.get(
        ranking_filter_value("market_data_ranking_purpose", "overall"),
        "総合評価",
    )
    market = RANKING_MARKET_LABELS.get(
        ranking_filter_value("market_data_ranking_market", "all"),
        "すべて",
    )
    asset_type = RANKING_ASSET_TYPE_LABELS.get(
        ranking_filter_value("market_data_ranking_asset_type", "all"),
        "すべて",
    )
    dividend = RANKING_DIVIDEND_LABELS.get(
        ranking_filter_value("market_data_ranking_dividend", "all"),
        "指定なし",
    )
    min_dividend = ranking_filter_value("market_data_ranking_min_dividend", "0.0")
    dividend_text = (
        f"配当利回り {min_dividend}% 以上"
        if ranking_filter_bool("market_data_ranking_dividend_enabled", False)
        else "配当利回り 指定なし"
    )
    return (
        f"条件: {region} / {product_type} / {ranking_purpose} / "
        f"{market} / {asset_type} / {dividend_text} / {dividend}"
    )


def ranking_filter_signature_from_state() -> str:
    return ranking_filter_signature(
        region=ranking_filter_value("market_data_ranking_region", "japan"),
        product_type=ranking_filter_value("market_data_ranking_product_type", "stock"),
        ranking_purpose=ranking_filter_value("market_data_ranking_purpose", "overall"),
        purpose="all",
        period_preset=ranking_filter_value("market_data_ranking_period", "short"),
        market=ranking_filter_value("market_data_ranking_market", "all"),
        asset_type=ranking_filter_value("market_data_ranking_asset_type", "all"),
        currency=ranking_filter_value("market_data_ranking_currency", "all"),
        dividend_category=ranking_filter_value("market_data_ranking_dividend", "all"),
        min_dividend_yield_pct=ranking_filter_value("market_data_ranking_min_dividend", "0.0"),
        market_cap_tier=ranking_filter_value("market_data_ranking_market_cap", "all"),
        index_family=ranking_filter_value("market_data_ranking_index_family", "all"),
        max_expense_ratio_pct=ranking_filter_value("market_data_ranking_max_expense", "1.00"),
        complexity=ranking_filter_value("market_data_ranking_complexity", "standard"),
        risk_band=ranking_filter_value("market_data_ranking_risk_band", "all"),
        theme=ranking_filter_value("market_data_ranking_theme", "all"),
        query=ranking_filter_value("market_data_ranking_symbol_query", ""),
        per_enabled=ranking_filter_bool("market_data_ranking_per_enabled", False),
        per_min=ranking_filter_value("market_data_ranking_per_min", "2.0"),
        per_max=ranking_filter_value("market_data_ranking_per_max", "20.0"),
        pbr_enabled=ranking_filter_bool("market_data_ranking_pbr_enabled", False),
        pbr_min=ranking_filter_value("market_data_ranking_pbr_min", "0.5"),
        pbr_max=ranking_filter_value("market_data_ranking_pbr_max", "2.0"),
        dividend_yield_enabled=ranking_filter_bool(
            "market_data_ranking_dividend_enabled",
            False,
        ),
        dividend_yield_max_pct=ranking_filter_value("market_data_ranking_dividend_max", "10.0"),
        roe_enabled=ranking_filter_bool("market_data_ranking_roe_enabled", False),
        roe_min_pct=ranking_filter_value("market_data_ranking_roe_min", "8.0"),
        roe_max_pct=ranking_filter_value("market_data_ranking_roe_max", "30.0"),
        consensus_enabled=ranking_filter_bool("market_data_ranking_consensus_enabled", False),
        consensus_min=ranking_filter_value("market_data_ranking_consensus_min", "2.5"),
        consensus_max=ranking_filter_value("market_data_ranking_consensus_max", "5.0"),
        limit=0,
    )


def initial_ranking_selected_labels_for_key(
    *,
    selection_key: str,
    labels: list[str],
    stored_selected_labels: list[str],
) -> list[str]:
    if selection_key not in st.session_state:
        return labels
    return initial_ranking_selected_labels(labels, stored_selected_labels)


def ensure_ranking_selection_widget_state(
    *,
    selection_key: str,
    labels: list[str],
    stored_selected_labels: list[str],
) -> None:
    if selection_key not in st.session_state:
        selected_labels = initial_ranking_selected_labels_for_key(
            selection_key=selection_key,
            labels=labels,
            stored_selected_labels=stored_selected_labels,
        )
        st.session_state[selection_key] = selected_labels
        st.session_state[MARKET_DATA_RANKING_SELECTED_LABELS_STATE_KEY] = selected_labels


def sync_ranking_selection_state(
    selection_key: str,
    selected_labels: list[str],
    *,
    update_widget_state: bool = False,
) -> None:
    st.session_state[MARKET_DATA_RANKING_SELECTED_LABELS_STATE_KEY] = selected_labels
    if update_widget_state:
        st.session_state[selection_key] = selected_labels


def apply_ranking_filter_state(
    preview_rows: list[dict[str, str]],
    filter_signature: str,
) -> None:
    selected_labels = symbol_candidate_labels(preview_rows)
    st.session_state["market_data_ranking_filter_signature"] = filter_signature
    sync_ranking_selection_state(
        ranking_symbols_state_key(filter_signature),
        selected_labels,
        update_widget_state=True,
    )
    st.session_state.pop(MARKET_DATA_RANKING_STATE_KEY, None)
    st.session_state.pop(MARKET_DATA_RANKING_ERROR_STATE_KEY, None)
    st.session_state[RANKING_FILTER_DIALOG_STATE_KEY] = False


def clear_ranking_filter_state() -> None:
    for key, default in {**RANKING_FILTER_DEFAULTS, **RANKING_METRIC_FILTER_DEFAULTS}.items():
        if isinstance(default, bool):
            st.session_state[key] = default
        elif key.endswith(("_min", "_max")) or key in {
            "market_data_ranking_min_dividend",
            "market_data_ranking_dividend_max",
            "market_data_ranking_max_expense",
        }:
            st.session_state[key] = float(default)
        else:
            st.session_state[key] = default
    st.session_state.pop(MARKET_DATA_RANKING_FILTERS_STATE_KEY, None)
    st.session_state.pop(MARKET_DATA_RANKING_SELECTED_LABELS_STATE_KEY, None)
    st.session_state.pop(MARKET_DATA_RANKING_STATE_KEY, None)
    st.session_state.pop(MARKET_DATA_RANKING_ERROR_STATE_KEY, None)
