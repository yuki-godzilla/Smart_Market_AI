from __future__ import annotations

import argparse
import csv
import json
import re
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URL = "https://search.sbisec.co.jp/v2/popwin/info/stock/pop6040_etf.html"
DEFAULT_OUTPUT_CSV = PROJECT_ROOT / "data" / "marketdata" / "symbol_universe_sources" / "sbi_overseas_etf_official_latest.csv"
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "marketdata" / "raw" / "sbi_overseas_etf"
DEFAULT_REPORT = PROJECT_ROOT / "reports" / "sbi_overseas_etf_import_report.json"


SBI_OVERSEAS_ETF_YAHOO_SYMBOL_OVERRIDES = {
    "シンガポールETF": {
        "AMOG": "A35.SI",
        "CSOP": "SRU.SI",
        "ICGB": "CYC.SI",
        "INDI-D": "INDI.SI",
        "LIOP": "CLR.SI",
        "LISC": "ESG.SI",
        "AMOL": "EVS.SI",
        "AMOT": "MBH.SI",
        "AMOE": "G3B.SI",
        "AMON": "CFA.SI",
        "UOBA": "GRN.SI",
    },
}

OUTPUT_FIELDNAMES = [
    "symbol",
    "name",
    "market",
    "asset_type",
    "currency",
    "broker",
    "tradability",
    "nisa_category",
    "investment_style",
    "is_sbi_supported",
    "is_active",
    "is_leveraged",
    "is_inverse",
    "theme",
    "sector",
    "aliases",
    "dividend_category",
    "market_cap_tier",
    "index_family",
    "expense_ratio_pct",
    "complexity",
    "tags",
    "data_quality",
    "risk_band",
    "metadata_source",
    "metadata_as_of",
    "metadata_updated_at",
    "yahoo_symbol",
    "yahoo_symbol_status",
    "yahoo_symbol_checked_at",
    "yahoo_symbol_note",
    "country",
    "exchange",
    "local_symbol",
    "primary_listing_country",
    "trading_currency",
    "settlement_currency",
    "quote_currency",
    "fx_pair_to_jpy",
    "foreign_market_group",
    "country_risk_band",
    "liquidity_tier",
    "asset_class",
    "region_exposure",
    "is_hedged",
    "smai_theme_tags",
    "foreign_data_quality",
    "foreign_data_quality_reasons",
    "sbi_foreign_tradability",
    "sbi_foreign_tradability_as_of",
    "sbi_foreign_tradability_source",
    "sbi_tradability_status",
    "sbi_tradability_verified",
    "sbi_tradability_as_of",
    "sbi_tradability_source",
    "nisa_growth_status",
    "nisa_growth_verified",
    "nisa_growth_as_of",
    "nisa_growth_source",
    "nisa_growth_eligible",
    "nisa_tsumitate_status",
    "nisa_tsumitate_verified",
    "nisa_tsumitate_as_of",
    "nisa_tsumitate_source",
    "nisa_tsumitate_eligible",
    "source_section",
    "source_market",
    "source_description",
    "source_expense_ratio_pct",
    "source_management_company",
    "source_nisa_growth",
    "source_url",
]

@dataclass(frozen=True)
class SectionConfig:
    market: str
    country: str
    group: str
    currency: str
    country_risk_band: str
    default_exchange: str

SECTION_CONFIGS: dict[str, SectionConfig] = {
    "米国ETF": SectionConfig("us", "United States", "us", "USD", "MEDIUM", "NYSEARCA"),
    "中国ETF": SectionConfig("hong_kong", "Hong Kong", "china_hk", "HKD", "MEDIUM", "HKEX"),
    "韓国ETF": SectionConfig("korea", "South Korea", "korea", "KRW", "MEDIUM", "KRX"),
    "シンガポールETF": SectionConfig("singapore", "Singapore", "asean", "SGD", "MEDIUM", "SGX"),
}

class _SbiHtmlTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tables: list[dict[str, object]] = []
        self._current_heading = ""
        self._heading_parts: list[str] = []
        self._in_heading = False
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
        elif tag == "br" and self._in_cell:
            self._cell_parts.append(" ")
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
        description="Fetch SBI official overseas ETF list and build a symbol-universe source CSV."
    )
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--input-html", type=Path, help="Use a local SBI HTML file instead of downloading.")
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--base-csv", type=Path, help="Optional current symbol_universe.csv for coverage analysis.")
    parser.add_argument("--as-of", type=_parse_date, default=date.today())
    parser.add_argument("--write", action="store_true", help="Write CSV/raw HTML/report. Without this, dry-run only.")
    args = parser.parse_args(argv)

    html = args.input_html.read_text(encoding="utf-8", errors="replace") if args.input_html else _download_text(args.url)
    if args.write:
        args.raw_dir.mkdir(parents=True, exist_ok=True)
        (args.raw_dir / f"sbi_overseas_etf_{args.as_of.isoformat().replace('-', '')}.html").write_text(html, encoding="utf-8")

    rows = parse_sbi_overseas_etf_html(html, as_of=args.as_of, source_url=args.url)
    report: dict[str, Any] = {
        "as_of": args.as_of.isoformat(),
        "generated_at": datetime.now().astimezone().isoformat(),
        "source_url": args.url,
        "total_rows": len(rows),
        "by_section": _counts(row["source_section"] for row in rows),
        "by_market": _counts(row["market"] for row in rows),
        "by_exchange": _counts(row["exchange"] for row in rows),
        "by_asset_class": _counts(row["asset_class"] for row in rows),
        "by_index_family": _counts(row["index_family"] for row in rows if row["index_family"]),
        "by_region_exposure": _counts(row["region_exposure"] for row in rows if row["region_exposure"]),
        "nisa_growth_status": _counts(row["nisa_growth_status"] for row in rows),
        "duplicate_symbols": sorted(_duplicates(row["symbol"] for row in rows)),
        "validation_errors": _validation_errors(rows),
    }
    if args.base_csv:
        report["coverage"] = _coverage_report(args.base_csv, rows)

    if args.write:
        args.output_csv.parent.mkdir(parents=True, exist_ok=True)
        _write_csv(args.output_csv, rows)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not report["validation_errors"] else 2


def parse_sbi_overseas_etf_html(html: str, *, as_of: date, source_url: str) -> list[dict[str, str]]:
    parser = _SbiHtmlTableParser()
    parser.feed(html)
    rows: list[dict[str, str]] = []
    for table in parser.tables:
        section = _canonical_section(str(table.get("section") or ""))
        if section not in SECTION_CONFIGS:
            continue
        table_rows = table.get("rows") or []
        if not isinstance(table_rows, list):
            continue
        rows.extend(_table_to_rows(table_rows, section=section, as_of=as_of, source_url=source_url))
    return _dedupe_rows(rows)


def _table_to_rows(table_rows: list[list[str]], *, section: str, as_of: date, source_url: str) -> list[dict[str, str]]:
    header_index = _find_header(table_rows)
    if header_index is None:
        return []
    headers = [_normalize_header(cell) for cell in table_rows[header_index]]
    rows: list[dict[str, str]] = []
    for values in table_rows[header_index + 1:]:
        raw = {headers[index]: values[index] if index < len(values) else "" for index in range(len(headers)) if headers[index]}
        normalized = _normalize_source_row(raw, section=section, as_of=as_of, source_url=source_url)
        if normalized:
            rows.append(normalized)
    return rows


def _find_header(rows: list[list[str]]) -> int | None:
    for index, row in enumerate(rows):
        headers = {_normalize_header(cell) for cell in row}
        if "code" in headers and "name" in headers and "source_market" in headers:
            return index
    return None


def _normalize_header(value: str) -> str:
    text = _clean_text(value).lower()
    if text in {"銘柄コード", "コード", "code", "ticker"}:
        return "code"
    if text in {"名称", "銘柄名", "name"}:
        return "name"
    if text in {"概要", "会社概要", "description"}:
        return "description"
    if text in {"市場", "market"}:
        return "source_market"
    if "経費率" in text or "信託報酬" in text or "expense" in text:
        return "expense_ratio_pct"
    if "運用会社" in text or "management" in text:
        return "management_company"
    if "nisa" in text and "成長" in text:
        return "nisa_growth"
    if "ファクト" in text:
        return "fact_sheet"
    return text


def _normalize_source_row(raw: dict[str, str], *, section: str, as_of: date, source_url: str) -> dict[str, str] | None:
    local_symbol = _normalize_local_symbol(raw.get("code", ""))
    name = _clean_text(raw.get("name", ""))
    if not local_symbol or not name:
        return None
    config = SECTION_CONFIGS[section]
    source_market = _clean_text(raw.get("source_market", "")) or config.default_exchange
    exchange = _exchange(section, source_market)
    symbol = _internal_symbol(section, local_symbol, exchange)
    yahoo_symbol, yahoo_note = _best_effort_yahoo_symbol(section, local_symbol, exchange)
    description = _clean_text(raw.get("description", ""))
    expense_ratio_pct = _normalize_percent(raw.get("expense_ratio_pct", ""))
    nisa_growth_status, nisa_growth_verified, nisa_growth_eligible = _nisa_growth_fields(raw.get("nisa_growth", ""))
    asset_class = _asset_class(name, description)
    region_exposure = _region_exposure(section, name, description)
    index_family = _index_family(section, name, description, asset_class, region_exposure)
    is_leveraged = _bool_text(_is_leveraged(name, description))
    is_inverse = _bool_text(_is_inverse(name, description))
    sector, theme, tags = _classification(asset_class, index_family, region_exposure, name, description, is_leveraged == "true", is_inverse == "true")
    complexity = _complexity(asset_class, is_leveraged == "true", is_inverse == "true", name, description)
    risk_band = _risk_band(asset_class, config.country_risk_band, is_leveraged == "true", is_inverse == "true", name, description)
    reasons = ["sbi_official_overseas_etf_list_imported"]
    if yahoo_note:
        reasons.append(yahoo_note)
    if not expense_ratio_pct:
        reasons.append("missing_expense_ratio")
    if asset_class == "equity" and not region_exposure:
        reasons.append("region_exposure_requires_review")
    if is_leveraged == "true" or is_inverse == "true":
        reasons.append("leveraged_or_inverse_etf")
    if "single_stock" == index_family:
        reasons.append("single_stock_etf")
    data_quality = "WARN" if reasons != ["sbi_official_overseas_etf_list_imported"] else "OK"
    now = datetime.now().astimezone().isoformat()
    nisa_category = "growth" if nisa_growth_eligible == "true" else ("none" if nisa_growth_eligible == "false" else "unknown")
    return {
        "symbol": symbol,
        "name": name,
        "market": config.market,
        "asset_type": "etf",
        "currency": config.currency,
        "broker": "sbi_securities",
        "tradability": "tradable",
        "nisa_category": nisa_category,
        "investment_style": "both",
        "is_sbi_supported": "true",
        "is_active": "true",
        "is_leveraged": is_leveraged,
        "is_inverse": is_inverse,
        "theme": theme,
        "sector": sector,
        "aliases": _aliases(local_symbol, name, description, raw.get("management_company", ""), source_market),
        "dividend_category": _dividend_category(name, description),
        "market_cap_tier": "",
        "index_family": index_family,
        "expense_ratio_pct": expense_ratio_pct,
        "complexity": complexity,
        "tags": _normalize_tags(tags),
        "data_quality": data_quality,
        "risk_band": risk_band,
        "metadata_source": "sbi_overseas_etf",
        "metadata_as_of": as_of.isoformat(),
        "metadata_updated_at": now,
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
        "asset_class": asset_class,
        "region_exposure": region_exposure,
        "is_hedged": "unknown",
        "smai_theme_tags": _normalize_tags(tags),
        "foreign_data_quality": data_quality,
        "foreign_data_quality_reasons": ";".join(reasons),
        "sbi_foreign_tradability": "tradable",
        "sbi_foreign_tradability_as_of": as_of.isoformat(),
        "sbi_foreign_tradability_source": "sbi_overseas_etf",
        "sbi_tradability_status": "confirmed",
        "sbi_tradability_verified": "true",
        "sbi_tradability_as_of": as_of.isoformat(),
        "sbi_tradability_source": "sbi_overseas_etf",
        "nisa_growth_status": nisa_growth_status,
        "nisa_growth_verified": nisa_growth_verified,
        "nisa_growth_eligible": nisa_growth_eligible,
        "nisa_growth_as_of": as_of.isoformat(),
        "nisa_growth_source": "sbi_overseas_etf",
        "nisa_tsumitate_status": "not_supported",
        "nisa_tsumitate_verified": "true",
        "nisa_tsumitate_as_of": as_of.isoformat(),
        "nisa_tsumitate_source": "sbi_overseas_etf",
        "nisa_tsumitate_eligible": "false",
        "source_section": section,
        "source_market": source_market,
        "source_description": description,
        "source_expense_ratio_pct": expense_ratio_pct,
        "source_management_company": _clean_text(raw.get("management_company", "")),
        "source_nisa_growth": _clean_text(raw.get("nisa_growth", "")),
        "source_url": source_url,
    }


def _canonical_section(section: str) -> str:
    text = _clean_text(section)
    for key in SECTION_CONFIGS:
        if key in text:
            return key
    return text


def _exchange(section: str, source_market: str) -> str:
    text = source_market.upper().replace(" ", "")
    if section == "米国ETF":
        if "NASDAQ" in text:
            return "NASDAQ"
        if "CBOE" in text:
            return "Cboe"
        if "NYSE" in text:
            return "NYSEARCA" if "ARCA" in text else "NYSE"
        return "NYSEARCA"
    if section == "中国ETF":
        return "HKEX"
    if section == "韓国ETF":
        return "KOSDAQ" if "KOSDAQ" in text else "KOSPI"
    if section == "シンガポールETF":
        return "SGX"
    return source_market


def _internal_symbol(section: str, local_symbol: str, exchange: str) -> str:
    if section == "米国ETF":
        return local_symbol
    if section == "中国ETF":
        return f"{local_symbol.zfill(5)}.HK" if local_symbol.isdigit() else f"{local_symbol}.HK"
    if section == "韓国ETF":
        return f"{local_symbol.zfill(6)}{'.KQ' if exchange == 'KOSDAQ' else '.KS'}"
    if section == "シンガポールETF":
        return f"{local_symbol}.SI"
    return local_symbol


def _best_effort_yahoo_symbol(section: str, local_symbol: str, exchange: str) -> tuple[str, str]:
    normalized_local_symbol = local_symbol.strip().upper()
    override = SBI_OVERSEAS_ETF_YAHOO_SYMBOL_OVERRIDES.get(section, {}).get(
        normalized_local_symbol
    )
    if override:
        return override, ""
    if section == "米国ETF":
        return local_symbol, ""
    if section == "中国ETF" and local_symbol.isdigit():
        return f"{int(local_symbol):04d}.HK", ""
    if section == "韓国ETF":
        return f"{local_symbol.zfill(6)}{'.KQ' if exchange == 'KOSDAQ' else '.KS'}", ""
    if section == "シンガポールETF":
        return f"{local_symbol}.SI", "yahoo_symbol_requires_review"
    return local_symbol, "yahoo_symbol_requires_review"


def _asset_class(name: str, description: str) -> str:
    text = f"{name} {description}".lower()
    if any(k in text for k in ["債券", "国債", "社債", "bond", "treasury", "debt", "loan", "ローン"]):
        return "bond"
    if any(k in text for k in ["reit", "リート", "不動産投資信託", "不動産"]):
        return "reit"
    if any(k in text for k in ["gold", "金 ", "ゴールド", "silver", "シルバー", "原油", "oil", "天然ガス", "gas", "commodity", "コモディティ"]):
        return "commodity"
    if any(k in text for k in ["通貨", "currency", "ドル", "円", "為替"]):
        return "currency"
    return "equity"


def _region_exposure(section: str, name: str, description: str) -> str:
    text = f"{name} {description}".lower()
    if section == "中国ETF":
        if "ベトナム" in text or "vietnam" in text:
            return "vietnam"
        return "china"
    if section == "韓国ETF":
        return "korea"
    if section == "シンガポールETF":
        if "asia" in text or "アジア" in text:
            return "asia_pacific"
        return "singapore"
    if any(k in text for k in ["s&p 500", "sp 500", "s&p500", "nasdaq", "米国", "us ", "usa", "u.s.", "nyse"]):
        return "us"
    if any(k in text for k in ["global", "world", "グローバル", "世界", "acwi"]):
        return "global"
    if any(k in text for k in ["emerging", "新興国", "エマージング"]):
        return "emerging"
    if any(k in text for k in ["developed", "先進国", "msci world", "除く米国"]):
        return "developed"
    if any(k in text for k in ["china", "中国", "香港", "hang seng", "ハンセン"]):
        return "china"
    if any(k in text for k in ["india", "インド"]):
        return "india"
    if any(k in text for k in ["japan", "日本"]):
        return "jp"
    if any(k in text for k in ["europe", "euro", "欧州", "ユーロ"]):
        return "europe"
    if any(k in text for k in ["africa", "アフリカ"]):
        return "africa"
    if any(k in text for k in ["latin", "ブラジル", "brazil", "南米"]):
        return "latin_america"
    return "global"


def _index_family(section: str, name: str, description: str, asset_class: str, region_exposure: str) -> str:
    text = f"{name} {description}".lower()
    if _is_single_stock(text):
        return "single_stock"
    if asset_class in {"bond", "reit", "commodity", "currency"}:
        return asset_class
    if any(k in text for k in ["s&p 500", "sp 500", "s&p500"]):
        return "sp500"
    if "nasdaq" in text:
        return "nasdaq100"
    if any(k in text for k in ["dow", "ダウ"]):
        return "dow_jones"
    if any(k in text for k in ["msci world", "先進国"]):
        return "msci_world"
    if any(k in text for k in ["acwi", "all country"]):
        return "acwi"
    if any(k in text for k in ["emerging", "新興国", "エマージング"]):
        return "emerging"
    if region_exposure == "china":
        return "china"
    if region_exposure == "india":
        return "india"
    if region_exposure == "jp":
        return "japan_equity"
    if region_exposure == "singapore":
        return "singapore_equity"
    if any(k in text for k in ["sector", "セクター", "ヘルスケア", "テクノロジー", "金融", "エネルギー", "公益", "不動産", "生活必需品", "一般消費財"]):
        return "sector"
    return "active" if "アクティブ" in text or "active" in text else ""


def _classification(asset_class: str, index_family: str, region_exposure: str, name: str, description: str, leveraged: bool, inverse: bool) -> tuple[str, str, str]:
    text = f"{name} {description}".lower()
    tags = ["index"]
    sector = "index"
    theme = "index"
    if asset_class == "bond":
        tags.append("bond"); theme = "bond"
    elif asset_class == "reit":
        tags.extend(["reit", "real_estate"]); theme = "reit"
    elif asset_class == "commodity":
        tags.append("commodity"); theme = "commodity"
    elif asset_class == "currency":
        tags.append("commodity"); theme = "currency"
    elif any(k in text for k in ["dividend", "配当", "高配当", "インカム", "income"]):
        # `theme` is a core enum used by Ranking filters; dividend/high-dividend
        # are represented as tags/dividend_category instead of a theme value.
        tags.extend(["dividend", "high_dividend"]); theme = "balanced"
    elif any(k in text for k in ["technology", "テクノロジー", "ai", "ビッグデータ", "半導体", "semiconductor"]):
        tags.append("technology"); theme = "technology"
    elif any(k in text for k in ["health", "ヘルスケア", "バイオ", "biotech"]):
        tags.append("healthcare"); theme = "healthcare"
    elif any(k in text for k in ["energy", "エネルギー", "原油", "oil", "gas"]):
        tags.append("energy"); theme = "energy"
    elif any(k in text for k in ["financial", "金融", "bank"]):
        tags.append("financial"); theme = "financial"
    elif any(k in text for k in ["consumer", "消費", "生活必需品"]):
        tags.append("consumer"); theme = "consumer"
    if leveraged or inverse:
        tags.append("trading")
    if _expense_low(text):
        tags.append("low_cost")
    return sector, theme, ",".join(tags)


def _complexity(asset_class: str, leveraged: bool, inverse: bool, name: str, description: str) -> str:
    text = f"{name} {description}".lower()
    if leveraged or inverse or _is_single_stock(text) or "カバード" in text or "covered call" in text:
        return "advanced"
    if asset_class in {"bond", "reit", "commodity", "currency"}:
        return "standard"
    if any(k in text for k in ["テーマ", "theme", "ai", "半導体", "biotech", "fang"]):
        return "thematic"
    return "standard"


def _risk_band(asset_class: str, country_risk_band: str, leveraged: bool, inverse: bool, name: str, description: str) -> str:
    text = f"{name} {description}".lower()
    if leveraged or inverse or _is_single_stock(text):
        return "HIGH"
    if asset_class == "bond":
        return "MEDIUM" if any(k in text for k in ["high yield", "ハイイールド", "新興国", "emerging", "レバレッジド"] ) else "LOW"
    if asset_class in {"commodity", "currency"}:
        return "MEDIUM"
    if country_risk_band == "HIGH":
        return "HIGH"
    return "MEDIUM"


def _is_leveraged(name: str, description: str) -> bool:
    text = f"{name} {description}".lower()
    return bool(re.search(r"\b[23]倍\b|ブル\s*[23]|[23]x|200%|300%|レバレッジ|leveraged|bull", text))


def _is_inverse(name: str, description: str) -> bool:
    text = f"{name} {description}".lower()
    return any(k in text for k in ["ベア", "インバース", "inverse", "bear", "マイナス", "opposite", "逆数"])


def _is_single_stock(text: str) -> bool:
    return bool(re.search(r"\b[a-z]{1,5}\)の日々のパフォーマンス|普通株式の日々のパフォーマンス|single stock", text, flags=re.IGNORECASE))


def _expense_low(text: str) -> bool:
    return False


def _dividend_category(name: str, description: str) -> str:
    text = f"{name} {description}".lower()
    if any(k in text for k in ["高配当", "high dividend", "superdividend"]):
        return "high_dividend"
    if any(k in text for k in ["配当", "dividend", "income", "インカム"]):
        return "dividend"
    return "none"


def _nisa_growth_fields(value: str) -> tuple[str, str, str]:
    """Return (confirmation_status, verified_bool, eligibility_bool).

    The main symbol schema uses confirmation statuses such as confirmed/unknown,
    while the eligibility itself is stored in nisa_growth_eligible.
    """
    text = _clean_text(value)
    if "〇" in text or "○" in text or text.lower() in {"yes", "true", "eligible"}:
        return "confirmed", "true", "true"
    if text in {"-", "－", "×"}:
        return "confirmed", "true", "false"
    return "unknown", "false", "unknown"


def _normalize_local_symbol(value: str) -> str:
    text = _clean_text(value).upper().replace("$", "")
    text = text.split()[0] if text else ""
    return re.sub(r"[^0-9A-Z-]", "", text)


def _normalize_percent(value: str) -> str:
    text = _clean_text(value).replace("％", "%")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return match.group(0) if match else ""


def _aliases(*values: str) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for value in values:
        for part in re.split(r"[,;/]", value or ""):
            cleaned = _clean_text(part)
            if cleaned and cleaned not in seen:
                parts.append(cleaned)
                seen.add(cleaned)
    return ";".join(parts[:8])


def _normalize_tags(value: str) -> str:
    allowed = {
        "automotive", "balanced", "bank", "bond", "commodity", "communication", "consumer", "dividend",
        "energy", "financial", "growth", "healthcare", "high_dividend", "industrial", "index", "installment",
        "insurance", "lower_risk", "low_cost", "materials", "quality", "real_estate", "reit", "semiconductor",
        "technology", "trading", "utilities", "value",
    }
    tags: list[str] = []
    for raw in re.split(r"[,;]", value or ""):
        tag = raw.strip()
        if tag in allowed and tag not in tags:
            tags.append(tag)
    return ",".join(tags or ["index"])


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _clean_text(value: object) -> str:
    text = str(value or "")
    text = text.replace("\u3000", " ").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _download_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read()
    for encoding in ("shift_jis", "cp932", "utf-8"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _counts(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = value or ""
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _duplicates(values: Iterable[str]) -> set[str]:
    seen: set[str] = set()
    dupes: set[str] = set()
    for value in values:
        key = value.strip().upper()
        if not key:
            continue
        if key in seen:
            dupes.add(key)
        seen.add(key)
    return dupes


def _dedupe_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    deduped: list[dict[str, str]] = []
    for row in rows:
        key = row["symbol"].upper()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _validation_errors(rows: Sequence[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    symbols = [row.get("symbol", "") for row in rows]
    for symbol in sorted(_duplicates(symbols)):
        errors.append(f"duplicate symbol: {symbol}")
    for index, row in enumerate(rows, start=2):
        for key in ("symbol", "name", "market", "asset_type", "currency", "yahoo_symbol"):
            if not row.get(key, "").strip():
                errors.append(f"row {index}: missing {key}")
        if row.get("asset_type") != "etf":
            errors.append(f"row {index}: asset_type must be etf")
        if row.get("risk_band") not in {"LOW", "MEDIUM", "HIGH"}:
            errors.append(f"row {index}: invalid risk_band={row.get('risk_band')}")
        if row.get("complexity") not in {"beginner", "standard", "advanced", "thematic"}:
            errors.append(f"row {index}: invalid complexity={row.get('complexity')}")
        if row.get("nisa_growth_status") not in {"confirmed", "estimated", "unknown", "not_supported"}:
            errors.append(f"row {index}: invalid nisa_growth_status={row.get('nisa_growth_status')}")
        if row.get("nisa_tsumitate_status") not in {"confirmed", "estimated", "unknown", "not_supported"}:
            errors.append(f"row {index}: invalid nisa_tsumitate_status={row.get('nisa_tsumitate_status')}")
    return errors[:200]


def _coverage_report(base_csv: Path, source_rows: Sequence[dict[str, str]]) -> dict[str, Any]:
    existing_rows: list[dict[str, str]] = []
    with base_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        existing_rows = list(reader)
    existing_by_symbol = {row.get("symbol", "").strip().upper(): row for row in existing_rows if row.get("symbol", "").strip()}
    source_symbols = [row["symbol"].strip().upper() for row in source_rows]
    existing = [symbol for symbol in source_symbols if symbol in existing_by_symbol]
    missing = [symbol for symbol in source_symbols if symbol not in existing_by_symbol]
    conflicts = [
        symbol
        for symbol in existing
        if (existing_by_symbol[symbol].get("asset_type", "").strip().lower() not in {"etf", ""})
    ]
    return {
        "base_rows": len(existing_rows),
        "source_rows": len(source_rows),
        "existing_rows": len(existing),
        "missing_rows": len(missing),
        "coverage_pct": round((len(existing) / len(source_rows) * 100), 2) if source_rows else 0.0,
        "conflicting_existing_symbols": conflicts[:100],
        "missing_symbol_sample": missing[:100],
        "existing_symbol_sample": existing[:100],
    }


def _write_csv(path: Path, rows: Sequence[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    raise SystemExit(main())
