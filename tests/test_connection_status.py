from ui.components.connection_status import (
    build_connection_diagnostic,
    estimate_session_state_size,
    infer_connection_type,
)


def test_connection_type_detection_covers_local_lan_and_tailscale() -> None:
    assert infer_connection_type("127.0.0.1") == "localhost"
    assert infer_connection_type("192.168.1.20") == "LAN"
    assert infer_connection_type("100.64.12.34") == "Tailscale"
    assert infer_connection_type("") == "不明"


def test_session_state_measurement_records_sizes_without_values() -> None:
    count, size = estimate_session_state_size({"small": "abc", "rows": list(range(20))})
    assert count == 2
    assert size > 20


def test_connection_diagnostic_reads_external_access_config() -> None:
    diagnostic = build_connection_diagnostic(
        client_address="100.64.12.34",
        session_state={"page": "ranking"},
    )
    assert diagnostic.connection_type == "Tailscale"
    assert diagnostic.static_serving is True
    assert diagnostic.websocket_compression is True
    assert diagnostic.websocket_ping_interval == 30
    assert diagnostic.disconnected_session_ttl == 300
    assert diagnostic.optimized_asset_count >= 12
