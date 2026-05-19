from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping, Sequence

JPX_LISTED_STOCK_SOURCE_FIELDNAMES = [
    "code",
    "security_name",
    "market",
    "asset_type",
    "currency",
    "theme",
    "sector",
    "tags",
    "aliases",
    "source_market_segment",
    "source_industry_33",
    "source_industry_17",
    "source_scale_category",
]

SBI_US_STOCK_SOURCE_FIELDNAMES = [
    "symbol",
    "name",
    "market",
    "asset_type",
    "currency",
    "sector",
    "theme",
    "aliases",
    "dividend_category",
    "dividend_yield_pct",
    "market_cap_tier",
    "tags",
    "per",
    "pbr",
    "roe_pct",
    "consensus_rating",
    "forecast_agreement",
    "data_quality",
    "risk_band",
]

SBI_US_ETF_SOURCE_FIELDNAMES = [
    "symbol",
    "name",
    "market",
    "asset_type",
    "currency",
    "index_family",
    "expense_ratio_pct",
    "complexity",
    "tags",
    "nisa_category",
    "investment_style",
    "is_leveraged",
    "is_inverse",
    "aliases",
]

_JPX_CODE_PATTERN = re.compile(r"^[0-9A-Z]{4}$")
_US_SYMBOL_PATTERN = re.compile(r"^[A-Z][A-Z0-9-]{0,14}$")
_JPX_STOCK_MARKET_MARKERS = ("グロース", "スタンダード", "プライム")
_JPX_NON_STOCK_MARKERS = (
    "ETF",
    "ETN",
    "REIT",
    "インフラファンド",
    "カントリーファンド",
    "ベンチャーファンド",
    "優先出資",
    "出資証券",
)

_CODE_ALIASES = ("code", "security_code", "local_code", "コード", "銘柄コード")
_NAME_ALIASES = ("security_name", "name", "company_name", "銘柄名", "名称")
_MARKET_SEGMENT_ALIASES = (
    "market_segment",
    "market_category",
    "market_product_category",
    "市場・商品区分",
    "市場区分",
)
_INDUSTRY_33_ALIASES = (
    "industry_33",
    "industry33",
    "33_industry",
    "33業種区分",
    "33業種",
)
_INDUSTRY_17_ALIASES = (
    "industry_17",
    "industry17",
    "17_industry",
    "17業種区分",
    "17業種",
)
_SCALE_ALIASES = ("scale_category", "size_category", "規模区分", "規模")
_SYMBOL_ALIASES = (
    "symbol",
    "ticker",
    "code",
    "local_code",
    "銘柄コード",
    "ティッカー",
    "シンボル",
    "コード",
)
_US_NAME_ALIASES = (
    "name",
    "security_name",
    "company_name",
    "english_name",
    "銘柄名",
    "名称",
    "英文名称",
)
_SECTOR_ALIASES = ("sector", "industry", "gics_sector", "セクター", "業種")
_TAGS_ALIASES = ("tags", "tag", "investment_style_tags", "タグ")
_DIVIDEND_CATEGORY_ALIASES = ("dividend_category", "配当カテゴリ")
_DIVIDEND_YIELD_ALIASES = ("dividend_yield_pct", "dividend_yield", "配当利回り")
_MARKET_CAP_TIER_ALIASES = ("market_cap_tier", "market_cap_size", "時価総額")
_PER_ALIASES = ("per", "pe_ratio", "PER")
_PBR_ALIASES = ("pbr", "price_to_book", "PBR")
_ROE_ALIASES = ("roe_pct", "roe", "ROE")
_CONSENSUS_RATING_ALIASES = ("consensus_rating", "rating", "コンセンサス")
_FORECAST_AGREEMENT_ALIASES = ("forecast_agreement", "予測一致")
_DATA_QUALITY_ALIASES = ("data_quality", "データ品質")
_RISK_BAND_ALIASES = ("risk_band", "risk", "リスク")
_INDEX_FAMILY_ALIASES = (
    "index_family",
    "underlying_index",
    "benchmark",
    "benchmark_index",
    "連動指数",
    "指数",
)
_EXPENSE_RATIO_ALIASES = (
    "expense_ratio_pct",
    "expense_ratio",
    "trust_fee_pct",
    "経費率",
    "信託報酬",
)
_COMPLEXITY_ALIASES = ("complexity", "leverage_type", "複雑さ")
_NISA_CATEGORY_ALIASES = ("nisa_category", "nisa_type", "NISA区分")
_INVESTMENT_STYLE_ALIASES = ("investment_style", "投資スタイル")
_IS_LEVERAGED_ALIASES = ("is_leveraged", "leveraged", "レバレッジ")
_IS_INVERSE_ALIASES = ("is_inverse", "inverse", "インバース")

_INDUSTRY_THEME_SECTOR_MAP = {
    "水産・農林業": ("consumer", "consumer"),
    "鉱業": ("energy", "energy"),
    "建設業": ("balanced", "industrial"),
    "建設・資材": ("balanced", "industrial"),
    "食料品": ("consumer", "consumer"),
    "繊維製品": ("consumer", "consumer"),
    "パルプ・紙": ("balanced", "materials"),
    "化学": ("balanced", "materials"),
    "素材・化学": ("balanced", "materials"),
    "医薬品": ("healthcare", "healthcare"),
    "石油・石炭製品": ("energy", "energy"),
    "ゴム製品": ("automotive", "materials"),
    "ガラス・土石製品": ("balanced", "materials"),
    "鉄鋼": ("balanced", "materials"),
    "鉄鋼・非鉄": ("balanced", "materials"),
    "非鉄金属": ("balanced", "materials"),
    "金属製品": ("balanced", "materials"),
    "機械": ("balanced", "industrial"),
    "電気機器": ("technology", "technology"),
    "電機・精密": ("technology", "technology"),
    "輸送用機器": ("automotive", "industrial"),
    "自動車・輸送機": ("automotive", "industrial"),
    "精密機器": ("technology", "technology"),
    "その他製品": ("consumer", "consumer"),
    "電気・ガス業": ("energy", "utilities"),
    "電力・ガス": ("energy", "utilities"),
    "陸運業": ("balanced", "industrial"),
    "海運業": ("balanced", "industrial"),
    "空運業": ("balanced", "industrial"),
    "倉庫・運輸関連業": ("balanced", "industrial"),
    "運輸・物流": ("balanced", "industrial"),
    "情報・通信業": ("technology", "technology"),
    "情報通信・サービスその他": ("technology", "technology"),
    "卸売業": ("trading", "industrial"),
    "商社・卸売": ("trading", "industrial"),
    "小売業": ("consumer", "consumer"),
    "銀行業": ("financial", "financial"),
    "銀行": ("financial", "financial"),
    "証券、商品先物取引業": ("financial", "financial"),
    "保険業": ("financial", "financial"),
    "その他金融業": ("financial", "financial"),
    "金融（除く銀行）": ("financial", "financial"),
    "不動産業": ("balanced", "real_estate"),
    "不動産": ("balanced", "real_estate"),
    "サービス業": ("consumer", "consumer"),
}

_US_SECTOR_THEME_SECTOR_MAP = {
    "communication": ("communication", "communication"),
    "communication services": ("communication", "communication"),
    "consumer discretionary": ("consumer", "consumer"),
    "consumer staples": ("consumer", "consumer"),
    "consumer": ("consumer", "consumer"),
    "energy": ("energy", "energy"),
    "financial": ("financial", "financial"),
    "financials": ("financial", "financial"),
    "health care": ("healthcare", "healthcare"),
    "healthcare": ("healthcare", "healthcare"),
    "industrial": ("balanced", "industrial"),
    "industrials": ("balanced", "industrial"),
    "information technology": ("technology", "technology"),
    "materials": ("balanced", "materials"),
    "real estate": ("balanced", "real_estate"),
    "semiconductor": ("semiconductor", "technology"),
    "semiconductors": ("semiconductor", "technology"),
    "technology": ("technology", "technology"),
    "utilities": ("energy", "utilities"),
    "コミュニケーション": ("communication", "communication"),
    "一般消費財": ("consumer", "consumer"),
    "生活必需品": ("consumer", "consumer"),
    "エネルギー": ("energy", "energy"),
    "金融": ("financial", "financial"),
    "ヘルスケア": ("healthcare", "healthcare"),
    "資本財": ("balanced", "industrial"),
    "素材": ("balanced", "materials"),
    "不動産": ("balanced", "real_estate"),
    "情報技術": ("technology", "technology"),
    "公益事業": ("energy", "utilities"),
}

_INDEX_FAMILY_KEYWORDS = {
    "acwi": ("ACWI", "ALL COUNTRY", "全世界"),
    "msci_world": ("MSCI WORLD", "DEVELOPED", "先進国"),
    "nasdaq100": ("NASDAQ 100", "NASDAQ100", "ナスダック100"),
    "nikkei225": ("NIKKEI 225", "日経225"),
    "small_us": ("SMALL-CAP", "SMALL CAP", "小型"),
    "sp500": ("S&P 500", "SP500", "S&P500"),
    "topix": ("TOPIX",),
    "total_us": ("TOTAL STOCK MARKET", "TOTAL U.S.", "全米"),
}

_LEVERAGED_MARKERS = (
    "2X",
    "3X",
    "BULL",
    "LEVERAGED",
    "ULTRA",
    "レバレッジ",
    "ブル",
)
_INVERSE_MARKERS = (
    "BEAR",
    "INVERSE",
    "SHORT",
    "インバース",
    "ベア",
    "反対",
)


@dataclass(frozen=True)
class SymbolUniverseSourceBuildResult:
    """Rows and manifest for a generated symbol-universe source CSV."""

    rows: list[dict[str, str]]
    manifest: dict[str, object]


def build_jpx_listed_stock_source_rows(
    raw_rows: Sequence[Mapping[str, Any]],
    *,
    as_of: date,
) -> SymbolUniverseSourceBuildResult:
    """Build source-import rows from JPX listed-stock raw rows.

    The JPX listed issue file is broader than the MVP ranking universe. This
    builder keeps domestic listed stocks and leaves ETF/ETN/REIT rows for a
    separate ETF/ETN source.
    """

    output_rows: list[dict[str, str]] = []
    skipped_rows: list[dict[str, str]] = []

    for index, raw_row in enumerate(raw_rows, start=2):
        code = _normalize_jpx_code(_first_value(raw_row, _CODE_ALIASES))
        name = _first_value(raw_row, _NAME_ALIASES)
        market_segment = _first_value(raw_row, _MARKET_SEGMENT_ALIASES)
        industry_33 = _first_value(raw_row, _INDUSTRY_33_ALIASES)
        industry_17 = _first_value(raw_row, _INDUSTRY_17_ALIASES)
        scale_category = _first_value(raw_row, _SCALE_ALIASES)

        if not code or not name:
            skipped_rows.append(_skipped_row(index, code, "JPX-LISTED-STOCK-MISSING-CODE-OR-NAME"))
            continue
        if not _is_jpx_listed_stock(code, name, market_segment):
            skipped_rows.append(_skipped_row(index, code, "JPX-LISTED-STOCK-OUT-OF-SCOPE"))
            continue

        theme, sector = _theme_sector_for_industry(industry_33, industry_17)
        tags = _tag_for_theme_sector(theme, sector)
        output_rows.append(
            {
                "code": code,
                "security_name": name,
                "market": "jp",
                "asset_type": "stock",
                "currency": "JPY",
                "theme": theme,
                "sector": sector,
                "tags": tags,
                "aliases": _aliases_for_jpx_row(
                    name,
                    market_segment,
                    industry_33,
                    industry_17,
                ),
                "source_market_segment": market_segment,
                "source_industry_33": industry_33,
                "source_industry_17": industry_17,
                "source_scale_category": scale_category,
            }
        )

    manifest = _source_build_manifest(
        source_kind="jpx_listed_stock",
        as_of=as_of,
        raw_rows=raw_rows,
        output_rows=output_rows,
        skipped_rows=skipped_rows,
        fieldnames=JPX_LISTED_STOCK_SOURCE_FIELDNAMES,
    )
    return SymbolUniverseSourceBuildResult(rows=output_rows, manifest=manifest)


def build_sbi_us_stock_source_rows(
    raw_rows: Sequence[Mapping[str, Any]],
    *,
    as_of: date,
) -> SymbolUniverseSourceBuildResult:
    """Build source-import rows from a local SBI US stock handling list."""

    output_rows: list[dict[str, str]] = []
    skipped_rows: list[dict[str, str]] = []

    for index, raw_row in enumerate(raw_rows, start=2):
        symbol = _normalize_us_symbol(_first_value(raw_row, _SYMBOL_ALIASES))
        name = _first_value(raw_row, _US_NAME_ALIASES)
        sector_raw = _first_value(raw_row, _SECTOR_ALIASES)

        if not symbol or not name:
            skipped_rows.append(_skipped_row(index, symbol, "SBI-US-STOCK-MISSING-SYMBOL-OR-NAME"))
            continue

        theme, sector = _theme_sector_for_us_sector(sector_raw)
        output_rows.append(
            {
                "symbol": symbol,
                "name": name,
                "market": "us",
                "asset_type": "stock",
                "currency": "USD",
                "sector": sector,
                "theme": theme,
                "aliases": _aliases_for_values(name, sector_raw),
                "dividend_category": _first_value(raw_row, _DIVIDEND_CATEGORY_ALIASES),
                "dividend_yield_pct": _normalize_percent(
                    _first_value(raw_row, _DIVIDEND_YIELD_ALIASES)
                ),
                "market_cap_tier": _first_value(raw_row, _MARKET_CAP_TIER_ALIASES),
                "tags": _first_value(raw_row, _TAGS_ALIASES)
                or _tag_for_theme_sector(theme, sector),
                "per": _first_value(raw_row, _PER_ALIASES),
                "pbr": _first_value(raw_row, _PBR_ALIASES),
                "roe_pct": _normalize_percent(_first_value(raw_row, _ROE_ALIASES)),
                "consensus_rating": _first_value(raw_row, _CONSENSUS_RATING_ALIASES),
                "forecast_agreement": _first_value(raw_row, _FORECAST_AGREEMENT_ALIASES),
                "data_quality": _first_value(raw_row, _DATA_QUALITY_ALIASES),
                "risk_band": _first_value(raw_row, _RISK_BAND_ALIASES),
            }
        )

    manifest = _source_build_manifest(
        source_kind="sbi_us_stock",
        as_of=as_of,
        raw_rows=raw_rows,
        output_rows=output_rows,
        skipped_rows=skipped_rows,
        fieldnames=SBI_US_STOCK_SOURCE_FIELDNAMES,
    )
    return SymbolUniverseSourceBuildResult(rows=output_rows, manifest=manifest)


def build_sbi_us_etf_source_rows(
    raw_rows: Sequence[Mapping[str, Any]],
    *,
    as_of: date,
) -> SymbolUniverseSourceBuildResult:
    """Build source-import rows from a local SBI US/overseas ETF handling list."""

    output_rows: list[dict[str, str]] = []
    skipped_rows: list[dict[str, str]] = []

    for index, raw_row in enumerate(raw_rows, start=2):
        symbol = _normalize_us_symbol(_first_value(raw_row, _SYMBOL_ALIASES))
        name = _first_value(raw_row, _US_NAME_ALIASES)
        index_raw = _first_value(raw_row, _INDEX_FAMILY_ALIASES)

        if not symbol or not name:
            skipped_rows.append(_skipped_row(index, symbol, "SBI-US-ETF-MISSING-SYMBOL-OR-NAME"))
            continue

        complexity = _complexity_for_etf(raw_row, name)
        is_leveraged = _flag_for_etf(raw_row, _IS_LEVERAGED_ALIASES, name, _LEVERAGED_MARKERS)
        is_inverse = _flag_for_etf(raw_row, _IS_INVERSE_ALIASES, name, _INVERSE_MARKERS)
        output_rows.append(
            {
                "symbol": symbol,
                "name": name,
                "market": "us",
                "asset_type": "etf",
                "currency": "USD",
                "index_family": _index_family_for_text(index_raw, name),
                "expense_ratio_pct": _normalize_percent(
                    _first_value(raw_row, _EXPENSE_RATIO_ALIASES)
                ),
                "complexity": complexity,
                "tags": _first_value(raw_row, _TAGS_ALIASES) or _tags_for_etf(complexity),
                "nisa_category": _first_value(raw_row, _NISA_CATEGORY_ALIASES),
                "investment_style": _first_value(raw_row, _INVESTMENT_STYLE_ALIASES)
                or ("lump_sum" if is_leveraged == "true" or is_inverse == "true" else "both"),
                "is_leveraged": is_leveraged,
                "is_inverse": is_inverse,
                "aliases": _aliases_for_values(name, index_raw),
            }
        )

    manifest = _source_build_manifest(
        source_kind="sbi_us_etf",
        as_of=as_of,
        raw_rows=raw_rows,
        output_rows=output_rows,
        skipped_rows=skipped_rows,
        fieldnames=SBI_US_ETF_SOURCE_FIELDNAMES,
    )
    return SymbolUniverseSourceBuildResult(rows=output_rows, manifest=manifest)


def _first_value(row: Mapping[str, Any], aliases: Sequence[str]) -> str:
    normalized_by_key = {str(key).strip().lower(): value for key, value in row.items()}
    for alias in aliases:
        value = normalized_by_key.get(alias.lower())
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _normalize_jpx_code(value: str) -> str:
    text = value.strip().upper()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    text = text.replace(".T", "")
    return text if _JPX_CODE_PATTERN.match(text) else ""


def _normalize_us_symbol(value: str) -> str:
    text = value.strip().upper().replace("$", "")
    if not text:
        return ""
    text = text.split()[0]
    text = text.replace(".", "-").replace("/", "-")
    return text if _US_SYMBOL_PATTERN.match(text) else ""


def _is_jpx_listed_stock(code: str, name: str, market_segment: str) -> bool:
    if not _JPX_CODE_PATTERN.match(code):
        return False
    combined_text = f"{name} {market_segment}".upper()
    if any(marker.upper() in combined_text for marker in _JPX_NON_STOCK_MARKERS):
        return False
    if market_segment and not any(marker in market_segment for marker in _JPX_STOCK_MARKET_MARKERS):
        return False
    return True


def _theme_sector_for_industry(industry_33: str, industry_17: str) -> tuple[str, str]:
    for industry in (industry_33, industry_17):
        if industry in _INDUSTRY_THEME_SECTOR_MAP:
            return _INDUSTRY_THEME_SECTOR_MAP[industry]
    return "balanced", "industrial"


def _theme_sector_for_us_sector(sector: str) -> tuple[str, str]:
    normalized_sector = sector.strip().lower()
    if normalized_sector in _US_SECTOR_THEME_SECTOR_MAP:
        return _US_SECTOR_THEME_SECTOR_MAP[normalized_sector]
    for marker, mapped in _US_SECTOR_THEME_SECTOR_MAP.items():
        if marker and marker in normalized_sector:
            return mapped
    return "balanced", "industrial"


def _tag_for_theme_sector(theme: str, sector: str) -> str:
    if theme in {"healthcare", "semiconductor", "technology"}:
        return "growth"
    if theme in {"energy", "financial", "telecom", "trading"} or sector == "utilities":
        return "dividend"
    if sector == "materials":
        return "value"
    return "balanced"


def _normalize_percent(value: str) -> str:
    text = value.strip().replace("%", "").replace(",", "")
    return text


def _index_family_for_text(index_text: str, name: str) -> str:
    combined_text = f"{index_text} {name}".upper()
    for index_family, markers in _INDEX_FAMILY_KEYWORDS.items():
        if any(marker in combined_text for marker in markers):
            return index_family
    return ""


def _complexity_for_etf(row: Mapping[str, Any], name: str) -> str:
    explicit_value = _first_value(row, _COMPLEXITY_ALIASES).strip().lower()
    if explicit_value:
        return explicit_value
    name_upper = name.upper()
    if any(marker in name_upper for marker in _INVERSE_MARKERS):
        return "inverse"
    if any(marker in name_upper for marker in _LEVERAGED_MARKERS):
        return "leveraged"
    return "beginner"


def _flag_for_etf(
    row: Mapping[str, Any],
    aliases: Sequence[str],
    name: str,
    name_markers: Sequence[str],
) -> str:
    explicit_value = _first_value(row, aliases).strip().lower()
    if explicit_value in {"true", "1", "yes", "y", "あり", "有"}:
        return "true"
    if explicit_value in {"false", "0", "no", "n", "なし", "無"}:
        return "false"
    name_upper = name.upper()
    return "true" if any(marker in name_upper for marker in name_markers) else "false"


def _tags_for_etf(complexity: str) -> str:
    if complexity in {"leveraged", "inverse", "etn", "advanced"}:
        return ""
    return "low_cost"


def _aliases_for_jpx_row(
    name: str,
    market_segment: str,
    industry_33: str,
    industry_17: str,
) -> str:
    values = [name, market_segment, industry_33, industry_17]
    return " ".join(value for value in values if value)


def _aliases_for_values(*values: str) -> str:
    return " ".join(value for value in values if value)


def _source_build_manifest(
    *,
    source_kind: str,
    as_of: date,
    raw_rows: Sequence[Mapping[str, Any]],
    output_rows: Sequence[Mapping[str, str]],
    skipped_rows: Sequence[Mapping[str, str]],
    fieldnames: Sequence[str],
) -> dict[str, object]:
    return {
        "operation": "symbol_universe_source_build",
        "source_kind": source_kind,
        "as_of": as_of.isoformat(),
        "input_rows": len(raw_rows),
        "output_rows": len(output_rows),
        "skipped_rows": len(skipped_rows),
        "skipped": list(skipped_rows[:50]),
        "fieldnames": list(fieldnames),
    }


def _skipped_row(source_row: int, code: str, code_name: str) -> dict[str, str]:
    return {
        "source_row": str(source_row),
        "code": code,
        "reason": code_name,
    }
