from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from backend.reporting.service import (
    DECISION_SUPPORT_NOTE,
    DecisionReportContext,
    render_decision_report_markdown,
)

ASSISTANT_DECISION_REPORT_ARCHIVE_SCHEMA_VERSION = "assistant-decision-report-archive-v1"
ASSISTANT_DECISION_REPORT_ARCHIVE_MANIFEST = "assistant_decision_report_manifest.json"

_ARCHIVE_TECHNICAL_MARKERS = (
    "provider raw",
    "debug logs",
    "raw exception",
    "stack trace",
    "request_id",
    "latency",
    "gateway_url",
    "internal metadata",
    "llm内部思考",
)


@dataclass(frozen=True)
class AssistantDecisionReportArchiveResult:
    """Files created when an Assistant Decision Report draft is archived."""

    draft_id: str
    markdown_path: Path
    manifest_path: Path
    zip_path: Path | None
    manifest_updated: bool
    manifest_error: str | None
    entry: dict[str, object]


def archive_assistant_decision_report_draft(
    context: DecisionReportContext,
    output_dir: Path,
    *,
    markdown: str | None = None,
    include_zip: bool = True,
    archived_at: datetime | None = None,
) -> AssistantDecisionReportArchiveResult:
    """Persist a sanitized Assistant Decision Report draft and update its manifest."""

    output_dir.mkdir(parents=True, exist_ok=True)
    clean_markdown = sanitize_assistant_decision_report_markdown(
        markdown or render_decision_report_markdown(context)
    )
    archive_time = archived_at or datetime.now(UTC)
    stem = _unique_archive_stem(context, clean_markdown, output_dir)
    markdown_path = output_dir / f"{stem}.md"
    zip_path = output_dir / f"{stem}.zip" if include_zip else None
    entry = _archive_entry(
        context,
        markdown=clean_markdown,
        archived_at=archive_time,
        markdown_filename=markdown_path.name,
        zip_filename=zip_path.name if zip_path is not None else None,
        draft_id=f"adr_{stem}",
    )

    markdown_path.write_text(clean_markdown, encoding="utf-8")
    if zip_path is not None:
        zip_path.write_bytes(assistant_decision_report_zip_download(clean_markdown, entry))

    manifest_path = output_dir / ASSISTANT_DECISION_REPORT_ARCHIVE_MANIFEST
    manifest_updated = True
    manifest_error: str | None = None
    try:
        _append_archive_manifest(manifest_path, entry)
    except OSError as exc:
        manifest_updated = False
        manifest_error = exc.__class__.__name__

    return AssistantDecisionReportArchiveResult(
        draft_id=str(entry["draft_id"]),
        markdown_path=markdown_path,
        manifest_path=manifest_path,
        zip_path=zip_path,
        manifest_updated=manifest_updated,
        manifest_error=manifest_error,
        entry=entry,
    )


def build_assistant_decision_report_archive_entry(
    context: DecisionReportContext,
    *,
    markdown: str,
    markdown_filename: str = "report.md",
    zip_filename: str | None = None,
    draft_id: str | None = None,
    archived_at: datetime | None = None,
) -> dict[str, object]:
    """Build a sanitized manifest entry for an Assistant draft archive/download."""

    clean_markdown = sanitize_assistant_decision_report_markdown(markdown)
    resolved_draft_id = (
        draft_id or f"adr_preview_{hashlib.sha256(clean_markdown.encode('utf-8')).hexdigest()[:6]}"
    )
    return _archive_entry(
        context,
        markdown=clean_markdown,
        archived_at=archived_at or datetime.now(UTC),
        markdown_filename=markdown_filename,
        zip_filename=zip_filename,
        draft_id=resolved_draft_id,
    )


def assistant_decision_report_zip_download(
    markdown: str, manifest_entry: dict[str, object]
) -> bytes:
    """Return an Assistant draft ZIP containing only the readable memo and manifest."""

    buffer = BytesIO()
    with ZipFile(buffer, mode="w") as archive:
        files = {
            "manifest.json": json.dumps(manifest_entry, ensure_ascii=False, indent=2) + "\n",
            "report.md": sanitize_assistant_decision_report_markdown(markdown),
        }
        for filename, payload in sorted(files.items()):
            info = ZipInfo(filename, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, payload.encode("utf-8"))
    return buffer.getvalue()


def sanitize_assistant_decision_report_markdown(markdown: str) -> str:
    """Remove raw provider/debug lines from archived Assistant report Markdown."""

    lines: list[str] = []
    for line in str(markdown or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        lowered = line.lower()
        if any(marker in lowered for marker in _ARCHIVE_TECHNICAL_MARKERS):
            continue
        lines.append(line.rstrip())
    clean = "\n".join(lines).strip()
    return f"{clean}\n" if clean else "# Decision Report Draft\n\n保存できる本文がありません。\n"


def _archive_entry(
    context: DecisionReportContext,
    *,
    markdown: str,
    archived_at: datetime,
    markdown_filename: str,
    zip_filename: str | None,
    draft_id: str,
) -> dict[str, object]:
    overview = _overview_summary(context)
    cached_only = _cached_only(overview)
    return {
        "schema_version": ASSISTANT_DECISION_REPORT_ARCHIVE_SCHEMA_VERSION,
        "draft_id": draft_id,
        "created_at": context.created_at.isoformat(),
        "archived_at": archived_at.isoformat(),
        "source": overview.get("source") or _source_provider(context),
        "intent": overview.get("intent") or "",
        "symbol": _symbol(context),
        "company_name": overview.get("company_name") or "",
        "title": context.title,
        "file": markdown_filename,
        "zip_file": zip_filename or "",
        "cached_only": cached_only,
        "fetch_mode": overview.get("fetch_mode") or ("cached_only" if cached_only else "approve"),
        "tool_status": _tool_status(context, cached_only=cached_only),
        "source_count": _source_count(context),
        "freshness_warnings": _freshness_warnings(context),
        "markdown_sha256": hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
        "decision_support_note": DECISION_SUPPORT_NOTE,
    }


def _append_archive_manifest(path: Path, entry: dict[str, object]) -> None:
    manifest = _read_archive_manifest(path)
    raw_reports = manifest.get("reports", [])
    reports = list(raw_reports) if isinstance(raw_reports, list) else []
    reports.append(entry)
    payload = {
        "schema_version": ASSISTANT_DECISION_REPORT_ARCHIVE_SCHEMA_VERSION,
        "updated_at": datetime.now(UTC).isoformat(),
        "reports": reports,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_archive_manifest(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"schema_version": ASSISTANT_DECISION_REPORT_ARCHIVE_SCHEMA_VERSION, "reports": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"schema_version": ASSISTANT_DECISION_REPORT_ARCHIVE_SCHEMA_VERSION, "reports": []}
    if not isinstance(payload, dict):
        return {"schema_version": ASSISTANT_DECISION_REPORT_ARCHIVE_SCHEMA_VERSION, "reports": []}
    reports = payload.get("reports", [])
    if not isinstance(reports, list):
        payload["reports"] = []
    return payload


def _unique_archive_stem(
    context: DecisionReportContext,
    markdown: str,
    output_dir: Path,
) -> str:
    timestamp = context.created_at.strftime("%Y%m%d_%H%M%S")
    slug = _archive_slug(_symbol(context) or context.title)
    digest = hashlib.sha256(
        f"{context.title}\n{context.created_at.isoformat()}\n{markdown}".encode("utf-8")
    ).hexdigest()[:6]
    base = f"{timestamp}_assistant_decision_report_{slug}_{digest}"
    candidate = base
    suffix = 1
    while (output_dir / f"{candidate}.md").exists() or (output_dir / f"{candidate}.zip").exists():
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


def _archive_slug(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9]+", "", str(value or "").strip())
    return clean[:32] or "topic"


def _overview_summary(context: DecisionReportContext) -> dict[str, str]:
    for section in context.sections:
        if section.summary.get("source") == "assistant_research_mode":
            return section.summary
        if section.source.provider == "assistant_research_mode":
            return section.summary
    return context.sections[0].summary if context.sections else {}


def _source_provider(context: DecisionReportContext) -> str:
    for section in context.sections:
        if section.source.provider:
            return section.source.provider
    return "assistant_decision_report"


def _symbol(context: DecisionReportContext) -> str:
    return next(
        (section.source.symbol or "" for section in context.sections if section.source.symbol), ""
    )


def _cached_only(summary: dict[str, str]) -> bool:
    return (
        str(summary.get("cached_only", "")).lower() == "true"
        or summary.get("fetch_mode") == "cached_only"
    )


def _tool_status(context: DecisionReportContext, *, cached_only: bool) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for section in context.sections:
        for row in section.rows:
            key = str(row.get("key") or row.get("tool") or "").strip()
            if not key:
                continue
            raw_status = str(row.get("status", "")).strip()
            external = str(row.get("external", "")).lower() == "true"
            statuses[key] = _archive_tool_status(raw_status, cached_only=cached_only and external)
    return statuses


def _archive_tool_status(status: str, *, cached_only: bool) -> str:
    if cached_only:
        return "skipped"
    if status == "confirmed":
        return "success"
    if status == "failed":
        return "failed"
    if status == "missing":
        return "missing"
    if status == "ok":
        return "success"
    return status or "unknown"


def _source_count(context: DecisionReportContext) -> int:
    return sum(
        1
        for section in context.sections
        for row in section.rows
        if str(row.get("row_type", "")).strip() == "source"
    )


def _freshness_warnings(context: DecisionReportContext) -> list[str]:
    warnings: list[str] = []
    for section in context.sections:
        for warning in section.warnings:
            lowered = warning.lower()
            if "freshness" in lowered or "鮮度" in warning or "古い" in warning:
                warnings.append(warning)
    return list(dict.fromkeys(warnings))
