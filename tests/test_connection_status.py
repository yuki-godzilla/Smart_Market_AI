from ui.components.connection_status import (
    _config_values,
    _optimized_asset_stats,
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
    assert diagnostic.optimized_asset_count >= 12


def test_connection_diagnostic_reuses_static_asset_inventory() -> None:
    _config_values.cache_clear()
    _optimized_asset_stats.cache_clear()

    first = build_connection_diagnostic(client_address="127.0.0.1", session_state={})
    cache_after_first = _optimized_asset_stats.cache_info()
    config_after_first = _config_values.cache_info()
    second = build_connection_diagnostic(client_address="127.0.0.1", session_state={})
    cache_after_second = _optimized_asset_stats.cache_info()
    config_after_second = _config_values.cache_info()

    assert (first.optimized_asset_count, first.optimized_asset_bytes) == (
        second.optimized_asset_count,
        second.optimized_asset_bytes,
    )
    assert cache_after_first.misses == 1
    assert cache_after_second.hits == 1
    assert config_after_first.misses == 1
    assert config_after_second.hits == 1
