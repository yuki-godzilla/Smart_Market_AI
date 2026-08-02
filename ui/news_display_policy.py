"""Deterministic labels and presentation tones for the News/Radar UI."""

from __future__ import annotations

FRESHNESS_LABELS = {"latest": "最新", "recent": "近日", "stale": "古め", "unknown": "未確認"}
RADAR_PROVENANCE_LABELS = {
    "direct_mention": "本文に出た銘柄",
    "inferred_candidate": "SMAI推測候補",
    "macro_proxy": "市場背景の確認",
}
RADAR_MATERIAL_TONE_LABELS = {
    "positive": "好材料を含む",
    "caution": "注意材料を含む",
    "mixed": "材料が混在",
    "unknown": "材料の方向は未確認",
}
RADAR_DATA_STATUS_LABELS = {
    "available": "確認可能",
    "partial": "一部確認",
    "unavailable": "未取得",
    "not_checked": "未確認",
}
MATERIAL_LABELS = {
    "earnings": "決算・業績",
    "fund_flow": "資金フロー",
    "macro": "マクロ",
    "policy": "政策",
    "risk": "リスク材料",
    "shareholder_return": "株主還元",
    "theme": "テーマ",
}
MATERIAL_TONES = {
    "earnings": "news",
    "fund_flow": "news",
    "macro": "news",
    "policy": "news",
    "risk": "news",
    "shareholder_return": "news",
    "theme": "news",
}


def freshness_label(status: str) -> str:
    return FRESHNESS_LABELS.get(status, status or "未確認")


def material_label(material_type: str | None) -> str:
    if material_type is None:
        return "未分類"
    return MATERIAL_LABELS.get(material_type, material_type)
