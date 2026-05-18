from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Sequence

from backend.marketdata.symbol_metadata_refresh import summarize_validation_issues
from backend.marketdata.symbol_metadata_schema import (
    symbol_universe_optional_columns,
    symbol_universe_required_columns,
)

SYMBOL_UNIVERSE_SOURCE_ALIASES = {
    "symbol": ("symbol", "ticker", "code"),
    "name": ("name", "security_name", "company_name", "fund_name"),
    "market": ("market", "region"),
    "asset_type": ("asset_type", "product_type"),
    "currency": ("currency",),
}


@dataclass(frozen=True)
class SymbolUniverseImportFailure:
    """One source row that could not be imported into the symbol universe."""

    source_row: int
    symbol: str
    code: str
    message: str


@dataclass(frozen=True)
class SymbolUniverseImportResult:
    """Proposed symbol-universe rows and manifest details."""

    rows: list[dict[str, str]]
    manifest: dict[str, object]


def symbol_universe_import_fieldnames() -> list[str]:
    """Return the canonical symbol_universe.csv field order."""

    return [
        *symbol_universe_required_columns(),
        *symbol_universe_optional_columns(),
    ]


def merge_symbol_universe_source_rows(
    existing_rows: Sequence[dict[str, str]],
    source_rows: Sequence[dict[str | None, Any]],
    *,
    source_name: str,
    as_of: date,
    updated_at: datetime,
    update_existing: bool = False,
    dry_run: bool = True,
    validation_before: Sequence[dict[str, str]] | None = None,
    validation_after: Sequence[dict[str, str]] | None = None,
) -> SymbolUniverseImportResult:
    """Merge a local curated source CSV into symbol_universe-shaped rows."""

    fieldnames = symbol_universe_import_fieldnames()
    proposed_rows = [_complete_existing_row(row, fieldnames) for row in existing_rows]
    row_index_by_symbol = {
        row["symbol"].strip().upper(): index
        for index, row in enumerate(proposed_rows)
        if row.get("symbol", "").strip()
    }

    imported_symbols: list[str] = []
    updated_symbols: list[str] = []
    skipped_existing_symbols: list[str] = []
    failures: list[SymbolUniverseImportFailure] = []
    changed_columns: set[str] = set()

    for source_row_number, source_row in enumerate(source_rows, start=2):
        normalized_row, failure = _source_row_to_symbol_universe_row(
            source_row,
            fieldnames=fieldnames,
            source_name=source_name,
            as_of=as_of,
            updated_at=updated_at,
            source_row_number=source_row_number,
        )
        if failure is not None:
            failures.append(failure)
            continue

        symbol = normalized_row["symbol"]
        normalized_symbol = symbol.upper()
        existing_index = row_index_by_symbol.get(normalized_symbol)
        if existing_index is None:
            proposed_rows.append(normalized_row)
            row_index_by_symbol[normalized_symbol] = len(proposed_rows) - 1
            imported_symbols.append(symbol)
            changed_columns.update(
                column for column, value in normalized_row.items() if value.strip()
            )
            continue

        if not update_existing:
            skipped_existing_symbols.append(symbol)
            continue

        existing_row = proposed_rows[existing_index]
        row_changed = False
        for column, value in normalized_row.items():
            if column == "symbol":
                continue
            if not value.strip() and column not in _operational_metadata_columns():
                continue
            if existing_row.get(column, "") == value:
                continue
            existing_row[column] = value
            changed_columns.add(column)
            row_changed = True
        if row_changed:
            updated_symbols.append(symbol)

    manifest = {
        "operation": "symbol_universe_source_import",
        "source": source_name,
        "dry_run": dry_run,
        "update_existing": update_existing,
        "as_of": as_of.isoformat(),
        "updated_at": updated_at.isoformat(),
        "existing_rows": len(existing_rows),
        "source_rows": len(source_rows),
        "total_rows": len(proposed_rows),
        "imported_rows": len(imported_symbols),
        "updated_rows": len(updated_symbols),
        "skipped_existing_rows": len(skipped_existing_symbols),
        "failed_rows": len(failures),
        "imported_symbols": imported_symbols,
        "updated_symbols": updated_symbols,
        "skipped_existing_symbols": skipped_existing_symbols,
        "failed_symbols": [failure.symbol for failure in failures if failure.symbol],
        "failures": [
            {
                "source_row": failure.source_row,
                "symbol": failure.symbol,
                "code": failure.code,
                "message": failure.message,
            }
            for failure in failures
        ],
        "changed_columns": sorted(changed_columns),
        "validation_before": summarize_validation_issues(validation_before or []),
        "validation_after": summarize_validation_issues(validation_after or []),
    }
    return SymbolUniverseImportResult(rows=proposed_rows, manifest=manifest)


def _complete_existing_row(
    row: dict[str, str],
    fieldnames: Sequence[str],
) -> dict[str, str]:
    return {column: str(row.get(column, "") or "").strip() for column in fieldnames}


def _source_row_to_symbol_universe_row(
    source_row: dict[str | None, Any],
    *,
    fieldnames: Sequence[str],
    source_name: str,
    as_of: date,
    updated_at: datetime,
    source_row_number: int,
) -> tuple[dict[str, str], SymbolUniverseImportFailure | None]:
    row = {column: _source_value(source_row, column) for column in fieldnames}
    symbol = row["symbol"].strip().upper()
    name = row["name"].strip()
    if not symbol:
        return row, SymbolUniverseImportFailure(
            source_row=source_row_number,
            symbol="",
            code="SYMBOL-UNIVERSE-IMPORT-MISSING-SYMBOL",
            message="symbol is required.",
        )
    row["symbol"] = symbol
    if not name:
        return row, SymbolUniverseImportFailure(
            source_row=source_row_number,
            symbol=symbol,
            code="SYMBOL-UNIVERSE-IMPORT-MISSING-NAME",
            message="name is required.",
        )

    if not row["market"]:
        row["market"] = "jp" if symbol.endswith(".T") else "us"
    if not row["asset_type"]:
        row["asset_type"] = "stock"
    if not row["currency"]:
        row["currency"] = "JPY" if row["market"] == "jp" else "USD"
    if not row["theme"] and row["asset_type"] == "etf":
        row["theme"] = "index"
    if not row["sector"] and row["asset_type"] == "etf":
        row["sector"] = "index"
    if not row["complexity"]:
        row["complexity"] = "beginner" if row["asset_type"] == "etf" else "standard"
    if not row["tags"] and row["asset_type"] == "etf":
        row["tags"] = "low_cost"

    row["metadata_source"] = row["metadata_source"] or source_name
    row["metadata_as_of"] = row["metadata_as_of"] or as_of.isoformat()
    row["metadata_updated_at"] = row["metadata_updated_at"] or updated_at.isoformat()
    return row, None


def _source_value(source_row: dict[str | None, Any], column: str) -> str:
    value = source_row.get(column)
    if value is None:
        for alias in SYMBOL_UNIVERSE_SOURCE_ALIASES.get(column, ()):
            value = source_row.get(alias)
            if value is not None:
                break
    return "" if value is None else str(value).strip()


def _operational_metadata_columns() -> set[str]:
    return {"metadata_source", "metadata_as_of", "metadata_updated_at"}
