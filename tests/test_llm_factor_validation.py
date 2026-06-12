from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from backend.llm_factor import (
    LLMFactorBacktestSignal,
    LLMFactorBaselineScore,
    LLMFactorFixtureManifest,
    LLMFactorHistoricalFixturePack,
    LLMFactorPriceBar,
    LLMFactorValidationConfig,
    build_llm_factor_validation_report_json,
    build_llm_factor_validation_report_markdown,
    load_llm_factor_historical_fixture_pack,
    run_llm_factor_backtest,
    run_llm_factor_validation_report,
)


def test_historical_fixture_pack_loads_deterministically() -> None:
    first = load_llm_factor_historical_fixture_pack()
    second = load_llm_factor_historical_fixture_pack()

    assert second.manifest.fixture_hash == first.manifest.fixture_hash
    assert second.signals == first.signals
    assert second.prices == first.prices
    assert second.baseline_scores == first.baseline_scores


def test_fixture_pack_contains_required_segments() -> None:
    pack = load_llm_factor_historical_fixture_pack()

    assert {
        "jp_large_cap",
        "us_large_cap",
        "etf",
        "high_dividend",
        "growth",
        "low_news_coverage",
        "osaka_gas_9532_t",
        "mixed_global",
    } <= set(pack.manifest.segments)
    assert pack.manifest.is_synthetic_or_static is True
    assert "deterministic validation fixture" in pack.manifest.data_policy


def test_classification_metrics_for_bullish_up_label() -> None:
    signal_date = date(2026, 1, 1)
    pack = _pack(
        signals=[
            _signal("AAA", signal_date, bullish=90, bearish=10),
            _signal("BBB", signal_date, bullish=10, bearish=90),
            _signal("AAA", signal_date + timedelta(days=10), bullish=90, bearish=10),
            _signal("BBB", signal_date + timedelta(days=10), bullish=10, bearish=90),
        ],
        prices=[
            *_path("AAA", signal_date, {1: 0.10}),
            *_path("BBB", signal_date, {1: -0.10}),
            *_path("AAA", signal_date + timedelta(days=10), {1: 0.12}),
            *_path("BBB", signal_date + timedelta(days=10), {1: -0.08}),
        ],
    )
    report = run_llm_factor_validation_report(pack, _config())
    metrics = _classification(report, "llm_bullish_score", "up")

    assert metrics.accuracy == pytest.approx(1.0)
    assert metrics.precision == pytest.approx(1.0)
    assert metrics.recall == pytest.approx(1.0)
    assert metrics.f1 == pytest.approx(1.0)
    assert metrics.auc == pytest.approx(1.0)


def test_bearish_predicts_down_label() -> None:
    signal_date = date(2026, 1, 1)
    pack = _pack(
        signals=[
            _signal("AAA", signal_date, bullish=10, bearish=90),
            _signal("BBB", signal_date, bullish=90, bearish=10),
            _signal("AAA", signal_date + timedelta(days=10), bullish=10, bearish=90),
            _signal("BBB", signal_date + timedelta(days=10), bullish=90, bearish=10),
        ],
        prices=[
            *_path("AAA", signal_date, {1: -0.10}),
            *_path("BBB", signal_date, {1: 0.10}),
            *_path("AAA", signal_date + timedelta(days=10), {1: -0.12}),
            *_path("BBB", signal_date + timedelta(days=10), {1: 0.08}),
        ],
    )
    report = run_llm_factor_validation_report(pack, _config())
    metrics = _classification(report, "llm_bearish_score", "down")

    assert metrics.precision == pytest.approx(1.0)
    assert metrics.recall == pytest.approx(1.0)
    assert metrics.auc == pytest.approx(1.0)


def test_risk_predicts_drawdown_label() -> None:
    signal_date = date(2026, 1, 1)
    pack = _pack(
        signals=[
            _signal("RISK", signal_date, bullish=20, bearish=80, risk=95),
            _signal("CALM", signal_date, bullish=70, bearish=20, risk=10),
            _signal("RISK", signal_date + timedelta(days=10), bullish=20, bearish=80, risk=95),
            _signal("CALM", signal_date + timedelta(days=10), bullish=70, bearish=20, risk=10),
        ],
        prices=[
            *_path("RISK", signal_date, {1: -0.12}),
            *_path("CALM", signal_date, {1: 0.02}),
            *_path("RISK", signal_date + timedelta(days=10), {1: -0.10}),
            *_path("CALM", signal_date + timedelta(days=10), {1: 0.03}),
        ],
    )
    report = run_llm_factor_validation_report(pack, _config(drawdown_threshold=0.05))
    classification = _classification(report, "llm_risk_score", "drawdown")
    risk = _risk(report, "llm_risk_score")

    assert classification.auc == pytest.approx(1.0)
    assert risk.high_score_avg_drawdown is not None
    assert risk.high_score_avg_drawdown <= -0.10


def test_auc_undefined_single_class_warning() -> None:
    signal_date = date(2026, 1, 1)
    pack = _pack(
        signals=[_signal("AAA", signal_date, bullish=80), _signal("BBB", signal_date, bullish=20)],
        prices=[*_path("AAA", signal_date, {1: 0.05}), *_path("BBB", signal_date, {1: 0.02})],
    )
    report = run_llm_factor_validation_report(pack, _config())
    metrics = _classification(report, "llm_bullish_score", "up")

    assert metrics.auc is None
    assert "AUC_UNDEFINED_SINGLE_CLASS" in _warning_codes(report)


def test_class_imbalance_warning() -> None:
    signal_date = date(2026, 1, 1)
    signals = [_signal(f"S{i}", signal_date, bullish=100 - i) for i in range(20)]
    prices = [
        bar
        for index, signal in enumerate(signals)
        for bar in _path(signal.symbol, signal_date, {1: 0.03 if index == 0 else -0.01})
    ]
    report = run_llm_factor_validation_report(
        pack := _pack(signals=signals, prices=prices), _config()
    )

    assert pack.manifest.signal_count == 20
    assert "CLASS_IMBALANCE" in _warning_codes(report)


def test_top_bottom_spread() -> None:
    signal_date = date(2026, 1, 1)
    pack = _pack(
        signals=[
            _signal("TOP", signal_date, bullish=90),
            _signal("MID", signal_date, bullish=50),
            _signal("BOT", signal_date, bullish=10),
        ],
        prices=[
            *_path("TOP", signal_date, {1: 0.10}),
            *_path("MID", signal_date, {1: 0.00}),
            *_path("BOT", signal_date, {1: -0.10}),
        ],
    )
    report = run_llm_factor_validation_report(pack, _config(top_quantile=0.67))
    metrics = _return_metric(report, "llm_bullish_score")

    assert metrics.top_quantile_mean_return == pytest.approx(0.10)
    assert metrics.bottom_quantile_mean_return == pytest.approx(-0.10)
    assert metrics.top_bottom_spread == pytest.approx(0.20)


def test_period_sharpe_and_max_drawdown() -> None:
    signal_date = date(2026, 1, 1)
    returns = [0.10, -0.05, 0.05]
    signals: list[LLMFactorBacktestSignal] = []
    prices: list[LLMFactorPriceBar] = []
    for index, forward_return in enumerate(returns):
        day = signal_date + timedelta(days=index * 10)
        signals.extend([_signal("TOP", day, bullish=90), _signal("BOT", day, bullish=10)])
        prices.extend(_path("TOP", day, {1: forward_return}))
        prices.extend(_path("BOT", day, {1: 0.00}))
    report = run_llm_factor_validation_report(_pack(signals=signals, prices=prices), _config())
    metrics = _risk(report, "llm_bullish_score")

    assert metrics.top_n_period_sharpe == pytest.approx(0.43643578)
    assert metrics.top_n_max_drawdown == pytest.approx(-0.05)


def test_sharpe_zero_volatility_warning() -> None:
    signal_date = date(2026, 1, 1)
    signals: list[LLMFactorBacktestSignal] = []
    prices: list[LLMFactorPriceBar] = []
    for index in range(3):
        day = signal_date + timedelta(days=index * 10)
        signals.extend([_signal("TOP", day, bullish=90), _signal("BOT", day, bullish=10)])
        prices.extend(_path("TOP", day, {1: 0.02}))
        prices.extend(_path("BOT", day, {1: 0.00}))
    report = run_llm_factor_validation_report(_pack(signals=signals, prices=prices), _config())

    assert _risk(report, "llm_bullish_score").top_n_period_sharpe is None
    assert "SHARPE_ZERO_VOLATILITY" in _warning_codes(report)


def test_overlapping_horizon_returns_warning() -> None:
    signal_date = date(2026, 1, 1)
    pack = _pack(
        signals=[_signal("AAA", signal_date, bullish=90), _signal("BBB", signal_date, bullish=10)],
        prices=[*_path("AAA", signal_date, {5: 0.05}), *_path("BBB", signal_date, {5: -0.02})],
    )
    report = run_llm_factor_validation_report(pack, _config(horizons=[5]))

    assert "OVERLAPPING_HORIZON_RETURNS" in _warning_codes(report)


def test_baseline_comparison_delta_metrics() -> None:
    signal_date = date(2026, 1, 1)
    signals = [
        _signal("AAA", signal_date, bullish=90),
        _signal("BBB", signal_date, bullish=10),
        _signal("AAA", signal_date + timedelta(days=10), bullish=90),
        _signal("BBB", signal_date + timedelta(days=10), bullish=10),
    ]
    baseline_scores = [
        _baseline(signal, "ranking_score", 10 if signal.symbol == "AAA" else 90)
        for signal in signals
    ]
    baseline_scores.extend(_baseline(signal, "forecast_score", 50) for signal in signals)
    baseline_scores.extend(_baseline(signal, "investment_score", 50) for signal in signals)
    baseline_scores.extend(_baseline(signal, "naive_baseline", 50) for signal in signals)
    pack = _pack(
        signals=signals,
        prices=[
            *_path("AAA", signal_date, {1: 0.10}),
            *_path("BBB", signal_date, {1: -0.10}),
            *_path("AAA", signal_date + timedelta(days=10), {1: 0.10}),
            *_path("BBB", signal_date + timedelta(days=10), {1: -0.10}),
        ],
        baseline_scores=baseline_scores,
    )
    report = run_llm_factor_validation_report(pack, _config())
    comparison = next(
        metric
        for metric in report.baseline_comparison_metrics
        if metric.factor_name == "llm_bullish_score" and metric.baseline_name == "ranking_score"
    )

    assert comparison.delta_auc is not None
    assert comparison.delta_auc > 0
    assert comparison.delta_top_n_mean_return is not None
    assert comparison.delta_top_n_mean_return > 0


def test_default_fixture_baseline_comparison_covers_expected_baselines() -> None:
    report = run_llm_factor_validation_report(
        load_llm_factor_historical_fixture_pack(),
        _config(horizons=[1]),
    )

    assert {
        "ranking_score",
        "forecast_score",
        "investment_score",
        "naive_baseline",
    } <= {metric.baseline_name for metric in report.baseline_comparison_metrics}


def test_missing_baseline_scores_do_not_break_report() -> None:
    signal_date = date(2026, 1, 1)
    report = run_llm_factor_validation_report(
        _pack(
            signals=[_signal("AAA", signal_date, bullish=90)],
            prices=_path("AAA", signal_date, {1: 0.05}),
            baseline_scores=[],
        ),
        _config(),
    )

    assert report.baseline_comparison_metrics == []
    assert "BASELINE_SCORE_MISSING" in _warning_codes(report)


def test_segment_metrics_are_computed() -> None:
    pack = load_llm_factor_historical_fixture_pack()
    report = run_llm_factor_validation_report(pack, _config(horizons=[1]))

    assert any(
        metric.segment_name == "symbol_group" and metric.segment_value == "low_news_coverage"
        for metric in report.segment_metrics
    )
    assert any(segment == "low_news_coverage" for segment in report.summary.segments)


def test_segment_too_small_warning() -> None:
    report = run_llm_factor_validation_report(
        load_llm_factor_historical_fixture_pack(),
        _config(horizons=[1], min_segment_samples=10_000),
    )

    assert "SEGMENT_TOO_SMALL" in _warning_codes(report)


def test_low_evidence_coverage_warning() -> None:
    pack = load_llm_factor_historical_fixture_pack()
    report = run_llm_factor_validation_report(
        pack,
        _config(horizons=[1], low_evidence_ratio_threshold=0.1),
    )

    assert "LOW_EVIDENCE_COVERAGE" in _warning_codes(report)


def test_validation_report_is_reproducible() -> None:
    pack = load_llm_factor_historical_fixture_pack()
    config = _config(horizons=[1])

    first = run_llm_factor_validation_report(pack, config)
    second = run_llm_factor_validation_report(pack, config)

    assert second.generated_report_hash == first.generated_report_hash
    assert build_llm_factor_validation_report_json(
        second
    ) == build_llm_factor_validation_report_json(first)
    assert build_llm_factor_validation_report_markdown(
        second
    ) == build_llm_factor_validation_report_markdown(first)


def test_report_explicitly_says_not_integrated() -> None:
    pack = load_llm_factor_historical_fixture_pack()
    report = run_llm_factor_validation_report(pack, _config(horizons=[1]))
    markdown = build_llm_factor_validation_report_markdown(report)

    assert "Ranking" in markdown
    assert "Forecast" in markdown
    assert "Investment Score" in markdown
    assert "には反映していません" in markdown
    assert "売買推奨ではありません" in markdown


def test_recommendation_does_not_enable_integration() -> None:
    report = run_llm_factor_validation_report(
        load_llm_factor_historical_fixture_pack(),
        _config(horizons=[1]),
    )

    assert report.recommendation.should_integrate_into_ranking_now is False
    assert report.recommendation.should_integrate_into_forecast_now is False
    assert report.recommendation.should_integrate_into_investment_score_now is False


def test_existing_backtest_first_slice_still_runs() -> None:
    signal_date = date(2026, 1, 1)
    result = run_llm_factor_backtest(
        _backtest_case(
            signals=[
                _signal("AAA", signal_date, bullish=90),
                _signal("BBB", signal_date, bullish=10),
            ],
            prices=[*_path("AAA", signal_date, {1: 0.10}), *_path("BBB", signal_date, {1: -0.10})],
        )
    )

    assert result.metrics
    assert result.input_hash
    assert result.config_hash


def _config(**updates: Any) -> LLMFactorValidationConfig:
    payload: dict[str, Any] = {
        "horizons": [1],
        "top_n": 1,
        "top_quantile": 0.5,
        "min_samples": 1,
        "min_dates": 1,
        "min_segment_samples": 1,
    }
    payload.update(updates)
    return LLMFactorValidationConfig(**payload)


def _pack(
    *,
    signals: list[LLMFactorBacktestSignal],
    prices: list[LLMFactorPriceBar],
    baseline_scores: list[LLMFactorBaselineScore] | None = None,
    symbol_segments: dict[str, dict[str, str]] | None = None,
) -> LLMFactorHistoricalFixturePack:
    dates = [signal.signal_date for signal in signals] + [price.date for price in prices]
    segments = symbol_segments or {
        signal.symbol: {
            "market": "TEST",
            "style": "unit",
            "news_coverage": "medium",
            "symbol_group": "unit",
        }
        for signal in signals
    }
    baseline_rows = (
        baseline_scores
        if baseline_scores is not None
        else [_baseline(signal, "ranking_score", 50) for signal in signals]
    )
    return LLMFactorHistoricalFixturePack(
        fixture_id="unit-fixture",
        version="v1",
        description="unit fixture",
        signals=signals,
        prices=prices,
        baseline_scores=baseline_rows,
        symbol_segments=segments,
        manifest=LLMFactorFixtureManifest(
            fixture_id="unit-fixture",
            version="v1",
            generated_by="tests",
            is_synthetic_or_static=True,
            data_policy="deterministic validation fixture",
            markets=["TEST"],
            segments=sorted({value for item in segments.values() for value in item.values()}),
            symbol_count=len(segments),
            signal_count=len(signals),
            price_bar_count=len(prices),
            start_date=min(dates),
            end_date=max(dates),
            fixture_hash="unit-fixture-hash",
        ),
    )


def _backtest_case(
    *,
    signals: list[LLMFactorBacktestSignal],
    prices: list[LLMFactorPriceBar],
):
    from backend.llm_factor import LLMFactorBacktestCase

    return LLMFactorBacktestCase(
        case_id="unit-backtest",
        signals=signals,
        prices=prices,
        horizons=[1],
        top_n=1,
        min_samples=1,
        min_dates=1,
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
    source_count: int = 2,
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
        source_count=source_count,
        llm_factor_result_id=f"{symbol}:{signal_date.isoformat()}",
    )


def _baseline(
    signal: LLMFactorBacktestSignal,
    baseline_name: str,
    score: float | None,
) -> LLMFactorBaselineScore:
    return LLMFactorBaselineScore(
        symbol=signal.symbol,
        signal_date=signal.signal_date,
        baseline_name=baseline_name,
        score=score,
    )


def _path(
    symbol: str,
    signal_date: date,
    returns: dict[int, float],
) -> list[LLMFactorPriceBar]:
    bars = [
        LLMFactorPriceBar(symbol=symbol, date=signal_date, close=100),
        LLMFactorPriceBar(symbol=symbol, date=signal_date + timedelta(days=1), close=100),
    ]
    max_horizon = max(returns)
    for offset in range(1, max_horizon + 1):
        forward_return = returns.get(offset)
        if forward_return is None:
            lower_horizons = [horizon for horizon in returns if horizon < offset]
            upper_horizons = [horizon for horizon in returns if horizon > offset]
            if lower_horizons and upper_horizons:
                left = max(lower_horizons)
                right = min(upper_horizons)
                ratio = (offset - left) / (right - left)
                forward_return = returns[left] + (returns[right] - returns[left]) * ratio
            else:
                forward_return = returns[min(returns)]
        bars.append(
            LLMFactorPriceBar(
                symbol=symbol,
                date=signal_date + timedelta(days=1 + offset),
                close=100 * (1 + forward_return),
            )
        )
    return bars


def _classification(report, factor_name: str, task: str):
    for metric in report.classification_metrics:
        if metric.factor_name == factor_name and metric.prediction_task == task:
            return metric
    raise AssertionError(f"classification metric not found: {factor_name} {task}")


def _return_metric(report, factor_name: str):
    for metric in report.return_metrics:
        if metric.factor_name == factor_name:
            return metric
    raise AssertionError(f"return metric not found: {factor_name}")


def _risk(report, factor_name: str):
    for metric in report.risk_metrics:
        if metric.factor_name == factor_name:
            return metric
    raise AssertionError(f"risk metric not found: {factor_name}")


def _warning_codes(report) -> set[str]:
    return {warning.code for warning in report.warnings}
