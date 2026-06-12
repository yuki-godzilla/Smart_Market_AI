from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date
from statistics import median, stdev

from backend.llm_factor.backtest_contracts import (
    LLMFactorBacktestSignal,
    LLMFactorBacktestWarning,
    LLMFactorPriceBar,
)
from backend.llm_factor.validation_contracts import (
    LLMFactorBaselineComparisonMetrics,
    LLMFactorBaselineScore,
    LLMFactorClassificationMetrics,
    LLMFactorConfusionMatrix,
    LLMFactorPredictionTask,
    LLMFactorReturnMetrics,
    LLMFactorRiskMetrics,
    LLMFactorSegmentMetrics,
    LLMFactorThresholdPolicy,
    LLMFactorValidationConfig,
)


@dataclass(frozen=True)
class LLMFactorEvaluationSample:
    symbol: str
    signal_date: date
    signal: LLMFactorBacktestSignal
    horizon_days: int
    forward_return: float
    drawdown: float
    segments: dict[str, str]


@dataclass(frozen=True)
class _ScoredEvaluationSample:
    symbol: str
    signal_date: date
    factor_score: float
    forward_return: float
    drawdown: float
    segments: dict[str, str]


_FactorGetter = Callable[[LLMFactorBacktestSignal], float]
_FactorDefinition = tuple[str, _FactorGetter]

BASELINE_NAMES: tuple[str, ...] = (
    "ranking_score",
    "forecast_score",
    "investment_score",
    "naive_baseline",
)

BASE_FACTOR_DEFINITIONS: tuple[_FactorDefinition, ...] = (
    ("llm_bullish_score", lambda signal: signal.bullish_score),
    ("llm_bearish_score", lambda signal: signal.bearish_score),
    ("llm_catalyst_score", lambda signal: signal.catalyst_score),
    ("llm_risk_score", lambda signal: signal.risk_score),
    ("llm_confidence_score", lambda signal: signal.confidence_score),
    ("llm_evidence_quality_score", lambda signal: signal.evidence_quality_score),
    ("llm_freshness_score", lambda signal: signal.freshness_score),
    ("llm_net_material_score", lambda signal: signal.bullish_score - signal.bearish_score),
    (
        "llm_quality_adjusted_bullish",
        lambda signal: signal.bullish_score
        * signal.confidence_score
        * signal.evidence_quality_score
        * signal.freshness_score,
    ),
    (
        "llm_quality_adjusted_net",
        lambda signal: (signal.bullish_score - signal.bearish_score)
        * signal.confidence_score
        * signal.evidence_quality_score
        * signal.freshness_score,
    ),
    (
        "llm_catalyst_with_freshness",
        lambda signal: signal.catalyst_score * signal.freshness_score,
    ),
    (
        "llm_risk_adjusted_material",
        lambda signal: signal.bullish_score - signal.bearish_score - signal.risk_score,
    ),
)

DIRECTIONAL_CATALYST_FACTOR: _FactorDefinition = (
    "llm_directional_catalyst_score",
    lambda signal: _sign(signal.bullish_score - signal.bearish_score)
    * signal.catalyst_score
    * signal.freshness_score,
)

PREDICTION_TASK_BY_FACTOR: dict[str, LLMFactorPredictionTask] = {
    "llm_bullish_score": "up",
    "llm_net_material_score": "up",
    "llm_quality_adjusted_bullish": "up",
    "llm_quality_adjusted_net": "up",
    "llm_bearish_score": "down",
    "llm_risk_score": "drawdown",
    "llm_catalyst_score": "absolute_move",
    "llm_catalyst_with_freshness": "absolute_move",
    "llm_risk_adjusted_material": "up",
    "llm_directional_catalyst_score": "up",
}


def factor_definitions(config: LLMFactorValidationConfig) -> tuple[_FactorDefinition, ...]:
    definitions = list(BASE_FACTOR_DEFINITIONS)
    if config.include_directional_catalyst_factor:
        definitions.append(DIRECTIONAL_CATALYST_FACTOR)
    return tuple(definitions)


def build_llm_factor_evaluation_samples(
    *,
    signals: Iterable[LLMFactorBacktestSignal],
    prices: Iterable[LLMFactorPriceBar],
    horizons: Iterable[int],
    entry_lag_bars: int,
    symbol_segments: dict[str, dict[str, str]] | None = None,
) -> tuple[dict[int, list[LLMFactorEvaluationSample]], list[LLMFactorBacktestWarning]]:
    price_index = _price_index(prices)
    segment_index = {
        _symbol_key(symbol): dict(segments) for symbol, segments in (symbol_segments or {}).items()
    }
    warnings: list[LLMFactorBacktestWarning] = []
    samples_by_horizon: dict[int, list[LLMFactorEvaluationSample]] = {}
    signal_list = sorted(signals, key=lambda row: (_symbol_key(row.symbol), row.signal_date))
    for horizon in sorted({horizon for horizon in horizons if horizon > 0}):
        samples: list[LLMFactorEvaluationSample] = []
        missing_count = 0
        for signal in signal_list:
            symbol_key = _symbol_key(signal.symbol)
            symbol_prices = price_index.get(symbol_key, [])
            base_index = _first_price_index_on_or_after(symbol_prices, signal.signal_date)
            if base_index is None:
                missing_count += 1
                continue
            entry_index = base_index + entry_lag_bars
            exit_index = entry_index + horizon
            if entry_index < 0 or exit_index >= len(symbol_prices):
                missing_count += 1
                continue
            window = symbol_prices[entry_index : exit_index + 1]
            if len(window) != horizon + 1:
                missing_count += 1
                continue
            entry_price = _price_value(window[0])
            exit_price = _price_value(window[-1])
            if entry_price <= 0 or exit_price <= 0:
                missing_count += 1
                continue
            drawdown = min((_price_value(bar) / entry_price) - 1 for bar in window)
            samples.append(
                LLMFactorEvaluationSample(
                    symbol=signal.symbol,
                    signal_date=signal.signal_date,
                    signal=signal,
                    horizon_days=horizon,
                    forward_return=(exit_price / entry_price) - 1,
                    drawdown=drawdown,
                    segments=segment_index.get(symbol_key, {}),
                )
            )
        samples_by_horizon[horizon] = samples
        if missing_count:
            warnings.append(
                LLMFactorBacktestWarning(
                    code="MISSING_PRICE",
                    message=(
                        f"horizon={horizon} で validation fixture の価格が足りない"
                        f" signal を {missing_count} 件除外しました。"
                    ),
                    horizon_days=horizon,
                    severity="warning",
                )
            )
    return samples_by_horizon, warnings


def compute_classification_metrics(
    *,
    samples_by_horizon: dict[int, list[LLMFactorEvaluationSample]],
    config: LLMFactorValidationConfig,
    factor_getters: tuple[_FactorDefinition, ...],
) -> tuple[list[LLMFactorClassificationMetrics], list[LLMFactorBacktestWarning]]:
    metrics: list[LLMFactorClassificationMetrics] = []
    warnings: list[LLMFactorBacktestWarning] = []
    for factor_name, score_getter in factor_getters:
        task = PREDICTION_TASK_BY_FACTOR.get(factor_name)
        if task is None:
            continue
        if task == "absolute_move" and not config.include_absolute_move_task:
            continue
        for horizon in sorted(samples_by_horizon):
            factor_metrics, factor_warnings = classification_metrics_for_samples(
                samples=samples_by_horizon[horizon],
                factor_name=factor_name,
                score_getter=score_getter,
                prediction_task=task,
                config=config,
            )
            metrics.append(factor_metrics)
            warnings.extend(factor_warnings)
    return metrics, warnings


def classification_metrics_for_samples(
    *,
    samples: list[LLMFactorEvaluationSample],
    factor_name: str,
    score_getter: _FactorGetter,
    prediction_task: LLMFactorPredictionTask,
    config: LLMFactorValidationConfig,
) -> tuple[LLMFactorClassificationMetrics, list[LLMFactorBacktestWarning]]:
    scored_samples = [
        _ScoredEvaluationSample(
            symbol=sample.symbol,
            signal_date=sample.signal_date,
            factor_score=score_getter(sample.signal),
            forward_return=sample.forward_return,
            drawdown=sample.drawdown,
            segments=sample.segments,
        )
        for sample in samples
    ]
    labels = [_label_for_task(sample, prediction_task, config) for sample in scored_samples]
    scores = [sample.factor_score for sample in scored_samples]
    predictions = _binary_predictions(
        scored_samples,
        threshold_policy=config.threshold_policy,
        score_threshold=config.fixed_score_threshold,
        quantile=config.top_quantile,
    )
    positive_count = sum(1 for label in labels if label)
    negative_count = len(labels) - positive_count
    tp = sum(
        1 for label, prediction in zip(labels, predictions, strict=True) if label and prediction
    )
    fp = sum(
        1 for label, prediction in zip(labels, predictions, strict=True) if not label and prediction
    )
    tn = sum(
        1
        for label, prediction in zip(labels, predictions, strict=True)
        if not label and not prediction
    )
    fn = sum(
        1 for label, prediction in zip(labels, predictions, strict=True) if label and not prediction
    )
    accuracy = None if not labels else (tp + tn) / len(labels)
    precision = _safe_ratio(tp, tp + fp)
    recall = _safe_ratio(tp, tp + fn)
    f1 = (
        None
        if precision is None or recall is None or precision + recall == 0
        else 2 * precision * recall / (precision + recall)
    )
    auc = _auc(labels, scores)
    average_precision = _average_precision(labels, scores)
    positive_rate = None if not labels else positive_count / len(labels)
    warnings = _classification_warnings(
        factor_name=factor_name,
        horizon_days=samples[0].horizon_days if samples else None,
        prediction_task=prediction_task,
        positive_rate=positive_rate,
        auc=auc,
        config=config,
    )
    return (
        LLMFactorClassificationMetrics(
            factor_name=factor_name,
            horizon_days=samples[0].horizon_days if samples else 1,
            prediction_task=prediction_task,
            sample_count=len(labels),
            positive_count=positive_count,
            negative_count=negative_count,
            positive_rate=positive_rate,
            threshold_policy=config.threshold_policy,
            score_threshold=(
                config.fixed_score_threshold
                if config.threshold_policy == "fixed_score_threshold"
                else None
            ),
            quantile=(
                config.top_quantile if config.threshold_policy == "top_quantile_by_date" else None
            ),
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1=f1,
            auc=auc,
            average_precision=average_precision,
            confusion_matrix=LLMFactorConfusionMatrix(tp=tp, fp=fp, tn=tn, fn=fn),
        ),
        warnings,
    )


def compute_return_metrics(
    *,
    samples_by_horizon: dict[int, list[LLMFactorEvaluationSample]],
    signal_count: int,
    config: LLMFactorValidationConfig,
    factor_getters: tuple[_FactorDefinition, ...],
    segment_filter: tuple[str, str] | None = None,
) -> list[LLMFactorReturnMetrics]:
    metrics: list[LLMFactorReturnMetrics] = []
    for factor_name, score_getter in factor_getters:
        for horizon in sorted(samples_by_horizon):
            samples = _filter_samples_by_segment(samples_by_horizon[horizon], segment_filter)
            metrics.append(
                return_metrics_for_samples(
                    samples=samples,
                    factor_name=factor_name,
                    score_getter=score_getter,
                    horizon_days=horizon,
                    signal_count=signal_count,
                    top_n=config.top_n,
                    top_quantile=config.top_quantile,
                    segment=_segment_label(segment_filter),
                )
            )
    return metrics


def return_metrics_for_samples(
    *,
    samples: list[LLMFactorEvaluationSample],
    factor_name: str,
    score_getter: _FactorGetter,
    horizon_days: int,
    signal_count: int,
    top_n: int,
    top_quantile: float,
    segment: str | None = None,
) -> LLMFactorReturnMetrics:
    scored_samples = _scored_samples(samples, score_getter)
    grouped = _group_by_signal_date(scored_samples)
    daily_universe_means: list[float] = []
    daily_universe_medians: list[float] = []
    daily_top_means: list[float] = []
    daily_top_medians: list[float] = []
    daily_top_hit_rates: list[float] = []
    daily_top_quantile_means: list[float] = []
    daily_bottom_quantile_means: list[float] = []
    for signal_date in sorted(grouped):
        day_samples = grouped[signal_date]
        sorted_samples = sorted(day_samples, key=lambda row: (-row.factor_score, row.symbol))
        top_samples = sorted_samples[: min(top_n, len(sorted_samples))]
        quantile_count = _top_quantile_count(len(sorted_samples), top_quantile)
        top_quantile_samples = sorted_samples[:quantile_count]
        bottom_quantile_samples = list(reversed(sorted_samples[-quantile_count:]))
        daily_universe_means.append(_required_mean(row.forward_return for row in day_samples))
        daily_universe_medians.append(median(row.forward_return for row in day_samples))
        daily_top_means.append(_required_mean(row.forward_return for row in top_samples))
        daily_top_medians.append(median(row.forward_return for row in top_samples))
        daily_top_hit_rates.append(
            _required_mean(1.0 if row.forward_return > 0 else 0.0 for row in top_samples)
        )
        daily_top_quantile_means.append(
            _required_mean(row.forward_return for row in top_quantile_samples)
        )
        daily_bottom_quantile_means.append(
            _required_mean(row.forward_return for row in bottom_quantile_samples)
        )
    universe_mean = _mean_or_none(daily_universe_means)
    top_n_mean = _mean_or_none(daily_top_means)
    top_quantile_mean = _mean_or_none(daily_top_quantile_means)
    bottom_quantile_mean = _mean_or_none(daily_bottom_quantile_means)
    return LLMFactorReturnMetrics(
        factor_name=factor_name,
        horizon_days=horizon_days,
        segment=segment,
        sample_count=len(scored_samples),
        date_count=len(grouped),
        coverage_ratio=(len(scored_samples) / signal_count if signal_count else 0.0),
        universe_mean_return=universe_mean,
        universe_median_return=_mean_or_none(daily_universe_medians),
        top_n_mean_return=top_n_mean,
        top_n_median_return=_mean_or_none(daily_top_medians),
        top_n_hit_rate=_mean_or_none(daily_top_hit_rates),
        top_quantile_mean_return=top_quantile_mean,
        bottom_quantile_mean_return=bottom_quantile_mean,
        top_bottom_spread=(
            None
            if top_quantile_mean is None or bottom_quantile_mean is None
            else top_quantile_mean - bottom_quantile_mean
        ),
        excess_top_n_mean_return=(
            None if top_n_mean is None or universe_mean is None else top_n_mean - universe_mean
        ),
        excess_top_quantile_mean_return=(
            None
            if top_quantile_mean is None or universe_mean is None
            else top_quantile_mean - universe_mean
        ),
    )


def compute_risk_metrics(
    *,
    samples_by_horizon: dict[int, list[LLMFactorEvaluationSample]],
    config: LLMFactorValidationConfig,
    factor_getters: tuple[_FactorDefinition, ...],
    segment_filter: tuple[str, str] | None = None,
) -> tuple[list[LLMFactorRiskMetrics], list[LLMFactorBacktestWarning]]:
    metrics: list[LLMFactorRiskMetrics] = []
    warnings: list[LLMFactorBacktestWarning] = []
    for factor_name, score_getter in factor_getters:
        for horizon in sorted(samples_by_horizon):
            samples = _filter_samples_by_segment(samples_by_horizon[horizon], segment_filter)
            factor_metrics, factor_warnings = risk_metrics_for_samples(
                samples=samples,
                factor_name=factor_name,
                score_getter=score_getter,
                horizon_days=horizon,
                config=config,
                segment=_segment_label(segment_filter),
            )
            metrics.append(factor_metrics)
            warnings.extend(factor_warnings)
    return metrics, warnings


def risk_metrics_for_samples(
    *,
    samples: list[LLMFactorEvaluationSample],
    factor_name: str,
    score_getter: _FactorGetter,
    horizon_days: int,
    config: LLMFactorValidationConfig,
    segment: str | None = None,
) -> tuple[LLMFactorRiskMetrics, list[LLMFactorBacktestWarning]]:
    scored_samples = _scored_samples(samples, score_getter)
    grouped = _group_by_signal_date(scored_samples)
    daily_top_returns: list[float] = []
    daily_high_drawdowns: list[float] = []
    daily_worst_drawdowns: list[float] = []
    daily_downside_hit_rates: list[float] = []
    for signal_date in sorted(grouped):
        day_samples = grouped[signal_date]
        sorted_samples = sorted(day_samples, key=lambda row: (-row.factor_score, row.symbol))
        top_samples = sorted_samples[: min(config.top_n, len(sorted_samples))]
        high_samples = sorted_samples[
            : _top_quantile_count(len(sorted_samples), config.top_quantile)
        ]
        daily_top_returns.append(_required_mean(row.forward_return for row in top_samples))
        daily_high_drawdowns.append(_required_mean(row.drawdown for row in high_samples))
        daily_worst_drawdowns.append(min(row.drawdown for row in high_samples))
        daily_downside_hit_rates.append(
            _required_mean(
                1.0 if row.drawdown <= -config.drawdown_threshold else 0.0 for row in high_samples
            )
        )
    volatility = _sample_stdev_or_none(daily_top_returns)
    period_sharpe = (
        None
        if volatility is None or volatility == 0
        else (_required_mean(row - config.risk_free_rate_per_period for row in daily_top_returns))
        / volatility
    )
    warnings = _risk_warnings(
        factor_name=factor_name,
        horizon_days=horizon_days,
        return_count=len(daily_top_returns),
        volatility=volatility,
        config=config,
    )
    annualized_sharpe = None
    if period_sharpe is not None and horizon_days == 1:
        annualized_sharpe = period_sharpe * math.sqrt(config.annualization_periods_per_year)
    return (
        LLMFactorRiskMetrics(
            factor_name=factor_name,
            horizon_days=horizon_days,
            segment=segment,
            sample_count=len(scored_samples),
            date_count=len(grouped),
            top_n_period_sharpe=period_sharpe,
            top_n_annualized_sharpe=annualized_sharpe,
            top_n_max_drawdown=_max_drawdown(daily_top_returns),
            top_n_volatility=volatility,
            high_score_avg_drawdown=_mean_or_none(daily_high_drawdowns),
            high_score_worst_drawdown=min(daily_worst_drawdowns) if daily_worst_drawdowns else None,
            downside_hit_rate=_mean_or_none(daily_downside_hit_rates),
        ),
        warnings,
    )


def compute_baseline_comparison_metrics(
    *,
    samples_by_horizon: dict[int, list[LLMFactorEvaluationSample]],
    baseline_scores: Iterable[LLMFactorBaselineScore],
    config: LLMFactorValidationConfig,
    factor_getters: tuple[_FactorDefinition, ...],
    segment_filter: tuple[str, str] | None = None,
) -> tuple[list[LLMFactorBaselineComparisonMetrics], list[LLMFactorBacktestWarning]]:
    baseline_lookup = _baseline_lookup(baseline_scores)
    warnings: list[LLMFactorBacktestWarning] = []
    if not baseline_lookup:
        return [], [
            LLMFactorBacktestWarning(
                code="BASELINE_SCORE_MISSING",
                message="baseline_scores がないため、既存モデルとの差分 metrics は skip しました。",
                severity="info",
            )
        ]
    metrics: list[LLMFactorBaselineComparisonMetrics] = []
    for baseline_name in BASELINE_NAMES:
        if not any(key[2] == baseline_name for key in baseline_lookup):
            warnings.append(
                LLMFactorBacktestWarning(
                    code="BASELINE_SCORE_MISSING",
                    message=f"{baseline_name} の baseline score がないため比較を skip しました。",
                    severity="info",
                )
            )
            continue
        for factor_name, score_getter in factor_getters:
            task = PREDICTION_TASK_BY_FACTOR.get(factor_name)
            if task is None:
                continue
            if task == "absolute_move" and not config.include_absolute_move_task:
                continue
            for horizon in sorted(samples_by_horizon):
                samples = _filter_samples_by_segment(samples_by_horizon[horizon], segment_filter)
                factor_samples = [
                    sample
                    for sample in samples
                    if baseline_lookup.get(
                        (_symbol_key(sample.symbol), sample.signal_date, baseline_name)
                    )
                    is not None
                ]
                if not factor_samples:
                    continue
                baseline_getter = _baseline_getter(baseline_lookup, baseline_name)
                factor_classification, _ = classification_metrics_for_samples(
                    samples=factor_samples,
                    factor_name=factor_name,
                    score_getter=score_getter,
                    prediction_task=task,
                    config=config,
                )
                baseline_classification, _ = classification_metrics_for_samples(
                    samples=factor_samples,
                    factor_name=baseline_name,
                    score_getter=baseline_getter,
                    prediction_task=task,
                    config=config,
                )
                factor_return = return_metrics_for_samples(
                    samples=factor_samples,
                    factor_name=factor_name,
                    score_getter=score_getter,
                    horizon_days=horizon,
                    signal_count=len(factor_samples),
                    top_n=config.top_n,
                    top_quantile=config.top_quantile,
                    segment=_segment_label(segment_filter),
                )
                baseline_return = return_metrics_for_samples(
                    samples=factor_samples,
                    factor_name=baseline_name,
                    score_getter=baseline_getter,
                    horizon_days=horizon,
                    signal_count=len(factor_samples),
                    top_n=config.top_n,
                    top_quantile=config.top_quantile,
                    segment=_segment_label(segment_filter),
                )
                factor_risk, _ = risk_metrics_for_samples(
                    samples=factor_samples,
                    factor_name=factor_name,
                    score_getter=score_getter,
                    horizon_days=horizon,
                    config=config,
                    segment=_segment_label(segment_filter),
                )
                baseline_risk, _ = risk_metrics_for_samples(
                    samples=factor_samples,
                    factor_name=baseline_name,
                    score_getter=baseline_getter,
                    horizon_days=horizon,
                    config=config,
                    segment=_segment_label(segment_filter),
                )
                metrics.append(
                    LLMFactorBaselineComparisonMetrics(
                        factor_name=factor_name,
                        baseline_name=baseline_name,
                        horizon_days=horizon,
                        prediction_task=task,
                        segment=_segment_label(segment_filter),
                        sample_count=len(factor_samples),
                        delta_accuracy=_delta(
                            factor_classification.accuracy,
                            baseline_classification.accuracy,
                        ),
                        delta_precision=_delta(
                            factor_classification.precision,
                            baseline_classification.precision,
                        ),
                        delta_recall=_delta(
                            factor_classification.recall,
                            baseline_classification.recall,
                        ),
                        delta_f1=_delta(factor_classification.f1, baseline_classification.f1),
                        delta_auc=_delta(factor_classification.auc, baseline_classification.auc),
                        delta_top_n_mean_return=_delta(
                            factor_return.top_n_mean_return,
                            baseline_return.top_n_mean_return,
                        ),
                        delta_top_quantile_mean_return=_delta(
                            factor_return.top_quantile_mean_return,
                            baseline_return.top_quantile_mean_return,
                        ),
                        delta_top_bottom_spread=_delta(
                            factor_return.top_bottom_spread,
                            baseline_return.top_bottom_spread,
                        ),
                        delta_period_sharpe=_delta(
                            factor_risk.top_n_period_sharpe,
                            baseline_risk.top_n_period_sharpe,
                        ),
                        delta_max_drawdown=_delta(
                            factor_risk.top_n_max_drawdown,
                            baseline_risk.top_n_max_drawdown,
                        ),
                    )
                )
    return metrics, warnings


def compute_segment_metrics(
    *,
    samples_by_horizon: dict[int, list[LLMFactorEvaluationSample]],
    baseline_scores: Iterable[LLMFactorBaselineScore],
    config: LLMFactorValidationConfig,
    factor_getters: tuple[_FactorDefinition, ...],
) -> tuple[list[LLMFactorSegmentMetrics], list[LLMFactorBacktestWarning]]:
    segment_values = _segment_values(samples_by_horizon)
    metrics: list[LLMFactorSegmentMetrics] = []
    warnings: list[LLMFactorBacktestWarning] = []
    for segment_name, values in segment_values.items():
        for segment_value in sorted(values):
            segment_filter = (segment_name, segment_value)
            filtered_by_horizon = {
                horizon: _filter_samples_by_segment(samples, segment_filter)
                for horizon, samples in samples_by_horizon.items()
            }
            segment_signal_count = len(
                {
                    (_symbol_key(sample.symbol), sample.signal_date)
                    for samples in filtered_by_horizon.values()
                    for sample in samples
                }
            )
            returns = {
                (metric.factor_name, metric.horizon_days): metric
                for metric in compute_return_metrics(
                    samples_by_horizon=filtered_by_horizon,
                    signal_count=max(segment_signal_count, 1),
                    config=config,
                    factor_getters=factor_getters,
                    segment_filter=None,
                )
            }
            risks, risk_warnings = compute_risk_metrics(
                samples_by_horizon=filtered_by_horizon,
                config=config,
                factor_getters=factor_getters,
                segment_filter=None,
            )
            risk_lookup = {(metric.factor_name, metric.horizon_days): metric for metric in risks}
            warnings.extend(risk_warnings)
            comparisons, comparison_warnings = compute_baseline_comparison_metrics(
                samples_by_horizon=filtered_by_horizon,
                baseline_scores=baseline_scores,
                config=config,
                factor_getters=factor_getters,
                segment_filter=None,
            )
            warnings.extend(comparison_warnings)
            comparison_lookup = {
                (metric.factor_name, metric.horizon_days): metric
                for metric in comparisons
                if metric.baseline_name == "ranking_score"
            }
            for factor_name, score_getter in factor_getters:
                task = PREDICTION_TASK_BY_FACTOR.get(factor_name)
                if task is None or (
                    task == "absolute_move" and not config.include_absolute_move_task
                ):
                    continue
                for horizon in sorted(filtered_by_horizon):
                    samples = filtered_by_horizon[horizon]
                    if len(samples) < config.min_segment_samples:
                        warnings.append(
                            LLMFactorBacktestWarning(
                                code="SEGMENT_TOO_SMALL",
                                message=(
                                    f"{segment_name}={segment_value} の sample_count={len(samples)} が"
                                    f" min_segment_samples={config.min_segment_samples} を下回ります。"
                                ),
                                factor_name=factor_name,
                                horizon_days=horizon,
                                severity="warning",
                            )
                        )
                    classification, _ = classification_metrics_for_samples(
                        samples=samples,
                        factor_name=factor_name,
                        score_getter=score_getter,
                        prediction_task=task,
                        config=config,
                    )
                    return_metric = returns.get((factor_name, horizon))
                    risk_metric = risk_lookup.get((factor_name, horizon))
                    comparison_metric = comparison_lookup.get((factor_name, horizon))
                    metrics.append(
                        LLMFactorSegmentMetrics(
                            segment_name=segment_name,
                            segment_value=segment_value,
                            factor_name=factor_name,
                            horizon_days=horizon,
                            sample_count=len(samples),
                            classification_auc=classification.auc,
                            classification_f1=classification.f1,
                            top_n_mean_return=(
                                return_metric.top_n_mean_return if return_metric else None
                            ),
                            top_bottom_spread=(
                                return_metric.top_bottom_spread if return_metric else None
                            ),
                            period_sharpe=(
                                risk_metric.top_n_period_sharpe if risk_metric else None
                            ),
                            max_drawdown=(risk_metric.top_n_max_drawdown if risk_metric else None),
                            baseline_delta_auc=(
                                comparison_metric.delta_auc if comparison_metric else None
                            ),
                        )
                    )
    return metrics, warnings


def low_evidence_coverage_warning(
    signals: Iterable[LLMFactorBacktestSignal],
    config: LLMFactorValidationConfig,
) -> LLMFactorBacktestWarning | None:
    signal_list = list(signals)
    if not signal_list:
        return None
    low_count = 0
    for signal in signal_list:
        if (
            signal.source_count <= config.low_evidence_source_count
            or signal.confidence_score < config.low_evidence_score_threshold
            or signal.evidence_quality_score < config.low_evidence_score_threshold
            or signal.freshness_score < config.low_evidence_score_threshold
        ):
            low_count += 1
    ratio = low_count / len(signal_list)
    if ratio < config.low_evidence_ratio_threshold:
        return None
    return LLMFactorBacktestWarning(
        code="LOW_EVIDENCE_COVERAGE",
        message=(
            f"source_count / confidence / evidence_quality / freshness が弱い signal 比率が "
            f"{ratio:.3f} です。低ニュース銘柄では LLM材料スコアを過信しないでください。"
        ),
        severity="warning",
    )


def _classification_warnings(
    *,
    factor_name: str,
    horizon_days: int | None,
    prediction_task: LLMFactorPredictionTask,
    positive_rate: float | None,
    auc: float | None,
    config: LLMFactorValidationConfig,
) -> list[LLMFactorBacktestWarning]:
    warnings: list[LLMFactorBacktestWarning] = []
    if auc is None:
        warnings.append(
            LLMFactorBacktestWarning(
                code="AUC_UNDEFINED_SINGLE_CLASS",
                message=(f"{prediction_task} label が片側 class のため AUC を計算できません。"),
                factor_name=factor_name,
                horizon_days=horizon_days,
                severity="warning",
            )
        )
    if (
        positive_rate is not None
        and (positive_rate < config.class_imbalance_low_threshold)
        or (positive_rate is not None and positive_rate > config.class_imbalance_high_threshold)
    ):
        warnings.append(
            LLMFactorBacktestWarning(
                code="CLASS_IMBALANCE",
                message=f"{prediction_task} label の positive_rate={positive_rate:.3f} が偏っています。",
                factor_name=factor_name,
                horizon_days=horizon_days,
                severity="warning",
            )
        )
    return warnings


def _risk_warnings(
    *,
    factor_name: str,
    horizon_days: int,
    return_count: int,
    volatility: float | None,
    config: LLMFactorValidationConfig,
) -> list[LLMFactorBacktestWarning]:
    warnings: list[LLMFactorBacktestWarning] = []
    if horizon_days > 1:
        warnings.append(
            LLMFactorBacktestWarning(
                code="OVERLAPPING_HORIZON_RETURNS",
                message=(
                    f"horizon={horizon_days} の forward return series は重複期間を含む可能性があるため、"
                    "annualized Sharpe は出さず period Sharpe を主指標にします。"
                ),
                factor_name=factor_name,
                horizon_days=horizon_days,
                severity="info",
            )
        )
    if return_count < config.min_dates:
        warnings.append(
            LLMFactorBacktestWarning(
                code="SHARPE_ON_SMALL_SAMPLE",
                message=(
                    f"date-level return series={return_count} が min_dates={config.min_dates} を"
                    "下回るため Sharpe は参考値です。"
                ),
                factor_name=factor_name,
                horizon_days=horizon_days,
                severity="warning",
            )
        )
    if return_count >= 2 and volatility == 0:
        warnings.append(
            LLMFactorBacktestWarning(
                code="SHARPE_ZERO_VOLATILITY",
                message="date-level return volatility が 0 のため Sharpe を計算しません。",
                factor_name=factor_name,
                horizon_days=horizon_days,
                severity="warning",
            )
        )
    return warnings


def _label_for_task(
    sample: _ScoredEvaluationSample,
    task: LLMFactorPredictionTask,
    config: LLMFactorValidationConfig,
) -> bool:
    if task == "up":
        return sample.forward_return > config.return_threshold
    if task == "down":
        return sample.forward_return < -config.return_threshold
    if task == "drawdown":
        return sample.drawdown <= -config.drawdown_threshold
    return abs(sample.forward_return) > config.absolute_move_threshold


def _binary_predictions(
    samples: list[_ScoredEvaluationSample],
    *,
    threshold_policy: LLMFactorThresholdPolicy,
    score_threshold: float | None,
    quantile: float,
) -> list[bool]:
    if threshold_policy == "fixed_score_threshold":
        threshold = 50.0 if score_threshold is None else score_threshold
        return [sample.factor_score >= threshold for sample in samples]
    predictions_by_key: set[tuple[str, date, float]] = set()
    grouped = _group_by_signal_date(samples)
    for signal_date, day_samples in grouped.items():
        sorted_samples = sorted(day_samples, key=lambda row: (-row.factor_score, row.symbol))
        for sample in sorted_samples[: _top_quantile_count(len(sorted_samples), quantile)]:
            predictions_by_key.add((sample.symbol, signal_date, sample.factor_score))
    return [
        (sample.symbol, sample.signal_date, sample.factor_score) in predictions_by_key
        for sample in samples
    ]


def _auc(labels: list[bool], scores: list[float]) -> float | None:
    positive_count = sum(1 for label in labels if label)
    negative_count = len(labels) - positive_count
    if positive_count == 0 or negative_count == 0:
        return None
    ranked = sorted(enumerate(scores), key=lambda item: item[1])
    ranks = [0.0] * len(scores)
    rank = 1
    index = 0
    while index < len(ranked):
        tie_end = index
        while tie_end + 1 < len(ranked) and ranked[tie_end + 1][1] == ranked[index][1]:
            tie_end += 1
        average_rank = (rank + rank + (tie_end - index)) / 2
        for tie_index in range(index, tie_end + 1):
            ranks[ranked[tie_index][0]] = average_rank
        rank += tie_end - index + 1
        index = tie_end + 1
    positive_rank_sum = sum(rank for rank, label in zip(ranks, labels, strict=True) if label)
    return (positive_rank_sum - positive_count * (positive_count + 1) / 2) / (
        positive_count * negative_count
    )


def _average_precision(labels: list[bool], scores: list[float]) -> float | None:
    positive_count = sum(1 for label in labels if label)
    if positive_count == 0:
        return None
    sorted_pairs = sorted(zip(scores, labels, strict=True), key=lambda item: item[0], reverse=True)
    hits = 0
    precision_sum = 0.0
    for index, (_, label) in enumerate(sorted_pairs, start=1):
        if label:
            hits += 1
            precision_sum += hits / index
    return precision_sum / positive_count


def _scored_samples(
    samples: list[LLMFactorEvaluationSample],
    score_getter: _FactorGetter,
) -> list[_ScoredEvaluationSample]:
    return [
        _ScoredEvaluationSample(
            symbol=sample.symbol,
            signal_date=sample.signal_date,
            factor_score=score_getter(sample.signal),
            forward_return=sample.forward_return,
            drawdown=sample.drawdown,
            segments=sample.segments,
        )
        for sample in samples
    ]


def _filter_samples_by_segment(
    samples: list[LLMFactorEvaluationSample],
    segment_filter: tuple[str, str] | None,
) -> list[LLMFactorEvaluationSample]:
    if segment_filter is None:
        return samples
    name, value = segment_filter
    return [sample for sample in samples if sample.segments.get(name) == value]


def _segment_values(
    samples_by_horizon: dict[int, list[LLMFactorEvaluationSample]],
) -> dict[str, set[str]]:
    values: dict[str, set[str]] = defaultdict(set)
    for samples in samples_by_horizon.values():
        for sample in samples:
            for segment_name, segment_value in sample.segments.items():
                values[segment_name].add(segment_value)
    return dict(sorted(values.items()))


def _segment_label(segment_filter: tuple[str, str] | None) -> str | None:
    if segment_filter is None:
        return None
    return f"{segment_filter[0]}={segment_filter[1]}"


def _baseline_lookup(
    baseline_scores: Iterable[LLMFactorBaselineScore],
) -> dict[tuple[str, date, str], float]:
    lookup: dict[tuple[str, date, str], float] = {}
    for score in baseline_scores:
        if score.score is None:
            continue
        lookup[(_symbol_key(score.symbol), score.signal_date, score.baseline_name)] = score.score
    return lookup


def _baseline_getter(
    baseline_lookup: dict[tuple[str, date, str], float],
    baseline_name: str,
) -> _FactorGetter:
    def getter(signal: LLMFactorBacktestSignal) -> float:
        return baseline_lookup[(_symbol_key(signal.symbol), signal.signal_date, baseline_name)]

    return getter


def _price_index(prices: Iterable[LLMFactorPriceBar]) -> dict[str, list[LLMFactorPriceBar]]:
    grouped: dict[str, dict[date, LLMFactorPriceBar]] = defaultdict(dict)
    for price in sorted(prices, key=lambda row: (_symbol_key(row.symbol), row.date)):
        grouped[_symbol_key(price.symbol)].setdefault(price.date, price)
    return {
        symbol: [by_date[price_date] for price_date in sorted(by_date)]
        for symbol, by_date in sorted(grouped.items())
    }


def _first_price_index_on_or_after(
    prices: list[LLMFactorPriceBar],
    signal_date: date,
) -> int | None:
    for index, price in enumerate(prices):
        if price.date >= signal_date:
            return index
    return None


def _price_value(price: LLMFactorPriceBar) -> float:
    return price.adjusted_close if price.adjusted_close is not None else price.close


def _group_by_signal_date(
    samples: Iterable[_ScoredEvaluationSample],
) -> dict[date, list[_ScoredEvaluationSample]]:
    grouped: dict[date, list[_ScoredEvaluationSample]] = defaultdict(list)
    for sample in samples:
        grouped[sample.signal_date].append(sample)
    return dict(grouped)


def _top_quantile_count(sample_count: int, quantile: float) -> int:
    if sample_count <= 0:
        return 0
    if quantile <= 0:
        return sample_count
    return max(1, math.ceil((1 - quantile) * sample_count))


def _mean_or_none(values: Iterable[float]) -> float | None:
    value_list = list(values)
    if not value_list:
        return None
    return sum(value_list) / len(value_list)


def _required_mean(values: Iterable[float]) -> float:
    value_list = list(values)
    if not value_list:
        raise ValueError("Cannot average an empty collection")
    return sum(value_list) / len(value_list)


def _sample_stdev_or_none(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    return stdev(values)


def _max_drawdown(returns: list[float]) -> float | None:
    if not returns:
        return None
    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0
    for period_return in returns:
        equity *= 1 + period_return
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity / peak - 1)
    return max_drawdown


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def _delta(value: float | None, baseline: float | None) -> float | None:
    if value is None or baseline is None:
        return None
    return value - baseline


def _sign(value: float) -> float:
    if value > 0:
        return 1.0
    if value < 0:
        return -1.0
    return 0.0


def _symbol_key(symbol: str) -> str:
    return symbol.strip().upper()
