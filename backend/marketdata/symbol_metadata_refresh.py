from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol, Sequence, runtime_checkable

METADATA_REFRESH_COLUMNS = (
    "metadata_source",
    "metadata_as_of",
    "metadata_updated_at",
)
SUPPORTED_METADATA_REFRESH_PROVIDERS = ("curated_csv",)
PLANNED_METADATA_REFRESH_PROVIDERS = (
    "yahoo",
    "fmp",
    "eodhd",
    "alpha_vantage",
    "polygon",
)


@dataclass(frozen=True)
class SymbolMetadataUpdate:
    """Provider-neutral metadata updates for one symbol."""

    symbol: str
    values: dict[str, str]


@runtime_checkable
class SymbolMetadataProvider(Protocol):
    """Provider boundary for symbol-universe metadata refresh."""

    name: str

    def fetch_metadata(
        self,
        rows: Sequence[dict[str, str]],
        *,
        as_of: date,
        updated_at: datetime,
    ) -> list[SymbolMetadataUpdate]:
        """Return metadata updates for the supplied symbol-universe rows."""


@dataclass(frozen=True)
class CuratedSymbolMetadataProvider:
    """Deterministic provider used to exercise the refresh path without network access."""

    name: str = "curated_csv"

    def fetch_metadata(
        self,
        rows: Sequence[dict[str, str]],
        *,
        as_of: date,
        updated_at: datetime,
    ) -> list[SymbolMetadataUpdate]:
        updates: list[SymbolMetadataUpdate] = []
        for row in rows:
            symbol = row.get("symbol", "").strip()
            if not symbol:
                continue
            updates.append(
                SymbolMetadataUpdate(
                    symbol=symbol,
                    values={
                        "metadata_source": self.name,
                        "metadata_as_of": as_of.isoformat(),
                        "metadata_updated_at": updated_at.isoformat(),
                    },
                )
            )
        return updates


@dataclass(frozen=True)
class MetadataRefreshResult:
    """Refresh result with proposed rows and manifest details."""

    rows: list[dict[str, str]]
    manifest: dict[str, object]


def create_symbol_metadata_provider(provider: str) -> SymbolMetadataProvider:
    """Create a metadata refresh provider without importing live dependencies."""

    if provider == "curated_csv":
        return CuratedSymbolMetadataProvider()
    if provider in PLANNED_METADATA_REFRESH_PROVIDERS:
        raise ValueError(f"{provider} metadata refresh provider is planned but not implemented.")
    raise ValueError(f"{provider} metadata refresh provider is not registered.")


def metadata_refresh_provider_details(provider: str) -> dict[str, object]:
    """Return provider capability details for metadata refresh diagnostics."""

    if provider in SUPPORTED_METADATA_REFRESH_PROVIDERS:
        return {
            "provider": provider,
            "registered": True,
            "implemented": True,
            "deterministic": provider == "curated_csv",
            "requires_external_opt_in": False,
            "supported_providers": list(SUPPORTED_METADATA_REFRESH_PROVIDERS),
            "planned_live_providers": list(PLANNED_METADATA_REFRESH_PROVIDERS),
        }
    if provider in PLANNED_METADATA_REFRESH_PROVIDERS:
        return {
            "provider": provider,
            "registered": True,
            "implemented": False,
            "deterministic": False,
            "requires_external_opt_in": True,
            "supported_providers": list(SUPPORTED_METADATA_REFRESH_PROVIDERS),
            "planned_live_providers": list(PLANNED_METADATA_REFRESH_PROVIDERS),
        }
    return {
        "provider": provider,
        "registered": False,
        "supported_providers": list(SUPPORTED_METADATA_REFRESH_PROVIDERS),
        "planned_live_providers": list(PLANNED_METADATA_REFRESH_PROVIDERS),
    }


def refresh_symbol_universe_metadata(
    rows: Sequence[dict[str, str]],
    *,
    provider: SymbolMetadataProvider,
    as_of: date,
    updated_at: datetime,
    dry_run: bool = True,
    validation_before: Sequence[dict[str, str]] | None = None,
    validation_after: Sequence[dict[str, str]] | None = None,
) -> MetadataRefreshResult:
    """Apply provider-neutral metadata updates to symbol-universe rows."""

    proposed_rows = [dict(row) for row in rows]
    row_index_by_symbol = {
        row.get("symbol", "").strip().upper(): index
        for index, row in enumerate(proposed_rows)
        if row.get("symbol", "").strip()
    }
    updates = provider.fetch_metadata(proposed_rows, as_of=as_of, updated_at=updated_at)

    changed_symbols: set[str] = set()
    changed_columns: set[str] = set()
    unknown_symbols: list[str] = []
    applied_updates = 0

    for update in updates:
        normalized_symbol = update.symbol.strip().upper()
        if not normalized_symbol:
            continue
        row_index = row_index_by_symbol.get(normalized_symbol)
        if row_index is None:
            unknown_symbols.append(update.symbol)
            continue
        applied_updates += 1
        row = proposed_rows[row_index]
        row_changed = False
        for column, value in update.values.items():
            normalized_value = "" if value is None else str(value)
            if row.get(column, "") == normalized_value:
                continue
            row[column] = normalized_value
            changed_columns.add(column)
            row_changed = True
        if row_changed:
            changed_symbols.add(row.get("symbol", update.symbol))

    manifest = {
        "operation": "symbol_universe_metadata_refresh",
        "provider": provider.name,
        "dry_run": dry_run,
        "as_of": as_of.isoformat(),
        "updated_at": updated_at.isoformat(),
        "total_rows": len(proposed_rows),
        "updates_requested": len(updates),
        "updates_applied": applied_updates,
        "changed_rows": len(changed_symbols),
        "changed_symbols": sorted(changed_symbols),
        "changed_columns": sorted(changed_columns),
        "unknown_symbols": unknown_symbols,
        "validation_before": summarize_validation_issues(validation_before or []),
        "validation_after": summarize_validation_issues(validation_after or []),
    }
    return MetadataRefreshResult(rows=proposed_rows, manifest=manifest)


def summarize_validation_issues(issues: Sequence[dict[str, str]]) -> dict[str, int]:
    """Summarize validation issues by severity for manifests."""

    errors = sum(1 for issue in issues if issue.get("severity", "error") == "error")
    warnings = sum(1 for issue in issues if issue.get("severity", "error") == "warning")
    return {
        "total": len(issues),
        "errors": errors,
        "warnings": warnings,
    }
