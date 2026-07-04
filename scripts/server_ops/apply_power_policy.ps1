[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this script from an elevated (Administrator) terminal."
}

Write-Host "[SMAI] Applying AC server power policy..."
& powercfg.exe /change monitor-timeout-ac 10
if ($LASTEXITCODE -ne 0) { throw "Failed to set the AC display timeout." }
& powercfg.exe /change standby-timeout-ac 0
if ($LASTEXITCODE -ne 0) { throw "Failed to disable AC sleep." }
& powercfg.exe /change hibernate-timeout-ac 0
if ($LASTEXITCODE -ne 0) { throw "Failed to disable the AC hibernate timeout." }
& powercfg.exe /hibernate off
if ($LASTEXITCODE -ne 0) { throw "Failed to disable hibernation." }

Write-Host "[OK] AC policy applied: display off=10 minutes, sleep=never, hibernate=off."
Write-Host ""
Write-Host "[SMAI] Current active power scheme:"
& powercfg.exe /getactivescheme
Write-Host ""
Write-Host "[SMAI] Current AC display settings:"
& powercfg.exe /query SCHEME_CURRENT SUB_VIDEO
Write-Host ""
Write-Host "[SMAI] Current AC sleep settings:"
& powercfg.exe /query SCHEME_CURRENT SUB_SLEEP

