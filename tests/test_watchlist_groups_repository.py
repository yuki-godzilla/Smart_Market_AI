from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from backend.watchlist_groups import (
    WatchlistGroup,
    WatchlistGroupsRepository,
    WatchlistGroupsState,
)


def test_repository_empty_round_trip_and_user_separation(tmp_path):
    repository = WatchlistGroupsRepository(tmp_path)

    assert repository.load("user_a").groups == ()

    now = datetime.now(UTC)
    state = WatchlistGroupsState(
        updated_at=now,
        groups=(
            WatchlistGroup(
                group_id="wg_12345678",
                name="日本株",
                order=10,
                tone="cyan",
                created_at=now,
                updated_at=now,
            ),
        ),
    )
    repository.save("user_a", state)

    assert repository.load("user_a") == state
    assert repository.load("user_b").groups == ()
    assert not list((tmp_path / "user_a").glob("*.tmp"))


def test_repository_rejects_default_and_unsafe_user(tmp_path):
    repository = WatchlistGroupsRepository(tmp_path)

    with pytest.raises(ValueError):
        repository.load("default")
    with pytest.raises(ValueError):
        repository.save("../outside", WatchlistGroupsRepository.empty_state())


def test_repository_broken_json_falls_back_to_empty(tmp_path):
    path = tmp_path / "user_a" / "watchlist_groups.json"
    path.parent.mkdir(parents=True)
    path.write_text("{broken", encoding="utf-8")

    state = WatchlistGroupsRepository(tmp_path).load("user_a")

    assert state.groups == ()
    assert state.placements == {}


def test_repository_writes_versioned_utf8_json(tmp_path):
    repository = WatchlistGroupsRepository(tmp_path)
    repository.save("user_a", repository.empty_state())

    payload = json.loads(
        (tmp_path / "user_a" / "watchlist_groups.json").read_text(encoding="utf-8")
    )

    assert payload["schema_version"] == 1
    assert payload["groups"] == []
    assert payload["placements"] == {}
