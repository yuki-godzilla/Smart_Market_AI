from __future__ import annotations

import html
from collections.abc import Sequence

from backend.assistant import AssistantActionSpec


def assistant_action_confirmation_html(
    *,
    action: AssistantActionSpec,
    target_label: str,
    materials: Sequence[str],
) -> str:
    external_note = _external_fetch_note(action)
    material_items = "".join(
        f"<li>{html.escape(item)}</li>" for item in materials if str(item).strip()
    )
    return (
        '<section class="smai-copilot-action-confirm">'
        '<span class="smai-copilot-tool-plan-title">実行前確認</span>'
        f"<h4>{html.escape(_action_heading(action))}</h4>"
        f"<p>対象: {html.escape(target_label or '現在の画面')}</p>"
        "<div>"
        "<strong>使用する材料</strong>"
        f"<ul>{material_items or '<li>現在画面の取得済み材料</li>'}</ul>"
        "</div>"
        "<div>"
        "<strong>この操作</strong>"
        "<ul>"
        "<li>売買判断ではありません。</li>"
        "<li>スコア・予測・AI総合は変更しません。</li>"
        f"{external_note}"
        "<li>broker連携や注文操作は行いません。</li>"
        "</ul>"
        "</div>"
        "</section>"
    )


def _external_fetch_note(action: AssistantActionSpec) -> str:
    if not action.is_external_fetch:
        return "<li>この操作では最新情報の取得は行いません。</li>"
    if action.action_id == "update_research":
        return (
            "<li>最新のニュース・開示・IR候補を確認します。</li>"
            "<li>取得には少し時間がかかる場合があります。一部だけ取得できることもあります。</li>"
            "<li>この操作だけでは、スコアや予測値は変更されません。</li>"
        )
    return "<li>最新情報を確認します。取得に少し時間がかかる場合があります。</li>"


def _action_heading(action: AssistantActionSpec) -> str:
    if action.action_id == "update_research":
        return "AI調査を更新します"
    if action.action_id == "create_decision_report":
        return "確認レポートを作成します"
    return f"{action.label}します"
