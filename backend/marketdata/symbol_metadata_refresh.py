from __future__ import annotations

import multiprocessing
import os
import queue
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Callable, Protocol, Sequence, runtime_checkable

METADATA_PROVENANCE_FIELDS = (
    "per",
    "pbr",
    "roe_pct",
    "dividend_yield_pct",
    "market_cap_tier",
    "market_cap",
    "expense_ratio_pct",
    "aum",
    "average_volume",
)
METADATA_REFRESH_COLUMNS = (
    "metadata_source",
    "metadata_as_of",
    "metadata_updated_at",
    *(
        f"{metric}_{suffix}"
        for metric in METADATA_PROVENANCE_FIELDS
        for suffix in ("source", "as_of", "quality")
    ),
)
SUPPORTED_METADATA_REFRESH_PROVIDERS = ("curated_csv", "yahoo")
PLANNED_METADATA_REFRESH_PROVIDERS = (
    "fmp",
    "eodhd",
    "alpha_vantage",
    "polygon",
)
MAX_REASONABLE_DIVIDEND_YIELD_RATIO = Decimal("0.20")
YAHOO_PERCENT_STYLE_DIVIDEND_YIELD_THRESHOLD = Decimal("0.20")
MAX_REASONABLE_PER = Decimal("200")
MAX_REASONABLE_PBR = Decimal("50")
MIN_REASONABLE_ROE_PCT = Decimal("-100")
MAX_REASONABLE_ROE_PCT = Decimal("100")


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

    @property
    def name(self) -> str:
        """Provider name recorded in refresh metadata and manifests."""
        ...

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
    no_update_symbols: list[str] = field(default_factory=list, init=False)
    symbol_timeout_seconds: float = 0
    progress_callback: Callable[[dict[str, object]], None] | None = None

    def fetch_metadata(
        self,
        rows: Sequence[dict[str, str]],
        *,
        as_of: date,
        updated_at: datetime,
    ) -> list[SymbolMetadataUpdate]:
        self.failures.clear()
        self.no_update_symbols.clear()
        updates: list[SymbolMetadataUpdate] = []
        ticker_info_reader = self.ticker_info_reader or _read_yahoo_ticker_info
        total = len(rows)
        started_at = time.monotonic()
        for index, row in enumerate(rows, start=1):
            symbol = row.get("symbol", "").strip()
            yahoo_symbol = _yahoo_lookup_symbol(row)
            if not symbol or not yahoo_symbol:
                continue
            symbol_started_at = time.monotonic()
            self._emit_progress(
                {
                    "event": "start",
                    "index": index,
                    "total": total,
                    "symbol": symbol,
                    "lookup_symbol": yahoo_symbol,
                    "elapsed_seconds": round(time.monotonic() - started_at, 2),
                }
            )
            try:
                info = self._read_info(
                    ticker_info_reader,
                    yahoo_symbol,
                    use_subprocess_timeout=self.ticker_info_reader is None,
                )
            except TimeoutError as exc:
                self.failures.append(
                    SymbolMetadataFailure(
                        symbol=symbol,
                        code="YAHOO-METADATA-TIMEOUT",
                        message=str(exc),
                    )
                )
                self._emit_progress(
                    {
                        "event": "timeout",
                        "index": index,
                        "total": total,
                        "symbol": symbol,
                        "lookup_symbol": yahoo_symbol,
                        "duration_seconds": round(time.monotonic() - symbol_started_at, 2),
                        "elapsed_seconds": round(time.monotonic() - started_at, 2),
                    }
                )
                continue
            except Exception as exc:  # noqa: BLE001 - provider failures are reported per symbol.
                self.failures.append(
                    SymbolMetadataFailure(
                        symbol=symbol,
                        code="YAHOO-METADATA-FAILED",
                        message=str(exc),
                    )
                )
                self._emit_progress(
                    {
                        "event": "failure",
                        "index": index,
                        "total": total,
                        "symbol": symbol,
                        "lookup_symbol": yahoo_symbol,
                        "duration_seconds": round(time.monotonic() - symbol_started_at, 2),
                        "elapsed_seconds": round(time.monotonic() - started_at, 2),
                        "message": str(exc),
                    }
                )
                continue

            try:
                values = _yahoo_metadata_values(row, info, as_of=as_of, updated_at=updated_at)
            except Exception as exc:  # noqa: BLE001 - bad provider fields should not abort a batch.
                self.failures.append(
                    SymbolMetadataFailure(
                        symbol=symbol,
                        code="YAHOO-METADATA-NORMALIZE-FAILED",
                        message=str(exc),
                    )
                )
                self._emit_progress(
                    {
                        "event": "failure",
                        "index": index,
                        "total": total,
                        "symbol": symbol,
                        "lookup_symbol": yahoo_symbol,
                        "duration_seconds": round(time.monotonic() - symbol_started_at, 2),
                        "elapsed_seconds": round(time.monotonic() - started_at, 2),
                        "message": str(exc),
                    }
                )
                continue
            has_substantive_values = _has_substantive_metadata_values(values)
            if values:
                values.setdefault("yahoo_symbol", yahoo_symbol)
                values["yahoo_symbol_status"] = "confirmed"
                values["yahoo_symbol_checked_at"] = updated_at.isoformat()
                updates.append(SymbolMetadataUpdate(symbol=symbol, values=values))
            if not has_substantive_values:
                self.no_update_symbols.append(symbol)
            self._emit_progress(
                {
                    "event": "done",
                    "index": index,
                    "total": total,
                    "symbol": symbol,
                    "lookup_symbol": yahoo_symbol,
                    "updated": bool(has_substantive_values),
                    "duration_seconds": round(time.monotonic() - symbol_started_at, 2),
                    "elapsed_seconds": round(time.monotonic() - started_at, 2),
                }
            )
        return updates

    def _read_info(
        self,
        ticker_info_reader: Callable[[str], dict[str, object]],
        symbol: str,
        *,
        use_subprocess_timeout: bool,
    ) -> dict[str, object]:
        if self.symbol_timeout_seconds <= 0:
            return ticker_info_reader(symbol)
        if not use_subprocess_timeout:
            return ticker_info_reader(symbol)
        return _read_yahoo_ticker_info_with_timeout(
            symbol, timeout_seconds=self.symbol_timeout_seconds
        )

    def _emit_progress(self, payload: dict[str, object]) -> None:
        if self.progress_callback is None:
            return
        self.progress_callback(payload)


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
    fill_missing_only: bool = False,
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
    unchanged_update_symbols: set[str] = set()

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
        original_row = dict(row)
        row_changed = False
        update_values = _with_metric_provenance(
            update.values,
            provider=provider.name,
            as_of=as_of,
        )
        for column, value in update_values.items():
            normalized_value = "" if value is None else str(value)
            provenance_metric = _provenance_metric_for_column(column)
            if (
                fill_missing_only
                and provenance_metric
                and original_row.get(provenance_metric, "").strip()
            ):
                continue
            if fill_missing_only and row.get(column, "").strip():
                continue
            if row.get(column, "") == normalized_value:
                continue
            row[column] = normalized_value
            changed_columns.add(column)
            row_changed = True
        if row_changed:
            changed_symbols.add(row.get("symbol", update.symbol))
        else:
            unchanged_update_symbols.add(row.get("symbol", update.symbol))

    no_update_symbols = list(getattr(provider, "no_update_symbols", []))

    manifest = {
        "operation": "symbol_universe_metadata_refresh",
        "provider": provider.name,
        "dry_run": dry_run,
        "fill_missing_only": fill_missing_only,
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
        "no_update_symbols": sorted({symbol for symbol in no_update_symbols if symbol}),
        "unchanged_update_symbols": sorted(
            {symbol for symbol in unchanged_update_symbols if symbol}
        ),
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


def _with_metric_provenance(
    values: dict[str, str],
    *,
    provider: str,
    as_of: date,
) -> dict[str, str]:
    enriched = dict(values)
    for metric in METADATA_PROVENANCE_FIELDS:
        if not str(values.get(metric, "")).strip():
            continue
        enriched.setdefault(f"{metric}_source", provider)
        enriched.setdefault(f"{metric}_as_of", as_of.isoformat())
        enriched.setdefault(f"{metric}_quality", "confirmed")
    return enriched


def _provenance_metric_for_column(column: str) -> str | None:
    for metric in METADATA_PROVENANCE_FIELDS:
        if column in {
            f"{metric}_source",
            f"{metric}_as_of",
            f"{metric}_quality",
        }:
            return metric
    return None


def summarize_validation_issues(issues: Sequence[dict[str, str]]) -> dict[str, int]:
    """Summarize validation issues by severity for manifests."""

    errors = sum(1 for issue in issues if issue.get("severity", "error") == "error")
    warnings = sum(1 for issue in issues if issue.get("severity", "error") == "warning")
    return {
        "total": len(issues),
        "errors": errors,
        "warnings": warnings,
    }


def _yahoo_lookup_symbol(row: dict[str, str]) -> str:
    yahoo_symbol = row.get("yahoo_symbol", "").strip()
    if yahoo_symbol:
        return yahoo_symbol
    return row.get("symbol", "").strip()


def _read_yahoo_ticker_info_worker(symbol: str, result_queue: multiprocessing.Queue) -> None:
    try:
        result_queue.put(("ok", _read_yahoo_ticker_info(symbol)))
    except BaseException as exc:  # noqa: BLE001 - subprocess boundary must report all failures.
        result_queue.put(("error", f"{type(exc).__name__}: {exc}"))


def _read_yahoo_ticker_info_with_timeout(
    symbol: str,
    *,
    timeout_seconds: float,
) -> dict[str, object]:
    if timeout_seconds <= 0:
        return _read_yahoo_ticker_info(symbol)
    ctx = multiprocessing.get_context("spawn" if os.name == "nt" else "fork")
    result_queue: multiprocessing.Queue = ctx.Queue(maxsize=1)
    process = ctx.Process(target=_read_yahoo_ticker_info_worker, args=(symbol, result_queue))
    process.daemon = True
    process.start()
    process.join(timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join(timeout=2)
        if process.is_alive():
            process.kill()
            process.join(timeout=2)
        raise TimeoutError(f"Yahoo metadata request timed out after {timeout_seconds:g}s")
    try:
        status, payload = result_queue.get_nowait()
    except queue.Empty as exc:
        raise RuntimeError("Yahoo metadata subprocess exited without a result") from exc
    if status == "ok" and isinstance(payload, dict):
        return payload
    raise RuntimeError(str(payload))


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
        values["theme"] = _theme_for_sector(sector)

    dividend_yield_pct = _yahoo_dividend_yield_pct(row, info)
    if dividend_yield_pct is not None:
        values["dividend_yield_pct"] = _format_decimal(dividend_yield_pct)
        values["dividend_category"] = _dividend_category(dividend_yield_pct)
    elif _existing_dividend_yield_pct_is_abnormal(row):
        values["dividend_yield_pct"] = ""
        values["dividend_category"] = ""

    per = _guard_per(_optional_decimal_info(info, "trailingPE")) or _guard_per(
        _optional_decimal_info(info, "forwardPE")
    )
    if per is not None:
        values["per"] = _format_decimal(per)
    elif _existing_per_is_abnormal(row):
        values["per"] = ""

    pbr = _guard_pbr(_optional_decimal_info(info, "priceToBook"))
    if pbr is not None:
        values["pbr"] = _format_decimal(pbr)
    elif _existing_pbr_is_abnormal(row):
        values["pbr"] = ""

    roe = _optional_decimal_info(info, "returnOnEquity")
    roe_pct = _guard_roe_pct(_yahoo_return_on_equity_pct(roe))
    if roe_pct is not None:
        values["roe_pct"] = _format_decimal(roe_pct)
    elif _existing_roe_pct_is_abnormal(row):
        values["roe_pct"] = ""

    market_cap = _optional_decimal_info(info, "marketCap")
    if market_cap is not None:
        values["market_cap"] = _format_decimal(market_cap)
        values["market_cap_tier"] = _market_cap_tier(
            market_cap,
            currency=str(info.get("currency") or row.get("currency") or ""),
            symbol=row.get("symbol", ""),
        )

    beta = _optional_decimal_info(info, "beta")
    if beta is not None:
        values["risk_band"] = _risk_band(beta)

    expense_ratio_pct = _yahoo_expense_ratio_pct(info)
    if row.get("asset_type") == "etf" and expense_ratio_pct is not None and expense_ratio_pct >= 0:
        values["expense_ratio_pct"] = _format_decimal(expense_ratio_pct)

    average_volume = (
        _optional_decimal_info(info, "averageVolume")
        or _optional_decimal_info(info, "averageDailyVolume10Day")
        or _optional_decimal_info(info, "averageVolume10days")
        or _optional_decimal_info(info, "threeMonthAverageVolume")
    )
    if average_volume is not None and average_volume >= 0:
        values["average_volume"] = _format_decimal(average_volume)

    if row.get("asset_type") in {"etf", "fund"}:
        aum = _optional_decimal_info(info, "totalAssets")
        if aum is not None and aum >= 0:
            values["aum"] = _format_decimal(aum)
        asset_class = str(info.get("category") or "").strip()
        if asset_class:
            values["asset_class"] = asset_class

    return values


def _has_substantive_metadata_values(values: dict[str, str]) -> bool:
    ignored = {
        "metadata_source",
        "metadata_as_of",
        "metadata_updated_at",
        "yahoo_symbol",
        "yahoo_symbol_status",
        "yahoo_symbol_checked_at",
    }
    return any(str(value).strip() for key, value in values.items() if key not in ignored)


def _optional_decimal_info(info: dict[str, object], key: str) -> Decimal | None:
    return _optional_decimal_value(info.get(key))


def _optional_decimal_value(value: object) -> Decimal | None:
    if value is None or str(value).lower() == "nan":
        return None
    try:
        decimal_value = Decimal(str(value))
    except InvalidOperation:
        return None
    if not decimal_value.is_finite():
        return None
    return decimal_value


def _ratio_to_percent(value: Decimal) -> Decimal:
    if abs(value) <= Decimal("1"):
        return value * Decimal("100")
    return value


def _yahoo_dividend_yield_pct(row: dict[str, str], info: dict[str, object]) -> Decimal | None:
    trailing_yield = _optional_decimal_info(info, "trailingAnnualDividendYield")
    if trailing_yield is not None:
        guarded_trailing_yield = _guard_dividend_yield_ratio(trailing_yield)
        if guarded_trailing_yield is not None:
            return _ratio_to_percent(guarded_trailing_yield)

    dividend_yield = _optional_decimal_info(info, "dividendYield")
    if dividend_yield is None or dividend_yield < 0:
        return None
    dividend_yield_ratio = _guard_dividend_yield_ratio(
        _normalize_yahoo_dividend_yield_ratio(row, dividend_yield)
    )
    if dividend_yield_ratio is None:
        return None
    return _ratio_to_percent(dividend_yield_ratio)


def _normalize_yahoo_dividend_yield_ratio(row: dict[str, str], value: Decimal) -> Decimal:
    is_jp_stock = row.get("asset_type") == "stock" and (
        row.get("market") == "jp" or row.get("symbol", "").endswith(".T")
    )
    if is_jp_stock and value >= Decimal("10") and value == value.to_integral_value():
        return value / Decimal("10000")
    if value > YAHOO_PERCENT_STYLE_DIVIDEND_YIELD_THRESHOLD:
        return value / Decimal("100")
    return value


def _guard_dividend_yield_ratio(value: Decimal) -> Decimal | None:
    if value < 0 or value > MAX_REASONABLE_DIVIDEND_YIELD_RATIO:
        return None
    return value


def _guard_per(value: Decimal | None) -> Decimal | None:
    if value is None or value <= 0 or value > MAX_REASONABLE_PER:
        return None
    return value


def _guard_pbr(value: Decimal | None) -> Decimal | None:
    if value is None or value <= 0 or value > MAX_REASONABLE_PBR:
        return None
    return value


def _yahoo_return_on_equity_pct(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value * Decimal("100")


def _guard_roe_pct(value: Decimal | None) -> Decimal | None:
    if value is None or value < MIN_REASONABLE_ROE_PCT or value > MAX_REASONABLE_ROE_PCT:
        return None
    return value


def _existing_dividend_yield_pct_is_abnormal(row: dict[str, str]) -> bool:
    value = _optional_decimal_value(row.get("dividend_yield_pct"))
    return value is not None and (
        value < 0 or value > MAX_REASONABLE_DIVIDEND_YIELD_RATIO * Decimal("100")
    )


def _existing_per_is_abnormal(row: dict[str, str]) -> bool:
    return _guard_per(_optional_decimal_value(row.get("per"))) is None and bool(
        row.get("per", "").strip()
    )


def _existing_pbr_is_abnormal(row: dict[str, str]) -> bool:
    return _guard_pbr(_optional_decimal_value(row.get("pbr"))) is None and bool(
        row.get("pbr", "").strip()
    )


def _existing_roe_pct_is_abnormal(row: dict[str, str]) -> bool:
    return _guard_roe_pct(_optional_decimal_value(row.get("roe_pct"))) is None and bool(
        row.get("roe_pct", "").strip()
    )


def _yahoo_expense_ratio_pct(info: dict[str, object]) -> Decimal | None:
    annual_ratio = _optional_decimal_info(info, "annualReportExpenseRatio")
    if annual_ratio is not None:
        return _ratio_to_percent(annual_ratio)

    net_expense_ratio = _optional_decimal_info(info, "netExpenseRatio")
    if net_expense_ratio is None:
        return None
    # yfinance commonly exposes netExpenseRatio as a percentage value
    # (for example, 0.03 means 0.03%).
    return net_expense_ratio


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


def _theme_for_sector(sector: str) -> str:
    return {
        "communication": "communication",
        "consumer": "consumer",
        "energy": "energy",
        "financial": "financial",
        "healthcare": "healthcare",
        "industrial": "balanced",
        "materials": "balanced",
        "real_estate": "balanced",
        "technology": "technology",
        "utilities": "energy",
    }.get(sector, "balanced")


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
