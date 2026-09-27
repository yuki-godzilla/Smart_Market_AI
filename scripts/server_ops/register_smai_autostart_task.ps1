[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$serverTaskName = "SmartMarketAI-Server-Autostart"
$watchTaskName = "SmartMarketAI-Server-Watch"
$legacyTaskName = "SmartMarketAI-LAN-Server"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$startScript = Join-Path $projectRoot "scripts\start_smai_server.bat"
if (-not (Test-Path -LiteralPath $startScript -PathType Leaf)) {
    throw "Required script was not found: $startScript"
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
    $triggerDescription = "Windows startup"
} else {
    $principal = New-ScheduledTaskPrincipal `
        -UserId $userId `
        -LogonType Interactive `
        -RunLevel Limited
    $serverTrigger = New-ScheduledTaskTrigger -AtLogOn -User $userId
    $triggerDescription = "user logon"
}
$serverTrigger.Delay = "PT1M"
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

# The web application is the only server process started by this registration.
# Keep the former watchdog task disabled if it was registered previously.
$watch = Get-ScheduledTask -TaskName $watchTaskName -ErrorAction SilentlyContinue
if ($null -ne $watch) {
    Disable-ScheduledTask -TaskName $watchTaskName -ErrorAction Stop | Out-Null
    if ($watch.State -eq "Running") {
        Stop-ScheduledTask -TaskName $watchTaskName -ErrorAction Stop
    }
    Write-Host "[SMAI] Disabled former startup watcher: $watchTaskName"
}

Register-SmaiTask `
    -Name $serverTaskName `
    -Script $startScript `
    -Description "Start Smart Market AI after Windows startup." `
    -TaskTrigger $serverTrigger
Write-Host "[SMAI] Main server starts 60 seconds after $triggerDescription."
Write-Host "[SMAI] start_smai_server.bat prevents duplicate Streamlit instances."
