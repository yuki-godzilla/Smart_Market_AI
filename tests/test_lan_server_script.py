from pathlib import Path


def test_lan_server_passes_detected_ip_to_streamlit_browser_address() -> None:
    script = Path("scripts/run_lan_server.bat").read_text(encoding="utf-8")

    assert "--server.address 0.0.0.0" in script
    assert "--browser.serverAddress %SMAI_LAN_IP%" in script
    assert "http://%SMAI_LAN_IP%:8501" in script


def test_lan_server_uses_localhost_when_lan_ip_detection_fails() -> None:
    script = Path("scripts/run_lan_server.bat").read_text(encoding="utf-8")

    assert 'set "SMAI_LAN_IP=localhost"' in script
    assert 'set "SMAI_LAN_IP_FOUND=0"' in script
    assert "YOUR_DESKTOP_PC_IP" not in script
