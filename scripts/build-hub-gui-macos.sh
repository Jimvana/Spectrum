#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="${SPECTRUM_HUB_DIST_ROOT:-"$ROOT/dist"}"
BUILDER="$ROOT/scripts/build-hub-gui.py"

if ! python3 -m PyInstaller --version >/dev/null 2>&1; then
  echo "PyInstaller is not installed. Run: npm run deps:hub-gui:macos" >&2
  exit 1
fi

python3 "$BUILDER" --platform macos --dist "$DIST"

if [[ ! -d "$DIST/SpectrumHub.app" ]]; then
  echo "PyInstaller finished but $DIST/SpectrumHub.app was not created." >&2
  exit 1
fi

echo "Built: $DIST/SpectrumHub.app"
