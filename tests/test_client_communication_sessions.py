from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from backend.server_ops.maintenance import (
    MaintenanceManager,
    classify_client_type,
    normalize_device_id,
    normalize_client_type,
)
from ui.server_ops_device import DEVICE_QUERY_KEY, device_identity_bridge_html, device_id_from_query


def _manager(tmp_path: Path) -> MaintenanceManager:
    return MaintenanceManager(
        state_path=tmp_path / "state.json",
        activity_path=tmp_path / "activity.json",
        notice_path=tmp_path / "notice.json",
        intent_path=tmp_path / "intent.json",
        lock_roots=(tmp_path / "writes",),
    )


def test_client_type_classifier_keeps_only_coarse_device_categories() -> None:
    assert classify_client_type("Mozilla/5.0 (Windows NT 10.0; Win64; x64)") == "desktop"
    assert (
        classify_client_type("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Mobile")
        == "smartphone"
    )
    assert classify_client_type("Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) Mobile") == "tablet"
    assert classify_client_type("Mozilla/5.0 (Linux; Android 14; Pixel 8) Mobile") == "smartphone"
    assert classify_client_type("Mozilla/5.0 (Linux; Android 14; SM-X710) AppleWebKit") == "tablet"
    assert normalize_client_type("untrusted-device-label") == "unknown"


def test_heartbeat_records_client_type_and_anonymous_device_id_without_retaining_the_user_agent(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    now = datetime(2026, 7, 12, 0, 0, tzinfo=UTC)
    manager.activity_path.write_text(
        '{"sessions": {"session-1": {"last_seen_at": "2026-07-11T00:00:00+00:00", '
        '"user_agent": "Mozilla/5.0 (sensitive raw value)"}}, "operations": {}}',
        encoding="utf-8",
    )

    device_id = "50a9dbe7-231a-4fd0-9e8d-a372fdaaa63d"
    manager.heartbeat("session-1", client_type="tablet", device_id=device_id, now=now)

    activity = manager._clean_activity(now + timedelta(seconds=1))
    session = activity["sessions"]["session-1"]
    assert session == {
        "last_seen_at": now.isoformat(),
        "client_type": "tablet",
        "device_id": device_id,
        "connection_state": "connected",
    }


def test_device_id_contract_accepts_only_random_uuidv4_values() -> None:
    device_id = "50a9dbe7-231a-4fd0-9e8d-a372fdaaa63d"

    assert normalize_device_id(device_id) == device_id
    assert normalize_device_id("not-a-device") == ""
    assert normalize_device_id("50a9dbe7-231a-1fd0-9e8d-a372fdaaa63d") == ""
    assert device_id_from_query({DEVICE_QUERY_KEY: device_id}) == device_id
    assert device_id_from_query({DEVICE_QUERY_KEY: "not-a-device"}) == ""


def test_device_identity_bridge_uses_only_local_random_storage_and_url_contract() -> None:
    bridge = device_identity_bridge_html()

    assert "localStorage" in bridge
    assert "crypto.randomUUID" in bridge
    assert DEVICE_QUERY_KEY in bridge
    assert "User-Agent" not in bridge
    assert "clientIP" not in bridge
    assert "document.cookie" not in bridge


def test_legacy_timestamp_session_still_blocks_maintenance_until_it_expires(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    now = datetime(2026, 7, 12, 0, 0, tzinfo=UTC)
    manager.activity_path.write_text(
        '{"sessions": {"legacy": "2026-07-12T00:00:00+00:00"}, "operations": {}}',
        encoding="utf-8",
    )

    decision = manager.evaluate_drain(now=now + timedelta(seconds=30))

    assert decision.active_sessions == 1
    assert decision.safe_to_restart is False
