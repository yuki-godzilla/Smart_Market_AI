from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_if_due_script_uses_state_gate_lock_and_existing_runner() -> None:
    script = _read("scripts/run_symbol_maintenance_if_due.bat")

    assert "tools\\symbol_maintenance_state.py begin" in script
    assert "tools\\symbol_maintenance_state.py finish" in script
    assert "data\\ops\\symbol_maintenance_state.json" in script
    assert "data\\ops\\symbol_maintenance.lock" in script
    assert 'set "SMAI_LOG_DIR=logs\\maintenance"' in script
    assert "symbol_maintenance_if_due_%SMAI_RUN_ID%.log" in script
    assert "call run_symbol_universe_import_all.bat" in script
    assert "Maintenance is not due. Skipping." in script
    assert "retry cooldown" in script
    assert "Reports: reports\\YYYY-MM-DD_HHMM\\" in script
    assert '>> "%SMAI_LOG_FILE%" echo(%~1' in script


def test_manual_script_warns_prompts_and_supports_force() -> None:
    script = _read("scripts/run_symbol_maintenance_manual.bat")

    assert 'if /i "%~1"=="/force"' in script
    assert "EnableDelayedExpansion" in script
    assert "set /p" in script
    assert 'if /i "!SMAI_CONFIRM!"=="y" goto :confirmed' in script
    assert 'if /i "!SMAI_CONFIRM!"=="yes" goto :confirmed' in script
    assert "heavy maintenance operation" in script
    assert "external data retrieval" in script
    assert "symbol_universe.csv" in script
    assert "Reports: reports\\YYYY-MM-DD_HHMM\\" in script
    assert "--force" in script
    assert "call run_symbol_universe_import_all.bat" in script
    assert '>> "%SMAI_LOG_FILE%" echo(%~1' in script


def test_maintenance_task_is_delayed_guarded_and_indirect() -> None:
    script = _read("scripts/register_symbol_maintenance_if_due_task.ps1")

    assert '"SmartMarketAI-Symbol-Maintenance-IfDue"' in script
    assert '$trigger.Delay = "PT10M"' in script
    assert "-MultipleInstances IgnoreNew" in script
    assert "-RestartCount 1" in script
    assert "-RestartInterval (New-TimeSpan -Minutes 30)" in script
    assert "run_symbol_maintenance_if_due.bat" in script
    assert "run_symbol_universe_import_all.bat" in script
    assert "-Execute $env:ComSpec" in script


def test_maintenance_task_unregistration_is_idempotent() -> None:
    script = _read("scripts/unregister_symbol_maintenance_if_due_task.ps1")

    assert '"SmartMarketAI-Symbol-Maintenance-IfDue"' in script
    assert "Scheduled task is not registered" in script
    assert "Unregister-ScheduledTask" in script
