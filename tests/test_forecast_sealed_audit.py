from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from backend.core.data_contracts import Bar, Symbol
from backend.forecast.sealed_audit import (
    ForecastSealedAuditConflict,
    ForecastSealedAuditCorruptData,
    SealedForecastAuditRepository,
    build_forecast_sealed_prediction,
    create_forecast_sealed_audit_manifest,
    forecast_sealed_validation_points,
    mature_forecast_sealed_predictions,
    summarize_forecast_sealed_audit,
    write_forecast_sealed_audit_artifacts,
)
from backend.forecast.service import (
    FORECAST_ROLE_CONFIDENCE_POLICY_VERSION,
    AdvancedForecastConsensus,
)


def test_repository_is_idempotent_and_rejects_immutable_prediction_change(
    tmp_path: Path,
) -> None:
    repository = SealedForecastAuditRepository(tmp_path / "audit.sqlite")
    manifest = _manifest()
    prediction = _prediction(manifest)

    assert repository.add_manifest(manifest) is True
    assert repository.add_manifest(manifest) is False
    first = repository.add_predictions([prediction])
    duplicate = repository.add_predictions([prediction])

    assert first.inserted_count == 1
    assert duplicate.duplicate_count == 1
    with pytest.raises(ForecastSealedAuditConflict):
        repository.add_predictions(
            [prediction.model_copy(update={"predicted_return": Decimal("0.12")})]
        )


def test_repository_detects_payload_tampering(tmp_path: Path) -> None:
    database = tmp_path / "audit.sqlite"
    repository = SealedForecastAuditRepository(database)
    manifest = _manifest()
    repository.add_manifest(manifest)
    prediction = _prediction(manifest)
    repository.add_predictions([prediction])

    with sqlite3.connect(database) as connection:
        payload = json.loads(
            connection.execute(
                "SELECT payload_json FROM audit_prediction WHERE prediction_id = ?",
                (prediction.prediction_id,),
            ).fetchone()[0]
        )
        payload["predicted_return"] = "0.99"
        connection.execute(
            "UPDATE audit_prediction SET payload_json = ? WHERE prediction_id = ?",
            (json.dumps(payload, sort_keys=True), prediction.prediction_id),
        )

    with pytest.raises(ForecastSealedAuditCorruptData):
        repository.list_predictions(manifest.manifest_id)


def test_maturation_waits_for_exact_later_bar_count_and_exports_points(tmp_path: Path) -> None:
    repository = SealedForecastAuditRepository(tmp_path / "audit.sqlite")
    manifest = _manifest()
    repository.add_manifest(manifest)
    prediction = _prediction(manifest)
    repository.add_predictions([prediction])
    bars = _bars(8)

    early = mature_forecast_sealed_predictions(
        repository,
        manifest.manifest_id,
        {"AAPL": bars[:6]},
        observed_at=bars[5].ts + timedelta(hours=1),
    )
    assert early.inserted_count == 0
    assert [item.reason for item in early.skips] == ["target_not_yet_available"]

    matured = mature_forecast_sealed_predictions(
        repository,
        manifest.manifest_id,
        {"AAPL": bars},
        observed_at=bars[-1].ts + timedelta(hours=1),
    )
    assert matured.inserted_count == 1
    points = forecast_sealed_validation_points(repository, manifest.manifest_id)
    assert len(points) == 1
    assert points[0].origin_at == bars[5].ts
    assert points[0].target_at == bars[7].ts
    assert points[0].actual_return == (bars[7].close / bars[5].close) - Decimal("1")


def test_maturation_fails_closed_for_late_capture_and_revised_origin(tmp_path: Path) -> None:
    bars = _bars(8)

    late_repository = SealedForecastAuditRepository(tmp_path / "late.sqlite")
    late_manifest = _manifest(manifest_id="fsa_late_capture_001")
    late_repository.add_manifest(late_manifest)
    late_prediction = _prediction(
        late_manifest,
        recorded_at=bars[7].ts + timedelta(hours=1),
    )
    late_repository.add_predictions([late_prediction])
    late_result = mature_forecast_sealed_predictions(
        late_repository,
        late_manifest.manifest_id,
        {"AAPL": bars},
        observed_at=bars[7].ts + timedelta(hours=2),
    )
    assert [item.reason for item in late_result.skips] == ["prediction_recorded_after_target"]

    revised_repository = SealedForecastAuditRepository(tmp_path / "revised.sqlite")
    revised_manifest = _manifest(manifest_id="fsa_revised_origin_001")
    revised_repository.add_manifest(revised_manifest)
    revised_prediction = _prediction(revised_manifest)
    revised_repository.add_predictions([revised_prediction])
    revised = list(bars)
    revised[5] = revised[5].model_copy(update={"close": Decimal("999")})
    revised_result = mature_forecast_sealed_predictions(
        revised_repository,
        revised_manifest.manifest_id,
        {"AAPL": revised},
        observed_at=bars[-1].ts + timedelta(hours=1),
    )
    assert [item.reason for item in revised_result.skips] == ["origin_close_revised"]


def test_manifest_boundary_and_policy_version_are_enforced(tmp_path: Path) -> None:
    manifest = _manifest()
    prediction = _prediction(manifest)
    repository = SealedForecastAuditRepository(tmp_path / "audit.sqlite")
    repository.add_manifest(manifest)

    with pytest.raises(ValueError, match="policy differs"):
        repository.add_predictions(
            [prediction.model_copy(update={"selection_policy_version": "changed"})]
        )

    with pytest.raises(ValueError, match="interval must contain"):
        repository.add_predictions(
            [prediction.model_copy(update={"predicted_return_upper": Decimal("0.01")})]
        )


def test_capture_rejects_origin_before_boundary_and_mixed_provider_bars() -> None:
    bars = _bars(8)
    manifest = create_forecast_sealed_audit_manifest(
        symbols=["AAPL"],
        horizons=[2],
        created_at=bars[5].ts + timedelta(hours=2),
        accept_origins_at_or_after=bars[5].ts + timedelta(hours=1),
        cohort="new_calendar",
        source_revision="test-revision",
        manifest_id="fsa_strict_boundary_001",
    )
    with pytest.raises(ValueError, match="predates"):
        build_forecast_sealed_prediction(
            manifest,
            _consensus(),
            bars[:6],
            recorded_at=bars[5].ts + timedelta(hours=1),
            market="US",
            asset_type="stock",
            regime="sideways",
        )

    mixed = list(bars[:6])
    mixed[0] = mixed[0].model_copy(update={"provider": "other"})
    with pytest.raises(ValueError, match="one provider"):
        build_forecast_sealed_prediction(
            _manifest(manifest_id="fsa_mixed_provider_001"),
            _consensus(),
            mixed,
            recorded_at=bars[5].ts + timedelta(hours=1),
            market="US",
            asset_type="stock",
            regime="sideways",
        )


def test_summary_and_artifacts_are_evaluation_compatible(tmp_path: Path) -> None:
    repository = SealedForecastAuditRepository(tmp_path / "audit.sqlite")
    manifest = _manifest(min_cases=1)
    repository.add_manifest(manifest)
    prediction = _prediction(manifest)
    repository.add_predictions([prediction])
    bars = _bars(8)
    mature_forecast_sealed_predictions(
        repository,
        manifest.manifest_id,
        {"AAPL": bars},
        observed_at=bars[-1].ts + timedelta(hours=1),
    )

    summary = summarize_forecast_sealed_audit(repository, manifest.manifest_id)
    row = summary.horizon_rows[0]
    assert row.sample_ready is True
    assert row.interval_sample_count == 1
    assert row.interval_coverage == Decimal("1")
    paths = write_forecast_sealed_audit_artifacts(
        repository,
        manifest.manifest_id,
        tmp_path / "output",
    )
    assert "forecast_consensus" in paths["validation_points"].read_text("utf-8")
    assert "新しい時点で保存した予測" in paths["report"].read_text("utf-8")
    prediction_lines = paths["predictions"].read_text("utf-8").splitlines()
    outcome_lines = paths["outcomes"].read_text("utf-8").splitlines()
    assert len(prediction_lines) == 1
    assert len(outcome_lines) == 1
    assert len(json.loads(prediction_lines[0])["content_hash"]) == 64

    integrity = repository.verify_integrity()
    assert integrity.manifest_count == 1
    assert integrity.prediction_count == 1
    assert integrity.outcome_count == 1

    backup = repository.backup_to(tmp_path / "backup" / "sealed.sqlite")
    backup_repository = SealedForecastAuditRepository(backup)
    backup_integrity = backup_repository.verify_integrity()
    assert backup_integrity == integrity.model_copy(update={"database_path": str(backup)})
    assert backup_repository.list_predictions(manifest.manifest_id) == [prediction]


def _manifest(
    *,
    manifest_id: str = "fsa_test_manifest_001",
    min_cases: int = 100,
):
    bars = _bars(8)
    return create_forecast_sealed_audit_manifest(
        symbols=["aapl"],
        horizons=[2],
        created_at=bars[5].ts + timedelta(hours=2),
        accept_origins_at_or_after=bars[5].ts - timedelta(days=1),
        cohort="new_calendar",
        source_revision="test-revision",
        manifest_id=manifest_id,
        min_cases_per_horizon=min_cases,
    )


def _prediction(
    manifest,
    *,
    recorded_at: datetime | None = None,
):
    bars = _bars(8)
    origin_bars = bars[:6]
    return build_forecast_sealed_prediction(
        manifest,
        _consensus(),
        origin_bars,
        recorded_at=recorded_at or origin_bars[-1].ts + timedelta(hours=1),
        market="US",
        asset_type="stock",
        regime="sideways",
    )


def _consensus() -> AdvancedForecastConsensus:
    return AdvancedForecastConsensus(
        symbol="AAPL",
        horizon_days=2,
        model_count=2,
        available_model_count=2,
        center_model_count=1,
        consensus_predicted_return=Decimal("0.05"),
        direction_predicted_return=Decimal("0.04"),
        consensus_forecast_close=Decimal("110.25"),
        median_predicted_return=Decimal("0.05"),
        min_predicted_return=Decimal("0.04"),
        max_predicted_return=Decimal("0.06"),
        predicted_return_range=Decimal("0.02"),
        center_predicted_return_range=Decimal("0"),
        direction_predicted_return_range=Decimal("0.02"),
        predicted_return_lower=Decimal("-0.10"),
        predicted_return_upper=Decimal("0.20"),
        forecast_close_lower=Decimal("94.50"),
        forecast_close_upper=Decimal("126.00"),
        agreement="medium",
        confidence="medium",
        center_confidence="medium",
        direction_confidence="medium",
        confidence_policy_version=FORECAST_ROLE_CONFIDENCE_POLICY_VERSION,
        direction_agreement_score=Decimal("75"),
        weighted_direction_score=Decimal("0.70"),
        mean_direction_accuracy=Decimal("0.60"),
        mean_rmse=Decimal("0.10"),
        selection_policy_version="horizon_validation_router_v1",
        horizon_band="short",
        audit_status="interpolated",
        selection_mode="quantile_anchor",
        center_adapter_names=["advanced_quantile"],
        direction_adapter_names=["advanced_quantile", "advanced_tree_sklearn"],
        selected_adapter_names=["advanced_quantile", "advanced_tree_sklearn"],
        model_weights={"advanced_quantile": Decimal("1")},
    )


def _bars(count: int) -> list[Bar]:
    start = datetime(2026, 7, 1, tzinfo=UTC)
    closes = [Decimal("100") + Decimal(index) for index in range(count)]
    return [
        Bar(
            symbol=Symbol(raw="AAPL", exchange="NASDAQ", code="AAPL", currency="USD"),
            ts=start + timedelta(days=index),
            open=close,
            high=close,
            low=close,
            close=close,
            volume=Decimal("1000000"),
            interval="1d",
            provider="fixture",
        )
        for index, close in enumerate(closes)
    ]
