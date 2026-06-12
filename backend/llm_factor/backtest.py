from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date

from backend.llm_factor.backtest_contracts import (
    LLMFactorBacktestCase,
    LLMFactorBacktestMetrics,
    LLMFactorBacktestResult,
    LLMFactorBacktestSignal,
    LLMFactorBacktestWarning,
    LLMFactorPriceBar,
)

LOW_COVERAGE_WARNING_THRESHOLD = 0.8
MULTIPLE_TESTING_WARNING_THRESHOLD = 20


@dataclass(frozen=True)
class _ForwardSample:
    symbol: str
    signal_date: date
    signal: LLMFactorBacktestSignal
    forward_return: float
    drawdown: float


@dataclass(frozen=True)
class _ScoredSample:
    symbol: str
    signal_date: date
    factor_score: float
    forward_return: float
    drawdown: float


_FactorDefinition = tuple[str, Callable[[LLMFactorBacktestSignal], float]]

FACTOR_DEFINITIONS: tuple[_FactorDefinition, ...] = (
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


def run_llm_factor_backtest(case: LLMFactorBacktestCase) -> LLMFactorBacktestResult:
    """Evaluate source-bound LLM material factors against future returns and drawdowns."""

    horizons = _canonical_horizons(case.horizons)
    signals, duplicate_count = _canonical_unique_signals(case.signals)
    prices = _price_index(case.prices)
    warnings: list[LLMFactorBacktestWarning] = []
    if duplicate_count:
        warnings.append(
            LLMFactorBacktestWarning(
                code="DUPLICATE_SIGNAL",
                message=(
                    f"同一 symbol + signal_date の signal が {duplicate_count} 件重複したため、"
                    "canonical sort 後の最初の signal だけを評価しました。"
                ),
                factor_name=None,
                horizon_days=None,
                severity="warning",
            )
        )
    if case.entry_lag_bars <= 0:
        warnings.append(
            LLMFactorBacktestWarning(
                code="LOOKAHEAD_RISK",
                message=(
                    "entry_lag_bars が 0 のため、signal_date 当日の価格を entry に使う"
                    "look-ahead risk があります。"
                ),
                factor_name=None,
                horizon_days=None,
                severity="warning",
            )
        )
    if len(FACTOR_DEFINITIONS) * len(horizons) >= MULTIPLE_TESTING_WARNING_THRESHOLD:
        warnings.append(
            LLMFactorBacktestWarning(
                code="MULTIPLE_TESTING_RISK",
                message=(
                    "多数の factor / horizon を探索的に評価しています。"
                    "この結果を Ranking weight に直接使わず、別期間で検証してください。"
                ),
                factor_name=None,
                horizon_days=None,
                severity="info",
            )
        )

    forward_samples_by_horizon: dict[int, list[_ForwardSample]] = {}
    missing_by_horizon: dict[int, int] = {}
    for horizon in horizons:
        samples, missing_count = _forward_samples_for_horizon(
            signals=signals,
            prices=prices,
            horizon_days=horizon,
            entry_lag_bars=case.entry_lag_bars,
        )
        forward_samples_by_horizon[horizon] = samples
        missing_by_horizon[horizon] = missing_count
        if missing_count:
            warnings.append(
                LLMFactorBacktestWarning(
                    code="MISSING_PRICE",
                    message=(
                        f"horizon={horizon} で entry / exit / drawdown window の価格が足りない"
                        f" signal を {missing_count} 件除外しました。"
                    ),
                    factor_name=None,
                    horizon_days=horizon,
                    severity="warning",
                )
            )

    metrics: list[LLMFactorBacktestMetrics] = []
    for factor_name, score_getter in FACTOR_DEFINITIONS:
        for horizon in horizons:
            factor_metrics = _metrics_for_factor(
                factor_name=factor_name,
                horizon_days=horizon,
                forward_samples=forward_samples_by_horizon[horizon],
                score_getter=score_getter,
                signal_count=len(signals),
                top_n=case.top_n,
                high_score_quantile=case.high_score_quantile,
            )
            metrics.append(factor_metrics)
            warnings.extend(
                _metric_warnings(
                    metrics=factor_metrics,
                    min_samples=case.min_samples,
                    min_dates=case.min_dates,
                )
            )

    return LLMFactorBacktestResult(
        case_id=case.case_id,
        metrics=metrics,
        warnings=warnings,
        input_hash=_input_hash(case),
        config_hash=_config_hash(case, horizons=horizons),
    )


def _forward_samples_for_horizon(
    *,
    signals: list[LLMFactorBacktestSignal],
    prices: dict[str, list[LLMFactorPriceBar]],
    horizon_days: int,
    entry_lag_bars: int,
) -> tuple[list[_ForwardSample], int]:
    samples: list[_ForwardSample] = []
    missing_count = 0
    for signal in signals:
        symbol_key = _symbol_key(signal.symbol)
        symbol_prices = prices.get(symbol_key, [])
        base_index = _first_price_index_on_or_after(symbol_prices, signal.signal_date)
        if base_index is None:
            missing_count += 1
            continue
        entry_index = base_index + entry_lag_bars
        exit_index = entry_index + horizon_days
        if entry_index < 0 or exit_index >= len(symbol_prices):
            missing_count += 1
            continue
        window = symbol_prices[entry_index : exit_index + 1]
        if len(window) != horizon_days + 1:
            missing_count += 1
            continue
        entry_price = _price_value(window[0])
        exit_price = _price_value(window[-1])
        if entry_price <= 0 or exit_price <= 0:
            missing_count += 1
            continue
        window_drawdown = min((_price_value(bar) / entry_price) - 1 for bar in window)
        samples.append(
            _ForwardSample(
                symbol=signal.symbol,
                signal_date=signal.signal_date,
                signal=signal,
                forward_return=(exit_price / entry_price) - 1,
                drawdown=window_drawdown,
            )
        )
    return samples, missing_count


def _metrics_for_factor(
    *,
    factor_name: str,
    horizon_days: int,
    forward_samples: Iterable[_ForwardSample],
    score_getter: Callable[[LLMFactorBacktestSignal], float],
    signal_count: int,
    top_n: int,
    high_score_quantile: float,
) -> LLMFactorBacktestMetrics:
    samples = [
        _ScoredSample(
            symbol=sample.symbol,
            signal_date=sample.signal_date,
            factor_score=score_getter(sample.signal),
            forward_return=sample.forward_return,
            drawdown=sample.drawdown,
        )
        for sample in forward_samples
    ]
    grouped = _group_by_signal_date(samples)
    daily_universe_returns: list[float] = []
    daily_universe_drawdowns: list[float] = []
    daily_top_returns: list[float] = []
    daily_high_returns: list[float] = []
    daily_high_hit_rates: list[float] = []
    daily_high_down_rates: list[float] = []
    daily_high_drawdowns: list[float] = []
    top_n_count = 0
    high_score_count = 0
    for signal_date in sorted(grouped):
        day_samples = grouped[signal_date]
        sorted_samples = sorted(day_samples, key=lambda row: (-row.factor_score, row.symbol))
        top_samples = sorted_samples[: min(top_n, len(sorted_samples))]
        high_samples = sorted_samples[: _high_score_count(len(sorted_samples), high_score_quantile)]
        top_n_count += len(top_samples)
        high_score_count += len(high_samples)
        daily_universe_returns.append(_required_mean(row.forward_return for row in day_samples))
        daily_universe_drawdowns.append(_required_mean(row.drawdown for row in day_samples))
        daily_top_returns.append(_required_mean(row.forward_return for row in top_samples))
        daily_high_returns.append(_required_mean(row.forward_return for row in high_samples))
        daily_high_hit_rates.append(
            _required_mean(1.0 if row.forward_return > 0 else 0.0 for row in high_samples)
        )
        daily_high_down_rates.append(
            _required_mean(1.0 if row.forward_return < 0 else 0.0 for row in high_samples)
        )
        daily_high_drawdowns.append(_required_mean(row.drawdown for row in high_samples))

    sample_count = len(samples)
    universe_mean_return = _mean_or_none(daily_universe_returns)
    top_n_mean_return = _mean_or_none(daily_top_returns)
    coverage_ratio = sample_count / signal_count if signal_count else 0.0
    unique_scores = {sample.factor_score for sample in samples}
    zero_variance_factor = bool(samples) and len(unique_scores) <= 1
    return LLMFactorBacktestMetrics(
        factor_name=factor_name,
        horizon_days=horizon_days,
        sample_count=sample_count,
        date_count=len(grouped),
        coverage_ratio=coverage_ratio,
        top_n_mean_return=top_n_mean_return,
        high_score_mean_return=_mean_or_none(daily_high_returns),
        high_score_hit_rate=_mean_or_none(daily_high_hit_rates),
        high_score_down_rate=_mean_or_none(daily_high_down_rates),
        high_score_avg_drawdown=_mean_or_none(daily_high_drawdowns),
        universe_mean_return=universe_mean_return,
        universe_avg_drawdown=_mean_or_none(daily_universe_drawdowns),
        excess_top_n_mean_return=(
            None
            if top_n_mean_return is None or universe_mean_return is None
            else top_n_mean_return - universe_mean_return
        ),
        high_score_count=high_score_count,
        top_n_count=top_n_count,
        zero_variance_factor=zero_variance_factor,
    )


def _metric_warnings(
    *,
    metrics: LLMFactorBacktestMetrics,
    min_samples: int,
    min_dates: int,
) -> list[LLMFactorBacktestWarning]:
    warnings: list[LLMFactorBacktestWarning] = []
    if metrics.sample_count < min_samples:
        warnings.append(
            LLMFactorBacktestWarning(
                code="INSUFFICIENT_SAMPLES",
                message=(
                    f"sample_count={metrics.sample_count} が min_samples={min_samples} を"
                    "下回るため、探索的な参考評価に留めてください。"
                ),
                factor_name=metrics.factor_name,
                horizon_days=metrics.horizon_days,
                severity="warning",
            )
        )
    if metrics.date_count < min_dates:
        warnings.append(
            LLMFactorBacktestWarning(
                code="INSUFFICIENT_DATES",
                message=(
                    f"date_count={metrics.date_count} が min_dates={min_dates} を下回ります。"
                    "単一日付に偏った評価として扱ってください。"
                ),
                factor_name=metrics.factor_name,
                horizon_days=metrics.horizon_days,
                severity="warning",
            )
        )
    if metrics.zero_variance_factor:
        warnings.append(
            LLMFactorBacktestWarning(
                code="ZERO_VARIANCE_FACTOR",
                message="評価可能 sample 内で factor score がすべて同一です。",
                factor_name=metrics.factor_name,
                horizon_days=metrics.horizon_days,
                severity="warning",
            )
        )
    if metrics.coverage_ratio < LOW_COVERAGE_WARNING_THRESHOLD:
        warnings.append(
            LLMFactorBacktestWarning(
                code="LOW_COVERAGE",
                message=(
                    f"coverage_ratio={metrics.coverage_ratio:.3f} が "
                    f"{LOW_COVERAGE_WARNING_THRESHOLD:.1f} を下回ります。"
                ),
                factor_name=metrics.factor_name,
                horizon_days=metrics.horizon_days,
                severity="warning",
            )
        )
    return warnings


def _canonical_unique_signals(
    signals: Iterable[LLMFactorBacktestSignal],
) -> tuple[list[LLMFactorBacktestSignal], int]:
    unique: dict[tuple[str, date], LLMFactorBacktestSignal] = {}
    duplicate_count = 0
    for signal in sorted(signals, key=_signal_sort_key):
        key = (_symbol_key(signal.symbol), signal.signal_date)
        if key in unique:
            duplicate_count += 1
            continue
        unique[key] = signal
    return list(unique.values()), duplicate_count


def _price_index(prices: Iterable[LLMFactorPriceBar]) -> dict[str, list[LLMFactorPriceBar]]:
    grouped: dict[str, dict[date, LLMFactorPriceBar]] = defaultdict(dict)
    for price in sorted(prices, key=lambda row: (_symbol_key(row.symbol), row.date)):
        grouped[_symbol_key(price.symbol)].setdefault(price.date, price)
    return {
        symbol: [by_date[price_date] for price_date in sorted(by_date)]
        for symbol, by_date in sorted(grouped.items())
    }


def _canonical_horizons(horizons: Iterable[int]) -> list[int]:
    normalized = sorted({horizon for horizon in horizons if horizon > 0})
    return normalized or [1]


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


def _group_by_signal_date(samples: Iterable[_ScoredSample]) -> dict[date, list[_ScoredSample]]:
    grouped: dict[date, list[_ScoredSample]] = defaultdict(list)
    for sample in samples:
        grouped[sample.signal_date].append(sample)
    return dict(grouped)


def _high_score_count(sample_count: int, quantile: float) -> int:
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


def _input_hash(case: LLMFactorBacktestCase) -> str:
    payload = {
        "signals": [
            signal.model_dump(mode="json") for signal in sorted(case.signals, key=_signal_sort_key)
        ],
        "prices": [
            price.model_dump(mode="json")
            for price in sorted(case.prices, key=lambda row: (_symbol_key(row.symbol), row.date))
        ],
    }
    return _sha256_json(payload)


def _config_hash(case: LLMFactorBacktestCase, *, horizons: list[int]) -> str:
    payload = {
        "horizons": horizons,
        "top_n": case.top_n,
        "high_score_quantile": case.high_score_quantile,
        "min_samples": case.min_samples,
        "min_dates": case.min_dates,
        "entry_lag_bars": case.entry_lag_bars,
        "quality_gate": case.quality_gate,
    }
    return _sha256_json(payload)


def _sha256_json(payload: object) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _signal_sort_key(signal: LLMFactorBacktestSignal) -> tuple[date, str, str, str]:
    return (
        signal.signal_date,
        _symbol_key(signal.symbol),
        signal.available_at.isoformat() if signal.available_at else "",
        signal.llm_factor_result_id or "",
    )


def _symbol_key(symbol: str) -> str:
    return symbol.strip().upper()
