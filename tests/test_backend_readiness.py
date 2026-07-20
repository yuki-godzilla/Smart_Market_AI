from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from backend.core.config import DataAccessConfig, Settings
from backend.forecast.sealed_audit import (
    SealedForecastAuditRepository,
    create_forecast_sealed_audit_manifest,
)
from backend.llm_factor.material_archive import archive_material_risk_signals
from backend.server_ops.backend_readiness import (
    REQUIRED_BACKEND_API_ROUTES,
    audit_backend_readiness,
    write_backend_readiness_outputs,
)
from tools.audit_backend_readiness import main


def test_backend_readiness_separates_pending_evidence_from_blockers(tmp_path: Path) -> None:
    database, manifest_id, archive, signals = _runtime_artifacts(tmp_path)

    report = audit_backend_readiness(
        _settings(),
        api_routes=set(REQUIRED_BACKEND_API_ROUTES),
        sealed_audit_database=database,
        sealed_audit_manifest_id=manifest_id,
        material_archive_path=archive,
        material_risk_signal_path=signals,
        generated_at=datetime(2026, 7, 20, 12, tzinfo=UTC),
    )

    assert report.status == "ready_with_pending_evidence"
    assert report.frontend_sprint_ready is True
    assert report.blocker_ids == []
    assert report.pending_ids == ["forecast.matured_evidence", "llm_material.signals"]
    assert {check.check_id for check in report.checks if check.status == "pass"} == {
        "api.required_routes",
        "marketdata.provider",
        "marketdata.operation_deadline",
        "forecast.sealed_audit",
        "llm_material.archive",
    }
    paths = write_backend_readiness_outputs(report, tmp_path / "output")
    assert paths["json"].is_file()
    assert "Frontend usability sprintへ移行可能: `true`" in paths["markdown"].read_text("utf-8")


def test_backend_readiness_fails_for_corrupt_material_archive(tmp_path: Path) -> None:
    database, manifest_id, archive, signals = _runtime_artifacts(tmp_path)
    archive.write_text("{bad json", encoding="utf-8")

    report = audit_backend_readiness(
        _settings(),
        api_routes=set(REQUIRED_BACKEND_API_ROUTES),
        sealed_audit_database=database,
        sealed_audit_manifest_id=manifest_id,
        material_archive_path=archive,
        material_risk_signal_path=signals,
    )

    assert report.status == "not_ready"
    assert report.frontend_sprint_ready is False
    assert report.blocker_ids == ["llm_material.archive"]


def test_backend_readiness_fails_for_missing_required_api_route(tmp_path: Path) -> None:
    database, manifest_id, archive, signals = _runtime_artifacts(tmp_path)
    routes = set(REQUIRED_BACKEND_API_ROUTES)
    routes.remove(("POST", "/forecast/evaluate"))

    report = audit_backend_readiness(
        _settings(),
        api_routes=routes,
        sealed_audit_database=database,
        sealed_audit_manifest_id=manifest_id,
        material_archive_path=archive,
        material_risk_signal_path=signals,
    )

    assert report.status == "not_ready"
    assert report.blocker_ids == ["api.required_routes"]


def test_backend_readiness_cli_writes_machine_and_human_reports(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database, manifest_id, archive, signals = _runtime_artifacts(tmp_path)
    monkeypatch.setenv("SMAI_CONFIG_FILE", "tests/fixtures/config/local.yaml")
    output = tmp_path / "cli-output"

    assert (
        main(
            [
                "--sealed-audit-database",
                str(database),
                "--sealed-audit-manifest-id",
                manifest_id,
                "--material-archive",
                str(archive),
                "--material-risk-signals",
                str(signals),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    payload = json.loads((output / "backend_readiness.json").read_text("utf-8"))
    assert payload["status"] == "ready_with_pending_evidence"
    assert payload["frontend_sprint_ready"] is True


def _runtime_artifacts(tmp_path: Path) -> tuple[Path, str, Path, Path]:
    created_at = datetime(2026, 7, 20, 12, tzinfo=UTC)
    manifest = create_forecast_sealed_audit_manifest(
        symbols=["7203.T"],
        horizons=[20],
        created_at=created_at,
        accept_origins_at_or_after=created_at - timedelta(days=1),
        cohort="new_calendar",
        source_revision="frozen-revision",
        manifest_id="fsa_backend_readiness_001",
    )
    database = tmp_path / "sealed.sqlite"
    SealedForecastAuditRepository(database).add_manifest(manifest)
    archive = tmp_path / "archive.json"
    archive.write_text("[]\n", encoding="utf-8")
    signals = tmp_path / "signals.json"
    archive_material_risk_signals([], path=signals)
    return database, manifest.manifest_id, archive, signals


def _settings() -> Settings:
    return Settings(dataaccess=DataAccessConfig(provider="mock", allow_external_providers=False))
