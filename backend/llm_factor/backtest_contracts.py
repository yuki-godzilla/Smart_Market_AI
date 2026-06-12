from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import ConfigDict, Field

from backend.core.data_contracts import StrictBaseModel

LLM_FACTOR_BACKTEST_RESULT_SCHEMA_VERSION = "llm-factor-backtest-result-v1"

LLMFactorBacktestWarningSeverity = Literal["info", "warning", "error"]


class LLMFactorBacktestSignal(StrictBaseModel):
    """One source-bound LLM Factor signal available for factor evaluation."""

    symbol: str = Field(min_length=1)
    signal_date: date
    available_at: datetime | None = None
    bullish_score: float = Field(allow_inf_nan=False)
    bearish_score: float = Field(allow_inf_nan=False)
    catalyst_score: float = Field(allow_inf_nan=False)
    risk_score: float = Field(allow_inf_nan=False)
    confidence_score: float = Field(allow_inf_nan=False)
    evidence_quality_score: float = Field(allow_inf_nan=False)
    freshness_score: float = Field(allow_inf_nan=False)
    source_count: int = Field(default=0, ge=0)
    llm_factor_result_id: str | None = Field(default=None, min_length=1)


class LLMFactorPriceBar(StrictBaseModel):
    """Minimal deterministic price fixture used by LLM Factor backtests."""

    symbol: str = Field(min_length=1)
    date: date
    open: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    close: float = Field(gt=0, allow_inf_nan=False)
    adjusted_close: float | None = Field(default=None, gt=0, allow_inf_nan=False)


class LLMFactorBacktestCase(StrictBaseModel):
    """Input contract for deterministic LLM Factor alpha evaluation."""

    case_id: str = Field(min_length=1)
    signals: list[LLMFactorBacktestSignal]
    prices: list[LLMFactorPriceBar]
    horizons: list[int] = Field(default_factory=lambda: [1, 5, 20])
    top_n: int = Field(default=10, ge=1)
    high_score_quantile: float = Field(default=0.8, ge=0, le=1, allow_inf_nan=False)
    min_samples: int = Field(default=30, ge=1)
    min_dates: int = Field(default=3, ge=1)
    entry_lag_bars: int = Field(default=1, ge=0)
    quality_gate: dict[str, float] | None = None


class LLMFactorBacktestMetrics(StrictBaseModel):
    """Factor-by-horizon diagnostics for source-bound LLM material scores."""

    factor_name: str = Field(min_length=1)
    horizon_days: int = Field(ge=1)
    sample_count: int = Field(ge=0)
    date_count: int = Field(ge=0)
    coverage_ratio: float = Field(ge=0, le=1, allow_inf_nan=False)
    top_n_mean_return: float | None = Field(default=None, allow_inf_nan=False)
    high_score_mean_return: float | None = Field(default=None, allow_inf_nan=False)
    high_score_hit_rate: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    high_score_down_rate: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    high_score_avg_drawdown: float | None = Field(default=None, allow_inf_nan=False)
    universe_mean_return: float | None = Field(default=None, allow_inf_nan=False)
    universe_avg_drawdown: float | None = Field(default=None, allow_inf_nan=False)
    excess_top_n_mean_return: float | None = Field(default=None, allow_inf_nan=False)
    high_score_count: int = Field(default=0, ge=0)
    top_n_count: int = Field(default=0, ge=0)
    zero_variance_factor: bool = False


class LLMFactorBacktestWarning(StrictBaseModel):
    """Structured warning emitted by LLM Factor alpha evaluation."""

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    factor_name: str | None = Field(default=None, min_length=1)
    horizon_days: int | None = Field(default=None, ge=1)
    severity: LLMFactorBacktestWarningSeverity = "warning"


class LLMFactorBacktestResult(StrictBaseModel):
    """Deterministic output for LLM Factor alpha diagnostics."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    schema_version: str = Field(
        default=LLM_FACTOR_BACKTEST_RESULT_SCHEMA_VERSION,
        min_length=1,
    )
    case_id: str = Field(min_length=1)
    metrics: list[LLMFactorBacktestMetrics]
    warnings: list[LLMFactorBacktestWarning] = Field(default_factory=list)
    input_hash: str = Field(min_length=1)
    config_hash: str = Field(min_length=1)
