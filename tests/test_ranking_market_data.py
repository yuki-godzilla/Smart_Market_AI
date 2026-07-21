from __future__ import annotations

import asyncio
import math
from datetime import UTC, date, datetime
from types import SimpleNamespace

from ui.ranking_market_data import (
    acquire_ranking_fundamental_inputs,
    acquire_ranking_market_data_inputs,
    build_ranking_feature_inputs,
    build_ranking_forecast_inputs,
    build_ranking_presentation_inputs,
    build_ranking_score_inputs,
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


def test_forecast_input_stage_preserves_consensus_and_progress_cadence() -> None:
    progress: list[tuple[str, float]] = []
    evaluation_calls: list[tuple[list[object], int]] = []
    bars_by_symbol = {symbol: [object()] for symbol in ["AAA", "BBB", "CCC"]}
    symbols_by_history_id = {id(bars[0]): symbol for symbol, bars in bars_by_symbol.items()}

    def build_evaluations(history, *, horizon_days):
        evaluation_calls.append((history, horizon_days))
        return ["evaluation"]

    def summarize(evaluations, *, history):
        assert evaluations == ["evaluation"]
        return SimpleNamespace(symbol=symbols_by_history_id[id(history[0])])

    result = build_ranking_forecast_inputs(
        ["AAA", "BBB", "CCC"],
        bars_by_symbol=bars_by_symbol,
        horizon_days=20,
        build_evaluations=build_evaluations,
        summarize_consensus=summarize,
        report_progress=lambda _callback, message, ratio: progress.append((message, ratio)),
        progress_callback=None,
    )

    assert set(result.consensus_by_symbol) == {"AAA", "BBB", "CCC"}
    assert result.horizon_days == 20
    assert [horizon for _history, horizon in evaluation_calls] == [20, 20, 20]
    assert [message for message, _ratio in progress] == [
        "基本予測を計算しています (1/3)。",
        "基本予測を計算しています (3/3)。",
    ]
    assert math.isclose(progress[0][1], 0.65 + 0.05 / 3)
    assert math.isclose(progress[1][1], 0.7)


def test_score_input_stage_preserves_service_order_consensus_and_rows() -> None:
    events: list[object] = []
    feature_snapshot = build_ranking_feature_inputs(
        [],
        as_of=date(2026, 7, 20),
        adapter=type("Adapter", (), {"healthcheck": lambda self: {"provider": "fixture"}})(),
        provider="fixture",
        quotes=[],
        fundamentals=[],
        bars=[],
        feature_builder_config=None,
        build_feature_rows=lambda **_kwargs: [],
        build_missing_summary=lambda _rows: {},
        build_quality_summary=lambda _rows: {},
    ).feature_snapshot
    consensus = {"AAA": SimpleNamespace(symbol="AAA")}

    def score_screening(snapshot, *, forecast_consensus_by_symbol):
        events.append(("screening", snapshot, forecast_consensus_by_symbol))
        return ["screening-score"]

    def score_investment(screening_scores, *, forecast_consensus_by_symbol):
        events.append(("investment", screening_scores, forecast_consensus_by_symbol))
        return ["investment-score"]

    def build_rows(investment_scores):
        events.append(("rows", investment_scores))
        return [{"symbol": "AAA"}]

    result = build_ranking_score_inputs(
        feature_snapshot,
        forecast_consensus_by_symbol=consensus,
        score_screening=score_screening,
        score_investment=score_investment,
        build_investment_rows=build_rows,
    )

    assert result.score_rows == [{"symbol": "AAA"}]
    assert [event[0] for event in events] == ["screening", "investment", "rows"]
    assert events[0][2] is consensus
    assert events[1][1] == ["screening-score"]


def test_presentation_input_stage_enriches_then_sorts_existing_rows() -> None:
    events: list[object] = []

    def enrich_feature(rows, feature_rows, **kwargs):
        events.append(("feature", rows, feature_rows, kwargs))
        return [{**row, "feature": "ready"} for row in rows]

    def enrich_advanced(rows, fields):
        events.append(("advanced", rows, fields))
        return [{**row, "advanced": fields.get(row["symbol"], {}).get("value", "")} for row in rows]

    def sort_rows(rows):
        events.append(("sort", rows))
        return list(reversed(rows))

    result = build_ranking_presentation_inputs(
        [{"symbol": "AAA"}, {"symbol": "BBB"}],
        feature_rows=[],
        bars_by_symbol={},
        source_currency_by_symbol={"AAA": "USD"},
        usd_jpy_rate="150",
        jpy_fx_rates={"USD": "150"},
        provider_name="fixture",
        advanced_forecast_fields_by_symbol={"AAA": {"value": "up"}},
        enrich_feature_details=enrich_feature,
        enrich_advanced_forecast=enrich_advanced,
        build_latest_volume=lambda _bars: {"AAA": "100"},
        sort_rows=sort_rows,
    )

    assert [event[0] for event in events] == ["feature", "advanced", "sort"]
    assert events[0][3]["latest_volume_by_symbol"] == {"AAA": "100"}
    assert result.ranked_rows == [
        {"symbol": "BBB", "feature": "ready", "advanced": ""},
        {"symbol": "AAA", "feature": "ready", "advanced": "up"},
    ]
