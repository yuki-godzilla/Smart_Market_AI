from __future__ import annotations

import json
from collections.abc import Collection
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from backend.core.errors import AppError
from backend.marketdata.ranking_universe_policy import (
    symbol_allowed_by_ranking_universe_policy,
)
from backend.scoring.reversal import calculate_reversal_expectation
from ui.content import ranking_texts
from ui.symbol_universe import symbol_universe_csv_rows, symbol_universe_search_rows

RANKING_ASSET_TYPE_LABELS = ranking_texts.RANKING_ASSET_TYPE_LABELS
RANKING_BETA_RISK_LABELS = ranking_texts.RANKING_BETA_RISK_LABELS
RANKING_COMPLEXITY_LABELS = ranking_texts.RANKING_COMPLEXITY_LABELS
RANKING_CRITERIA_GUIDE_ROWS = ranking_texts.RANKING_CRITERIA_GUIDE_ROWS
RANKING_CURRENCY_LABELS = ranking_texts.RANKING_CURRENCY_LABELS
RANKING_DETAIL_FILTER_LABELS = ranking_texts.RANKING_DETAIL_FILTER_LABELS
RANKING_DIVIDEND_LABELS = ranking_texts.RANKING_DIVIDEND_LABELS
RANKING_FETCH_LIMIT_LABELS = ranking_texts.RANKING_FETCH_LIMIT_LABELS
RANKING_INDEX_FAMILY_LABELS = ranking_texts.RANKING_INDEX_FAMILY_LABELS
RANKING_INSTALLMENT_LABELS = ranking_texts.RANKING_INSTALLMENT_LABELS
RANKING_MANAGEMENT_STYLE_LABELS = ranking_texts.RANKING_MANAGEMENT_STYLE_LABELS
RANKING_MARKET_CAP_LABELS = ranking_texts.RANKING_MARKET_CAP_LABELS
RANKING_MARKET_LABELS = ranking_texts.RANKING_MARKET_LABELS
RANKING_MVP_PRODUCT_TYPE_LABELS = ranking_texts.RANKING_MVP_PRODUCT_TYPE_LABELS
RANKING_MVP_REGION_LABELS = ranking_texts.RANKING_MVP_REGION_LABELS
RANKING_NISA_ELIGIBILITY_LABELS = ranking_texts.RANKING_NISA_ELIGIBILITY_LABELS
RANKING_OFFICIAL_SECTOR_LABELS = ranking_texts.RANKING_OFFICIAL_SECTOR_LABELS
RANKING_PERIOD_LABELS = ranking_texts.RANKING_PERIOD_LABELS
RANKING_POLICY_DESCRIPTIONS = ranking_texts.RANKING_POLICY_DESCRIPTIONS
RANKING_PRODUCT_TYPE_LABELS = ranking_texts.RANKING_PRODUCT_TYPE_LABELS
RANKING_PURPOSE_LABELS = ranking_texts.RANKING_PURPOSE_LABELS
RANKING_REGION_LABELS = ranking_texts.RANKING_REGION_LABELS
RANKING_RISK_BAND_LABELS = ranking_texts.RANKING_RISK_BAND_LABELS
RANKING_INVESTMENT_THEME_LABELS = ranking_texts.RANKING_INVESTMENT_THEME_LABELS
RANKING_SCORE_FIELD_LABELS = ranking_texts.RANKING_SCORE_FIELD_LABELS
RANKING_THEME_LABELS = ranking_texts.RANKING_THEME_LABELS
RANKING_WEIGHT_PRESET_LABELS = ranking_texts.RANKING_WEIGHT_PRESET_LABELS

MAX_RANKING_CONCURRENT_FETCHES = 6
MAX_RANKING_BATCH_FETCH_SYMBOLS = 25
MAX_RANKING_BUILD_CACHE_ENTRIES = 8
LIVE_MARKET_DATA_PROVIDERS = {"yahoo", "polygon"}
LIVE_RANKING_WARNING_SYMBOL_THRESHOLD = 30
RANKING_MAX_REASONABLE_DIVIDEND_YIELD_PCT = Decimal("20")
RANKING_MAX_REASONABLE_PER = Decimal("200")
RANKING_MAX_REASONABLE_PBR = Decimal("50")
RANKING_MIN_REASONABLE_ROE_PCT = Decimal("-100")
RANKING_MAX_REASONABLE_ROE_PCT = Decimal("100")
RANKING_FUNDAMENTAL_METRIC_FIELDS = {"dividend_yield_pct", "per", "pbr", "roe_pct"}
RANKING_STOCK_ONLY_DETAIL_FILTERS = {"market_cap", "per", "pbr", "roe"}
RANKING_FUND_COST_DETAIL_FILTERS = {"benchmark_index", "expense_ratio", "complexity"}
RANKING_CROSS_ASSET_DETAIL_FILTERS = {
    "investment_theme",
    "nisa_eligibility",
    "dividend_yield",
}

RANKING_REGION_JAPAN = "japan"
RANKING_REGION_US = "us"
RANKING_REGION_CHINA_HK = "china_hk"
RANKING_REGION_KOREA = "korea"
RANKING_REGION_ASEAN = "asean"
RANKING_REGION_OTHER_GLOBAL = "other_global"
RANKING_REGION_ALL = "all"

RANKING_ASEAN_MARKETS = {"vietnam", "indonesia", "singapore", "thailand", "malaysia"}
RANKING_FOREIGN_NON_US_MARKETS = {
    "hong_kong",
    "china",
    "korea",
    "vietnam",
    "indonesia",
    "singapore",
    "thailand",
    "malaysia",
    "russia",
    "other_global",
}

RANKING_PRODUCT_STOCK = "stock"
RANKING_PRODUCT_ETF = "etf"
RANKING_PRODUCT_MUTUAL_FUND = "mutual_fund"
RANKING_PRODUCT_ALL = "all"

RANKING_PURPOSE_DIVIDEND = "dividend"
RANKING_PURPOSE_GROWTH = "growth"
RANKING_PURPOSE_VALUE = "value"
RANKING_PURPOSE_STABILITY = "stability"
RANKING_PURPOSE_TREND = "trend"
RANKING_PURPOSE_UPSIDE_SIGNAL = "upside_signal"
RANKING_PURPOSE_DOWNSIDE_SIGNAL = "downside_signal"
RANKING_PURPOSE_REVERSAL_EXPECTATION = "reversal_expectation"
RANKING_PURPOSE_SORT_TOTAL_SCORE = "sort_total_score"
RANKING_PURPOSE_SORT_DIVIDEND_YIELD = "sort_dividend_yield"
RANKING_PURPOSE_SORT_PER = "sort_per"
RANKING_PURPOSE_SORT_PBR = "sort_pbr"
RANKING_PURPOSE_SORT_ROE = "sort_roe"
RANKING_PURPOSE_SORT_MARKET_CAP = "sort_market_cap"
RANKING_PURPOSE_SORT_VOLUME = "sort_volume"
RANKING_PURPOSE_SORT_VOLATILITY = "sort_volatility"
RANKING_PURPOSE_SORT_RISK = "sort_risk"
RANKING_PURPOSE_SORT_DATA_QUALITY = "sort_data_quality"
RANKING_PURPOSE_MULTI_FACTOR = "multi_factor"
RANKING_PURPOSE_QUALITY_GROWTH = "quality_growth"
RANKING_PURPOSE_QUALITY_VALUE = "quality_value"
RANKING_PURPOSE_SUSTAINABLE_INCOME = "sustainable_income"
RANKING_PURPOSE_MIN_VOLATILITY = "min_volatility"
RANKING_PURPOSE_MOMENTUM = "momentum"
RANKING_PURPOSE_RISK_ADJUSTED = "risk_adjusted"
RANKING_PURPOSE_SMALL_GROWTH = "small_growth"
RANKING_PURPOSE_NISA_LONG_TERM = "nisa_long_term"
RANKING_PURPOSE_DATA_CONFIDENCE = "data_confidence"
RANKING_PURPOSE_ETF_CORE_COST = "etf_core_cost"
RANKING_PURPOSE_ETF_INCOME = "etf_income"
RANKING_PURPOSE_SIMPLE_SORT_ORDER = (
    RANKING_PURPOSE_SORT_TOTAL_SCORE,
    RANKING_PURPOSE_SORT_DIVIDEND_YIELD,
    RANKING_PURPOSE_SORT_PER,
    RANKING_PURPOSE_SORT_PBR,
    RANKING_PURPOSE_SORT_ROE,
    RANKING_PURPOSE_SORT_MARKET_CAP,
    RANKING_PURPOSE_SORT_VOLUME,
    RANKING_PURPOSE_SORT_VOLATILITY,
    RANKING_PURPOSE_SORT_RISK,
    RANKING_PURPOSE_SORT_DATA_QUALITY,
)
RANKING_SORT_DISPLAY_ORDER = (
    RANKING_PURPOSE_SORT_TOTAL_SCORE,
    RANKING_PURPOSE_SORT_DIVIDEND_YIELD,
    RANKING_PURPOSE_SORT_PER,
    RANKING_PURPOSE_SORT_PBR,
    RANKING_PURPOSE_SORT_ROE,
)
RANKING_POLICY_DISPLAY_ORDER = (
    RANKING_PURPOSE_MULTI_FACTOR,
    RANKING_PURPOSE_UPSIDE_SIGNAL,
    RANKING_PURPOSE_REVERSAL_EXPECTATION,
    RANKING_PURPOSE_DOWNSIDE_SIGNAL,
    RANKING_PURPOSE_MOMENTUM,
    RANKING_PURPOSE_QUALITY_GROWTH,
    RANKING_PURPOSE_QUALITY_VALUE,
    RANKING_PURPOSE_SUSTAINABLE_INCOME,
    RANKING_PURPOSE_MIN_VOLATILITY,
    RANKING_PURPOSE_RISK_ADJUSTED,
    RANKING_PURPOSE_SMALL_GROWTH,
    RANKING_PURPOSE_NISA_LONG_TERM,
    RANKING_PURPOSE_DATA_CONFIDENCE,
    RANKING_PURPOSE_ETF_CORE_COST,
    RANKING_PURPOSE_ETF_INCOME,
)
RANKING_POLICY_LABELS = {
    RANKING_PURPOSE_MULTI_FACTOR: "AI総合",
}
RANKING_POLICY_PURPOSE_ALIASES = {
    RANKING_PURPOSE_DIVIDEND: RANKING_PURPOSE_SUSTAINABLE_INCOME,
    RANKING_PURPOSE_GROWTH: RANKING_PURPOSE_QUALITY_GROWTH,
    RANKING_PURPOSE_VALUE: RANKING_PURPOSE_QUALITY_VALUE,
    RANKING_PURPOSE_STABILITY: RANKING_PURPOSE_MIN_VOLATILITY,
    RANKING_PURPOSE_TREND: RANKING_PURPOSE_MOMENTUM,
}
RANKING_PURPOSE_DISPLAY_ORDER = (
    RANKING_PURPOSE_MULTI_FACTOR,
    RANKING_PURPOSE_UPSIDE_SIGNAL,
    RANKING_PURPOSE_REVERSAL_EXPECTATION,
    RANKING_PURPOSE_MOMENTUM,
    RANKING_PURPOSE_QUALITY_GROWTH,
    RANKING_PURPOSE_QUALITY_VALUE,
    RANKING_PURPOSE_SUSTAINABLE_INCOME,
    RANKING_PURPOSE_MIN_VOLATILITY,
    RANKING_PURPOSE_RISK_ADJUSTED,
    RANKING_PURPOSE_SMALL_GROWTH,
    RANKING_PURPOSE_NISA_LONG_TERM,
    RANKING_PURPOSE_DATA_CONFIDENCE,
    RANKING_PURPOSE_ETF_CORE_COST,
    RANKING_PURPOSE_ETF_INCOME,
    RANKING_PURPOSE_GROWTH,
    RANKING_PURPOSE_TREND,
    RANKING_PURPOSE_VALUE,
    RANKING_PURPOSE_DIVIDEND,
    RANKING_PURPOSE_STABILITY,
)
RANKING_PURPOSE_ETF_DISPLAY_ORDER = (
    RANKING_PURPOSE_MULTI_FACTOR,
    RANKING_PURPOSE_ETF_CORE_COST,
    RANKING_PURPOSE_ETF_INCOME,
    RANKING_PURPOSE_DATA_CONFIDENCE,
    RANKING_PURPOSE_MIN_VOLATILITY,
    RANKING_PURPOSE_RISK_ADJUSTED,
    RANKING_PURPOSE_NISA_LONG_TERM,
    RANKING_PURPOSE_UPSIDE_SIGNAL,
    RANKING_PURPOSE_MOMENTUM,
    RANKING_PURPOSE_QUALITY_GROWTH,
    RANKING_PURPOSE_SUSTAINABLE_INCOME,
    RANKING_PURPOSE_QUALITY_VALUE,
    RANKING_PURPOSE_SMALL_GROWTH,
    RANKING_PURPOSE_GROWTH,
    RANKING_PURPOSE_TREND,
    RANKING_PURPOSE_VALUE,
    RANKING_PURPOSE_DIVIDEND,
    RANKING_PURPOSE_STABILITY,
)
RANKING_INVESTMENT_STYLE_METRICS = {
    RANKING_PURPOSE_MULTI_FACTOR: [
        "screening_score",
        "direction_signal",
        "downside_warning",
        "advanced_forecast",
        "data_quality",
        "risk_signal",
        "database_fit",
        "metadata_confidence",
    ],
    RANKING_PURPOSE_QUALITY_GROWTH: [
        "roe",
        "direction_signal",
        "screening_score",
        "data_quality",
        "per_guardrail",
        "market_cap",
    ],
    RANKING_PURPOSE_QUALITY_VALUE: [
        "per",
        "pbr",
        "roe",
        "data_quality",
        "risk_signal",
        "metadata_confidence",
    ],
    RANKING_PURPOSE_SUSTAINABLE_INCOME: [
        "dividend_yield",
        "dividend_category",
        "risk_band",
        "pbr",
        "data_quality",
        "metadata_confidence",
    ],
    RANKING_PURPOSE_MIN_VOLATILITY: [
        "risk_band",
        "risk_signal",
        "volatility",
        "drawdown",
        "market_cap",
        "data_quality",
    ],
    RANKING_PURPOSE_MOMENTUM: [
        "recent_return",
        "price_momentum",
        "direction_signal",
        "upside_signal",
        "risk_signal",
        "data_quality",
        "volume_change",
    ],
    RANKING_PURPOSE_RISK_ADJUSTED: [
        "return_per_risk",
        "risk_signal",
        "drawdown",
        "direction_signal",
        "data_quality",
        "database_fit",
    ],
    RANKING_PURPOSE_SMALL_GROWTH: [
        "market_cap",
        "roe",
        "screening_score",
        "direction_signal",
        "risk_signal",
        "metadata_confidence",
    ],
    RANKING_PURPOSE_NISA_LONG_TERM: [
        "nisa_eligibility",
        "investment_style",
        "risk_band",
        "roe",
        "data_quality",
        "valuation_guardrail",
    ],
    RANKING_PURPOSE_DATA_CONFIDENCE: [
        "metadata_source",
        "metadata_as_of",
        "data_quality",
        "available_fields",
        "provider_completeness",
        "missing_warnings",
    ],
    RANKING_PURPOSE_ETF_CORE_COST: [
        "expense_ratio",
        "benchmark_index",
        "complexity",
        "nisa_eligibility",
        "data_quality",
        "metadata_confidence",
    ],
    RANKING_PURPOSE_ETF_INCOME: [
        "dividend_yield",
        "expense_ratio",
        "benchmark_index",
        "currency",
        "complexity",
        "data_quality",
    ],
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
        "direction_signal",
        "volume_change",
        "recent_return",
        "volatility",
    ],
    RANKING_PURPOSE_UPSIDE_SIGNAL: [
        "direction_signal",
        "upside_signal",
        "downside_warning",
        "screening_score",
        "risk_signal",
        "data_quality",
    ],
}

RANKING_PRESET_BALANCED = "balanced"
RANKING_PRESET_FORECAST = "forecast"
RANKING_PRESET_QUALITY = "quality"
RANKING_PRESET_RISK = "risk"
RANKING_PRESET_INCOME = "income"
RANKING_PRESET_GROWTH = "growth_profile"
RANKING_PRESET_VALUE = "value_profile"
RANKING_PRESET_STABILITY = "stability_profile"
RANKING_PRESET_TREND = "trend_profile"
RANKING_PRESET_UPSIDE_SIGNAL = "upside_signal_profile"
RANKING_PRESET_DOWNSIDE_SIGNAL = "downside_signal_profile"
RANKING_PRESET_REVERSAL_EXPECTATION = "reversal_expectation_profile"
RANKING_PRESET_MULTI_FACTOR = "multi_factor_profile"
RANKING_PRESET_QUALITY_GROWTH = "quality_growth_profile"
RANKING_PRESET_QUALITY_VALUE = "quality_value_profile"
RANKING_PRESET_SUSTAINABLE_INCOME = "sustainable_income_profile"
RANKING_PRESET_MIN_VOLATILITY = "min_volatility_profile"
RANKING_PRESET_MOMENTUM = "momentum_profile"
RANKING_PRESET_RISK_ADJUSTED = "risk_adjusted_profile"
RANKING_PRESET_SMALL_GROWTH = "small_growth_profile"
RANKING_PRESET_NISA_LONG_TERM = "nisa_long_term_profile"
RANKING_PRESET_DATA_CONFIDENCE = "data_confidence_profile"
RANKING_PRESET_ETF_CORE_COST = "etf_core_cost_profile"
RANKING_PRESET_ETF_INCOME = "etf_income_profile"
RANKING_PRESET_SORT_TOTAL_SCORE = "sort_total_score"
RANKING_PRESET_SORT_DIVIDEND_YIELD = "sort_dividend_yield"
RANKING_PRESET_SORT_PER = "sort_per"
RANKING_PRESET_SORT_PBR = "sort_pbr"
RANKING_PRESET_SORT_ROE = "sort_roe"
RANKING_PRESET_SORT_MARKET_CAP = "sort_market_cap"
RANKING_PRESET_SORT_VOLUME = "sort_volume"
RANKING_PRESET_SORT_VOLATILITY = "sort_volatility"
RANKING_PRESET_SORT_RISK = "sort_risk"
RANKING_PRESET_SORT_DATA_QUALITY = "sort_data_quality"
RANKING_FETCH_LIMIT_PRESET = RANKING_PRESET_MULTI_FACTOR
RANKING_METRIC_SORT_PRESETS: dict[str, tuple[str, str]] = {
    RANKING_PRESET_REVERSAL_EXPECTATION: ("reversal_expectation_score", "desc"),
    RANKING_PRESET_DOWNSIDE_SIGNAL: ("downside_signal_score", "desc"),
    RANKING_PRESET_SORT_TOTAL_SCORE: ("total_score", "desc"),
    RANKING_PRESET_SORT_DIVIDEND_YIELD: ("dividend_yield_pct", "desc"),
    RANKING_PRESET_SORT_PER: ("per", "asc"),
    RANKING_PRESET_SORT_PBR: ("pbr", "asc"),
    RANKING_PRESET_SORT_ROE: ("roe_pct", "desc"),
    RANKING_PRESET_SORT_MARKET_CAP: ("market_cap", "desc"),
    RANKING_PRESET_SORT_VOLUME: ("volume", "desc"),
    RANKING_PRESET_SORT_VOLATILITY: ("volatility", "asc"),
    # risk_signal_score is a "risk confirmation" score: higher means easier to confirm.
    RANKING_PRESET_SORT_RISK: ("risk_signal_score", "desc"),
    RANKING_PRESET_SORT_DATA_QUALITY: ("data_quality_score", "desc"),
}
RANKING_WEIGHT_PRESETS: dict[str, dict[str, Decimal]] = {
    RANKING_PRESET_BALANCED: {
        "screening_score": Decimal("0.30"),
        "upside_signal_score": Decimal("0.14"),
        "downside_signal_score": Decimal("0.06"),
        "data_quality_score": Decimal("0.15"),
        "risk_signal_score": Decimal("0.15"),
        "database_fit_score": Decimal("0.10"),
        "metadata_confidence_score": Decimal("0.10"),
    },
    RANKING_PRESET_FORECAST: {
        "upside_signal_score": Decimal("0.25"),
        "downside_signal_score": Decimal("0.10"),
        "screening_score": Decimal("0.25"),
        "data_quality_score": Decimal("0.15"),
        "risk_signal_score": Decimal("0.10"),
        "database_fit_score": Decimal("0.05"),
        "metadata_confidence_score": Decimal("0.10"),
    },
    RANKING_PRESET_UPSIDE_SIGNAL: {
        "upside_signal_score": Decimal("0.25"),
        "downside_signal_score": Decimal("0.10"),
        "screening_score": Decimal("0.25"),
        "risk_signal_score": Decimal("0.10"),
        "data_quality_score": Decimal("0.15"),
        "database_fit_score": Decimal("0.05"),
        "metadata_confidence_score": Decimal("0.10"),
    },
    RANKING_PRESET_QUALITY: {
        "screening_score": Decimal("0.25"),
        "upside_signal_score": Decimal("0.07"),
        "downside_signal_score": Decimal("0.03"),
        "data_quality_score": Decimal("0.40"),
        "risk_signal_score": Decimal("0.10"),
        "database_fit_score": Decimal("0.05"),
        "metadata_confidence_score": Decimal("0.10"),
    },
    RANKING_PRESET_RISK: {
        "screening_score": Decimal("0.25"),
        "upside_signal_score": Decimal("0.05"),
        "downside_signal_score": Decimal("0.05"),
        "data_quality_score": Decimal("0.20"),
        "risk_signal_score": Decimal("0.30"),
        "database_fit_score": Decimal("0.05"),
        "metadata_confidence_score": Decimal("0.10"),
    },
    RANKING_PRESET_INCOME: {
        "database_fit_score": Decimal("0.30"),
        "risk_signal_score": Decimal("0.20"),
        "data_quality_score": Decimal("0.20"),
        "metadata_confidence_score": Decimal("0.15"),
        "screening_score": Decimal("0.10"),
        "upside_signal_score": Decimal("0.03"),
        "downside_signal_score": Decimal("0.02"),
    },
    RANKING_PRESET_GROWTH: {
        "screening_score": Decimal("0.25"),
        "upside_signal_score": Decimal("0.18"),
        "downside_signal_score": Decimal("0.07"),
        "data_quality_score": Decimal("0.10"),
        "risk_signal_score": Decimal("0.10"),
        "database_fit_score": Decimal("0.20"),
        "metadata_confidence_score": Decimal("0.10"),
    },
    RANKING_PRESET_VALUE: {
        "database_fit_score": Decimal("0.30"),
        "screening_score": Decimal("0.20"),
        "risk_signal_score": Decimal("0.20"),
        "data_quality_score": Decimal("0.15"),
        "metadata_confidence_score": Decimal("0.10"),
        "upside_signal_score": Decimal("0.03"),
        "downside_signal_score": Decimal("0.02"),
    },
    RANKING_PRESET_STABILITY: {
        "risk_signal_score": Decimal("0.30"),
        "data_quality_score": Decimal("0.20"),
        "metadata_confidence_score": Decimal("0.15"),
        "screening_score": Decimal("0.15"),
        "database_fit_score": Decimal("0.10"),
        "upside_signal_score": Decimal("0.05"),
        "downside_signal_score": Decimal("0.05"),
    },
    RANKING_PRESET_TREND: {
        "screening_score": Decimal("0.30"),
        "upside_signal_score": Decimal("0.22"),
        "downside_signal_score": Decimal("0.08"),
        "data_quality_score": Decimal("0.10"),
        "risk_signal_score": Decimal("0.15"),
        "database_fit_score": Decimal("0.05"),
        "metadata_confidence_score": Decimal("0.10"),
    },
    RANKING_PRESET_MULTI_FACTOR: {
        "screening_score": Decimal("0.30"),
        "upside_signal_score": Decimal("0.18"),
        "advanced_forecast_upside_score": Decimal("0.07"),
        "advanced_forecast_quality_score": Decimal("0.05"),
        "risk_signal_score": Decimal("0.17"),
        "downside_signal_score": Decimal("0.05"),
        "advanced_forecast_downside_score": Decimal("0.03"),
        "data_quality_score": Decimal("0.06"),
        "metadata_confidence_score": Decimal("0.04"),
        "research_score": Decimal("0.05"),
    },
    RANKING_PRESET_QUALITY_GROWTH: {
        "database_fit_score": Decimal("0.25"),
        "upside_signal_score": Decimal("0.18"),
        "downside_signal_score": Decimal("0.07"),
        "screening_score": Decimal("0.20"),
        "risk_signal_score": Decimal("0.10"),
        "data_quality_score": Decimal("0.10"),
        "metadata_confidence_score": Decimal("0.10"),
    },
    RANKING_PRESET_QUALITY_VALUE: {
        "database_fit_score": Decimal("0.30"),
        "screening_score": Decimal("0.20"),
        "risk_signal_score": Decimal("0.20"),
        "data_quality_score": Decimal("0.12"),
        "metadata_confidence_score": Decimal("0.08"),
        "upside_signal_score": Decimal("0.03"),
        "downside_signal_score": Decimal("0.02"),
        "research_score": Decimal("0.05"),
    },
    RANKING_PRESET_SUSTAINABLE_INCOME: {
        "database_fit_score": Decimal("0.30"),
        "risk_signal_score": Decimal("0.20"),
        "data_quality_score": Decimal("0.15"),
        "screening_score": Decimal("0.15"),
        "metadata_confidence_score": Decimal("0.10"),
        "upside_signal_score": Decimal("0.05"),
        "research_score": Decimal("0.05"),
    },
    RANKING_PRESET_MIN_VOLATILITY: {
        "risk_signal_score": Decimal("0.30"),
        "data_quality_score": Decimal("0.20"),
        "metadata_confidence_score": Decimal("0.15"),
        "screening_score": Decimal("0.15"),
        "database_fit_score": Decimal("0.15"),
        "research_score": Decimal("0.05"),
    },
    RANKING_PRESET_MOMENTUM: {
        "screening_score": Decimal("0.30"),
        "upside_signal_score": Decimal("0.22"),
        "downside_signal_score": Decimal("0.08"),
        "risk_signal_score": Decimal("0.15"),
        "data_quality_score": Decimal("0.10"),
        "database_fit_score": Decimal("0.05"),
        "metadata_confidence_score": Decimal("0.10"),
    },
    RANKING_PRESET_RISK_ADJUSTED: {
        "screening_score": Decimal("0.20"),
        "upside_signal_score": Decimal("0.15"),
        "downside_signal_score": Decimal("0.05"),
        "data_quality_score": Decimal("0.15"),
        "risk_signal_score": Decimal("0.20"),
        "database_fit_score": Decimal("0.15"),
        "metadata_confidence_score": Decimal("0.10"),
    },
    RANKING_PRESET_SMALL_GROWTH: {
        "screening_score": Decimal("0.25"),
        "upside_signal_score": Decimal("0.20"),
        "data_quality_score": Decimal("0.10"),
        "risk_signal_score": Decimal("0.15"),
        "database_fit_score": Decimal("0.25"),
        "metadata_confidence_score": Decimal("0.05"),
    },
    RANKING_PRESET_NISA_LONG_TERM: {
        "screening_score": Decimal("0.20"),
        "upside_signal_score": Decimal("0.10"),
        "data_quality_score": Decimal("0.20"),
        "risk_signal_score": Decimal("0.20"),
        "database_fit_score": Decimal("0.15"),
        "metadata_confidence_score": Decimal("0.10"),
        "research_score": Decimal("0.05"),
    },
    RANKING_PRESET_DATA_CONFIDENCE: {
        "screening_score": Decimal("0.10"),
        "upside_signal_score": Decimal("0.03"),
        "downside_signal_score": Decimal("0.02"),
        "data_quality_score": Decimal("0.35"),
        "risk_signal_score": Decimal("0.10"),
        "database_fit_score": Decimal("0.10"),
        "metadata_confidence_score": Decimal("0.30"),
    },
    RANKING_PRESET_ETF_CORE_COST: {
        "screening_score": Decimal("0.15"),
        "data_quality_score": Decimal("0.20"),
        "risk_signal_score": Decimal("0.20"),
        "database_fit_score": Decimal("0.30"),
        "metadata_confidence_score": Decimal("0.10"),
        "research_score": Decimal("0.05"),
    },
    RANKING_PRESET_ETF_INCOME: {
        "screening_score": Decimal("0.15"),
        "data_quality_score": Decimal("0.15"),
        "risk_signal_score": Decimal("0.20"),
        "database_fit_score": Decimal("0.35"),
        "metadata_confidence_score": Decimal("0.10"),
        "research_score": Decimal("0.05"),
    },
}

RANKING_WEIGHT_GROUPS: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    RANKING_PRESET_MULTI_FACTOR: (
        ("基礎評価", ("screening_score",)),
        (
            "予測・上昇気配",
            (
                "upside_signal_score",
                "advanced_forecast_upside_score",
                "advanced_forecast_quality_score",
            ),
        ),
        (
            "リスク・下振れ警戒",
            (
                "risk_signal_score",
                "downside_signal_score",
                "advanced_forecast_downside_score",
            ),
        ),
        ("データ信頼度", ("data_quality_score", "metadata_confidence_score")),
        ("Research確認材料", ("research_score",)),
    ),
}
RANKING_PURPOSE_WEIGHT_PRESETS = {
    RANKING_PURPOSE_SORT_TOTAL_SCORE: RANKING_PRESET_SORT_TOTAL_SCORE,
    RANKING_PURPOSE_SORT_DIVIDEND_YIELD: RANKING_PRESET_SORT_DIVIDEND_YIELD,
    RANKING_PURPOSE_SORT_PER: RANKING_PRESET_SORT_PER,
    RANKING_PURPOSE_SORT_PBR: RANKING_PRESET_SORT_PBR,
    RANKING_PURPOSE_SORT_ROE: RANKING_PRESET_SORT_ROE,
    RANKING_PURPOSE_SORT_MARKET_CAP: RANKING_PRESET_SORT_MARKET_CAP,
    RANKING_PURPOSE_SORT_VOLUME: RANKING_PRESET_SORT_VOLUME,
    RANKING_PURPOSE_SORT_VOLATILITY: RANKING_PRESET_SORT_VOLATILITY,
    RANKING_PURPOSE_SORT_RISK: RANKING_PRESET_SORT_RISK,
    RANKING_PURPOSE_SORT_DATA_QUALITY: RANKING_PRESET_SORT_DATA_QUALITY,
    RANKING_PURPOSE_MULTI_FACTOR: RANKING_PRESET_MULTI_FACTOR,
    RANKING_PURPOSE_QUALITY_GROWTH: RANKING_PRESET_QUALITY_GROWTH,
    RANKING_PURPOSE_QUALITY_VALUE: RANKING_PRESET_QUALITY_VALUE,
    RANKING_PURPOSE_SUSTAINABLE_INCOME: RANKING_PRESET_SUSTAINABLE_INCOME,
    RANKING_PURPOSE_MIN_VOLATILITY: RANKING_PRESET_MIN_VOLATILITY,
    RANKING_PURPOSE_MOMENTUM: RANKING_PRESET_MOMENTUM,
    RANKING_PURPOSE_RISK_ADJUSTED: RANKING_PRESET_RISK_ADJUSTED,
    RANKING_PURPOSE_SMALL_GROWTH: RANKING_PRESET_SMALL_GROWTH,
    RANKING_PURPOSE_NISA_LONG_TERM: RANKING_PRESET_NISA_LONG_TERM,
    RANKING_PURPOSE_DATA_CONFIDENCE: RANKING_PRESET_DATA_CONFIDENCE,
    RANKING_PURPOSE_ETF_CORE_COST: RANKING_PRESET_ETF_CORE_COST,
    RANKING_PURPOSE_ETF_INCOME: RANKING_PRESET_ETF_INCOME,
    RANKING_PURPOSE_DIVIDEND: RANKING_PRESET_INCOME,
    RANKING_PURPOSE_GROWTH: RANKING_PRESET_GROWTH,
    RANKING_PURPOSE_VALUE: RANKING_PRESET_VALUE,
    RANKING_PURPOSE_STABILITY: RANKING_PRESET_STABILITY,
    RANKING_PURPOSE_TREND: RANKING_PRESET_TREND,
    RANKING_PURPOSE_UPSIDE_SIGNAL: RANKING_PRESET_UPSIDE_SIGNAL,
    RANKING_PURPOSE_REVERSAL_EXPECTATION: RANKING_PRESET_REVERSAL_EXPECTATION,
    RANKING_PURPOSE_DOWNSIDE_SIGNAL: RANKING_PRESET_DOWNSIDE_SIGNAL,
}
RANKING_FETCH_LIMIT_FAST = "fast_100"
RANKING_FETCH_LIMIT_BALANCED = "balanced_300"
RANKING_FETCH_LIMIT_BROAD = "broad_800"
RANKING_FETCH_LIMIT_ALL = "all"
RANKING_FETCH_LIMIT_VALUES = {
    RANKING_FETCH_LIMIT_FAST: 100,
    RANKING_FETCH_LIMIT_BALANCED: 300,
    RANKING_FETCH_LIMIT_BROAD: 800,
    RANKING_FETCH_LIMIT_ALL: 0,
}
RANKING_DEFAULT_PERIOD_PRESET = "standard"
RANKING_PERIOD_PRESETS = {
    "short": 30,
    RANKING_DEFAULT_PERIOD_PRESET: 90,
    "medium": 180,
    "long": 365,
    "long_3y": 365 * 3,
    "long_5y": 365 * 5,
}
RANKING_YEAR_PERIOD_PRESETS = {
    "long": 1,
    "long_3y": 3,
    "long_5y": 5,
}
RANKING_BETA_RISK_ALL = "all"
RANKING_BETA_RISK_LOW = "low"
RANKING_BETA_RISK_STANDARD_OR_LOWER = "standard_or_lower"
RANKING_BETA_RISK_STANDARD = "standard"
RANKING_BETA_RISK_HIGH = "high"
RANKING_DETAIL_FILTERS_BY_CATEGORY = {
    (RANKING_REGION_JAPAN, RANKING_PRODUCT_STOCK): [
        "official_sector",
        "investment_theme",
        "market_cap",
        "risk_band",
        "dividend_yield",
        "per",
        "pbr",
        "roe",
        "nisa_eligibility",
    ],
    (RANKING_REGION_US, RANKING_PRODUCT_STOCK): [
        "official_sector",
        "investment_theme",
        "market_cap",
        "risk_band",
        "dividend_yield",
        "per",
        "roe",
        "nisa_eligibility",
    ],
    (RANKING_REGION_OTHER_GLOBAL, RANKING_PRODUCT_STOCK): [
        "official_sector",
        "investment_theme",
        "market_cap",
        "risk_band",
        "dividend_yield",
        "nisa_eligibility",
    ],
    (RANKING_REGION_ALL, RANKING_PRODUCT_STOCK): [
        "official_sector",
        "investment_theme",
        "market_cap",
        "risk_band",
        "dividend_yield",
        "per",
        "roe",
        "nisa_eligibility",
    ],
    (RANKING_REGION_ALL, RANKING_PRODUCT_ETF): [
        "investment_theme",
        "benchmark_index",
        "expense_ratio",
        "dividend_yield",
        "complexity",
        "nisa_eligibility",
    ],
    (RANKING_REGION_ALL, RANKING_PRODUCT_MUTUAL_FUND): [
        "expense_ratio",
        "nisa_eligibility",
        "complexity",
    ],
    (RANKING_REGION_ALL, RANKING_PRODUCT_ALL): [
        "official_sector",
        "investment_theme",
        "market_cap",
        "risk_band",
        "dividend_yield",
        "benchmark_index",
        "expense_ratio",
        "complexity",
        "nisa_eligibility",
    ],
}
RANKING_FILTER_DEFAULTS: dict[str, str] = {
    "market_data_ranking_region": RANKING_REGION_JAPAN,
    "market_data_ranking_product_type": RANKING_PRODUCT_STOCK,
    "market_data_ranking_policy": RANKING_PURPOSE_MULTI_FACTOR,
    "market_data_ranking_purpose": RANKING_PURPOSE_MULTI_FACTOR,
    "market_data_ranking_fetch_limit": RANKING_FETCH_LIMIT_BALANCED,
    "market_data_ranking_period": RANKING_DEFAULT_PERIOD_PRESET,
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
    "market_data_ranking_official_sector": "all",
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
RANKING_FILTER_HELP_TEXTS = ranking_texts.RANKING_FILTER_HELP_TEXTS
RANKING_PURPOSE_HELP_TEXTS = ranking_texts.RANKING_PURPOSE_HELP_TEXTS

RANKING_PURPOSE_PRIMARY_COLUMNS: dict[str, tuple[str, ...]] = {
    RANKING_PURPOSE_SORT_TOTAL_SCORE: (
        "総合スコア",
        "Screening",
        "Risk",
        "データ品質",
    ),
    RANKING_PURPOSE_SORT_DIVIDEND_YIELD: (
        "配当利回り",
        "Risk",
        "データ品質",
        "総合スコア",
    ),
    RANKING_PURPOSE_SORT_PER: (
        "PER",
        "PBR",
        "ROE",
        "Risk",
        "データ品質",
    ),
    RANKING_PURPOSE_SORT_PBR: (
        "PBR",
        "PER",
        "ROE",
        "Risk",
        "データ品質",
    ),
    RANKING_PURPOSE_SORT_ROE: (
        "ROE",
        "PER",
        "PBR",
        "データ品質",
        "Risk",
    ),
    RANKING_PURPOSE_SORT_MARKET_CAP: (
        "時価総額",
        "出来高",
        "データ品質",
        "総合スコア",
    ),
    RANKING_PURPOSE_SORT_VOLUME: (
        "出来高",
        "時価総額",
        "ボラティリティ",
        "総合スコア",
    ),
    RANKING_PURPOSE_SORT_VOLATILITY: (
        "ボラティリティ",
        "Risk",
        "データ品質",
        "総合スコア",
    ),
    RANKING_PURPOSE_SORT_RISK: (
        "Risk",
        "ボラティリティ",
        "下降警戒",
        "データ品質",
    ),
    RANKING_PURPOSE_SORT_DATA_QUALITY: (
        "データ品質",
        "DB信頼度",
        "根拠状態",
        "総合スコア",
    ),
    RANKING_PURPOSE_MULTI_FACTOR: (
        "総合スコア",
        "上昇気配",
        "下降警戒",
        "Risk",
        "データ品質",
    ),
    RANKING_PURPOSE_UPSIDE_SIGNAL: (
        "上昇気配",
        "下降警戒",
        "予測変化率",
        "方向一致",
    ),
    RANKING_PURPOSE_DOWNSIDE_SIGNAL: (
        "下降警戒",
        "Risk",
        "予測変化率",
        "上昇気配",
        "データ品質",
    ),
    RANKING_PURPOSE_REVERSAL_EXPECTATION: (
        "上向き兆候",
        "チャート形状",
        "調整/安定度",
        "20日高値乖離",
        "5日騰落率",
        "予測変化率",
        "上昇気配",
        "下降警戒",
        "Risk",
        "配当罠警戒",
        "総合スコア",
        "上向き兆候理由",
    ),
    RANKING_PURPOSE_MOMENTUM: (
        "Screening",
        "上昇気配",
        "下降警戒",
        "Risk",
    ),
    RANKING_PURPOSE_QUALITY_GROWTH: (
        "条件適合度",
        "ROE",
        "上昇気配",
        "Screening",
        "Risk",
    ),
    RANKING_PURPOSE_QUALITY_VALUE: (
        "条件適合度",
        "PER",
        "PBR",
        "ROE",
        "Risk",
    ),
    RANKING_PURPOSE_SUSTAINABLE_INCOME: (
        "配当利回り",
        "条件適合度",
        "Risk",
        "データ品質",
        "DB信頼度",
    ),
    RANKING_PURPOSE_MIN_VOLATILITY: (
        "Risk",
        "下降警戒",
        "データ品質",
        "DB信頼度",
        "時価総額",
    ),
    RANKING_PURPOSE_RISK_ADJUSTED: (
        "Risk",
        "Screening",
        "下降警戒",
        "上昇気配",
        "データ品質",
    ),
    RANKING_PURPOSE_SMALL_GROWTH: (
        "時価総額",
        "ROE",
        "上昇気配",
        "Screening",
        "Risk",
    ),
    RANKING_PURPOSE_NISA_LONG_TERM: (
        "NISA",
        "投資スタイル",
        "Risk",
        "データ品質",
        "条件適合度",
    ),
    RANKING_PURPOSE_DATA_CONFIDENCE: (
        "データ品質",
        "DB信頼度",
        "根拠状態",
        "条件適合度",
        "注意点",
    ),
    RANKING_PURPOSE_ETF_CORE_COST: (
        "経費率",
        "連動指数",
        "条件適合度",
        "データ品質",
        "DB信頼度",
    ),
    RANKING_PURPOSE_ETF_INCOME: (
        "配当利回り",
        "経費率",
        "連動指数",
        "条件適合度",
        "Risk",
    ),
    RANKING_PURPOSE_DIVIDEND: (
        "配当利回り",
        "条件適合度",
        "Risk",
        "データ品質",
        "DB信頼度",
    ),
    RANKING_PURPOSE_GROWTH: (
        "条件適合度",
        "ROE",
        "上昇気配",
        "Screening",
        "Risk",
    ),
    RANKING_PURPOSE_VALUE: (
        "条件適合度",
        "PER",
        "PBR",
        "Risk",
        "データ品質",
    ),
    RANKING_PURPOSE_STABILITY: (
        "Risk",
        "下降警戒",
        "データ品質",
        "DB信頼度",
        "時価総額",
    ),
    RANKING_PURPOSE_TREND: (
        "Screening",
        "上昇気配",
        "下降警戒",
        "Risk",
    ),
}

RANKING_PURPOSE_FOCUS_SUMMARIES = {
    RANKING_PURPOSE_SORT_TOTAL_SCORE: (
        "総合スコアが高い順です。複数材料の比較用スコアで、売買推奨ではありません。"
    ),
    RANKING_PURPOSE_SORT_DIVIDEND_YIELD: (
        "配当利回りが高い順です。高配当でも、業績・財務・減配リスクを確認します。"
    ),
    RANKING_PURPOSE_SORT_PER: (
        "PERが低い順です。割安に見える理由が業績悪化や一時要因ではないか確認します。"
    ),
    RANKING_PURPOSE_SORT_PBR: (
        "PBRが低い順です。資産面の割安さと収益性・市場評価の低さを合わせて確認します。"
    ),
    RANKING_PURPOSE_SORT_ROE: (
        "ROEが高い順です。資本効率の高さに加え、一時利益や財務レバレッジを確認します。"
    ),
    RANKING_PURPOSE_SORT_MARKET_CAP: (
        "時価総額が大きい順です。企業規模や流動性を見ますが、成長余地とは別観点です。"
    ),
    RANKING_PURPOSE_SORT_VOLUME: ("出来高が多い順です。取引の活発さや短期的な注目度を確認します。"),
    RANKING_PURPOSE_SORT_VOLATILITY: (
        "値動きが小さい順です。安定性の確認に使いますが、高リターンを意味するものではありません。"
    ),
    RANKING_PURPOSE_SORT_RISK: (
        "リスク確認スコアが高い順です。安定性を確認しやすい候補の参考で、安全保証ではありません。"
    ),
    RANKING_PURPOSE_SORT_DATA_QUALITY: (
        "データ品質が高い順です。欠損が少なく、取得状態が安定した候補から確認します。"
    ),
    RANKING_PURPOSE_MULTI_FACTOR: "総合点だけでなく、上昇気配・下降警戒・リスク・データ信頼度の偏りを確認します。",
    RANKING_PURPOSE_UPSIDE_SIGNAL: "上向きシグナルが強く、下降警戒が相対的に低い深掘り候補を確認します。",
    RANKING_PURPOSE_DOWNSIDE_SIGNAL: (
        "下降警戒が強い候補から、下落継続・急落・予測下振れの理由を確認します。"
    ),
    RANKING_PURPOSE_REVERSAL_EXPECTATION: (
        "まだ大きく上がっていない銘柄から、押し目・底打ち・横ばい上放れ・蓄積準備を探します。"
    ),
    RANKING_PURPOSE_MOMENTUM: "足元の価格評価と上昇気配・下降警戒がそろっているか、追随リスクも含めて確認します。",
    RANKING_PURPOSE_QUALITY_GROWTH: "成長条件に合う候補で、上昇気配と品質が伴っているかを確認します。",
    RANKING_PURPOSE_QUALITY_VALUE: "割安に見える候補で、リスクやデータ不足が理由になっていないかを確認します。",
    RANKING_PURPOSE_SUSTAINABLE_INCOME: "配当利回りだけでなく、持続性・リスク・データ信頼度を確認します。",
    RANKING_PURPOSE_MIN_VOLATILITY: "値動きの落ち着きとデータ信頼度を優先し、下降警戒を確認します。",
    RANKING_PURPOSE_RISK_ADJUSTED: "安定成長の候補として、リスク・下降警戒・データ信頼度の釣り合いを確認します。",
    RANKING_PURPOSE_SMALL_GROWTH: "小型・成長条件に合う候補で、上昇気配とリスクの釣り合いを確認します。",
    RANKING_PURPOSE_NISA_LONG_TERM: "制度適合、長期確認のしやすさ、リスク、データ信頼度を確認します。",
    RANKING_PURPOSE_DATA_CONFIDENCE: "まず根拠やデータがそろった候補から確認します。",
    RANKING_PURPOSE_ETF_CORE_COST: "ETFのコア候補として、コスト・指数・複雑性・データ信頼度を確認します。",
    RANKING_PURPOSE_ETF_INCOME: "ETFのインカム候補として、分配材料・コスト・分散性を確認します。",
    RANKING_PURPOSE_DIVIDEND: "旧来の配当重視として、配当材料と持続性の確認に寄せて表示します。",
    RANKING_PURPOSE_GROWTH: "旧来の成長重視として、成長条件と上昇気配・下降警戒の確認に寄せて表示します。",
    RANKING_PURPOSE_VALUE: "旧来の割安重視として、割安条件とRiskの確認に寄せて表示します。",
    RANKING_PURPOSE_STABILITY: "旧来の安定重視として、リスクとデータ信頼度の確認に寄せて表示します。",
    RANKING_PURPOSE_TREND: "旧来のトレンド重視として、足元の勢いと上昇気配・下降警戒の確認に寄せて表示します。",
}


def symbol_candidate_labels(rows: list[dict[str, str]], query: str = "") -> list[str]:
    labels = [f"{row['symbol']} - {row['name']}" for row in rows]
    normalized_query = query.strip().lower()
    if normalized_query:
        labels = [label for label in labels if normalized_query in label.lower()]
    return labels


def ranking_fetch_limit_label(limit_key: str) -> str:
    return RANKING_FETCH_LIMIT_LABELS.get(limit_key, limit_key)


def ranking_fetch_limit_value(limit_key: str) -> int:
    return RANKING_FETCH_LIMIT_VALUES.get(
        limit_key, RANKING_FETCH_LIMIT_VALUES[RANKING_FETCH_LIMIT_BALANCED]
    )


def limited_ranking_selected_labels(
    selected_labels: list[str],
    candidate_rows: list[dict[str, str]],
    *,
    preset: str,
    limit_key: str,
) -> list[str]:
    """Limit selected labels by local metadata before expensive provider fetches."""

    limit = ranking_fetch_limit_value(limit_key)
    if limit <= 0 or len(selected_labels) <= limit:
        return selected_labels

    selected_label_set = set(selected_labels)
    scored_labels: list[tuple[Decimal, str, str]] = []
    seen_labels: set[str] = set()
    for row in candidate_rows:
        label = f"{row.get('symbol', '')} - {row.get('name', row.get('symbol', ''))}"
        if label not in selected_label_set:
            continue
        database_fit = ranking_database_fit_score(row, preset)
        metadata_confidence = ranking_metadata_confidence_score(row)
        score = (database_fit * Decimal("0.7")) + (metadata_confidence * Decimal("0.3"))
        scored_labels.append((score, row.get("symbol", ""), label))
        seen_labels.add(label)

    for label in selected_labels:
        if label not in seen_labels:
            scored_labels.append((Decimal("-1"), label, label))

    scored_labels.sort(key=lambda item: (-item[0], item[1]))
    return [label for _, _, label in scored_labels[:limit]]


def ranking_period_label(preset: str) -> str:
    return RANKING_PERIOD_LABELS.get(preset, preset)


def ranking_region_label(region: str) -> str:
    return RANKING_REGION_LABELS.get(region, region)


def ranking_product_type_label(product_type: str) -> str:
    return RANKING_PRODUCT_TYPE_LABELS.get(product_type, product_type)


def ranking_purpose_label(purpose: str) -> str:
    return RANKING_PURPOSE_LABELS.get(purpose, purpose)


def ranking_policy_label(purpose: str) -> str:
    return RANKING_POLICY_LABELS.get(purpose, ranking_purpose_label(purpose))


def ranking_sort_label(purpose: str) -> str:
    return ranking_purpose_label(purpose)


def ranking_policy_for_purpose(purpose: str) -> str:
    if purpose in RANKING_POLICY_DISPLAY_ORDER:
        return purpose
    return RANKING_POLICY_PURPOSE_ALIASES.get(purpose, RANKING_PURPOSE_MULTI_FACTOR)


def ranking_policy_description(purpose: str) -> ranking_texts.RankingPolicyDescription:
    policy = (
        purpose
        if purpose in RANKING_POLICY_DESCRIPTIONS
        else RANKING_POLICY_PURPOSE_ALIASES.get(purpose, "")
    )
    description = RANKING_POLICY_DESCRIPTIONS.get(policy)
    if description is not None:
        return description
    label = ranking_policy_label(purpose)
    return {
        "short_summary": f"{label}の評価方針で候補を比較します。",
        "suited_for": "選択中の観点で候補を並べたい時",
        "main_focus": ("総合スコア",),
        "caution": "ランキングは比較・深掘り候補の整理であり、売買推奨ではありません。",
    }


def ranking_policy_options(product_type: str = RANKING_PRODUCT_STOCK) -> list[str]:
    """Return beginner-facing evaluation policies, not every internal profile."""

    _ = product_type
    return list(RANKING_POLICY_DISPLAY_ORDER)


def ranking_sort_options(product_type: str = RANKING_PRODUCT_STOCK) -> list[str]:
    """Return the compact top-level metric sort choices."""

    _ = product_type
    return list(RANKING_SORT_DISPLAY_ORDER)


def ranking_sort_help(purpose: str) -> str:
    return ranking_purpose_help(purpose)


def ranking_purpose_options(product_type: str = RANKING_PRODUCT_STOCK) -> list[str]:
    """Return top-level evaluation policy options for the Ranking UI."""

    return ranking_policy_options(product_type)


def ranking_purpose_help(purpose: str) -> str:
    return RANKING_PURPOSE_HELP_TEXTS.get(
        purpose,
        "取得後の表示順を決める評価軸です。銘柄DBと取得期間の価格評価を合わせて並べ替えます。",
    )


def ranking_weight_preset_for_purpose(purpose: str) -> str:
    return RANKING_PURPOSE_WEIGHT_PRESETS.get(purpose, RANKING_PRESET_BALANCED)


def ranking_weight_group_rows(preset: str) -> list[dict[str, str]]:
    """Return beginner-friendly grouped weight rows for a ranking preset."""

    weights = RANKING_WEIGHT_PRESETS.get(preset, {})
    groups = RANKING_WEIGHT_GROUPS.get(preset)
    if groups is None:
        return [
            {
                "group": RANKING_SCORE_FIELD_LABELS.get(field, field),
                "weight": _format_percent(weight),
            }
            for field, weight in weights.items()
            if weight > 0
        ]
    return [
        {
            "group": label,
            "weight": _format_percent(
                sum((weights.get(field, Decimal("0")) for field in fields), Decimal("0"))
            ),
        }
        for label, fields in groups
    ]


def ranking_purpose_primary_columns(purpose: str) -> tuple[str, ...]:
    return RANKING_PURPOSE_PRIMARY_COLUMNS.get(
        purpose,
        RANKING_PURPOSE_PRIMARY_COLUMNS[RANKING_PURPOSE_MULTI_FACTOR],
    )


def ranking_purpose_focus_summary(purpose: str) -> str:
    return RANKING_PURPOSE_FOCUS_SUMMARIES.get(
        purpose,
        "選択中の条件で重みが高い指標を中心に、深掘り候補を比較します。",
    )


def _ranking_metric_sort_primary_summary(purpose: str, preset: str) -> str:
    label = ranking_purpose_label(purpose)
    _, direction = RANKING_METRIC_SORT_PRESETS[preset]
    direction_label = "高い順" if direction == "desc" else "低い順"
    if purpose == RANKING_PURPOSE_REVERSAL_EXPECTATION:
        return f"{label} {direction_label}"
    if "順" in label:
        return label
    return f"{label} {direction_label}"


def _ranking_metric_sort_tie_breaker_summary(preset: str) -> str:
    if preset == RANKING_PRESET_REVERSAL_EXPECTATION:
        return "下落安全性・予測変化率・下降警戒で補助"
    return "総合スコアで補助"


def ranking_purpose_weight_summary(purpose: str, *, limit: int = 4) -> tuple[str, ...]:
    preset = ranking_weight_preset_for_purpose(purpose)
    if preset in RANKING_METRIC_SORT_PRESETS:
        return (
            f"主指標 {_ranking_metric_sort_primary_summary(purpose, preset)}",
            "欠損データ N/Aは末尾",
            f"同点補正 {_ranking_metric_sort_tie_breaker_summary(preset)}",
        )[:limit]
    weights = RANKING_WEIGHT_PRESETS.get(preset, RANKING_WEIGHT_PRESETS[RANKING_PRESET_BALANCED])
    ranked_weights = sorted(weights.items(), key=lambda item: (-item[1], item[0]))
    return tuple(
        f"{RANKING_SCORE_FIELD_LABELS.get(field, field)} {weight * Decimal('100'):.0f}%"
        for field, weight in ranked_weights[:limit]
        if weight > 0
    )


def ranking_purpose_context_cards(purpose: str, *, limit: int = 4) -> list[dict[str, str]]:
    """Return structured cards for the ranking-purpose guide UI."""

    preset = ranking_weight_preset_for_purpose(purpose)
    if preset in RANKING_METRIC_SORT_PRESETS:
        return [
            {
                "label": "主指標",
                "value": _ranking_metric_sort_primary_summary(purpose, preset),
                "help": "このランキング基準で最初に見る指標",
                "badge": "並び替え",
            },
            {
                "label": "欠損データ",
                "value": "N/Aは末尾",
                "help": "値が取れない候補は下位に回します",
                "badge": "データ",
            },
            {
                "label": "同点補正",
                "value": _ranking_metric_sort_tie_breaker_summary(preset),
                "help": "同点時は補助指標で順序を安定させます",
                "badge": "補助",
            },
        ][:limit]

    weights = RANKING_WEIGHT_PRESETS.get(preset, RANKING_WEIGHT_PRESETS[RANKING_PRESET_BALANCED])
    ranked_weights = sorted(weights.items(), key=lambda item: (-item[1], item[0]))
    return [
        {
            "label": RANKING_SCORE_FIELD_LABELS.get(field, field),
            "value": f"{weight * Decimal('100'):.0f}%",
            "help": "このランキング基準で重視する指標",
            "badge": "重み",
        }
        for field, weight in ranked_weights[:limit]
        if weight > 0
    ]


def ranking_detail_filters_for_category(region: str, product_type: str) -> list[str]:
    if product_type == RANKING_PRODUCT_ETF:
        return RANKING_DETAIL_FILTERS_BY_CATEGORY[(RANKING_REGION_ALL, RANKING_PRODUCT_ETF)]
    if product_type == RANKING_PRODUCT_MUTUAL_FUND:
        return RANKING_DETAIL_FILTERS_BY_CATEGORY[(RANKING_REGION_ALL, RANKING_PRODUCT_MUTUAL_FUND)]
    if product_type == RANKING_PRODUCT_STOCK:
        if region == RANKING_REGION_JAPAN:
            return RANKING_DETAIL_FILTERS_BY_CATEGORY[(RANKING_REGION_JAPAN, RANKING_PRODUCT_STOCK)]
        if region == RANKING_REGION_US:
            return RANKING_DETAIL_FILTERS_BY_CATEGORY[(RANKING_REGION_US, RANKING_PRODUCT_STOCK)]
        if region in {
            RANKING_REGION_CHINA_HK,
            RANKING_REGION_KOREA,
            RANKING_REGION_ASEAN,
            RANKING_REGION_OTHER_GLOBAL,
        }:
            return RANKING_DETAIL_FILTERS_BY_CATEGORY[
                (RANKING_REGION_OTHER_GLOBAL, RANKING_PRODUCT_STOCK)
            ]
        return RANKING_DETAIL_FILTERS_BY_CATEGORY[(RANKING_REGION_ALL, RANKING_PRODUCT_STOCK)]
    return RANKING_DETAIL_FILTERS_BY_CATEGORY[(RANKING_REGION_ALL, RANKING_PRODUCT_ALL)]


def _shift_years(value: date, years: int) -> date:
    target_year = value.year + years
    try:
        return value.replace(year=target_year)
    except ValueError:
        return value.replace(year=target_year, day=28)


def ranking_period_dates(preset: str, end: date) -> tuple[date, date]:
    years = RANKING_YEAR_PERIOD_PRESETS.get(preset)
    if years is not None:
        return _shift_years(end, -years), end

    days = RANKING_PERIOD_PRESETS.get(
        preset,
        RANKING_PERIOD_PRESETS[RANKING_DEFAULT_PERIOD_PRESET],
    )
    return end - timedelta(days=days), end


def symbol_universe_rows(
    reference_rows: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    if reference_rows is None:
        rows = symbol_universe_search_rows()
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


def normalize_dividend_filter_values(
    *,
    dividend_category: str,
    min_dividend_yield_pct: Decimal | str | int = Decimal("0"),
    dividend_yield_enabled: bool = False,
    dividend_yield_max_pct: Decimal | str | int = Decimal("10.0"),
) -> tuple[str, str, bool, str]:
    """Keep dividend category and explicit yield range mutually exclusive."""

    if dividend_yield_enabled:
        return "all", str(min_dividend_yield_pct), True, str(dividend_yield_max_pct)
    if dividend_category != "all":
        return dividend_category, "0.0", False, "10.0"
    return "all", "0.0", False, "10.0"


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
    official_sector: str = "all",
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
    apply_universe_policy: bool = True,
    active_detail_filters: Collection[str] | None = None,
) -> list[dict[str, str]]:
    normalized_query = query.strip().lower()
    (
        dividend_category,
        min_dividend_yield_pct,
        dividend_yield_enabled,
        dividend_yield_max_pct,
    ) = normalize_dividend_filter_values(
        dividend_category=dividend_category,
        min_dividend_yield_pct=min_dividend_yield_pct,
        dividend_yield_enabled=dividend_yield_enabled,
        dividend_yield_max_pct=dividend_yield_max_pct,
    )
    min_dividend = _decimal_filter_value(min_dividend_yield_pct, Decimal("0"))
    max_expense = _decimal_filter_value(max_expense_ratio_pct, Decimal("1.00"))
    detail_filters = (
        set(active_detail_filters)
        if active_detail_filters is not None
        else _active_ranking_detail_filters(region, product_type)
    )
    filtered: list[dict[str, str]] = []
    _ = ranking_purpose
    for row in rows:
        tags = _symbol_universe_values(row, "tags")
        theme_values = _symbol_theme_filter_values(row)
        official_sector_values = _symbol_official_sector_filter_values(row)
        if apply_universe_policy and not symbol_allowed_by_ranking_universe_policy(row):
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
            and not _symbol_matches_beta_risk(row, risk_band)
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
            "official_sector" in detail_filters
            and official_sector != "all"
            and official_sector not in official_sector_values
        ):
            continue
        if "investment_theme" in detail_filters and theme != "all" and theme not in theme_values:
            continue
        if (
            "industry_or_sector" in detail_filters
            and theme != "all"
            and theme not in theme_values
            and theme not in official_sector_values
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
                    row.get("sector", ""),
                    row.get("smai_theme_tags", ""),
                    row.get("sector_gics", ""),
                    row.get("industry_gics", ""),
                    row.get("tse_33_industry", ""),
                    row.get("topix_17", ""),
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
    official_sector: str = "all",
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
    else:
        (
            dividend_category,
            min_dividend_yield_pct,
            dividend_yield_enabled,
            dividend_yield_max_pct,
        ) = normalize_dividend_filter_values(
            dividend_category=dividend_category,
            min_dividend_yield_pct=min_dividend_yield_pct,
            dividend_yield_enabled=dividend_yield_enabled,
            dividend_yield_max_pct=dividend_yield_max_pct,
        )
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
    if "official_sector" not in detail_filters:
        official_sector = "all"
    if "investment_theme" not in detail_filters and "industry_or_sector" not in detail_filters:
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
            official_sector,
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


def ranking_insufficient_bars_error_row(
    *,
    provider: str,
    symbol: str,
    bar_count: int,
    display_start: date,
    display_end: date,
) -> dict[str, str]:
    """Explain why a symbol with too little history was excluded."""

    details = {
        "provider": provider,
        "symbol": symbol,
        "bar_count": bar_count,
        "display_start": display_start.isoformat(),
        "display_end": display_end.isoformat(),
        "reason": "insufficient_ohlcv_rows",
    }
    return {
        "symbol": symbol,
        "code": "RANKING-INSUFFICIENT-BARS",
        "message": "価格データが2本未満のため、ランキングから除外しました。",
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
        f"{provider} の {symbol_count} 銘柄ランキングは時間がかかる場合があります。"
        "遅い場合は期間や対象を絞ってください。"
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


def ranking_deep_dive_symbol_options(rows: list[dict[str, str]]) -> list[str]:
    """Return deep-dive symbols in the displayed ranking order."""

    indexed_rows = list(enumerate(rows))

    def sort_key(item: tuple[int, dict[str, str]]) -> tuple[int, int]:
        source_index, row = item
        try:
            rank = int(row.get("rank", ""))
        except (TypeError, ValueError):
            rank = len(rows) + source_index + 1
        return rank, source_index

    return ranking_symbol_options([row for _, row in sorted(indexed_rows, key=sort_key)])


def ranking_deep_dive_default_symbol(
    rows: list[dict[str, str]],
    *,
    current_symbol: str | None,
    source_key: str,
    current_source_key: str | None,
) -> str | None:
    options = ranking_deep_dive_symbol_options(rows)
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
    symbol_rows_by_symbol: dict[str, dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    if preset in RANKING_METRIC_SORT_PRESETS:
        return apply_ranking_metric_sort_preset(rows, preset, symbol_rows_by_symbol)
    weights = RANKING_WEIGHT_PRESETS[preset]
    preset_label = ranking_weight_preset_label(preset)
    symbol_rows = symbol_rows_by_symbol or {
        row.get("symbol", "").strip().upper(): row
        for row in symbol_universe_csv_rows()
        if row.get("symbol", "").strip()
    }
    reweighted_rows: list[dict[str, str]] = []
    for row in rows:
        symbol_row = symbol_rows.get(row.get("symbol", "").strip().upper(), {})
        database_fit_score = ranking_database_fit_score(symbol_row, preset)
        metadata_confidence_score = ranking_metadata_confidence_score(symbol_row)
        enriched_row = {
            **row,
            "dividend_yield_pct": row.get("dividend_yield_pct", "")
            or symbol_row.get("dividend_yield_pct", ""),
            "per": row.get("per", "") or symbol_row.get("per", ""),
            "pbr": row.get("pbr", "") or symbol_row.get("pbr", ""),
            "roe_pct": row.get("roe_pct", "") or symbol_row.get("roe_pct", ""),
            "database_fit_score": _format_score(database_fit_score),
            "metadata_confidence_score": _format_score(metadata_confidence_score),
        }
        enriched_row = _ensure_ranking_signal_fields(enriched_row)
        total = Decimal("0")
        for field, weight in weights.items():
            component_score = _ranking_component_score(enriched_row, field)
            total += component_score * weight
        warnings = row.get("warnings", "")
        reweighted_rows.append(
            {
                **enriched_row,
                "total_score": _format_score(total),
                "score_band": _score_band_for_total(total, warnings),
                "ranking_profile": preset_label,
                "note": ranking_profile_note(preset, symbol_row, database_fit_score),
            }
        )
    return rank_investment_score_rows(reweighted_rows)


def apply_ranking_metric_sort_preset(
    rows: list[dict[str, str]],
    preset: str,
    symbol_rows_by_symbol: dict[str, dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    field, direction = RANKING_METRIC_SORT_PRESETS[preset]
    preset_label = ranking_weight_preset_label(preset)
    symbol_rows = symbol_rows_by_symbol or {
        row.get("symbol", "").strip().upper(): row
        for row in symbol_universe_csv_rows()
        if row.get("symbol", "").strip()
    }
    enriched_rows: list[tuple[Decimal | None, dict[str, str]]] = []
    for row in rows:
        symbol_row = symbol_rows.get(row.get("symbol", "").strip().upper(), {})
        database_fit_score = ranking_database_fit_score(symbol_row, preset)
        metadata_confidence_score = ranking_metadata_confidence_score(symbol_row)
        enriched_row = {
            **row,
            "dividend_yield_pct": row.get("dividend_yield_pct", "")
            or symbol_row.get("dividend_yield_pct", ""),
            "per": row.get("per", "") or symbol_row.get("per", ""),
            "pbr": row.get("pbr", "") or symbol_row.get("pbr", ""),
            "roe_pct": row.get("roe_pct", "") or symbol_row.get("roe_pct", ""),
            "database_fit_score": row.get("database_fit_score", "")
            or _format_score(database_fit_score),
            "metadata_confidence_score": row.get("metadata_confidence_score", "")
            or _format_score(metadata_confidence_score),
            "ranking_profile": row.get("ranking_profile", "") or preset_label,
            "note": row.get("note", "") or ranking_metric_sort_note(preset),
        }
        enriched_row = _ensure_ranking_signal_fields(enriched_row)
        enriched_rows.append((_ranking_metric_sort_value(enriched_row, field), enriched_row))
    if preset == RANKING_PRESET_REVERSAL_EXPECTATION:
        ranked = sorted(
            (row for _, row in enriched_rows),
            key=lambda row: (
                -(
                    _ranking_sort_decimal_from_text(row.get("reversal_expectation_score", ""))
                    or Decimal("-1")
                ),
                -(
                    _ranking_sort_decimal_from_text(row.get("reversal_safety_score", ""))
                    or Decimal("-1")
                ),
                -(
                    _ranking_sort_decimal_from_text(row.get("forecast_return_pct", ""))
                    or Decimal("-999")
                ),
                _ranking_sort_decimal_from_text(row.get("downside_signal_score", ""))
                or Decimal("999"),
                -(_ranking_sort_decimal_from_text(row.get("total_score", "")) or Decimal("-1")),
                row.get("symbol", ""),
            ),
        )
        return [{**row, "rank": str(index)} for index, row in enumerate(ranked, start=1)]
    reverse_metric = direction == "desc"

    def sort_key(item: tuple[Decimal | None, dict[str, str]]) -> tuple[object, ...]:
        metric_value, row = item
        total_score = _ranking_sort_decimal_from_text(row.get("total_score", ""))
        symbol = row.get("symbol", "")
        if metric_value is None:
            metric_key = Decimal("0")
        else:
            metric_key = -metric_value if reverse_metric else metric_value
        total_key = -(total_score or Decimal("-1"))
        return (metric_value is None, metric_key, total_key, symbol)

    ranked = [row for _, row in sorted(enriched_rows, key=sort_key)]
    return [{**row, "rank": str(index)} for index, row in enumerate(ranked, start=1)]


def ranking_metric_sort_note(preset: str) -> str:
    return {
        RANKING_PRESET_SORT_TOTAL_SCORE: "総合スコア順です。比較候補を絞る参考順で、売買推奨ではありません。",
        RANKING_PRESET_SORT_DIVIDEND_YIELD: "配当利回り順です。減配リスクや業績の安定性を合わせて確認します。",
        RANKING_PRESET_SORT_PER: "PER低い順です。低評価の理由が一時要因か業績不安かを確認します。",
        RANKING_PRESET_SORT_PBR: "PBR低い順です。資産面の割安さと収益性を合わせて確認します。",
        RANKING_PRESET_SORT_ROE: "ROE高い順です。一時利益や財務レバレッジも確認します。",
        RANKING_PRESET_SORT_MARKET_CAP: "時価総額順です。企業規模と流動性の確認材料です。",
        RANKING_PRESET_SORT_VOLUME: "出来高順です。短期的な注目度や売買しやすさの参考です。",
        RANKING_PRESET_SORT_VOLATILITY: "値動き小さい順です。安定性の参考であり、リターン保証ではありません。",
        RANKING_PRESET_SORT_RISK: (
            "リスク確認しやすい順です。安全保証ではなく、値動きと下落耐性の確認材料です。"
        ),
        RANKING_PRESET_SORT_DATA_QUALITY: "データ信頼度順です。欠損が少ない候補から確認します。",
    }.get(preset, "比較候補を確認するための並べ替えです。")


def _ranking_metric_sort_value(row: dict[str, str], field: str) -> Decimal | None:
    metric_value = ranking_fundamental_metric_value(field, row.get(field, ""))
    if field in RANKING_FUNDAMENTAL_METRIC_FIELDS:
        return metric_value
    return _ranking_sort_decimal_from_text(row.get(field, ""))


def _ensure_ranking_signal_fields(row: dict[str, str]) -> dict[str, str]:
    forecast_agreement = _optional_decimal_from_text(row.get("forecast_agreement_score", ""))
    neutral_direction = forecast_agreement if forecast_agreement is not None else Decimal("50")
    upside = _optional_decimal_from_text(row.get("upside_signal_score", ""))
    downside = _optional_decimal_from_text(row.get("downside_signal_score", ""))
    enriched = dict(row)
    if not enriched.get("upside_signal_score"):
        enriched["upside_signal_score"] = _format_score(upside or neutral_direction)
    if not enriched.get("downside_signal_score"):
        enriched["downside_signal_score"] = _format_score(downside or Decimal("50"))
    # Leave absent forecast/model evidence absent during score calculation.
    # `calculate_reversal_expectation` treats absence as neutral, whereas an
    # explicit zero is a meaningful negative observation. The display values
    # are filled after scoring for backward-compatible table rendering.
    enriched.update(calculate_reversal_expectation(enriched).as_row())
    if not enriched.get("forecast_return_pct"):
        enriched["forecast_return_pct"] = "0"
    if not enriched.get("up_model_count"):
        enriched["up_model_count"] = "0"
    if not enriched.get("down_model_count"):
        enriched["down_model_count"] = "0"
    if not enriched.get("flat_model_count"):
        enriched["flat_model_count"] = "0"
    if not enriched.get("research_score"):
        enriched["research_score"] = "50"
    for advanced_field in (
        "advanced_forecast_upside_score",
        "advanced_forecast_downside_score",
        "advanced_forecast_quality_score",
    ):
        if not enriched.get(advanced_field):
            enriched[advanced_field] = "50"
    return enriched


def _ranking_component_score(row: dict[str, str], field: str) -> Decimal:
    value = _optional_decimal_from_text(row.get(field, ""))
    if field in {"downside_signal_score", "advanced_forecast_downside_score"}:
        # Lower downside warning ranks higher; UI still displays the raw warning score.
        if value is None:
            return Decimal("50")
        return max(Decimal("0"), min(Decimal("100"), Decimal("100") - value))
    if value is not None:
        return value
    if field in {
        "advanced_forecast_upside_score",
        "advanced_forecast_quality_score",
        "research_score",
    }:
        return Decimal("50")
    if field == "upside_signal_score":
        return _optional_decimal_from_text(row.get("forecast_agreement_score", "")) or Decimal("50")
    return Decimal("0")


def ranking_database_fit_score(
    symbol_row: dict[str, str],
    preset: str,
) -> Decimal:
    """Score how well the local symbol master matches the selected ranking profile."""

    if not symbol_row:
        return Decimal("40")
    score = Decimal("50")
    asset_type = symbol_row.get("asset_type", "")
    if symbol_row.get("is_active", "").lower() in {"", "true"}:
        score += Decimal("5")
    if _symbol_matches_nisa_eligibility(symbol_row, "eligible"):
        score += Decimal("5")
    if asset_type == "etf":
        score += _etf_database_fit_bonus(symbol_row, preset)
    else:
        score += _stock_database_fit_bonus(symbol_row, preset)
    return max(Decimal("0"), min(Decimal("100"), score))


def ranking_metadata_confidence_score(symbol_row: dict[str, str]) -> Decimal:
    """Prefer rows with a clear source, freshness, and enough ranking metadata."""

    if not symbol_row:
        return Decimal("30")
    score = Decimal("35")
    if symbol_row.get("metadata_source"):
        score += Decimal("15")
    if symbol_row.get("metadata_as_of") or symbol_row.get("metadata_updated_at"):
        score += Decimal("15")
    common_fields = [
        "nisa_category",
        "market_cap_tier",
        "dividend_yield_pct",
        "dividend_category",
        "risk_band",
    ]
    stock_fields = ["per", "pbr", "roe_pct"]
    etf_fields = ["index_family", "expense_ratio_pct", "complexity"]
    fields = common_fields + (etf_fields if symbol_row.get("asset_type") == "etf" else stock_fields)
    available = sum(1 for field in fields if _symbol_metadata_field_available(symbol_row, field))
    score += Decimal(available) * Decimal("5")
    return max(Decimal("0"), min(Decimal("100"), score))


def ranking_profile_note(
    preset: str,
    symbol_row: dict[str, str],
    database_fit_score: Decimal,
) -> str:
    profile = ranking_weight_preset_label(preset)
    if database_fit_score >= Decimal("75"):
        return f"{profile}の条件に合いやすい候補です。" "売買推奨ではなく、根拠確認の優先順です。"
    if database_fit_score >= Decimal("55"):
        return f"{profile}で比較しています。" "銘柄DBの根拠と価格データを合わせて確認してください。"
    if symbol_row:
        return (
            f"{profile}ではDB条件の確認余地があります。"
            "詳細モーダルで不足項目を確認してください。"
        )
    return f"{profile}で比較しています。銘柄DB未登録項目があるため詳細確認が必要です。"


def _stock_database_fit_bonus(symbol_row: dict[str, str], preset: str) -> Decimal:
    dividend_yield = ranking_dividend_yield_pct_value(symbol_row.get("dividend_yield_pct", ""))
    per = ranking_per_value(symbol_row.get("per", ""))
    pbr = ranking_pbr_value(symbol_row.get("pbr", ""))
    roe = ranking_roe_pct_value(symbol_row.get("roe_pct", "")) or Decimal("0")
    risk_band = symbol_row.get("risk_band", "")
    market_cap_tier = symbol_row.get("market_cap_tier", "")
    bonus = Decimal("0")
    if preset in {RANKING_PRESET_INCOME, RANKING_PRESET_SUSTAINABLE_INCOME}:
        if dividend_yield is not None and dividend_yield >= Decimal("3"):
            bonus += Decimal("25")
        elif dividend_yield is not None and dividend_yield > Decimal("0"):
            bonus += Decimal("10")
        if pbr is not None and pbr <= Decimal("2"):
            bonus += Decimal("5")
        if risk_band in {"LOW", "MEDIUM"}:
            bonus += Decimal("10")
        if (
            preset == RANKING_PRESET_SUSTAINABLE_INCOME
            and dividend_yield is not None
            and dividend_yield <= Decimal("8")
        ):
            bonus += Decimal("5")
    elif preset in {RANKING_PRESET_GROWTH, RANKING_PRESET_QUALITY_GROWTH}:
        if roe >= Decimal("20"):
            bonus += Decimal("20")
        elif roe >= Decimal("10"):
            bonus += Decimal("10")
        if per is not None and per <= Decimal("40"):
            bonus += Decimal("5")
        if market_cap_tier in {"mega", "large", "mid"}:
            bonus += Decimal("5")
        if preset == RANKING_PRESET_QUALITY_GROWTH and risk_band != "HIGH":
            bonus += Decimal("5")
    elif preset in {RANKING_PRESET_VALUE, RANKING_PRESET_QUALITY_VALUE}:
        if per is not None and per <= Decimal("15"):
            bonus += Decimal("20")
        elif per is not None and per <= Decimal("25"):
            bonus += Decimal("10")
        if pbr is not None and pbr <= Decimal("1.5"):
            bonus += Decimal("20")
        elif pbr is not None and pbr <= Decimal("3"):
            bonus += Decimal("10")
        if roe >= Decimal("8"):
            bonus += Decimal("5")
        if preset == RANKING_PRESET_QUALITY_VALUE and risk_band in {"LOW", "MEDIUM"}:
            bonus += Decimal("5")
    elif preset in {RANKING_PRESET_STABILITY, RANKING_PRESET_MIN_VOLATILITY}:
        if market_cap_tier in {"mega", "large"}:
            bonus += Decimal("20")
        elif market_cap_tier == "mid":
            bonus += Decimal("10")
        if risk_band in {"LOW", "MEDIUM"}:
            bonus += Decimal("20")
        if dividend_yield is not None and Decimal("0") < dividend_yield <= Decimal("5"):
            bonus += Decimal("5")
        if preset == RANKING_PRESET_MIN_VOLATILITY and risk_band == "LOW":
            bonus += Decimal("5")
    elif preset in {RANKING_PRESET_TREND, RANKING_PRESET_MOMENTUM}:
        if market_cap_tier in {"mega", "large", "mid"}:
            bonus += Decimal("10")
        if risk_band != "HIGH":
            bonus += Decimal("5")
        if preset == RANKING_PRESET_MOMENTUM and roe >= Decimal("8"):
            bonus += Decimal("5")
    elif preset == RANKING_PRESET_RISK_ADJUSTED:
        if risk_band in {"LOW", "MEDIUM"}:
            bonus += Decimal("20")
        if roe >= Decimal("8"):
            bonus += Decimal("10")
        if market_cap_tier in {"mega", "large", "mid"}:
            bonus += Decimal("10")
    elif preset == RANKING_PRESET_SMALL_GROWTH:
        if market_cap_tier in {"small", "micro"}:
            bonus += Decimal("20")
        elif market_cap_tier == "mid":
            bonus += Decimal("10")
        if roe >= Decimal("15"):
            bonus += Decimal("15")
        elif roe >= Decimal("8"):
            bonus += Decimal("8")
        if risk_band != "HIGH":
            bonus += Decimal("5")
    elif preset == RANKING_PRESET_NISA_LONG_TERM:
        if _symbol_matches_nisa_eligibility(symbol_row, "eligible"):
            bonus += Decimal("15")
        if risk_band in {"LOW", "MEDIUM"}:
            bonus += Decimal("15")
        if roe >= Decimal("8"):
            bonus += Decimal("10")
        if per is None or per <= Decimal("40"):
            bonus += Decimal("5")
    elif preset == RANKING_PRESET_DATA_CONFIDENCE:
        if symbol_row.get("metadata_source"):
            bonus += Decimal("10")
        if symbol_row.get("metadata_as_of") or symbol_row.get("metadata_updated_at"):
            bonus += Decimal("10")
        if per is not None and pbr is not None and roe > Decimal("0"):
            bonus += Decimal("15")
        if risk_band:
            bonus += Decimal("10")
    else:
        if roe >= Decimal("8"):
            bonus += Decimal("10")
        if risk_band in {"LOW", "MEDIUM"}:
            bonus += Decimal("10")
        if market_cap_tier in {"mega", "large", "mid"}:
            bonus += Decimal("5")
    return bonus


def _etf_database_fit_bonus(symbol_row: dict[str, str], preset: str) -> Decimal:
    expense_ratio = _optional_decimal_from_text(symbol_row.get("expense_ratio_pct", "")) or Decimal(
        "99"
    )
    dividend_yield = ranking_dividend_yield_pct_value(
        symbol_row.get("dividend_yield_pct", "")
    ) or Decimal("0")
    complexity = symbol_row.get("complexity", "")
    index_family = symbol_row.get("index_family", "")
    bonus = Decimal("0")
    if expense_ratio <= Decimal("0.2"):
        bonus += Decimal("20")
    elif expense_ratio <= Decimal("0.5"):
        bonus += Decimal("10")
    if complexity in {"beginner", "standard"}:
        bonus += Decimal("10")
    if index_family:
        bonus += Decimal("10")
    if preset in {
        RANKING_PRESET_INCOME,
        RANKING_PRESET_SUSTAINABLE_INCOME,
    } and dividend_yield >= Decimal("2"):
        bonus += Decimal("10")
    if (
        preset in {RANKING_PRESET_STABILITY, RANKING_PRESET_MIN_VOLATILITY}
        and complexity == "beginner"
    ):
        bonus += Decimal("5")
    if preset == RANKING_PRESET_ETF_CORE_COST:
        if expense_ratio <= Decimal("0.1"):
            bonus += Decimal("10")
        if complexity == "beginner":
            bonus += Decimal("10")
        if _symbol_matches_nisa_eligibility(symbol_row, "eligible"):
            bonus += Decimal("10")
    if preset == RANKING_PRESET_ETF_INCOME:
        if dividend_yield >= Decimal("2"):
            bonus += Decimal("15")
        if expense_ratio <= Decimal("0.5"):
            bonus += Decimal("5")
        if index_family:
            bonus += Decimal("5")
    if preset == RANKING_PRESET_DATA_CONFIDENCE:
        if symbol_row.get("metadata_source"):
            bonus += Decimal("10")
        if symbol_row.get("metadata_as_of") or symbol_row.get("metadata_updated_at"):
            bonus += Decimal("10")
    return bonus


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
    if key == "dividend_yield_pct":
        value = ranking_dividend_yield_pct_value(row.get(key, ""))
        if value is None:
            return False
    elif key in {"per", "pbr", "roe_pct"}:
        value = ranking_fundamental_metric_value(key, row.get(key, ""))
        if value is None:
            return False
    else:
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
        "dividend_yield_pct": row.get("dividend_yield_pct", ""),
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
        "smai_theme_tags": row.get("smai_theme_tags", ""),
        "sector_gics": row.get("sector_gics", ""),
        "industry_gics": row.get("industry_gics", ""),
        "subindustry_gics": row.get("subindustry_gics", ""),
        "tse_33_industry": row.get("tse_33_industry", ""),
        "topix_17": row.get("topix_17", ""),
        "consensus_rating": row.get("consensus_rating", ""),
        "forecast_agreement": row.get("forecast_agreement", ""),
        "data_quality": row.get("data_quality", ""),
        "risk_band": row.get("risk_band", ""),
        "metadata_source": row.get("metadata_source", ""),
        "metadata_as_of": row.get("metadata_as_of", ""),
        "metadata_updated_at": row.get("metadata_updated_at", ""),
    }
    return universe_row


def _symbol_universe_values(row: dict[str, str], key: str) -> set[str]:
    return {value.strip() for value in row.get(key, "").split(",") if value.strip()}


_OFFICIAL_SECTOR_NORMALIZED_VALUES = {
    "basic materials": "materials",
    "communication services": "communication",
    "consumer cyclical": "consumer",
    "consumer defensive": "consumer",
    "consumer discretionary": "consumer",
    "consumer staples": "consumer",
    "financial services": "financial",
    "financials": "financial",
    "health care": "healthcare",
    "information technology": "technology",
    "industrials": "industrial",
    "real estate": "real_estate",
    "水産・農林業": "consumer",
    "鉱業": "energy",
    "建設業": "industrial",
    "建設・資材": "industrial",
    "食料品": "consumer",
    "繊維製品": "consumer",
    "パルプ・紙": "materials",
    "化学": "materials",
    "素材・化学": "materials",
    "医薬品": "healthcare",
    "石油・石炭製品": "energy",
    "ゴム製品": "materials",
    "ガラス・土石製品": "materials",
    "鉄鋼": "materials",
    "鉄鋼・非鉄": "materials",
    "非鉄金属": "materials",
    "金属製品": "materials",
    "機械": "industrial",
    "電気機器": "technology",
    "電機・精密": "technology",
    "輸送用機器": "consumer",
    "自動車・輸送機": "consumer",
    "精密機器": "technology",
    "その他製品": "consumer",
    "電気・ガス業": "utilities",
    "電力・ガス": "utilities",
    "陸運業": "industrial",
    "海運業": "industrial",
    "空運業": "industrial",
    "倉庫・運輸関連業": "industrial",
    "運輸・物流": "industrial",
    "情報・通信業": "communication",
    "情報通信・サービスその他": "communication",
    "卸売業": "industrial",
    "商社・卸売": "industrial",
    "小売業": "consumer",
    "銀行業": "financial",
    "銀行": "financial",
    "証券、商品先物取引業": "financial",
    "保険業": "financial",
    "その他金融業": "financial",
    "金融（除く銀行）": "financial",
    "不動産業": "real_estate",
    "不動産": "real_estate",
    "サービス業": "consumer",
}


def _normalized_official_sector_value(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return ""
    normalized = stripped.lower()
    if normalized in RANKING_OFFICIAL_SECTOR_LABELS:
        return normalized
    return _OFFICIAL_SECTOR_NORMALIZED_VALUES.get(
        normalized
    ) or _OFFICIAL_SECTOR_NORMALIZED_VALUES.get(stripped, "")


def _symbol_official_sector_filter_values(row: dict[str, str]) -> set[str]:
    values: set[str] = set()
    for key in (
        "sector",
        "sector_gics",
        "industry_gics",
        "subindustry_gics",
        "tse_33_industry",
        "topix_17",
    ):
        raw_value = row.get(key, "").strip()
        if not raw_value:
            continue
        values.add(raw_value)
        normalized = _normalized_official_sector_value(raw_value)
        if normalized:
            values.add(normalized)
    return values


def _symbol_theme_filter_values(row: dict[str, str]) -> set[str]:
    values = set()
    for key in (
        "smai_theme_tags",
        "theme",
        "index_family",
    ):
        raw_value = row.get(key, "").strip()
        if not raw_value:
            continue
        if key in {"tags", "smai_theme_tags"}:
            values.update(_symbol_universe_values(row, key))
        else:
            values.add(raw_value)
    return values


def _single_value_getter(key: str):
    def getter(row: dict[str, str]) -> set[str]:
        value = row.get(key, "").strip()
        return {value} if value else set()

    return getter


def _risk_filter_values(row: dict[str, str]) -> set[str]:
    risk_band = row.get("risk_band", "").strip()
    values: set[str] = set()
    if risk_band == "LOW":
        values.update({RANKING_BETA_RISK_LOW, RANKING_BETA_RISK_STANDARD_OR_LOWER})
    elif risk_band == "MEDIUM":
        values.update({RANKING_BETA_RISK_STANDARD, RANKING_BETA_RISK_STANDARD_OR_LOWER})
    elif risk_band == "HIGH":
        values.add(RANKING_BETA_RISK_HIGH)
    return values


def _nisa_filter_values(row: dict[str, str]) -> set[str]:
    return {
        value
        for value in RANKING_NISA_ELIGIBILITY_LABELS
        if value != "all" and _symbol_matches_nisa_eligibility(row, value)
    }


def _complexity_filter_values(row: dict[str, str]) -> set[str]:
    return {
        value
        for value in RANKING_COMPLEXITY_LABELS
        if value != "all" and _symbol_complexity_allowed(row.get("complexity", "standard"), value)
    }


def symbol_universe_filter_value_counts(
    rows: list[dict[str, str]],
    category: str,
) -> dict[str, int]:
    """Return UI filter counts using the same classification logic as ranking filters.

    Counts are intentionally based on filter values rather than a single DB column.
    For example, investment themes include ``theme``, ``smai_theme_tags`` and
    ``index_family`` so the UI can surface categories that are present in the DB
    even when the primary theme column is coarser. Generic filters also use the
    same helper semantics as the actual screening condition, e.g. ``standard``
    complexity means beginner + standard products.
    """

    counts: dict[str, int] = {}
    if category == "official_sector":
        allowed_values = set(RANKING_OFFICIAL_SECTOR_LABELS) - {"all"}
        value_getter = _symbol_official_sector_filter_values
    elif category == "investment_theme":
        allowed_values = set(RANKING_INVESTMENT_THEME_LABELS) - {"all"}
        value_getter = _symbol_theme_filter_values
    elif category == "market_cap":
        allowed_values = set(RANKING_MARKET_CAP_LABELS) - {"all"}
        value_getter = _single_value_getter("market_cap_tier")
    elif category == "risk_band":
        allowed_values = set(RANKING_BETA_RISK_LABELS) - {"all"}
        value_getter = _risk_filter_values
    elif category == "nisa_eligibility":
        allowed_values = set(RANKING_NISA_ELIGIBILITY_LABELS) - {"all"}
        value_getter = _nisa_filter_values
    elif category == "benchmark_index":
        allowed_values = set(RANKING_INDEX_FAMILY_LABELS) - {"all"}
        value_getter = _single_value_getter("index_family")
    elif category == "complexity":
        allowed_values = set(RANKING_COMPLEXITY_LABELS) - {"all"}
        value_getter = _complexity_filter_values
    elif category == "dividend_category":
        allowed_values = set(RANKING_DIVIDEND_LABELS) - {"all"}
        value_getter = _single_value_getter("dividend_category")
    elif category == "currency":
        allowed_values = set(RANKING_CURRENCY_LABELS) - {"all"}
        value_getter = _single_value_getter("currency")
    else:
        return counts

    for row in rows:
        row_values = {value for value in value_getter(row) if value in allowed_values}
        for value in row_values:
            counts[value] = counts.get(value, 0) + 1
    return counts


def _symbol_matches_region(row: dict[str, str], region: str) -> bool:
    market = row.get("market", "")
    foreign_group = row.get("foreign_market_group", "")
    if region == RANKING_REGION_ALL:
        return True
    if region == RANKING_REGION_JAPAN:
        return market == "jp"
    if region == RANKING_REGION_US:
        return market == "us"
    if region == RANKING_REGION_CHINA_HK:
        return market in {"hong_kong", "china"} or foreign_group == "china_hk"
    if region == RANKING_REGION_KOREA:
        return market == "korea" or foreign_group == "korea"
    if region == RANKING_REGION_ASEAN:
        return market in RANKING_ASEAN_MARKETS or foreign_group == "asean"
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


def _symbol_matches_beta_risk(row: dict[str, str], selected_risk: str) -> bool:
    risk_band = row.get("risk_band", "")
    if selected_risk in {RANKING_BETA_RISK_ALL, ""}:
        return True
    if selected_risk in {RANKING_BETA_RISK_LOW, "LOW"}:
        return risk_band == "LOW"
    if selected_risk == RANKING_BETA_RISK_STANDARD_OR_LOWER:
        return risk_band in {"LOW", "MEDIUM"}
    if selected_risk in {RANKING_BETA_RISK_STANDARD, "MEDIUM"}:
        return risk_band == "MEDIUM"
    if selected_risk in {RANKING_BETA_RISK_HIGH, "HIGH"}:
        return risk_band == "HIGH"
    return risk_band == selected_risk


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
    growth = row.get("nisa_growth_eligible", "") == "true" or nisa_category in {
        "both",
        "growth",
    }
    tsumitate = row.get("nisa_tsumitate_eligible", "") == "true" or nisa_category in {
        "both",
        "tsumitate",
    }
    if nisa_eligibility == "eligible":
        return growth or tsumitate
    if nisa_eligibility == "growth":
        return growth
    if nisa_eligibility == "none":
        return nisa_category == "none" or (
            row.get("nisa_growth_eligible", "") == "false"
            and row.get("nisa_tsumitate_eligible", "") == "false"
        )
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


def _format_percent(value: Decimal) -> str:
    return f"{value * Decimal('100'):.0f}%"


def ranking_dividend_yield_pct_value(value: object) -> Decimal | None:
    dividend_yield = _ranking_sort_decimal_from_text(value)
    if dividend_yield is None:
        return None
    if dividend_yield < Decimal("0") or dividend_yield > RANKING_MAX_REASONABLE_DIVIDEND_YIELD_PCT:
        return None
    return dividend_yield


def ranking_dividend_yield_pct_is_abnormal(value: object) -> bool:
    dividend_yield = _ranking_sort_decimal_from_text(value)
    return dividend_yield is not None and dividend_yield > RANKING_MAX_REASONABLE_DIVIDEND_YIELD_PCT


def ranking_per_value(value: object) -> Decimal | None:
    per = _ranking_sort_decimal_from_text(value)
    if per is None:
        return None
    if per <= Decimal("0") or per > RANKING_MAX_REASONABLE_PER:
        return None
    return per


def ranking_pbr_value(value: object) -> Decimal | None:
    pbr = _ranking_sort_decimal_from_text(value)
    if pbr is None:
        return None
    if pbr <= Decimal("0") or pbr > RANKING_MAX_REASONABLE_PBR:
        return None
    return pbr


def ranking_roe_pct_value(value: object) -> Decimal | None:
    roe = _ranking_sort_decimal_from_text(value)
    if roe is None:
        return None
    if roe < RANKING_MIN_REASONABLE_ROE_PCT or roe > RANKING_MAX_REASONABLE_ROE_PCT:
        return None
    return roe


def ranking_fundamental_metric_value(field: str, value: object) -> Decimal | None:
    if field == "dividend_yield_pct":
        return ranking_dividend_yield_pct_value(value)
    if field == "per":
        return ranking_per_value(value)
    if field == "pbr":
        return ranking_pbr_value(value)
    if field == "roe_pct":
        return ranking_roe_pct_value(value)
    return None


def ranking_fundamental_metric_is_abnormal(field: str, value: object) -> bool:
    metric_value = _ranking_sort_decimal_from_text(value)
    return (
        metric_value is not None
        and field in RANKING_FUNDAMENTAL_METRIC_FIELDS
        and ranking_fundamental_metric_value(field, value) is None
    )


def _symbol_metadata_field_available(symbol_row: dict[str, str], field: str) -> bool:
    value = str(symbol_row.get(field, "")).strip()
    if not value:
        return False
    if (
        field in RANKING_FUNDAMENTAL_METRIC_FIELDS
        and ranking_fundamental_metric_value(field, value) is None
    ):
        return False
    return True


def _optional_decimal_from_text(value: str) -> Decimal | None:
    if value == "":
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def _ranking_sort_decimal_from_text(value: object) -> Decimal | None:
    text = str(value or "").replace(",", "").replace("%", "").strip()
    if not text or text in {"-", "N/A", "未接続", "未登録", "未取得", "未計算"}:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None
