from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_scheduled_start_script_has_guarded_logged_workstation_startup() -> None:
    script = _read("scripts/start_smai_server.bat")

    assert "if not defined SMAI_PERFORMANCE_PROFILE" in script
    assert 'set "SMAI_PERFORMANCE_PROFILE=workstation"' in script
    assert 'set "SMAI_ASSISTANT_GATEWAY_AUTOSTART=1"' in script
    assert "logs\\server_ops" in script
    assert "-m backend.server_ops.launcher" in script
    assert "--browser-address localhost" in script
    assert "--maintenance-startup" in script
    assert "--resilient" in script
    assert 'if /i "%~1"=="/console"' in script
    assert "--visible-console" in script
    assert "Interactive Main Application server console" in script
    assert "Keep this window open while SMAI is running." in script
    assert "SMAI_MAIN_APPLICATION_URL" in script
    assert "SMAI_LOCAL_APPLICATION_URL" in script
    assert "tailscale ip -4" not in script
    assert "websocket compression=enabled" in script
    assert "Duplicate-safe shared launcher: enabled" in script
    assert "run_symbol_universe_import_all.bat" not in script
    assert "pause" not in script.lower()
    assert '>> "%SMAI_LOG_FILE%" echo(%~1' in script


def test_status_script_checks_smai_gateway_and_ollama() -> None:
    script = _read("scripts/check_smai_server_status.bat")

    assert "%SMAI_LOCAL_APPLICATION_URL%/_stcore/health" in script
    assert "http://127.0.0.1:8088/health" in script
    assert "http://127.0.0.1:11434/api/tags" in script
    assert "SMAI_MAIN_APPLICATION_URL" in script


def test_stop_script_only_stops_matching_8501_smai_listener() -> None:
    wrapper = _read("scripts/stop_smai_server.bat")
    script = _read("scripts/server_ops/stop_smai_server.ps1")

    assert "backend.server_ops.network --emit-json" in script
    assert "Get-NetTCPConnection -LocalPort $mainPort -State Listen" in script
    assert "CommandLine:" in script
    assert "streamlit.+ui[\\/]+app\\.py" in script
    assert 'if /i "%~1"=="/quiet"' in wrapper
    assert "stop_smai_server.ps1" in wrapper
    assert "-Quiet" in wrapper
    assert "Stop-Process -Id $process.ProcessId" in script


def test_restart_script_reuses_guarded_stop_and_waits_for_health() -> None:
    script = _read("scripts/restart_smai_server.bat")
    implementation = _read("scripts/server_ops/restart_smai_server.ps1")

    assert "server_ops\\restart_smai_server.ps1" in script
    assert "stop_smai_server.bat" in implementation
    assert "start_smai_server.bat" in implementation
    assert "-Verb RunAs" in implementation
    assert "-WindowStyle Hidden" in implementation
    assert '"/k"' in implementation
    assert 'call "{0}" /console' in implementation
    assert "backend.server_ops.network --emit-json" in implementation
    assert "local_access_url" in implementation
    assert "AddSeconds(45)" in implementation
    assert "taskkill" not in implementation.lower()


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
