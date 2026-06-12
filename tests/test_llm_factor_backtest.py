from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from backend.llm_factor import (
    LLMFactorBacktestCase,
    LLMFactorBacktestSignal,
    LLMFactorPriceBar,
    run_llm_factor_backtest,
)


def test_bullish_top_n_mean_return_is_positive_or_exceeds_universe() -> None:
    result = run_llm_factor_backtest(_fixture_case(horizons=[1], top_n=1))
    metrics = _metric(result, "llm_bullish_score", 1)

    assert metrics.top_n_mean_return is not None
    assert metrics.universe_mean_return is not None
    assert metrics.top_n_mean_return > 0
    assert metrics.top_n_mean_return > metrics.universe_mean_return
    assert metrics.excess_top_n_mean_return == pytest.approx(
        metrics.top_n_mean_return - metrics.universe_mean_return
    )


def test_bearish_high_score_has_high_down_rate() -> None:
    result = run_llm_factor_backtest(_fixture_case(horizons=[1], top_n=1, high_score_quantile=0.6))
    metrics = _metric(result, "llm_bearish_score", 1)

    assert metrics.high_score_down_rate == pytest.approx(1.0)
    assert metrics.high_score_hit_rate == pytest.approx(0.0)


def test_risk_high_score_has_larger_drawdown() -> None:
    result = run_llm_factor_backtest(_fixture_case(horizons=[3], top_n=1))
    metrics = _metric(result, "llm_risk_score", 3)

    assert metrics.high_score_avg_drawdown is not None
    assert metrics.universe_avg_drawdown is not None
    assert metrics.high_score_avg_drawdown == pytest.approx(-0.2)
    assert metrics.high_score_avg_drawdown < metrics.universe_avg_drawdown


def test_net_material_score_is_derived() -> None:
    signal_date = date(2026, 1, 1)
    case = LLMFactorBacktestCase(
        case_id="net-derived",
        signals=[
            _signal("RAW_BULLISH", signal_date, bullish=90, bearish=95),
            _signal("NET_WINNER", signal_date, bullish=80, bearish=0),
        ],
        prices=[
            *_flat_path("RAW_BULLISH", signal_date, entry=100, exit_price=90),
            *_flat_path("NET_WINNER", signal_date, entry=100, exit_price=120),
        ],
        horizons=[1],
        top_n=1,
        min_samples=1,
        min_dates=1,
    )

    result = run_llm_factor_backtest(case)

    assert _metric(result, "llm_bullish_score", 1).top_n_mean_return == pytest.approx(-0.1)
    assert _metric(result, "llm_net_material_score", 1).top_n_mean_return == pytest.approx(0.2)


def test_quality_adjusted_net_score_is_derived() -> None:
    signal_date = date(2026, 1, 1)
    case = LLMFactorBacktestCase(
        case_id="quality-adjusted-net",
        signals=[
            _signal(
                "HIGH_RAW_LOW_QUALITY",
                signal_date,
                bullish=95,
                bearish=0,
                confidence=1,
                evidence_quality=1,
                freshness=1,
            ),
            _signal(
                "LOW_RAW_HIGH_QUALITY",
                signal_date,
                bullish=50,
                bearish=0,
                confidence=100,
                evidence_quality=100,
                freshness=100,
            ),
        ],
        prices=[
            *_flat_path("HIGH_RAW_LOW_QUALITY", signal_date, entry=100, exit_price=90),
            *_flat_path("LOW_RAW_HIGH_QUALITY", signal_date, entry=100, exit_price=115),
        ],
        horizons=[1],
        top_n=1,
        min_samples=1,
        min_dates=1,
    )

    result = run_llm_factor_backtest(case)

    assert _metric(result, "llm_net_material_score", 1).top_n_mean_return == pytest.approx(-0.1)
    assert _metric(result, "llm_quality_adjusted_net", 1).top_n_mean_return == pytest.approx(0.15)


def test_missing_price_emits_warning() -> None:
    signal_date = date(2026, 1, 1)
    case = LLMFactorBacktestCase(
        case_id="missing-price",
        signals=[_signal("AAA", signal_date)],
        prices=_flat_path("AAA", signal_date, entry=100, exit_price=101),
        horizons=[5],
        min_samples=1,
        min_dates=1,
    )

    result = run_llm_factor_backtest(case)

    assert _warning_codes(result) >= {"MISSING_PRICE", "LOW_COVERAGE"}
    assert _metric(result, "llm_bullish_score", 5).sample_count == 0


def test_insufficient_samples_warning() -> None:
    signal_date = date(2026, 1, 1)
    case = LLMFactorBacktestCase(
        case_id="insufficient-samples",
        signals=[_signal("AAA", signal_date)],
        prices=_flat_path("AAA", signal_date, entry=100, exit_price=105),
        horizons=[1],
        min_samples=2,
        min_dates=1,
    )

    result = run_llm_factor_backtest(case)

    assert "INSUFFICIENT_SAMPLES" in _warning_codes(result)


def test_result_is_reproducible() -> None:
    case = _fixture_case(horizons=[1, 3], top_n=1)

    first = run_llm_factor_backtest(case)
    second = run_llm_factor_backtest(case)

    assert second.model_dump(mode="json") == first.model_dump(mode="json")
    assert second.input_hash == first.input_hash
    assert second.config_hash == first.config_hash


def test_entry_lag_prevents_same_day_leakage() -> None:
    signal_date = date(2026, 1, 1)
    case = LLMFactorBacktestCase(
        case_id="entry-lag",
        signals=[_signal("AAA", signal_date, bullish=90)],
        prices=[
            LLMFactorPriceBar(symbol="AAA", date=signal_date, open=1000, close=1000),
            LLMFactorPriceBar(symbol="AAA", date=signal_date + timedelta(days=1), close=100),
            LLMFactorPriceBar(symbol="AAA", date=signal_date + timedelta(days=2), close=110),
        ],
        horizons=[1],
        top_n=1,
        min_samples=1,
        min_dates=1,
        entry_lag_bars=1,
    )

    result = run_llm_factor_backtest(case)

    assert _metric(result, "llm_bullish_score", 1).top_n_mean_return == pytest.approx(0.1)
    assert "LOOKAHEAD_RISK" not in _warning_codes(result)


def test_zero_variance_factor_warning() -> None:
    case = _fixture_case(horizons=[1], top_n=1, bullish_override=50)

    result = run_llm_factor_backtest(case)

    assert any(
        warning.code == "ZERO_VARIANCE_FACTOR"
        and warning.factor_name == "llm_bullish_score"
        and warning.horizon_days == 1
        for warning in result.warnings
    )
    assert _metric(result, "llm_bullish_score", 1).zero_variance_factor is True


def test_duplicate_signal_warning_keeps_first_canonical_signal() -> None:
    signal_date = date(2026, 1, 1)
    case = LLMFactorBacktestCase(
        case_id="duplicate-signal",
        signals=[
            _signal("AAA", signal_date, bullish=90, result_id="a"),
            _signal("AAA", signal_date, bullish=10, result_id="b"),
            _signal("BBB", signal_date, bullish=20),
        ],
        prices=[
            *_flat_path("AAA", signal_date, entry=100, exit_price=110),
            *_flat_path("BBB", signal_date, entry=100, exit_price=90),
        ],
        horizons=[1],
        top_n=1,
        min_samples=1,
        min_dates=1,
    )

    result = run_llm_factor_backtest(case)

    assert "DUPLICATE_SIGNAL" in _warning_codes(result)
    assert _metric(result, "llm_bullish_score", 1).top_n_mean_return == pytest.approx(0.1)


def test_entry_lag_zero_emits_lookahead_warning() -> None:
    signal_date = date(2026, 1, 1)
    case = LLMFactorBacktestCase(
        case_id="lookahead-risk",
        signals=[_signal("AAA", signal_date)],
        prices=_flat_path("AAA", signal_date, entry=100, exit_price=105),
        horizons=[1],
        min_samples=1,
        min_dates=1,
        entry_lag_bars=0,
    )

    result = run_llm_factor_backtest(case)

    assert "LOOKAHEAD_RISK" in _warning_codes(result)


def _fixture_case(
    *,
    horizons: list[int],
    top_n: int,
    high_score_quantile: float = 0.8,
    bullish_override: float | None = None,
) -> LLMFactorBacktestCase:
    signal_dates = [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)]
    signals: list[LLMFactorBacktestSignal] = []
    prices: list[LLMFactorPriceBar] = []
    for signal_date in signal_dates:
        signals.extend(
            [
                _signal(
                    "GOOD",
                    signal_date,
                    bullish=bullish_override if bullish_override is not None else 95,
                    bearish=5,
                    risk=10,
                    catalyst=80,
                ),
                _signal(
                    "MID",
                    signal_date,
                    bullish=bullish_override if bullish_override is not None else 55,
                    bearish=25,
                    risk=25,
                    catalyst=50,
                ),
                _signal(
                    "BAD",
                    signal_date,
                    bullish=bullish_override if bullish_override is not None else 20,
                    bearish=95,
                    risk=60,
                    catalyst=40,
                ),
                _signal(
                    "RISK",
                    signal_date,
                    bullish=bullish_override if bullish_override is not None else 10,
                    bearish=85,
                    risk=98,
                    catalyst=35,
                ),
                _signal(
                    "CAT",
                    signal_date,
                    bullish=bullish_override if bullish_override is not None else 70,
                    bearish=20,
                    risk=20,
                    catalyst=95,
                ),
            ]
        )
        prices.extend(_price_path("GOOD", signal_date, exit_day_1=110, exit_day_3=112))
        prices.extend(_price_path("MID", signal_date, exit_day_1=102, exit_day_3=103))
        prices.extend(_price_path("BAD", signal_date, exit_day_1=90, exit_day_3=88))
        prices.extend(_price_path("RISK", signal_date, exit_day_1=95, exit_day_3=95, day_2=80))
        prices.extend(_price_path("CAT", signal_date, exit_day_1=105, exit_day_3=107))
    return LLMFactorBacktestCase(
        case_id="fixture",
        signals=signals,
        prices=prices,
        horizons=horizons,
        top_n=top_n,
        high_score_quantile=high_score_quantile,
        min_samples=1,
        min_dates=1,
        entry_lag_bars=1,
    )


def _signal(
    symbol: str,
    signal_date: date,
    *,
    bullish: float = 60,
    bearish: float = 20,
    catalyst: float = 50,
    risk: float = 20,
    confidence: float = 80,
    evidence_quality: float = 80,
    freshness: float = 80,
    result_id: str | None = None,
) -> LLMFactorBacktestSignal:
    return LLMFactorBacktestSignal(
        symbol=symbol,
        signal_date=signal_date,
        available_at=datetime.combine(signal_date, datetime.min.time(), tzinfo=UTC),
        bullish_score=bullish,
        bearish_score=bearish,
        catalyst_score=catalyst,
        risk_score=risk,
        confidence_score=confidence,
        evidence_quality_score=evidence_quality,
        freshness_score=freshness,
        source_count=2,
        llm_factor_result_id=result_id,
    )


def _price_path(
    symbol: str,
    signal_date: date,
    *,
    exit_day_1: float,
    exit_day_3: float,
    day_2: float | None = None,
) -> list[LLMFactorPriceBar]:
    prices = [100, 100, exit_day_1, day_2 if day_2 is not None else exit_day_1, exit_day_3]
    return [
        LLMFactorPriceBar(
            symbol=symbol,
            date=signal_date + timedelta(days=offset),
            close=price,
        )
        for offset, price in enumerate(prices)
    ]


def _flat_path(
    symbol: str,
    signal_date: date,
    *,
    entry: float,
    exit_price: float,
) -> list[LLMFactorPriceBar]:
    return [
        LLMFactorPriceBar(symbol=symbol, date=signal_date, close=entry),
        LLMFactorPriceBar(symbol=symbol, date=signal_date + timedelta(days=1), close=entry),
        LLMFactorPriceBar(symbol=symbol, date=signal_date + timedelta(days=2), close=exit_price),
    ]


def _metric(result, factor_name: str, horizon_days: int):
    for metric in result.metrics:
        if metric.factor_name == factor_name and metric.horizon_days == horizon_days:
            return metric
    raise AssertionError(f"metric not found: {factor_name} horizon={horizon_days}")


def _warning_codes(result) -> set[str]:
    return {warning.code for warning in result.warnings}
