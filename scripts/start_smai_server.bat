@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

set "SMAI_ROOT=%CD%"
set "SMAI_PYTHON=%SMAI_ROOT%\venv_SMAI\Scripts\python.exe"
set "SMAI_LOG_DIR=%SMAI_ROOT%\logs\server_ops"
if not defined SMAI_PERFORMANCE_PROFILE set "SMAI_PERFORMANCE_PROFILE=workstation"
set "SMAI_ASSISTANT_GATEWAY_AUTOSTART=1"

if not exist "%SMAI_LOG_DIR%" mkdir "%SMAI_LOG_DIR%"
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "SMAI_RUN_ID=%%I"
set "SMAI_LOG_FILE=%SMAI_LOG_DIR%\smai_server_%SMAI_RUN_ID%.log"
set "SMAI_AUTOSTART_LOG=%SMAI_LOG_DIR%\autostart.log"
>> "%SMAI_AUTOSTART_LOG%" echo(%DATE% %TIME% [START] start_smai_server.bat invoked.

call :log "============================================================"
call :log "[SMAI] Scheduled LAN server startup"
call :log "[SMAI] Root: %SMAI_ROOT%"
call :log "[SMAI] Performance profile: %SMAI_PERFORMANCE_PROFILE%"
call :log "[SMAI] Assistant Gateway autostart: %SMAI_ASSISTANT_GATEWAY_AUTOSTART%"
call :log "[SMAI] Streamlit config: static serving=enabled, websocket compression=enabled"
call :log "[SMAI] Duplicate-safe shared launcher: enabled"

if not exist "%SMAI_PYTHON%" (
    call :log "[ERROR] Python virtual environment was not found: %SMAI_PYTHON%"
    exit /b 1
)

set "SMAI_LAN_IP="
for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "Get-NetIPConfiguration -ErrorAction SilentlyContinue | Where-Object { $_.IPv4DefaultGateway -ne $null -and $_.IPv4Address -ne $null } | Select-Object -First 1 -ExpandProperty IPv4Address | Select-Object -ExpandProperty IPAddress" 2^>nul`) do set "SMAI_LAN_IP=%%I"
if "%SMAI_LAN_IP%"=="" set "SMAI_LAN_IP=localhost"

call :log "[SMAI] Local URL: http://localhost:8501"
call :log "[SMAI] LAN URL: http://%SMAI_LAN_IP%:8501"
set "SMAI_TAILSCALE_IP="
for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "$command=Get-Command tailscale -ErrorAction SilentlyContinue; if($command){tailscale ip -4 2^>$null | Select-Object -First 1}" 2^>nul`) do set "SMAI_TAILSCALE_IP=%%I"
if not "%SMAI_TAILSCALE_IP%"=="" call :log "[SMAI] Tailscale URL: http://%SMAI_TAILSCALE_IP%:8501"
call :log "[SMAI] Listening on 0.0.0.0:8501 (bind address; do not open 0.0.0.0 in a browser)"
call :log "[SMAI] Starting Streamlit..."
>> "%SMAI_AUTOSTART_LOG%" echo(%DATE% %TIME% [OK] Starting SMAI Streamlit server.
"%SMAI_PYTHON%" -m backend.server_ops.launcher ^
  --browser-address %SMAI_LAN_IP% ^
  --maintenance-startup >> "%SMAI_LOG_FILE%" 2>&1

set "SMAI_EXIT_CODE=%ERRORLEVEL%"
call :log "[SMAI] Streamlit stopped with exit code %SMAI_EXIT_CODE%."
exit /b %SMAI_EXIT_CODE%

:log
echo %~1
>> "%SMAI_LOG_FILE%" echo(%~1
exit /b 0
