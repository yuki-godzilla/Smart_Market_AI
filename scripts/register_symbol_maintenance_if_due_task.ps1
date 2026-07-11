[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$taskName = "SmartMarketAI-Symbol-Maintenance-IfDue"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$maintenanceScript = Join-Path $projectRoot "scripts\run_symbol_maintenance_if_due.bat"

if (-not (Test-Path -LiteralPath $maintenanceScript -PathType Leaf)) {
    throw "Maintenance script was not found: $maintenanceScript"
}

$userId = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction `
    -Execute $env:ComSpec `
    -Argument "/d /c `"$maintenanceScript`"" `
    -WorkingDirectory $projectRoot
$logonTrigger = New-ScheduledTaskTrigger -AtLogOn -User $userId
$logonTrigger.Delay = "PT10M"
$dailyTrigger = New-ScheduledTaskTrigger -Daily -At "03:30"
$principal = New-ScheduledTaskPrincipal `
    -UserId $userId `
    -LogonType Interactive `
    -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -RestartCount 1 `
    -RestartInterval (New-TimeSpan -Minutes 30) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -StartWhenAvailable

$task = New-ScheduledTask `
    -Action $action `
    -Trigger @($logonTrigger, $dailyTrigger) `
    -Principal $principal `
    -Settings $settings `
    -Description "Check symbol maintenance after logon and daily; run only when due."

$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($null -ne $existing) {
    Write-Host "[SMAI] Updating existing scheduled task: $taskName"
} else {
    Write-Host "[SMAI] Registering scheduled task: $taskName"
}

Register-ScheduledTask -TaskName $taskName -InputObject $task -Force | Out-Null
Write-Host "[OK] Symbol maintenance if-due task is registered."
Write-Host "     Trigger: user logon + 10 minutes, and daily at 03:30"
Write-Host "     Script:  $maintenanceScript"
Write-Host "     Policy:  IgnoreNew, retry once after 30 minutes"
Write-Host "     The heavy run_symbol_universe_import_all.bat is not registered directly."
