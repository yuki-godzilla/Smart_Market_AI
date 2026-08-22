from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def _read(relative: str) -> str:
    return (SCRIPTS / relative).read_text(encoding="utf-8")


def test_runtime_launcher_is_powershell_first_and_file_logged() -> None:
    runtime = _read("start_smai_runtime.ps1")

    assert "backend.server_ops.launcher" in runtime
    assert "--maintenance-startup" in runtime
    assert "--resilient" in runtime
    assert "runtime.log" in runtime
    assert "start_smai_server.bat" not in runtime
    assert "cmd.exe" not in runtime.casefold()


def test_autostart_registers_hidden_runtime_and_disables_legacy_tasks() -> None:
    registration = _read("server_ops/register_smai_autostart_task.ps1")

    assert '"SmartMarketAI-Runtime"' in registration
    assert '"SmartMarketAI-Server-Watch"' in registration
    assert '"SmartMarketAI-LAN-Server"' in registration
    assert '"SmartMarketAI-Server-Autostart"' in registration
    assert "-NonInteractive -WindowStyle Hidden" in registration
    assert "start_smai_runtime.ps1" in registration
    assert "$env:ComSpec" not in registration


def test_watcher_recovers_through_hidden_runtime_launcher() -> None:
    watcher = _read("server_ops/watch_smai_server.ps1")

    assert "start_smai_runtime.ps1" in watcher
    assert "start_smai_server.bat" not in watcher
    assert '"-WindowStyle", "Hidden"' in watcher
    assert "$env:ComSpec" not in watcher


def test_restart_uses_hidden_runtime_launcher_for_startup_side() -> None:
    restart = _read("server_ops/restart_smai_server.ps1")

    assert "start_smai_runtime.ps1" in restart
    assert "start_smai_server.bat" not in restart
    assert '"-WindowStyle", "Hidden"' in restart
