[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$taskName = "SmartMarketAI-Symbol-Maintenance-IfDue"
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue

if ($null -eq $existing) {
    Write-Host "[INFO] Scheduled task is not registered: $taskName"
    exit 0
}

Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
Write-Host "[OK] Scheduled task was removed: $taskName"

