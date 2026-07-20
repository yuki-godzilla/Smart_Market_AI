"""Evaluate labelled Radar interpretation payloads without a Gateway connection."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_FIXTURE = Path("tests/fixtures/news/radar_interpretation_shadow_cases.json")


def main() -> int:
    from backend.news import (
        RadarInterpretationShadowFixture,
        evaluate_radar_interpretation_shadow_fixture,
        radar_interpretation_shadow_report_markdown,
    )

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    fixture = RadarInterpretationShadowFixture.model_validate_json(
        args.fixture.read_text(encoding="utf-8")
    )
    report = evaluate_radar_interpretation_shadow_fixture(fixture)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "radar_interpretation_shadow_report.json").write_text(
        report.model_dump_json(indent=2),
        encoding="utf-8",
    )
    (args.output_dir / "radar_interpretation_shadow_report.md").write_text(
        radar_interpretation_shadow_report_markdown(report),
        encoding="utf-8",
    )
    print(
        "radar interpretation shadow evaluation: "
        f"{report.passed_count}/{report.case_count} expected outcomes matched"
    )
    return 0 if report.failed_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
