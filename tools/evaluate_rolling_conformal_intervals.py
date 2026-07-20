from __future__ import annotations

import argparse
import csv
import sys
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main(argv: list[str] | None = None) -> int:
    from backend.forecast.evaluation import ForecastValidationPoint
    from backend.forecast.rolling_conformal import (
        DEFAULT_INTERVAL_HALF_WIDTH_FLOOR,
        DEFAULT_MAX_HISTORY_POINTS,
        DEFAULT_MAX_SCORE_QUANTILE,
        DEFAULT_MIN_GROUP_SAMPLE_COUNT,
        DEFAULT_MIN_ORIGIN_COUNT,
        DEFAULT_MIN_POOLED_SAMPLE_COUNT,
        DEFAULT_TARGET_INTERVAL_COVERAGE,
        evaluate_rolling_conformal_intervals,
        write_rolling_conformal_outputs,
    )

    parser = argparse.ArgumentParser(
        description=(
            "Evaluate causal rolling conformal interval calibration without changing "
            "forecast centers or directions."
        )
    )
    parser.add_argument(
        "--calibration-points",
        action="append",
        required=True,
        help="Forecast validation-points CSV. Repeat to pool disjoint calibration cohorts.",
    )
    parser.add_argument(
        "--evaluation-points",
        action="append",
        required=True,
        help="Forecast validation-points CSV. Repeat to pool evaluation cohorts.",
    )
    parser.add_argument("--output", default="reports/rolling_conformal_intervals")
    parser.add_argument(
        "--evaluation-role",
        choices=("historical_replay", "new_sealed_audit"),
        default="historical_replay",
    )
    parser.add_argument(
        "--separation-mode",
        choices=("symbol_disjoint", "temporal_disjoint"),
        default="symbol_disjoint",
    )
    parser.add_argument(
        "--target-coverage",
        type=Decimal,
        default=DEFAULT_TARGET_INTERVAL_COVERAGE,
    )
    parser.add_argument(
        "--interval-half-width-floor",
        type=Decimal,
        default=DEFAULT_INTERVAL_HALF_WIDTH_FLOOR,
    )
    parser.add_argument(
        "--min-group-samples",
        type=int,
        default=DEFAULT_MIN_GROUP_SAMPLE_COUNT,
    )
    parser.add_argument(
        "--min-pooled-samples",
        type=int,
        default=DEFAULT_MIN_POOLED_SAMPLE_COUNT,
    )
    parser.add_argument(
        "--min-origins",
        type=int,
        default=DEFAULT_MIN_ORIGIN_COUNT,
    )
    parser.add_argument(
        "--max-history-points",
        type=int,
        default=DEFAULT_MAX_HISTORY_POINTS,
    )
    parser.add_argument(
        "--include-matured-evaluation-history",
        action="store_true",
        help=(
            "Prequential mode: later origins may use earlier evaluation labels only after "
            "their target_at has matured."
        ),
    )
    parser.add_argument(
        "--max-score-quantile",
        type=Decimal,
        default=DEFAULT_MAX_SCORE_QUANTILE,
        help="Normalized expansion cap; default 0.5 limits total width to about 1.5x.",
    )
    args = parser.parse_args(argv)
    try:
        calibration = _read_forecast_points(
            [Path(value) for value in args.calibration_points],
            ForecastValidationPoint,
        )
        evaluation = _read_forecast_points(
            [Path(value) for value in args.evaluation_points],
            ForecastValidationPoint,
        )
        report = evaluate_rolling_conformal_intervals(
            calibration,
            evaluation,
            evaluation_role=args.evaluation_role,
            separation_mode=args.separation_mode,
            target_interval_coverage=args.target_coverage,
            interval_half_width_floor=args.interval_half_width_floor,
            min_group_sample_count=args.min_group_samples,
            min_pooled_sample_count=args.min_pooled_samples,
            min_origin_count=args.min_origins,
            max_history_points=args.max_history_points,
            include_matured_evaluation_history=args.include_matured_evaluation_history,
            max_score_quantile=args.max_score_quantile,
        )
    except (OSError, ValueError) as exc:
        print(f"Unable to evaluate rolling conformal intervals: {exc}", file=sys.stderr)
        return 2

    paths = write_rolling_conformal_outputs(report, Path(args.output))
    calibrated_count = sum(
        prediction.decision_status == "calibrated" for prediction in report.predictions
    )
    print(f"calibration points: {report.eligible_calibration_count}")
    print(f"evaluation points: {report.eligible_evaluation_count}")
    print(f"calibrated points: {calibrated_count}")
    print(f"separation valid: {str(report.separation_valid).lower()}")
    print(f"metric gates passed: {str(report.metric_gates_passed).lower()}")
    print(f"review status: {report.review_status}")
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


def _read_forecast_points(paths: list[Path], model_type):
    points = []
    for path in paths:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {
                "symbol",
                "market",
                "asset_type",
                "regime",
                "model_name",
                "horizon_days",
                "origin_at",
                "target_at",
                "predicted_return",
                "predicted_return_lower",
                "predicted_return_upper",
                "actual_return",
            }
            missing = required - set(reader.fieldnames or ())
            if missing:
                raise ValueError(f"{path}: missing required columns: {', '.join(sorted(missing))}")
            for line_number, raw in enumerate(reader, start=2):
                payload = {key: _none_if_empty(value) for key, value in raw.items()}
                try:
                    points.append(model_type.model_validate(payload))
                except ValueError as exc:
                    raise ValueError(f"{path}: invalid row {line_number}: {exc}") from exc
    return points


def _none_if_empty(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
