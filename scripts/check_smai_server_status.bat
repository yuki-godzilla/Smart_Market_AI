@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

set "SMAI_LAN_IP="
for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "Get-NetIPConfiguration -ErrorAction SilentlyContinue | Where-Object { $_.IPv4DefaultGateway -ne $null -and $_.IPv4Address -ne $null } | Select-Object -First 1 -ExpandProperty IPv4Address | Select-Object -ExpandProperty IPAddress" 2^>nul`) do set "SMAI_LAN_IP=%%I"

echo [SMAI] Server status
echo ====================
call :check_url "SMAI Streamlit" "http://localhost:8501/_stcore/health"
set "SMAI_STATUS=%ERRORLEVEL%"

if exist "%USERPROFILE%\workspace\SMAI_Server_Analytics\run_health.bat" (
    call "%USERPROFILE%\workspace\SMAI_Server_Analytics\run_health.bat"
)

if not "%SMAI_LAN_IP%"=="" (
    echo [INFO] iPhone/iPad URL: http://%SMAI_LAN_IP%:8501
) else (
    echo [WARN] LAN IPv4 address could not be detected. Run ipconfig to check it.
)

echo.
echo [SMAI] Optional local dependencies
call :check_url "Assistant Gateway" "http://127.0.0.1:8088/health"
call :check_url "Ollama" "http://127.0.0.1:11434/api/tags"

echo.
if "%SMAI_STATUS%"=="0" (
    echo [OK] SMAI is available at http://localhost:8501
) else (
    echo [NG] SMAI is not responding at http://localhost:8501
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
