from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_CSV_PATH = PROJECT_ROOT / "data" / "marketdata" / "symbol_universe.csv"
DEFAULT_MANIFEST_PATH = (
    PROJECT_ROOT / "data" / "marketdata" / "symbol_universe_import_manifest.json"
)

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.marketdata.symbol_universe_import import (  # noqa: E402
    SymbolUniverseImportDefaults,
    merge_symbol_universe_source_rows,
    symbol_universe_import_fieldnames,
    symbol_universe_source_profile,
    symbol_universe_source_profile_names,
)
from ui.symbol_universe import validate_symbol_universe_rows  # noqa: E402


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import a local curated source CSV into symbol_universe.csv."
    )
    parser.add_argument("--base-csv", type=Path, default=DEFAULT_BASE_CSV_PATH)
    parser.add_argument("--source-csv", type=Path, required=True)
    parser.add_argument("--source-name")
    parser.add_argument(
        "--source-profile",
        choices=symbol_universe_source_profile_names(),
        help="Apply named defaults for common source CSVs.",
    )
    parser.add_argument("--default-market", default="")
    parser.add_argument("--default-asset-type", default="")
    parser.add_argument("--default-currency", default="")
    parser.add_argument("--symbol-suffix", default="")
    parser.add_argument("--as-of", type=_parse_date, default=date.today())
    parser.add_argument(
        "--updated-at",
        type=_parse_datetime,
        default=datetime.now().astimezone(),
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument(
        "--update-existing",
        action="store_true",
        help="Update existing symbols with non-empty source values. Defaults to append-only.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write proposed CSV and manifest. Without this flag the command is a dry-run.",
    )
    args = parser.parse_args(argv)

    base_fieldnames, existing_rows = _read_csv(args.base_csv)
    _, source_rows = _read_csv(args.source_csv)
    write_fieldnames = _write_fieldnames(base_fieldnames)
    profile = symbol_universe_source_profile(args.source_profile) if args.source_profile else None
    defaults = _import_defaults(args, profile)
    source_name = args.source_name or (profile.source_name if profile else "curated_csv")
    validation_before = validate_symbol_universe_rows(
        existing_rows,
        fieldnames=write_fieldnames,
    )

    preview_result = merge_symbol_universe_source_rows(
        existing_rows,
        source_rows,
        source_name=source_name,
        as_of=args.as_of,
        updated_at=args.updated_at,
        defaults=defaults,
        update_existing=args.update_existing,
        dry_run=not args.write,
        validation_before=validation_before,
    )
    validation_after = validate_symbol_universe_rows(
        preview_result.rows,
        fieldnames=write_fieldnames,
    )
    result = merge_symbol_universe_source_rows(
        existing_rows,
        source_rows,
        source_name=source_name,
        as_of=args.as_of,
        updated_at=args.updated_at,
        defaults=defaults,
        update_existing=args.update_existing,
        dry_run=not args.write,
        validation_before=validation_before,
        validation_after=validation_after,
    )

    if args.write and result.manifest["validation_after"]["errors"]:
        print(json.dumps(result.manifest, ensure_ascii=False, indent=2, sort_keys=True))
        print("Refusing to write because validation_after has errors.", file=sys.stderr)
        return 2

    if args.write:
        _write_csv(args.base_csv, result.rows, write_fieldnames)
        _write_manifest(args.manifest, result.manifest)

    print(json.dumps(result.manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _read_csv(path: Path) -> tuple[list[str], list[dict[str | None, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        rows = [
            {key: "" if value is None else str(value).strip() for key, value in raw_row.items()}
            for raw_row in reader
            if raw_row.get("symbol") or raw_row.get("ticker") or raw_row.get("code")
        ]
    return list(reader.fieldnames or []), rows


def _write_csv(
    path: Path,
    rows: Sequence[dict[str, str]],
    fieldnames: Sequence[str],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_manifest(path: Path, manifest: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _import_defaults(args, profile) -> SymbolUniverseImportDefaults:
    profile_defaults = profile.defaults if profile else SymbolUniverseImportDefaults()
    return SymbolUniverseImportDefaults(
        market=args.default_market or profile_defaults.market,
        asset_type=args.default_asset_type or profile_defaults.asset_type,
        currency=args.default_currency or profile_defaults.currency,
        symbol_suffix=args.symbol_suffix or profile_defaults.symbol_suffix,
        column_defaults=profile_defaults.column_defaults,
    )


def _write_fieldnames(base_fieldnames: Sequence[str]) -> list[str]:
    fieldnames = list(base_fieldnames)
    for column in symbol_universe_import_fieldnames():
        if column not in fieldnames:
            fieldnames.append(column)
    return fieldnames


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


if __name__ == "__main__":
    raise SystemExit(main())
