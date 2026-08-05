"""Strict live OHLCV snapshot collection for sealed Forecast audits."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, Sequence

from pydantic import Field

from backend.core.data_contracts import Bar, Interval, StrictBaseModel

FORECAST_LIVE_DATASET_SCHEMA_VERSION = "forecast-live-dataset-v1"


class ForecastOHLCVProvider(Protocol):
    async def fetch_ohlcv(
        self,
        symbols: list[str],
        start: datetime,
        end: datetime,
        interval: Interval = "1d",
    ) -> list[Bar]: ...


class ForecastLiveDatasetFailure(StrictBaseModel):
    symbols: list[str] = Field(min_length=1)
    reason: str = Field(min_length=1)
    error_type: str | None = None


class ForecastLiveDatasetCollectionResult(StrictBaseModel):
    schema_version: str = FORECAST_LIVE_DATASET_SCHEMA_VERSION
    provider: str = Field(min_length=1)
    started_at: datetime
    completed_at: datetime
    requested_symbols: list[str] = Field(min_length=1)
    returned_symbols: list[str]
    batch_count: int = Field(ge=1)
    bar_count: int = Field(ge=0)
    complete: bool
    ohlcv_path: str = Field(min_length=1)
    metadata_path: str = Field(min_length=1)
    failures_path: str = Field(min_length=1)
    failures: list[ForecastLiveDatasetFailure] = Field(default_factory=list)


async def collect_forecast_live_dataset(
    provider: ForecastOHLCVProvider,
    *,
    provider_name: str,
    symbols: Sequence[str],
    start: datetime,
    end: datetime,
    batch_size: int,
    metadata_source: Path,
    output_dir: Path,
    started_at: datetime,
) -> ForecastLiveDatasetCollectionResult:
    """Collect one diagnostic snapshot without mutating the sealed audit database."""

    _require_aware(start, "start")
    _require_aware(end, "end")
    _require_aware(started_at, "started_at")
    if end <= start:
        raise ValueError("end must follow start")
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    normalized_symbols = sorted({_normalize_symbol(symbol) for symbol in symbols if symbol.strip()})
    if not normalized_symbols:
        raise ValueError("at least one symbol is required")
    if not metadata_source.is_file():
        raise ValueError(f"metadata CSV not found: {metadata_source}")

    bars: list[Bar] = []
    failures: list[ForecastLiveDatasetFailure] = []
    for offset in range(0, len(normalized_symbols), batch_size):
        batch = normalized_symbols[offset : offset + batch_size]
        try:
            fetched = await provider.fetch_ohlcv(batch, start=start, end=end, interval="1d")
        except Exception as exc:  # noqa: BLE001 - preserve other batches and a typed reason.
            failures.append(
                ForecastLiveDatasetFailure(
                    symbols=batch,
                    reason="provider_error",
                    error_type=type(exc).__name__,
                )
            )
            continue
        expected = set(batch)
        returned = {_normalize_symbol(bar.symbol.raw) for bar in fetched}
        unexpected = sorted(returned - expected)
        if unexpected:
            failures.append(
                ForecastLiveDatasetFailure(
                    symbols=unexpected,
                    reason="unexpected_symbol",
                )
            )
        bars.extend(bar for bar in fetched if _normalize_symbol(bar.symbol.raw) in expected)
        for symbol in sorted(expected - returned):
            failures.append(ForecastLiveDatasetFailure(symbols=[symbol], reason="no_bars"))

    duplicate_keys = _duplicate_bar_keys(bars)
    for symbol in sorted({symbol for symbol, _ in duplicate_keys}):
        failures.append(
            ForecastLiveDatasetFailure(
                symbols=[symbol],
                reason="duplicate_bar_timestamp",
            )
        )
    invalid_bars = [
        bar
        for bar in bars
        if bar.interval != "1d"
        or bar.ts.tzinfo is None
        or bar.ts.utcoffset() is None
        or bar.ts < start
        or bar.ts > end
    ]
    if invalid_bars:
        failures.append(
            ForecastLiveDatasetFailure(
                symbols=sorted({_normalize_symbol(bar.symbol.raw) for bar in invalid_bars}),
                reason="invalid_bar_contract",
            )
        )
    providers = {bar.provider for bar in bars}
    if len(providers) > 1:
        failures.append(
            ForecastLiveDatasetFailure(
                symbols=normalized_symbols,
                reason="mixed_provider",
            )
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    ohlcv_path = output_dir / "ohlcv.csv"
    metadata_path = output_dir / "symbols.csv"
    failures_path = output_dir / "fetch_failures.csv"
    write_forecast_ohlcv_csv(ohlcv_path, bars)
    metadata_symbols = write_forecast_metadata_subset(
        metadata_source,
        metadata_path,
        set(normalized_symbols),
    )
    for symbol in sorted(set(normalized_symbols) - metadata_symbols):
        failures.append(ForecastLiveDatasetFailure(symbols=[symbol], reason="missing_metadata"))
    write_forecast_collection_failures(failures_path, failures)

    returned_symbols = sorted({_normalize_symbol(bar.symbol.raw) for bar in bars})
    complete = not failures and returned_symbols == normalized_symbols and bool(bars)
    result = ForecastLiveDatasetCollectionResult(
        provider=provider_name.strip() or "unknown",
        started_at=started_at,
        completed_at=datetime.now(UTC),
        requested_symbols=normalized_symbols,
        returned_symbols=returned_symbols,
        batch_count=(len(normalized_symbols) + batch_size - 1) // batch_size,
        bar_count=len(bars),
        complete=complete,
        ohlcv_path=str(ohlcv_path),
        metadata_path=str(metadata_path),
        failures_path=str(failures_path),
        failures=failures,
    )
    (output_dir / "collection_manifest.json").write_text(
        result.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return result


def write_forecast_ohlcv_csv(path: Path, bars: Sequence[Bar]) -> None:
    fieldnames = ["symbol", "ts", "open", "high", "low", "close", "volume"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for bar in sorted(bars, key=lambda item: (_normalize_symbol(item.symbol.raw), item.ts)):
            writer.writerow(
                {
                    "symbol": _normalize_symbol(bar.symbol.raw),
                    "ts": bar.ts.isoformat(),
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                    "volume": bar.volume,
                }
            )


def write_forecast_metadata_subset(source: Path, target: Path, symbols: set[str]) -> set[str]:
    with source.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        if "symbol" not in fieldnames:
            raise ValueError("metadata CSV is missing symbol column")
        rows = [row for row in reader if _normalize_symbol(row.get("symbol", "")) in symbols]
    by_symbol = {_normalize_symbol(row["symbol"]): row for row in rows}
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for symbol in sorted(symbols):
            row = by_symbol.get(symbol)
            if row is not None:
                writer.writerow(row)
    return set(by_symbol)


def write_forecast_collection_failures(
    path: Path,
    rows: Sequence[ForecastLiveDatasetFailure],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["symbols", "reason", "error_type"],
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "symbols": ",".join(row.symbols),
                    "reason": row.reason,
                    "error_type": row.error_type or "",
                }
            )


def _duplicate_bar_keys(bars: Sequence[Bar]) -> set[tuple[str, datetime]]:
    seen: set[tuple[str, datetime]] = set()
    duplicates: set[tuple[str, datetime]] = set()
    for bar in bars:
        key = (_normalize_symbol(bar.symbol.raw), bar.ts)
        if key in seen:
            duplicates.add(key)
        seen.add(key)
    return duplicates


def _normalize_symbol(value: str) -> str:
    return value.strip().upper()


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
