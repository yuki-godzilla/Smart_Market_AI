param(
    [switch]$Elevated
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$stopScript = Join-Path $projectRoot "scripts\stop_smai_server.bat"
$startScript = Join-Path $projectRoot "scripts\start_smai_server.bat"
$healthUrl = "http://127.0.0.1:8501/_stcore/health"

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

Start-Process `
    -FilePath $env:ComSpec `
    -ArgumentList @("/d", "/c", ('"{0}"' -f $startScript)) `
    -WorkingDirectory $projectRoot `
    -WindowStyle Hidden

$deadline = (Get-Date).AddSeconds(45)
do {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $healthUrl -TimeoutSec 2
        if ($response.StatusCode -eq 200) {
            Write-Host "[OK] SMAI restarted successfully: http://localhost:8501"
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
