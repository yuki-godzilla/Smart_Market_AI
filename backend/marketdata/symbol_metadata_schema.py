from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

METADATA_TIER_CORE = "core"
METADATA_TIER_RANKING_FILTER = "ranking_filter"
METADATA_TIER_FUND_EXTENDED = "fund_extended"
METADATA_TIER_OPERATIONAL = "operational"

METADATA_STORAGE_SYMBOL_UNIVERSE = "symbol_universe"
METADATA_STORAGE_FUTURE_FUND_METADATA = "future_fund_metadata"


@dataclass(frozen=True)
class MetadataField:
    """Field policy for symbol and fund metadata."""

    key: str
    label: str
    tier: str
    storage: str
    required_column: bool = False
    required_value: bool = False
    source_required: bool = False
    freshness_days: int | None = None
    value_type: str = "text"
    allowed_values: frozenset[str] = frozenset()
    minimum: Decimal | None = None
    maximum: Decimal | None = None


SYMBOL_METADATA_FIELDS: tuple[MetadataField, ...] = (
    MetadataField(
        key="symbol",
        label="銘柄コード",
        tier=METADATA_TIER_CORE,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        required_column=True,
        required_value=True,
    ),
    MetadataField(
        key="name",
        label="銘柄名",
        tier=METADATA_TIER_CORE,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        required_column=True,
        required_value=True,
    ),
    MetadataField(
        key="market",
        label="市場/地域",
        tier=METADATA_TIER_CORE,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        required_column=True,
        required_value=True,
        allowed_values=frozenset(
            {
                "jp",
                "us",
                "developed_ex_us",
                "emerging",
                "europe",
                "china",
                "hong_kong",
                "korea",
                "vietnam",
                "indonesia",
                "singapore",
                "thailand",
                "malaysia",
                "russia",
                "india",
                "global",
                "other_global",
            }
        ),
    ),
    MetadataField(
        key="asset_type",
        label="商品",
        tier=METADATA_TIER_CORE,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        required_column=True,
        required_value=True,
        allowed_values=frozenset(
            {
                "adr",
                "bond",
                "cfd",
                "commodity",
                "crypto",
                "etf",
                "fund",
                "futures",
                "fx",
                "investment_trust",
                "mmf",
                "mutual_fund",
                "option",
                "reit",
                "stock",
            }
        ),
    ),
    MetadataField(
        key="currency",
        label="通貨",
        tier=METADATA_TIER_CORE,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        required_column=True,
        required_value=True,
        allowed_values=frozenset(
            {
                "JPY",
                "USD",
                "EUR",
                "GBP",
                "CHF",
                "CAD",
                "AUD",
                "HKD",
                "CNY",
                "KRW",
                "VND",
                "IDR",
                "SGD",
                "THB",
                "MYR",
                "INR",
            }
        ),
    ),
    MetadataField(
        key="country",
        label="国・地域",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
    ),
    MetadataField(
        key="exchange",
        label="取引所",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
    ),
    MetadataField(
        key="local_symbol",
        label="現地銘柄コード",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
    ),
    MetadataField(
        key="primary_listing_country",
        label="主上場国",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
    ),
    MetadataField(
        key="trading_currency",
        label="取引通貨",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        allowed_values=frozenset({"JPY", "USD", "HKD", "KRW", "VND", "IDR", "SGD", "THB", "MYR", "CNY", "unknown"}),
    ),
    MetadataField(
        key="settlement_currency",
        label="決済通貨",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        allowed_values=frozenset({"JPY", "USD", "HKD", "KRW", "VND", "IDR", "SGD", "THB", "MYR", "CNY", "unknown"}),
    ),
    MetadataField(
        key="quote_currency",
        label="価格表示通貨",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        allowed_values=frozenset({"JPY", "USD", "HKD", "KRW", "VND", "IDR", "SGD", "THB", "MYR", "CNY", "unknown"}),
    ),
    MetadataField(
        key="fx_pair_to_jpy",
        label="円換算FXペア",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        allowed_values=frozenset({"", "USDJPY", "HKDJPY", "KRWJPY", "VNDJPY", "IDRJPY", "SGDJPY", "THBJPY", "MYRJPY", "CNYJPY"}),
    ),
    MetadataField(
        key="foreign_market_group",
        label="外国株市場グループ",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        allowed_values=frozenset({"japan", "us", "china_hk", "korea", "asean", "other_global", "not_applicable", "unknown"}),
    ),
    MetadataField(
        key="country_risk_band",
        label="カントリーリスク",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        allowed_values=frozenset({"LOW", "MEDIUM", "HIGH", "VERY_HIGH", "unknown", "not_applicable"}),
    ),
    MetadataField(
        key="liquidity_tier",
        label="流動性ランク",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        allowed_values=frozenset({"high", "medium", "low", "unknown", "not_applicable"}),
    ),
    MetadataField(
        key="foreign_data_quality",
        label="外国株データ品質",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        allowed_values=frozenset({"OK", "WARN", "BLOCK", "unknown", "not_applicable"}),
    ),
    MetadataField(
        key="foreign_data_quality_reasons",
        label="外国株データ品質理由",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        value_type="csv_tags",
    ),
    MetadataField(
        key="sbi_foreign_tradability",
        label="SBI外国株取扱",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        allowed_values=frozenset({"tradable", "not_tradable", "unknown", "not_applicable"}),
    ),
    MetadataField(
        key="sbi_foreign_tradability_as_of",
        label="SBI外国株取扱確認日",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        value_type="date",
    ),
    MetadataField(
        key="sbi_foreign_tradability_source",
        label="SBI外国株取扱確認元",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
    ),
    MetadataField(
        key="broker",
        label="取扱会社",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        required_column=True,
        allowed_values=frozenset({"sbi_securities", "unknown"}),
    ),
    MetadataField(
        key="tradability",
        label="取扱状態",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        required_column=True,
        allowed_values=frozenset({"tradable", "not_tradable", "unknown"}),
    ),
    MetadataField(
        key="nisa_category",
        label="NISA区分",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        required_column=True,
        allowed_values=frozenset({"growth", "tsumitate", "both", "none", "unknown"}),
    ),
    MetadataField(
        key="investment_style",
        label="投資スタイル",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        required_column=True,
        allowed_values=frozenset({"lump_sum", "recurring", "both", "unknown"}),
    ),
    MetadataField(
        key="is_sbi_supported",
        label="SBI取扱対象",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        required_column=True,
        value_type="bool",
        allowed_values=frozenset({"true", "false", "unknown"}),
    ),
    MetadataField(
        key="is_active",
        label="有効銘柄",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        required_column=True,
        value_type="bool",
        allowed_values=frozenset({"true", "false", "unknown"}),
    ),
    MetadataField(
        key="is_leveraged",
        label="レバレッジ商品",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        required_column=True,
        value_type="bool",
        allowed_values=frozenset({"true", "false", "unknown"}),
    ),
    MetadataField(
        key="is_inverse",
        label="インバース商品",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        required_column=True,
        value_type="bool",
        allowed_values=frozenset({"true", "false", "unknown"}),
    ),
    MetadataField(
        key="theme",
        label="テーマ",
        tier=METADATA_TIER_CORE,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        required_column=True,
        allowed_values=frozenset(
            {
                "automotive",
                "balanced",
                "bank",
                "bond",
                "commodity",
                "communication",
                "consumer",
                "energy",
                "financial",
                "healthcare",
                "index",
                "industrial",
                "insurance",
                "materials",
                "real_estate",
                "reit",
                "semiconductor",
                "technology",
                "telecom",
                "trading",
                "utilities",
            }
        ),
    ),
    MetadataField(
        key="sector",
        label="業種/セクター",
        tier=METADATA_TIER_CORE,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        required_column=True,
        allowed_values=frozenset(
            {
                "communication",
                "consumer",
                "energy",
                "financial",
                "healthcare",
                "index",
                "industrial",
                "materials",
                "real_estate",
                "technology",
                "utilities",
            }
        ),
    ),
    MetadataField(
        key="sector_gics",
        label="GICSセクター",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
    ),
    MetadataField(
        key="industry_gics",
        label="GICS業種",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
    ),
    MetadataField(
        key="subindustry_gics",
        label="GICSサブ業種",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
    ),
    MetadataField(
        key="tse_33_industry",
        label="東証33業種",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
    ),
    MetadataField(
        key="topix_17",
        label="TOPIX-17業種",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
    ),
    MetadataField(
        key="smai_theme_tags",
        label="SMAI投資テーマ",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        value_type="csv_tags",
    ),
    MetadataField(
        key="theme_confidence",
        label="テーマ分類信頼度",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        value_type="decimal",
        minimum=Decimal("0"),
        maximum=Decimal("1"),
    ),
    MetadataField(
        key="theme_source",
        label="テーマ分類出所",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
    ),
    MetadataField(
        key="aliases",
        label="検索別名",
        tier=METADATA_TIER_CORE,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        required_column=True,
    ),
    MetadataField(
        key="yahoo_symbol",
        label="Yahoo用銘柄コード",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
    ),
    MetadataField(
        key="yahoo_symbol_status",
        label="Yahoo銘柄コード確認状態",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        allowed_values=frozenset({"confirmed", "generated", "requires_review", "unavailable", "stale"}),
    ),
    MetadataField(
        key="yahoo_symbol_checked_at",
        label="Yahoo銘柄コード確認日",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
    ),
    MetadataField(
        key="yahoo_symbol_note",
        label="Yahoo銘柄コードメモ",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
    ),
    MetadataField(
        key="dividend_category",
        label="配当カテゴリ",
        tier=METADATA_TIER_RANKING_FILTER,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        required_column=True,
        source_required=True,
        freshness_days=180,
        allowed_values=frozenset({"dividend", "growth_dividend", "high_dividend", "none"}),
    ),
    MetadataField(
        key="dividend_yield_pct",
        label="配当利回り",
        tier=METADATA_TIER_RANKING_FILTER,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        required_column=True,
        source_required=True,
        freshness_days=90,
        value_type="decimal",
        minimum=Decimal("0"),
    ),
    MetadataField(
        key="market_cap_tier",
        label="時価総額",
        tier=METADATA_TIER_RANKING_FILTER,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        required_column=True,
        source_required=True,
        freshness_days=180,
        allowed_values=frozenset({"mega", "large", "mid", "small", "micro"}),
    ),
    MetadataField(
        key="market_cap",
        label="時価総額（取得値）",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        source_required=True,
        freshness_days=90,
        value_type="decimal",
        minimum=Decimal("0"),
    ),
    MetadataField(
        key="index_family",
        label="指数",
        tier=METADATA_TIER_RANKING_FILTER,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        required_column=True,
        allowed_values=frozenset(
            {
                "acwi",
                "active",
                "bond",
                "china",
                "commodity",
                "currency",
                "dividend",
                "dow_jones",
                "emerging",
                "india",
                "japan_equity",
                "jpx_nikkei400",
                "msci_world",
                "nasdaq100",
                "nikkei225",
                "reit",
                "sector",
                "singapore_equity",
                "single_stock",
                "small_us",
                "sp500",
                "style_factor",
                "topix",
                "total_us",
            }
        ),
    ),
    MetadataField(
        key="expense_ratio_pct",
        label="信託報酬/経費率",
        tier=METADATA_TIER_RANKING_FILTER,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        required_column=True,
        source_required=True,
        freshness_days=180,
        value_type="decimal",
        minimum=Decimal("0"),
    ),
    MetadataField(
        key="complexity",
        label="複雑さ",
        tier=METADATA_TIER_RANKING_FILTER,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        required_column=True,
        allowed_values=frozenset(
            {
                "beginner",
                "standard",
                "advanced",
                "currency_select",
                "etn",
                "inverse",
                "leveraged",
                "thematic",
            }
        ),
    ),
    MetadataField(
        key="tags",
        label="タグ",
        tier=METADATA_TIER_RANKING_FILTER,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        required_column=True,
        value_type="csv_tags",
        allowed_values=frozenset(
            {
                "automotive",
                "balanced",
                "bank",
                "bond",
                "commodity",
                "communication",
                "consumer",
                "dividend",
                "energy",
                "financial",
                "growth",
                "healthcare",
                "high_dividend",
                "industrial",
                "index",
                "installment",
                "insurance",
                "lower_risk",
                "low_cost",
                "materials",
                "quality",
                "real_estate",
                "reit",
                "semiconductor",
                "technology",
                "trading",
                "utilities",
                "value",
            }
        ),
    ),
    MetadataField(
        key="per",
        label="PER",
        tier=METADATA_TIER_RANKING_FILTER,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        required_column=True,
        source_required=True,
        freshness_days=90,
        value_type="decimal",
    ),
    MetadataField(
        key="pbr",
        label="PBR",
        tier=METADATA_TIER_RANKING_FILTER,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        required_column=True,
        source_required=True,
        freshness_days=90,
        value_type="decimal",
        minimum=Decimal("0"),
    ),
    MetadataField(
        key="roe_pct",
        label="ROE",
        tier=METADATA_TIER_RANKING_FILTER,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        required_column=True,
        source_required=True,
        freshness_days=180,
        value_type="decimal",
    ),
    MetadataField(
        key="consensus_rating",
        label="コンセンサス",
        tier=METADATA_TIER_RANKING_FILTER,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        required_column=True,
        source_required=True,
        freshness_days=30,
        value_type="decimal",
        minimum=Decimal("1"),
        maximum=Decimal("5"),
    ),
    MetadataField(
        key="forecast_agreement",
        label="予測一致",
        tier=METADATA_TIER_RANKING_FILTER,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        required_column=True,
        allowed_values=frozenset({"HIGH", "MEDIUM", "LOW"}),
    ),
    MetadataField(
        key="data_quality",
        label="データ品質",
        tier=METADATA_TIER_RANKING_FILTER,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        required_column=True,
        allowed_values=frozenset({"OK", "WARN", "BLOCK"}),
    ),
    MetadataField(
        key="data_quality_reasons",
        label="データ品質理由",
        tier=METADATA_TIER_RANKING_FILTER,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
    ),
    MetadataField(
        key="risk_band",
        label="リスク",
        tier=METADATA_TIER_RANKING_FILTER,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        required_column=True,
        source_required=True,
        freshness_days=90,
        allowed_values=frozenset({"LOW", "MEDIUM", "HIGH"}),
    ),
    MetadataField(
        key="sbi_tradability_status",
        label="SBI取扱確認状態",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        allowed_values=frozenset({"confirmed", "estimated", "unknown", "not_supported"}),
    ),
    MetadataField(
        key="sbi_tradability_verified",
        label="SBI取扱確認済み",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        value_type="bool",
        allowed_values=frozenset({"true", "false", "unknown"}),
    ),
    MetadataField(
        key="sbi_tradability_as_of",
        label="SBI取扱確認日",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        value_type="date",
    ),
    MetadataField(
        key="sbi_tradability_source",
        label="SBI取扱確認元",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
    ),
    MetadataField(
        key="nisa_growth_status",
        label="NISA成長投資枠確認状態",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        allowed_values=frozenset({"confirmed", "estimated", "unknown", "not_supported"}),
    ),
    MetadataField(
        key="nisa_growth_verified",
        label="NISA成長投資枠確認済み",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        value_type="bool",
        allowed_values=frozenset({"true", "false", "unknown"}),
    ),
    MetadataField(
        key="nisa_growth_as_of",
        label="NISA成長投資枠確認日",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        value_type="date",
    ),
    MetadataField(
        key="nisa_growth_source",
        label="NISA成長投資枠確認元",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
    ),
    MetadataField(
        key="nisa_tsumitate_status",
        label="NISAつみたて投資枠確認状態",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        allowed_values=frozenset({"confirmed", "estimated", "unknown", "not_supported"}),
    ),
    MetadataField(
        key="nisa_tsumitate_verified",
        label="NISAつみたて投資枠確認済み",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        value_type="bool",
        allowed_values=frozenset({"true", "false", "unknown"}),
    ),
    MetadataField(
        key="nisa_tsumitate_as_of",
        label="NISAつみたて投資枠確認日",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        value_type="date",
    ),
    MetadataField(
        key="nisa_tsumitate_source",
        label="NISAつみたて投資枠確認元",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
    ),
    MetadataField(
        key="metadata_source",
        label="metadata出所",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        allowed_values=frozenset(
            {
                "curated_csv",
                "csv",
                "alpha_vantage",
                "eodhd",
                "fmp",
                "fsa",
                "imaj",
                "jpx",
                "jpx_listed_stock",
                "jpx_nisa_growth",
                "jpx_reit",
                "manual",
                "mutual_fund_seed",
                "polygon",
                "sbi_us_etf_removed",
                "sbi_us_etf",
                "sbi_overseas_etf",
                "sbi_us_stock_removed",
                "sbi_us_stock",
                "sbi_foreign_stock",
                "sbi_hk_stock",
                "sbi_korea_stock",
                "sbi_vietnam_stock",
                "sbi_indonesia_stock",
                "sbi_singapore_stock",
                "sbi_thailand_stock",
                "sbi_malaysia_stock",
                "unknown",
                "yahoo",
            }
        ),
    ),
    MetadataField(
        key="metadata_as_of",
        label="metadata基準日",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        value_type="date",
    ),
    MetadataField(
        key="metadata_updated_at",
        label="metadata更新日時",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        value_type="datetime",
    ),
    MetadataField(
        key="trust_fee_pct",
        label="信託報酬",
        tier=METADATA_TIER_FUND_EXTENDED,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        source_required=True,
        freshness_days=180,
        value_type="decimal",
        minimum=Decimal("0"),
    ),
    MetadataField(
        key="aum",
        label="純資産総額",
        tier=METADATA_TIER_FUND_EXTENDED,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        source_required=True,
        freshness_days=30,
        value_type="decimal",
        minimum=Decimal("0"),
    ),
    MetadataField(
        key="average_volume",
        label="平均出来高",
        tier=METADATA_TIER_FUND_EXTENDED,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        source_required=True,
        freshness_days=30,
        value_type="decimal",
        minimum=Decimal("0"),
    ),
    MetadataField(
        key="asset_class",
        label="資産クラス",
        tier=METADATA_TIER_FUND_EXTENDED,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
    ),
    MetadataField(
        key="region_exposure",
        label="投資地域",
        tier=METADATA_TIER_FUND_EXTENDED,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
    ),
    MetadataField(
        key="is_hedged",
        label="為替ヘッジ",
        tier=METADATA_TIER_FUND_EXTENDED,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        value_type="bool",
        allowed_values=frozenset({"true", "false", "unknown"}),
    ),
    MetadataField(
        key="nisa_tsumitate_eligible",
        label="NISAつみたて投資枠",
        tier=METADATA_TIER_FUND_EXTENDED,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        source_required=True,
        freshness_days=180,
        value_type="bool",
        allowed_values=frozenset({"true", "false", "unknown"}),
    ),
    MetadataField(
        key="nisa_growth_eligible",
        label="NISA成長投資枠",
        tier=METADATA_TIER_FUND_EXTENDED,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        source_required=True,
        freshness_days=180,
        value_type="bool",
        allowed_values=frozenset({"true", "false", "unknown"}),
    ),
    MetadataField(
        key="installment_available",
        label="積立可否",
        tier=METADATA_TIER_FUND_EXTENDED,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        source_required=True,
        freshness_days=180,
        value_type="bool",
        allowed_values=frozenset({"true", "false", "unknown"}),
    ),
    MetadataField(
        key="installment_source",
        label="積立可否の出所",
        tier=METADATA_TIER_FUND_EXTENDED,
        storage=METADATA_STORAGE_FUTURE_FUND_METADATA,
    ),
    MetadataField(
        key="management_style",
        label="運用方式",
        tier=METADATA_TIER_FUND_EXTENDED,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        allowed_values=frozenset({"index", "active"}),
    ),
    MetadataField(
        key="distribution_policy",
        label="分配方針",
        tier=METADATA_TIER_FUND_EXTENDED,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        allowed_values=frozenset(
            {"none", "monthly", "quarterly", "semiannual", "annual", "irregular"}
        ),
    ),
)

METRIC_PROVENANCE_BASE_FIELDS: tuple[str, ...] = (
    "per",
    "pbr",
    "roe_pct",
    "dividend_yield_pct",
    "market_cap_tier",
    "market_cap",
    "expense_ratio_pct",
    "aum",
    "average_volume",
)

SYMBOL_METADATA_FIELDS += tuple(
    MetadataField(
        key=f"{metric}_{suffix}",
        label=f"{metric} {suffix}",
        tier=METADATA_TIER_OPERATIONAL,
        storage=METADATA_STORAGE_SYMBOL_UNIVERSE,
        value_type="date" if suffix == "as_of" else "text",
        allowed_values=(
            frozenset({"confirmed", "derived", "estimated", "unknown", "stale", "missing"})
            if suffix == "quality"
            else frozenset()
        ),
    )
    for metric in METRIC_PROVENANCE_BASE_FIELDS
    for suffix in ("source", "as_of", "quality")
)


def metadata_field_by_key(key: str) -> MetadataField | None:
    return METADATA_FIELD_BY_KEY.get(key)


def metadata_fields_by_tier(tier: str) -> list[MetadataField]:
    return [field for field in SYMBOL_METADATA_FIELDS if field.tier == tier]


def metadata_fields_by_storage(storage: str) -> list[MetadataField]:
    return [field for field in SYMBOL_METADATA_FIELDS if field.storage == storage]


def symbol_universe_required_columns() -> tuple[str, ...]:
    return tuple(
        field.key
        for field in SYMBOL_METADATA_FIELDS
        if field.storage == METADATA_STORAGE_SYMBOL_UNIVERSE and field.required_column
    )


def symbol_universe_optional_columns() -> tuple[str, ...]:
    return tuple(
        field.key
        for field in SYMBOL_METADATA_FIELDS
        if field.storage == METADATA_STORAGE_SYMBOL_UNIVERSE and not field.required_column
    )


def symbol_universe_required_value_columns() -> tuple[str, ...]:
    return tuple(
        field.key
        for field in SYMBOL_METADATA_FIELDS
        if field.storage == METADATA_STORAGE_SYMBOL_UNIVERSE and field.required_value
    )


def symbol_universe_metadata_value_columns() -> tuple[str, ...]:
    return ("metadata_source", "metadata_as_of")


def symbol_universe_allowed_values() -> dict[str, set[str]]:
    return {
        field.key: set(field.allowed_values)
        for field in metadata_fields_by_storage(METADATA_STORAGE_SYMBOL_UNIVERSE)
        if field.allowed_values and field.value_type != "csv_tags"
    }


def symbol_universe_allowed_tags() -> set[str]:
    field = metadata_field_by_key("tags")
    return set(field.allowed_values) if field else set()


def symbol_universe_decimal_columns() -> tuple[str, ...]:
    return tuple(
        field.key
        for field in metadata_fields_by_storage(METADATA_STORAGE_SYMBOL_UNIVERSE)
        if field.value_type == "decimal"
    )


def symbol_universe_source_required_fields() -> tuple[MetadataField, ...]:
    return tuple(
        field
        for field in metadata_fields_by_storage(METADATA_STORAGE_SYMBOL_UNIVERSE)
        if field.source_required
    )


METADATA_FIELD_BY_KEY = {field.key: field for field in SYMBOL_METADATA_FIELDS}
