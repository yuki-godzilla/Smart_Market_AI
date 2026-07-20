from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

ModelT = TypeVar("ModelT", bound=BaseModel)


def main(argv: list[str] | None = None) -> int:
    from backend.forecast.evaluation import ForecastValidationPoint
    from backend.llm_factor.material_archive import (
        DEFAULT_MATERIAL_ARCHIVE_PATH,
        load_material_archive,
        load_material_risk_signals,
    )
    from backend.llm_factor.material_shadow_evaluation import (
        evaluate_material_risk_shadow,
        write_material_risk_shadow_outputs,
    )

    parser = argparse.ArgumentParser(
        description="Evaluate point-in-time LLM risk signals as confidence/range-only shadow data."
    )
    parser.add_argument("--forecast-points", required=True)
    parser.add_argument("--signals-json", required=True)
    parser.add_argument("--archive", default=str(DEFAULT_MATERIAL_ARCHIVE_PATH))
    parser.add_argument("--output", default="reports/llm_material_risk_shadow")
    args = parser.parse_args(argv)
    try:
        points = _read_forecast_points(Path(args.forecast_points), ForecastValidationPoint)
        signals_result = load_material_risk_signals(Path(args.signals_json))
        if signals_result.warnings:
            raise ValueError(signals_result.warnings[0])
        signals = signals_result.signals
        archive = load_material_archive(Path(args.archive))
        if archive.warnings:
            raise ValueError(archive.warnings[0])
    except (OSError, ValueError) as exc:
        print(f"Unable to load point-in-time shadow inputs: {exc}", file=sys.stderr)
        return 2
    report = evaluate_material_risk_shadow(points, signals, archive.records)
    paths = write_material_risk_shadow_outputs(report, Path(args.output))
    print(f"eligible forecasts: {report.eligible_forecast_count}")
    print(f"matched signals: {report.matched_signal_count}")
    print(f"applied cases: {report.applied_case_count}")
    print(f"adoption status: {report.adoption_status}")
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


def _read_forecast_points(path: Path, model_type: type[ModelT]) -> list[ModelT]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
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
        }
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"missing required columns: {', '.join(sorted(missing))}")
        points = []
        for line_number, raw in enumerate(reader, start=2):
            payload = {key: _none_if_empty(value) for key, value in raw.items()}
            try:
                points.append(model_type.model_validate(payload))
            except ValueError as exc:
                raise ValueError(f"invalid forecast row {line_number}: {exc}") from exc
    return points


def _none_if_empty(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
