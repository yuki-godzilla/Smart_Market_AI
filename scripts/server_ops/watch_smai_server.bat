@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0watch_smai_server.ps1"
exit /b %ERRORLEVEL%

