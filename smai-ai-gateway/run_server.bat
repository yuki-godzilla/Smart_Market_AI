@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" (
  call ".venv\Scripts\activate.bat"
) else if exist "..\venv_SMAI\Scripts\activate.bat" (
  call "..\venv_SMAI\Scripts\activate.bat"
)

uvicorn app.main:app --reload --host 127.0.0.1 --port 8088
