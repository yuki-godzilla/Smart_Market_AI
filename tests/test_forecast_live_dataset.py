from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from backend.core.data_contracts import Bar, Symbol
from backend.forecast.live_dataset import collect_forecast_live_dataset


class _Provider:
    def __init__(self, missing: set[str] | None = None) -> None:
        self.missing = missing or set()

    async def fetch_ohlcv(self, symbols, start, end, interval="1d"):
        return [
            Bar(
                symbol=Symbol(
                    raw=symbol,
                    exchange="NASDAQ",
                    code=symbol,
                    currency="USD",
                ),
                ts=end - timedelta(days=1),
                open=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100"),
                volume=Decimal("1000"),
                interval=interval,
                provider="fixture",
            )
            for symbol in symbols
            if symbol not in self.missing
        ]


def test_live_collection_publishes_complete_typed_snapshot(tmp_path: Path) -> None:
    metadata = _metadata(tmp_path)
    end = datetime(2026, 7, 20, tzinfo=UTC)
    result = asyncio.run(
        collect_forecast_live_dataset(
            _Provider(),
            provider_name="fixture",
            symbols=["MSFT", "AAPL"],
            start=end - timedelta(days=365),
            end=end,
            batch_size=1,
            metadata_source=metadata,
            output_dir=tmp_path / "snapshot",
            started_at=end,
        )
    )

    assert result.complete is True
    assert result.requested_symbols == ["AAPL", "MSFT"]
    assert result.returned_symbols == ["AAPL", "MSFT"]
    assert result.bar_count == 2
    assert Path(result.ohlcv_path).is_file()
    assert (tmp_path / "snapshot" / "collection_manifest.json").is_file()


def test_live_collection_marks_missing_symbol_incomplete(tmp_path: Path) -> None:
    metadata = _metadata(tmp_path)
    end = datetime(2026, 7, 20, tzinfo=UTC)
    result = asyncio.run(
        collect_forecast_live_dataset(
            _Provider(missing={"MSFT"}),
            provider_name="fixture",
            symbols=["AAPL", "MSFT"],
            start=end - timedelta(days=365),
            end=end,
            batch_size=2,
            metadata_source=metadata,
            output_dir=tmp_path / "incomplete",
            started_at=end,
        )
    )

    assert result.complete is False
    assert [(item.symbols, item.reason) for item in result.failures] == [(["MSFT"], "no_bars")]
    assert "MSFT,no_bars" in Path(result.failures_path).read_text("utf-8")


def _metadata(tmp_path: Path) -> Path:
    path = tmp_path / "metadata.csv"
    path.write_text(
        "symbol,market,asset_type,currency,exchange,local_symbol\n"
        "AAPL,US,stock,USD,NASDAQ,AAPL\n"
        "MSFT,US,stock,USD,NASDAQ,MSFT\n",
        encoding="utf-8",
    )
    return path
