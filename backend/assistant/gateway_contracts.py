from __future__ import annotations

from datetime import datetime
from typing import Literal, Mapping, Sequence
from uuid import uuid4

from pydantic import Field

from backend.core.data_contracts import StrictBaseModel
from backend.reporting import (
    DECISION_SUPPORT_NOTE,
    DecisionReportContext,
    DecisionReportSection,
)

ASSISTANT_CONTEXT_BUNDLE_SCHEMA_VERSION = "assistant-context-bundle-v1"
ASSISTANT_GATEWAY_REQUEST_SCHEMA_VERSION = "assistant-gateway-request-v1"
ASSISTANT_GATEWAY_RESPONSE_SCHEMA_VERSION = "assistant-gateway-response-v1"
ASSISTANT_GATEWAY_RADAR_INTERPRETATION_SCHEMA_VERSION = "radar_interpretation.v1"
ASSISTANT_PLANNER_REQUEST_SCHEMA_VERSION = "assistant_tool_planner_request.v1"
ASSISTANT_PLANNER_RESPONSE_SCHEMA_VERSION = "assistant_tool_planner_response.v1"
ASSISTANT_PLANNER_PROMPT_VERSION = "assistant_tool_planner_mvp.v1"

AssistantGatewayTask = Literal["explain", "summarize", "compare", "next_steps", "chat"]
AssistantGatewayLanguage = Literal["ja", "en"]
AssistantGatewayConfidence = Literal["low", "medium", "high"]
AssistantGatewayAnswerFormat = Literal["materials_cautions_checkpoints"]
AssistantGatewayStatus = Literal["ok", "fallback", "error"]
AssistantPlannerActionType = Literal[
    "navigation", "state_change", "data_fetch", "report", "explain"
]
AssistantPlannerPlanType = Literal["tool_plan", "guided_workflow"]
AssistantPlannerPriority = Literal["high", "medium", "low"]
AssistantPlannerSource = Literal["llm", "fallback"]
AssistantGatewayTaskType = Literal[
    "free_chat",
    "identity",
    "app_help",
    "capability_help",
    "screen_guidance",
    "stock_summary",
    "forecast_risk_compare",
    "news_materials",
    "rag_summary",
    "decision_report_draft",
    "llm_factor_generation",
    "cockpit_interpretation",
    "report_export_summary",
    "assistant_tool_plan",
]
AssistantGatewayExecutionMode = Literal["auto", "light", "quality", "off"]
AssistantGatewayEnvironmentProfile = Literal["notebook", "desktop", "server", "offline"]
AssistantGatewayProfileName = Literal[
    "notebook_dev",
    "notebook_standard",
    "desktop_fast",
    "desktop_analysis",
    "desktop_heavy",
    "assistant_fast",
    "assistant_standard",
    "assistant_quality",
    "report_quality",
    "fallback",
]

_DEFAULT_CONTEXT_PRIVACY_NOTES = (
    "Provider raw fields, debug logs, and full external source bodies are excluded.",
    "The bundle is for explanation and confirmation support, not score or ranking recomputation.",
)
_REDACTED_KEY_TERMS = (
    "provider_raw",
    "raw_payload",
    "raw_text",
    "full_text",
    "source_text",
    "body_html",
    "html",
    "payload",
    "debug",
    "traceback",
    "log",
    "本文全文",
)


class AssistantContextSection(StrictBaseModel):
    """Safe, compact section context that can be sent to an external LLM Gateway."""

    section_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_kind: str = Field(min_length=1)
    provider: str | None = Field(default=None, min_length=1)
    symbol: str | None = Field(default=None, min_length=1)
    summary: dict[str, str] = Field(default_factory=dict)
    rows: list[dict[str, str]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    included_fields: list[str] = Field(default_factory=list)
    redacted_fields: list[str] = Field(default_factory=list)


class AssistantContextBundle(StrictBaseModel):
    """Shared context for floating Copilot, future chat UI, and Gateway requests."""

    schema_version: str = ASSISTANT_CONTEXT_BUNDLE_SCHEMA_VERSION
    bundle_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source: Literal["decision_report", "streamlit_context", "manual"] = "decision_report"
    created_at: datetime
    language: AssistantGatewayLanguage = "ja"
    active_context_id: str | None = Field(default=None, min_length=1)
    sections: list[AssistantContextSection] = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    privacy_notes: list[str] = Field(default_factory=lambda: list(_DEFAULT_CONTEXT_PRIVACY_NOTES))
    decision_support_note: str = DECISION_SUPPORT_NOTE


class AssistantGatewayConstraints(StrictBaseModel):
    """Safety and output constraints SMAI sends with every external Gateway request."""

    no_investment_advice: bool = True
    do_not_change_scores: bool = True
    do_not_rank_symbols: bool = True
    answer_format: AssistantGatewayAnswerFormat = "materials_cautions_checkpoints"
    require_referenced_sections: bool = True


class AssistantGatewayMessage(StrictBaseModel):
    """Optional future chat history item."""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class AssistantGatewayRequest(StrictBaseModel):
    """External LLM Gateway request contract kept independent from provider details."""

    schema_version: str = ASSISTANT_GATEWAY_REQUEST_SCHEMA_VERSION
    task: AssistantGatewayTask = "explain"
    language: AssistantGatewayLanguage = "ja"
    user_question: str = Field(min_length=1)
    context: AssistantContextBundle
    constraints: AssistantGatewayConstraints = Field(default_factory=AssistantGatewayConstraints)
    conversation_id: str | None = Field(default=None, min_length=1)
    message_history: list[AssistantGatewayMessage] = Field(default_factory=list)
    active_context_id: str | None = Field(default=None, min_length=1)
    referenced_context_ids: list[str] = Field(default_factory=list)
    response_schema: str | None = Field(default=None, min_length=1)
    task_type: AssistantGatewayTaskType = "free_chat"
    execution_mode: AssistantGatewayExecutionMode = "auto"
    environment_profile: AssistantGatewayEnvironmentProfile = "notebook"
    preferred_profile: AssistantGatewayProfileName | None = None
    request_id: str = Field(default_factory=lambda: uuid4().hex, min_length=1)


class AssistantGatewayReferencedSection(StrictBaseModel):
    """Gateway response reference back to a section from AssistantContextBundle."""

    section_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_kind: str = Field(min_length=1)


class AssistantGatewayEvidencePoint(StrictBaseModel):
    """One short response field tied to exact client-provided evidence IDs."""

    text: str = Field(min_length=1, max_length=320)
    cited_evidence_ids: list[str] = Field(min_length=1, max_length=5)


class AssistantGatewayRadarInterpretation(StrictBaseModel):
    """Evidence-bound payload used only for the optional Investment Radar memo."""

    schema_version: str = Field(
        default=ASSISTANT_GATEWAY_RADAR_INTERPRETATION_SCHEMA_VERSION,
        min_length=1,
    )
    candidate_id: str = Field(min_length=1)
    summary: AssistantGatewayEvidencePoint
    positive_materials: list[AssistantGatewayEvidencePoint] = Field(
        default_factory=list, max_length=4
    )
    cautions: list[AssistantGatewayEvidencePoint] = Field(default_factory=list, max_length=4)
    unknowns: list[AssistantGatewayEvidencePoint] = Field(default_factory=list, max_length=4)
    next_checkpoints: list[AssistantGatewayEvidencePoint] = Field(
        default_factory=list, max_length=4
    )


class AssistantGatewayResponse(StrictBaseModel):
    """SMAI-facing response shape expected from the external LLM Gateway."""

    schema_version: str = ASSISTANT_GATEWAY_RESPONSE_SCHEMA_VERSION
    answer: str = Field(min_length=1)
    materials: list[str] = Field(default_factory=list)
    cautions: list[str] = Field(default_factory=list)
    next_checkpoints: list[str] = Field(default_factory=list)
    referenced_sections: list[AssistantGatewayReferencedSection] = Field(default_factory=list)
    radar_interpretation: AssistantGatewayRadarInterpretation | None = None
    confidence: AssistantGatewayConfidence = "low"
    safety_notes: list[str] = Field(default_factory=list)
    provider: str | None = Field(default=None, min_length=1)
    model: str | None = Field(default=None, min_length=1)
    profile: AssistantGatewayProfileName | None = None
    elapsed_ms: int | None = Field(default=None, ge=0)
    gateway_status: AssistantGatewayStatus = "ok"
    fallback_reason: str | None = Field(default=None, min_length=1)
    request_id: str | None = Field(default=None, min_length=1)
    timeout_sec: float | None = Field(default=None, ge=0)
    context_tokens_estimate: int | None = Field(default=None, ge=0)
    prompt_chars: int | None = Field(default=None, ge=0)
    response_chars: int | None = Field(default=None, ge=0)
    tool_execution_ms: int | None = Field(default=None, ge=0)
    llm_generation_ms: int | None = Field(default=None, ge=0)
    total_elapsed_ms: int | None = Field(default=None, ge=0)
    decision_support_note: str = DECISION_SUPPORT_NOTE


class PlannerAvailableAction(StrictBaseModel):
    """Action metadata the parent SMAI app allows the Gateway planner to reference."""

    action_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    description: str = Field(min_length=1)
    action_type: AssistantPlannerActionType
    requires_confirmation: bool = True
    is_external_fetch: bool = False
    enabled: bool = True
    disabled_reason: str | None = Field(default=None, min_length=1)


class AssistantPlannerConstraints(StrictBaseModel):
    """Planner-specific safety constraints sent to the Gateway."""

    no_investment_advice: bool = True
    no_auto_execution: bool = True
    do_not_change_scores: bool = True
    do_not_rank_symbols: bool = True
    require_confirmation_for_external_fetch: bool = True
    max_steps: int = Field(default=5, gt=0, le=6)
    allowed_action_ids: list[str] = Field(default_factory=list)


class AssistantPlannerRequest(StrictBaseModel):
    """Request contract for optional LLM-generated action plans."""

    schema_version: str = ASSISTANT_PLANNER_REQUEST_SCHEMA_VERSION
    prompt_version: str = ASSISTANT_PLANNER_PROMPT_VERSION
    task_type: Literal["assistant_tool_plan"] = "assistant_tool_plan"
    language: AssistantGatewayLanguage = "ja"
    user_question: str = Field(min_length=1)
    current_page: str = Field(min_length=1)
    context_summary: str = Field(min_length=1)
    material_state: dict[str, str] = Field(default_factory=dict)
    available_actions: list[PlannerAvailableAction] = Field(default_factory=list)
    constraints: AssistantPlannerConstraints = Field(default_factory=AssistantPlannerConstraints)
    request_id: str = Field(default_factory=lambda: uuid4().hex, min_length=1)
    model: str | None = Field(default=None, min_length=1)
    profile: AssistantGatewayProfileName | None = None
    execution_mode: AssistantGatewayExecutionMode = "auto"
    environment_profile: AssistantGatewayEnvironmentProfile = "notebook"
    preferred_profile: AssistantGatewayProfileName | None = None


class AssistantPlannerStep(StrictBaseModel):
    """One proposed planner step from the Gateway."""

    step_id: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=80)
    summary: str = Field(min_length=1, max_length=240)
    action_id: str | None = Field(default=None, min_length=1)
    reason: str = Field(min_length=1, max_length=240)
    requires_confirmation: bool = True
    confidence: float = Field(default=0.5, ge=0, le=1)
    priority: AssistantPlannerPriority = "medium"


class AssistantPlannerResponse(StrictBaseModel):
    """Gateway response contract for optional LLM-generated plans."""

    schema_version: str = ASSISTANT_PLANNER_RESPONSE_SCHEMA_VERSION
    plan_type: AssistantPlannerPlanType = "tool_plan"
    user_intent: str = Field(min_length=1)
    overall_summary: str = Field(min_length=1, max_length=320)
    steps: list[AssistantPlannerStep] = Field(default_factory=list, max_length=6)
    safety_note: str = Field(
        default="この提案は確認手順の整理であり、売買推奨ではありません。",
        min_length=1,
    )
    planner_source: AssistantPlannerSource = "llm"
    provider: str | None = Field(default=None, min_length=1)
    model: str | None = Field(default=None, min_length=1)
    profile: AssistantGatewayProfileName | None = None
    elapsed_ms: int | None = Field(default=None, ge=0)
    gateway_status: AssistantGatewayStatus = "ok"
    fallback_reason: str | None = Field(default=None, min_length=1)
    request_id: str | None = Field(default=None, min_length=1)
    timeout_sec: float | None = Field(default=None, ge=0)
    prompt_chars: int | None = Field(default=None, ge=0)
    response_chars: int | None = Field(default=None, ge=0)
    llm_generation_ms: int | None = Field(default=None, ge=0)
    total_elapsed_ms: int | None = Field(default=None, ge=0)


def build_assistant_context_bundle(
    report_context: DecisionReportContext,
    *,
    bundle_id: str | None = None,
    active_context_id: str | None = None,
    language: AssistantGatewayLanguage = "ja",
    max_sections: int = 8,
    max_rows_per_section: int = 8,
    max_text_chars: int = 320,
) -> AssistantContextBundle:
    """Convert DecisionReportContext into a compact, safe Gateway context bundle."""

    selected_sections = report_context.sections[:max_sections]
    privacy_notes = list(_DEFAULT_CONTEXT_PRIVACY_NOTES)
    if len(report_context.sections) > len(selected_sections):
        omitted = len(report_context.sections) - len(selected_sections)
        privacy_notes.append(f"{omitted} section(s) were omitted by max_sections.")

    return AssistantContextBundle(
        bundle_id=bundle_id or _bundle_id_from_context(report_context),
        title=_trim_text(report_context.title, max_text_chars),
        created_at=report_context.created_at,
        language=language,
        active_context_id=active_context_id,
        sections=[
            _context_section_from_report_section(
                section,
                index=index,
                max_rows=max_rows_per_section,
                max_text_chars=max_text_chars,
            )
            for index, section in enumerate(selected_sections)
        ],
        tags=[_trim_text(tag, max_text_chars) for tag in report_context.tags if tag.strip()],
        privacy_notes=privacy_notes,
    )


def build_assistant_gateway_request(
    *,
    question: str,
    context: AssistantContextBundle,
    task: AssistantGatewayTask = "explain",
    language: AssistantGatewayLanguage = "ja",
    conversation_id: str | None = None,
    message_history: Sequence[AssistantGatewayMessage] = (),
    active_context_id: str | None = None,
    referenced_context_ids: Sequence[str] = (),
    response_schema: str | None = None,
    task_type: AssistantGatewayTaskType = "free_chat",
    execution_mode: AssistantGatewayExecutionMode = "auto",
    environment_profile: AssistantGatewayEnvironmentProfile = "notebook",
    preferred_profile: AssistantGatewayProfileName | None = None,
) -> AssistantGatewayRequest:
    """Build the network-free request object SMAI will later send to the Gateway."""

    return AssistantGatewayRequest(
        task=task,
        language=language,
        user_question=question.strip(),
        context=context,
        conversation_id=conversation_id,
        message_history=list(message_history),
        active_context_id=active_context_id or context.active_context_id,
        referenced_context_ids=list(referenced_context_ids),
        response_schema=response_schema,
        task_type=task_type,
        execution_mode=execution_mode,
        environment_profile=environment_profile,
        preferred_profile=preferred_profile,
    )


def _context_section_from_report_section(
    section: DecisionReportSection,
    *,
    index: int,
    max_rows: int,
    max_text_chars: int,
) -> AssistantContextSection:
    summary, redacted_summary = _safe_mapping(section.summary, max_text_chars=max_text_chars)
    rows: list[dict[str, str]] = []
    redacted_fields: list[str] = list(redacted_summary)
    for row in section.rows[:max_rows]:
        safe_row, redacted_row = _safe_mapping(row, max_text_chars=max_text_chars)
        if safe_row:
            rows.append(safe_row)
        redacted_fields.extend(redacted_row)
    if len(section.rows) > max_rows:
        redacted_fields.append("rows.omitted_by_limit")
    if section.source.metadata:
        redacted_fields.append("source.metadata")

    warnings = _safe_strings(section.warnings, max_text_chars=max_text_chars)
    notes = _safe_strings(section.notes, max_text_chars=max_text_chars)
    included_fields = _included_fields(summary, rows, warnings=warnings, notes=notes)

    return AssistantContextSection(
        section_id=f"{section.source.kind}-{index + 1}",
        title=_trim_text(section.title, max_text_chars),
        source_kind=section.source.kind,
        provider=(
            _trim_text(section.source.provider, max_text_chars) if section.source.provider else None
        ),
        symbol=(
            _trim_text(section.source.symbol, max_text_chars) if section.source.symbol else None
        ),
        summary=summary,
        rows=rows,
        warnings=warnings,
        notes=notes,
        included_fields=included_fields,
        redacted_fields=_dedupe(redacted_fields),
    )


def _safe_mapping(
    values: Mapping[str, str],
    *,
    max_text_chars: int,
) -> tuple[dict[str, str], list[str]]:
    safe: dict[str, str] = {}
    redacted: list[str] = []
    for key, value in values.items():
        normalized_key = str(key).strip()
        if not normalized_key:
            continue
        if _should_redact_key(normalized_key):
            redacted.append(normalized_key)
            continue
        normalized_value = _trim_text(value, max_text_chars)
        if normalized_value:
            safe[normalized_key] = normalized_value
    return safe, redacted


def _safe_strings(values: Sequence[str], *, max_text_chars: int) -> list[str]:
    return [
        _trim_text(value, max_text_chars) for value in values if _trim_text(value, max_text_chars)
    ]


def _included_fields(
    summary: Mapping[str, str],
    rows: Sequence[Mapping[str, str]],
    *,
    warnings: Sequence[str],
    notes: Sequence[str],
) -> list[str]:
    fields = list(summary.keys())
    for row in rows:
        fields.extend(row.keys())
    if warnings:
        fields.append("warnings")
    if notes:
        fields.append("notes")
    return _dedupe(fields)


def _should_redact_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_").replace(" ", "_")
    return any(term in normalized for term in _REDACTED_KEY_TERMS)


def _trim_text(value: object, max_chars: int) -> str:
    text = str(value).strip()
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars].rstrip()}..."


def _bundle_id_from_context(report_context: DecisionReportContext) -> str:
    timestamp = report_context.created_at.strftime("%Y%m%d%H%M%S")
    return f"decision-report-{timestamp}"


def _dedupe(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result
