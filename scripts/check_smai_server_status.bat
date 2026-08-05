@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

set "SMAI_ROOT=%CD%"
set "SMAI_PYTHON=%SMAI_ROOT%\venv_SMAI\Scripts\python.exe"
if not defined SMAI_CONFIG_FILE set "SMAI_CONFIG_FILE=%SMAI_ROOT%\config\server.yaml"
if not exist "%SMAI_PYTHON%" (
    echo [ERROR] Python virtual environment was not found: %SMAI_PYTHON%
    exit /b 1
)
for /f "usebackq delims=" %%I in (`"%SMAI_PYTHON%" -m backend.server_ops.network --emit-batch`) do %%I
if errorlevel 1 (
    echo [ERROR] SMAI MagicDNS URL could not be resolved. Check config\server.yaml or SMAI_TAILSCALE_HOSTNAME.
    exit /b 2
)

echo [SMAI] Server status
echo ====================
call :check_url "SMAI Streamlit" "%SMAI_LOCAL_APPLICATION_URL%/_stcore/health"
set "SMAI_STATUS=%ERRORLEVEL%"

if exist "%USERPROFILE%\workspace\SMAI_Server_Analytics\run_health.bat" (
    call "%USERPROFILE%\workspace\SMAI_Server_Analytics\run_health.bat"
)

echo [INFO] Normal access URL: %SMAI_MAIN_APPLICATION_URL%
echo [INFO] Start Tailscale on the connecting device before opening the normal access URL.

echo.
echo [SMAI] Optional local dependencies
call :check_url "Assistant Gateway" "http://127.0.0.1:8088/health"
call :check_url "Ollama" "http://127.0.0.1:11434/api/tags"

echo.
if "%SMAI_STATUS%"=="0" (
    echo [OK] SMAI is available at %SMAI_LOCAL_APPLICATION_URL%
) else (
    echo [NG] SMAI is not responding at %SMAI_LOCAL_APPLICATION_URL%
)
exit /b %SMAI_STATUS%

:check_url
powershell -NoProfile -Command "try { $r=Invoke-WebRequest -UseBasicParsing -Uri '%~2' -TimeoutSec 3; if($r.StatusCode -ge 200 -and $r.StatusCode -lt 400){exit 0}else{exit 1} } catch { exit 1 }"
if errorlevel 1 (
    echo [NG] %~1 - %~2
    exit /b 1
)
echo [OK] %~1 - %~2
exit /b 0
