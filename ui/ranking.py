from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from backend.core.errors import AppError
from backend.marketdata.ranking_universe_policy import (
    symbol_allowed_by_ranking_universe_policy,
)
from ui.symbol_universe import symbol_universe_csv_rows

MAX_RANKING_CONCURRENT_FETCHES = 8
MAX_RANKING_BATCH_FETCH_SYMBOLS = 10
MAX_RANKING_BUILD_CACHE_ENTRIES = 8
LIVE_MARKET_DATA_PROVIDERS = {"yahoo", "polygon"}
LIVE_RANKING_WARNING_SYMBOL_THRESHOLD = 30

RANKING_REGION_JAPAN = "japan"
RANKING_REGION_US = "us"
RANKING_REGION_OTHER_GLOBAL = "other_global"
RANKING_REGION_ALL = "all"
RANKING_REGION_LABELS = {
    RANKING_REGION_JAPAN: "国内",
    RANKING_REGION_US: "米国",
    RANKING_REGION_OTHER_GLOBAL: "その他海外",
    RANKING_REGION_ALL: "全体",
}
RANKING_MVP_REGION_LABELS = {
    RANKING_REGION_JAPAN: RANKING_REGION_LABELS[RANKING_REGION_JAPAN],
    RANKING_REGION_US: RANKING_REGION_LABELS[RANKING_REGION_US],
    RANKING_REGION_ALL: RANKING_REGION_LABELS[RANKING_REGION_ALL],
}

RANKING_PRODUCT_STOCK = "stock"
RANKING_PRODUCT_ETF = "etf"
RANKING_PRODUCT_MUTUAL_FUND = "mutual_fund"
RANKING_PRODUCT_ALL = "all"
RANKING_PRODUCT_TYPE_LABELS = {
    RANKING_PRODUCT_STOCK: "株式",
    RANKING_PRODUCT_ETF: "ETF",
    RANKING_PRODUCT_MUTUAL_FUND: "投信",
    RANKING_PRODUCT_ALL: "全体",
}
RANKING_MVP_PRODUCT_TYPE_LABELS = {
    RANKING_PRODUCT_STOCK: RANKING_PRODUCT_TYPE_LABELS[RANKING_PRODUCT_STOCK],
    RANKING_PRODUCT_ETF: RANKING_PRODUCT_TYPE_LABELS[RANKING_PRODUCT_ETF],
}

RANKING_PURPOSE_DIVIDEND = "dividend"
RANKING_PURPOSE_GROWTH = "growth"
RANKING_PURPOSE_VALUE = "value"
RANKING_PURPOSE_STABILITY = "stability"
RANKING_PURPOSE_TREND = "trend"
RANKING_PURPOSE_LABELS = {
    RANKING_PURPOSE_DIVIDEND: "配当重視",
    RANKING_PURPOSE_GROWTH: "成長重視",
    RANKING_PURPOSE_VALUE: "割安重視",
    RANKING_PURPOSE_STABILITY: "安定重視",
    RANKING_PURPOSE_TREND: "トレンド重視",
}
RANKING_INVESTMENT_STYLE_METRICS = {
    RANKING_PURPOSE_DIVIDEND: [
        "dividend_yield",
        "dividend_growth",
        "payout_ratio",
        "free_cash_flow",
        "earnings_stability",
        "volatility",
    ],
    RANKING_PURPOSE_GROWTH: [
        "revenue_growth",
        "eps_growth",
        "roe",
        "operating_margin",
        "price_momentum",
        "market_cap",
    ],
    RANKING_PURPOSE_VALUE: [
        "per",
        "pbr",
        "psr",
        "ev_ebitda",
        "dividend_yield",
        "historical_valuation_gap",
    ],
    RANKING_PURPOSE_STABILITY: [
        "market_cap",
        "beta",
        "volatility",
        "equity_ratio",
        "operating_margin",
        "earnings_stability",
    ],
    RANKING_PURPOSE_TREND: [
        "moving_average_signal",
        "rsi",
        "macd",
        "volume_change",
        "recent_return",
        "volatility",
    ],
}

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
RANKING_PURPOSE_WEIGHT_PRESETS = {
    RANKING_PURPOSE_DIVIDEND: RANKING_PRESET_BALANCED,
    RANKING_PURPOSE_GROWTH: RANKING_PRESET_FORECAST,
    RANKING_PURPOSE_VALUE: RANKING_PRESET_BALANCED,
    RANKING_PURPOSE_STABILITY: RANKING_PRESET_RISK,
    RANKING_PURPOSE_TREND: RANKING_PRESET_FORECAST,
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
    "balanced": "バランス",
    "technology": "テクノロジー",
    "telecom": "通信",
    "communication": "コミュニケーション",
    "semiconductor": "半導体",
    "financial": "金融",
    "consumer": "消費",
    "healthcare": "ヘルスケア",
    "energy": "エネルギー",
    "automotive": "自動車",
    "trading": "商社",
    "industrial": "資本財/工業",
    "materials": "素材",
    "real_estate": "不動産",
    "utilities": "公益",
    "index": "インデックス",
    "reit": "REIT",
    "commodity": "コモディティ",
    "dividend": "高配当",
}
RANKING_MARKET_CAP_LABELS = {
    "all": "指定なし",
    "mega": "超大型",
    "large": "大型",
    "mid": "中型",
    "small": "小型",
    "micro": "超小型",
}
RANKING_INDEX_FAMILY_LABELS = {
    "all": "指定なし",
    "sp500": "S&P 500",
    "nasdaq100": "NASDAQ 100",
    "total_us": "全米",
    "small_us": "米国小型",
    "acwi": "全世界",
    "msci_world": "先進国",
    "topix": "TOPIX",
    "nikkei225": "日経225",
    "jpx_nikkei400": "JPX日経400",
    "dow_jones": "Dow Jones",
    "emerging": "新興国",
    "china": "中国株",
    "india": "インド株",
    "singapore_equity": "シンガポール株",
    "japan_equity": "日本株",
    "dividend": "高配当/配当",
    "reit": "REIT",
    "bond": "債券",
    "commodity": "コモディティ",
    "currency": "通貨",
    "single_stock": "個別株連動",
    "style_factor": "スタイル/ファクター",
    "active": "アクティブ",
    "sector": "セクター/テーマ",
}
RANKING_RISK_BAND_LABELS = {
    "all": "指定なし",
    "LOW": "低め",
    "MEDIUM": "中くらい",
    "HIGH": "高め",
}
RANKING_MANAGEMENT_STYLE_LABELS = {
    "all": "指定なし",
    "index": "インデックス",
    "active": "アクティブ",
}
RANKING_NISA_ELIGIBILITY_LABELS = {
    "all": "指定なし",
    "eligible": "NISA対象",
    "growth": "成長投資枠",
    "tsumitate": "つみたて投資枠",
    "both": "両方",
}
RANKING_INSTALLMENT_LABELS = {
    "all": "指定なし",
    "true": "積立可能",
    "false": "積立不可",
}
RANKING_DETAIL_FILTER_LABELS = {
    "industry_or_sector": "業種/テーマ",
    "market_cap": "時価総額",
    "dividend_yield": "配当利回り",
    "per": "PER",
    "pbr": "PBR",
    "roe": "ROE",
    "nisa_eligibility": "NISA",
    "benchmark_index": "連動指数",
    "expense_ratio": "信託報酬/経費率",
    "complexity": "複雑さ",
}
RANKING_DETAIL_FILTERS_BY_CATEGORY = {
    (RANKING_REGION_JAPAN, RANKING_PRODUCT_STOCK): [
        "industry_or_sector",
        "market_cap",
        "dividend_yield",
        "per",
        "pbr",
        "roe",
        "nisa_eligibility",
    ],
    (RANKING_REGION_US, RANKING_PRODUCT_STOCK): [
        "industry_or_sector",
        "market_cap",
        "dividend_yield",
        "per",
        "roe",
        "nisa_eligibility",
    ],
    (RANKING_REGION_ALL, RANKING_PRODUCT_STOCK): [
        "industry_or_sector",
        "market_cap",
        "dividend_yield",
        "per",
        "roe",
        "nisa_eligibility",
    ],
    (RANKING_REGION_ALL, RANKING_PRODUCT_ETF): [
        "nisa_eligibility",
        "benchmark_index",
        "expense_ratio",
        "dividend_yield",
        "complexity",
    ],
}
RANKING_FILTER_DEFAULTS: dict[str, str] = {
    "market_data_ranking_region": RANKING_REGION_JAPAN,
    "market_data_ranking_product_type": RANKING_PRODUCT_STOCK,
    "market_data_ranking_purpose": RANKING_PURPOSE_DIVIDEND,
    "market_data_ranking_market": "all",
    "market_data_ranking_asset_type": "all",
    "market_data_ranking_currency": "all",
    "market_data_ranking_dividend": "all",
    "market_data_ranking_min_dividend": "0.0",
    "market_data_ranking_market_cap": "all",
    "market_data_ranking_index_family": "all",
    "market_data_ranking_max_expense": "1.00",
    "market_data_ranking_complexity": "standard",
    "market_data_ranking_nisa": "all",
    "market_data_ranking_risk_band": "all",
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


def ranking_region_label(region: str) -> str:
    return RANKING_REGION_LABELS.get(region, region)


def ranking_product_type_label(product_type: str) -> str:
    return RANKING_PRODUCT_TYPE_LABELS.get(product_type, product_type)


def ranking_purpose_label(purpose: str) -> str:
    return RANKING_PURPOSE_LABELS.get(purpose, purpose)


def ranking_weight_preset_for_purpose(purpose: str) -> str:
    return RANKING_PURPOSE_WEIGHT_PRESETS.get(purpose, RANKING_PRESET_BALANCED)


def ranking_detail_filters_for_category(region: str, product_type: str) -> list[str]:
    if product_type == RANKING_PRODUCT_ETF:
        return RANKING_DETAIL_FILTERS_BY_CATEGORY[(RANKING_REGION_ALL, RANKING_PRODUCT_ETF)]
    if product_type == RANKING_PRODUCT_MUTUAL_FUND:
        return []
    if product_type == RANKING_PRODUCT_STOCK:
        if region == RANKING_REGION_JAPAN:
            return RANKING_DETAIL_FILTERS_BY_CATEGORY[(RANKING_REGION_JAPAN, RANKING_PRODUCT_STOCK)]
        if region == RANKING_REGION_US:
            return RANKING_DETAIL_FILTERS_BY_CATEGORY[(RANKING_REGION_US, RANKING_PRODUCT_STOCK)]
        return RANKING_DETAIL_FILTERS_BY_CATEGORY[(RANKING_REGION_ALL, RANKING_PRODUCT_STOCK)]
    return [
        "industry_or_sector",
        "market_cap",
        "dividend_yield",
        "per",
        "pbr",
        "roe",
        "benchmark_index",
        "expense_ratio",
        "complexity",
        "nisa_eligibility",
    ]


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
    region: str = RANKING_REGION_ALL,
    product_type: str = RANKING_PRODUCT_ALL,
    ranking_purpose: str = RANKING_PURPOSE_DIVIDEND,
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
    management_style: str = "all",
    nisa_eligibility: str = "all",
    installment_available: str = "all",
    risk_band: str = "all",
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
    detail_filters = _active_ranking_detail_filters(region, product_type)
    filtered: list[dict[str, str]] = []
    _ = ranking_purpose
    for row in rows:
        tags = _symbol_universe_values(row, "tags")
        if not symbol_allowed_by_ranking_universe_policy(row):
            continue
        if not _symbol_matches_region(row, region):
            continue
        if not _symbol_matches_product_type(row, product_type):
            continue
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
        if (
            "dividend_yield" in detail_filters
            and dividend_category != "all"
            and row.get("dividend_category") != dividend_category
        ):
            continue
        if (
            "market_cap" in detail_filters
            and market_cap_tier != "all"
            and row.get("market_cap_tier") != market_cap_tier
        ):
            continue
        if (
            "risk_band" in detail_filters
            and risk_band != "all"
            and row.get("risk_band") != risk_band
        ):
            continue
        if (
            "benchmark_index" in detail_filters
            and index_family != "all"
            and row.get("index_family") != index_family
        ):
            continue
        if "expense_ratio" in detail_filters:
            cost_ratio = _symbol_cost_ratio(row)
            if cost_ratio and _decimal_filter_value(cost_ratio, Decimal("99")) > max_expense:
                continue
        if "complexity" in detail_filters and not _symbol_complexity_allowed(
            row.get("complexity", "standard"),
            complexity,
        ):
            continue
        if (
            "management_style" in detail_filters
            and management_style != "all"
            and row.get("management_style") != management_style
        ):
            continue
        if "nisa_eligibility" in detail_filters and not _symbol_matches_nisa_eligibility(
            row, nisa_eligibility
        ):
            continue
        if (
            "installment_available" in detail_filters
            and installment_available != "all"
            and row.get("installment_available") != installment_available
        ):
            continue
        if (
            "industry_or_sector" in detail_filters
            and theme != "all"
            and theme not in tags
            and row.get("theme") != theme
            and row.get("sector") != theme
        ):
            continue
        if (
            "per" in detail_filters
            and per_enabled
            and not _row_decimal_in_range(row, "per", per_min, per_max)
        ):
            continue
        if (
            "pbr" in detail_filters
            and pbr_enabled
            and not _row_decimal_in_range(row, "pbr", pbr_min, pbr_max)
        ):
            continue
        if (
            "dividend_yield" in detail_filters
            and dividend_yield_enabled
            and not _row_decimal_in_range(
                row,
                "dividend_yield_pct",
                min_dividend,
                dividend_yield_max_pct,
            )
        ):
            continue
        if (
            "roe" in detail_filters
            and roe_enabled
            and not _row_decimal_in_range(row, "roe_pct", roe_min_pct, roe_max_pct)
        ):
            continue
        if (
            "consensus" in detail_filters
            and consensus_enabled
            and not _row_decimal_in_range(
                row,
                "consensus_rating",
                consensus_min,
                consensus_max,
            )
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
    region: str = RANKING_REGION_ALL,
    product_type: str = RANKING_PRODUCT_ALL,
    ranking_purpose: str = RANKING_PURPOSE_DIVIDEND,
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
    management_style: str = "all",
    nisa_eligibility: str = "all",
    installment_available: str = "all",
    risk_band: str = "all",
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
    detail_filters = _active_ranking_detail_filters(region, product_type)
    if "dividend_yield" not in detail_filters:
        dividend_category = "all"
        min_dividend_yield_pct = "0.0"
        dividend_yield_enabled = False
        dividend_yield_max_pct = "10.0"
    if "market_cap" not in detail_filters:
        market_cap_tier = "all"
    if "benchmark_index" not in detail_filters:
        index_family = "all"
    if "expense_ratio" not in detail_filters:
        max_expense_ratio_pct = "1.00"
    if "complexity" not in detail_filters:
        complexity = "standard"
    if "management_style" not in detail_filters:
        management_style = "all"
    if "nisa_eligibility" not in detail_filters:
        nisa_eligibility = "all"
    if "installment_available" not in detail_filters:
        installment_available = "all"
    if "risk_band" not in detail_filters:
        risk_band = "all"
    if "industry_or_sector" not in detail_filters:
        theme = "all"
    if "per" not in detail_filters:
        per_enabled = False
        per_min = "2.0"
        per_max = "20.0"
    if "pbr" not in detail_filters:
        pbr_enabled = False
        pbr_min = "0.5"
        pbr_max = "2.0"
    if "roe" not in detail_filters:
        roe_enabled = False
        roe_min_pct = "8.0"
        roe_max_pct = "30.0"
    if "consensus" not in detail_filters:
        consensus_enabled = False
        consensus_min = "2.5"
        consensus_max = "5.0"
    return "|".join(
        [
            region,
            product_type,
            ranking_purpose,
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
            management_style,
            nisa_eligibility,
            installment_available,
            risk_band,
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


def ranking_no_bars_error_row(
    *,
    provider: str,
    symbol: str,
    display_start: date,
    display_end: date,
    fetch_start: datetime,
    fetch_end: datetime,
) -> dict[str, str]:
    details = {
        "provider": provider,
        "symbol": symbol,
        "request": {
            "operation": "ranking_fetch_ohlcv",
            "symbol": symbol,
            "interval": "1d",
            "display_start": display_start.isoformat(),
            "display_end": display_end.isoformat(),
            "fetch_start": fetch_start.isoformat(),
            "fetch_end": fetch_end.isoformat(),
        },
        "reason": "no_ohlcv_rows",
    }
    return {
        "symbol": symbol,
        "code": "RANKING-NO-BARS",
        "message": "価格データを取得できなかったため、ランキングから除外しました。",
        "details": json.dumps(details, ensure_ascii=False, sort_keys=True),
    }


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


def ranking_deep_dive_default_symbol(
    rows: list[dict[str, str]],
    *,
    current_symbol: str | None,
    source_key: str,
    current_source_key: str | None,
) -> str | None:
    options = ranking_symbol_options(rows)
    if not options:
        return None
    if current_source_key != source_key:
        return options[0]
    if current_symbol not in options:
        return options[0]
    return current_symbol


def rank_investment_score_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    ranked = sorted(
        rows,
        key=lambda row: _optional_decimal_from_text(row.get("total_score", "")) or Decimal("-1"),
        reverse=True,
    )
    return [
        {
            **row,
            "rank": str(index),
        }
        for index, row in enumerate(ranked, start=1)
    ]


def apply_ranking_weight_preset(
    rows: list[dict[str, str]],
    preset: str,
) -> list[dict[str, str]]:
    weights = RANKING_WEIGHT_PRESETS[preset]
    preset_label = ranking_weight_preset_label(preset)
    reweighted_rows: list[dict[str, str]] = []
    for row in rows:
        total = Decimal("0")
        for field, weight in weights.items():
            component_score = _optional_decimal_from_text(row.get(field, "")) or Decimal("0")
            total += component_score * weight
        warnings = row.get("warnings", "")
        reweighted_rows.append(
            {
                **row,
                "total_score": _format_score(total),
                "score_band": _score_band_for_total(total, warnings),
                "note": f"{preset_label}で並べ替えています。売買推奨ではなく、深掘り候補の整理です。",
            }
        )
    return rank_investment_score_rows(reweighted_rows)


def _ranking_error_symbol_summary(symbols: list[str]) -> str:
    if len(symbols) <= 8:
        return ", ".join(symbols)
    return f"{', '.join(symbols[:8])}, ... (+{len(symbols) - 8})"


def _active_ranking_detail_filters(region: str, product_type: str) -> set[str]:
    return set(ranking_detail_filters_for_category(region, product_type))


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
        "broker": row.get("broker", ""),
        "tradability": row.get("tradability", ""),
        "nisa_category": row.get("nisa_category", ""),
        "investment_style": row.get("investment_style", ""),
        "is_sbi_supported": row.get("is_sbi_supported", ""),
        "is_active": row.get("is_active", ""),
        "is_leveraged": row.get("is_leveraged", ""),
        "is_inverse": row.get("is_inverse", ""),
        "theme": theme,
        "dividend_category": dividend_category,
        "dividend_yield_pct": row.get("dividend_yield_pct") or "0",
        "market_cap_tier": row.get("market_cap_tier") or "mid",
        "index_family": row.get("index_family", ""),
        "yahoo_symbol": row.get("yahoo_symbol", ""),
        "expense_ratio_pct": row.get("expense_ratio_pct", ""),
        "trust_fee_pct": row.get("trust_fee_pct", ""),
        "aum": row.get("aum", ""),
        "nisa_tsumitate_eligible": row.get("nisa_tsumitate_eligible", ""),
        "nisa_growth_eligible": row.get("nisa_growth_eligible", ""),
        "installment_available": row.get("installment_available", ""),
        "management_style": row.get("management_style", ""),
        "distribution_policy": row.get("distribution_policy", ""),
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
    return universe_row


def _symbol_universe_values(row: dict[str, str], key: str) -> set[str]:
    return {value.strip() for value in row.get(key, "").split(",") if value.strip()}


def _symbol_matches_region(row: dict[str, str], region: str) -> bool:
    market = row.get("market", "")
    if region == RANKING_REGION_ALL:
        return True
    if region == RANKING_REGION_JAPAN:
        return market == "jp"
    if region == RANKING_REGION_US:
        return market == "us"
    if region == RANKING_REGION_OTHER_GLOBAL:
        return market not in {"jp", "us"}
    return True


def _symbol_matches_product_type(row: dict[str, str], product_type: str) -> bool:
    asset_type = row.get("asset_type", "")
    if product_type == RANKING_PRODUCT_ALL:
        return True
    if product_type == RANKING_PRODUCT_STOCK:
        return asset_type == "stock"
    if product_type == RANKING_PRODUCT_ETF:
        return asset_type == "etf"
    if product_type == RANKING_PRODUCT_MUTUAL_FUND:
        return False
    return True


def _symbol_complexity_allowed(symbol_complexity: str, selected_complexity: str) -> bool:
    if selected_complexity == "all":
        return True
    if selected_complexity == "standard":
        return symbol_complexity in {"beginner", "standard"}
    return symbol_complexity == "beginner"


def _symbol_cost_ratio(row: dict[str, str]) -> str:
    asset_type = row.get("asset_type", "")
    if asset_type in {"mutual_fund", "fund", "investment_trust"}:
        return row.get("trust_fee_pct", "") or row.get("expense_ratio_pct", "")
    if asset_type == "etf":
        return row.get("expense_ratio_pct", "")
    return ""


def _symbol_matches_nisa_eligibility(row: dict[str, str], nisa_eligibility: str) -> bool:
    if nisa_eligibility == "all":
        return True
    nisa_category = row.get("nisa_category", "")
    growth = row.get("nisa_growth_eligible", "") == "true" or nisa_category in {"both", "growth"}
    tsumitate = row.get("nisa_tsumitate_eligible", "") == "true" or nisa_category in {
        "both",
        "tsumitate",
    }
    if nisa_eligibility == "eligible":
        return growth or tsumitate
    if nisa_eligibility == "growth":
        return growth
    if nisa_eligibility == "tsumitate":
        return tsumitate
    if nisa_eligibility == "both":
        return growth and tsumitate
    return True


def _score_band_for_total(total_score: Decimal, warnings: str) -> str:
    warning_items = {item.strip() for item in warnings.split(",") if item.strip()}
    if "data_quality:block" in warning_items:
        return "REVIEW"
    if total_score >= Decimal("75") and not warning_items:
        return "STRONG"
    if warning_items and total_score < Decimal("65"):
        return "CAUTION"
    if total_score >= Decimal("55"):
        return "BALANCED"
    if total_score >= Decimal("40"):
        return "CAUTION"
    return "REVIEW"


def _format_score(value: Decimal) -> str:
    rounded = value.quantize(Decimal("0.01"))
    return format(rounded.normalize(), "f")


def _optional_decimal_from_text(value: str) -> Decimal | None:
    if value == "":
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None
