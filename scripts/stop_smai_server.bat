@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

if /i "%~1"=="/quiet" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0server_ops\stop_smai_server.ps1" -Quiet
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0server_ops\stop_smai_server.ps1"
)
exit /b %ERRORLEVEL%
