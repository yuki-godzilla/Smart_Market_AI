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
RANKING_PURPOSE_UPSIDE_SIGNAL = "upside_signal"
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
RANKING_PURPOSE_LABELS = {
    RANKING_PURPOSE_MULTI_FACTOR: "総合マルチファクター",
    RANKING_PURPOSE_UPSIDE_SIGNAL: "上昇気配重視",
    RANKING_PURPOSE_MOMENTUM: "モメンタム・トレンド",
    RANKING_PURPOSE_QUALITY_GROWTH: "成長クオリティ",
    RANKING_PURPOSE_QUALITY_VALUE: "割安クオリティ",
    RANKING_PURPOSE_SUSTAINABLE_INCOME: "高配当の持続性",
    RANKING_PURPOSE_MIN_VOLATILITY: "低ボラ・安定",
    RANKING_PURPOSE_RISK_ADJUSTED: "リスク調整パフォーマンス",
    RANKING_PURPOSE_SMALL_GROWTH: "小型・成長探索",
    RANKING_PURPOSE_NISA_LONG_TERM: "NISA長期適合",
    RANKING_PURPOSE_DATA_CONFIDENCE: "データ信頼度優先",
    RANKING_PURPOSE_ETF_CORE_COST: "ETF低コスト・コア",
    RANKING_PURPOSE_ETF_INCOME: "ETFインカム・分散",
    RANKING_PURPOSE_DIVIDEND: "配当重視",
    RANKING_PURPOSE_GROWTH: "成長重視",
    RANKING_PURPOSE_VALUE: "割安重視",
    RANKING_PURPOSE_STABILITY: "安定重視",
    RANKING_PURPOSE_TREND: "トレンド重視",
}
RANKING_PURPOSE_DISPLAY_ORDER = (
    RANKING_PURPOSE_MULTI_FACTOR,
    RANKING_PURPOSE_UPSIDE_SIGNAL,
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
RANKING_FETCH_LIMIT_PRESET = RANKING_PRESET_MULTI_FACTOR
RANKING_WEIGHT_PRESET_LABELS = {
    RANKING_PRESET_BALANCED: "総合バランス",
    RANKING_PRESET_FORECAST: "上昇気配重視",
    RANKING_PRESET_QUALITY: "データ品質重視",
    RANKING_PRESET_RISK: "リスク控えめ",
    RANKING_PRESET_INCOME: "配当・インカム重視",
    RANKING_PRESET_GROWTH: "成長性重視",
    RANKING_PRESET_VALUE: "割安性重視",
    RANKING_PRESET_STABILITY: "安定性重視",
    RANKING_PRESET_TREND: "トレンド重視",
    RANKING_PRESET_UPSIDE_SIGNAL: "上昇気配重視",
    RANKING_PRESET_MULTI_FACTOR: "総合マルチファクター",
    RANKING_PRESET_QUALITY_GROWTH: "成長クオリティ",
    RANKING_PRESET_QUALITY_VALUE: "割安クオリティ",
    RANKING_PRESET_SUSTAINABLE_INCOME: "高配当の持続性",
    RANKING_PRESET_MIN_VOLATILITY: "低ボラ・安定",
    RANKING_PRESET_MOMENTUM: "モメンタム・トレンド",
    RANKING_PRESET_RISK_ADJUSTED: "リスク調整パフォーマンス",
    RANKING_PRESET_SMALL_GROWTH: "小型・成長探索",
    RANKING_PRESET_NISA_LONG_TERM: "NISA長期適合",
    RANKING_PRESET_DATA_CONFIDENCE: "データ信頼度優先",
    RANKING_PRESET_ETF_CORE_COST: "ETF低コスト・コア",
    RANKING_PRESET_ETF_INCOME: "ETFインカム・分散",
}
RANKING_WEIGHT_PRESETS: dict[str, dict[str, Decimal]] = {
    RANKING_PRESET_BALANCED: {
        "screening_score": Decimal("0.30"),
        "direction_net_score": Decimal("0.15"),
        "data_quality_score": Decimal("0.15"),
        "risk_signal_score": Decimal("0.15"),
        "database_fit_score": Decimal("0.10"),
        "metadata_confidence_score": Decimal("0.10"),
        "upside_signal_score": Decimal("0.05"),
    },
    RANKING_PRESET_FORECAST: {
        "direction_net_score": Decimal("0.35"),
        "screening_score": Decimal("0.25"),
        "data_quality_score": Decimal("0.15"),
        "risk_signal_score": Decimal("0.10"),
        "database_fit_score": Decimal("0.05"),
        "metadata_confidence_score": Decimal("0.10"),
    },
    RANKING_PRESET_UPSIDE_SIGNAL: {
        "direction_net_score": Decimal("0.35"),
        "screening_score": Decimal("0.25"),
        "risk_signal_score": Decimal("0.10"),
        "data_quality_score": Decimal("0.15"),
        "database_fit_score": Decimal("0.05"),
        "metadata_confidence_score": Decimal("0.10"),
    },
    RANKING_PRESET_QUALITY: {
        "screening_score": Decimal("0.25"),
        "direction_net_score": Decimal("0.10"),
        "data_quality_score": Decimal("0.40"),
        "risk_signal_score": Decimal("0.10"),
        "database_fit_score": Decimal("0.05"),
        "metadata_confidence_score": Decimal("0.10"),
    },
    RANKING_PRESET_RISK: {
        "screening_score": Decimal("0.25"),
        "direction_net_score": Decimal("0.10"),
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
        "direction_net_score": Decimal("0.05"),
    },
    RANKING_PRESET_GROWTH: {
        "screening_score": Decimal("0.25"),
        "direction_net_score": Decimal("0.25"),
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
        "direction_net_score": Decimal("0.05"),
    },
    RANKING_PRESET_STABILITY: {
        "risk_signal_score": Decimal("0.30"),
        "data_quality_score": Decimal("0.20"),
        "metadata_confidence_score": Decimal("0.15"),
        "screening_score": Decimal("0.15"),
        "database_fit_score": Decimal("0.10"),
        "direction_net_score": Decimal("0.10"),
    },
    RANKING_PRESET_TREND: {
        "screening_score": Decimal("0.30"),
        "direction_net_score": Decimal("0.30"),
        "data_quality_score": Decimal("0.10"),
        "risk_signal_score": Decimal("0.15"),
        "database_fit_score": Decimal("0.05"),
        "metadata_confidence_score": Decimal("0.10"),
    },
    RANKING_PRESET_MULTI_FACTOR: {
        "screening_score": Decimal("0.25"),
        "direction_net_score": Decimal("0.20"),
        "data_quality_score": Decimal("0.15"),
        "risk_signal_score": Decimal("0.15"),
        "database_fit_score": Decimal("0.10"),
        "metadata_confidence_score": Decimal("0.10"),
        "research_score": Decimal("0.05"),
    },
    RANKING_PRESET_QUALITY_GROWTH: {
        "database_fit_score": Decimal("0.25"),
        "direction_net_score": Decimal("0.25"),
        "screening_score": Decimal("0.20"),
        "risk_signal_score": Decimal("0.10"),
        "data_quality_score": Decimal("0.10"),
        "metadata_confidence_score": Decimal("0.10"),
    },
    RANKING_PRESET_QUALITY_VALUE: {
        "database_fit_score": Decimal("0.30"),
        "screening_score": Decimal("0.20"),
        "risk_signal_score": Decimal("0.20"),
        "data_quality_score": Decimal("0.15"),
        "metadata_confidence_score": Decimal("0.10"),
        "direction_net_score": Decimal("0.05"),
    },
    RANKING_PRESET_SUSTAINABLE_INCOME: {
        "database_fit_score": Decimal("0.30"),
        "risk_signal_score": Decimal("0.20"),
        "data_quality_score": Decimal("0.20"),
        "metadata_confidence_score": Decimal("0.15"),
        "screening_score": Decimal("0.10"),
        "direction_net_score": Decimal("0.05"),
    },
    RANKING_PRESET_MIN_VOLATILITY: {
        "risk_signal_score": Decimal("0.30"),
        "data_quality_score": Decimal("0.20"),
        "metadata_confidence_score": Decimal("0.15"),
        "screening_score": Decimal("0.15"),
        "database_fit_score": Decimal("0.10"),
        "direction_net_score": Decimal("0.10"),
    },
    RANKING_PRESET_MOMENTUM: {
        "screening_score": Decimal("0.30"),
        "direction_net_score": Decimal("0.30"),
        "risk_signal_score": Decimal("0.15"),
        "data_quality_score": Decimal("0.10"),
        "database_fit_score": Decimal("0.05"),
        "metadata_confidence_score": Decimal("0.10"),
    },
    RANKING_PRESET_RISK_ADJUSTED: {
        "screening_score": Decimal("0.20"),
        "direction_net_score": Decimal("0.10"),
        "data_quality_score": Decimal("0.15"),
        "risk_signal_score": Decimal("0.30"),
        "database_fit_score": Decimal("0.15"),
        "metadata_confidence_score": Decimal("0.10"),
    },
    RANKING_PRESET_SMALL_GROWTH: {
        "screening_score": Decimal("0.25"),
        "direction_net_score": Decimal("0.25"),
        "data_quality_score": Decimal("0.10"),
        "risk_signal_score": Decimal("0.10"),
        "database_fit_score": Decimal("0.25"),
        "metadata_confidence_score": Decimal("0.05"),
    },
    RANKING_PRESET_NISA_LONG_TERM: {
        "screening_score": Decimal("0.20"),
        "direction_net_score": Decimal("0.15"),
        "data_quality_score": Decimal("0.20"),
        "risk_signal_score": Decimal("0.20"),
        "database_fit_score": Decimal("0.15"),
        "metadata_confidence_score": Decimal("0.10"),
    },
    RANKING_PRESET_DATA_CONFIDENCE: {
        "screening_score": Decimal("0.10"),
        "direction_net_score": Decimal("0.05"),
        "data_quality_score": Decimal("0.35"),
        "risk_signal_score": Decimal("0.10"),
        "database_fit_score": Decimal("0.10"),
        "metadata_confidence_score": Decimal("0.30"),
    },
    RANKING_PRESET_ETF_CORE_COST: {
        "screening_score": Decimal("0.15"),
        "direction_net_score": Decimal("0.10"),
        "data_quality_score": Decimal("0.20"),
        "risk_signal_score": Decimal("0.15"),
        "database_fit_score": Decimal("0.30"),
        "metadata_confidence_score": Decimal("0.10"),
    },
    RANKING_PRESET_ETF_INCOME: {
        "screening_score": Decimal("0.15"),
        "direction_net_score": Decimal("0.10"),
        "data_quality_score": Decimal("0.20"),
        "risk_signal_score": Decimal("0.15"),
        "database_fit_score": Decimal("0.30"),
        "metadata_confidence_score": Decimal("0.10"),
    },
}
RANKING_PURPOSE_WEIGHT_PRESETS = {
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
}
RANKING_FETCH_LIMIT_FAST = "fast_100"
RANKING_FETCH_LIMIT_BALANCED = "balanced_300"
RANKING_FETCH_LIMIT_BROAD = "broad_800"
RANKING_FETCH_LIMIT_ALL = "all"
RANKING_FETCH_LIMIT_LABELS = {
    RANKING_FETCH_LIMIT_FAST: "高速: 上位100件",
    RANKING_FETCH_LIMIT_BALANCED: "標準: 上位300件",
    RANKING_FETCH_LIMIT_BROAD: "広め: 上位800件",
    RANKING_FETCH_LIMIT_ALL: "全件取得",
}
RANKING_FETCH_LIMIT_VALUES = {
    RANKING_FETCH_LIMIT_FAST: 100,
    RANKING_FETCH_LIMIT_BALANCED: 300,
    RANKING_FETCH_LIMIT_BROAD: 800,
    RANKING_FETCH_LIMIT_ALL: 0,
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
    "high_dividend": "配当利回り 3%以上",
    "dividend": "配当利回り 0%超〜3%未満",
    "none": "配当利回り 0%",
    "growth_dividend": "連続増配候補（metadata指定・利回り条件なし）",
}
RANKING_COMPLEXITY_LABELS = {
    "beginner": "初心者向け",
    "standard": "標準まで",
    "all": "上級者向けも含める",
}
RANKING_THEME_LABELS = {
    "all": "指定なし",
    "balanced": "分散/その他",
    "technology": "テクノロジー",
    "telecom": "通信（旧分類）",
    "communication": "通信・メディア",
    "semiconductor": "半導体",
    "financial": "金融",
    "consumer": "消費財・サービス",
    "healthcare": "ヘルスケア",
    "energy": "エネルギー",
    "automotive": "自動車",
    "trading": "商社",
    "industrial": "工業・資本財",
    "materials": "素材",
    "real_estate": "不動産",
    "utilities": "公益",
    "index": "インデックスETF",
    "bond": "債券",
    "reit": "REIT",
    "commodity": "コモディティ",
}
RANKING_MARKET_CAP_LABELS = {
    "all": "指定なし",
    "mega": "超大型（JP 10兆円以上 / US $200B以上）",
    "large": "大型（JP 1兆〜10兆円 / US $10B〜$200B）",
    "mid": "中型（JP 1,000億〜1兆円 / US $2B〜$10B）",
    "small": "小型（JP 100億〜1,000億円 / US $300M〜$2B）",
    "micro": "超小型（JP 100億円未満 / US $300M未満）",
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
    "dividend": "配当系指数",
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
RANKING_BETA_RISK_ALL = "all"
RANKING_BETA_RISK_LOW = "low"
RANKING_BETA_RISK_STANDARD_OR_LOWER = "standard_or_lower"
RANKING_BETA_RISK_STANDARD = "standard"
RANKING_BETA_RISK_HIGH = "high"
RANKING_BETA_RISK_LABELS = {
    RANKING_BETA_RISK_ALL: "指定なし（βで絞らない）",
    RANKING_BETA_RISK_LOW: "低変動のみ（β < 0.8）",
    RANKING_BETA_RISK_STANDARD_OR_LOWER: "標準以下（β <= 1.2）",
    RANKING_BETA_RISK_STANDARD: "標準のみ（0.8 <= β <= 1.2）",
    RANKING_BETA_RISK_HIGH: "高変動のみ（β > 1.2）",
}
RANKING_MANAGEMENT_STYLE_LABELS = {
    "all": "指定なし",
    "index": "インデックス",
    "active": "アクティブ",
}
RANKING_NISA_ELIGIBILITY_LABELS = {
    "all": "指定なし（NISAで絞らない）",
    "eligible": "NISA対象のみ（成長投資枠）",
    "none": "NISA対象外のみ",
}
RANKING_INSTALLMENT_LABELS = {
    "all": "指定なし",
    "true": "積立可能",
    "false": "積立不可",
}
RANKING_DETAIL_FILTER_LABELS = {
    "industry_or_sector": "業種/テーマ",
    "market_cap": "時価総額",
    "risk_band": "市場感応度（β）",
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
        "risk_band",
        "dividend_yield",
        "per",
        "pbr",
        "roe",
        "nisa_eligibility",
    ],
    (RANKING_REGION_US, RANKING_PRODUCT_STOCK): [
        "industry_or_sector",
        "market_cap",
        "risk_band",
        "dividend_yield",
        "per",
        "roe",
        "nisa_eligibility",
    ],
    (RANKING_REGION_ALL, RANKING_PRODUCT_STOCK): [
        "industry_or_sector",
        "market_cap",
        "risk_band",
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
    "market_data_ranking_purpose": RANKING_PURPOSE_MULTI_FACTOR,
    "market_data_ranking_fetch_limit": RANKING_FETCH_LIMIT_BALANCED,
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
RANKING_FILTER_HELP_TEXTS = {
    "industry_or_sector": (
        "業種やテーマで候補を絞ります。株式は主にsector/theme、ETFは指数・投資対象の"
        "分類を使います。"
    ),
    "market_cap": (
        "会社の規模感です。日本株は10兆円/1兆円/1,000億円/100億円、米国株は"
        "$200B/$10B/$2B/$300Mを境目に分類します。JPX規模区分由来の行は"
        "TOPIX Core30/Large70/Mid400/Smallなどを対応させています。"
    ),
    "risk_band": (
        "市場感応度（β）は、市場平均を1.0とした値動きの大きさの目安です。"
        "β 0.8未満は低変動、0.8〜1.2は市場並み、1.2超は高変動として扱います。"
        "SMAIでは主にYahoo metadataのbetaから分類しています。"
        "将来の値動きや損失を保証するものではありません。"
    ),
    "nisa_eligibility": (
        "NISA対象/対象外で絞ります。現在のランキング対象は株式・ETF中心です。"
        "株式候補は成長投資枠対象として整理済みなので、株式でNISA対象のみを"
        "選んでも件数が変わらない場合があります。ETFは対象/対象外が混在します。"
    ),
    "benchmark_index": (
        "ETFが主に連動を目指す指数や投資対象です。S&P 500、全世界、債券などの"
        "中身の違いを確認します。"
    ),
    "expense_ratio": (
        "ETFや投信の保有コストです。長期保有では低いほど手元に残るリターンに" "効きやすくなります。"
    ),
    "complexity": (
        "商品の分かりやすさの目安です。標準までを選ぶと、レバレッジ型など複雑な商品を"
        "避けやすくなります。"
    ),
    "dividend_category": (
        "配当利回りの帯で候補を絞ります。0%、0%超〜3%未満、3%以上を選べます。"
        "下の配当利回り(%)をONにして細かく指定する場合、この分類条件は使いません。"
        "連続増配候補は利回りではなく、curated metadataで指定された分類です。"
    ),
    "currency": "取引通貨で候補を絞ります。為替の影響も確認したい時に使います。",
    "dividend_yield": (
        "株価に対する年間配当の目安です。高いほど配当収入は大きく見えますが、"
        "極端に高い場合は減配や株価下落も確認します。"
    ),
    "per": (
        "利益に対して株価が何倍かを示します。低いほど割安に見えますが、"
        "成長鈍化や一時的な利益変動も確認します。"
    ),
    "pbr": (
        "純資産に対して株価が何倍かを示します。低いほど資産面では割安に見えますが、"
        "収益力もあわせて確認します。"
    ),
    "roe": (
        "自己資本でどれだけ利益を出しているかを示します。高いほど資本効率が良い目安ですが、"
        "一時的な上振れもあります。"
    ),
    "keyword": "ticker、会社名、テーマ、別名で候補を探します。",
    "period": (
        "ランキング計算に使う価格データの期間です。短期は直近の値動きや材料反応、"
        "中期は数週間のトレンド、長期は大きな上下動を含めた安定性の確認に使います。"
        "候補の絞り込み条件ではなく、スコア・Risk・方向感の見え方に影響します。"
    ),
}
RANKING_PURPOSE_HELP_TEXTS = {
    RANKING_PURPOSE_MULTI_FACTOR: (
        "Screening、方向感、Risk、Data Quality、条件適合度をバランスよく見ます。"
        "特定テーマに寄せず、まず深掘り候補を広く並べたい時の基準です。"
    ),
    RANKING_PURPOSE_QUALITY_GROWTH: (
        "ROE、上昇気配、Screening、Data Qualityを重視します。"
        "高PER/PBRは単純減点ではなく、成長期待と価格水準の釣り合いを確認する材料として扱います。"
    ),
    RANKING_PURPOSE_QUALITY_VALUE: (
        "PER/PBRの低さだけでなく、ROE、Data Quality、Riskも合わせて見ます。"
        "割安に見える理由が業績不安やデータ不足ではないかを確認するための並べ替えです。"
    ),
    RANKING_PURPOSE_SUSTAINABLE_INCOME: (
        "配当利回り、配当カテゴリ、Risk、PBR、Data Qualityを重視します。"
        "極端な高配当は魅力だけでなく、減配リスクの確認対象として扱います。"
    ),
    RANKING_PURPOSE_MIN_VOLATILITY: (
        "Risk signal、β分類、Data Quality、銘柄規模を重視します。"
        "上昇率よりも値動きの落ち着きと確認しやすさを優先する基準です。"
    ),
    RANKING_PURPOSE_MOMENTUM: (
        "取得期間の価格評価、方向感、Screeningを重視します。"
        "上昇基調でもRiskが強い候補は確認対象として扱い、追随リスクを見落としにくくします。"
    ),
    RANKING_PURPOSE_RISK_ADJUSTED: (
        "リターンだけでなくRisk signal、Data Quality、条件適合度を合わせて見ます。"
        "同じ上昇でも、値動きの荒さに対して見合うかを確認するための基準です。"
    ),
    RANKING_PURPOSE_SMALL_GROWTH: (
        "小型・中型の成長余地、ROE、Screening、上昇気配を重視します。"
        "変動率や流動性の不確実性が出やすいため、RiskとDB信頼度も確認します。"
    ),
    RANKING_PURPOSE_NISA_LONG_TERM: (
        "NISA適合、投資スタイル、Risk、Data Quality、ROEを重視します。"
        "長期保有候補として、制度適合と事業品質を一緒に確認する基準です。"
    ),
    RANKING_PURPOSE_DATA_CONFIDENCE: (
        "metadata source、更新日、Data Quality、欠損の少なさを最優先します。"
        "判断前に、まず根拠がそろった銘柄から確認したい時に使います。"
    ),
    RANKING_PURPOSE_ETF_CORE_COST: (
        "経費率、連動指数、複雑性、NISA適合、DB信頼度を重視します。"
        "長期保有の土台になりやすいETF候補を整理する基準です。"
    ),
    RANKING_PURPOSE_ETF_INCOME: (
        "ETFの利回り、経費率、指数、通貨、複雑性、Data Qualityを重視します。"
        "インカム候補でもコストと分散性を同時に確認します。"
    ),
    RANKING_PURPOSE_DIVIDEND: (
        "旧来の配当重視です。配当利回りと条件適合度を中心に比較します。"
        "新しい配当評価には「高配当の持続性」も使えます。"
    ),
    RANKING_PURPOSE_GROWTH: (
        "旧来の成長重視です。方向感とROE寄りの条件適合度を中心に比較します。"
        "より品質を見たい場合は「成長クオリティ」を使います。"
    ),
    RANKING_PURPOSE_VALUE: (
        "旧来の割安重視です。PER/PBR寄りの条件適合度を中心に比較します。"
        "割安の質まで確認する場合は「割安クオリティ」を使います。"
    ),
    RANKING_PURPOSE_STABILITY: (
        "旧来の安定重視です。RiskとData Qualityを中心に比較します。"
        "より低変動に寄せる場合は「低ボラ・安定」を使います。"
    ),
    RANKING_PURPOSE_TREND: (
        "旧来のトレンド重視です。方向感と直近の価格評価を中心に比較します。"
        "外部ファクターのMomentumに近い見方は「モメンタム・トレンド」を使います。"
    ),
    RANKING_PURPOSE_UPSIDE_SIGNAL: (
        "上昇気配、下向きシグナルの低さ、Screening、Data Qualityを重視します。"
        "買い推奨ではなく、短期的に深掘りする候補を整理するための基準です。"
    ),
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


def ranking_purpose_options(product_type: str = RANKING_PRODUCT_STOCK) -> list[str]:
    """Return purpose options in the order users are most likely to scan."""

    preferred_order = (
        RANKING_PURPOSE_ETF_DISPLAY_ORDER
        if product_type == RANKING_PRODUCT_ETF
        else RANKING_PURPOSE_DISPLAY_ORDER
    )
    ordered = [purpose for purpose in preferred_order if purpose in RANKING_PURPOSE_LABELS]
    ordered.extend(purpose for purpose in RANKING_PURPOSE_LABELS if purpose not in ordered)
    return ordered


def ranking_purpose_help(purpose: str) -> str:
    return RANKING_PURPOSE_HELP_TEXTS.get(
        purpose,
        "取得後の表示順を決める評価軸です。銘柄DBと取得期間の価格評価を合わせて並べ替えます。",
    )


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
        "risk_band",
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
    symbol_rows_by_symbol: dict[str, dict[str, str]] | None = None,
) -> list[dict[str, str]]:
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


def _ensure_ranking_signal_fields(row: dict[str, str]) -> dict[str, str]:
    forecast_agreement = _optional_decimal_from_text(row.get("forecast_agreement_score", ""))
    neutral_direction = forecast_agreement if forecast_agreement is not None else Decimal("50")
    direction_net = _optional_decimal_from_text(row.get("direction_net_score", ""))
    upside = _optional_decimal_from_text(row.get("upside_signal_score", ""))
    downside = _optional_decimal_from_text(row.get("downside_signal_score", ""))
    enriched = dict(row)
    if not enriched.get("direction_net_score"):
        enriched["direction_net_score"] = _format_score(direction_net or neutral_direction)
    if not enriched.get("upside_signal_score"):
        enriched["upside_signal_score"] = _format_score(upside or neutral_direction)
    if not enriched.get("downside_signal_score"):
        enriched["downside_signal_score"] = _format_score(downside or Decimal("50"))
    if not enriched.get("direction_signal_label"):
        enriched["direction_signal_label"] = "UNKNOWN"
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
    return enriched


def _ranking_component_score(row: dict[str, str], field: str) -> Decimal:
    value = _optional_decimal_from_text(row.get(field, ""))
    if value is not None:
        return value
    if field == "research_score":
        return Decimal("50")
    if field in {"direction_net_score", "upside_signal_score"}:
        return _optional_decimal_from_text(row.get("forecast_agreement_score", "")) or Decimal("50")
    if field == "downside_signal_score":
        return Decimal("50")
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
    available = sum(1 for field in fields if str(symbol_row.get(field, "")).strip())
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
    dividend_yield = _optional_decimal_from_text(
        symbol_row.get("dividend_yield_pct", "")
    ) or Decimal("0")
    per = _optional_decimal_from_text(symbol_row.get("per", ""))
    pbr = _optional_decimal_from_text(symbol_row.get("pbr", ""))
    roe = _optional_decimal_from_text(symbol_row.get("roe_pct", "")) or Decimal("0")
    risk_band = symbol_row.get("risk_band", "")
    market_cap_tier = symbol_row.get("market_cap_tier", "")
    bonus = Decimal("0")
    if preset in {RANKING_PRESET_INCOME, RANKING_PRESET_SUSTAINABLE_INCOME}:
        if dividend_yield >= Decimal("3"):
            bonus += Decimal("25")
        elif dividend_yield > Decimal("0"):
            bonus += Decimal("10")
        if pbr is not None and pbr <= Decimal("2"):
            bonus += Decimal("5")
        if risk_band in {"LOW", "MEDIUM"}:
            bonus += Decimal("10")
        if preset == RANKING_PRESET_SUSTAINABLE_INCOME and dividend_yield <= Decimal("8"):
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
        if Decimal("0") < dividend_yield <= Decimal("5"):
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
    dividend_yield = _optional_decimal_from_text(
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
        "metadata_source": row.get("metadata_source", ""),
        "metadata_as_of": row.get("metadata_as_of", ""),
        "metadata_updated_at": row.get("metadata_updated_at", ""),
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


def _optional_decimal_from_text(value: str) -> Decimal | None:
    if value == "":
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None
