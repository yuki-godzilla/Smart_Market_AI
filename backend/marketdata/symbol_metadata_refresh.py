from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Callable, Protocol, Sequence, runtime_checkable

METADATA_REFRESH_COLUMNS = (
    "metadata_source",
    "metadata_as_of",
    "metadata_updated_at",
)
SUPPORTED_METADATA_REFRESH_PROVIDERS = ("curated_csv", "yahoo")
PLANNED_METADATA_REFRESH_PROVIDERS = (
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


@dataclass(frozen=True)
class SymbolMetadataFailure:
    """Provider-neutral metadata refresh failure for one symbol."""

    symbol: str
    code: str
    message: str


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


@dataclass
class YahooSymbolMetadataProvider:
    """Opt-in Yahoo metadata provider backed by yfinance ticker info."""

    ticker_info_reader: Callable[[str], dict[str, object]] | None = None
    name: str = "yahoo"
    failures: list[SymbolMetadataFailure] = field(default_factory=list, init=False)

    def fetch_metadata(
        self,
        rows: Sequence[dict[str, str]],
        *,
        as_of: date,
        updated_at: datetime,
    ) -> list[SymbolMetadataUpdate]:
        self.failures.clear()
        updates: list[SymbolMetadataUpdate] = []
        ticker_info_reader = self.ticker_info_reader or _read_yahoo_ticker_info
        for row in rows:
            symbol = row.get("symbol", "").strip()
            if not symbol:
                continue
            try:
                info = ticker_info_reader(symbol)
            except Exception as exc:  # noqa: BLE001 - provider failures are reported per symbol.
                self.failures.append(
                    SymbolMetadataFailure(
                        symbol=symbol,
                        code="YAHOO-METADATA-FAILED",
                        message=str(exc),
                    )
                )
                continue

            values = _yahoo_metadata_values(row, info, as_of=as_of, updated_at=updated_at)
            if values:
                updates.append(SymbolMetadataUpdate(symbol=symbol, values=values))
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
    if provider == "yahoo":
        return YahooSymbolMetadataProvider()
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
            "requires_external_opt_in": provider != "curated_csv",
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
    failures = list(getattr(provider, "failures", []))

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
        "failed_symbols": [failure.symbol for failure in failures],
        "failures": [
            {
                "symbol": failure.symbol,
                "code": failure.code,
                "message": failure.message,
            }
            for failure in failures
        ],
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


def _read_yahoo_ticker_info(symbol: str) -> dict[str, object]:
    from backend.marketdata.providers.yahoo import (  # noqa: PLC0415
        _call_yfinance_silently,
        _load_yfinance,
        _ticker_info,
        shared_yfinance_session,
    )

    yf = _load_yfinance()
    ticker = yf.Ticker(symbol, session=shared_yfinance_session())
    return _call_yfinance_silently(_ticker_info, ticker)


def _yahoo_metadata_values(
    row: dict[str, str],
    info: dict[str, object],
    *,
    as_of: date,
    updated_at: datetime,
) -> dict[str, str]:
    values = {
        "metadata_source": "yahoo",
        "metadata_as_of": as_of.isoformat(),
        "metadata_updated_at": updated_at.isoformat(),
    }
    sector = _yahoo_sector(info)
    if sector:
        values["sector"] = sector
        values.setdefault("theme", sector)

    dividend_yield = _optional_decimal_info(info, "dividendYield")
    if dividend_yield is None:
        dividend_yield = _optional_decimal_info(info, "trailingAnnualDividendYield")
    if dividend_yield is not None:
        dividend_yield_pct = _ratio_to_percent(dividend_yield)
        values["dividend_yield_pct"] = _format_decimal(dividend_yield_pct)
        values["dividend_category"] = _dividend_category(dividend_yield_pct)

    per = _optional_decimal_info(info, "trailingPE") or _optional_decimal_info(info, "forwardPE")
    if per is not None:
        values["per"] = _format_decimal(per)

    pbr = _optional_decimal_info(info, "priceToBook")
    if pbr is not None:
        values["pbr"] = _format_decimal(pbr)

    roe = _optional_decimal_info(info, "returnOnEquity")
    if roe is not None:
        values["roe_pct"] = _format_decimal(_ratio_to_percent(roe))

    market_cap = _optional_decimal_info(info, "marketCap")
    if market_cap is not None:
        values["market_cap_tier"] = _market_cap_tier(
            market_cap,
            currency=str(info.get("currency") or row.get("currency") or ""),
            symbol=row.get("symbol", ""),
        )

    beta = _optional_decimal_info(info, "beta")
    if beta is not None:
        values["risk_band"] = _risk_band(beta)

    expense_ratio = _optional_decimal_info(info, "annualReportExpenseRatio")
    if expense_ratio is None:
        expense_ratio = _optional_decimal_info(info, "netExpenseRatio")
    if row.get("asset_type") == "etf" and expense_ratio is not None:
        values["expense_ratio_pct"] = _format_decimal(_ratio_to_percent(expense_ratio))

    return values


def _optional_decimal_info(info: dict[str, object], key: str) -> Decimal | None:
    value = info.get(key)
    if value is None or str(value).lower() == "nan":
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _ratio_to_percent(value: Decimal) -> Decimal:
    if abs(value) <= Decimal("1"):
        return value * Decimal("100")
    return value


def _format_decimal(value: Decimal) -> str:
    normalized = value.quantize(Decimal("0.01")).normalize()
    return format(normalized, "f")


def _yahoo_sector(info: dict[str, object]) -> str | None:
    raw_sector = str(info.get("sector") or "").strip().lower()
    return {
        "basic materials": "materials",
        "communication services": "communication",
        "consumer cyclical": "consumer",
        "consumer defensive": "consumer",
        "energy": "energy",
        "financial services": "financial",
        "healthcare": "healthcare",
        "industrials": "industrial",
        "real estate": "real_estate",
        "technology": "technology",
        "utilities": "utilities",
    }.get(raw_sector)


def _dividend_category(dividend_yield_pct: Decimal) -> str:
    if dividend_yield_pct <= 0:
        return "none"
    if dividend_yield_pct >= Decimal("3"):
        return "high_dividend"
    return "dividend"


def _market_cap_tier(market_cap: Decimal, *, currency: str, symbol: str) -> str:
    if currency == "JPY" or symbol.endswith(".T"):
        if market_cap >= Decimal("10000000000000"):
            return "mega"
        if market_cap >= Decimal("1000000000000"):
            return "large"
        if market_cap >= Decimal("100000000000"):
            return "mid"
        if market_cap >= Decimal("10000000000"):
            return "small"
        return "micro"

    if market_cap >= Decimal("200000000000"):
        return "mega"
    if market_cap >= Decimal("10000000000"):
        return "large"
    if market_cap >= Decimal("2000000000"):
        return "mid"
    if market_cap >= Decimal("300000000"):
        return "small"
    return "micro"


def _risk_band(beta: Decimal) -> str:
    if beta < Decimal("0.8"):
        return "LOW"
    if beta <= Decimal("1.2"):
        return "MEDIUM"
    return "HIGH"
