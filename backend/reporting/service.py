from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Literal, Mapping, Sequence

from pydantic import Field

from backend.core.data_contracts import StrictBaseModel
from backend.core.errors import ValidationAppError

DECISION_REPORT_SCHEMA_VERSION = "decision-report-context-v1"
DECISION_SUPPORT_NOTE = (
    "This report is decision-support material only and is not a buy/sell recommendation."
)

ReportSourceKind = Literal["cockpit", "ranking", "rebalance", "metadata", "manual"]


class DecisionReportSource(StrictBaseModel):
    """Origin metadata for a reusable decision-report section."""

    kind: ReportSourceKind
    provider: str | None = Field(default=None, min_length=1)
    symbol: str | None = Field(default=None, min_length=1)
    as_of: date | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class DecisionReportSection(StrictBaseModel):
    """One reusable block of existing UI/API output for a future report."""

    title: str = Field(min_length=1)
    source: DecisionReportSource
    summary: dict[str, str] = Field(default_factory=dict)
    rows: list[dict[str, str]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class DecisionReportContext(StrictBaseModel):
    """Local-first report context shared by API, UI, export, and future assistants."""

    schema_version: str = DECISION_REPORT_SCHEMA_VERSION
    title: str = Field(min_length=1)
    created_at: datetime
    sections: list[DecisionReportSection] = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    decision_support_note: str = DECISION_SUPPORT_NOTE


class DecisionReportManifest(StrictBaseModel):
    """Small export manifest for local Decision Report artifacts."""

    schema_version: str = DECISION_REPORT_SCHEMA_VERSION
    created_at: datetime
    title: str
    section_count: int = Field(ge=1)
    sources: list[str]
    files: list[dict[str, str]]
    decision_support_note: str = DECISION_SUPPORT_NOTE


def build_report_section(
    *,
    title: str,
    source_kind: ReportSourceKind,
    provider: str | None = None,
    symbol: str | None = None,
    as_of: date | None = None,
    summary: Mapping[str, object] | None = None,
    rows: Sequence[Mapping[str, object]] | None = None,
    warnings: list[str] | None = None,
    notes: list[str] | None = None,
    metadata: dict[str, str] | None = None,
) -> DecisionReportSection:
    """Build a report section from existing table-like UI/API outputs."""

    normalized_summary = _normalize_mapping(summary or {})
    normalized_rows = [_normalize_mapping(row) for row in rows or []]
    normalized_warnings = _normalize_strings(warnings or [])
    normalized_notes = _normalize_strings(notes or [])
    if not (normalized_summary or normalized_rows or normalized_warnings or normalized_notes):
        raise ValidationAppError(
            "Decision report section must include summary, rows, warnings, or notes.",
            details={"title": title, "source_kind": source_kind},
        )

    return DecisionReportSection(
        title=title.strip(),
        source=DecisionReportSource(
            kind=source_kind,
            provider=provider.strip() if provider else None,
            symbol=symbol.strip() if symbol else None,
            as_of=as_of,
            metadata=_normalize_mapping(metadata or {}),
        ),
        summary=normalized_summary,
        rows=normalized_rows,
        warnings=normalized_warnings,
        notes=normalized_notes,
    )


def build_decision_report_context(
    *,
    title: str,
    sections: list[DecisionReportSection],
    created_at: datetime | None = None,
    tags: list[str] | None = None,
) -> DecisionReportContext:
    """Create the reusable context object for a deterministic Decision Report."""

    if not sections:
        raise ValidationAppError("Decision report context requires at least one section.")
    timestamp = created_at or datetime.now(UTC)
    return DecisionReportContext(
        title=title.strip(),
        created_at=timestamp,
        sections=sections,
        tags=_normalize_strings(tags or []),
    )


def build_data_confidence_section(
    *,
    provider: str | None = None,
    symbol: str | None = None,
    as_of: date | None = None,
    price_period: str | None = None,
    data_quality: str | None = None,
    metadata_source: str | None = None,
    metadata_as_of: str | None = None,
    missing_fields: list[str] | None = None,
    coverage_rows: Sequence[Mapping[str, object]] | None = None,
    warnings: list[str] | None = None,
    notes: list[str] | None = None,
) -> DecisionReportSection:
    """Build the standard report section for data availability and confidence."""

    summary: dict[str, object] = {
        "provider": provider,
        "price_period": price_period,
        "data_quality": data_quality,
        "metadata_source": metadata_source,
        "metadata_as_of": metadata_as_of,
    }
    normalized_missing = _normalize_strings(missing_fields or [])
    normalized_warnings = _normalize_strings(warnings or [])
    if normalized_missing:
        summary["missing_fields"] = ", ".join(normalized_missing)
        normalized_warnings.append(
            "Some metadata fields are blank and should be reviewed as data gaps, not zero values."
        )
    normalized_notes = _normalize_strings(notes or [])
    normalized_notes.append(
        "Unconfirmed metadata remains blank until a verified source or explicit opt-in refresh provides it."
    )

    return build_report_section(
        title="Data coverage and confidence",
        source_kind="metadata",
        provider=provider,
        symbol=symbol,
        as_of=as_of,
        summary=summary,
        rows=[_normalize_mapping(row) for row in coverage_rows or []],
        warnings=normalized_warnings,
        notes=normalized_notes,
    )


def build_symbol_metadata_section(
    *,
    symbol: str,
    name: str | None = None,
    as_of: date | None = None,
    metadata: Mapping[str, object] | None = None,
    warnings: list[str] | None = None,
    notes: list[str] | None = None,
) -> DecisionReportSection:
    """Build the standard report section for local symbol-master attributes."""

    summary: dict[str, object] = {"symbol": symbol, "name": name}
    summary.update(metadata or {})
    return build_report_section(
        title="Symbol metadata",
        source_kind="metadata",
        symbol=symbol,
        as_of=as_of,
        summary=summary,
        warnings=warnings,
        notes=notes,
    )


def build_decision_checkpoints_section(
    *,
    checkpoints: Sequence[Mapping[str, object]],
    symbol: str | None = None,
    as_of: date | None = None,
    notes: list[str] | None = None,
) -> DecisionReportSection:
    """Build the standard section for next checks without turning them into advice."""

    if not checkpoints:
        raise ValidationAppError("Decision checkpoints require at least one row.")
    normalized_notes = _normalize_strings(notes or [])
    normalized_notes.append(
        "These checkpoints organize review work and are not buy/sell instructions."
    )
    return build_report_section(
        title="Decision checkpoints",
        source_kind="manual",
        symbol=symbol,
        as_of=as_of,
        rows=[_normalize_mapping(row) for row in checkpoints],
        notes=normalized_notes,
    )


def render_decision_report_markdown(context: DecisionReportContext) -> str:
    """Render a deterministic Markdown report from a Decision Report context."""

    lines = [
        f"# {context.title}",
        "",
        f"- Schema: {context.schema_version}",
        f"- Created at: {context.created_at.isoformat()}",
        f"- Note: {context.decision_support_note}",
    ]
    if context.tags:
        lines.append(f"- Tags: {', '.join(context.tags)}")

    for section in context.sections:
        lines.extend(["", f"## {section.title}", ""])
        lines.append(f"- Source: {section.source.kind}")
        if section.source.provider:
            lines.append(f"- Provider: {section.source.provider}")
        if section.source.symbol:
            lines.append(f"- Symbol: {section.source.symbol}")
        if section.source.as_of:
            lines.append(f"- As of: {section.source.as_of.isoformat()}")
        for key, value in section.source.metadata.items():
            lines.append(f"- {key}: {value}")
        if section.summary:
            lines.extend(["", "### Summary"])
            lines.extend(f"- {key}: {value}" for key, value in section.summary.items())
        if section.rows:
            lines.extend(["", "### Rows"])
            lines.extend(_markdown_table(section.rows))
        if section.warnings:
            lines.extend(["", "### Warnings"])
            lines.extend(f"- {warning}" for warning in section.warnings)
        if section.notes:
            lines.extend(["", "### Notes"])
            lines.extend(f"- {note}" for note in section.notes)

    return "\n".join(lines) + "\n"


def build_decision_report_manifest(context: DecisionReportContext) -> DecisionReportManifest:
    """Describe local export files that can be produced from the report context."""

    return DecisionReportManifest(
        created_at=context.created_at,
        title=context.title,
        section_count=len(context.sections),
        sources=[section.source.kind for section in context.sections],
        files=[
            {
                "filename": "decision_report_context.json",
                "description": "Structured context used to render the Decision Report.",
            },
            {
                "filename": "decision_report.md",
                "description": "Deterministic Markdown report rendered from local context.",
            },
        ],
    )


def _normalize_mapping(values: Mapping[str, object]) -> dict[str, str]:
    return {
        str(key).strip(): str(value).strip()
        for key, value in values.items()
        if str(key).strip() and value is not None and str(value).strip()
    }


def _normalize_strings(values: list[str]) -> list[str]:
    return [value.strip() for value in values if value.strip()]


def _markdown_table(rows: list[dict[str, str]]) -> list[str]:
    headers: list[str] = []
    for row in rows:
        for key in row:
            if key not in headers:
                headers.append(key)

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        values = [_escape_table_cell(row.get(header, "")) for header in headers]
        lines.append("| " + " | ".join(values) + " |")
    return lines


def _escape_table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
