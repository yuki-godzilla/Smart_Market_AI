import csv
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backend.forecast.evaluation import CONSENSUS_MODEL_NAME, ForecastValidationPoint
from tools.evaluate_rolling_conformal_intervals import main


def test_cli_pools_repeatable_inputs_and_writes_shadow_outputs(tmp_path) -> None:
    calibration_path = tmp_path / "calibration.csv"
    evaluation_path = tmp_path / "evaluation.csv"
    output = tmp_path / "output"
    _write_points(
        calibration_path,
        [
            _point(
                symbol=f"CAL{index}",
                origin=datetime(2020, 1 + (index % 2) * 3, 1, tzinfo=UTC),
                target=datetime(2020, 2 + (index % 2) * 3, 1, tzinfo=UTC),
            )
            for index in range(40)
        ],
    )
    audit_origin = datetime(2022, 1, 1, tzinfo=UTC)
    _write_points(
        evaluation_path,
        [
            _point(
                symbol=f"AUDIT{index}",
                origin=audit_origin,
                target=audit_origin + timedelta(days=30),
            )
            for index in range(100)
        ],
    )

    exit_code = main(
        [
            "--calibration-points",
            str(calibration_path),
            "--evaluation-points",
            str(evaluation_path),
            "--output",
            str(output),
        ]
    )

    assert exit_code == 0
    assert (output / "rolling_conformal_cases.csv").exists()
    assert (output / "rolling_conformal_metrics.csv").exists()
    report = (output / "rolling_conformal_report.md").read_text(encoding="utf-8")
    assert "historical_replay" in report
    assert "runtime review eligible: false" in report


def _point(
    *,
    symbol: str,
    origin: datetime,
    target: datetime,
) -> ForecastValidationPoint:
    return ForecastValidationPoint(
        symbol=symbol,
        market="us",
        asset_type="stock",
        regime="sideways",
        model_name=CONSENSUS_MODEL_NAME,
        horizon_days=20,
        origin_at=origin,
        target_at=target,
        predicted_return=Decimal("0"),
        direction_predicted_return=Decimal("0.01"),
        predicted_return_lower=Decimal("-0.05"),
        predicted_return_upper=Decimal("0.05"),
        actual_return=Decimal("0.08"),
    )


def _write_points(path, points: list[ForecastValidationPoint]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(ForecastValidationPoint.model_fields),
            lineterminator="\n",
        )
        writer.writeheader()
        for point in points:
            writer.writerow(point.model_dump(mode="json"))
