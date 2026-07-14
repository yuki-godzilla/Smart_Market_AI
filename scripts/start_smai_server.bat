@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

set "SMAI_CONSOLE_MODE=0"
if /i "%~1"=="/console" set "SMAI_CONSOLE_MODE=1"
set "SMAI_ROOT=%CD%"
set "SMAI_PYTHON=%SMAI_ROOT%\venv_SMAI\Scripts\python.exe"
set "SMAI_LOG_DIR=%SMAI_ROOT%\logs\server_ops"
if not defined SMAI_CONFIG_FILE set "SMAI_CONFIG_FILE=%SMAI_ROOT%\config\server.yaml"
if not defined SMAI_PERFORMANCE_PROFILE set "SMAI_PERFORMANCE_PROFILE=workstation"
set "SMAI_ASSISTANT_GATEWAY_AUTOSTART=1"

if not exist "%SMAI_LOG_DIR%" mkdir "%SMAI_LOG_DIR%"
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "SMAI_RUN_ID=%%I"
set "SMAI_LOG_FILE=%SMAI_LOG_DIR%\smai_server_%SMAI_RUN_ID%.log"
set "SMAI_AUTOSTART_LOG=%SMAI_LOG_DIR%\autostart.log"
>> "%SMAI_AUTOSTART_LOG%" echo(%DATE% %TIME% [START] start_smai_server.bat invoked.

call :log "============================================================"
if "%SMAI_CONSOLE_MODE%"=="1" (
    call :log "[SMAI] Interactive Main Application server console"
) else (
    call :log "[SMAI] Scheduled Main Application server startup"
)
call :log "[SMAI] Root: %SMAI_ROOT%"
call :log "[SMAI] Performance profile: %SMAI_PERFORMANCE_PROFILE%"
call :log "[SMAI] Assistant Gateway autostart: %SMAI_ASSISTANT_GATEWAY_AUTOSTART%"
call :log "[SMAI] Streamlit config: static serving=enabled, websocket compression=enabled"
call :log "[SMAI] Duplicate-safe shared launcher: enabled"

if not exist "%SMAI_PYTHON%" (
    call :log "[ERROR] Python virtual environment was not found: %SMAI_PYTHON%"
    exit /b 1
)

for /f "usebackq delims=" %%I in (`"%SMAI_PYTHON%" -m backend.server_ops.network --emit-batch`) do %%I
if errorlevel 1 (
    call :log "[ERROR] SMAI MagicDNS URL could not be resolved. Check config/server.yaml or SMAI_TAILSCALE_HOSTNAME."
    exit /b 2
)

call :log "[SMAI] SMAI Main Application started."
call :log "[SMAI] Normal access: %SMAI_MAIN_APPLICATION_URL%"
call :log "[SMAI] Server-local check: %SMAI_LOCAL_APPLICATION_URL%"
call :log "[SMAI] Start Tailscale on the connecting device before opening the normal access URL."
call :log "[SMAI] Listening on 0.0.0.0:%SMAI_MAIN_PORT% (bind address; do not open 0.0.0.0 in a browser)"
call :log "[SMAI] Do not expose this port to the Internet."
if "%SMAI_CONSOLE_MODE%"=="1" call :log "[SMAI] Keep this window open while SMAI is running."
call :log "[SMAI] Starting Streamlit..."
>> "%SMAI_AUTOSTART_LOG%" echo(%DATE% %TIME% [OK] Starting SMAI Streamlit server.
if "%SMAI_CONSOLE_MODE%"=="1" (
    "%SMAI_PYTHON%" -m backend.server_ops.launcher --browser-address localhost --maintenance-startup --resilient --visible-console
) else (
    "%SMAI_PYTHON%" -m backend.server_ops.launcher ^
      --browser-address localhost ^
      --maintenance-startup ^
      --resilient >> "%SMAI_LOG_FILE%" 2>&1
)

set "SMAI_EXIT_CODE=%ERRORLEVEL%"
if "%SMAI_EXIT_CODE%"=="10" (
    call :log "[SMAI] Existing SMAI server remains available."
    exit /b 0
)
call :log "[SMAI] Streamlit stopped with exit code %SMAI_EXIT_CODE%."
exit /b %SMAI_EXIT_CODE%

:log
echo %~1
>> "%SMAI_LOG_FILE%" echo(%~1
exit /b 0
