from __future__ import annotations

import json
from pathlib import Path

from ui.last_session import (
    MAX_SNAPSHOT_BYTES,
    load_last_session,
    restore_last_session,
    save_last_session,
    save_last_session_if_changed,
    snapshot_from_session_state,
)


def _snapshot() -> dict[str, object]:
    return {
        "schema_version": 1,
        "updated_at": "2026-07-02T21:00:00+09:00",
        "selected_user_id": "u_12345678",
        "active_page": "cockpit",
        "selected_symbol": "7203.T",
        "ranking_filters": {
            "market_data_ranking_region": "jp",
            "ignored_large_field": "x" * 100,
        },
    }


def test_last_session_round_trip_keeps_only_allowlisted_small_fields(tmp_path: Path) -> None:
    path = tmp_path / "last_session.json"

    assert save_last_session(_snapshot(), path) is True

    restored = load_last_session(path)
    assert restored is not None
    assert restored["selected_user_id"] == "u_12345678"
    assert restored["selected_symbol"] == "7203.T"
    assert restored["ranking_filters"] == {"market_data_ranking_region": "jp"}
    assert path.stat().st_size < MAX_SNAPSHOT_BYTES


def test_corrupt_or_oversized_snapshot_is_ignored(tmp_path: Path) -> None:
    path = tmp_path / "last_session.json"
    path.write_text("{broken", encoding="utf-8")
    assert load_last_session(path) is None
    path.write_text("x" * (MAX_SNAPSHOT_BYTES + 1), encoding="utf-8")
    assert load_last_session(path) is None


def test_restore_uses_valid_user_and_restores_page_symbol_and_filters(tmp_path: Path) -> None:
    path = tmp_path / "last_session.json"
    assert save_last_session(_snapshot(), path)
    state: dict[str, object] = {}

    restored = restore_last_session(
        state,
        valid_user_ids={"u_12345678"},
        path=path,
    )

    assert restored == {
        "selected_user_id": "u_12345678",
        "active_page": "cockpit",
        "selected_symbol": "7203.T",
    }
    assert state["smai_current_user_id"] == "u_12345678"
    assert state["sidemenu_page"] == "cockpit"
    assert state["market_data_symbol_candidate"] == "7203.T"
    assert state["market_data_ranking_region"] == "jp"


def test_restore_url_values_win_and_missing_user_safely_falls_back(tmp_path: Path) -> None:
    path = tmp_path / "last_session.json"
    assert save_last_session(_snapshot(), path)
    state: dict[str, object] = {}

    restore_last_session(
        state,
        valid_user_ids={"u_other123"},
        query_params={
            "smai_start_profile": "u_other123",
            "smai_page": "news",
            "smai_symbol": "AAPL",
        },
        path=path,
    )

    assert "smai_current_user_id" not in state
    assert "sidemenu_page" not in state
    assert "market_data_symbol_candidate" not in state


def test_restore_can_preserve_user_selection_as_startup_gate(tmp_path: Path) -> None:
    path = tmp_path / "last_session.json"
    assert save_last_session(_snapshot(), path)
    state: dict[str, object] = {}

    restored = restore_last_session(
        state,
        valid_user_ids={"u_12345678"},
        path=path,
        restore_selected_user=False,
        restore_active_page=False,
    )

    assert "smai_current_user_id" not in state
    assert "sidemenu_page" not in state
    assert restored == {
        "selected_symbol": "7203.T",
    }


def test_snapshot_does_not_serialize_large_or_unknown_session_values() -> None:
    state = {
        "smai_current_user_id": "u_12345678",
        "sidemenu_page": "ranking",
        "huge_dataframe_or_llm_text": "x" * 100_000,
        "market_data_ranking_region": "us",
    }

    snapshot = snapshot_from_session_state(state, selected_symbol="AAPL")

    assert snapshot is not None
    assert "huge_dataframe_or_llm_text" not in snapshot
    assert len(json.dumps(snapshot)) < 1_000


def test_save_failure_is_non_fatal_and_unchanged_state_is_not_rewritten(
    tmp_path: Path,
) -> None:
    state = {"smai_current_user_id": "u_12345678", "sidemenu_page": "cockpit"}
    path = tmp_path / "last_session.json"
    assert save_last_session_if_changed(state, path=path) is True
    first_contents = path.read_text(encoding="utf-8")
    assert save_last_session_if_changed(state, path=path) is False
    assert path.read_text(encoding="utf-8") == first_contents

    directory_path = tmp_path / "not-a-file"
    directory_path.mkdir()
    assert save_last_session(_snapshot(), directory_path) is False
