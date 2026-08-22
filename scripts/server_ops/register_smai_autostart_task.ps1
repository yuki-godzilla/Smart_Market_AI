[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$runtimeTaskName = "SmartMarketAI-Runtime"
$watchTaskName = "SmartMarketAI-Server-Watch"
$legacyTaskNames = @(
    "SmartMarketAI-LAN-Server",
    "SmartMarketAI-Server-Autostart"
)
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$runtimeScript = Join-Path $projectRoot "scripts\start_smai_runtime.ps1"
$watchScript = Join-Path $projectRoot "scripts\server_ops\watch_smai_server.ps1"
$powershell = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"

foreach ($path in @($runtimeScript, $watchScript)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required script was not found: $path"
    }
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principalCheck = [Security.Principal.WindowsPrincipal]::new($identity)
$userId = $identity.Name
$isAdministrator = $principalCheck.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if ($isAdministrator) {
    $principal = New-ScheduledTaskPrincipal -UserId $userId -LogonType S4U -RunLevel Highest
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $triggerDescription = "Windows startup"
} else {
    $principal = New-ScheduledTaskPrincipal -UserId $userId -LogonType Interactive -RunLevel Limited
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $userId
    $triggerDescription = "user logon"
}
$trigger.Delay = "PT1M"

$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -StartWhenAvailable

function Register-SmaiPowerShellTask {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$Script,
        [Parameter(Mandatory)][string]$Description
    )
    $arguments = "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Script`""
    $action = New-ScheduledTaskAction -Execute $powershell -Argument $arguments -WorkingDirectory $projectRoot
    $task = New-ScheduledTask -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description $Description
    Register-ScheduledTask -TaskName $Name -InputObject $task -Force | Out-Null
    Write-Host "[OK] Registered hidden task: $Name"
}

foreach ($legacyTaskName in $legacyTaskNames) {
    $legacy = Get-ScheduledTask -TaskName $legacyTaskName -ErrorAction SilentlyContinue
    if ($null -ne $legacy) {
        Disable-ScheduledTask -TaskName $legacyTaskName | Out-Null
        Write-Host "[SMAI] Disabled legacy startup task: $legacyTaskName"
    }
}

Register-SmaiPowerShellTask `
    -Name $runtimeTaskName `
    -Script $runtimeScript `
    -Description "Start Smart Market AI runtime without a visible console."

Register-SmaiPowerShellTask `
    -Name $watchTaskName `
    -Script $watchScript `
    -Description "Monitor Smart Market AI without a visible console."

Write-Host "[SMAI] Tasks start 60 seconds after $triggerDescription."
Write-Host "[SMAI] Runtime and watcher use hidden PowerShell actions; no CMD window is required."
