from __future__ import annotations

from collections.abc import Iterable


def assistant_action_confirm_label(action_id: str) -> str:
    return {
        "update_research": "AI調査を更新する前に確認",
        "create_decision_report": "確認レポートを作る前に確認",
        "refresh_news": "ニュースを更新する前に確認",
    }.get(action_id, "実行前に確認")


def assistant_action_execute_label(action_id: str) -> str:
    return {
        "update_research": "AI調査を更新する",
        "create_decision_report": "作成する",
        "refresh_news": "ニュースを更新",
    }.get(action_id, "実行する")


def assistant_action_materials(
    material_status: Iterable[tuple[str, str]],
) -> tuple[str, ...]:
    return tuple(f"{label}: {value}" for label, value in material_status if label != "LLM")


def assistant_action_cancelled_title(action_id: str) -> str:
    return {
        "update_research": "AI調査の更新をキャンセルしました",
        "create_decision_report": "確認レポートの作成をキャンセルしました",
        "refresh_news": "ニュース更新をキャンセルしました",
    }.get(action_id, "操作をキャンセルしました")
