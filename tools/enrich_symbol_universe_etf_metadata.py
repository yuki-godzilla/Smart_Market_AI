from __future__ import annotations

# ruff: noqa: E402,I001

import argparse
import csv
import json
import sys
from collections import Counter
from collections.abc import Mapping
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
DEFAULT_SOURCE_DIR = PROJECT_ROOT / "data" / "marketdata" / "symbol_universe_sources"
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
NISA_FIELDNAMES = (
    "nisa_category",
    "nisa_growth_eligible",
    "nisa_tsumitate_eligible",
)
NISA_ELIGIBLE_CATEGORIES = {"growth", "both", "tsumitate"}
NISA_KNOWN_CATEGORIES = NISA_ELIGIBLE_CATEGORIES | {"none"}

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
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    rows, fieldnames = _read_rows(args.csv)
    overrides = _read_overrides(args.overrides)
    nisa_coverage = build_official_etf_nisa_coverage(args.source_dir)
    fieldnames = _enrichment_fieldnames(fieldnames)
    result = enrich_etf_metadata(
        rows,
        overrides=overrides,
        official_nisa_coverage=nisa_coverage,
    )
    manifest = build_manifest(result, csv_path=args.csv, rows=rows)

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
    official_nisa_coverage: Mapping[str, str] | None = None,
) -> list[dict[str, object]]:
    changes: list[dict[str, object]] = []
    override_rows = overrides or {}
    nisa_coverage = official_nisa_coverage or {}
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

        changed_fields.extend(apply_official_etf_nisa_coverage(row, coverage=nisa_coverage))

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


def build_official_etf_nisa_coverage(source_dir: Path) -> dict[str, str]:
    """Return ETF NISA categories confirmed by local official source CSVs.

    This intentionally uses only source coverage, not name inference. ETF rows
    found in a dated JPX/SBI official source but absent from dated NISA growth
    lists are treated as confirmed `none` for the current source snapshot.
    """

    coverage: dict[str, str] = {}
    if not source_dir.exists():
        return coverage

    for path in sorted(source_dir.glob("jpx_etf_*.csv")):
        if "seed" in path.name:
            continue
        rows, _ = _read_rows(path)
        if "nisa_growth" in path.name:
            for row in rows:
                _set_nisa_coverage_category(coverage, row.get("symbol", ""), "growth")
        else:
            for row in rows:
                _set_nisa_coverage_category(coverage, row.get("symbol", ""), "none")

    for path in sorted(source_dir.glob("nisa_eligibility_*.csv")):
        if "seed" in path.name:
            continue
        rows, _ = _read_rows(path)
        for row in rows:
            category = _known_nisa_category(row.get("nisa_category", ""))
            if category:
                _set_nisa_coverage_category(coverage, row.get("symbol", ""), category)

    for path in sorted(source_dir.glob("sbi_us_etf_*.csv")):
        if "seed" in path.name:
            continue
        rows, _ = _read_rows(path)
        for row in rows:
            category = _known_nisa_category(row.get("nisa_category", ""))
            _set_nisa_coverage_category(
                coverage,
                row.get("symbol", ""),
                category or "none",
            )

    return coverage


def apply_official_etf_nisa_coverage(
    row: dict[str, str],
    *,
    coverage: Mapping[str, str],
) -> list[str]:
    symbol = row.get("symbol", "").strip().upper()
    target_category = _known_nisa_category(coverage.get(symbol, ""))
    if not target_category:
        return []

    changed_fields: list[str] = []
    updates = {
        "nisa_category": target_category,
        **_nisa_flags_for_category(target_category),
    }
    for field, value in updates.items():
        current_value = row.get(field, "").strip()
        if current_value != value:
            row[field] = value
            changed_fields.append(field)
    return changed_fields


def _set_nisa_coverage_category(
    coverage: dict[str, str],
    symbol: str,
    category: str,
) -> None:
    resolved_symbol = symbol.strip().upper()
    resolved_category = _known_nisa_category(category)
    if not resolved_symbol or not resolved_category:
        return
    if resolved_category in NISA_ELIGIBLE_CATEGORIES or resolved_symbol not in coverage:
        coverage[resolved_symbol] = resolved_category


def _known_nisa_category(category: str) -> str:
    resolved = category.strip().lower()
    return resolved if resolved in NISA_KNOWN_CATEGORIES else ""


def _nisa_flags_for_category(category: str) -> dict[str, str]:
    if category == "growth":
        return {"nisa_growth_eligible": "true", "nisa_tsumitate_eligible": "false"}
    if category == "tsumitate":
        return {"nisa_growth_eligible": "false", "nisa_tsumitate_eligible": "true"}
    if category == "both":
        return {"nisa_growth_eligible": "true", "nisa_tsumitate_eligible": "true"}
    return {"nisa_growth_eligible": "false", "nisa_tsumitate_eligible": "false"}


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
    rows: Sequence[dict[str, str]] | None = None,
) -> dict[str, object]:
    changed_fields = Counter(field for change in changes for field in _changed_fields(change))
    index_family_updates = Counter(
        str(after["index_family"])
        for change in changes
        if "index_family" in _changed_fields(change)
        for after in [_change_after(change)]
        if "index_family" in after
    )
    manifest: dict[str, object] = {
        "operation": "symbol_universe_etf_metadata_enrichment",
        "csv": str(csv_path),
        "changed_rows": len(changes),
        "changed_columns": dict(changed_fields),
        "index_family_updates": dict(index_family_updates),
        "nisa_category_updates": changed_fields.get("nisa_category", 0),
        "expense_ratio_scale_corrections": changed_fields.get("expense_ratio_pct", 0),
        "changed_symbol_sample": [str(change.get("symbol", "")) for change in changes[:50]],
    }
    if rows is not None:
        manifest["post_update_summary"] = build_post_update_summary(rows)
    return manifest


def _changed_fields(change: Mapping[str, object]) -> list[str]:
    value = change.get("changed_fields", [])
    if not isinstance(value, list):
        return []
    return [field for field in value if isinstance(field, str)]


def _change_after(change: Mapping[str, object]) -> Mapping[str, object]:
    value = change.get("after", {})
    return value if isinstance(value, Mapping) else {}


def build_post_update_summary(rows: Sequence[dict[str, str]]) -> dict[str, object]:
    etf_rows = [row for row in rows if row.get("asset_type") == "etf"]
    return {
        "etf_rows": len(etf_rows),
        "etf_index_family_missing": sum(1 for row in etf_rows if not row.get("index_family")),
        "etf_nisa_category_counts": dict(
            Counter(row.get("nisa_category") or "(blank)" for row in etf_rows)
        ),
        "etf_nisa_unknown": sum(1 for row in etf_rows if row.get("nisa_category") == "unknown"),
    }


if __name__ == "__main__":
    raise SystemExit(main())
