"""Network-free shadow evaluation for evidence-bound Radar interpretations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import Field, ValidationError

from backend.assistant.gateway_contracts import AssistantGatewayResponse
from backend.core.data_contracts import StrictBaseModel
from backend.news.contracts import RadarCandidate, RadarEvidenceBundle
from backend.news.radar_interpretation import (
    RadarInterpretationValidationError,
    build_radar_interpretation_context,
    radar_interpretation_from_gateway_response,
)

ShadowExpectedOutcome = Literal["accepted", "rejected"]
ShadowActualOutcome = Literal["accepted", "rejected"]


class RadarInterpretationShadowCase(StrictBaseModel):
    """One labelled Gateway payload evaluated without an external call."""

    case_id: str = Field(min_length=1)
    raw_response: dict[str, object]
    expected_outcome: ShadowExpectedOutcome
    expected_reason: str | None = Field(default=None, min_length=1)


class RadarInterpretationShadowFixture(StrictBaseModel):
    """Shared candidate/evidence context and labelled payload cases."""

    candidate: RadarCandidate
    evidence_bundle: RadarEvidenceBundle
    cases: list[RadarInterpretationShadowCase] = Field(min_length=1)


class RadarInterpretationShadowCaseResult(StrictBaseModel):
    case_id: str = Field(min_length=1)
    expected_outcome: ShadowExpectedOutcome
    expected_reason: str | None = Field(default=None, min_length=1)
    actual_outcome: ShadowActualOutcome
    actual_reason: str | None = Field(default=None, min_length=1)
    passed: bool


class RadarInterpretationShadowReport(StrictBaseModel):
    generated_at: datetime
    case_count: int = Field(ge=0)
    accepted_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)
    passed_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    results: list[RadarInterpretationShadowCaseResult] = Field(default_factory=list)


def evaluate_radar_interpretation_shadow_fixture(
    fixture: RadarInterpretationShadowFixture,
    *,
    now: datetime | None = None,
) -> RadarInterpretationShadowReport:
    """Evaluate typed and malformed payloads against the parent grounding validator."""

    generated_at = _ensure_utc(now or datetime.now(UTC))
    context = build_radar_interpretation_context(
        fixture.candidate,
        fixture.evidence_bundle,
        now=generated_at,
    )
    results = [
        _evaluate_case(case, context=context, generated_at=generated_at) for case in fixture.cases
    ]
    accepted_count = sum(result.actual_outcome == "accepted" for result in results)
    passed_count = sum(result.passed for result in results)
    return RadarInterpretationShadowReport(
        generated_at=generated_at,
        case_count=len(results),
        accepted_count=accepted_count,
        rejected_count=len(results) - accepted_count,
        passed_count=passed_count,
        failed_count=len(results) - passed_count,
        results=results,
    )


def radar_interpretation_shadow_report_markdown(
    report: RadarInterpretationShadowReport,
) -> str:
    """Render a short human-readable report without provider payload contents."""

    lines = [
        "# Radar Interpretation Shadow Evaluation",
        "",
        f"- Generated at: {report.generated_at.isoformat()}",
        f"- Cases: {report.case_count}",
        f"- Accepted: {report.accepted_count}",
        f"- Rejected: {report.rejected_count}",
        f"- Expected outcome matched: {report.passed_count}/{report.case_count}",
        "",
        "| Case | Expected | Actual | Reason | Passed |",
        "| --- | --- | --- | --- | --- |",
    ]
    for result in report.results:
        expected = _expected_label(result.expected_outcome, result.expected_reason)
        actual = _expected_label(result.actual_outcome, result.actual_reason)
        lines.append(
            f"| {result.case_id} | {expected} | {actual} | "
            f"{result.actual_reason or '-'} | {'yes' if result.passed else 'no'} |"
        )
    return "\n".join(lines) + "\n"


def _evaluate_case(
    case: RadarInterpretationShadowCase,
    *,
    context,
    generated_at: datetime,
) -> RadarInterpretationShadowCaseResult:
    actual_outcome: ShadowActualOutcome
    actual_reason: str | None
    try:
        response = AssistantGatewayResponse.model_validate(case.raw_response)
    except ValidationError:
        actual_outcome = "rejected"
        actual_reason = "malformed_json"
    else:
        try:
            radar_interpretation_from_gateway_response(
                response,
                context=context,
                generated_at=generated_at,
            )
        except RadarInterpretationValidationError as exc:
            actual_outcome = "rejected"
            actual_reason = exc.reason
        else:
            actual_outcome = "accepted"
            actual_reason = None
    passed = actual_outcome == case.expected_outcome and actual_reason == case.expected_reason
    return RadarInterpretationShadowCaseResult(
        case_id=case.case_id,
        expected_outcome=case.expected_outcome,
        expected_reason=case.expected_reason,
        actual_outcome=actual_outcome,
        actual_reason=actual_reason,
        passed=passed,
    )


def _expected_label(outcome: str, reason: str | None) -> str:
    return f"{outcome}:{reason}" if reason else outcome


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
