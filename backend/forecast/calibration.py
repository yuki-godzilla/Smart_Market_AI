from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from pydantic import Field

from backend.core.data_contracts import StrictBaseModel

CALIBRATION_FACTORS = (
    Decimal("0.25"),
    Decimal("0.50"),
    Decimal("0.75"),
    Decimal("1.00"),
)
MIN_RELATIVE_RMSE_IMPROVEMENT = Decimal("0.01")


class ForecastCalibrationResult(StrictBaseModel):
    horizon_days: int = Field(ge=1)
    factor: Decimal = Field(gt=0, le=1)
    tuning_rmse: Decimal = Field(ge=0)
    holdout_rmse: Decimal = Field(ge=0)
    default_holdout_rmse: Decimal = Field(ge=0)
    holdout_direction_accuracy: Decimal = Field(ge=0, le=1)
    default_holdout_direction_accuracy: Decimal = Field(ge=0, le=1)
    adopted: bool
    reason: str = Field(min_length=1)


def evaluate_consensus_calibration(
    points_path: Path,
) -> list[ForecastCalibrationResult]:
    points = _load_consensus_points(points_path)
    results = []
    for horizon, rows in sorted(points.items()):
        origins = sorted({row[0] for row in rows})
        split = max(1, int(len(origins) * 0.6)) if len(origins) >= 2 else len(origins)
        tuning_origins = set(origins[:split])
        holdout_origins = set(origins[split:])
        tuning = [row for row in rows if row[0] in tuning_origins]
        holdout = [row for row in rows if row[0] in holdout_origins]
        factor = min(CALIBRATION_FACTORS, key=lambda value: _rmse(tuning, value))
        default_rmse = _rmse(holdout, Decimal("1"))
        calibrated_rmse = _rmse(holdout, factor)
        default_direction = _direction_accuracy(holdout, Decimal("1"))
        calibrated_direction = _direction_accuracy(holdout, factor)
        adopted = bool(holdout) and (
            calibrated_rmse <= default_rmse * (Decimal("1") - MIN_RELATIVE_RMSE_IMPROVEMENT)
            and calibrated_direction >= default_direction
        )
        results.append(
            ForecastCalibrationResult(
                horizon_days=horizon,
                factor=factor,
                tuning_rmse=_rmse(tuning, factor),
                holdout_rmse=calibrated_rmse,
                default_holdout_rmse=default_rmse,
                holdout_direction_accuracy=calibrated_direction,
                default_holdout_direction_accuracy=default_direction,
                adopted=adopted,
                reason=(
                    "時間順holdoutでRMSEを1%以上改善し、方向一致率を維持しました。"
                    if adopted
                    else "時間順holdoutの採用条件を満たさないため既定値を維持します。"
                ),
            )
        )
    return results


def validate_consensus_calibration(
    points_path: Path,
    factors: dict[int, Decimal],
) -> list[ForecastCalibrationResult]:
    points = _load_consensus_points(points_path)
    results = []
    for horizon, factor in sorted(factors.items()):
        rows = points.get(horizon, [])
        default_rmse = _rmse(rows, Decimal("1"))
        calibrated_rmse = _rmse(rows, factor)
        default_direction = _direction_accuracy(rows, Decimal("1"))
        calibrated_direction = _direction_accuracy(rows, factor)
        adopted = bool(rows) and (
            calibrated_rmse <= default_rmse * (Decimal("1") - MIN_RELATIVE_RMSE_IMPROVEMENT)
            and calibrated_direction >= default_direction
        )
        results.append(
            ForecastCalibrationResult(
                horizon_days=horizon,
                factor=factor,
                tuning_rmse=Decimal("0"),
                holdout_rmse=calibrated_rmse,
                default_holdout_rmse=default_rmse,
                holdout_direction_accuracy=calibrated_direction,
                default_holdout_direction_accuracy=default_direction,
                adopted=adopted,
                reason=(
                    "未使用銘柄群でRMSEを1%以上改善し、方向一致率を維持しました。"
                    if adopted
                    else "未使用銘柄群で再現しないため採用しません。"
                ),
            )
        )
    return results


def write_calibration_report(
    tuning: list[ForecastCalibrationResult],
    validation: list[ForecastCalibrationResult],
    path: Path,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Forecast Consensus Calibration Sprint",
        "",
        "予測方向を変えず、予測幅だけを保守的に縮小する事前定義候補を比較します。",
        "factorは調整群の前半originで選び、後半originと銘柄非重複の検証群で確認します。",
        "",
        "| Stage | Horizon | Factor | Default RMSE | Candidate RMSE | Direction | Adopted |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    lines.extend(_result_line("tuning-holdout", row) for row in tuning)
    lines.extend(_result_line("symbol-validation", row) for row in validation)
    lines.extend(["", "監査群を確認するまではruntimeへ適用しません。", ""])
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return path


def _load_consensus_points(path: Path):
    grouped: dict[int, list[tuple[datetime, Decimal, Decimal]]] = defaultdict(list)
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["model_name"] != "forecast_consensus":
                continue
            grouped[int(row["horizon_days"])].append(
                (
                    datetime.fromisoformat(row["origin_at"]),
                    Decimal(row["predicted_return"]),
                    Decimal(row["actual_return"]),
                )
            )
    return grouped


def _rmse(rows, factor: Decimal) -> Decimal:
    if not rows:
        return Decimal("0")
    mean_square = sum(
        ((predicted * factor - actual) ** 2 for _, predicted, actual in rows),
        Decimal("0"),
    ) / Decimal(len(rows))
    return mean_square.sqrt().quantize(Decimal("0.0001"))


def _direction_accuracy(rows, factor: Decimal) -> Decimal:
    if not rows:
        return Decimal("0")
    matches = sum(_sign(predicted * factor) == _sign(actual) for _, predicted, actual in rows)
    return (Decimal(matches) / Decimal(len(rows))).quantize(Decimal("0.0001"))


def _sign(value: Decimal) -> int:
    return 1 if value > 0 else -1 if value < 0 else 0


def _result_line(stage: str, row: ForecastCalibrationResult) -> str:
    return (
        f"| {stage} | {row.horizon_days} | {row.factor} | "
        f"{row.default_holdout_rmse} | {row.holdout_rmse} | "
        f"{row.holdout_direction_accuracy} | {'yes' if row.adopted else 'no'} |"
    )
