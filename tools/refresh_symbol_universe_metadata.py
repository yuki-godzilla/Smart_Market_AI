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
DEFAULT_MANIFEST_PATH = PROJECT_ROOT / "data" / "marketdata" / "symbol_universe_manifest.json"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.marketdata.symbol_metadata_refresh import (  # noqa: E402
    METADATA_REFRESH_COLUMNS,
    create_symbol_metadata_provider,
    refresh_symbol_universe_metadata,
)
from ui.symbol_universe import validate_symbol_universe_rows  # noqa: E402


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Refresh symbol_universe.csv metadata with an explicit provider."
    )
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV_PATH)
    parser.add_argument("--provider", default="curated_csv")
    parser.add_argument("--as-of", type=_parse_date, default=date.today())
    parser.add_argument("--updated-at", type=_parse_datetime, default=datetime.now().astimezone())
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write proposed CSV and manifest. Without this flag the command is a dry-run.",
    )
    args = parser.parse_args(argv)

    fieldnames, rows = _read_symbol_universe_csv(args.csv)
    try:
        provider = create_symbol_metadata_provider(args.provider)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    validation_before = validate_symbol_universe_rows(rows, fieldnames=fieldnames)
    write_fieldnames = _write_fieldnames(fieldnames, rows)

    preview_result = refresh_symbol_universe_metadata(
        rows,
        provider=provider,
        as_of=args.as_of,
        updated_at=args.updated_at,
        dry_run=not args.write,
        validation_before=validation_before,
    )
    validation_after = validate_symbol_universe_rows(
        preview_result.rows,
        fieldnames=write_fieldnames,
    )
    result = refresh_symbol_universe_metadata(
        rows,
        provider=provider,
        as_of=args.as_of,
        updated_at=args.updated_at,
        dry_run=not args.write,
        validation_before=validation_before,
        validation_after=validation_after,
    )

    if args.write and result.manifest["validation_after"]["errors"]:
        print(json.dumps(result.manifest, ensure_ascii=False, indent=2, sort_keys=True))
        print("Refusing to write because validation_after has errors.", file=sys.stderr)
        return 2

    if args.write:
        _write_symbol_universe_csv(args.csv, result.rows, write_fieldnames)
        _write_manifest(args.manifest, result.manifest)

    print(json.dumps(result.manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _read_symbol_universe_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        fieldnames = list(reader.fieldnames or [])
        rows = [
            {str(key): ("" if value is None else str(value).strip()) for key, value in row.items()}
            for row in reader
            if row.get("symbol")
        ]
    return fieldnames, rows


def _write_symbol_universe_csv(
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


def _write_fieldnames(
    fieldnames: Sequence[str],
    rows: Sequence[dict[str, str]],
) -> list[str]:
    write_fieldnames = list(fieldnames)
    for column in METADATA_REFRESH_COLUMNS:
        if column not in write_fieldnames:
            write_fieldnames.append(column)
    for row in rows:
        for column in row:
            if column not in write_fieldnames:
                write_fieldnames.append(column)
    return write_fieldnames


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


if __name__ == "__main__":
    raise SystemExit(main())
