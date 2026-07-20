import csv
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backend.forecast import ConservativeCalibrationObservation
from tools.evaluate_cross_sectional_residual_forecast import main


def test_cli_writes_evaluation_only_cross_sectional_artifacts(tmp_path) -> None:
    calibration_path = tmp_path / "calibration.csv"
    evaluation_path = tmp_path / "evaluation.csv"
    output = tmp_path / "output"
    calibration = [
        _observation(
            f"TRAIN{origin_index}_{symbol_index}",
            datetime(2020, 1, 1, tzinfo=UTC) + timedelta(days=origin_index * 60),
            symbol_index,
            split="development",
        )
        for origin_index in range(6)
        for symbol_index in range(10)
    ]
    evaluation = [
        _observation(
            f"AUDIT{symbol_index}",
            datetime(2022, 1, 1, tzinfo=UTC),
            symbol_index,
            split="raw_audit",
        )
        for symbol_index in range(10)
    ]
    _write_points(calibration_path, calibration)
    _write_points(evaluation_path, evaluation)

    exit_code = main(
        [
            "--calibration-points",
            str(calibration_path),
            "--evaluation-points",
            str(evaluation_path),
            "--output",
            str(output),
            "--evaluation-split",
            "cross_sectional_audit",
            "--min-training-samples",
            "30",
            "--min-training-origins",
            "4",
            "--min-fit-samples",
            "30",
            "--min-validation-samples",
            "10",
            "--min-cross-section-size",
            "5",
            "--min-samples-leaf",
            "2",
        ]
    )

    assert exit_code == 0
    manifest = json.loads((output / "cross_sectional_residual_manifest.json").read_text("utf-8"))
    summary = (output / "cross_sectional_residual_evaluation.md").read_text("utf-8")
    assert manifest["evaluation_only"] is True
    assert manifest["runtime_changed"] is False
    assert manifest["symbol_disjoint"] is True
    assert manifest["evaluation_observation_count"] == 10
    assert manifest["parameters"]["max_leaf_nodes"] == 7
    assert "ランタイムは未変更" in summary
    assert (output / "cross_sectional_residual_metrics.csv").is_file()
    assert (output / "cross_sectional_residual_predictions.csv").is_file()
    assert (output / "cross_sectional_residual_decisions.csv").is_file()


def _observation(
    symbol: str,
    origin: datetime,
    symbol_index: int,
    *,
    split: str,
) -> ConservativeCalibrationObservation:
    anchor = Decimal("-0.04") + Decimal(symbol_index) * Decimal("0.01")
    residual = Decimal("0.05") if symbol_index >= 5 else Decimal("-0.05")
    return ConservativeCalibrationObservation(
        cohort="fixture",
        split=split,
        symbol=symbol,
        market="us",
        asset_type="stock",
        regime="sideways",
        horizon_days=20,
        origin_at=origin,
        target_at=origin + timedelta(days=20),
        consensus_return=anchor,
        actual_return=anchor + residual,
        conservative_returns={
            "advanced_quantile": anchor + residual / Decimal("5"),
            "moving_average_3": anchor,
        },
    )


def _write_points(path, observations: list[ConservativeCalibrationObservation]) -> None:
    fieldnames = [
        "cohort",
        "split",
        "symbol",
        "market",
        "asset_type",
        "regime",
        "horizon_days",
        "origin_at",
        "target_at",
        "consensus_return",
        "advanced_quantile_return",
        "moving_average_3_return",
        "actual_return",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for observation in observations:
            writer.writerow(
                {
                    "cohort": observation.cohort,
                    "split": observation.split,
                    "symbol": observation.symbol,
                    "market": observation.market,
                    "asset_type": observation.asset_type,
                    "regime": observation.regime,
                    "horizon_days": observation.horizon_days,
                    "origin_at": observation.origin_at.isoformat(),
                    "target_at": observation.target_at.isoformat(),
                    "consensus_return": observation.consensus_return,
                    "advanced_quantile_return": observation.conservative_returns[
                        "advanced_quantile"
                    ],
                    "moving_average_3_return": observation.conservative_returns["moving_average_3"],
                    "actual_return": observation.actual_return,
                }
            )
