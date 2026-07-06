from __future__ import annotations

import csv
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from pydantic import Field

from backend.core.data_contracts import StrictBaseModel
from backend.forecast.adapters import (
    AdvancedGbdtSklearnForecastAdapter,
    AdvancedLinearForecastAdapter,
    AdvancedQuantileForecastAdapter,
    AdvancedTreeSklearnForecastAdapter,
)
from backend.forecast.advanced_registry import AdvancedForecastAdapter
from backend.forecast.evaluation import ForecastEvaluationCase


class ForecastTuningResult(StrictBaseModel):
    adapter_name: str = Field(min_length=1)
    horizon_days: int = Field(ge=1)
    candidate_name: str = Field(min_length=1)
    tuning_rmse: Decimal = Field(ge=0)
    holdout_rmse: Decimal = Field(ge=0)
    default_holdout_rmse: Decimal = Field(ge=0)
    holdout_direction_accuracy: Decimal = Field(ge=0, le=1)
    default_holdout_direction_accuracy: Decimal = Field(ge=0, le=1)
    adopted: bool
    parameters: dict[str, str | int | float]
    reason: str = Field(min_length=1)


@dataclass(frozen=True)
class _Candidate:
    adapter_name: str
    name: str
    parameters: dict[str, str | int | float]
    factory: Callable[[], AdvancedForecastAdapter]
    is_default: bool = False


@dataclass(frozen=True)
class _Point:
    origin_at: datetime
    predicted: Decimal
    actual: Decimal


def tune_forecast_adapters(
    cases: list[ForecastEvaluationCase],
    *,
    horizons: tuple[int, ...] = (20, 60),
    max_origins: int = 5,
) -> list[ForecastTuningResult]:
    """Compare one bounded candidate per existing adapter on temporal holdout."""

    results: list[ForecastTuningResult] = []
    for adapter_name, candidates in _candidate_groups().items():
        default = next(candidate for candidate in candidates if candidate.is_default)
        alternative = next(candidate for candidate in candidates if not candidate.is_default)
        for horizon in horizons:
            candidate_points = {
                candidate.name: _candidate_points(
                    cases,
                    candidate,
                    horizon_days=horizon,
                    max_origins=max_origins,
                )
                for candidate in candidates
            }
            origins = sorted(
                {point.origin_at for points in candidate_points.values() for point in points}
            )
            split = max(1, int(len(origins) * 0.6)) if len(origins) >= 2 else len(origins)
            tuning_origins = set(origins[:split])
            holdout_origins = set(origins[split:])
            default_holdout = _select(candidate_points[default.name], holdout_origins)
            alternative_tuning = _select(candidate_points[alternative.name], tuning_origins)
            alternative_holdout = _select(candidate_points[alternative.name], holdout_origins)
            default_holdout_rmse = _rmse(default_holdout)
            alternative_holdout_rmse = _rmse(alternative_holdout)
            default_direction = _direction_accuracy(default_holdout)
            alternative_direction = _direction_accuracy(alternative_holdout)
            adopted = bool(alternative_holdout) and (
                alternative_holdout_rmse < default_holdout_rmse
                and alternative_direction >= default_direction
            )
            results.append(
                ForecastTuningResult(
                    adapter_name=adapter_name,
                    horizon_days=horizon,
                    candidate_name=alternative.name,
                    tuning_rmse=_rmse(alternative_tuning),
                    holdout_rmse=alternative_holdout_rmse,
                    default_holdout_rmse=default_holdout_rmse,
                    holdout_direction_accuracy=alternative_direction,
                    default_holdout_direction_accuracy=default_direction,
                    adopted=adopted,
                    parameters=alternative.parameters,
                    reason=(
                        "時系列holdoutでRMSEが改善し、方向一致率を維持しました。"
                        if adopted
                        else "時系列holdoutの採用条件を満たさないため既定設定を維持します。"
                    ),
                )
            )
    return results


def write_forecast_tuning_artifacts(
    results: list[ForecastTuningResult],
    output_dir: Path,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "forecast_model_tuning_results.csv"
    markdown_path = output_dir / "forecast_model_tuning_summary.md"
    fieldnames = list(ForecastTuningResult.model_fields)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            row = result.model_dump(mode="json")
            row["parameters"] = ",".join(
                f"{key}={value}" for key, value in result.parameters.items()
            )
            writer.writerow(row)
    lines = [
        "# Forecast Model Tuning Summary",
        "",
        "既存4モデルのbounded candidateを時系列holdoutで比較します。",
        "採用条件未達の候補は通常予測へ反映しません。",
        "",
    ]
    for result in results:
        lines.extend(
            [
                f"## {result.adapter_name} / {result.horizon_days}営業日",
                "",
                f"- 候補: `{result.candidate_name}`",
                f"- 判定: {'採用候補' if result.adopted else '既定維持'}",
                f"- 既定holdout RMSE: {result.default_holdout_rmse}",
                f"- 候補holdout RMSE: {result.holdout_rmse}",
                f"- 既定方向一致率: {result.default_holdout_direction_accuracy}",
                f"- 候補方向一致率: {result.holdout_direction_accuracy}",
                f"- 理由: {result.reason}",
                "",
            ]
        )
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    return {"tuning_csv": csv_path, "tuning_markdown": markdown_path}


def _candidate_points(
    cases: list[ForecastEvaluationCase],
    candidate: _Candidate,
    *,
    horizon_days: int,
    max_origins: int,
) -> list[_Point]:
    points: list[_Point] = []
    for case in cases:
        bars = sorted(case.bars, key=lambda bar: bar.ts)
        for origin in _origins(len(bars), horizon_days, max_origins):
            try:
                predicted = (
                    candidate.factory()
                    .forecast(
                        bars[: origin + 1],
                        horizon_days=horizon_days,
                    )
                    .predicted_return
                )
            except ValueError:
                continue
            actual = (bars[origin + horizon_days].close / bars[origin].close) - Decimal("1")
            points.append(
                _Point(
                    origin_at=bars[origin].ts,
                    predicted=predicted,
                    actual=actual,
                )
            )
    return points


def _candidate_groups() -> dict[str, tuple[_Candidate, _Candidate]]:
    return {
        "advanced_linear": (
            _Candidate("advanced_linear", "default", {}, AdvancedLinearForecastAdapter, True),
            _Candidate(
                "advanced_linear",
                "ridge_alpha_4",
                {"alpha": 4.0},
                lambda: AdvancedLinearForecastAdapter(alpha=4.0),
            ),
        ),
        "advanced_tree_sklearn": (
            _Candidate(
                "advanced_tree_sklearn",
                "default",
                {},
                AdvancedTreeSklearnForecastAdapter,
                True,
            ),
            _Candidate(
                "advanced_tree_sklearn",
                "conservative_tree",
                {"n_estimators": 96, "max_depth": 3, "min_samples_leaf": 6},
                lambda: AdvancedTreeSklearnForecastAdapter(
                    n_estimators=96,
                    max_depth=3,
                    min_samples_leaf=6,
                ),
            ),
        ),
        "advanced_gbdt_sklearn": (
            _Candidate(
                "advanced_gbdt_sklearn",
                "default",
                {},
                AdvancedGbdtSklearnForecastAdapter,
                True,
            ),
            _Candidate(
                "advanced_gbdt_sklearn",
                "regularized_gbdt",
                {"max_iter": 64, "min_samples_leaf": 8, "l2_regularization": 0.1},
                lambda: AdvancedGbdtSklearnForecastAdapter(
                    max_iter=64,
                    min_samples_leaf=8,
                    l2_regularization=0.1,
                ),
            ),
        ),
        "advanced_quantile": (
            _Candidate(
                "advanced_quantile",
                "default",
                {},
                AdvancedQuantileForecastAdapter,
                True,
            ),
            _Candidate(
                "advanced_quantile",
                "lower_center_quantile",
                {"center_quantile": 0.45},
                lambda: AdvancedQuantileForecastAdapter(center_quantile=0.45),
            ),
        ),
    }


def _origins(count: int, horizon: int, maximum: int) -> list[int]:
    first = max(40, horizon + 24) - 1
    last = count - horizon - 1
    if last < first:
        return []
    values = list(range(first, last + 1))
    if len(values) <= maximum:
        return values
    return sorted(
        {values[round(index * (len(values) - 1) / (maximum - 1))] for index in range(maximum)}
    )


def _select(points: list[_Point], origins: set[datetime]) -> list[_Point]:
    return [point for point in points if point.origin_at in origins]


def _rmse(points: list[_Point]) -> Decimal:
    if not points:
        return Decimal("0.0000")
    value = sum(
        ((point.predicted - point.actual) ** 2 for point in points),
        Decimal("0"),
    ) / Decimal(len(points))
    return value.sqrt().quantize(Decimal("0.0001"))


def _direction_accuracy(points: list[_Point]) -> Decimal:
    if not points:
        return Decimal("0.0000")
    matches = sum(1 for point in points if (point.predicted > 0) == (point.actual > 0))
    return (Decimal(matches) / Decimal(len(points))).quantize(Decimal("0.0001"))
