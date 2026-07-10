from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.forecast.calibration import (  # noqa: E402
    evaluate_consensus_calibration,
    validate_consensus_calibration,
    write_calibration_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate bounded consensus calibration.")
    parser.add_argument("--tuning-points", required=True)
    parser.add_argument("--validation-points", required=True)
    parser.add_argument("--output", default="reports/phase34_forecast_calibration.md")
    args = parser.parse_args(argv)
    tuning = evaluate_consensus_calibration(Path(args.tuning_points))
    validation = validate_consensus_calibration(
        Path(args.validation_points),
        {row.horizon_days: row.factor for row in tuning if row.adopted},
    )
    path = write_calibration_report(tuning, validation, Path(args.output))
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
