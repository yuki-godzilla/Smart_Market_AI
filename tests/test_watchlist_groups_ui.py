from __future__ import annotations

from backend.watchlist_groups import WATCHLIST_GROUP_TONES
from ui import user_data, watchlist_groups
from ui.styles import SMAI_GLOBAL_CSS
from ui.watchlist_groups import (
    TONE_LABELS,
    compact_watchlist_card_html,
    group_preview_html,
    group_section_header_html,
)


def test_group_header_uses_tone_count_and_escapes_content():
    markup = group_section_header_html(
        "<日本株>",
        "<国内候補>",
        "cyan",
        2,
        False,
    )

    assert "smai-watchlist-group-section--tone-cyan" in markup
    assert "2件" in markup
    assert "&lt;日本株&gt;" in markup
    assert "<日本株>" not in markup


def test_unclassified_and_unknown_tone_are_slate():
    markup = group_section_header_html("未分類", None, "unknown", 0, True)

    assert "smai-watchlist-group-section--tone-slate" in markup
    assert "まだグループに配置していない" in markup


def test_compact_card_omits_missing_metrics_and_escapes_values():
    markup = compact_watchlist_card_html(
        {
            "symbol": "7974.T",
            "name": "<Nintendo>",
            "ai_score": "未取得",
            "upside": "68",
            "downside": "32",
        }
    )

    assert "&lt;Nintendo&gt;" in markup
    assert "AI総合" not in markup
    assert "上昇気配" in markup
    assert "下振れ警戒" in markup


def test_tone_candidates_preview_and_action_styles_are_available():
    assert set(TONE_LABELS) == set(WATCHLIST_GROUP_TONES)
    assert "smai-watchlist-group-section--tone-purple" in group_preview_html(
        "半導体・AI",
        "成長候補",
        "purple",
    )
    for class_name in (
        "smai-watchlist-action-primary",
        "smai-watchlist-action-edit",
        "smai-watchlist-action-save",
        "smai-watchlist-action-danger",
        "smai-watchlist-action-secondary",
    ):
        assert class_name in SMAI_GLOBAL_CSS
    for tone in WATCHLIST_GROUP_TONES:
        assert f"smai-watchlist-group-section--tone-{tone}" in SMAI_GLOBAL_CSS


def test_default_user_group_store_is_session_only(monkeypatch):
    state: dict[str, object] = {"smai_current_user_id": "default"}
    monkeypatch.setattr(user_data.st, "session_state", state)
    monkeypatch.setattr(watchlist_groups.st, "session_state", state)

    service, user_id = watchlist_groups.current_watchlist_groups_service()
    group = service.create_group(user_id, "セッション用")

    assert group.name == "セッション用"
    assert "smai_default_user_watchlist_groups" in state
    assert service.list_groups(user_id).groups[0].group_id == group.group_id
