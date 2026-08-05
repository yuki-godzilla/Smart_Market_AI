import csv
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from backend.forecast.conservative_calibration import ConservativeCalibrationObservation
from tools.evaluate_adaptive_forecast_calibration import (
    assert_observation_symbol_disjoint,
    load_calibration_point_csvs,
    main,
)


def test_point_csv_loader_preserves_all_adaptive_source_returns(tmp_path) -> None:
    path = tmp_path / "points.csv"
    observation = _observation("TRAIN", datetime(2020, 1, 1, tzinfo=UTC), "0")
    _write_points(path, [observation])

    loaded = load_calibration_point_csvs((path,))

    assert len(loaded) == 1
    assert loaded[0].consensus_return == Decimal("0.2")
    assert loaded[0].conservative_returns["advanced_quantile"] == Decimal("0.1")
    assert loaded[0].conservative_returns["moving_average_3"] == Decimal("0.05")


def test_symbol_disjoint_gate_rejects_calibration_overlap() -> None:
    origin = datetime(2020, 1, 1, tzinfo=UTC)
    calibration = [_observation("OVERLAP", origin, "0")]
    evaluation = [_observation("OVERLAP", origin + timedelta(days=90), "0")]

    with pytest.raises(ValueError, match="overlap calibration history"):
        assert_observation_symbol_disjoint(calibration, evaluation)


def test_cli_writes_evaluation_only_manifest_and_japanese_report(tmp_path) -> None:
    calibration_path = tmp_path / "calibration.csv"
    evaluation_path = tmp_path / "evaluation.csv"
    output = tmp_path / "output"
    origins = (
        datetime(2020, 1, 1, tzinfo=UTC),
        datetime(2020, 4, 1, tzinfo=UTC),
        datetime(2020, 7, 1, tzinfo=UTC),
        datetime(2020, 10, 1, tzinfo=UTC),
    )
    calibration = [
        _observation(f"TRAIN{origin_index}_{symbol_index}", origin, "0")
        for origin_index, origin in enumerate(origins)
        for symbol_index in range(10)
    ]
    audit_origin = datetime(2021, 3, 1, tzinfo=UTC)
    evaluation = [
        _observation(f"AUDIT{index}", audit_origin, "0", split="raw_audit") for index in range(12)
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
            "adaptive_audit",
        ]
    )

    assert exit_code == 0
    manifest = json.loads((output / "adaptive_calibration_manifest.json").read_text("utf-8"))
    summary = (output / "adaptive_calibration_evaluation.md").read_text("utf-8")
    assert manifest["evaluation_only"] is True
    assert manifest["runtime_changed"] is False
    assert manifest["symbol_disjoint"] is True
    assert manifest["selected_prediction_count"] == 12
    assert manifest["adaptive_parameters"]["weight_grid_step"] == "0.1"
    assert manifest["adaptive_parameters"]["minimum_adaptive_selection_rate"] == "0.50"
    assert "ランタイムは未変更" in summary
    assert "通過: **はい**" in summary


def _observation(
    symbol: str,
    origin: datetime,
    actual: str,
    *,
    split: str = "calibration_history",
) -> ConservativeCalibrationObservation:
    return ConservativeCalibrationObservation(
        cohort="fixture",
        split=split,
        symbol=symbol,
        market="us",
        asset_type="stock",
        regime="uptrend",
        horizon_days=20,
        origin_at=origin,
        target_at=origin + timedelta(days=30),
        consensus_return=Decimal("0.2"),
        actual_return=Decimal(actual),
        conservative_returns={
            "advanced_quantile": Decimal("0.1"),
            "moving_average_3": Decimal("0.05"),
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
