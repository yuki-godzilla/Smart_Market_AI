from pathlib import Path


def test_manual_server_uses_the_magicdns_url_and_localhost_browser_address() -> None:
    script = Path("scripts/run_lan_server.bat").read_text(encoding="utf-8")

    assert "-m backend.server_ops.launcher" in script
    assert "--browser-address localhost" in script
    assert "SMAI_MAIN_APPLICATION_URL" in script
    assert "SMAI_LOCAL_APPLICATION_URL" in script
    assert "tailscale ip -4" not in script
    assert "WebSocket compression: enabled" in script
    assert "Duplicate-safe shared launcher: enabled" in script
    assert 'if "%SMAI_EXIT_CODE%"=="10"' in script
    assert "Existing SMAI server remains available. Nothing was stopped." in script
    assert "pause" not in script.lower()


def test_manual_server_resolves_magicdns_url_through_the_common_module() -> None:
    script = Path("scripts/run_lan_server.bat").read_text(encoding="utf-8")

    assert "backend.server_ops.network --emit-batch" in script
    assert "SMAI_TAILSCALE_HOSTNAME" in script
    assert "SMAI_LAN_IP" not in script
