@echo off
setlocal ENABLEDELAYEDEXPANSION

REM ===========================
REM Smart Market AI Setup Script
REM ===========================

REM base directories
set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%\.."
for %%I in ("%REPO_ROOT%") do set "REPO_ROOT=%%~fI"
set "VENV_NAME=venv_SMAI"
set "VENV_DIR=%REPO_ROOT%\%VENV_NAME%"
set "BLACK_CACHE_DIR=%REPO_ROOT%\.black_cache"

REM requirements inside setup folder
set "REQ_MAIN=%SCRIPT_DIR%\requirements.txt"
set "REQ_DEV=%SCRIPT_DIR%\requirements-dev.txt"

if "%~1"=="/?" (
  echo Usage: setup\setup.bat
  echo.
  echo Creates %VENV_NAME%, installs dependencies, and configures BLACK_CACHE_DIR.
  exit /b 0
)
if /I "%~1"=="--help" (
  echo Usage: setup\setup.bat
  echo.
  echo Creates %VENV_NAME%, installs dependencies, and configures BLACK_CACHE_DIR.
  exit /b 0
)

REM ---------- Pick Python ----------
set "PYCMD="
where py >nul 2>&1
if not errorlevel 1 (
  py -3.11 -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)" >nul 2>&1
  if not errorlevel 1 set "PYCMD=py -3.11"
  if not defined PYCMD (
    py -3.12 -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)" >nul 2>&1
    if not errorlevel 1 set "PYCMD=py -3.12"
  )
)
if not defined PYCMD (
  if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "PYCMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
  ) else if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PYCMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
  )
)
if not defined PYCMD (
  where python >nul 2>&1
  if not errorlevel 1 (
    python -c "import sys; raise SystemExit(0 if sys.version_info[:2] in ((3, 11), (3, 12)) else 1)" >nul 2>&1
    if not errorlevel 1 set "PYCMD=python"
  )
)
if not defined PYCMD (
  echo [ERROR] Python 3.11 or 3.12 not found. Install from python.org and ensure PATH is set.
  exit /b 1
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

REM ---------- Configure tool cache ----------
echo [info] Configure Black cache: %BLACK_CACHE_DIR%
setx BLACK_CACHE_DIR "%BLACK_CACHE_DIR%" >nul
set "BLACK_CACHE_DIR=%BLACK_CACHE_DIR%"

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
echo.
echo Black cache:
echo   BLACK_CACHE_DIR=%BLACK_CACHE_DIR%

endlocal
