@echo off
setlocal
cd /d "%~dp0\.."

set "SMAI_PYTHON=%CD%\venv_SMAI\Scripts\python.exe"
if not exist "%SMAI_PYTHON%" (
    echo [SMAI] Python virtual environment was not found:
    echo        %SMAI_PYTHON%
    echo [SMAI] Create venv_SMAI or use the normal project setup first.
    pause
    exit /b 1
)

echo [SMAI] Starting LAN access on http://0.0.0.0:8501
echo [SMAI] From this PC, open http://localhost:8501
echo [SMAI] Use only on a trusted private network. Do not expose port 8501 to the Internet.
"%SMAI_PYTHON%" -m streamlit run ui/app.py --server.address 0.0.0.0 --server.port 8501

set "SMAI_EXIT_CODE=%ERRORLEVEL%"
echo.
echo [SMAI] Streamlit stopped with exit code %SMAI_EXIT_CODE%.
pause
exit /b %SMAI_EXIT_CODE%

