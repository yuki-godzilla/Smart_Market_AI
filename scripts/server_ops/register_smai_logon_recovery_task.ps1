[CmdletBinding()]
param(
    [switch]$Unregister
)

$ErrorActionPreference = "Stop"
$taskName = "SmartMarketAI-Server-Logon-Recovery"
if ($Unregister) {
    if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction Stop
    }
    Write-Host "[OK] Removed logon recovery task: $taskName"
    return
}

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$runner = Join-Path $projectRoot "scripts\start_smai_server_hidden.vbs"
$python = Join-Path $projectRoot "venv_SMAI\Scripts\python.exe"
foreach ($requiredPath in @($runner, $python, (Join-Path $projectRoot "scripts\start_smai_server.bat"))) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Required startup file was not found: $requiredPath"
    }
}

# A user-owned fallback for a missed boot task. The existing boot task is
# preserved, and both paths use the launcher's shared lock and health check.
$userId = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction `
    -Execute "$env:SystemRoot\System32\wscript.exe" `
    -Argument "//B //Nologo `"$runner`"" `
    -WorkingDirectory $projectRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $userId
$trigger.Delay = "PT1M"
$principal = New-ScheduledTaskPrincipal -UserId $userId -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable
$task = New-ScheduledTask `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Description "Recover SMAI after user logon if the boot task did not start it; shared launcher prevents duplicates."
Register-ScheduledTask -TaskName $taskName -InputObject $task -Force -ErrorAction Stop | Out-Null
Write-Host "[OK] Registered hidden logon recovery task: $taskName"
Write-Host "[SMAI] Existing healthy servers are reused; the boot task is preserved."
