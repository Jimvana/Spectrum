#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/.server.pid"
LOG_FILE="$SCRIPT_DIR/server.log"
HOST="${SPEC_GUI_HOST:-127.0.0.1}"
PORT="${SPEC_GUI_PORT:-8765}"

if [[ -f "$PID_FILE" ]]; then
  PID="$(cat "$PID_FILE")"
  if [[ -n "$PID" ]] && kill -0 "$PID" 2>/dev/null; then
    echo "Spectrum GUI is already running at http://$HOST:$PORT (pid $PID)."
    exit 0
  fi
  rm -f "$PID_FILE"
fi

if command -v lsof >/dev/null 2>&1; then
  EXISTING_PID="$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null | head -n 1 || true)"
  if [[ -n "$EXISTING_PID" ]]; then
    echo "Something is already listening at http://$HOST:$PORT (pid $EXISTING_PID)."
    echo "Run $SCRIPT_DIR/stop_server.sh first, or set SPEC_GUI_PORT to another port."
    exit 1
  fi
fi

cd "$SCRIPT_DIR/../.."
nohup python "CLI Tool/gui/server.py" --host "$HOST" --port "$PORT" --open > "$LOG_FILE" 2>&1 &
PID="$!"
echo "$PID" > "$PID_FILE"

echo "Started Spectrum GUI at http://$HOST:$PORT (pid $PID)."
echo "Log: $LOG_FILE"
