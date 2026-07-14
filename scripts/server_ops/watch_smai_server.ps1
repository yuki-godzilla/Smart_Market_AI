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
$supervisorStopRequestPath = Join-Path $projectRoot "data\ops\server_ops\streamlit.stop"
if ([string]::IsNullOrWhiteSpace($env:SMAI_CONFIG_FILE)) {
    $env:SMAI_CONFIG_FILE = Join-Path $projectRoot "config\server.yaml"
}

New-Item -ItemType Directory -Path $logDir -Force | Out-Null

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    Write-Error "SMAI Python environment was not found: $python"
    exit 1
}
$network = & $python -m backend.server_ops.network --emit-json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or $null -eq $network) {
    Write-Error "SMAI network settings could not be resolved. Watcher was not started."
    exit 1
}
$mainPort = [int]$network.port

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
    $connection = Get-NetTCPConnection -LocalPort $mainPort -State Listen -ErrorAction SilentlyContinue |
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
        Write-WatchLog "[ERROR] SMAI recovery did not open TCP $mainPort."
    }
}

function Restart-SmaiService {
    $connection = Get-NetTCPConnection -LocalPort $mainPort -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($null -eq $connection) {
        Write-WatchLog "[INFO] SMAI listener already stopped before maintenance restart."
    } else {
        $process = Get-CimInstance Win32_Process `
            -Filter ("ProcessId=" + $connection.OwningProcess) `
            -ErrorAction SilentlyContinue
        if ($null -eq $process -or [string]$process.CommandLine -notmatch "(?i)streamlit.+ui[\\/]+app\.py") {
            throw "TCP $mainPort listener is not the expected SMAI Streamlit process."
        }
        New-Item -ItemType Directory -Path (Split-Path $supervisorStopRequestPath) -Force |
            Out-Null
        Set-Content -LiteralPath $supervisorStopRequestPath `
            -Value "maintenance_restart" -Encoding ASCII
        try {
            Stop-Process -Id $connection.OwningProcess -Force -ErrorAction Stop
        } catch {
            Remove-Item -LiteralPath $supervisorStopRequestPath -Force -ErrorAction SilentlyContinue
            throw
        }
        Write-WatchLog "[INFO] Stopped SMAI Streamlit PID $($connection.OwningProcess)."
        Start-Sleep -Seconds 3
    }
    & $python -m backend.server_ops.maintenance clear-notice
    Start-SmaiRecovery
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
        Write-WatchLog "[TEST] Restart conditions met; SMAI service restart suppressed by -NoRestart."
        return
    }
    Write-WatchLog "[WARN] All safety checks passed. Restarting the SMAI service."
    Write-MaintenanceLog "[RESTART] All safety checks passed; SMAI service restart requested."
    Restart-SmaiService
}

Write-WatchLog "[START] SMAI server watcher started (interval=${IntervalMinutes}m)."
do {
    try {
        if (Test-SmaiListener) {
            Write-WatchLog "[OK] Streamlit process and TCP $mainPort listener are healthy."
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
