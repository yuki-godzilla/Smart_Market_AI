$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
$python = Join-Path $repoRoot "venv_SMAI\Scripts\python.exe"
$specPath = Join-Path $repoRoot "packaging\smai.spec"
$readmeSource = Join-Path $repoRoot "packaging\README_PRE_RELEASE.txt"
$distRoot = Join-Path $repoRoot "dist"
$buildRoot = Join-Path $repoRoot "build"
$appDist = Join-Path $distRoot "SMAI"

function Assert-WorkspacePath {
    param([string]$Path)
    $rootFull = [System.IO.Path]::GetFullPath($repoRoot)
    $pathFull = [System.IO.Path]::GetFullPath($Path)
    if (-not $pathFull.StartsWith($rootFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to operate outside workspace: $pathFull"
    }
    return $pathFull
}

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python venv was not found: $python"
}
if (-not (Test-Path -LiteralPath $specPath)) {
    throw "PyInstaller spec was not found: $specPath"
}
if (-not (Test-Path -LiteralPath $readmeSource)) {
    throw "Pre-release README was not found: $readmeSource"
}

Push-Location $repoRoot
try {
    & $python -m PyInstaller --version | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller is not installed. Run: $python -m pip install -r setup\requirements-build.txt"
    }

    foreach ($target in @($buildRoot, $distRoot)) {
        $safeTarget = Assert-WorkspacePath $target
        if (Test-Path -LiteralPath $safeTarget) {
            Remove-Item -LiteralPath $safeTarget -Recurse -Force
        }
    }

    & $python -m PyInstaller $specPath --clean --noconfirm
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed."
    }

    if (-not (Test-Path -LiteralPath $appDist)) {
        throw "Expected dist folder was not created: $appDist"
    }

    Copy-Item -LiteralPath $readmeSource -Destination (Join-Path $appDist "README_PRE_RELEASE.txt") -Force

    Write-Host ""
    Write-Host "Smart Market AI pre-release build created:"
    Write-Host "  $(Join-Path $appDist 'SMAI.exe')"
    Write-Host "  $(Join-Path $appDist 'README_PRE_RELEASE.txt')"
} finally {
    Pop-Location
}
