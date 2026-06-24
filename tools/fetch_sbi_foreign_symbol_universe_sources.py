from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_CSV = PROJECT_ROOT / "data" / "marketdata" / "symbol_universe_sources" / "sbi_foreign_stock_official_latest.csv"
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "marketdata" / "raw" / "sbi_foreign"
DEFAULT_REPORT = PROJECT_ROOT / "reports" / "sbi_foreign_stock_import_report.json"

SBI_FOREIGN_LIST_URLS: dict[str, str] = {
    "sbi_hk_stock": "https://search.sbisec.co.jp/v2/popwin/info/stock/pop6040_hk_list.html",
    "sbi_korea_stock": "https://search.sbisec.co.jp/v2/popwin/info/stock/pop6040_kr_list.html",
    "sbi_vietnam_stock": "https://search.sbisec.co.jp/v2/popwin/info/stock/pop6040_vn_list.html",
    "sbi_indonesia_stock": "https://search.sbisec.co.jp/v2/popwin/info/stock/pop6040_id_list.html",
    "sbi_singapore_stock": "https://search.sbisec.co.jp/v2/popwin/info/stock/pop6040_sg_list.html",
    "sbi_thailand_stock": "https://search.sbisec.co.jp/v2/popwin/info/stock/pop6040_th_list.html",
    "sbi_malaysia_stock": "https://search.sbisec.co.jp/v2/popwin/info/stock/pop6040_my_list.html",
}

@dataclass(frozen=True)
class MarketConfig:
    market: str
    country: str
    group: str
    currency: str
    exchange: str
    country_risk_band: str
    internal_suffix: str
    url_source: str

MARKET_CONFIGS: dict[str, MarketConfig] = {
    "sbi_hk_stock": MarketConfig("hong_kong", "Hong Kong", "china_hk", "HKD", "HKEX", "MEDIUM", ".HK", "sbi_hk_stock"),
    "sbi_korea_stock": MarketConfig("korea", "South Korea", "korea", "KRW", "KRX", "MEDIUM", ".KS", "sbi_korea_stock"),
    "sbi_vietnam_stock": MarketConfig("vietnam", "Vietnam", "asean", "VND", "HOSE", "HIGH", ".VN", "sbi_vietnam_stock"),
    "sbi_indonesia_stock": MarketConfig("indonesia", "Indonesia", "asean", "IDR", "IDX", "HIGH", ".JK", "sbi_indonesia_stock"),
    "sbi_singapore_stock": MarketConfig("singapore", "Singapore", "asean", "SGD", "SGX", "MEDIUM", ".SI", "sbi_singapore_stock"),
    "sbi_thailand_stock": MarketConfig("thailand", "Thailand", "asean", "THB", "SET", "HIGH", ".BK", "sbi_thailand_stock"),
    "sbi_malaysia_stock": MarketConfig("malaysia", "Malaysia", "asean", "MYR", "BURSA", "MEDIUM", ".KL", "sbi_malaysia_stock"),
}


SBI_FOREIGN_YAHOO_SYMBOL_OVERRIDES = {
    "singapore": {
        "CAPN": "9CI.SI",
        "CMDG": "C52.SI",
        "CTDM": "C09.SI",
        "DBSM": "D05.SI",
        "DELF": "P34.SI",
        "FRNM": "F99.SI",
        "FRPL": "TQ5.SI",
        "GAGR": "E5H.SI",
        "OLAG": "VC2.SI",
        "GENS": "G13.SI",
        "IFAR": "5JS.SI",
        "JCYC": "C07.SI",
        "KPLM": "BN4.SI",
        "AMOL": "EVS.SI",
        "AMOE": "G3B.SI",
        "OCBC": "O39.SI",
        "OVES": "LJ3.SI",
        "SATS": "S58.SI",
        "SCIL": "U96.SI",
        "SEAT": "5E2.SI",
        "SGXL": "S68.SI",
        "SIAE": "S59.SI",
        "SIAL": "C6L.SI",
        "SIND": "U06.SI",
        "SPOS": "S08.SI",
        "SPRM": "T39.SI",
        "STAR": "CC3.SI",
        "STEG": "S63.SI",
        "STEL": "Z74.SI",
        "UOBH": "U11.SI",
        "UTOS": "U14.SI",
        "VENM": "V03.SI",
        "WLIL": "F34.SI",
        "YAZG": "BS6.SI",
        "YNLG": "Z25.SI",
        "YOMA": "Z59.SI",
    },
    "malaysia": {
        "AIRX": "5238.KL",
        "AMMB": "1015.KL",
        "AXIA": "6888.KL",
        "BATO": "4162.KL",
        "BUAB": "5210.KL",
        "CAPI": "5099.KL",
        "CIMB": "1023.KL",
        "DSOM": "6947.KL",
        "GAMU": "5398.KL",
        "GENM": "4715.KL",
        "GENP": "2291.KL",
        "GENT": "3182.KL",
        "HLBB": "5819.KL",
        "HLCB": "1082.KL",
        "IHHH": "5225.KL",
        "IJMS": "3336.KL",
        "IOIB": "1961.KL",
        "IOIP": "5249.KL",
        "KLKK": "2445.KL",
        "MBBM": "1155.KL",
        "MHEB": "5186.KL",
        "MISC": "3816.KL",
        "MMCB": "2194.KL",
        "MXSC": "6012.KL",
        "NESM": "4707.KL",
        "PCGB": "5183.KL",
        "PEPT": "4065.KL",
        "PETR": "5681.KL",
        "PGAS": "6033.KL",
        "PRKN": "5657.KL",
        "PUBM": "1295.KL",
        "RHBC": "1066.KL",
        "SEVE": "5250.KL",
        "SETI": "8664.KL",
        "SIME": "4197.KL",
        "TENA": "5347.KL",
        "TLMM": "4863.KL",
        "UMSB": "5148.KL",
        "UMWS": "4588.KL",
        "VELE": "5243.KL",
        "YTLP": "6742.KL",
        "YTLS": "4677.KL",
    },
}

OUTPUT_FIELDNAMES = [
    "symbol", "name", "market", "asset_type", "currency", "broker", "tradability",
    "nisa_category", "investment_style", "is_sbi_supported", "is_active", "is_leveraged",
    "is_inverse", "theme", "sector", "aliases", "dividend_category", "market_cap_tier",
    "index_family", "expense_ratio_pct", "complexity", "tags", "data_quality", "risk_band",
    "metadata_source", "metadata_as_of", "metadata_updated_at", "yahoo_symbol", "yahoo_symbol_status", "yahoo_symbol_checked_at", "yahoo_symbol_note", "country",
    "exchange", "local_symbol", "primary_listing_country", "trading_currency", "settlement_currency",
    "quote_currency", "fx_pair_to_jpy", "foreign_market_group", "country_risk_band",
    "liquidity_tier", "foreign_data_quality", "foreign_data_quality_reasons",
    "sbi_foreign_tradability", "sbi_foreign_tradability_as_of", "sbi_foreign_tradability_source",
    "sbi_tradability_status", "sbi_tradability_verified", "sbi_tradability_as_of", "sbi_tradability_source",
    "source_section", "source_market", "source_industry", "source_description", "source_url",
]

class _SbiHtmlTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tables: list[dict[str, object]] = []
        self._heading_parts: list[str] = []
        self._in_heading = False
        self._current_heading = ""
        self._in_table = False
        self._in_row = False
        self._in_cell = False
        self._rows: list[list[str]] = []
        self._row: list[str] = []
        self._cell_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"h2", "h3", "h4"}:
            self._in_heading = True
            self._heading_parts = []
        elif tag == "table":
            self._in_table = True
            self._rows = []
        elif self._in_table and tag == "tr":
            self._in_row = True
            self._row = []
        elif self._in_row and tag in {"td", "th"}:
            self._in_cell = True
            self._cell_parts = []

    def handle_data(self, data: str) -> None:
        text = _clean_text(data)
        if not text:
            return
        if self._in_heading:
            self._heading_parts.append(text)
        elif self._in_cell:
            self._cell_parts.append(text)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"h2", "h3", "h4"} and self._in_heading:
            heading = _clean_text(" ".join(self._heading_parts))
            if heading:
                self._current_heading = heading
            self._in_heading = False
        elif self._in_cell and tag in {"td", "th"}:
            self._row.append(_clean_text(" ".join(self._cell_parts)))
            self._in_cell = False
        elif self._in_row and tag == "tr":
            if any(cell.strip() for cell in self._row):
                self._rows.append(self._row)
            self._in_row = False
        elif self._in_table and tag == "table":
            if self._rows:
                self.tables.append({"section": self._current_heading, "rows": self._rows})
            self._in_table = False


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch official SBI foreign-stock list pages and build a symbol-universe source CSV."
    )
    parser.add_argument("--source-kind", choices=tuple(SBI_FOREIGN_LIST_URLS), action="append")
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--as-of", type=_parse_date, default=date.today())
    parser.add_argument("--write", action="store_true", help="Write CSV/raw HTML/report. Without this, dry-run only.")
    args = parser.parse_args(argv)

    source_kinds = args.source_kind or list(SBI_FOREIGN_LIST_URLS)
    all_rows: list[dict[str, str]] = []
    report: dict[str, object] = {
        "as_of": args.as_of.isoformat(),
        "generated_at": datetime.now().astimezone().isoformat(),
        "sources": {},
    }
    for source_kind in source_kinds:
        url = SBI_FOREIGN_LIST_URLS[source_kind]
        html = _download_text(url)
        if args.write:
            args.raw_dir.mkdir(parents=True, exist_ok=True)
            (args.raw_dir / f"{source_kind}_{args.as_of.isoformat().replace('-', '')}.html").write_text(html, encoding="utf-8")
        rows = parse_sbi_foreign_list_html(html, source_kind=source_kind, as_of=args.as_of, source_url=url)
        all_rows.extend(rows)
        report["sources"][source_kind] = {
            "url": url,
            "rows": len(rows),
            "by_asset_type": _counts(row["asset_type"] for row in rows),
            "by_market": _counts(row["source_market"] for row in rows),
            "sample_symbols": [row["symbol"] for row in rows[:10]],
        }
    duplicate_symbols = sorted(_duplicates(row["symbol"] for row in all_rows))
    report["total_rows"] = len(all_rows)
    report["duplicate_symbols"] = duplicate_symbols
    report["validation_errors"] = _validation_errors(all_rows)

    if args.write:
        args.output_csv.parent.mkdir(parents=True, exist_ok=True)
        _write_csv(args.output_csv, all_rows)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not report["validation_errors"] else 2


def parse_sbi_foreign_list_html(html: str, *, source_kind: str, as_of: date, source_url: str) -> list[dict[str, str]]:
    config = MARKET_CONFIGS[source_kind]
    parser = _SbiHtmlTableParser()
    parser.feed(html)
    rows: list[dict[str, str]] = []
    for table in parser.tables:
        section = str(table.get("section") or "")
        table_rows = table.get("rows") or []
        if not isinstance(table_rows, list):
            continue
        rows.extend(_table_to_rows(table_rows, section=section, config=config, source_kind=source_kind, as_of=as_of, source_url=source_url))
    return rows


def _table_to_rows(table_rows: list[list[str]], *, section: str, config: MarketConfig, source_kind: str, as_of: date, source_url: str) -> list[dict[str, str]]:
    header_index = _find_header(table_rows)
    if header_index is None:
        return []
    headers = [_normalize_header(cell) for cell in table_rows[header_index]]
    rows: list[dict[str, str]] = []
    for values in table_rows[header_index + 1:]:
        row = {headers[index]: values[index] if index < len(values) else "" for index in range(len(headers)) if headers[index]}
        normalized = _normalize_source_row(row, section=section, config=config, source_kind=source_kind, as_of=as_of, source_url=source_url)
        if normalized:
            rows.append(normalized)
    return rows


def _find_header(rows: list[list[str]]) -> int | None:
    for index, row in enumerate(rows):
        headers = {_normalize_header(cell) for cell in row}
        if ("code" in headers or "ticker" in headers) and ("name" in headers or "name_ja" in headers or "name_kana" in headers):
            return index
    return None


def _normalize_header(value: str) -> str:
    text = _clean_text(value).lower()
    if text in {"コード", "銘柄コード", "code"}:
        return "code"
    if text in {"ティッカー", "ticker"}:
        return "ticker"
    if "取引所コード" in text:
        return "exchange_code"
    if text in {"銘柄", "銘柄名", "銘柄（英語）", "名称", "name"}:
        return "name"
    if "銘柄名" in text and "カナ" in text:
        return "name_kana"
    if "銘柄名" in text and "漢字" in text:
        return "name_ja"
    if text in {"会社概要", "事業内容", "連動指数", "概要"}:
        return "description"
    if "市場" in text and ("業種" in text or "セクター" in text):
        return "source_market_industry"
    if text in {"市場", "市場名"}:
        return "source_market"
    if text in {"業種", "セクター"}:
        return "source_industry"
    if "信託報酬" in text or "経費率" in text:
        return "expense_ratio_pct"
    return text


def _normalize_source_row(row: dict[str, str], *, section: str, config: MarketConfig, source_kind: str, as_of: date, source_url: str) -> dict[str, str] | None:
    local_symbol = _normalize_local_symbol(row.get("ticker") or row.get("code") or "")
    if not local_symbol:
        return None
    name = row.get("name") or row.get("name_ja") or row.get("name_kana")
    name = _clean_text(name)
    if not name:
        return None
    description = _clean_text(row.get("description", ""))
    combined_market_industry = _clean_text(row.get("source_market_industry", ""))
    combined_market, combined_industry = _split_market_industry(combined_market_industry)
    source_market = _clean_text(row.get("source_market", "")) or combined_market or config.exchange
    source_industry = _clean_text(row.get("source_industry", "")) or combined_industry
    asset_type = _asset_type_for_section(section, name, description)
    sector, theme, tags, index_family = _classification(asset_type, source_industry, name, description)
    exchange = _exchange_for_row(config, source_market)
    symbol = _internal_symbol(local_symbol, config, exchange)
    yahoo_symbol, yahoo_note = _best_effort_yahoo_symbol(local_symbol, config, exchange)
    data_quality_reasons = ["sbi_official_list_imported", "market_metrics_missing"]
    if yahoo_note:
        data_quality_reasons.append(yahoo_note)
    if not source_industry and asset_type == "stock":
        data_quality_reasons.append("sector_inferred_from_description")
    if asset_type != "stock":
        data_quality_reasons.append("foreign_fund_classification_requires_review")
    return {
        "symbol": symbol,
        "name": name,
        "market": config.market,
        "asset_type": asset_type,
        "currency": config.currency,
        "broker": "sbi_securities",
        "tradability": "tradable",
        "nisa_category": "unknown",
        "investment_style": "lump_sum" if asset_type == "stock" else "unknown",
        "is_sbi_supported": "true",
        "is_active": "true",
        "is_leveraged": "false",
        "is_inverse": "false",
        "theme": theme,
        "sector": sector,
        "aliases": _aliases(local_symbol, name, row.get("name_kana", ""), row.get("name_ja", ""), description, source_industry),
        # Keep generated rows strictly compatible with symbol_metadata_schema.py.
        # Blank values are safer than unapproved placeholders because the importer
        # validates allowed-value fields for the whole DB after appending rows.
        "dividend_category": "none",
        "market_cap_tier": "",
        "index_family": index_family,
        "expense_ratio_pct": _normalize_percent(row.get("expense_ratio_pct", "")),
        "complexity": _complexity(asset_type),
        "tags": _normalize_ranking_tags(tags),
        "data_quality": "WARN",
        "risk_band": _risk_band(asset_type, config.country_risk_band),
        "metadata_source": source_kind,
        "metadata_as_of": as_of.isoformat(),
        "metadata_updated_at": datetime.now().astimezone().isoformat(),
        "yahoo_symbol": yahoo_symbol,
        "yahoo_symbol_status": "requires_review" if yahoo_note else "generated",
        "yahoo_symbol_checked_at": "",
        "yahoo_symbol_note": yahoo_note,
        "country": config.country,
        "exchange": exchange,
        "local_symbol": local_symbol,
        "primary_listing_country": config.country,
        "trading_currency": config.currency,
        "settlement_currency": config.currency,
        "quote_currency": config.currency,
        "fx_pair_to_jpy": f"{config.currency}JPY" if config.currency != "JPY" else "",
        "foreign_market_group": config.group,
        "country_risk_band": config.country_risk_band,
        "liquidity_tier": "unknown",
        "foreign_data_quality": "WARN",
        "foreign_data_quality_reasons": ";".join(data_quality_reasons),
        "sbi_foreign_tradability": "tradable",
        "sbi_foreign_tradability_as_of": as_of.isoformat(),
        "sbi_foreign_tradability_source": source_kind,
        "sbi_tradability_status": "confirmed",
        "sbi_tradability_verified": "true",
        "sbi_tradability_as_of": as_of.isoformat(),
        "sbi_tradability_source": source_kind,
        "source_section": section,
        "source_market": source_market,
        "source_industry": source_industry,
        "source_description": description,
        "source_url": source_url,
    }




def _split_market_industry(value: str) -> tuple[str, str]:
    text = _clean_text(value)
    if not text:
        return "", ""
    parts = text.split(maxsplit=1)
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def _normalize_ranking_tags(value: str) -> str:
    """Return tags in the comma-separated format expected by ui.symbol_universe."""

    aliases = {
        "foreign_stock": "balanced",
        "foreign_etf": "index",
        "income": "reit",
        "telecom": "communication",
        "hang_seng": "index",
        "msci": "index",
        "ftse": "index",
        "csi": "index",
    }
    allowed = {
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
    tags: list[str] = []
    seen: set[str] = set()
    for raw in re.split(r"[,;]", value or ""):
        tag = aliases.get(raw.strip(), raw.strip())
        if not tag or tag not in allowed or tag in seen:
            continue
        tags.append(tag)
        seen.add(tag)
    return ",".join(tags or ["balanced"])


def _asset_type_for_section(section: str, name: str, description: str) -> str:
    if _looks_like_reit(section, name, description):
        return "reit"
    text = f"{section} {name} {description}".lower()
    if "etf" in text or "上場投信" in text or "連動" in text or "インデックス" in text:
        return "etf"
    return "stock"


def _looks_like_reit(section: str, name: str, description: str) -> bool:
    # Avoid false positives from ordinary Japanese/English words such as
    # コンクリート and Wall Street, while keeping SBI's explicit REIT sections.
    text = f"{section} {name} {description}"
    if "不動産投資信託" in text:
        return True
    if re.search(r"(?<![A-Za-z])REIT(?![A-Za-z])", text, flags=re.IGNORECASE):
        return True
    return bool(re.search(r"(?<![ァ-ンー])リート(?![ァ-ンー])", text))


def _classification(asset_type: str, source_industry: str, name: str, description: str) -> tuple[str, str, str, str]:
    text = f"{source_industry} {name} {description}".lower()
    if asset_type == "etf":
        index_family = _index_family(text)
        tags = "index"
        if index_family == "bond":
            tags = "index,bond"
        elif index_family == "reit":
            tags = "index,reit,real_estate"
        elif index_family in {"china", "emerging", "singapore_equity"}:
            tags = "index"
        return "index", "index", tags, index_family
    if asset_type == "reit":
        return "real_estate", "reit", "reit,real_estate", ""
    keyword_map: list[tuple[tuple[str, ...], str, str, str]] = [
        (("銀行", "bank", "commercial bank"), "financial", "bank", "bank"),
        (("保険", "insurance"), "financial", "insurance", "insurance"),
        (("金融", "証券", "securities", "financial"), "financial", "financial", "financial"),
        (("半導体", "semiconductor", "電子", "電気", "technology", "通信・技術", "it", "ソフト", "インターネット"), "technology", "technology", "technology"),
        (("通信", "telecom", "携帯電話", "インターネット"), "communication", "telecom", "communication"),
        (("不動産", "property", "real estate", "reit"), "real_estate", "real_estate", "real_estate"),
        (("電力", "ガス", "utilities", "発電", "水道"), "utilities", "utilities", "utilities"),
        (("石油", "天然ガス", "エネルギー", "energy", "oil", "coal", "石炭"), "energy", "energy", "energy"),
        (("医薬", "ヘルスケア", "病院", "health", "pharma", "biotech"), "healthcare", "healthcare", "healthcare"),
        (("自動車", "automotive", "vehicle", "motor", "バッテリー", "タイヤ"), "consumer", "automotive", "automotive"),
        (("食品", "小売", "飲料", "consumer", "retail", "ホテル", "航空", "旅行", "カジノ"), "consumer", "consumer", "consumer"),
        (("建設", "資材", "鉄鋼", "素材", "化学", "セメント", "鉱物", "製造", "工業"), "industrial", "industrial", "industrial"),
    ]
    for keywords, sector, theme, tag in keyword_map:
        if any(keyword in text for keyword in keywords):
            return sector, theme, tag, ""
    return "consumer", "balanced", "balanced", ""


def _index_family(text: str) -> str:
    if "bond" in text or "債券" in text:
        return "bond"
    if "reit" in text or "リート" in text:
        return "reit"
    if "singapore" in text or "ストレーツタイムズ" in text or "straits times" in text:
        return "singapore_equity"
    if "hang seng" in text or "ハンセン" in text or "csi" in text or "中国a50" in text or "china" in text or "中国" in text:
        return "china"
    if "msci" in text or "ftse" in text:
        return "emerging"
    return ""


def _exchange_for_row(config: MarketConfig, source_market: str) -> str:
    text = source_market.upper()
    if "KOSDAQ" in text:
        return "KOSDAQ"
    if "KOSPI" in text:
        return "KOSPI"
    if "HNX" in text:
        return "HNX"
    if "HOSE" in text:
        return "HOSE"
    if "SET" in text:
        return "SET"
    if "IDX" in text:
        return "IDX"
    return config.exchange


def _internal_symbol(local_symbol: str, config: MarketConfig, exchange: str) -> str:
    suffix = config.internal_suffix
    if config.market == "korea" and exchange == "KOSDAQ":
        suffix = ".KQ"
    return f"{local_symbol}{suffix}"


def _best_effort_yahoo_symbol(local_symbol: str, config: MarketConfig, exchange: str) -> tuple[str, str]:
    normalized_local_symbol = local_symbol.strip().upper()
    override = SBI_FOREIGN_YAHOO_SYMBOL_OVERRIDES.get(config.market, {}).get(
        normalized_local_symbol
    )
    if override:
        return override, ""
    if config.market == "hong_kong" and local_symbol.isdigit():
        return f"{int(local_symbol):04d}.HK", ""
    if config.market == "korea":
        return f"{local_symbol}{'.KQ' if exchange == 'KOSDAQ' else '.KS'}", ""
    if config.market == "indonesia":
        return f"{local_symbol}.JK", ""
    if config.market == "thailand":
        return f"{local_symbol}.BK", ""
    if config.market == "vietnam":
        return f"{local_symbol}.VN", ""
    # SBI Singapore/Malaysia tickers are often broker aliases rather than exchange/Yahoo codes.
    return f"{local_symbol}{config.internal_suffix}", "yahoo_symbol_requires_review"


def _complexity(asset_type: str) -> str:
    if asset_type == "etf":
        return "standard"
    if asset_type == "reit":
        return "standard"
    return "standard"


def _risk_band(asset_type: str, country_risk_band: str) -> str:
    if country_risk_band == "HIGH":
        return "HIGH"
    if country_risk_band == "LOW":
        return "LOW"
    return "MEDIUM"


def _normalize_local_symbol(value: str) -> str:
    text = _clean_text(value).upper().replace("$", "")
    text = text.split()[0] if text else ""
    return re.sub(r"[^0-9A-Z-]", "", text)


def _normalize_percent(value: str) -> str:
    text = _clean_text(value).replace("％", "%")
    if not text:
        return ""
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return match.group(0) if match else ""


def _aliases(*values: str) -> str:
    aliases: list[str] = []
    seen: set[str] = set()
    for value in values:
        for part in re.split(r"[;/|、,]", value or ""):
            item = _clean_text(part)
            if item and item not in seen:
                aliases.append(item)
                seen.add(item)
    return ";".join(aliases[:12])


def _clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


def _download_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 SMAI/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read()
    for encoding in ("utf-8", "cp932", "shift_jis"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def _write_csv(path: Path, rows: Sequence[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _counts(values) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _duplicates(values) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def _validation_errors(rows: Sequence[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    for idx, row in enumerate(rows, start=2):
        if not row.get("symbol"):
            errors.append(f"row {idx}: missing symbol")
        if not row.get("name"):
            errors.append(f"row {idx}: missing name")
        if not row.get("market"):
            errors.append(f"row {idx}: missing market")
        if not row.get("currency"):
            errors.append(f"row {idx}: missing currency")
    duplicates = _duplicates(row.get("symbol", "") for row in rows)
    if duplicates:
        errors.append(f"duplicate symbols: {', '.join(sorted(duplicates)[:20])}")
    return errors[:100]


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


if __name__ == "__main__":
    raise SystemExit(main())
