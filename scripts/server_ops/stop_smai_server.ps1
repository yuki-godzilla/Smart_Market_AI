[CmdletBinding()]
param(
    [switch]$Quiet,
    [ValidateRange(1, 300)]
    [int]$DrainTimeoutSeconds = 30,
    [ValidateRange(1, 300)]
    [int]$ProcessTimeoutSeconds = 30
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$python = Join-Path $projectRoot "venv_SMAI\Scripts\python.exe"
$stopRequestPath = Join-Path $projectRoot "data\ops\server_ops\streamlit.stop"

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    Write-Error "SMAI Python environment was not found: $python"
    exit 1
}

$connection = Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue |
    Select-Object -First 1
if ($null -eq $connection) {
    Write-Output "[INFO] No process is listening on TCP 8501."
    exit 0
}

$process = Get-CimInstance Win32_Process `
    -Filter ("ProcessId=" + $connection.OwningProcess) `
    -ErrorAction SilentlyContinue
if ($null -eq $process) {
    Write-Error ("Could not inspect PID " + $connection.OwningProcess + ".")
    exit 2
}

$commandLine = [string]$process.CommandLine
Write-Output ("[SMAI] Target PID: " + $process.ProcessId)
Write-Output ("[SMAI] CommandLine: " + $commandLine)
if ($commandLine -notmatch "(?i)streamlit.+ui[\/]+app\.py") {
    Write-Error "The listener does not look like the SMAI Streamlit server. Nothing was stopped."
    exit 3
}

if (-not $Quiet) {
    $answer = Read-Host "Stop this SMAI server? [y/N]"
    if ($answer -notmatch "^(?i)y(es)?$") {
        Write-Output "[INFO] Cancelled."
        exit 4
    }
}

& $python -m backend.server_ops.maintenance request-stop `
    --mode manual_stop --requested-by local_operator --reason-code operator_requested
if ($LASTEXITCODE -ne 0) {
    Write-Error "Could not persist the manual stop intent. Nothing was stopped."
    exit 5
}

New-Item -ItemType Directory -Path (Split-Path $stopRequestPath) -Force | Out-Null
Set-Content -LiteralPath $stopRequestPath -Value "manual_stop" -Encoding ASCII
& $python -m backend.server_ops.maintenance mark-intent --status draining

$drainDeadline = (Get-Date).AddSeconds($DrainTimeoutSeconds)
$drained = $false
do {
    & $python -m backend.server_ops.maintenance drain 2>$null
    $drainCode = $LASTEXITCODE
    if ($drainCode -eq 0) {
        $drained = $true
        break
    }
    if ($drainCode -ne 20) {
        & $python -m backend.server_ops.maintenance mark-intent --status unknown 2>$null
        Remove-Item -LiteralPath $stopRequestPath -Force -ErrorAction SilentlyContinue
        Write-Error "The drain state could not be determined. Stop deferred."
        exit 6
    }
    Start-Sleep -Seconds 1
} while ((Get-Date) -lt $drainDeadline)

if (-not $drained) {
    & $python -m backend.server_ops.maintenance mark-intent --status timed_out 2>$null
    Write-Output "[WARN] Drain timed out after $DrainTimeoutSeconds seconds; terminating the service."
}

try {
    Stop-Process -Id $process.ProcessId -ErrorAction Stop
    $processDeadline = (Get-Date).AddSeconds($ProcessTimeoutSeconds)
    do {
        Start-Sleep -Seconds 1
        $stillRunning = Get-Process -Id $process.ProcessId -ErrorAction SilentlyContinue
    } while ($null -ne $stillRunning -and (Get-Date) -lt $processDeadline)

    if ($null -ne $stillRunning) {
        Write-Output "[WARN] Graceful process stop timed out; forcing termination."
        Stop-Process -Id $process.ProcessId -Force -ErrorAction Stop
        & $python -m backend.server_ops.maintenance mark-intent --status timed_out 2>$null
    } else {
        & $python -m backend.server_ops.maintenance mark-intent --status stopped 2>$null
    }
}
catch {
    & $python -m backend.server_ops.maintenance mark-intent --status unknown 2>$null
    Remove-Item -LiteralPath $stopRequestPath -Force -ErrorAction SilentlyContinue
    throw
}

Write-Output ("[OK] Stopped SMAI server PID " + $process.ProcessId + ".")
exit 0
