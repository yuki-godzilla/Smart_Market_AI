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

call :log "============================================================"
call :log "[SMAI] Scheduled LAN server startup"
call :log "[SMAI] Root: %SMAI_ROOT%"
call :log "[SMAI] Performance profile: %SMAI_PERFORMANCE_PROFILE%"
call :log "[SMAI] Assistant Gateway autostart: %SMAI_ASSISTANT_GATEWAY_AUTOSTART%"

if not exist "%SMAI_PYTHON%" (
    call :log "[ERROR] Python virtual environment was not found: %SMAI_PYTHON%"
    exit /b 1
)

powershell -NoProfile -Command "$c=Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1; if(-not $c){exit 0}; $p=Get-CimInstance Win32_Process -Filter ('ProcessId=' + $c.OwningProcess) -ErrorAction SilentlyContinue; $cmd=[string]$p.CommandLine; Write-Output ('[SMAI] Port 8501 is already listening. PID=' + $c.OwningProcess); Write-Output ('[SMAI] CommandLine: ' + $cmd); if($cmd -match '(?i)streamlit.+ui[\\/]+app\.py'){exit 10}else{exit 11}" >> "%SMAI_LOG_FILE%" 2>&1
set "SMAI_PORT_STATUS=%ERRORLEVEL%"

if "%SMAI_PORT_STATUS%"=="10" (
    call :log "[OK] SMAI is already running. A second instance will not be started."
    exit /b 0
)
if "%SMAI_PORT_STATUS%"=="11" (
    call :log "[ERROR] Port 8501 is used by another process. SMAI was not started."
    exit /b 2
)
if not "%SMAI_PORT_STATUS%"=="0" (
    call :log "[ERROR] Port inspection failed with exit code %SMAI_PORT_STATUS%."
    exit /b %SMAI_PORT_STATUS%
)

set "SMAI_LAN_IP="
for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "Get-NetIPConfiguration -ErrorAction SilentlyContinue | Where-Object { $_.IPv4DefaultGateway -ne $null -and $_.IPv4Address -ne $null } | Select-Object -First 1 -ExpandProperty IPv4Address | Select-Object -ExpandProperty IPAddress" 2^>nul`) do set "SMAI_LAN_IP=%%I"
if "%SMAI_LAN_IP%"=="" set "SMAI_LAN_IP=localhost"

call :log "[SMAI] Local URL: http://localhost:8501"
call :log "[SMAI] LAN URL: http://%SMAI_LAN_IP%:8501"
call :log "[SMAI] Listening on 0.0.0.0:8501 (bind address; do not open 0.0.0.0 in a browser)"
call :log "[SMAI] Starting Streamlit..."

"%SMAI_PYTHON%" -m streamlit run ui/app.py ^
  --server.address 0.0.0.0 ^
  --server.port 8501 ^
  --server.headless true ^
  --browser.serverAddress %SMAI_LAN_IP% >> "%SMAI_LOG_FILE%" 2>&1

set "SMAI_EXIT_CODE=%ERRORLEVEL%"
call :log "[SMAI] Streamlit stopped with exit code %SMAI_EXIT_CODE%."
exit /b %SMAI_EXIT_CODE%

:log
echo %~1
>> "%SMAI_LOG_FILE%" echo(%~1
exit /b 0
