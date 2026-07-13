from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from backend.news import (
    RadarInterpretationShadowFixture,
    evaluate_radar_interpretation_shadow_fixture,
    radar_interpretation_shadow_report_markdown,
)

FIXTURE_PATH = Path("tests/fixtures/news/radar_interpretation_shadow_cases.json")


def test_radar_interpretation_shadow_fixture_rejects_every_unsafe_payload():
    fixture = RadarInterpretationShadowFixture.model_validate_json(
        FIXTURE_PATH.read_text(encoding="utf-8")
    )

    report = evaluate_radar_interpretation_shadow_fixture(
        fixture,
        now=datetime(2026, 7, 13, 12, 0, tzinfo=UTC),
    )

    assert report.case_count == 8
    assert report.accepted_count == 1
    assert report.rejected_count == 7
    assert report.passed_count == 8
    assert report.failed_count == 0
    assert {result.actual_reason for result in report.results} >= {
        None,
        "malformed_json",
        "unknown_evidence",
        "wrong_symbol",
        "unsupported_number",
        "unsupported_date",
        "policy_violation",
    }


def test_radar_interpretation_shadow_markdown_omits_raw_gateway_payloads():
    fixture = RadarInterpretationShadowFixture.model_validate_json(
        FIXTURE_PATH.read_text(encoding="utf-8")
    )
    report = evaluate_radar_interpretation_shadow_fixture(
        fixture,
        now=datetime(2026, 7, 13, 12, 0, tzinfo=UTC),
    )

    markdown = radar_interpretation_shadow_report_markdown(report)

    assert "Expected outcome matched: 8/8" in markdown
    assert "unsupported_number" in markdown
    assert "raw_response" not in markdown
    assert "fixture-model" not in markdown
