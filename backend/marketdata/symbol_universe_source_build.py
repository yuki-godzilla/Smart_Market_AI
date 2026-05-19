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

_JPX_CODE_PATTERN = re.compile(r"^[0-9A-Z]{4}$")
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

    manifest = {
        "operation": "symbol_universe_source_build",
        "source_kind": "jpx_listed_stock",
        "as_of": as_of.isoformat(),
        "input_rows": len(raw_rows),
        "output_rows": len(output_rows),
        "skipped_rows": len(skipped_rows),
        "skipped": skipped_rows[:50],
        "fieldnames": list(JPX_LISTED_STOCK_SOURCE_FIELDNAMES),
    }
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


def _tag_for_theme_sector(theme: str, sector: str) -> str:
    if theme in {"healthcare", "semiconductor", "technology"}:
        return "growth"
    if theme in {"energy", "financial", "telecom", "trading"} or sector == "utilities":
        return "dividend"
    if sector == "materials":
        return "value"
    return "balanced"


def _aliases_for_jpx_row(
    name: str,
    market_segment: str,
    industry_33: str,
    industry_17: str,
) -> str:
    values = [name, market_segment, industry_33, industry_17]
    return " ".join(value for value in values if value)


def _skipped_row(source_row: int, code: str, code_name: str) -> dict[str, str]:
    return {
        "source_row": str(source_row),
        "code": code,
        "reason": code_name,
    }
