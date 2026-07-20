@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

set "SMAI_ROOT=%CD%"
set "SMAI_PYTHON=%SMAI_ROOT%\venv_SMAI\Scripts\python.exe"
if not defined SMAI_CONFIG_FILE set "SMAI_CONFIG_FILE=%SMAI_ROOT%\config\server.yaml"

if not exist "%SMAI_PYTHON%" (
    echo [SMAI] Python virtual environment was not found:
    echo        %SMAI_PYTHON%
    echo [SMAI] Create venv_SMAI or use the normal project setup first.
    exit /b 1
)

for /f "usebackq delims=" %%I in (`"%SMAI_PYTHON%" -m backend.server_ops.network --emit-batch`) do %%I
if errorlevel 1 (
    echo [ERROR] SMAI MagicDNS URL could not be resolved.
    echo [SMAI] Check config\server.yaml or SMAI_TAILSCALE_HOSTNAME.
    exit /b 2
)

echo [SMAI] Starting SMAI Main Application...
echo [SMAI] Listening on all network interfaces: 0.0.0.0:%SMAI_MAIN_PORT%
echo [SMAI] Static serving: enabled
echo [SMAI] WebSocket compression: enabled
echo [SMAI] Duplicate-safe shared launcher: enabled
echo.
echo [SMAI] Normal access from another PC, iPad, or smartphone:
echo        %SMAI_MAIN_APPLICATION_URL%
echo [SMAI] Start Tailscale on the connecting device before opening this URL.
echo.
echo [SMAI] Server PC local check:
echo        %SMAI_LOCAL_APPLICATION_URL%
echo.
echo [SMAI] Do not expose port %SMAI_MAIN_PORT% to the Internet.
echo.

"%SMAI_PYTHON%" -m backend.server_ops.launcher ^
  --browser-address localhost

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
