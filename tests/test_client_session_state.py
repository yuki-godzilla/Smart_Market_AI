from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ui.last_session import (
    CLIENT_ID_STATE_KEY,
    MAX_SNAPSHOT_BYTES,
    clear_client_session,
    client_session_path,
    ensure_client_id,
    generate_client_id,
    load_client_session,
    restore_client_session,
    save_client_session,
    save_client_session_if_changed,
    snapshot_from_session_state,
    valid_client_id,
)

NOW = datetime(2026, 7, 3, 2, 20, tzinfo=UTC)
CLIENT_ID = "smai_client_0123456789abcdef01234567"


def _snapshot(*, last_seen_at: datetime = NOW) -> dict[str, object]:
    return {
        "schema_version": 1,
        "client_id": CLIENT_ID,
        "selected_user_id": "u_12345678",
        "active_page": "cockpit",
        "selected_symbol": "7203.T",
        "ranking_filters": {
            "market_data_ranking_region": "jp",
            "ignored_large_field": "x" * 100,
        },
        "last_seen_at": last_seen_at.isoformat(),
    }


def test_client_id_is_generated_and_reflected_in_query_params() -> None:
    state: dict[str, object] = {}
    query_params: dict[str, object] = {}

    client_id = ensure_client_id(state, query_params)

    assert valid_client_id(client_id)
    assert query_params["client"] == client_id
    assert state[CLIENT_ID_STATE_KEY] == client_id
    assert valid_client_id(generate_client_id())


def test_existing_valid_client_id_wins_and_unsafe_id_is_replaced() -> None:
    state: dict[str, object] = {CLIENT_ID_STATE_KEY: CLIENT_ID}
    query_params: dict[str, object] = {"client": "../../escape"}

    assert ensure_client_id(state, query_params) == CLIENT_ID
    assert query_params["client"] == CLIENT_ID
    assert client_session_path("../../escape") is None


def test_client_snapshot_round_trip_keeps_only_allowlisted_small_fields(
    tmp_path: Path,
) -> None:
    path = tmp_path / "clients" / f"{CLIENT_ID}.json"

    assert save_client_session(_snapshot(), path) is True

    restored = load_client_session(path)
    assert restored is not None
    assert restored["selected_user_id"] == "u_12345678"
    assert restored["selected_symbol"] == "7203.T"
    assert restored["ranking_filters"] == {"market_data_ranking_region": "jp"}
    assert path.stat().st_size < MAX_SNAPSHOT_BYTES


def test_recent_snapshot_restores_user_page_symbol_and_filters(tmp_path: Path) -> None:
    path = tmp_path / f"{CLIENT_ID}.json"
    assert save_client_session(_snapshot(), path)
    state: dict[str, object] = {CLIENT_ID_STATE_KEY: CLIENT_ID}

    restored = restore_client_session(
        state,
        client_id=CLIENT_ID,
        valid_user_ids={"u_12345678"},
        directory=tmp_path,
        now=NOW + timedelta(minutes=30),
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


def test_expired_snapshot_is_deleted_and_restored_state_is_cleared(tmp_path: Path) -> None:
    path = tmp_path / f"{CLIENT_ID}.json"
    assert save_client_session(_snapshot(), path)
    state: dict[str, object] = {
        "smai_current_user_id": "stale",
        "sidemenu_page": "ranking",
        "market_data_symbol_candidate": "AAPL",
    }

    restored = restore_client_session(
        state,
        client_id=CLIENT_ID,
        valid_user_ids={"u_12345678"},
        directory=tmp_path,
        now=NOW + timedelta(minutes=30, seconds=1),
    )

    assert restored is None
    assert not path.exists()
    assert "smai_current_user_id" not in state
    assert "sidemenu_page" not in state
    assert "market_data_symbol_candidate" not in state


def test_missing_user_deletes_snapshot_and_safely_falls_back(tmp_path: Path) -> None:
    path = tmp_path / f"{CLIENT_ID}.json"
    assert save_client_session(_snapshot(), path)
    state: dict[str, object] = {}

    restore_client_session(
        state,
        client_id=CLIENT_ID,
        valid_user_ids={"u_other123"},
        directory=tmp_path,
        now=NOW,
    )

    assert "smai_current_user_id" not in state
    assert not path.exists()


def test_snapshot_does_not_serialize_large_or_unknown_session_values() -> None:
    state = {
        "smai_current_user_id": "u_12345678",
        "sidemenu_page": "ranking",
        "huge_dataframe_or_llm_text": "x" * 100_000,
        "market_data_ranking_region": "us",
    }

    snapshot = snapshot_from_session_state(
        state,
        client_id=CLIENT_ID,
        selected_symbol="AAPL",
        now=NOW,
    )

    assert snapshot is not None
    assert "huge_dataframe_or_llm_text" not in snapshot
    assert len(json.dumps(snapshot)) < 1_000


def test_ranking_detail_filters_survive_client_session_restore(tmp_path: Path) -> None:
    state: dict[str, object] = {
        "smai_current_user_id": "u_12345678",
        "sidemenu_page": "ranking",
        "market_data_ranking_period": "long_3y",
        "market_data_ranking_dividend_enabled": True,
        "market_data_ranking_dividend_min": "3.0",
        "market_data_ranking_per_enabled": True,
        "market_data_ranking_per_min": "5.0",
        "market_data_ranking_per_max": "20.0",
    }
    snapshot = snapshot_from_session_state(
        state,
        client_id=CLIENT_ID,
        now=NOW,
    )
    assert snapshot is not None
    path = tmp_path / f"{CLIENT_ID}.json"
    assert save_client_session(snapshot, path)

    restored_state: dict[str, object] = {}
    restore_client_session(
        restored_state,
        client_id=CLIENT_ID,
        valid_user_ids={"u_12345678"},
        directory=tmp_path,
        now=NOW,
    )

    assert restored_state["market_data_ranking_period"] == "long_3y"
    assert restored_state["market_data_ranking_dividend_enabled"] is True
    assert restored_state["market_data_ranking_dividend_min"] == "3.0"
    assert restored_state["market_data_ranking_per_enabled"] is True
    assert restored_state["market_data_ranking_per_min"] == "5.0"
    assert restored_state["market_data_ranking_per_max"] == "20.0"


def test_corrupt_snapshot_and_save_failure_are_non_fatal(tmp_path: Path) -> None:
    path = tmp_path / f"{CLIENT_ID}.json"
    path.write_text("{broken", encoding="utf-8")
    assert load_client_session(path) is None
    state: dict[str, object] = {}
    assert (
        restore_client_session(
            state,
            client_id=CLIENT_ID,
            valid_user_ids={"u_12345678"},
            directory=tmp_path,
            now=NOW,
        )
        is None
    )

    directory_path = tmp_path / "not-a-file"
    directory_path.mkdir()
    assert save_client_session(_snapshot(), directory_path) is False


def test_unchanged_snapshot_is_not_rewritten_and_release_clears_it(tmp_path: Path) -> None:
    state: dict[str, object] = {
        CLIENT_ID_STATE_KEY: CLIENT_ID,
        "smai_current_user_id": "u_12345678",
        "sidemenu_page": "cockpit",
    }
    assert save_client_session_if_changed(
        state,
        client_id=CLIENT_ID,
        directory=tmp_path,
        now=NOW,
    )
    path = tmp_path / f"{CLIENT_ID}.json"
    first_contents = path.read_text(encoding="utf-8")
    assert not save_client_session_if_changed(
        state,
        client_id=CLIENT_ID,
        directory=tmp_path,
        now=NOW + timedelta(minutes=1),
    )
    assert path.read_text(encoding="utf-8") == first_contents

    assert save_client_session_if_changed(
        state,
        client_id=CLIENT_ID,
        directory=tmp_path,
        now=NOW + timedelta(minutes=2),
        force_write=True,
    )
    assert path.read_text(encoding="utf-8") != first_contents

    assert clear_client_session(state, client_id=CLIENT_ID, directory=tmp_path)
    assert not path.exists()
    assert "smai_current_user_id" not in state
    assert state[CLIENT_ID_STATE_KEY] == CLIENT_ID
