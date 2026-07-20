from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from backend.forecast.sealed_audit import (
    SealedForecastAuditRepository,
    create_forecast_sealed_audit_manifest,
)
from tools.run_llm_material_risk_cycle import main


def test_cli_runs_network_free_when_no_origin_has_eligible_material(tmp_path: Path) -> None:
    database = tmp_path / "sealed.sqlite"
    archive = tmp_path / "archive.json"
    archive.write_text("[]\n", encoding="utf-8")
    now = datetime.now(UTC)
    manifest = create_forecast_sealed_audit_manifest(
        symbols=["AAPL"],
        horizons=[20],
        created_at=now,
        accept_origins_at_or_after=now - timedelta(days=1),
        cohort="new_calendar",
        source_revision="frozen-revision",
        manifest_id="fsa_material_risk_cli_001",
    )
    SealedForecastAuditRepository(database).add_manifest(manifest)
    output = tmp_path / "runs"

    assert (
        main(
            [
                "--database",
                str(database),
                "--manifest-id",
                manifest.manifest_id,
                "--archive",
                str(archive),
                "--signals",
                str(tmp_path / "signals.json"),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    run_dir = next(output.iterdir())
    result = json.loads((run_dir / "llm_material_risk_cycle.json").read_text("utf-8"))
    assert result["status"] == "completed_no_eligible"
    assert result["generated_signal_count"] == 0
