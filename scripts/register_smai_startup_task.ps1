[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$taskName = "SmartMarketAI-LAN-Server"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$startScript = Join-Path $projectRoot "scripts\start_smai_server.bat"

if (-not (Test-Path -LiteralPath $startScript -PathType Leaf)) {
    throw "Startup script was not found: $startScript"
}

$userId = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction `
    -Execute $env:ComSpec `
    -Argument "/d /c `"$startScript`"" `
    -WorkingDirectory $projectRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $userId
$trigger.Delay = "PT1M"
$principal = New-ScheduledTaskPrincipal `
    -UserId $userId `
    -LogonType Interactive `
    -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -StartWhenAvailable

$task = New-ScheduledTask `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Description "Start the Smart Market AI LAN server 60 seconds after user logon."

$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($null -ne $existing) {
    Write-Host "[SMAI] Updating existing scheduled task: $taskName"
} else {
    Write-Host "[SMAI] Registering scheduled task: $taskName"
}

Register-ScheduledTask -TaskName $taskName -InputObject $task -Force | Out-Null
Write-Host "[OK] Scheduled task is registered."
Write-Host "     Trigger: user logon + 60 seconds"
Write-Host "     Script:  $startScript"
Write-Host "     Policy:  IgnoreNew, retry 3 times at 1-minute intervals"
