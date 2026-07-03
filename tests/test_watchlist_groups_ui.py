from __future__ import annotations

from backend.watchlist_groups import WATCHLIST_GROUP_TONES
from ui import user_data, watchlist_groups
from ui.styles import SMAI_GLOBAL_CSS
from ui.watchlist_groups import (
    TONE_LABELS,
    apply_sortable_payload,
    build_sortable_watchlist_containers,
    compact_watchlist_card_html,
    draft_add_group,
    draft_delete_group,
    draft_move_symbol,
    draft_update_group,
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
    markup = group_section_header_html(
        "未分類",
        None,
        "unknown",
        2,
        True,
        collapsed=True,
        representative_symbols=["AAPL", "7203.T"],
    )

    assert "smai-watchlist-group-section--tone-slate" in markup
    assert "まだグループに配置していない" in markup
    assert "▶ 未分類" in markup
    assert "上位: AAPL, 7203.T" in markup


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
    assert "上昇気配" not in markup
    assert "下振れ警戒" not in markup
    assert "7974.T" in markup


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


def test_editor_draft_add_update_move_delete_without_persisting():
    draft = watchlist_groups.empty_watchlist_groups_state()
    draft = draft_add_group(draft, "日本株", "国内候補", "cyan")
    group_id = draft.groups[0].group_id
    draft = draft_move_symbol(draft, "7974.T", group_id)
    draft = draft_update_group(draft, group_id, "日本個別株", "更新後", "green")

    assert draft.groups[0].name == "日本個別株"
    assert draft.groups[0].tone == "green"
    assert draft.placements["7974.T"].group_id == group_id

    deleted = draft_delete_group(draft, group_id)
    assert deleted.groups == ()
    assert "7974.T" not in deleted.placements


def test_normal_group_renderer_has_no_current_confirmation_or_move_select():
    source = __import__("inspect").getsource(watchlist_groups.render_grouped_watchlist)

    assert "現在確認" not in source
    assert "移動先" not in source
    assert "render_card(row)" in source


def test_sortable_containers_are_chip_only_and_keep_empty_and_unclassified_last():
    draft = watchlist_groups.empty_watchlist_groups_state()
    draft = draft_add_group(draft, "日本株", None, "cyan")
    containers, item_symbols, header_groups = build_sortable_watchlist_containers(
        [{"symbol": "AAPL", "name": "Apple", "ai_score": "99"}],
        draft,
    )

    assert len(containers) == 2
    assert containers[0]["items"] == []
    assert str(containers[-1]["header"]).startswith("未分類")
    assert containers[-1]["items"] == ["AAPL | Apple"]
    assert item_symbols == {"AAPL | Apple": "AAPL"}
    assert header_groups[str(containers[-1]["header"])] is None
    assert "99" not in str(containers)


def test_sortable_payload_moves_and_orders_symbols_in_draft():
    draft = watchlist_groups.empty_watchlist_groups_state()
    draft = draft_add_group(draft, "日本株", None, "cyan")
    group = draft.groups[0]
    rows = [
        {"symbol": "AAPL", "name": "Apple"},
        {"symbol": "7974.T", "name": "Nintendo"},
    ]
    containers, item_symbols, header_groups = build_sortable_watchlist_containers(rows, draft)
    group_header = str(containers[0]["header"])
    uncategorized_header = str(containers[-1]["header"])
    payload = [
        {
            "header": group_header,
            "items": ["7974.T | Nintendo", "AAPL | Apple"],
        },
        {"header": uncategorized_header, "items": []},
    ]

    updated = apply_sortable_payload(
        draft,
        payload,
        item_symbols=item_symbols,
        header_groups=header_groups,
    )

    assert updated.placements["7974.T"].group_id == group.group_id
    assert updated.placements["7974.T"].order == 10
    assert updated.placements["AAPL"].order == 20


def test_sortable_payload_rejects_unknown_group_and_ignores_duplicate_unknown_symbol():
    draft = watchlist_groups.empty_watchlist_groups_state()
    draft = draft_add_group(draft, "日本株", None, "cyan")
    containers, item_symbols, header_groups = build_sortable_watchlist_containers(
        [{"symbol": "AAPL", "name": "Apple"}],
        draft,
    )
    invalid = [{"header": "unknown", "items": ["AAPL | Apple"]}]
    assert (
        apply_sortable_payload(
            draft,
            invalid,
            item_symbols=item_symbols,
            header_groups=header_groups,
        )
        == draft
    )

    group_header = str(containers[0]["header"])
    uncategorized_header = str(containers[-1]["header"])
    duplicate = [
        {"header": group_header, "items": ["AAPL | Apple", "UNKNOWN"]},
        {"header": uncategorized_header, "items": ["AAPL | Apple"]},
    ]
    updated = apply_sortable_payload(
        draft,
        duplicate,
        item_symbols=item_symbols,
        header_groups=header_groups,
    )
    assert updated.placements["AAPL"].group_id == draft.groups[0].group_id
