from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import ConfigDict, Field

from backend.core.data_contracts import StrictBaseModel
from backend.llm_factor.backtest_contracts import (
    LLMFactorBacktestSignal,
    LLMFactorBacktestWarning,
    LLMFactorPriceBar,
)

LLM_FACTOR_VALIDATION_REPORT_SCHEMA_VERSION = "llm-factor-validation-report-v1"

LLMFactorPredictionTask = Literal["up", "down", "drawdown", "absolute_move"]
LLMFactorThresholdPolicy = Literal["fixed_score_threshold", "top_quantile_by_date"]
LLMFactorRecommendationStatus = Literal[
    "evidence_insufficient",
    "reference_display_only",
    "candidate_for_optional_integration_later",
]


class LLMFactorBaselineScore(StrictBaseModel):
    """Fixture-only baseline score used to compare LLM factors with existing model surfaces."""

    symbol: str = Field(min_length=1)
    signal_date: date
    baseline_name: str = Field(min_length=1)
    score: float | None = Field(default=None, allow_inf_nan=False)


class LLMFactorFixtureManifest(StrictBaseModel):
    """Deterministic fixture manifest for broader LLM Factor validation."""

    fixture_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    generated_by: str = Field(min_length=1)
    is_synthetic_or_static: bool
    data_policy: str = Field(min_length=1)
    markets: list[str]
    segments: list[str]
    symbol_count: int = Field(ge=0)
    signal_count: int = Field(ge=0)
    price_bar_count: int = Field(ge=0)
    start_date: date
    end_date: date
    fixture_hash: str = Field(min_length=1)


class LLMFactorHistoricalFixturePack(StrictBaseModel):
    """Synthetic/static fixture pack for deterministic LLM Factor validation."""

    fixture_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    description: str = Field(min_length=1)
    signals: list[LLMFactorBacktestSignal]
    prices: list[LLMFactorPriceBar]
    baseline_scores: list[LLMFactorBaselineScore] = Field(default_factory=list)
    manifest: LLMFactorFixtureManifest
    symbol_segments: dict[str, dict[str, str]] = Field(default_factory=dict)


class LLMFactorValidationConfig(StrictBaseModel):
    """Configuration for deterministic LLM Factor validation reports."""

    horizons: list[int] = Field(default_factory=lambda: [1, 5, 20])
    top_n: int = Field(default=5, ge=1)
    top_quantile: float = Field(default=0.8, ge=0, le=1, allow_inf_nan=False)
    threshold_policy: LLMFactorThresholdPolicy = "top_quantile_by_date"
    fixed_score_threshold: float | None = Field(default=None, allow_inf_nan=False)
    return_threshold: float = Field(default=0.0, ge=0, allow_inf_nan=False)
    drawdown_threshold: float = Field(default=0.05, ge=0, allow_inf_nan=False)
    absolute_move_threshold: float = Field(default=0.03, ge=0, allow_inf_nan=False)
    risk_free_rate_per_period: float = Field(default=0.0, allow_inf_nan=False)
    entry_lag_bars: int = Field(default=1, ge=0)
    min_samples: int = Field(default=30, ge=1)
    min_dates: int = Field(default=3, ge=1)
    min_segment_samples: int = Field(default=10, ge=1)
    low_evidence_source_count: int = Field(default=1, ge=0)
    low_evidence_score_threshold: float = Field(default=40.0, ge=0, le=100, allow_inf_nan=False)
    low_evidence_ratio_threshold: float = Field(default=0.25, ge=0, le=1, allow_inf_nan=False)
    class_imbalance_low_threshold: float = Field(default=0.1, ge=0, le=1, allow_inf_nan=False)
    class_imbalance_high_threshold: float = Field(default=0.9, ge=0, le=1, allow_inf_nan=False)
    annualization_periods_per_year: int = Field(default=252, ge=1)
    include_directional_catalyst_factor: bool = True
    include_absolute_move_task: bool = True


class LLMFactorConfusionMatrix(StrictBaseModel):
    tp: int = Field(ge=0)
    fp: int = Field(ge=0)
    tn: int = Field(ge=0)
    fn: int = Field(ge=0)


class LLMFactorClassificationMetrics(StrictBaseModel):
    factor_name: str = Field(min_length=1)
    horizon_days: int = Field(ge=1)
    prediction_task: LLMFactorPredictionTask
    sample_count: int = Field(ge=0)
    positive_count: int = Field(ge=0)
    negative_count: int = Field(ge=0)
    positive_rate: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    threshold_policy: LLMFactorThresholdPolicy
    score_threshold: float | None = Field(default=None, allow_inf_nan=False)
    quantile: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    accuracy: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    precision: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    recall: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    f1: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    auc: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    average_precision: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    confusion_matrix: LLMFactorConfusionMatrix


class LLMFactorReturnMetrics(StrictBaseModel):
    factor_name: str = Field(min_length=1)
    horizon_days: int = Field(ge=1)
    segment: str | None = Field(default=None, min_length=1)
    sample_count: int = Field(ge=0)
    date_count: int = Field(ge=0)
    coverage_ratio: float = Field(ge=0, le=1, allow_inf_nan=False)
    universe_mean_return: float | None = Field(default=None, allow_inf_nan=False)
    universe_median_return: float | None = Field(default=None, allow_inf_nan=False)
    top_n_mean_return: float | None = Field(default=None, allow_inf_nan=False)
    top_n_median_return: float | None = Field(default=None, allow_inf_nan=False)
    top_n_hit_rate: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    top_quantile_mean_return: float | None = Field(default=None, allow_inf_nan=False)
    bottom_quantile_mean_return: float | None = Field(default=None, allow_inf_nan=False)
    top_bottom_spread: float | None = Field(default=None, allow_inf_nan=False)
    excess_top_n_mean_return: float | None = Field(default=None, allow_inf_nan=False)
    excess_top_quantile_mean_return: float | None = Field(default=None, allow_inf_nan=False)


class LLMFactorRiskMetrics(StrictBaseModel):
    factor_name: str = Field(min_length=1)
    horizon_days: int = Field(ge=1)
    segment: str | None = Field(default=None, min_length=1)
    sample_count: int = Field(ge=0)
    date_count: int = Field(ge=0)
    top_n_period_sharpe: float | None = Field(default=None, allow_inf_nan=False)
    top_n_annualized_sharpe: float | None = Field(default=None, allow_inf_nan=False)
    top_n_max_drawdown: float | None = Field(default=None, le=0, allow_inf_nan=False)
    top_n_volatility: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    high_score_avg_drawdown: float | None = Field(default=None, allow_inf_nan=False)
    high_score_worst_drawdown: float | None = Field(default=None, allow_inf_nan=False)
    downside_hit_rate: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)


class LLMFactorBaselineComparisonMetrics(StrictBaseModel):
    factor_name: str = Field(min_length=1)
    baseline_name: str = Field(min_length=1)
    horizon_days: int = Field(ge=1)
    prediction_task: LLMFactorPredictionTask | None = None
    segment: str | None = Field(default=None, min_length=1)
    sample_count: int = Field(ge=0)
    delta_accuracy: float | None = Field(default=None, allow_inf_nan=False)
    delta_precision: float | None = Field(default=None, allow_inf_nan=False)
    delta_recall: float | None = Field(default=None, allow_inf_nan=False)
    delta_f1: float | None = Field(default=None, allow_inf_nan=False)
    delta_auc: float | None = Field(default=None, allow_inf_nan=False)
    delta_top_n_mean_return: float | None = Field(default=None, allow_inf_nan=False)
    delta_top_quantile_mean_return: float | None = Field(default=None, allow_inf_nan=False)
    delta_top_bottom_spread: float | None = Field(default=None, allow_inf_nan=False)
    delta_period_sharpe: float | None = Field(default=None, allow_inf_nan=False)
    delta_max_drawdown: float | None = Field(default=None, allow_inf_nan=False)


class LLMFactorSegmentMetrics(StrictBaseModel):
    segment_name: str = Field(min_length=1)
    segment_value: str = Field(min_length=1)
    factor_name: str = Field(min_length=1)
    horizon_days: int = Field(ge=1)
    sample_count: int = Field(ge=0)
    classification_auc: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    classification_f1: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    top_n_mean_return: float | None = Field(default=None, allow_inf_nan=False)
    top_bottom_spread: float | None = Field(default=None, allow_inf_nan=False)
    period_sharpe: float | None = Field(default=None, allow_inf_nan=False)
    max_drawdown: float | None = Field(default=None, le=0, allow_inf_nan=False)
    baseline_delta_auc: float | None = Field(default=None, allow_inf_nan=False)


class LLMFactorValidationSummary(StrictBaseModel):
    sample_count: int = Field(ge=0)
    symbol_count: int = Field(ge=0)
    date_count: int = Field(ge=0)
    segments: list[str]
    horizons: list[int]
    factor_count: int = Field(ge=0)
    best_factors_by_auc: list[str]
    best_factors_by_top_n_return: list[str]
    best_factors_by_drawdown_signal: list[str]
    best_segments: list[str]
    weak_segments: list[str]


class LLMFactorValidationRecommendation(StrictBaseModel):
    status: LLMFactorRecommendationStatus
    reasons: list[str]
    should_integrate_into_ranking_now: bool = False
    should_integrate_into_forecast_now: bool = False
    should_integrate_into_investment_score_now: bool = False


class LLMFactorValidationReport(StrictBaseModel):
    """Deterministic validation report for LLM material factors."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    schema_version: str = Field(default=LLM_FACTOR_VALIDATION_REPORT_SCHEMA_VERSION, min_length=1)
    fixture_id: str = Field(min_length=1)
    fixture_version: str = Field(min_length=1)
    config_hash: str = Field(min_length=1)
    input_hash: str = Field(min_length=1)
    generated_report_hash: str = Field(min_length=1)
    summary: LLMFactorValidationSummary
    classification_metrics: list[LLMFactorClassificationMetrics]
    return_metrics: list[LLMFactorReturnMetrics]
    risk_metrics: list[LLMFactorRiskMetrics]
    baseline_comparison_metrics: list[LLMFactorBaselineComparisonMetrics]
    segment_metrics: list[LLMFactorSegmentMetrics]
    warnings: list[LLMFactorBacktestWarning] = Field(default_factory=list)
    recommendation: LLMFactorValidationRecommendation
