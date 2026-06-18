from __future__ import annotations

from datetime import UTC, datetime

from pydantic import Field

from backend.assistant.action_result import ActionExecutionStatus, AssistantActionResult
from backend.assistant.context_builder import SMAIAssistantContext
from backend.assistant.tool_registry import AssistantActionSpec
from backend.core.data_contracts import StrictBaseModel


class AssistantActionAuditEntry(StrictBaseModel):
    """Minimal audit metadata for a user-confirmed Assistant action."""

    action_id: str = Field(min_length=1)
    action_type: str = Field(min_length=1)
    requested_by: str = "user"
    confirmed: bool
    status: ActionExecutionStatus
    page_context: str | None = Field(default=None, min_length=1)
    symbol: str | None = Field(default=None, min_length=1)
    started_at: datetime
    completed_at: datetime | None = None
    error_code: str | None = Field(default=None, min_length=1)


def build_assistant_action_audit_entry(
    *,
    result: AssistantActionResult,
    action: AssistantActionSpec | None,
    context: SMAIAssistantContext,
    confirmed: bool,
) -> AssistantActionAuditEntry:
    started_at = result.started_at or datetime.now(UTC)
    return AssistantActionAuditEntry(
        action_id=result.action_id,
        action_type=action.action_type if action is not None else "unknown",
        confirmed=confirmed,
        status=result.status,
        page_context=context.current_page,
        symbol=_result_symbol(result),
        started_at=started_at,
        completed_at=result.completed_at,
        error_code=result.error_code,
    )


def _result_symbol(result: AssistantActionResult) -> str | None:
    symbol = str(result.details.get("symbol", "") or "").strip()
    return symbol or None
