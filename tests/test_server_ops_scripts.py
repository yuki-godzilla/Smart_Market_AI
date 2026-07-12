from pathlib import Path


def test_server_watcher_uses_two_stage_safe_restart_check() -> None:
    script = Path("scripts/server_ops/watch_smai_server.ps1").read_text(encoding="utf-8")

    assert "Get-NetTCPConnection -LocalPort 8501" in script
    assert "backend.server_ops.maintenance evaluate" in script
    assert "Start-Sleep -Seconds 30" in script
    assert script.count("backend.server_ops.maintenance evaluate") == 2
    assert "Restart-SmaiService" in script
    assert "Stop-Process -Id $connection.OwningProcess" in script
    assert "shutdown.exe" not in script
    assert "-NoRestart" in script


def test_autostart_registers_server_and_watcher_at_startup() -> None:
    script = Path("scripts/server_ops/register_smai_autostart_task.ps1").read_text(encoding="utf-8")

    assert "SmartMarketAI-Server-Autostart" in script
    assert "SmartMarketAI-Server-Watch" in script
    assert "New-ScheduledTaskTrigger -AtStartup" in script
    assert "New-ScheduledTaskTrigger -AtLogOn" in script
    assert "-LogonType Interactive" in script
    assert "MultipleInstances IgnoreNew" in script
    assert "start_smai_server.bat" in script


def test_power_policy_only_changes_ac_timeouts() -> None:
    script = Path("scripts/server_ops/apply_power_policy.ps1").read_text(encoding="utf-8")

    assert "monitor-timeout-ac 10" in script
    assert "standby-timeout-ac 0" in script
    assert "hibernate-timeout-ac 0" in script
    assert "powercfg.exe /hibernate off" in script
    assert "-timeout-dc" not in script
