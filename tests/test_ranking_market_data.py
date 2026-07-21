from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime

from ui.ranking_market_data import acquire_ranking_market_data_inputs


def test_market_data_input_stage_keeps_provider_failure_distinct_from_no_bars() -> None:
    progress: list[tuple[str, float]] = []

    async def fetch_ohlcv(*_args, **_kwargs):
        return [], [], {"BBB"}

    async def fetch_fx(_adapter, _currencies):
        return {"USD": "150"}

    def no_bars_error(**kwargs):
        return {"kind": "no_bars", "symbol": kwargs["symbol"]}

    result = asyncio.run(
        acquire_ranking_market_data_inputs(
            ["AAA", "BBB"],
            provider="fixture",
            start=date(2026, 7, 1),
            end=date(2026, 7, 20),
            adapter=object(),
            feature_start=datetime(2026, 4, 1, tzinfo=UTC),
            fetch_end=datetime(2026, 7, 20, tzinfo=UTC),
            provider_symbols_by_symbol={"AAA": "AAA", "BBB": "BBB"},
            symbol_chunks=[["AAA", "BBB"]],
            display_symbols_by_provider_symbol={"AAA": ["AAA"], "BBB": ["BBB"]},
            fetch_ohlcv=fetch_ohlcv,
            bars_with_display_symbols=lambda bars, **_kwargs: bars,
            bars_by_symbol_builder=lambda symbols, _bars: {symbol: [] for symbol in symbols},
            currency_by_symbol_builder=lambda _bars_by_symbol: {"AAA": "USD", "BBB": "USD"},
            fetch_jpy_fx_rates=fetch_fx,
            no_bars_error_row=no_bars_error,
            insufficient_bars_error_row=lambda **_kwargs: {"kind": "insufficient"},
            report_progress=lambda _callback, message, ratio: progress.append((message, ratio)),
            progress_callback=None,
        )
    )

    assert result.available_symbols == []
    assert result.quotes == []
    assert result.error_rows == [{"kind": "no_bars", "symbol": "AAA"}]
    assert result.usd_jpy_rate == "150"
    assert progress[0][0] == "価格データをまとめて取得しています (1/1)。"
    assert progress[-1] == ("価格データを整理しています。", 0.45)
