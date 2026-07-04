[CmdletBinding()]
param(
    [ValidateRange(1, 1440)]
    [int]$IntervalMinutes = 5,
    [switch]$Once,
    [switch]$NoRestart
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$python = Join-Path $projectRoot "venv_SMAI\Scripts\python.exe"
$startScript = Join-Path $projectRoot "scripts\start_smai_server.bat"
$logDir = Join-Path $projectRoot "logs\server_ops"
$logPath = Join-Path $logDir "watch_server.log"
$maintenanceLogPath = Join-Path $logDir "maintenance.log"

New-Item -ItemType Directory -Path $logDir -Force | Out-Null

function Write-WatchLog {
    param([string]$Message)
    $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -LiteralPath $logPath -Value $line -Encoding UTF8
    Write-Host $line
}

function Write-MaintenanceLog {
    param([string]$Message)
    $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -LiteralPath $maintenanceLogPath -Value $line -Encoding UTF8
}

function Test-SmaiListener {
    $connection = Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($null -eq $connection) { return $false }
    $process = Get-CimInstance Win32_Process `
        -Filter ("ProcessId=" + $connection.OwningProcess) `
        -ErrorAction SilentlyContinue
    if ($null -eq $process) { return $false }
    return ([string]$process.CommandLine -match "(?i)streamlit.+ui[\\/]+app\.py")
}

function Start-SmaiRecovery {
    Write-WatchLog "[WARN] SMAI listener is down. Starting recovery."
    Start-Process `
        -FilePath $env:ComSpec `
        -ArgumentList "/d", "/c", "`"$startScript`"" `
        -WorkingDirectory $projectRoot `
        -WindowStyle Hidden
    Start-Sleep -Seconds 20
    if (Test-SmaiListener) {
        Write-WatchLog "[OK] SMAI recovery succeeded."
    } else {
        Write-WatchLog "[ERROR] SMAI recovery did not open TCP 8501."
    }
}

function Invoke-MaintenanceCheck {
    & $python -m backend.server_ops.maintenance evaluate
    $decisionCode = $LASTEXITCODE
    if ($decisionCode -eq 10) {
        Write-WatchLog "[OK] Maintenance is not due."
        Write-MaintenanceLog "[OK] Uptime threshold has not been reached."
        return
    }
    if ($decisionCode -eq 20) {
        Write-WatchLog "[INFO] Maintenance restart deferred because SMAI is active or not safe."
        Write-MaintenanceLog "[DEFER] Active session, operation, or file lock is present."
        return
    }
    if ($decisionCode -ne 0) {
        Write-WatchLog "[ERROR] Maintenance state evaluation failed (exit=$decisionCode). Restart deferred."
        return
    }

    & $python -m backend.server_ops.maintenance notice
    if ($LASTEXITCODE -ne 0) {
        Write-WatchLog "[ERROR] Could not publish the maintenance notice. Restart deferred."
        return
    }
    Write-WatchLog "[INFO] Safe conditions met. Published 30-second maintenance notice."
    Write-MaintenanceLog "[NOTICE] Safe conditions met; final check in 30 seconds."
    Start-Sleep -Seconds 30

    & $python -m backend.server_ops.maintenance evaluate
    $finalCode = $LASTEXITCODE
    if ($finalCode -ne 0) {
        & $python -m backend.server_ops.maintenance clear-notice
        Write-WatchLog "[INFO] Maintenance restart cancelled after the final safety check."
        Write-MaintenanceLog "[DEFER] Final safety check changed; restart cancelled."
        return
    }
    if ($NoRestart) {
        & $python -m backend.server_ops.maintenance clear-notice
        Write-WatchLog "[TEST] Restart conditions met; Windows restart suppressed by -NoRestart."
        return
    }
    Write-WatchLog "[WARN] All safety checks passed. Restarting Windows for maintenance."
    Write-MaintenanceLog "[RESTART] All safety checks passed; Windows restart requested."
    & shutdown.exe /r /t 0 /d p:0:0 /c "SMAI scheduled maintenance restart"
}

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    Write-WatchLog "[ERROR] Python virtual environment was not found: $python"
    exit 1
}

Write-WatchLog "[START] SMAI server watcher started (interval=${IntervalMinutes}m)."
do {
    try {
        if (Test-SmaiListener) {
            Write-WatchLog "[OK] Streamlit process and TCP 8501 listener are healthy."
            Invoke-MaintenanceCheck
        } else {
            Start-SmaiRecovery
        }
    } catch {
        Write-WatchLog ("[ERROR] Watch cycle failed: " + $_.Exception.Message)
    }
    if (-not $Once) {
        Start-Sleep -Seconds ($IntervalMinutes * 60)
    }
} while (-not $Once)
