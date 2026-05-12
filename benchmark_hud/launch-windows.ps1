$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$Url = "http://127.0.0.1:8765"

Set-Location $RepoRoot
Start-Process $Url

if (Get-Command py -ErrorAction SilentlyContinue) {
    py -3 benchmark_hud/server.py --host 127.0.0.1 --port 8765
} else {
    python benchmark_hud/server.py --host 127.0.0.1 --port 8765
}
