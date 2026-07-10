import csv
from decimal import Decimal

from backend.forecast.calibration import (
    evaluate_consensus_calibration,
    validate_consensus_calibration,
)


def test_consensus_calibration_uses_temporal_holdout_and_symbol_validation(tmp_path):
    tuning_path = tmp_path / "tuning.csv"
    validation_path = tmp_path / "validation.csv"
    _write_points(tuning_path, predicted="0.20", actual="0.05")
    _write_points(validation_path, predicted="0.20", actual="0.05")

    tuning = evaluate_consensus_calibration(tuning_path)
    validation = validate_consensus_calibration(
        validation_path,
        {row.horizon_days: row.factor for row in tuning if row.adopted},
    )

    assert tuning[0].factor == Decimal("0.25")
    assert tuning[0].adopted is True
    assert validation[0].adopted is True
    assert validation[0].holdout_rmse < validation[0].default_holdout_rmse


def _write_points(path, *, predicted: str, actual: str):
    fieldnames = [
        "symbol",
        "market",
        "asset_type",
        "regime",
        "model_name",
        "horizon_days",
        "origin_at",
        "target_at",
        "predicted_return",
        "actual_return",
        "model_disagreement",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for index in range(5):
            writer.writerow(
                {
                    "symbol": "AAA",
                    "market": "us",
                    "asset_type": "stock",
                    "regime": "sideways",
                    "model_name": "forecast_consensus",
                    "horizon_days": "20",
                    "origin_at": f"202{index}-01-01T00:00:00+00:00",
                    "target_at": f"202{index}-02-01T00:00:00+00:00",
                    "predicted_return": predicted,
                    "actual_return": actual,
                    "model_disagreement": "0.01",
                }
            )
