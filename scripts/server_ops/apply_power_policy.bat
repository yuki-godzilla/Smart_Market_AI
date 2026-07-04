@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0apply_power_policy.ps1"
exit /b %ERRORLEVEL%

