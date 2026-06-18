from __future__ import annotations

import html
from collections.abc import Mapping

from backend.assistant import AssistantActionResult

_STATUS_LABELS = {
    "success": "成功",
    "failed": "失敗",
    "skipped": "未実行",
    "partial_success": "一部成功",
    "not_available": "利用不可",
    "cancelled": "キャンセル",
    "validation_error": "確認エラー",
}


def assistant_action_result_card_html(result: AssistantActionResult | Mapping[str, object]) -> str:
    value = (
        result
        if isinstance(result, AssistantActionResult)
        else AssistantActionResult.model_validate(result)
    )
    status_label = _STATUS_LABELS.get(value.status, value.status)
    warnings = "".join(
        f"<li>{html.escape(item)}</li>" for item in value.warnings if str(item).strip()
    )
    followups = "".join(
        f"<li>{html.escape(_followup_label(item))}</li>"
        for item in value.followup_actions
        if str(item).strip()
    )
    error = (
        f'<p class="smai-copilot-action-result-error">理由: '
        f"{html.escape(value.error_message or value.user_message)}</p>"
        if value.status in {"failed", "not_available", "validation_error"} and value.user_message
        else ""
    )
    created = value.completed_at.strftime("%Y-%m-%d %H:%M") if value.completed_at else ""
    return (
        '<section class="smai-copilot-action-result '
        f'smai-copilot-action-result--{html.escape(value.status)}">'
        f"<span>実行結果: {html.escape(status_label)}</span>"
        f"<h4>{html.escape(value.title)}</h4>"
        f"<p>{html.escape(value.summary)}</p>"
        f"<p>{html.escape(value.user_message)}</p>"
        f"{error}"
        f"{f'<small>作成時刻: {html.escape(created)}</small>' if created else ''}"
        f"{f'<div><strong>注意</strong><ul>{warnings}</ul></div>' if warnings else ''}"
        f"{f'<div><strong>次にできること</strong><ul>{followups}</ul></div>' if followups else ''}"
        "</section>"
    )


def _followup_label(action_id: str) -> str:
    labels = {
        "download_decision_report": "レポートを見る / 保存する",
        "open_research_section": "Cockpitで根拠資料を確認する",
        "create_decision_report": "確認レポートを作る",
        "open_cockpit": "銘柄コックピットで銘柄を選ぶ",
        "fetch_symbol_data": "データを取得する",
        "retry_update_research": "AI調査をもう一度更新する",
        "answer_with_existing_materials": "取得済み材料だけで確認する",
        "summarize_next_checks": "次の確認を整理する",
    }
    return labels.get(str(action_id), str(action_id))
