from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from backend.core.data_contracts import StrictBaseModel

ActionExecutionStatus = Literal[
    "success",
    "failed",
    "skipped",
    "partial_success",
    "not_available",
    "cancelled",
    "validation_error",
]


class AssistantActionResult(StrictBaseModel):
    """User-safe result returned after an Assistant action execution attempt."""

    action_id: str = Field(min_length=1)
    status: ActionExecutionStatus
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    user_message: str = Field(min_length=1)
    details: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    error_code: str | None = Field(default=None, min_length=1)
    error_message: str | None = Field(default=None, min_length=1)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    requires_followup: bool = False
    followup_actions: list[str] = Field(default_factory=list)


def safe_action_error_message(error_code: str | None) -> str:
    code = str(error_code or "").strip()
    messages = {
        "confirmation_required": "実行前確認が完了していないため、操作は実行していません。",
        "unknown_action": "この操作は現在のSMAIアシスタントでは利用できません。",
        "disabled_action": "この操作は現在の画面では利用できません。",
        "destructive_action": "安全のため、この操作はSMAIアシスタントから実行できません。",
        "symbol_missing": "対象銘柄が特定できません。先に銘柄コックピットで銘柄を選んでください。",
        "insufficient_materials": "価格やAI予測など、確認レポートに必要な材料が不足しています。",
        "report_builder_unavailable": "確認レポート作成に必要な部品を利用できませんでした。",
        "not_implemented": "この操作はまだ実行接続されていません。",
        "execution_error": "操作中に問題が発生しました。入力材料を確認してもう一度試してください。",
    }
    return messages.get(code, "操作を完了できませんでした。入力材料を確認してください。")
