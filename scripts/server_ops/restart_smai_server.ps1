param(
    [switch]$Elevated
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$python = Join-Path $projectRoot "venv_SMAI\Scripts\python.exe"
$stopScript = Join-Path $projectRoot "scripts\stop_smai_server.bat"
$startScript = Join-Path $projectRoot "scripts\start_smai_server.bat"
if ([string]::IsNullOrWhiteSpace($env:SMAI_CONFIG_FILE)) {
    $env:SMAI_CONFIG_FILE = Join-Path $projectRoot "config\server.yaml"
}
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    Write-Error "SMAI Python environment was not found: $python"
    exit 1
}
$network = & $python -m backend.server_ops.network --emit-json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or $null -eq $network) {
    Write-Error "SMAI network settings could not be resolved. Restart was cancelled."
    exit 1
}
$healthUrl = ([string]$network.local_access_url) + "/_stcore/health"
$localAccessUrl = [string]$network.local_access_url

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Administrator)) {
    if ($Elevated) {
        Write-Error "Administrator privileges are required to stop the current SMAI server."
        exit 1
    }

    Write-Host "[SMAI] Requesting administrator privileges for a safe restart..."
    $arguments = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", ('"{0}"' -f $PSCommandPath),
        "-Elevated"
    )
    Start-Process -FilePath "powershell.exe" -ArgumentList $arguments -WorkingDirectory $projectRoot -Verb RunAs
    exit 0
}

Write-Host "[SMAI] Restarting the SMAI Streamlit server..."
$stopProcess = Start-Process `
    -FilePath $env:ComSpec `
    -ArgumentList @("/d", "/c", ('"{0}" /quiet' -f $stopScript)) `
    -WorkingDirectory $projectRoot `
    -Wait `
    -PassThru `
    -WindowStyle Hidden
if ($stopProcess.ExitCode -ne 0) {
    Write-Error "SMAI could not be stopped safely. Restart was cancelled."
    exit 2
}

Write-Host "[SMAI] Opening the SMAI server console..."
Start-Process `
    -FilePath $env:ComSpec `
    -ArgumentList @("/d", "/k", ('call "{0}" /console' -f $startScript)) `
    -WorkingDirectory $projectRoot

$deadline = (Get-Date).AddSeconds(45)
do {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $healthUrl -TimeoutSec 2
        if ($response.StatusCode -eq 200) {
            Write-Host "[OK] SMAI restarted successfully: $localAccessUrl"
            exit 0
        }
    }
    catch {
        # Startup is asynchronous; retry until the bounded deadline.
    }
    Start-Sleep -Seconds 1
} while ((Get-Date) -lt $deadline)

Write-Error "SMAI did not become healthy within 45 seconds."
exit 3
