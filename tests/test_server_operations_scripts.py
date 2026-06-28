from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_scheduled_start_script_has_guarded_logged_workstation_startup() -> None:
    script = _read("scripts/start_smai_server.bat")

    assert "if not defined SMAI_PERFORMANCE_PROFILE" in script
    assert 'set "SMAI_PERFORMANCE_PROFILE=workstation"' in script
    assert 'set "SMAI_ASSISTANT_GATEWAY_AUTOSTART=1"' in script
    assert "logs\\server_ops" in script
    assert "Get-NetTCPConnection -LocalPort 8501 -State Listen" in script
    assert "A second instance will not be started." in script
    assert "--server.address 0.0.0.0" in script
    assert "--server.headless true" in script
    assert "--browser.serverAddress %SMAI_LAN_IP%" in script
    assert "run_symbol_universe_import_all.bat" not in script
    assert "pause" not in script.lower()
    assert '>> "%SMAI_LOG_FILE%" echo(%~1' in script


def test_status_script_checks_smai_gateway_and_ollama() -> None:
    script = _read("scripts/check_smai_server_status.bat")

    assert "http://localhost:8501/_stcore/health" in script
    assert "http://127.0.0.1:8088/health" in script
    assert "http://127.0.0.1:11434/api/tags" in script
    assert "http://%SMAI_LAN_IP%:8501" in script


def test_stop_script_only_stops_matching_8501_smai_listener() -> None:
    script = _read("scripts/stop_smai_server.bat")

    assert "Get-NetTCPConnection -LocalPort 8501 -State Listen" in script
    assert "CommandLine:" in script
    assert "streamlit.+ui[\\\\/]+app\\.py" in script
    assert 'if /i "%~1"=="/quiet"' in script
    assert "Stop-Process -Id $p.ProcessId" in script


def test_task_registration_has_logon_delay_retry_and_ignore_new() -> None:
    script = _read("scripts/register_smai_startup_task.ps1")

    assert '"SmartMarketAI-LAN-Server"' in script
    assert "New-ScheduledTaskTrigger -AtLogOn" in script
    assert '$trigger.Delay = "PT1M"' in script
    assert "-MultipleInstances IgnoreNew" in script
    assert "-RestartCount 3" in script
    assert "-ExecutionTimeLimit ([TimeSpan]::Zero)" in script
    assert "start_smai_server.bat" in script
    assert "-Execute $env:ComSpec" in script
    assert "Register-ScheduledTask" in script


def test_task_unregistration_is_idempotent() -> None:
    script = _read("scripts/unregister_smai_startup_task.ps1")

    assert '"SmartMarketAI-LAN-Server"' in script
    assert "Get-ScheduledTask" in script
    assert "Scheduled task is not registered" in script
    assert "Unregister-ScheduledTask" in script
