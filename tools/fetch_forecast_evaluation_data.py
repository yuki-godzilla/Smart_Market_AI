from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.forecast.live_dataset import (  # noqa: E402
    collect_forecast_live_dataset,
    write_forecast_ohlcv_csv,
)

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

    end = datetime.now(UTC)
    start = end - timedelta(days=365 * args.years)
    provider = YahooMarketDataProviderAdapter(
        DataAccessConfig(
            provider="yahoo",
            allow_external_providers=True,
            timeouts_ms=TimeoutConfig(connect=5000, read=30000),
        )
    )
    symbols = list(dict.fromkeys(args.symbols))
    result = await collect_forecast_live_dataset(
        provider,
        provider_name="yahoo",
        symbols=symbols,
        start=start,
        end=end,
        batch_size=args.batch_size,
        metadata_source=Path(args.metadata),
        output_dir=Path(args.output_dir),
        started_at=end,
    )
    print(
        f"forecast evaluation live dataset: {result.bar_count} bars / "
        f"{len(result.returned_symbols)} symbols / complete={str(result.complete).lower()}"
    )
    for failure in result.failures:
        print(
            f"failure: {','.join(failure.symbols)}:{failure.reason}:" f"{failure.error_type or '-'}"
        )
    return 0 if result.complete else 2


def _write_ohlcv(path: Path, bars) -> None:
    write_forecast_ohlcv_csv(path, bars)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
