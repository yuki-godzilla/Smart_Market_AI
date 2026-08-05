from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from backend.forecast import (
    ConservativeCalibrationObservation,
    build_conservative_calibration_report,
    evaluate_horizon_conditioned_calibration,
)
from tools.evaluate_frozen_forecast_calibration import (
    DEFAULT_EXCLUSION_METADATA,
    DEFAULT_PROFILE,
    assert_symbol_disjoint,
    load_frozen_calibration_profiles,
    parse_evaluation_end,
    render_frozen_replication_markdown,
)


def test_default_exclusion_metadata_is_tracked_and_available() -> None:
    assert all(Path(path).is_file() for path in DEFAULT_EXCLUSION_METADATA)


def test_frozen_profile_loader_keeps_exact_20_and_60_day_weights() -> None:
    profiles, sha256 = load_frozen_calibration_profiles(Path(DEFAULT_PROFILE))
    by_horizon = {profile.horizon_days: profile for profile in profiles}

    assert len(sha256) == 64
    assert by_horizon[20].consensus_weight == Decimal("0.3")
    assert by_horizon[20].conservative_weight == Decimal("0.7")
    assert by_horizon[60].consensus_weight == Decimal("0")
    assert by_horizon[60].conservative_weight == Decimal("1")


def test_symbol_disjoint_gate_rejects_any_prior_cohort_overlap(tmp_path) -> None:
    prior = tmp_path / "prior.csv"
    prior.write_text("symbol,market\nAAA,us\nBBB,jp\n", encoding="utf-8")

    assert_symbol_disjoint({"CCC"}, (prior,))
    with pytest.raises(ValueError, match="not symbol-disjoint"):
        assert_symbol_disjoint({"AAA", "CCC"}, (prior,))


def test_replication_report_names_frozen_boundary_and_no_runtime_adoption() -> None:
    profiles, sha256 = load_frozen_calibration_profiles(Path(DEFAULT_PROFILE))
    observations = [_observation(horizon) for horizon in (20, 60)]
    metrics = evaluate_horizon_conditioned_calibration(observations, profiles)
    report = build_conservative_calibration_report(
        profiles,
        metrics,
        required_splits=("new_audit",),
    )

    markdown = render_frozen_replication_markdown(
        report,
        observations,
        profile_sha256=sha256,
        requested_symbol_count=1,
        eligible_symbol_count=1,
        evaluation_end=parse_evaluation_end("2025-12-31"),
        recent_bars=750,
        max_origins=3,
    )

    assert "プロファイル再調整: **なし**" in markdown
    assert "ランタイムの Forecast、Cockpit、Ranking、スコアは未変更" in markdown
    assert "後日の暦期間を使った監査が引き続き必要" in markdown


def test_evaluation_end_parses_date_as_utc_end_of_day() -> None:
    parsed = parse_evaluation_end("2025-12-31")

    assert parsed is not None
    assert parsed.tzinfo == UTC
    assert parsed.isoformat().startswith("2025-12-31T23:59:59.999999")


def _observation(horizon: int) -> ConservativeCalibrationObservation:
    origin = datetime(2024, 1, 1, tzinfo=UTC)
    return ConservativeCalibrationObservation(
        cohort="new_symbols",
        split="new_audit",
        symbol="CCC",
        market="us",
        asset_type="stock",
        regime="uptrend",
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
