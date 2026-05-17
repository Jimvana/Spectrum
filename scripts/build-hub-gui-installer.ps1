$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$ExeBuild = Join-Path $Root "scripts\build-hub-gui-exe.ps1"
$InstallerScript = Join-Path $Root "installer\SpectrumHub.iss"
$SourceDir = Join-Path $Root "dist\SpectrumHub"
$StagedDist = Join-Path $Root "dist-installer-build"
$StagedSourceDir = Join-Path $StagedDist "SpectrumHub"
$OutputDir = Join-Path $Root "dist\installer"
$ExistingExe = Join-Path $SourceDir "SpectrumHub.exe"
$IconFile = Join-Path $Root "packages\cli\src\spectrum_cli\assets\spec-icon.ico"

function Find-InnoCompiler {
    $pathCommand = Get-Command "iscc.exe" -ErrorAction SilentlyContinue
    if ($pathCommand) {
        return $pathCommand.Source
    }

    $candidates = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return $candidate
        }
    }

    return $null
}

$iscc = Find-InnoCompiler
if (-not $iscc) {
    Write-Error @"
Inno Setup compiler was not found.

Install it, then rerun this script:
  winget install JRSoftware.InnoSetup
"@
}

$running = Get-Process SpectrumHub -ErrorAction SilentlyContinue
if ($running -and (Test-Path -LiteralPath $ExistingExe)) {
    $ids = ($running | Select-Object -ExpandProperty Id) -join ", "
    Write-Warning "SpectrumHub.exe is running (PID: $ids). Building a fresh installer staging copy instead of replacing locked dist\SpectrumHub."
    $env:SPECTRUM_HUB_DIST_ROOT = $StagedDist
    $env:SPECTRUM_HUB_ALLOW_RUNNING = "1"
    & $ExeBuild
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Spectrum Hub executable build failed; installer was not created."
    }
    $SourceDir = $StagedSourceDir
} else {
    & $ExeBuild
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Spectrum Hub executable build failed; installer was not created."
    }
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

& $iscc `
    "/DSourceDir=$SourceDir" `
    "/DOutputDir=$OutputDir" `
    "/DIconFile=$IconFile" `
    $InstallerScript

if ($LASTEXITCODE -ne 0) {
    Write-Error "Inno Setup failed to build the installer."
}

Write-Host "Installer output:"
Get-ChildItem -LiteralPath $OutputDir -Filter "SpectrumHubSetup-*.exe" | Select-Object FullName,Length | Format-Table -AutoSize
