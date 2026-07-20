import csv
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backend.forecast import (
    ConservativeCalibrationObservation,
    build_conservative_calibration_report,
    evaluate_horizon_conditioned_calibration,
    fit_horizon_conditioned_calibration,
)
from tools.evaluate_conservative_forecast_calibration import (
    render_conservative_calibration_markdown,
    write_conservative_calibration_artifacts,
)


def test_conservative_calibration_tool_writes_frozen_profile_metrics_and_points(tmp_path) -> None:
    observations = [
        _observation(index=index, split=split, horizon=horizon)
        for split in ("tuning", "validation", "audit")
        for horizon in (20, 60)
        for index in range(10)
    ]
    profiles = fit_horizon_conditioned_calibration(
        [observation for observation in observations if observation.split == "tuning"]
    )
    metrics = evaluate_horizon_conditioned_calibration(observations, profiles)
    report = build_conservative_calibration_report(profiles, metrics)

    paths = write_conservative_calibration_artifacts(
        report,
        observations,
        tmp_path,
        recent_bars=750,
        max_origins=3,
    )

    profile_payload = json.loads(paths["profile"].read_text(encoding="utf-8"))
    with paths["points"].open(encoding="utf-8", newline="") as handle:
        point_rows = list(csv.DictReader(handle))
    markdown = paths["summary"].read_text(encoding="utf-8")

    assert len(profile_payload["profiles"]) == 2
    assert len(point_rows) == 60
    assert {row["split"] for row in point_rows} == {"tuning", "validation", "audit"}
    assert all(row["retained_direction_return"] == row["consensus_return"] for row in point_rows)
    assert "profileはtuningだけで決定" in markdown
    assert "Runtime review eligible" in markdown
    assert render_conservative_calibration_markdown(
        report, recent_bars=750, max_origins=3
    ).startswith("# Horizon-conditioned")


def _observation(*, index: int, split: str, horizon: int) -> ConservativeCalibrationObservation:
    origin = datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=index)
    return ConservativeCalibrationObservation(
        cohort="fixture",
        split=split,
        symbol=f"SYM{index:03d}",
        market="us",
        asset_type="stock",
        regime="range_bound",
        horizon_days=horizon,
        origin_at=origin,
        target_at=origin + timedelta(days=horizon),
        consensus_return=Decimal("0.20"),
        actual_return=Decimal("0.10"),
        conservative_returns={
            "advanced_quantile": Decimal("0.12"),
            "moving_average_3": Decimal("0.10"),
        },
    )
