from pathlib import Path


def test_symbol_import_reports_are_grouped_by_execution_minute() -> None:
    script = Path("run_symbol_universe_import_all.bat").read_text(encoding="utf-8")
    expected_run_slot = (
        'set "RUN_SLOT=%RUN_ID:~0,4%-%RUN_ID:~4,2%-%RUN_ID:~6,2%_%RUN_ID:~9,4%"'
    )

    assert expected_run_slot in script
    assert 'set "REPORT_DIR=reports\\%RUN_SLOT%"' in script
    assert 'if not exist "%REPORT_DIR%" mkdir "%REPORT_DIR%"' in script
    assert "--report %REPORT_DIR%\\" in script
    assert "--manifest %REPORT_DIR%\\" in script
