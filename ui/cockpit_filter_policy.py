"""Pure Cockpit symbol-filter defaults, filtering, and search policy."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ui.ranking import (
    RANKING_INVESTMENT_THEME_LABELS,
    RANKING_OFFICIAL_SECTOR_LABELS,
    filter_symbol_universe_rows,
    ranking_detail_filters_for_category,
)

MARKET_DATA_COCKPIT_FILTER_DEFAULTS: dict[str, str | bool] = {
    "market_data_cockpit_region": "all",
    "market_data_cockpit_product_type": "all",
    "market_data_cockpit_official_sector": "all",
    "market_data_cockpit_theme": "all",
    "market_data_cockpit_market_cap": "all",
    "market_data_cockpit_index_family": "all",
    "market_data_cockpit_max_expense": "2.00",
    "market_data_cockpit_complexity": "all",
    "market_data_cockpit_dividend": "all",
    "market_data_cockpit_currency": "all",
    "market_data_cockpit_nisa": "all",
    "market_data_cockpit_risk_band": "all",
    "market_data_cockpit_dividend_enabled": False,
    "market_data_cockpit_min_dividend": "3.0",
    "market_data_cockpit_dividend_max": "10.0",
    "market_data_cockpit_per_enabled": False,
    "market_data_cockpit_per_min": "2.0",
    "market_data_cockpit_per_max": "20.0",
    "market_data_cockpit_pbr_enabled": False,
    "market_data_cockpit_pbr_min": "0.5",
    "market_data_cockpit_pbr_max": "2.0",
    "market_data_cockpit_roe_enabled": False,
    "market_data_cockpit_roe_min": "8.0",
    "market_data_cockpit_roe_max": "30.0",
}


def _truthy_filter_value(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def cockpit_detail_filters_for_category(region: str, product_type: str) -> frozenset[str]:
    return frozenset(ranking_detail_filters_for_category(region, product_type))


def cockpit_filter_has_active_conditions_from_values(
    values: Mapping[str, object],
) -> bool:
    region = str(values.get("market_data_cockpit_region", "all"))
    product_type = str(values.get("market_data_cockpit_product_type", "all"))
    detail_filters = cockpit_detail_filters_for_category(region, product_type)
    selector_keys = [
        "market_data_cockpit_region",
        "market_data_cockpit_product_type",
        "market_data_cockpit_currency",
    ]
    if "official_sector" in detail_filters:
        selector_keys.append("market_data_cockpit_official_sector")
    if "investment_theme" in detail_filters:
        selector_keys.append("market_data_cockpit_theme")
    if "market_cap" in detail_filters:
        selector_keys.append("market_data_cockpit_market_cap")
    if "dividend_yield" in detail_filters:
        selector_keys.append("market_data_cockpit_dividend")
    if "nisa_eligibility" in detail_filters:
        selector_keys.append("market_data_cockpit_nisa")
    if "risk_band" in detail_filters:
        selector_keys.append("market_data_cockpit_risk_band")
    if "benchmark_index" in detail_filters:
        selector_keys.append("market_data_cockpit_index_family")
    if "complexity" in detail_filters:
        selector_keys.append("market_data_cockpit_complexity")
    for key in selector_keys:
        default = MARKET_DATA_COCKPIT_FILTER_DEFAULTS[key]
        if str(values.get(key, default)) != str(default):
            return True
    if "expense_ratio" in detail_filters:
        default = str(MARKET_DATA_COCKPIT_FILTER_DEFAULTS["market_data_cockpit_max_expense"])
        if str(values.get("market_data_cockpit_max_expense", default)).strip() != default:
            return True
    metric_enabled_keys: list[str] = []
    if "dividend_yield" in detail_filters:
        metric_enabled_keys.append("market_data_cockpit_dividend_enabled")
    if "per" in detail_filters:
        metric_enabled_keys.append("market_data_cockpit_per_enabled")
    if "pbr" in detail_filters:
        metric_enabled_keys.append("market_data_cockpit_pbr_enabled")
    if "roe" in detail_filters:
        metric_enabled_keys.append("market_data_cockpit_roe_enabled")
    return any(_truthy_filter_value(values.get(key, False)) for key in metric_enabled_keys)


def cockpit_filtered_symbol_rows_from_values(
    rows: list[dict[str, str]],
    *,
    region: str,
    product_type: str,
    currency: str,
    dividend_category: str,
    market_cap_tier: str,
    nisa_eligibility: str,
    risk_band: str,
    official_sector: str,
    theme: str,
    index_family: str,
    max_expense_ratio_pct: Decimal | str | int | float,
    complexity: str,
    dividend_yield_enabled: bool,
    min_dividend_yield_pct: Decimal | str | int | float,
    dividend_yield_max_pct: Decimal | str | int | float,
    per_enabled: bool,
    per_min: Decimal | str | int | float,
    per_max: Decimal | str | int | float,
    pbr_enabled: bool,
    pbr_min: Decimal | str | int | float,
    pbr_max: Decimal | str | int | float,
    roe_enabled: bool,
    roe_min_pct: Decimal | str | int | float,
    roe_max_pct: Decimal | str | int | float,
    active_detail_filters: frozenset[str] | None = None,
) -> list[dict[str, str]]:
    return filter_symbol_universe_rows(
        rows,
        region=region,
        product_type=product_type,
        currency=currency,
        dividend_category=dividend_category,
        market_cap_tier=market_cap_tier,
        index_family=index_family,
        max_expense_ratio_pct=str(max_expense_ratio_pct),
        complexity=complexity,
        nisa_eligibility=nisa_eligibility,
        risk_band=risk_band,
        official_sector=official_sector,
        theme=theme,
        dividend_yield_enabled=dividend_yield_enabled,
        min_dividend_yield_pct=str(min_dividend_yield_pct),
        dividend_yield_max_pct=str(dividend_yield_max_pct),
        per_enabled=per_enabled,
        per_min=str(per_min),
        per_max=str(per_max),
        pbr_enabled=pbr_enabled,
        pbr_min=str(pbr_min),
        pbr_max=str(pbr_max),
        roe_enabled=roe_enabled,
        roe_min_pct=str(roe_min_pct),
        roe_max_pct=str(roe_max_pct),
        limit=len(rows),
        apply_universe_policy=False,
        active_detail_filters=active_detail_filters,
    )


def cockpit_keyword_filtered_symbol_rows(
    rows: list[dict[str, str]],
    query: str,
) -> list[dict[str, str]]:
    normalized_query = _normalized_cockpit_search_text(query)
    if not normalized_query:
        return rows
    matched_rows = [
        row for row in rows if cockpit_symbol_search_rank(row, normalized_query) is not None
    ]

    def sort_key(row: Mapping[str, object]) -> tuple[int, str]:
        rank = cockpit_symbol_search_rank(row, normalized_query)
        return (rank if rank is not None else 99, str(row.get("symbol", "")).upper())

    return sorted(
        matched_rows,
        key=sort_key,
    )


def _normalized_cockpit_search_text(value: object) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _cockpit_search_field_text(row: Mapping[str, object], *fields: str) -> str:
    values: list[str] = []
    for field in fields:
        value = row.get(field)
        if isinstance(value, list | tuple | set):
            values.extend(str(item) for item in value)
        elif value is not None:
            values.append(str(value))
    return _normalized_cockpit_search_text(" ".join(values))


def cockpit_symbol_search_rank(
    row: Mapping[str, object],
    query: str,
) -> int | None:
    """Return the user-facing Cockpit search rank; lower values are better."""

    normalized_query = _normalized_cockpit_search_text(query)
    if not normalized_query:
        return 0
    symbol = _cockpit_search_field_text(row, "symbol")
    aliases = _cockpit_search_field_text(row, "aliases", "alias")
    name = _cockpit_search_field_text(row, "name")
    sector = _cockpit_search_field_text(
        row,
        "sector",
        "industry",
        "sector_gics",
        "industry_gics",
        "subindustry_gics",
        "tse_33_industry",
        "topix_17",
    )
    theme = _cockpit_search_field_text(row, "theme")
    sector = _normalized_cockpit_search_text(
        f"{sector} {RANKING_OFFICIAL_SECTOR_LABELS.get(str(row.get('sector', '')), '')}"
    )
    theme = _normalized_cockpit_search_text(
        f"{theme} {RANKING_INVESTMENT_THEME_LABELS.get(str(row.get('theme', '')), '')}"
    )
    tags = _cockpit_search_field_text(row, "tags", "smai_theme_tags")
    ranked_matches = (
        symbol == normalized_query,
        symbol.startswith(normalized_query),
        aliases.startswith(normalized_query),
        name.startswith(normalized_query),
        normalized_query in aliases,
        normalized_query in name,
        normalized_query in sector,
        normalized_query in theme,
        normalized_query in tags,
    )
    return next((rank for rank, matched in enumerate(ranked_matches) if matched), None)
