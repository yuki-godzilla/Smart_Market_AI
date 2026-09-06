[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$serverTaskName = "SmartMarketAI-Server-Autostart"
$watchTaskName = "SmartMarketAI-Server-Watch"
$legacyTaskName = "SmartMarketAI-LAN-Server"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$startScript = Join-Path $projectRoot "scripts\start_smai_server.bat"
$watchScript = Join-Path $projectRoot "scripts\server_ops\watch_smai_server.bat"

foreach ($path in @($startScript, $watchScript)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required script was not found: $path"
    }
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principalCheck = [Security.Principal.WindowsPrincipal]::new($identity)
$userId = $identity.Name
$isAdministrator = $principalCheck.IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)
if ($isAdministrator) {
    $principal = New-ScheduledTaskPrincipal -UserId $userId -LogonType S4U -RunLevel Highest
    $serverTrigger = New-ScheduledTaskTrigger -AtStartup
    $watchTrigger = New-ScheduledTaskTrigger -AtStartup
    $triggerDescription = "Windows startup"
} else {
    $principal = New-ScheduledTaskPrincipal `
        -UserId $userId `
        -LogonType Interactive `
        -RunLevel Limited
    $serverTrigger = New-ScheduledTaskTrigger -AtLogOn -User $userId
    $watchTrigger = New-ScheduledTaskTrigger -AtLogOn -User $userId
    $triggerDescription = "user logon"
}
$serverTrigger.Delay = "PT1M"
# The watcher performs an immediate health check.  Starting it alongside the
# server can therefore create an unnecessary duplicate-safe recovery request.
$watchTrigger.Delay = "PT3M"
$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -StartWhenAvailable

function Register-SmaiTask {
    param(
        [string]$Name,
        [string]$Script,
        [string]$Description,
        $TaskTrigger
    )
    $action = New-ScheduledTaskAction `
        -Execute $env:ComSpec `
        -Argument "/d /c `"$Script`"" `
        -WorkingDirectory $projectRoot
    $task = New-ScheduledTask `
        -Action $action `
        -Trigger $TaskTrigger `
        -Principal $principal `
        -Settings $settings `
        -Description $Description
    Register-ScheduledTask -TaskName $Name -InputObject $task -Force -ErrorAction Stop | Out-Null
    Write-Host "[OK] Registered: $Name"
}

$legacy = Get-ScheduledTask -TaskName $legacyTaskName -ErrorAction SilentlyContinue
if ($null -ne $legacy) {
    Disable-ScheduledTask -TaskName $legacyTaskName | Out-Null
    Write-Host "[SMAI] Disabled legacy task to prevent duplicate startup: $legacyTaskName"
}

Register-SmaiTask `
    -Name $serverTaskName `
    -Script $startScript `
    -Description "Start Smart Market AI after Windows startup." `
    -TaskTrigger $serverTrigger
Register-SmaiTask `
    -Name $watchTaskName `
    -Script $watchScript `
    -Description "Monitor Smart Market AI and perform safe maintenance restart checks." `
    -TaskTrigger $watchTrigger

Write-Host "[SMAI] Main server starts 60 seconds after $triggerDescription."
Write-Host "[SMAI] Server watcher starts 180 seconds after $triggerDescription."
Write-Host "[SMAI] start_smai_server.bat prevents duplicate Streamlit instances."
