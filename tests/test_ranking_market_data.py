from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime

from ui.ranking_market_data import (
    acquire_ranking_fundamental_inputs,
    acquire_ranking_market_data_inputs,
    build_ranking_feature_inputs,
)


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


def test_fundamental_input_stage_restores_symbols_and_keeps_non_fatal_errors() -> None:
    received: dict[str, object] = {}

    async def fetch_fundamentals(adapter, symbols, **kwargs):
        received["adapter"] = adapter
        received["symbols"] = symbols
        received["kwargs"] = kwargs
        return [], [{"symbol": "AAPL", "reason": "unavailable"}]

    def restore_symbols(fundamentals, **kwargs):
        received["fundamentals"] = fundamentals
        received["mapping"] = kwargs["provider_symbols_by_symbol"]
        return fundamentals

    result = asyncio.run(
        acquire_ranking_fundamental_inputs(
            ["7203.T", "AAPL"],
            provider="yahoo",
            as_of=date(2026, 7, 20),
            adapter="adapter",
            provider_symbols_by_symbol={"7203.T": "7203.T", "AAPL": "AAPL"},
            display_symbols_by_provider_symbol={"7203.T": ["7203.T"], "AAPL": ["AAPL"]},
            fetch_fundamentals=fetch_fundamentals,
            fundamentals_with_display_symbols=restore_symbols,
        )
    )

    assert result.fundamentals == []
    assert result.error_rows == [{"symbol": "AAPL", "reason": "unavailable"}]
    assert received["adapter"] == "adapter"
    assert received["symbols"] == ["7203.T", "AAPL"]
    assert received["mapping"] == {"7203.T": "7203.T", "AAPL": "AAPL"}


def test_feature_input_stage_preserves_builder_rows_provider_and_summaries() -> None:
    received: dict[str, object] = {}

    class Adapter:
        @staticmethod
        def healthcheck() -> dict[str, str]:
            return {"provider": "fixture-provider"}

    def build_rows(**kwargs):
        received.update(kwargs)
        return []

    result = build_ranking_feature_inputs(
        ["7203.T"],
        as_of=date(2026, 7, 20),
        adapter=Adapter(),
        provider="fixture",
        quotes=[],
        fundamentals=[],
        bars=[],
        feature_builder_config="feature-config",
        build_feature_rows=build_rows,
        build_missing_summary=lambda _rows: {"close": 1},
        build_quality_summary=lambda _rows: {"WARN": 1},
    )

    assert received["symbols"] == ["7203.T"]
    assert received["cfg"] == "feature-config"
    assert result.provider_name == "fixture-provider"
    assert result.feature_rows == []
    assert result.feature_snapshot.missing_summary == {"close": 1}
    assert result.feature_snapshot.quality_summary == {"WARN": 1}
