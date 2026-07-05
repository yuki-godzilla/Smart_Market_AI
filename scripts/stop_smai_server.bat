@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

set "SMAI_QUIET=0"
if /i "%~1"=="/quiet" set "SMAI_QUIET=1"

powershell -NoProfile -Command "$quiet=('%SMAI_QUIET%' -eq '1'); $c=Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1; if(-not $c){Write-Output '[INFO] No process is listening on TCP 8501.'; exit 0}; $p=Get-CimInstance Win32_Process -Filter ('ProcessId=' + $c.OwningProcess) -ErrorAction SilentlyContinue; if(-not $p){Write-Output ('[ERROR] Could not inspect PID ' + $c.OwningProcess + '.'); exit 2}; $cmd=[string]$p.CommandLine; Write-Output ('[SMAI] Target PID: ' + $p.ProcessId); Write-Output ('[SMAI] CommandLine: ' + $cmd); if($cmd -notmatch '(?i)streamlit.+ui[\\/]+app\.py'){Write-Output '[ERROR] The listener does not look like the SMAI Streamlit server. Nothing was stopped.'; exit 3}; if(-not $quiet){$answer=Read-Host 'Stop this SMAI server? [y/N]'; if($answer -notmatch '^(?i)y(es)?$'){Write-Output '[INFO] Cancelled.'; exit 4}}; $request=Join-Path '%CD%' 'data\ops\server_ops\streamlit.stop'; New-Item -ItemType Directory -Path (Split-Path $request) -Force | Out-Null; Set-Content -LiteralPath $request -Value 'manual_stop' -Encoding ASCII; try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop } catch { Remove-Item -LiteralPath $request -Force -ErrorAction SilentlyContinue; throw }; Write-Output ('[OK] Stopped SMAI server PID ' + $p.ProcessId + ' and its resilient launcher.'); exit 0"
exit /b %ERRORLEVEL%
