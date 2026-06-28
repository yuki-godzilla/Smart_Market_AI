from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Sequence, cast

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV_PATH = PROJECT_ROOT / "data" / "marketdata" / "symbol_universe.csv"
DEFAULT_MANIFEST_PATH = PROJECT_ROOT / "data" / "marketdata" / "symbol_universe_manifest.json"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.marketdata.symbol_metadata_refresh import (  # noqa: E402
    METADATA_REFRESH_COLUMNS,
    SymbolMetadataFailure,
    SymbolMetadataProvider,
    SymbolMetadataUpdate,
    create_symbol_metadata_provider,
    metadata_refresh_provider_details,
    refresh_symbol_universe_metadata,
    summarize_validation_issues,
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
    parser.add_argument("--symbols", default="", help="Comma-separated symbol allowlist.")
    parser.add_argument("--asset-type", default="", help="Refresh only rows with this asset_type.")
    parser.add_argument("--market", default="", help="Refresh only rows with this market.")
    parser.add_argument(
        "--metadata-source",
        default="",
        help="Refresh only rows with this metadata_source.",
    )
    parser.add_argument(
        "--missing-any",
        default="",
        help="Comma-separated columns. Refresh only rows where at least one is blank.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit selected rows after filters. 0 means no limit.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write proposed CSV and manifest. Without this flag the command is a dry-run.",
    )
    parser.add_argument(
        "--fill-missing-only",
        action="store_true",
        help="Only fill blank cells; preserve existing canonical values.",
    )
    parser.add_argument(
        "--allow-live",
        action="store_true",
        help="Allow an external live provider such as yahoo. Never enabled by default.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=25,
        help="Print live progress every N processed symbols. 0 disables progress logs.",
    )
    parser.add_argument(
        "--symbol-timeout-seconds",
        type=float,
        default=0,
        help=(
            "Per-symbol live Yahoo timeout. 0 disables subprocess timeout. "
            "When set, timed-out symbols are skipped and reported as failures."
        ),
    )
    parser.add_argument(
        "--strict-validation",
        action="store_true",
        help=(
            "Refuse --write whenever validation_after has any errors. "
            "By default, pre-existing validation errors do not block writes unless "
            "the refresh increases the error count."
        ),
    )
    args = parser.parse_args(argv)

    fieldnames, rows = _read_symbol_universe_csv(args.csv)
    provider_details = metadata_refresh_provider_details(args.provider)
    if provider_details.get("requires_external_opt_in") and not args.allow_live:
        print(
            f"{args.provider} metadata refresh requires --allow-live.",
            file=sys.stderr,
        )
        return 2
    try:
        base_provider = create_symbol_metadata_provider(args.provider)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    _configure_live_provider_runtime(
        base_provider,
        progress_every=args.progress_every,
        symbol_timeout_seconds=args.symbol_timeout_seconds,
    )
    selected_rows = _select_refresh_rows(
        rows,
        symbols=_parse_list(args.symbols),
        asset_type=args.asset_type,
        market=args.market,
        metadata_source=args.metadata_source,
        missing_any=_parse_list(args.missing_any),
        limit=args.limit,
    )
    provider = _ScopedSymbolMetadataProvider(
        base_provider=base_provider,
        selected_symbols={
            row.get("symbol", "").strip().upper()
            for row in selected_rows
            if row.get("symbol", "").strip()
        },
    )
    validation_before = validate_symbol_universe_rows(
        cast(Sequence[dict[str | None, Any]], rows),
        fieldnames=fieldnames,
    )
    write_fieldnames = _write_fieldnames(fieldnames, rows)

    if args.progress_every > 0:
        print(
            json.dumps(
                {
                    "event": "selection",
                    "provider": args.provider,
                    "selected_rows": len(selected_rows),
                    "total_rows": len(rows),
                    "write": bool(args.write),
                    "symbol_timeout_seconds": args.symbol_timeout_seconds,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
            flush=True,
        )

    result = refresh_symbol_universe_metadata(
        rows,
        provider=provider,
        as_of=args.as_of,
        updated_at=args.updated_at,
        dry_run=not args.write,
        validation_before=validation_before,
        fill_missing_only=args.fill_missing_only,
    )
    validation_after = validate_symbol_universe_rows(
        cast(Sequence[dict[str | None, Any]], result.rows),
        fieldnames=write_fieldnames,
    )
    validation_after_summary = summarize_validation_issues(validation_after)
    result.manifest["validation_after"] = validation_after_summary
    result.manifest["selection"] = _selection_manifest(
        rows,
        selected_rows,
        symbols=_parse_list(args.symbols),
        asset_type=args.asset_type,
        market=args.market,
        metadata_source=args.metadata_source,
        missing_any=_parse_list(args.missing_any),
        limit=args.limit,
    )

    validation_before_summary = summarize_validation_issues(validation_before)
    if args.write and _should_refuse_write_due_to_validation(
        validation_before_summary=validation_before_summary,
        validation_after_summary=validation_after_summary,
        strict_validation=args.strict_validation,
    ):
        print(json.dumps(result.manifest, ensure_ascii=False, indent=2, sort_keys=True))
        if args.strict_validation:
            print(
                "Refusing to write because --strict-validation is set and validation_after has errors.",
                file=sys.stderr,
            )
        else:
            print(
                "Refusing to write because validation_after introduced additional errors.",
                file=sys.stderr,
            )
        return 2
    if args.write and validation_after_summary["errors"]:
        print(
            json.dumps(
                {
                    "event": "validation_warning",
                    "message": "Writing despite pre-existing validation errors because the refresh did not increase the error count.",
                    "validation_before": validation_before_summary,
                    "validation_after": validation_after_summary,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )

    if args.write:
        _write_symbol_universe_csv(args.csv, result.rows, write_fieldnames)
        _write_manifest(args.manifest, result.manifest)

    print(json.dumps(result.manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _should_refuse_write_due_to_validation(
    *,
    validation_before_summary: dict[str, int],
    validation_after_summary: dict[str, int],
    strict_validation: bool,
) -> bool:
    after_errors = int(validation_after_summary.get("errors", 0))
    before_errors = int(validation_before_summary.get("errors", 0))
    if after_errors <= 0:
        return False
    if strict_validation:
        return True
    return after_errors > before_errors


class _ScopedSymbolMetadataProvider:
    """Limit an existing provider to selected symbols without changing refresh output rows."""

    def __init__(
        self,
        *,
        base_provider: SymbolMetadataProvider,
        selected_symbols: set[str],
    ) -> None:
        self._base_provider = base_provider
        self._selected_symbols = selected_symbols
        self.name = base_provider.name

    @property
    def failures(self) -> list[SymbolMetadataFailure]:
        return list(getattr(self._base_provider, "failures", []))

    @property
    def no_update_symbols(self) -> list[str]:
        return list(getattr(self._base_provider, "no_update_symbols", []))

    def fetch_metadata(
        self,
        rows: Sequence[dict[str, str]],
        *,
        as_of: date,
        updated_at: datetime,
    ) -> list[SymbolMetadataUpdate]:
        scoped_rows = [
            row for row in rows if row.get("symbol", "").strip().upper() in self._selected_symbols
        ]
        return self._base_provider.fetch_metadata(
            scoped_rows,
            as_of=as_of,
            updated_at=updated_at,
        )


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


def _select_refresh_rows(
    rows: Sequence[dict[str, str]],
    *,
    symbols: Sequence[str],
    asset_type: str,
    market: str,
    metadata_source: str,
    missing_any: Sequence[str],
    limit: int,
) -> list[dict[str, str]]:
    symbol_set = {symbol.strip().upper() for symbol in symbols if symbol.strip()}
    selected_rows = [
        row
        for row in rows
        if (not symbol_set or row.get("symbol", "").strip().upper() in symbol_set)
        and (not asset_type or row.get("asset_type") == asset_type)
        and (not market or row.get("market") == market)
        and (not metadata_source or row.get("metadata_source") == metadata_source)
        and (not missing_any or any(not row.get(column, "").strip() for column in missing_any))
    ]
    if limit > 0:
        return selected_rows[:limit]
    return selected_rows


def _configure_live_provider_runtime(
    provider: SymbolMetadataProvider,
    *,
    progress_every: int,
    symbol_timeout_seconds: float,
) -> None:
    if hasattr(provider, "symbol_timeout_seconds"):
        setattr(provider, "symbol_timeout_seconds", max(0.0, float(symbol_timeout_seconds)))
    if progress_every > 0 and hasattr(provider, "progress_callback"):
        started_at = time.monotonic()

        def _progress(payload: dict[str, object]) -> None:
            event = str(payload.get("event") or "")
            index = int(str(payload.get("index") or 0))
            total = int(str(payload.get("total") or 0))
            should_print = event in {"failure", "timeout"} or (
                event == "done" and (index == 1 or index == total or index % progress_every == 0)
            )
            if not should_print:
                return
            elapsed = time.monotonic() - started_at
            rate = index / elapsed if elapsed > 0 and index > 0 else 0
            remaining = (total - index) / rate if rate > 0 and total >= index else None
            message = dict(payload)
            message["rate_symbols_per_second"] = round(rate, 4)
            if remaining is not None:
                message["eta_seconds"] = round(remaining, 1)
            print(
                json.dumps(message, ensure_ascii=False, sort_keys=True), file=sys.stderr, flush=True
            )

        setattr(provider, "progress_callback", _progress)


def _selection_manifest(
    rows: Sequence[dict[str, str]],
    selected_rows: Sequence[dict[str, str]],
    *,
    symbols: Sequence[str],
    asset_type: str,
    market: str,
    metadata_source: str,
    missing_any: Sequence[str],
    limit: int,
) -> dict[str, object]:
    selected_symbols = [row.get("symbol", "") for row in selected_rows]
    sample_limit = 50
    return {
        "total_rows": len(rows),
        "selected_rows": len(selected_rows),
        "filters": {
            "symbols": list(symbols),
            "asset_type": asset_type,
            "market": market,
            "metadata_source": metadata_source,
            "missing_any": list(missing_any),
            "limit": limit,
        },
        "selected_symbols": selected_symbols[:sample_limit],
        "selected_symbols_truncated": len(selected_symbols) > sample_limit,
    }


def _parse_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


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
