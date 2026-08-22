[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $projectRoot "venv_SMAI\Scripts\python.exe"
$logDir = Join-Path $projectRoot "logs\server_ops"
$runtimeLog = Join-Path $logDir "runtime.log"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Write-RuntimeLog {
    param([string]$Message)
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -LiteralPath $runtimeLog -Value "$stamp $Message" -Encoding UTF8
}

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    Write-RuntimeLog "ERROR Python virtual environment not found: $python"
    exit 1
}

$env:SMAI_PERFORMANCE_PROFILE = if ($env:SMAI_PERFORMANCE_PROFILE) { $env:SMAI_PERFORMANCE_PROFILE } else { "workstation" }
$env:SMAI_ASSISTANT_GATEWAY_AUTOSTART = "1"

$lanIp = Get-NetIPConfiguration -ErrorAction SilentlyContinue |
    Where-Object { $_.IPv4DefaultGateway -ne $null -and $_.IPv4Address -ne $null } |
    Select-Object -First 1 -ExpandProperty IPv4Address |
    Select-Object -ExpandProperty IPAddress
if (-not $lanIp) { $lanIp = "localhost" }

Write-RuntimeLog "START SmartMarketAI Runtime. browser-address=$lanIp profile=$($env:SMAI_PERFORMANCE_PROFILE)"
Push-Location $projectRoot
try {
    & $python -m backend.server_ops.launcher --browser-address $lanIp --maintenance-startup --resilient *>> $runtimeLog
    $exitCode = $LASTEXITCODE
    if ($exitCode -eq 10) {
        Write-RuntimeLog "REUSE Existing SMAI runtime is already healthy."
        exit 0
    }
    Write-RuntimeLog "STOP Runtime exited with code $exitCode."
    exit $exitCode
} catch {
    Write-RuntimeLog "ERROR $($_.Exception.Message)"
    exit 1
} finally {
    Pop-Location
}
