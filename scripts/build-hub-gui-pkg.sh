#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${SPECTRUM_HUB_VERSION:-0.1.0-preview.6}"
APP_SOURCE="${SPECTRUM_HUB_APP:-"$ROOT/dist/SpectrumHub.app"}"
OUTPUT_DIR="${SPECTRUM_HUB_PKG_OUTPUT_DIR:-"$ROOT/installer"}"
OUTPUT_PKG="$OUTPUT_DIR/SpectrumHub-$VERSION-macos.pkg"
STAGING="$ROOT/build/spectrum-hub-gui-installer/macos-pkg"
ROOT_DIR="$STAGING/root"
SCRIPTS_DIR="$STAGING/scripts"
APP_TARGET="$ROOT_DIR/Applications/SpectrumHub.app"
IDENTIFIER="co.uk.agegatepro.spectrumhub"

if [[ ! -d "$APP_SOURCE" ]]; then
  echo "SpectrumHub.app was not found at $APP_SOURCE. Run: npm run build:hub-gui:macos" >&2
  exit 1
fi

if command -v xattr >/dev/null 2>&1; then
  xattr -cr "$APP_SOURCE"
fi
if command -v codesign >/dev/null 2>&1; then
  codesign --force --deep --sign - "$APP_SOURCE" >/dev/null 2>&1 || true
fi

rm -rf "$STAGING"
mkdir -p "$ROOT_DIR/Applications" "$SCRIPTS_DIR" "$OUTPUT_DIR"
COPYFILE_DISABLE=1 ditto --noextattr --norsrc "$APP_SOURCE" "$APP_TARGET"
find "$ROOT_DIR" -name ".DS_Store" -delete
find "$ROOT_DIR" -name "._*" -delete
if command -v xattr >/dev/null 2>&1; then
  xattr -cr "$ROOT_DIR"
fi

cat > "$SCRIPTS_DIR/postinstall" <<'SH'
#!/bin/sh
set -u

LOG_FILE="/var/log/spectrum-hub-install.log"
CLI_PACKAGE="${SPECTRUM_HUB_CLI_PACKAGE:-spectrumstore@latest}"

log() {
  printf '%s\n' "$1" >> "$LOG_FILE"
}

run_as_console_user() {
  console_user="$(stat -f "%Su" /dev/console 2>/dev/null || true)"
  if [ -z "$console_user" ] || [ "$console_user" = "root" ]; then
    return 1
  fi
  su - "$console_user" -c "$1"
}

find_user_npm() {
  run_as_console_user 'command -v npm' 2>/dev/null && return 0
  for candidate in /opt/homebrew/bin/npm /usr/local/bin/npm /usr/bin/npm; do
    if [ -x "$candidate" ]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

install_cli_if_possible() {
  npm_path="$(find_user_npm || true)"
  if [ -z "$npm_path" ]; then
    log "npm was not found; SpectrumHub.app is self-contained. To install the CLI later, install Node.js 18+ and run: npm install -g $CLI_PACKAGE"
    return 0
  fi

  quoted_npm="'$(printf "%s" "$npm_path" | sed "s/'/'\\''/g")'"
  install_command="$quoted_npm install -g $CLI_PACKAGE"
  if run_as_console_user "$install_command" >> "$LOG_FILE" 2>&1; then
    log "Installed Spectrum CLI with $npm_path: $CLI_PACKAGE"
    return 0
  fi

  log "User-level npm install failed; retrying as installer user."
  if "$npm_path" install -g "$CLI_PACKAGE" >> "$LOG_FILE" 2>&1; then
    log "Installed Spectrum CLI as installer user with $npm_path: $CLI_PACKAGE"
    return 0
  fi

  log "Spectrum CLI install failed; SpectrumHub.app remains installed and self-contained."
  return 0
}

log "Starting Spectrum Hub postinstall."
install_cli_if_possible
log "Spectrum Hub postinstall complete."
exit 0
SH
chmod 755 "$SCRIPTS_DIR/postinstall"

COPYFILE_DISABLE=1 pkgbuild \
  --root "$ROOT_DIR" \
  --scripts "$SCRIPTS_DIR" \
  --identifier "$IDENTIFIER" \
  --version "$VERSION" \
  --install-location "/" \
  "$OUTPUT_PKG"

echo "Built: $OUTPUT_PKG"
