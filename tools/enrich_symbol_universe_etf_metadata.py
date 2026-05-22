from __future__ import annotations

# ruff: noqa: E402,I001

import argparse
import csv
import json
import sys
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SYMBOL_UNIVERSE_CSV = PROJECT_ROOT / "data" / "marketdata" / "symbol_universe.csv"
DEFAULT_MANIFEST_PATH = (
    PROJECT_ROOT / "data" / "marketdata" / "symbol_universe_etf_metadata_enrichment_manifest.json"
)
DEFAULT_OVERRIDE_CSV = (
    PROJECT_ROOT / "data" / "marketdata" / "symbol_universe_etf_metadata_overrides.csv"
)
ENRICHMENT_FIELDNAMES = ("yahoo_symbol",)
OVERRIDE_COLUMNS = (
    "yahoo_symbol",
    "index_family",
    "complexity",
    "is_leveraged",
    "is_inverse",
    "theme",
    "management_style",
)

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.marketdata.symbol_universe_source_build import (  # noqa: E402
    infer_index_family_for_text,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Enrich deterministic ETF metadata in symbol_universe.csv."
    )
    parser.add_argument("--csv", type=Path, default=DEFAULT_SYMBOL_UNIVERSE_CSV)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--overrides", type=Path, default=DEFAULT_OVERRIDE_CSV)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    rows, fieldnames = _read_rows(args.csv)
    overrides = _read_overrides(args.overrides)
    fieldnames = _enrichment_fieldnames(fieldnames)
    result = enrich_etf_metadata(rows, overrides=overrides)
    manifest = build_manifest(result, csv_path=args.csv)

    if args.write:
        _write_rows(args.csv, fieldnames, rows)
        args.manifest.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    print(
        json.dumps(
            {**manifest, "dry_run": not args.write},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _read_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return (
            [
                {key: "" if value is None else str(value).strip() for key, value in row.items()}
                for row in reader
            ],
            list(reader.fieldnames or []),
        )


def _write_rows(
    path: Path,
    fieldnames: Sequence[str],
    rows: Sequence[dict[str, str]],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _read_overrides(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    rows, _ = _read_rows(path)
    return {row["symbol"].strip().upper(): row for row in rows if row.get("symbol", "").strip()}


def _enrichment_fieldnames(fieldnames: Sequence[str]) -> list[str]:
    resolved = list(fieldnames)
    for fieldname in ENRICHMENT_FIELDNAMES:
        if fieldname not in resolved:
            resolved.append(fieldname)
    return resolved


def enrich_etf_metadata(
    rows: Sequence[dict[str, str]],
    *,
    overrides: dict[str, dict[str, str]] | None = None,
) -> list[dict[str, object]]:
    changes: list[dict[str, object]] = []
    override_rows = overrides or {}
    for row in rows:
        if row.get("asset_type") != "etf":
            continue

        before = dict(row)
        changed_fields: list[str] = []
        override = override_rows.get(row.get("symbol", "").strip().upper(), {})
        for field in OVERRIDE_COLUMNS:
            value = override.get(field, "").strip()
            if value and row.get(field, "") != value:
                row[field] = value
                changed_fields.append(field)

        if not row.get("index_family", "").strip():
            inferred_index = infer_etf_index_family(row)
            if inferred_index:
                row["index_family"] = inferred_index
                changed_fields.append("index_family")

        corrected_expense_ratio = corrected_yahoo_expense_ratio_pct(row)
        if corrected_expense_ratio:
            row["expense_ratio_pct"] = corrected_expense_ratio
            changed_fields.append("expense_ratio_pct")

        if changed_fields:
            changes.append(
                {
                    "symbol": row.get("symbol", ""),
                    "name": row.get("name", ""),
                    "changed_fields": changed_fields,
                    "before": {field: before.get(field, "") for field in changed_fields},
                    "after": {field: row.get(field, "") for field in changed_fields},
                }
            )
    return changes


def infer_etf_index_family(row: dict[str, str]) -> str:
    return infer_index_family_for_text(
        row.get("index_family", ""),
        " ".join(
            [
                row.get("symbol", ""),
                row.get("name", ""),
                row.get("aliases", ""),
                row.get("theme", ""),
                row.get("tags", ""),
            ]
        ),
    )


def corrected_yahoo_expense_ratio_pct(row: dict[str, str]) -> str:
    if row.get("metadata_source") != "yahoo":
        return ""
    if row.get("asset_type") != "etf":
        return ""

    raw_value = row.get("expense_ratio_pct", "").strip()
    if not raw_value:
        return ""
    try:
        value = Decimal(raw_value)
    except InvalidOperation:
        return ""
    if value <= Decimal("1"):
        return ""

    corrected = (value / Decimal("100")).quantize(Decimal("0.0001")).normalize()
    return format(corrected, "f")


def build_manifest(
    changes: Sequence[dict[str, object]],
    *,
    csv_path: Path,
) -> dict[str, object]:
    changed_fields = Counter(
        field
        for change in changes
        for field in change.get("changed_fields", [])
        if isinstance(field, str)
    )
    index_family_updates = Counter(
        str(change["after"]["index_family"])
        for change in changes
        if "index_family" in change.get("changed_fields", [])
    )
    return {
        "operation": "symbol_universe_etf_metadata_enrichment",
        "csv": str(csv_path),
        "changed_rows": len(changes),
        "changed_columns": dict(changed_fields),
        "index_family_updates": dict(index_family_updates),
        "expense_ratio_scale_corrections": changed_fields.get("expense_ratio_pct", 0),
        "changed_symbol_sample": [str(change.get("symbol", "")) for change in changes[:50]],
    }


if __name__ == "__main__":
    raise SystemExit(main())
