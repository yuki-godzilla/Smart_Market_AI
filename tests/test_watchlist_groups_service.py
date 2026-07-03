from __future__ import annotations

from collections import Counter

import pytest

from backend.watchlist_groups import (
    WATCHLIST_GROUP_TONES,
    WatchlistGroupsRepository,
    WatchlistGroupsService,
    assign_default_tone,
    build_grouped_watchlist,
)


def test_group_crud_description_tone_order_and_delete_placements(tmp_path):
    service = WatchlistGroupsService(WatchlistGroupsRepository(tmp_path))
    first = service.create_group("user_a", " 日本株 ", " 国内候補 ", "cyan")
    second = service.create_group("user_a", "米国株", None, "blue")
    service.move_symbol("user_a", "7974.t", first.group_id)

    updated = service.update_group(
        "user_a",
        first.group_id,
        name="日本個別株",
        description="国内の個別株候補",
        tone="green",
    )
    service.move_group("user_a", second.group_id, -1)

    state = service.list_groups("user_a")
    assert updated.name == "日本個別株"
    assert updated.description == "国内の個別株候補"
    assert updated.tone == "green"
    assert [group.group_id for group in sorted(state.groups, key=lambda item: item.order)] == [
        second.group_id,
        first.group_id,
    ]
    assert state.placements["7974.T"].group_id == first.group_id

    service.delete_group("user_a", first.group_id)
    state = service.list_groups("user_a")
    assert "7974.T" not in state.placements
    assert all(group.group_id != first.group_id for group in state.groups)


def test_group_validation_duplicate_limit_and_unknown_targets(tmp_path):
    service = WatchlistGroupsService(WatchlistGroupsRepository(tmp_path))
    group = service.create_group("user_a", "日本株")

    with pytest.raises(ValueError, match="同じ名前"):
        service.create_group("user_a", "日本株")
    with pytest.raises(ValueError, match="見つかりません"):
        service.move_symbol("user_a", "AAPL", "wg_abcdefgh")
    with pytest.raises(ValueError, match="見つかりません"):
        service.update_group(
            "user_a",
            "wg_abcdefgh",
            name="不存在",
            description=None,
            tone="cyan",
        )
    with pytest.raises(ValueError):
        service.move_symbol("user_a", "bad symbol", group.group_id)

    for index in range(1, 20):
        service.create_group("user_a", f"グループ{index}")
    with pytest.raises(ValueError, match="20件"):
        service.create_group("user_a", "21件目")


def test_tone_assignment_prefers_unused_then_least_used(tmp_path):
    service = WatchlistGroupsService(WatchlistGroupsRepository(tmp_path))
    assigned = [
        service.create_group("user_a", f"group-{index}").tone
        for index in range(len(WATCHLIST_GROUP_TONES))
    ]
    assert assigned == list(WATCHLIST_GROUP_TONES)

    service.create_group("user_a", "cyan-extra", tone="cyan")
    state = service.list_groups("user_a")
    counts = Counter(group.tone for group in state.groups)

    assert counts["cyan"] == 2
    assert assign_default_tone(state) == "blue"


def test_grouped_watchlist_keeps_orphan_hidden_and_unclassified_last(tmp_path):
    service = WatchlistGroupsService(WatchlistGroupsRepository(tmp_path))
    group = service.create_group("user_a", "日本株")
    service.move_symbol("user_a", "7974.T", group.group_id)
    service.move_symbol("user_a", "GHOST", group.group_id)
    favorites = [
        {"symbol": "7974.T", "name": "任天堂"},
        {"symbol": "AAPL", "name": "Apple"},
    ]

    sections = build_grouped_watchlist(favorites, service.list_groups("user_a"))

    assert [section.name for section in sections] == ["日本株", "未分類"]
    assert [item["symbol"] for item in sections[0].items] == ["7974.T"]
    assert [item["symbol"] for item in sections[-1].items] == ["AAPL"]
    assert sections[-1].tone == "slate"
    assert sections[-1].is_system is True


def test_removed_favorite_placement_can_restore_when_favorite_returns(tmp_path):
    service = WatchlistGroupsService(WatchlistGroupsRepository(tmp_path))
    group = service.create_group("user_a", "米国株")
    service.move_symbol("user_a", "AAPL", group.group_id)
    state = service.list_groups("user_a")

    assert build_grouped_watchlist([], state)[0].items == ()
    restored = build_grouped_watchlist([{"symbol": "AAPL"}], state)
    assert restored[0].items[0]["symbol"] == "AAPL"


def test_editor_draft_is_persisted_only_when_save_state_is_called(tmp_path):
    service = WatchlistGroupsService(WatchlistGroupsRepository(tmp_path))
    original = service.list_groups("user_a")
    group = service.create_group("user_a", "保存前")
    persisted = service.list_groups("user_a")
    draft = persisted.model_copy(update={"groups": ()})

    assert service.list_groups("user_a").groups[0].group_id == group.group_id
    service.save_state("user_a", draft)
    assert service.list_groups("user_a").groups == ()
    assert original.groups == ()
