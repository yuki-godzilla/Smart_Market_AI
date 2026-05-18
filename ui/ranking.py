from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from backend.core.errors import AppError
from ui.symbol_universe import symbol_universe_csv_rows

MAX_RANKING_CONCURRENT_FETCHES = 8
MAX_RANKING_BATCH_FETCH_SYMBOLS = 10
MAX_RANKING_BUILD_CACHE_ENTRIES = 8
LIVE_MARKET_DATA_PROVIDERS = {"yahoo", "polygon"}
LIVE_RANKING_WARNING_SYMBOL_THRESHOLD = 30

RANKING_PRESET_BALANCED = "balanced"
RANKING_PRESET_FORECAST = "forecast"
RANKING_PRESET_QUALITY = "quality"
RANKING_PRESET_RISK = "risk"
RANKING_WEIGHT_PRESET_LABELS = {
    RANKING_PRESET_BALANCED: "バランス重視",
    RANKING_PRESET_FORECAST: "予測一致重視",
    RANKING_PRESET_QUALITY: "データ品質重視",
    RANKING_PRESET_RISK: "リスク控えめ",
}
RANKING_WEIGHT_PRESETS: dict[str, dict[str, Decimal]] = {
    RANKING_PRESET_BALANCED: {
        "screening_score": Decimal("0.50"),
        "forecast_agreement_score": Decimal("0.20"),
        "data_quality_score": Decimal("0.20"),
        "risk_signal_score": Decimal("0.10"),
    },
    RANKING_PRESET_FORECAST: {
        "screening_score": Decimal("0.35"),
        "forecast_agreement_score": Decimal("0.40"),
        "data_quality_score": Decimal("0.15"),
        "risk_signal_score": Decimal("0.10"),
    },
    RANKING_PRESET_QUALITY: {
        "screening_score": Decimal("0.35"),
        "forecast_agreement_score": Decimal("0.15"),
        "data_quality_score": Decimal("0.40"),
        "risk_signal_score": Decimal("0.10"),
    },
    RANKING_PRESET_RISK: {
        "screening_score": Decimal("0.35"),
        "forecast_agreement_score": Decimal("0.15"),
        "data_quality_score": Decimal("0.20"),
        "risk_signal_score": Decimal("0.30"),
    },
}
RANKING_PERIOD_PRESETS = {
    "short": 7,
    "medium": 30,
    "long": 365,
}
RANKING_PERIOD_LABELS = {
    "short": "短期: 1週間",
    "medium": "中期: 1か月",
    "long": "長期: 1年",
}
RANKING_MARKET_LABELS = {
    "all": "すべて",
    "jp": "日本株",
    "us": "米国株",
    "etf": "ETF",
}
RANKING_ASSET_TYPE_LABELS = {
    "all": "すべて",
    "stock": "個別株",
    "etf": "ETF",
    "adr": "ADR",
}
RANKING_CURRENCY_LABELS = {
    "all": "すべて",
    "JPY": "JPY",
    "USD": "USD",
}
RANKING_DIVIDEND_LABELS = {
    "all": "指定なし",
    "high_dividend": "高配当候補",
    "dividend": "配当あり",
    "none": "配当なし",
    "growth_dividend": "連続増配候補",
}
RANKING_COMPLEXITY_LABELS = {
    "beginner": "初心者向け",
    "standard": "標準まで",
    "all": "上級者向けも含める",
}
RANKING_THEME_LABELS = {
    "all": "指定なし",
    "technology": "テクノロジー",
    "semiconductor": "半導体",
    "financial": "金融",
    "consumer": "消費",
    "healthcare": "ヘルスケア",
    "energy": "エネルギー",
    "automotive": "自動車",
    "trading": "商社",
    "index": "インデックス",
    "dividend": "高配当",
}
RANKING_MARKET_CAP_LABELS = {
    "all": "指定なし",
    "mega": "超大型",
    "large": "大型",
    "mid": "中型",
}
RANKING_INDEX_FAMILY_LABELS = {
    "all": "指定なし",
    "sp500": "S&P 500",
    "nasdaq100": "NASDAQ 100",
    "total_us": "全米",
    "small_us": "米国小型",
}
RANKING_FILTER_DEFAULTS: dict[str, str] = {
    "market_data_ranking_market": "all",
    "market_data_ranking_asset_type": "all",
    "market_data_ranking_currency": "all",
    "market_data_ranking_dividend": "all",
    "market_data_ranking_min_dividend": "0.0",
    "market_data_ranking_market_cap": "all",
    "market_data_ranking_index_family": "all",
    "market_data_ranking_max_expense": "1.00",
    "market_data_ranking_complexity": "standard",
    "market_data_ranking_theme": "all",
    "market_data_ranking_symbol_query": "",
}
RANKING_METRIC_FILTER_DEFAULTS: dict[str, str | bool] = {
    "market_data_ranking_per_enabled": False,
    "market_data_ranking_per_min": "2.0",
    "market_data_ranking_per_max": "20.0",
    "market_data_ranking_pbr_enabled": False,
    "market_data_ranking_pbr_min": "0.5",
    "market_data_ranking_pbr_max": "2.0",
    "market_data_ranking_dividend_enabled": False,
    "market_data_ranking_dividend_min": "3.0",
    "market_data_ranking_dividend_max": "10.0",
    "market_data_ranking_roe_enabled": False,
    "market_data_ranking_roe_min": "8.0",
    "market_data_ranking_roe_max": "30.0",
    "market_data_ranking_consensus_enabled": False,
    "market_data_ranking_consensus_min": "2.5",
    "market_data_ranking_consensus_max": "5.0",
}


def symbol_candidate_labels(rows: list[dict[str, str]], query: str = "") -> list[str]:
    labels = [f"{row['symbol']} - {row['name']}" for row in rows]
    normalized_query = query.strip().lower()
    if normalized_query:
        labels = [label for label in labels if normalized_query in label.lower()]
    return labels


def ranking_period_label(preset: str) -> str:
    return RANKING_PERIOD_LABELS.get(preset, preset)


def ranking_period_dates(preset: str, end: date) -> tuple[date, date]:
    days = RANKING_PERIOD_PRESETS.get(preset, RANKING_PERIOD_PRESETS["medium"])
    return end - timedelta(days=days), end


def symbol_universe_rows(
    reference_rows: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    if reference_rows is None:
        rows = symbol_universe_csv_rows()
    else:
        csv_rows_by_symbol = {
            row["symbol"].upper(): row for row in symbol_universe_csv_rows() if row.get("symbol")
        }
        rows = [
            {
                **csv_rows_by_symbol.get(row.get("symbol", "").strip().upper(), {}),
                **row,
            }
            for row in reference_rows
        ]
    return [_symbol_universe_row(row) for row in rows]


def filter_symbol_universe_rows(
    rows: list[dict[str, str]],
    *,
    purpose: str = "all",
    market: str = "all",
    asset_type: str = "all",
    currency: str = "all",
    dividend_category: str = "all",
    min_dividend_yield_pct: Decimal | str | int = Decimal("0"),
    market_cap_tier: str = "all",
    index_family: str = "all",
    max_expense_ratio_pct: Decimal | str | int = Decimal("1.00"),
    complexity: str = "standard",
    theme: str = "all",
    query: str = "",
    per_enabled: bool = False,
    per_min: Decimal | str | int = Decimal("2.0"),
    per_max: Decimal | str | int = Decimal("20.0"),
    pbr_enabled: bool = False,
    pbr_min: Decimal | str | int = Decimal("0.5"),
    pbr_max: Decimal | str | int = Decimal("2.0"),
    dividend_yield_enabled: bool = False,
    dividend_yield_max_pct: Decimal | str | int = Decimal("10.0"),
    roe_enabled: bool = False,
    roe_min_pct: Decimal | str | int = Decimal("8.0"),
    roe_max_pct: Decimal | str | int = Decimal("30.0"),
    consensus_enabled: bool = False,
    consensus_min: Decimal | str | int = Decimal("2.5"),
    consensus_max: Decimal | str | int = Decimal("5.0"),
    limit: int = 10,
) -> list[dict[str, str]]:
    normalized_query = query.strip().lower()
    min_dividend = _decimal_filter_value(min_dividend_yield_pct, Decimal("0"))
    max_expense = _decimal_filter_value(max_expense_ratio_pct, Decimal("1.00"))
    filtered: list[dict[str, str]] = []
    for row in rows:
        tags = _symbol_universe_values(row, "tags")
        if purpose != "all" and purpose not in tags:
            continue
        if market == "etf":
            if row.get("asset_type") != "etf":
                continue
        elif market != "all" and row.get("market") != market:
            continue
        if asset_type != "all" and row.get("asset_type") != asset_type:
            continue
        if currency != "all" and row.get("currency") != currency:
            continue
        if dividend_category != "all" and row.get("dividend_category") != dividend_category:
            continue
        if market_cap_tier != "all" and row.get("market_cap_tier") != market_cap_tier:
            continue
        if index_family != "all" and row.get("index_family") != index_family:
            continue
        expense_ratio = row.get("expense_ratio_pct", "")
        if row.get("asset_type") == "etf" and expense_ratio:
            if _decimal_filter_value(expense_ratio, Decimal("99")) > max_expense:
                continue
        if not _symbol_complexity_allowed(row.get("complexity", "standard"), complexity):
            continue
        if theme != "all" and theme not in tags and row.get("theme") != theme:
            continue
        if per_enabled and not _row_decimal_in_range(row, "per", per_min, per_max):
            continue
        if pbr_enabled and not _row_decimal_in_range(row, "pbr", pbr_min, pbr_max):
            continue
        if dividend_yield_enabled and not _row_decimal_in_range(
            row,
            "dividend_yield_pct",
            min_dividend,
            dividend_yield_max_pct,
        ):
            continue
        if roe_enabled and not _row_decimal_in_range(row, "roe_pct", roe_min_pct, roe_max_pct):
            continue
        if consensus_enabled and not _row_decimal_in_range(
            row,
            "consensus_rating",
            consensus_min,
            consensus_max,
        ):
            continue
        if normalized_query:
            label = " ".join(
                [
                    row.get("symbol", ""),
                    row.get("name", ""),
                    row.get("theme", ""),
                    row.get("dividend_category", ""),
                    row.get("tags", ""),
                    row.get("aliases", ""),
                ]
            ).lower()
            if normalized_query not in label:
                continue
        filtered.append(row)
    return filtered[: max(limit, 0)]


def ranking_filter_signature(
    *,
    purpose: str,
    period_preset: str,
    market: str,
    asset_type: str,
    currency: str,
    dividend_category: str,
    min_dividend_yield_pct: str = "0.0",
    market_cap_tier: str = "all",
    index_family: str = "all",
    max_expense_ratio_pct: str = "1.00",
    complexity: str,
    theme: str,
    query: str,
    per_enabled: bool = False,
    per_min: str = "2.0",
    per_max: str = "20.0",
    pbr_enabled: bool = False,
    pbr_min: str = "0.5",
    pbr_max: str = "2.0",
    dividend_yield_enabled: bool = False,
    dividend_yield_max_pct: str = "10.0",
    roe_enabled: bool = False,
    roe_min_pct: str = "8.0",
    roe_max_pct: str = "30.0",
    consensus_enabled: bool = False,
    consensus_min: str = "2.5",
    consensus_max: str = "5.0",
    limit: int,
) -> str:
    _ = period_preset
    return "|".join(
        [
            purpose,
            market,
            asset_type,
            currency,
            dividend_category,
            min_dividend_yield_pct,
            market_cap_tier,
            index_family,
            max_expense_ratio_pct,
            complexity,
            theme,
            query.strip().lower(),
            str(per_enabled),
            per_min,
            per_max,
            str(pbr_enabled),
            pbr_min,
            pbr_max,
            str(dividend_yield_enabled),
            dividend_yield_max_pct,
            str(roe_enabled),
            roe_min_pct,
            roe_max_pct,
            str(consensus_enabled),
            consensus_min,
            consensus_max,
            str(limit),
        ]
    )


def ranking_symbols_state_key(filter_signature: str) -> str:
    return f"market_data_ranking_symbols_{filter_signature}"


def valid_ranking_selected_labels(
    selected_labels: list[str],
    available_labels: list[str],
) -> list[str]:
    available = set(available_labels)
    return [label for label in selected_labels if label in available]


def initial_ranking_selected_labels(
    labels: list[str],
    stored_selected_labels: list[str],
) -> list[str]:
    selected_labels = valid_ranking_selected_labels(stored_selected_labels, labels)
    return selected_labels or labels


def ranking_weight_preset_label(preset: str) -> str:
    return RANKING_WEIGHT_PRESET_LABELS.get(preset, preset)


def ranking_provider_error_rows(
    provider: str,
    symbols: list[str],
    exc: AppError,
) -> list[dict[str, str]]:
    details = dict(exc.details)
    details.setdefault("provider", provider)
    details.setdefault("symbols", symbols)
    return [
        {
            "symbol": _ranking_error_symbol_summary(symbols),
            "code": exc.code,
            "message": exc.message,
            "details": json.dumps(details, ensure_ascii=False, sort_keys=True),
        }
    ]


def ranking_symbol_chunks(symbols: list[str]) -> list[list[str]]:
    return [
        symbols[index : index + MAX_RANKING_BATCH_FETCH_SYMBOLS]
        for index in range(0, len(symbols), MAX_RANKING_BATCH_FETCH_SYMBOLS)
    ] or [[]]


def live_ranking_symbol_warning_message(provider: str, symbol_count: int) -> str | None:
    if provider not in LIVE_MARKET_DATA_PROVIDERS:
        return None
    if symbol_count <= LIVE_RANKING_WARNING_SYMBOL_THRESHOLD:
        return None
    return (
        f"{provider} は外部通信のため、{symbol_count} 銘柄のランキング作成には時間がかかる場合があります。"
        "通信が不安定な場合は、取得期間を短くするか、比較する銘柄を絞って再実行してください。"
    )


def ranking_build_cache_key(
    *,
    provider: str,
    symbols: list[str],
    start: date,
    end: date,
) -> str:
    return "|".join([provider, start.isoformat(), end.isoformat(), ",".join(symbols)])


def ranking_symbol_options(rows: list[dict[str, str]]) -> list[str]:
    symbols: list[str] = []
    seen: set[str] = set()
    for row in rows:
        symbol = row.get("symbol", "").strip()
        normalized = symbol.upper()
        if not symbol or normalized in seen:
            continue
        symbols.append(symbol)
        seen.add(normalized)
    return symbols


def _ranking_error_symbol_summary(symbols: list[str]) -> str:
    if len(symbols) <= 8:
        return ", ".join(symbols)
    return f"{', '.join(symbols[:8])}, ... (+{len(symbols) - 8})"


def _row_decimal_in_range(
    row: dict[str, str],
    key: str,
    min_value: Decimal | str | int,
    max_value: Decimal | str | int,
) -> bool:
    value = _decimal_filter_value(row.get(key, ""), Decimal("-999999"))
    lower = _decimal_filter_value(min_value, Decimal("-999999"))
    upper = _decimal_filter_value(max_value, Decimal("999999"))
    return lower <= value <= upper


def _decimal_filter_value(value: Decimal | str | int, default: Decimal) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return default


def _symbol_universe_row(row: dict[str, str]) -> dict[str, str]:
    symbol = row.get("symbol", "").strip()
    default_market = row.get("market") or ("jp" if symbol.upper().endswith(".T") else "us")
    default_currency = row.get("currency") or ("JPY" if default_market == "jp" else "USD")
    default_asset_type = row.get("asset_type") or "stock"
    theme = row.get("theme") or "consumer"
    dividend_category = row.get("dividend_category") or "dividend"
    tags = _symbol_universe_values(row, "tags") or {"balanced"}
    universe_row = {
        "symbol": symbol,
        "name": row.get("name", symbol),
        "market": default_market,
        "asset_type": default_asset_type,
        "currency": default_currency,
        "theme": theme,
        "dividend_category": dividend_category,
        "dividend_yield_pct": row.get("dividend_yield_pct") or "0",
        "market_cap_tier": row.get("market_cap_tier") or "mid",
        "index_family": row.get("index_family", ""),
        "expense_ratio_pct": row.get("expense_ratio_pct", ""),
        "complexity": row.get("complexity")
        or ("beginner" if default_asset_type == "etf" else "standard"),
        "tags": ",".join(sorted(tags)),
        "aliases": row.get("aliases", ""),
        "per": row.get("per", ""),
        "pbr": row.get("pbr", ""),
        "roe_pct": row.get("roe_pct", ""),
        "sector": row.get("sector", ""),
        "consensus_rating": row.get("consensus_rating", ""),
        "forecast_agreement": row.get("forecast_agreement", ""),
        "data_quality": row.get("data_quality", ""),
        "risk_band": row.get("risk_band", ""),
    }
    if universe_row["asset_type"] == "etf":
        universe_row["market"] = "us"
    return universe_row


def _symbol_universe_values(row: dict[str, str], key: str) -> set[str]:
    return {value.strip() for value in row.get(key, "").split(",") if value.strip()}


def _symbol_complexity_allowed(symbol_complexity: str, selected_complexity: str) -> bool:
    if selected_complexity == "all":
        return True
    if selected_complexity == "standard":
        return symbol_complexity in {"beginner", "standard"}
    return symbol_complexity == "beginner"
