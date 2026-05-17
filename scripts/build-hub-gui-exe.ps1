$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Dist = if ($env:SPECTRUM_HUB_DIST_ROOT) { $env:SPECTRUM_HUB_DIST_ROOT } else { Join-Path $Root "dist" }
$Builder = Join-Path $Root "scripts\build-hub-gui.py"

$running = Get-Process SpectrumHub -ErrorAction SilentlyContinue
if ($running -and $env:SPECTRUM_HUB_ALLOW_RUNNING -ne "1") {
    $ids = ($running | Select-Object -ExpandProperty Id) -join ", "
    Write-Error "SpectrumHub.exe is still running (PID: $ids). Close Spectrum Hub before rebuilding so PyInstaller can replace dist\SpectrumHub."
}

python -m PyInstaller --version >$null
if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller is not installed. Run: npm run deps:hub-gui"
}

python $Builder --platform windows --dist $Dist

if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller failed to build SpectrumHub.exe."
}

Write-Host "Built: $(Join-Path $Dist 'SpectrumHub\SpectrumHub.exe')"
