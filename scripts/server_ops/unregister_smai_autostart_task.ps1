[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$taskNames = @("SmartMarketAI-Server-Autostart", "SmartMarketAI-Server-Watch")

foreach ($taskName in $taskNames) {
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($null -eq $task) {
        Write-Host "[INFO] Not registered: $taskName"
        continue
    }
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host "[OK] Removed: $taskName"
}

Write-Host "[INFO] The legacy SmartMarketAI-LAN-Server task is left disabled if it exists."

