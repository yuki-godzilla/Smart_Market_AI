from __future__ import annotations

from collections.abc import Mapping


def compact_confidence_summary(row: Mapping[str, str]) -> str:
    """Build the compact Ranking confidence line without touching UI state."""

    parts: list[str] = []
    for label, column in (("品質", "データ品質"), ("条件", "条件適合度"), ("DB", "DB信頼度")):
        value = str(row.get(column, "")).strip()
        if value:
            parts.append(f"{label}{value}")
    research_status = str(row.get("根拠状態", "")).strip()
    if research_status:
        parts.append(research_status)
    return " / ".join(parts)


def full_confirmation_note(reason: str, checkpoint: str) -> str:
    """Combine Ranking reason/checkpoint text using the established display contract."""

    checkpoint = checkpoint.strip()
    reason = reason.strip()
    generic_checkpoint = "銘柄コックピットで価格・予測・リスクを確認します。"
    if checkpoint and checkpoint != generic_checkpoint:
        if reason and reason != checkpoint:
            return f"{reason} / {checkpoint}"
        return checkpoint
    return reason or checkpoint
