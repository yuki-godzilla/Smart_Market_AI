from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit backend contracts before the frontend usability sprint."
    )
    parser.add_argument(
        "--sealed-audit-database",
        default="data/cache/forecast_sealed_audit.sqlite",
    )
    parser.add_argument("--sealed-audit-manifest-id")
    parser.add_argument(
        "--material-archive",
        default="data/cache/point_in_time_material_archive_v1.json",
    )
    parser.add_argument(
        "--material-risk-signals",
        default="data/cache/llm_material_risk_signals_v1.json",
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    from backend.app.main import app
    from backend.core.config import get_settings
    from backend.server_ops.backend_readiness import (
        audit_backend_readiness,
        write_backend_readiness_outputs,
    )

    routes: set[tuple[str, str]] = set()
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if not isinstance(path, str) or not isinstance(methods, set):
            continue
        routes.update((method, path) for method in methods if isinstance(method, str))
    report = audit_backend_readiness(
        get_settings(),
        api_routes=routes,
        sealed_audit_database=Path(args.sealed_audit_database),
        sealed_audit_manifest_id=args.sealed_audit_manifest_id,
        material_archive_path=Path(args.material_archive),
        material_risk_signal_path=Path(args.material_risk_signals),
    )
    paths = write_backend_readiness_outputs(report, Path(args.output))
    print(f"status: {report.status}")
    print(f"frontend sprint ready: {str(report.frontend_sprint_ready).lower()}")
    print(f"blockers: {len(report.blocker_ids)}")
    print(f"pending: {len(report.pending_ids)}")
    print(f"report: {paths['markdown']}")
    return 2 if report.status == "not_ready" else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
