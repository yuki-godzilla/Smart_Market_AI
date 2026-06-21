from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV_PATH = PROJECT_ROOT / "data" / "marketdata" / "symbol_universe.csv"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "data" / "marketdata" / "symbol_universe_quality_report.json"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.marketdata.symbol_metadata_schema import (  # noqa: E402
    METADATA_TIER_RANKING_FILTER,
    metadata_field_by_key,
)

DEFAULT_COVERAGE_COLUMNS = (
    "sector",
    "theme",
    "dividend_category",
    "dividend_yield_pct",
    "market_cap",
    "market_cap_tier",
    "index_family",
    "expense_ratio_pct",
    "asset_class",
    "average_volume",
    "aum",
    "complexity",
    "per",
    "pbr",
    "roe_pct",
    "consensus_rating",
    "risk_band",
    "nisa_category",
    "is_sbi_supported",
)

QUALITY_COVERAGE_FIELDS = {
    "per": "per",
    "pbr": "pbr",
    "roe": "roe_pct",
    "dividend_yield": "dividend_yield_pct",
    "market_cap": "market_cap",
    "market_cap_category": "market_cap_tier",
    "sector": "sector",
    "theme": "theme",
    "nisa": "nisa_category",
    # Use the explicit reliability status instead of is_sbi_supported so unknown
    # tradability is not reported as fully covered merely because a broker policy
    # flag exists.
    "sbi_tradability": "sbi_tradability_status",
    "etf_expense_ratio": "expense_ratio_pct",
    "etf_index_family": "index_family",
    "etf_asset_class": "asset_class",
}
STOCK_QUALITY_FIELDS = (
    "per",
    "pbr",
    "roe",
    "dividend_yield",
    "market_cap",
    "market_cap_category",
    "sector",
    "theme",
    "nisa",
    "sbi_tradability",
)
ETF_QUALITY_FIELDS = (
    "dividend_yield",
    "etf_expense_ratio",
    "etf_index_family",
    "etf_asset_class",
    "nisa",
    "sbi_tradability",
    "sector",
    "theme",
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Summarize symbol_universe.csv ranking metadata coverage."
    )
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--asset-type", default="")
    parser.add_argument("--market", default="")
    parser.add_argument("--metadata-source", default="")
    parser.add_argument(
        "--checked-at",
        type=_parse_datetime,
        default=datetime.now().astimezone(),
    )
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    rows = _read_rows(args.csv)
    selected_rows = _select_rows(
        rows,
        asset_type=args.asset_type,
        market=args.market,
        metadata_source=args.metadata_source,
    )
    report = build_metadata_coverage_report(
        selected_rows,
        checked_at=args.checked_at,
        csv_path=args.csv,
        filters={
            "asset_type": args.asset_type,
            "market": args.market,
            "metadata_source": args.metadata_source,
        },
    )
    if args.write:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def build_metadata_coverage_report(
    rows: Sequence[dict[str, str]],
    *,
    checked_at: datetime,
    csv_path: Path,
    filters: dict[str, str] | None = None,
) -> dict[str, object]:
    """Return a compact coverage report for data-side ranking metadata."""

    report = {
        "operation": "symbol_universe_metadata_coverage",
        "csv": _report_path(csv_path),
        "checked_at": checked_at.isoformat(),
        "filters": filters or {},
        "total_rows": len(rows),
        "columns": list(DEFAULT_COVERAGE_COLUMNS),
        "column_labels": _column_labels(DEFAULT_COVERAGE_COLUMNS),
        "overall": _coverage_for_rows(rows, DEFAULT_COVERAGE_COLUMNS),
        "by_asset_type": _group_coverage(rows, "asset_type"),
        "by_metadata_source": _group_coverage(rows, "metadata_source"),
        "by_asset_type_and_source": _multi_group_coverage(
            rows,
            ("asset_type", "metadata_source"),
        ),
    }
    report.update(
        {
            "total_symbols": len(rows),
            "by_region": _group_counts(rows, "market"),
            "by_product_type": _group_counts(rows, "asset_type"),
            "coverage": _named_coverage(rows),
            "coverage_by_product_type": _product_scope_coverage(rows),
            "sbi_tradability_status_breakdown": _group_counts(rows, "sbi_tradability_status"),
            "nisa_category_breakdown": _group_counts(rows, "nisa_category"),
        }
    )
    return report


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [
            {str(key): "" if value is None else str(value).strip() for key, value in row.items()}
            for row in csv.DictReader(file)
            if row.get("symbol")
        ]


def _report_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


def _select_rows(
    rows: Sequence[dict[str, str]],
    *,
    asset_type: str = "",
    market: str = "",
    metadata_source: str = "",
) -> list[dict[str, str]]:
    return [
        row
        for row in rows
        if (not asset_type or row.get("asset_type") == asset_type)
        and (not market or row.get("market") == market)
        and (not metadata_source or row.get("metadata_source") == metadata_source)
    ]


def _coverage_for_rows(
    rows: Sequence[dict[str, str]],
    columns: Sequence[str],
) -> dict[str, object]:
    total = len(rows)
    by_column = {}
    for column in columns:
        filled = sum(1 for row in rows if _has_metadata_value(row, column))
        by_column[column] = {
            "filled": filled,
            "missing": total - filled,
            "coverage": round(filled / total, 4) if total else 0,
        }
    return {
        "rows": total,
        "by_column": by_column,
    }


def _group_coverage(rows: Sequence[dict[str, str]], key: str) -> dict[str, object]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get(key) or "(blank)"].append(row)
    return {
        group_key: _coverage_for_rows(group_rows, DEFAULT_COVERAGE_COLUMNS)
        for group_key, group_rows in sorted(grouped.items())
    }


def _multi_group_coverage(
    rows: Sequence[dict[str, str]],
    keys: Sequence[str],
) -> list[dict[str, object]]:
    grouped: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row.get(key) or "(blank)" for key in keys)].append(row)
    return [
        {
            "group": {key: value for key, value in zip(keys, group_key, strict=True)},
            "coverage": _coverage_for_rows(group_rows, DEFAULT_COVERAGE_COLUMNS),
        }
        for group_key, group_rows in sorted(grouped.items())
    ]


def _group_counts(rows: Sequence[dict[str, str]], key: str) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[row.get(key) or "(blank)"] += 1
    return dict(sorted(counts.items()))


def _named_coverage(
    rows: Sequence[dict[str, str]],
    fields: Sequence[str] | None = None,
) -> dict[str, object]:
    selected_fields = fields or tuple(QUALITY_COVERAGE_FIELDS)
    return {name: _coverage_value(rows, QUALITY_COVERAGE_FIELDS[name]) for name in selected_fields}


def _product_scope_coverage(
    rows: Sequence[dict[str, str]],
) -> dict[str, dict[str, object]]:
    scopes = {
        "stock_jp": (
            [row for row in rows if row.get("asset_type") == "stock" and row.get("market") == "jp"],
            STOCK_QUALITY_FIELDS,
        ),
        "stock_us": (
            [row for row in rows if row.get("asset_type") == "stock" and row.get("market") == "us"],
            STOCK_QUALITY_FIELDS,
        ),
        "etf": (
            [row for row in rows if row.get("asset_type") == "etf"],
            ETF_QUALITY_FIELDS,
        ),
    }
    return {
        scope: {
            "total_symbols": len(scope_rows),
            "coverage": _named_coverage(scope_rows, fields),
        }
        for scope, (scope_rows, fields) in scopes.items()
    }


def _coverage_value(rows: Sequence[dict[str, str]], column: str) -> dict[str, object]:
    total = len(rows)
    filled = sum(1 for row in rows if _has_metadata_value(row, column))
    return {
        "filled": filled,
        "missing": total - filled,
        "coverage": round(filled / total, 4) if total else 0,
    }


def _column_labels(columns: Sequence[str]) -> dict[str, str]:
    return {
        column: field.label
        for column in columns
        if (field := metadata_field_by_key(column)) and field.tier == METADATA_TIER_RANKING_FILTER
    }


VALID_NONE_COLUMNS = {
    "nisa_category",
    "dividend_category",
    "distribution_policy",
}


def _has_metadata_value(row: dict[str, str], column: str) -> bool:
    value = (row.get(column) or "").strip().lower()
    if not value or value in {"n/a", "na", "null"}:
        return False
    if value == "unknown":
        return False
    if value == "none" and column not in VALID_NONE_COLUMNS:
        return False
    return True


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


if __name__ == "__main__":
    raise SystemExit(main())
