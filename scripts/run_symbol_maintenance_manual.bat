@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0\.."

set "SMAI_FORCE=0"
if /i "%~1"=="/force" set "SMAI_FORCE=1"

echo ============================================================
echo [SMAI] Manual symbol maintenance
echo.
echo This is a heavy maintenance operation with external data retrieval.
echo It can update data\marketdata\symbol_universe.csv and metadata.
echo Backups: data\marketdata\backup\
echo Reports: reports\YYYY-MM-DD_HHMM\
echo Logs: logs\maintenance\
echo The SMAI LAN server is managed separately and will not be stopped.
echo ============================================================
echo.

if "%SMAI_FORCE%"=="1" goto :confirmed
set /p "SMAI_CONFIRM=Run symbol maintenance now? [y/N]: "
if /i "!SMAI_CONFIRM!"=="y" goto :confirmed
if /i "!SMAI_CONFIRM!"=="yes" goto :confirmed
echo [SMAI] Cancelled.
exit /b 0

:confirmed

set "SMAI_ROOT=%CD%"
set "SMAI_PYTHON=%SMAI_ROOT%\venv_SMAI\Scripts\python.exe"
set "SMAI_STATE_FILE=data\ops\symbol_maintenance_state.json"
set "SMAI_LOCK_FILE=data\ops\symbol_maintenance.lock"
set "SMAI_LOG_DIR=logs\maintenance"
if not defined SMAI_SYMBOL_MAINTENANCE_INTERVAL_DAYS set "SMAI_SYMBOL_MAINTENANCE_INTERVAL_DAYS=7"
if not defined SMAI_SYMBOL_MAINTENANCE_RETRY_COOLDOWN_HOURS set "SMAI_SYMBOL_MAINTENANCE_RETRY_COOLDOWN_HOURS=24"

if not exist "%SMAI_LOG_DIR%" mkdir "%SMAI_LOG_DIR%"
if not exist "data\ops" mkdir "data\ops"
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "SMAI_RUN_ID=%%I"
set "SMAI_LOG_FILE=%SMAI_LOG_DIR%\symbol_maintenance_%SMAI_RUN_ID%.log"

call :log "[SMAI] Manual symbol maintenance started."
call :log "[SMAI] Started at: %DATE% %TIME%"
call :log "[SMAI] State file: %SMAI_STATE_FILE%"
call :log "[SMAI] Lock file: %SMAI_LOCK_FILE%"
call :log "[SMAI] Log file: %SMAI_LOG_FILE%"

if not exist "%SMAI_PYTHON%" (
    call :log "[ERROR] Python virtual environment was not found: %SMAI_PYTHON%"
    exit /b 1
)
if not exist "run_symbol_universe_import_all.bat" (
    call :log "[ERROR] Maintenance runner was not found: run_symbol_universe_import_all.bat"
    exit /b 1
)

"%SMAI_PYTHON%" tools\symbol_maintenance_state.py begin ^
  --state "%SMAI_STATE_FILE%" ^
  --lock "%SMAI_LOCK_FILE%" ^
  --log-path "%SMAI_LOG_FILE%" ^
  --force >> "%SMAI_LOG_FILE%" 2>&1
set "SMAI_DECISION_EXIT=%ERRORLEVEL%"

if "%SMAI_DECISION_EXIT%"=="12" (
    call :log "[SMAI] Maintenance lock exists. Duplicate execution was blocked."
    exit /b 0
)
if not "%SMAI_DECISION_EXIT%"=="0" (
    call :log "[ERROR] Maintenance start failed with exit code %SMAI_DECISION_EXIT%."
    exit /b %SMAI_DECISION_EXIT%
)

call :log "[SMAI] Starting run_symbol_universe_import_all.bat..."
call run_symbol_universe_import_all.bat >> "%SMAI_LOG_FILE%" 2>&1
set "SMAI_MAINTENANCE_EXIT=%ERRORLEVEL%"

"%SMAI_PYTHON%" tools\symbol_maintenance_state.py finish ^
  --state "%SMAI_STATE_FILE%" ^
  --lock "%SMAI_LOCK_FILE%" ^
  --log-path "%SMAI_LOG_FILE%" ^
  --exit-code %SMAI_MAINTENANCE_EXIT% >> "%SMAI_LOG_FILE%" 2>&1
set "SMAI_STATE_EXIT=%ERRORLEVEL%"

if not "%SMAI_STATE_EXIT%"=="0" (
    call :log "[ERROR] State update failed with exit code %SMAI_STATE_EXIT%. Lock was kept for safety."
    exit /b %SMAI_STATE_EXIT%
)

call :log "[SMAI] Finished at: %DATE% %TIME%"
call :log "[SMAI] Maintenance exit code: %SMAI_MAINTENANCE_EXIT%"
call :log "[SMAI] Reports: reports\YYYY-MM-DD_HHMM\"
call :log "[SMAI] Backups: data\marketdata\backup\"
exit /b %SMAI_MAINTENANCE_EXIT%

:log
echo %~1
>> "%SMAI_LOG_FILE%" echo(%~1
exit /b 0
