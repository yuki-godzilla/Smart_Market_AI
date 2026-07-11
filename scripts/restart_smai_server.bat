@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0server_ops\restart_smai_server.ps1"
exit /b %ERRORLEVEL%
