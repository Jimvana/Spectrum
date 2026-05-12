#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
URL="http://127.0.0.1:8765"

cd "$REPO_ROOT"
open "$URL"
python3 benchmark_hud/server.py --host 127.0.0.1 --port 8765
