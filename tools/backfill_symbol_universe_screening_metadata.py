from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence, TypedDict, cast

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV_PATH = PROJECT_ROOT / "data" / "marketdata" / "symbol_universe.csv"
DEFAULT_MANIFEST_PATH = (
    PROJECT_ROOT / "data" / "marketdata" / "symbol_universe_screening_backfill_manifest.json"
)
DEFAULT_SOURCE_DIR = PROJECT_ROOT / "data" / "marketdata" / "symbol_universe_sources"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.marketdata.symbol_metadata_refresh import (  # noqa: E402
    METADATA_PROVENANCE_FIELDS,
)
from backend.marketdata.symbol_metadata_schema import (  # noqa: E402
    symbol_universe_optional_columns,
)
from ui.symbol_universe import validate_symbol_universe_rows  # noqa: E402

# This tool deliberately performs deterministic, local-only metadata materialization.
# It does not fetch live market data and never estimates financial numeric values.

THEME_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "semiconductor",
        (r"半導体", r"semiconductor", r"\bchip\b", r"gpu", r"nvidia", r"asml", r"tsmc"),
    ),
    (
        "automotive",
        (
            r"自動車",
            r"automotive",
            r"\bauto\b",
            r"toyota",
            r"トヨタ",
            r"honda",
            r"ホンダ",
            r"nissan",
            r"日産",
            r"mazda",
            r"マツダ",
            r"subaru",
            r"スバル",
            r"suzuki",
            r"スズキ",
            r"tesla",
            r"ford",
            r"general motors",
        ),
    ),
    (
        "trading",
        (
            r"商社",
            r"trading company",
            r"mitsubishi corp",
            r"三菱商事",
            r"mitsui & co",
            r"三井物産",
            r"itochu",
            r"伊藤忠",
            r"marubeni",
            r"丸紅",
            r"住友商事",
            r"toyota tsusho",
            r"豊田通商",
        ),
    ),
    ("bank", (r"銀行", r"\bbank\b", r"financial group", r"フィナンシャルグループ")),
    ("insurance", (r"保険", r"insurance", r"insurer")),
    (
        "communication",
        (
            r"通信",
            r"telecom",
            r"telecommunication",
            r"mobile",
            r"wireless",
            r"\bntt\b",
            r"kddi",
            r"softbank",
            r"ソフトバンク",
        ),
    ),
    (
        "utilities",
        (
            r"電力",
            r"electric power",
            r"utilities",
            r"utility",
            r"ガス",
            r"\bgas\b",
            r"osaka gas",
            r"tokyo gas",
        ),
    ),
    (
        "healthcare",
        (
            r"医薬",
            r"製薬",
            r"pharma",
            r"pharmaceutical",
            r"biotech",
            r"healthcare",
            r"medical",
        ),
    ),
    ("real_estate", (r"不動産", r"real estate", r"\breit\b", r"投資法人")),
    ("energy", (r"石油", r"資源", r"energy", r"\boil\b", r"exploration", r"drilling")),
    ("high_dividend", (r"高配当", r"high dividend")),
)

DIRECT_THEME_VALUES = {
    "technology",
    "communication",
    "financial",
    "consumer",
    "healthcare",
    "energy",
    "automotive",
    "trading",
    "industrial",
    "materials",
    "real_estate",
    "utilities",
    "semiconductor",
    "index",
    "bond",
    "reit",
    "commodity",
}

EQUITY_INDEX_FAMILIES = {
    "acwi",
    "china",
    "dividend",
    "dow_jones",
    "emerging",
    "india",
    "japan_equity",
    "jpx_nikkei400",
    "msci_world",
    "nasdaq100",
    "nikkei225",
    "sector",
    "singapore_equity",
    "single_stock",
    "small_us",
    "sp500",
    "style_factor",
    "topix",
    "total_us",
}
ASSET_CLASS_BY_INDEX_FAMILY = {
    **{index_family: "equity" for index_family in EQUITY_INDEX_FAMILIES},
    "bond": "bond",
    "commodity": "commodity",
    "currency": "currency",
    "reit": "reit",
}
REGION_EXPOSURE_BY_INDEX_FAMILY = {
    "sp500": "us",
    "nasdaq100": "us",
    "total_us": "us",
    "small_us": "us",
    "dow_jones": "us",
    "topix": "jp",
    "nikkei225": "jp",
    "jpx_nikkei400": "jp",
    "japan_equity": "jp",
    "acwi": "global",
    "msci_world": "developed",
    "emerging": "emerging",
    "china": "china",
    "india": "india",
    "singapore_equity": "singapore",
    "bond": "global",
    "commodity": "global",
    "currency": "global",
    "reit": "global",
}
OFFICIAL_NISA_SOURCES = {"fsa", "jpx_nisa_growth"}
ONE_TO_ONE_GICS_SECTOR_LABELS = {
    "communication": "Communication Services",
    "energy": "Energy",
    "financial": "Financials",
    "healthcare": "Health Care",
    "industrial": "Industrials",
    "materials": "Materials",
    "real_estate": "Real Estate",
    "technology": "Information Technology",
    "utilities": "Utilities",
}


class BackfillStats(TypedDict):
    changed_cells_by_column: dict[str, int]
    official_classification_rows: int
    theme_tagged_rows: int
    reliability_status_rows: int
    etf_classification_rows: int
    metric_provenance_rows: int


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize local screening metadata columns and deterministic theme tags "
            "for symbol_universe.csv. No live data is fetched."
        )
    )
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV_PATH)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--updated-at", type=_parse_datetime, default=datetime.now().astimezone())
    output_mode = parser.add_mutually_exclusive_group()
    output_mode.add_argument("--write", action="store_true")
    output_mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview deterministic backfill changes without writing files (default).",
    )
    args = parser.parse_args(argv)

    fieldnames, rows = _read_rows(args.csv)
    proposed_fieldnames = _materialized_fieldnames(fieldnames)
    proposed_rows = [
        {column: row.get(column, "") for column in proposed_fieldnames} for row in rows
    ]

    official_source_path, jpx_official_classifications = _load_jpx_official_classifications(
        args.source_dir
    )
    stats = _backfill_rows(
        proposed_rows,
        jpx_official_classifications=jpx_official_classifications,
    )
    validation_after = validate_symbol_universe_rows(
        cast(Sequence[dict[str | None, Any]], proposed_rows),
        fieldnames=proposed_fieldnames,
    )
    validation_errors = [issue for issue in validation_after if issue.get("severity") == "error"]
    manifest = {
        "operation": "symbol_universe_screening_metadata_backfill",
        "csv": _report_path(args.csv),
        "dry_run": not args.write,
        "updated_at": args.updated_at.isoformat(),
        "total_rows": len(proposed_rows),
        "added_columns": [column for column in proposed_fieldnames if column not in fieldnames],
        "changed_cells_by_column": dict(sorted(stats["changed_cells_by_column"].items())),
        "official_classification_source": (
            _report_path(official_source_path) if official_source_path else ""
        ),
        "official_classification_rows": stats["official_classification_rows"],
        "theme_tagged_rows": stats["theme_tagged_rows"],
        "reliability_status_rows": stats["reliability_status_rows"],
        "etf_classification_rows": stats["etf_classification_rows"],
        "metric_provenance_rows": stats["metric_provenance_rows"],
        "validation_after": {
            "total": len(validation_after),
            "errors": len(validation_errors),
            "warnings": len(validation_after) - len(validation_errors),
        },
    }

    if validation_errors:
        print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
        print("Refusing to write because validation_after has errors.", file=sys.stderr)
        return 2

    if args.write:
        _write_rows(args.csv, proposed_fieldnames, proposed_rows)
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        fieldnames = list(reader.fieldnames or [])
        rows = [
            {str(key): "" if value is None else str(value).strip() for key, value in row.items()}
            for row in reader
            if row.get("symbol")
        ]
    return fieldnames, rows


def _write_rows(path: Path, fieldnames: Sequence[str], rows: Sequence[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _materialized_fieldnames(fieldnames: Sequence[str]) -> list[str]:
    result = list(fieldnames)
    for column in symbol_universe_optional_columns():
        if column not in result:
            result.append(column)
    return result


def _backfill_rows(
    rows: Sequence[dict[str, str]],
    *,
    jpx_official_classifications: dict[str, dict[str, str]] | None = None,
) -> BackfillStats:
    changed_cells_by_column: defaultdict[str, int] = defaultdict(int)
    official_classification_rows = 0
    theme_tagged_rows = 0
    reliability_status_rows = 0
    etf_classification_rows = 0
    metric_provenance_rows = 0

    for row in rows:
        before = dict(row)
        _backfill_official_classification(
            row,
            jpx_official_classifications=jpx_official_classifications or {},
        )
        _backfill_reliability_status(row)
        _backfill_theme_tags(row)
        _backfill_etf_classification(row)
        _backfill_metric_provenance(row)

        changed_columns = [
            column for column, value in row.items() if before.get(column, "") != value
        ]
        for column in changed_columns:
            changed_cells_by_column[column] += 1
        if any(
            column in changed_columns for column in ("sector_gics", "tse_33_industry", "topix_17")
        ):
            official_classification_rows += 1
        if any(
            column in changed_columns
            for column in ("smai_theme_tags", "theme_confidence", "theme_source")
        ):
            theme_tagged_rows += 1
        if any(
            column.startswith(("sbi_tradability_", "nisa_growth_", "nisa_tsumitate_"))
            for column in changed_columns
        ):
            reliability_status_rows += 1
        if any(
            column in changed_columns for column in ("asset_class", "region_exposure", "is_hedged")
        ):
            etf_classification_rows += 1
        if any(column.endswith(("_source", "_as_of", "_quality")) for column in changed_columns):
            metric_provenance_rows += 1

    return {
        "changed_cells_by_column": dict(changed_cells_by_column),
        "official_classification_rows": official_classification_rows,
        "theme_tagged_rows": theme_tagged_rows,
        "reliability_status_rows": reliability_status_rows,
        "etf_classification_rows": etf_classification_rows,
        "metric_provenance_rows": metric_provenance_rows,
    }


def _load_jpx_official_classifications(
    source_dir: Path,
) -> tuple[Path | None, dict[str, dict[str, str]]]:
    source_paths = sorted(source_dir.glob("jpx_listed_stock_*.csv"))
    if not source_paths:
        return None, {}
    source_path = source_paths[-1]
    classifications: dict[str, dict[str, str]] = {}
    with source_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            code = (row.get("code") or row.get("symbol") or "").strip()
            if not code:
                continue
            symbol = code if code.upper().endswith(".T") else f"{code}.T"
            industry_33 = (
                row.get("source_industry_33") or row.get("tse_33_industry") or ""
            ).strip()
            topix_17 = (row.get("source_industry_17") or row.get("topix_17") or "").strip()
            if industry_33 or topix_17:
                classifications[symbol.upper()] = {
                    "tse_33_industry": industry_33,
                    "topix_17": topix_17,
                }
    return source_path, classifications


def _backfill_official_classification(
    row: dict[str, str],
    *,
    jpx_official_classifications: dict[str, dict[str, str]],
) -> None:
    symbol = row.get("symbol", "").strip().upper()
    if (
        row.get("market") == "jp"
        and row.get("asset_type") == "stock"
        and symbol in jpx_official_classifications
    ):
        classification = jpx_official_classifications[symbol]
        if not row.get("tse_33_industry", "").strip():
            row["tse_33_industry"] = classification.get("tse_33_industry", "")
        if not row.get("topix_17", "").strip():
            row["topix_17"] = classification.get("topix_17", "")

    if (
        row.get("market") == "us"
        and row.get("asset_type") == "stock"
        and not row.get("sector_gics", "").strip()
    ):
        sector_gics = ONE_TO_ONE_GICS_SECTOR_LABELS.get(row.get("sector", "").strip())
        if sector_gics:
            row["sector_gics"] = sector_gics


def _backfill_reliability_status(row: dict[str, str]) -> None:
    source = (row.get("metadata_source") or "symbol_universe_csv").strip()
    as_of = row.get("metadata_as_of", "").strip()
    normalized_source = source.lower()
    tradability = row.get("tradability", "").strip().lower()
    is_sbi_supported = row.get("is_sbi_supported", "").strip().lower()

    if not row.get("sbi_tradability_status", "").strip():
        if tradability == "not_tradable" or is_sbi_supported == "false":
            row["sbi_tradability_status"] = "not_supported"
        elif tradability == "tradable":
            row["sbi_tradability_status"] = "confirmed"
        elif is_sbi_supported == "true":
            row["sbi_tradability_status"] = "estimated"
        else:
            row["sbi_tradability_status"] = "unknown"
    if not row.get("sbi_tradability_verified", "").strip():
        row["sbi_tradability_verified"] = (
            "true"
            if row["sbi_tradability_status"] in {"confirmed", "not_supported"}
            and normalized_source.startswith("sbi_")
            else "false"
        )
    if not row.get("sbi_tradability_as_of", "").strip() and as_of:
        row["sbi_tradability_as_of"] = as_of
    if not row.get("sbi_tradability_source", "").strip() and source:
        row["sbi_tradability_source"] = source

    official_nisa = normalized_source in OFFICIAL_NISA_SOURCES
    nisa_category = row.get("nisa_category", "").strip().lower() or "unknown"
    _backfill_nisa_prefix(
        row,
        prefix="nisa_growth",
        eligible=nisa_category in {"growth", "both"},
        unsupported=nisa_category in {"none", "tsumitate"},
        official=official_nisa,
        source=source,
        as_of=as_of,
    )
    _backfill_nisa_prefix(
        row,
        prefix="nisa_tsumitate",
        eligible=nisa_category in {"tsumitate", "both"},
        unsupported=nisa_category in {"none", "growth"},
        official=official_nisa,
        source=source,
        as_of=as_of,
    )


def _backfill_nisa_prefix(
    row: dict[str, str],
    *,
    prefix: str,
    eligible: bool,
    unsupported: bool,
    official: bool,
    source: str,
    as_of: str,
) -> None:
    if not row.get(f"{prefix}_status", "").strip():
        if eligible:
            row[f"{prefix}_status"] = "confirmed" if official else "estimated"
        elif unsupported:
            row[f"{prefix}_status"] = "not_supported"
        else:
            row[f"{prefix}_status"] = "unknown"
    if not row.get(f"{prefix}_verified", "").strip():
        row[f"{prefix}_verified"] = (
            "true" if official and row[f"{prefix}_status"] != "unknown" else "false"
        )
    if not row.get(f"{prefix}_as_of", "").strip() and as_of:
        row[f"{prefix}_as_of"] = as_of
    if not row.get(f"{prefix}_source", "").strip() and source:
        row[f"{prefix}_source"] = source


def _backfill_theme_tags(row: dict[str, str]) -> None:
    existing_tags = _csv_values(row.get("smai_theme_tags", ""))
    tags = set(existing_tags)
    theme = row.get("theme", "").strip()
    sector = row.get("sector", "").strip()
    if theme in DIRECT_THEME_VALUES:
        tags.add(theme)
    if sector in DIRECT_THEME_VALUES and sector != theme:
        tags.add(sector)
    if row.get("asset_type") == "etf":
        index_family = row.get("index_family", "").strip()
        if index_family in DIRECT_THEME_VALUES:
            tags.add(index_family)
        if index_family:
            tags.add("index")
    if row.get("dividend_category") == "high_dividend":
        tags.add("high_dividend")

    searchable_text = _searchable_text(row)
    for tag, patterns in THEME_RULES:
        if any(re.search(pattern, searchable_text, flags=re.IGNORECASE) for pattern in patterns):
            tags.add(tag)

    if tags != existing_tags:
        row["smai_theme_tags"] = ",".join(sorted(tags))
        if not row.get("theme_confidence", "").strip():
            row["theme_confidence"] = "0.80"
        if not row.get("theme_source", "").strip():
            row["theme_source"] = "rule_backfill_v1"


def _searchable_text(row: dict[str, str]) -> str:
    fields = (
        "symbol",
        "name",
        "aliases",
        "theme",
        "sector",
        "sector_gics",
        "industry_gics",
        "subindustry_gics",
        "tse_33_industry",
        "topix_17",
        "tags",
        "index_family",
        "asset_type",
    )
    return " ".join(row.get(field, "") for field in fields).lower()


def _csv_values(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


def _backfill_etf_classification(row: dict[str, str]) -> None:
    if row.get("asset_type") != "etf":
        return
    index_family = row.get("index_family", "").strip()
    if not row.get("asset_class", "").strip():
        asset_class = ASSET_CLASS_BY_INDEX_FAMILY.get(index_family)
        if asset_class:
            row["asset_class"] = asset_class
    if not row.get("region_exposure", "").strip():
        region_exposure = REGION_EXPOSURE_BY_INDEX_FAMILY.get(index_family)
        if region_exposure:
            row["region_exposure"] = region_exposure
    if not row.get("is_hedged", "").strip():
        text = _searchable_text(row)
        row["is_hedged"] = (
            "true" if any(term in text for term in ("為替ヘッジ", "hedged")) else "unknown"
        )


def _backfill_metric_provenance(row: dict[str, str]) -> None:
    source = (row.get("metadata_source") or "symbol_universe_csv").strip()
    as_of = row.get("metadata_as_of", "").strip()
    quality = "confirmed" if source == "yahoo" else "estimated"
    for metric in METADATA_PROVENANCE_FIELDS:
        if not row.get(metric, "").strip():
            continue
        if not row.get(f"{metric}_source", "").strip():
            row[f"{metric}_source"] = source
        if as_of and not row.get(f"{metric}_as_of", "").strip():
            row[f"{metric}_as_of"] = as_of
        if not row.get(f"{metric}_quality", "").strip():
            row[f"{metric}_quality"] = "derived" if metric == "market_cap_tier" else quality


def _report_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


if __name__ == "__main__":
    raise SystemExit(main())
