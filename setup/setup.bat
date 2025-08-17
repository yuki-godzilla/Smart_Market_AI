@echo off
setlocal ENABLEDELAYEDEXPANSION

REM ===========================
REM Smart Market AI Setup Script
REM ===========================

REM base directories
set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%\.."
set "VENV_NAME=venv_SMAI"
set "VENV_DIR=%REPO_ROOT%\%VENV_NAME%"

REM requirements inside setup folder
set "REQ_MAIN=%SCRIPT_DIR%\requirements.txt"
set "REQ_DEV=%SCRIPT_DIR%\requirements-dev.txt"

REM ---------- Pick Python ----------
set "PYCMD=py -3.11"
where py >nul 2>&1 || (
  if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "PYCMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
  ) else (
    echo [ERROR] Python 3.11 not found. Install from python.org and ensure PATH is set.
    exit /b 1
  )
)

echo [0/6] Repo root: %REPO_ROOT%
echo        Using: %PYCMD%

REM ---------- Check requirements ----------
if not exist "%REQ_MAIN%" (
  echo [ERROR] Not found: %REQ_MAIN%
  exit /b 1
)
if not exist "%REQ_DEV%" (
  echo [ERROR] Not found: %REQ_DEV%
  exit /b 1
)

REM ---------- Create venv ----------
if exist "%VENV_DIR%" (
  echo [info] Removing existing venv: %VENV_DIR%
  rmdir /s /q "%VENV_DIR%"
)
echo [1/6] Create virtual environment: %VENV_DIR% ...
%PYCMD% -m venv "%VENV_DIR%" || (echo [ERROR] Failed to create venv & exit /b 1)

REM ---------- Activate ----------
echo [2/6] Activate virtual environment...
call "%VENV_DIR%\Scripts\activate.bat" || (echo [ERROR] Failed to activate venv & exit /b 1)

REM ---------- Upgrade pip ----------
echo [3/6] Upgrade pip...
python -m pip install --upgrade pip || (echo [ERROR] pip upgrade failed & exit /b 1)

REM ---------- Install deps ----------
echo [4/6] Install dependencies from setup/...
pip install -r "%REQ_MAIN%" -r "%REQ_DEV%" || (echo [ERROR] Dependency install failed & exit /b 1)

REM ---------- Verify ----------
echo [5/6] Verify tools...
ruff --version && black --version && pytest --version || (echo [ERROR] Tool verification failed & exit /b 1)

REM ---------- Done ----------
echo [6/6] Setup finished successfully!
echo.
echo To activate later:
echo   %VENV_NAME%\Scripts\Activate.ps1   (PowerShell)
echo   %VENV_NAME%\Scripts\activate.bat   (cmd)

endlocal
