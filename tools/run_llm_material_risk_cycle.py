from __future__ import annotations

import argparse
import secrets
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class _DisabledGateway:
    def generate(self, request):
        from backend.llm_factor.gateway_adapter import LLMFactorGatewayError

        raise LLMFactorGatewayError(
            "live LLM call was not explicitly enabled",
            gateway_error_type="disabled",
            retryable=False,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate point-in-time LLM material-risk signals for sealed Forecast origins."
        )
    )
    parser.add_argument(
        "--database",
        default="data/cache/forecast_sealed_audit.sqlite",
    )
    parser.add_argument("--manifest-id", required=True)
    parser.add_argument(
        "--archive",
        default="data/cache/point_in_time_material_archive_v1.json",
    )
    parser.add_argument(
        "--signals",
        default="data/cache/llm_material_risk_signals_v1.json",
    )
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-evidence-items", type=int, default=8)
    parser.add_argument(
        "--allow-live-llm",
        action="store_true",
        help="Explicitly allow calls to the configured SMAI AI Gateway.",
    )
    args = parser.parse_args(argv)
    if args.max_evidence_items < 1 or args.max_evidence_items > 20:
        parser.error("--max-evidence-items must be between 1 and 20")
    return _run(args)


def _run(args: argparse.Namespace) -> int:
    from backend.core.config import get_settings
    from backend.forecast.sealed_audit import (
        ForecastSealedAuditError,
        SealedForecastAuditRepository,
    )
    from backend.llm_factor.gateway_adapter import (
        HttpLLMFactorGatewayClient,
        LLMFactorGatewayClient,
    )
    from backend.llm_factor.material_risk_cycle import (
        MaterialRiskCycleError,
        create_material_risk_cycle_run_id,
        run_material_risk_cycle,
        write_material_risk_cycle_failure,
    )

    started_at = datetime.now(UTC)
    run_id = create_material_risk_cycle_run_id(started_at)
    run_dir = Path(args.output) / (f"{started_at:%Y%m%dT%H%M%SZ}_{secrets.token_hex(3)}")
    run_dir.mkdir(parents=True, exist_ok=False)
    settings = get_settings()
    config = settings.llm_factor.live
    gateway: LLMFactorGatewayClient = _DisabledGateway()
    if args.allow_live_llm:
        gateway = HttpLLMFactorGatewayClient(
            base_url=config.base_url,
            endpoint_path=config.endpoint_path,
            timeout_seconds=config.timeout_seconds,
            model=config.model,
            execution_mode=config.execution_mode,
            environment_profile=config.environment_profile,
            preferred_profile=config.preferred_profile,
        )
    try:
        result = run_material_risk_cycle(
            SealedForecastAuditRepository(Path(args.database)),
            gateway,
            manifest_id=args.manifest_id,
            archive_path=Path(args.archive),
            signal_path=Path(args.signals),
            output_dir=run_dir,
            started_at=started_at,
            max_evidence_items=args.max_evidence_items,
            prompt_version=config.prompt_version,
            run_id=run_id,
        )
    except (MaterialRiskCycleError, ForecastSealedAuditError, ValueError) as exc:
        path = write_material_risk_cycle_failure(
            run_dir,
            run_id=run_id,
            manifest_id=args.manifest_id,
            started_at=started_at,
            stage="cycle",
            error=exc,
        )
        print(f"LLM material risk cycle failed: {exc}", file=sys.stderr)
        print(f"failure: {path}", file=sys.stderr)
        return 2
    print(f"run: {result.run_id}")
    print(f"status: {result.status}")
    print(f"forecast groups: {result.forecast_group_count}")
    print(f"generated signals: {result.generated_signal_count}")
    print(f"existing signals: {result.existing_signal_count}")
    print(f"output: {run_dir}")
    return 1 if result.status == "completed_with_failures" else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
