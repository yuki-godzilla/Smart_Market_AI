@echo off
setlocal
cd /d "%~dp0\.."

set "SMAI_PYTHON=%CD%\venv_SMAI\Scripts\python.exe"
if not exist "%SMAI_PYTHON%" (
    echo [SMAI] Python virtual environment was not found:
    echo        %SMAI_PYTHON%
    echo [SMAI] Create venv_SMAI or use the normal project setup first.
    exit /b 1
)

set "SMAI_LAN_IP="
set "SMAI_LAN_IP_FOUND=1"
for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "Get-NetIPConfiguration -ErrorAction SilentlyContinue | Where-Object { $_.IPv4DefaultGateway -ne $null -and $_.IPv4Address -ne $null } | Select-Object -First 1 -ExpandProperty IPv4Address | Select-Object -ExpandProperty IPAddress" 2^>nul`) do set "SMAI_LAN_IP=%%I"

if "%SMAI_LAN_IP%"=="" (
    set "SMAI_LAN_IP=localhost"
    set "SMAI_LAN_IP_FOUND=0"
)

echo [SMAI] Starting LAN server...
echo [SMAI] Listening on all network interfaces: 0.0.0.0:8501
echo [SMAI] Static serving: enabled
echo [SMAI] WebSocket compression: enabled
echo [SMAI] Duplicate-safe shared launcher: enabled
echo.
echo [SMAI] From this PC, open:
echo        http://localhost:8501
echo.
if "%SMAI_LAN_IP_FOUND%"=="1" (
    echo [SMAI] From iPhone / iPad on the same Wi-Fi, open:
    echo        http://%SMAI_LAN_IP%:8501
) else (
    echo [SMAI] LAN IPv4 address could not be detected automatically.
    echo [SMAI] Streamlit URL display will fall back to http://localhost:8501
    echo [SMAI] Run ipconfig to find the Desktop PC IPv4 address for mobile access.
)
for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "$command=Get-Command tailscale -ErrorAction SilentlyContinue; if($command){tailscale ip -4 2^>$null | Select-Object -First 1}" 2^>nul`) do set "SMAI_TAILSCALE_IP=%%I"
if not "%SMAI_TAILSCALE_IP%"=="" (
    echo.
    echo [SMAI] From a trusted Tailscale device, open:
    echo        http://%SMAI_TAILSCALE_IP%:8501
)
echo.
echo [SMAI] If the mobile URL does not open, check:
echo        1. iPhone/iPad is on the same Wi-Fi
echo        2. Windows Firewall allows TCP 8501 on private networks
echo        3. The displayed IP is your Desktop PC LAN IP
echo.
echo [SMAI] Use only on a trusted private network.
echo [SMAI] Do not expose port 8501 to the Internet.
echo.

"%SMAI_PYTHON%" -m backend.server_ops.launcher ^
  --browser-address %SMAI_LAN_IP%

set "SMAI_EXIT_CODE=%ERRORLEVEL%"
echo.
if "%SMAI_EXIT_CODE%"=="10" (
    echo [SMAI] Existing SMAI server remains available. Nothing was stopped.
    exit /b 0
)
if "%SMAI_EXIT_CODE%"=="130" (
    echo [SMAI] Streamlit stopped by user.
    exit /b 0
)
if "%SMAI_EXIT_CODE%"=="0" (
    echo [SMAI] Streamlit stopped normally.
    exit /b 0
)
echo [SMAI] Streamlit exited with error code %SMAI_EXIT_CODE%.
exit /b %SMAI_EXIT_CODE%
