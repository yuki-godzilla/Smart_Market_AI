from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV_PATH = PROJECT_ROOT / "data" / "marketdata" / "symbol_universe.csv"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "data" / "marketdata" / "symbol_universe_manual_patch_report.json"
METADATA_COLUMNS = (
    "per",
    "pbr",
    "roe_pct",
    "dividend_yield_pct",
    "market_cap",
    "market_cap_tier",
    "average_volume",
    "expense_ratio_pct",
    "aum",
    "sector_gics",
    "industry_gics",
    "sector",
    "theme",
    "asset_class",
    "index_family",
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Apply a reviewed/manual metadata patch CSV to symbol_universe.csv."
    )
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV_PATH)
    parser.add_argument("--patch", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--as-of", type=_parse_date, default=date.today())
    parser.add_argument("--source", default="manual_review")
    parser.add_argument("--quality", default="reviewed")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    fieldnames, rows = _read_csv(args.csv)
    patch_rows = _read_patch(args.patch)
    new_rows, report = apply_patch_rows(
        rows,
        patch_rows,
        as_of=args.as_of,
        default_source=args.source,
        default_quality=args.quality,
        overwrite=args.overwrite,
    )
    report["operation"] = "symbol_universe_manual_metadata_patch"
    report["csv"] = _report_path(args.csv)
    report["patch"] = _report_path(args.patch)
    report["dry_run"] = not args.write
    report["updated_at"] = datetime.now().astimezone().isoformat()

    write_fieldnames = _write_fieldnames(fieldnames, new_rows)
    if args.write:
        _write_csv(args.csv, new_rows, write_fieldnames)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def apply_patch_rows(
    rows: Sequence[dict[str, str]],
    patch_rows: Sequence[dict[str, str]],
    *,
    as_of: date,
    default_source: str,
    default_quality: str,
    overwrite: bool,
) -> tuple[list[dict[str, str]], dict[str, object]]:
    new_rows = [dict(row) for row in rows]
    index_by_symbol = {
        row.get("symbol", "").strip().upper(): index
        for index, row in enumerate(new_rows)
        if row.get("symbol", "").strip()
    }
    changed_symbols: set[str] = set()
    changed_columns: set[str] = set()
    unknown_symbols: list[str] = []
    skipped_existing = 0

    for patch in patch_rows:
        symbol = patch.get("symbol", "").strip().upper()
        if not symbol:
            continue
        row_index = index_by_symbol.get(symbol)
        if row_index is None:
            unknown_symbols.append(symbol)
            continue
        row = new_rows[row_index]
        patch_source = patch.get("source", "").strip() or default_source
        patch_as_of = patch.get("as_of", "").strip() or as_of.isoformat()
        patch_quality = patch.get("quality", "").strip() or default_quality
        row_changed = False

        for column in METADATA_COLUMNS:
            value = patch.get(column, "").strip()
            if not value:
                continue
            if row.get(column, "").strip() and not overwrite:
                skipped_existing += 1
                continue
            if row.get(column, "") != value:
                row[column] = value
                row_changed = True
                changed_columns.add(column)
            if column in {"sector", "theme", "sector_gics", "industry_gics", "asset_class", "index_family"}:
                continue
            for suffix, suffix_value in (
                ("source", patch_source),
                ("as_of", patch_as_of),
                ("quality", patch_quality),
            ):
                provenance_column = f"{column}_{suffix}"
                if row.get(provenance_column, "") != suffix_value:
                    row[provenance_column] = suffix_value
                    row_changed = True
                    changed_columns.add(provenance_column)

        note = patch.get("note", "").strip()
        if note:
            reason = f"manual_patch:{note}"
            reasons = {part.strip() for part in row.get("data_quality_reasons", "").split(";") if part.strip()}
            if reason not in reasons:
                reasons.add(reason)
                row["data_quality_reasons"] = ";".join(sorted(reasons))
                row_changed = True
                changed_columns.add("data_quality_reasons")
        if row_changed:
            changed_symbols.add(symbol)

    return new_rows, {
        "total_rows": len(new_rows),
        "patch_rows": len(patch_rows),
        "changed_rows": len(changed_symbols),
        "changed_symbols_sample": sorted(changed_symbols)[:50],
        "changed_symbols_truncated": len(changed_symbols) > 50,
        "changed_columns": sorted(changed_columns),
        "unknown_symbols": unknown_symbols,
        "skipped_existing_cells": skipped_existing,
        "overwrite": overwrite,
    }


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        fieldnames = list(reader.fieldnames or [])
        rows = [
            {str(key): "" if value is None else str(value).strip() for key, value in row.items()}
            for row in reader
            if row.get("symbol")
        ]
    return fieldnames, rows


def _read_patch(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [
            {str(key): "" if value is None else str(value).strip() for key, value in row.items()}
            for row in csv.DictReader(file)
            if row.get("symbol")
        ]


def _write_csv(path: Path, rows: Sequence[dict[str, str]], fieldnames: Sequence[str]) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    tmp_path.replace(path)


def _write_fieldnames(fieldnames: Sequence[str], rows: Sequence[dict[str, str]]) -> list[str]:
    result = list(fieldnames)
    for row in rows:
        for column in row:
            if column not in result:
                result.append(column)
    for column in ("data_quality_reasons",):
        if column not in result:
            result.append(column)
    return result


def _report_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


if __name__ == "__main__":
    raise SystemExit(main())
