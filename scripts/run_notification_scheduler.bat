@echo off
setlocal
cd /d "%~dp0\.."

set "SMAI_PYTHON=%CD%\venv_SMAI\Scripts\python.exe"
if not exist "%SMAI_PYTHON%" (
    echo [SMAI] Python virtual environment was not found.
    exit /b 1
)

echo [SMAI] Starting notification scheduler...
"%SMAI_PYTHON%" -m backend.notifications.scheduler_runner --interval 30
exit /b %ERRORLEVEL%
