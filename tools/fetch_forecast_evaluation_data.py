from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_SYMBOLS = (
    "7203.T",
    "6758.T",
    "8306.T",
    "9984.T",
    "9432.T",
    "8035.T",
    "1306.T",
    "1321.T",
    "1489.T",
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "GOOGL",
    "JPM",
    "XOM",
    "JNJ",
    "SPY",
    "QQQ",
    "IWM",
    "TLT",
    "GLD",
    "VTI",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Explicitly fetch long Yahoo OHLCV for offline forecast evaluation.",
    )
    parser.add_argument("--allow-live", action="store_true")
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=6)
    parser.add_argument("--symbols", nargs="*", default=list(DEFAULT_SYMBOLS))
    parser.add_argument("--metadata", default="data/marketdata/symbol_universe.csv")
    parser.add_argument("--output-dir", default="data/forecast_evaluation")
    args = parser.parse_args(argv)
    if not args.allow_live:
        parser.error("--allow-live is required for external Yahoo access")
    if args.years < 2:
        parser.error("--years must be at least 2")
    if args.batch_size < 1:
        parser.error("--batch-size must be positive")
    return asyncio.run(_run(args))


async def _run(args: argparse.Namespace) -> int:
    from backend.core.config import DataAccessConfig, TimeoutConfig
    from backend.marketdata.providers.yahoo import YahooMarketDataProviderAdapter

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    end = datetime.now(UTC)
    start = end - timedelta(days=365 * args.years)
    provider = YahooMarketDataProviderAdapter(
        DataAccessConfig(
            provider="yahoo",
            allow_external_providers=True,
            timeouts_ms=TimeoutConfig(connect=5000, read=30000),
        )
    )
    all_bars = []
    failures: list[dict[str, str]] = []
    symbols = list(dict.fromkeys(args.symbols))
    for offset in range(0, len(symbols), args.batch_size):
        batch = symbols[offset : offset + args.batch_size]
        try:
            bars = await provider.fetch_ohlcv(batch, start=start, end=end, interval="1d")
        except Exception as exc:  # noqa: BLE001 - explicit live collection must continue.
            bars = []
            failures.append(
                {
                    "symbols": ",".join(batch),
                    "error": type(exc).__name__,
                }
            )
        returned = {bar.symbol.raw for bar in bars}
        all_bars.extend(bars)
        for symbol in batch:
            if symbol not in returned:
                failures.append({"symbols": symbol, "error": "no_bars"})
        print(f"batch {offset // args.batch_size + 1}: {len(bars)} bars")

    _write_ohlcv(output_dir / "ohlcv.csv", all_bars)
    _write_metadata_subset(
        Path(args.metadata),
        output_dir / "symbols.csv",
        {bar.symbol.raw for bar in all_bars},
    )
    _write_failures(output_dir / "fetch_failures.csv", failures)
    print(
        f"forecast evaluation live dataset: {len(all_bars)} bars / {len(set(bar.symbol.raw for bar in all_bars))} symbols"
    )
    return 0 if all_bars else 2


def _write_ohlcv(path: Path, bars) -> None:
    fieldnames = ["symbol", "ts", "open", "high", "low", "close", "volume"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for bar in sorted(bars, key=lambda item: (item.symbol.raw, item.ts)):
            writer.writerow(
                {
                    "symbol": bar.symbol.raw,
                    "ts": bar.ts.isoformat(),
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                    "volume": bar.volume,
                }
            )


def _write_metadata_subset(source: Path, target: Path, symbols: set[str]) -> None:
    with source.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        rows = [row for row in reader if row.get("symbol") in symbols]
    by_symbol = {row["symbol"]: row for row in rows}
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for symbol in sorted(symbols):
            row = by_symbol.get(symbol)
            if row is not None:
                writer.writerow(row)


def _write_failures(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["symbols", "error"],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
