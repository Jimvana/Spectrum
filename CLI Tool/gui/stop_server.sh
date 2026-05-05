#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/.server.pid"
PORT="${SPEC_GUI_PORT:-8765}"

stop_pid() {
  local pid="$1"
  if [[ -z "$pid" ]]; then
    return 0
  fi
  if ! kill -0 "$pid" 2>/dev/null; then
    return 0
  fi

  kill "$pid" 2>/dev/null || true
  for _ in {1..30}; do
    if ! kill -0 "$pid" 2>/dev/null; then
      return 0
    fi
    sleep 0.1
  done

  kill -9 "$pid" 2>/dev/null || true
}

STOPPED=0

if [[ -f "$PID_FILE" ]]; then
  PID="$(cat "$PID_FILE")"
  if [[ -n "$PID" ]] && kill -0 "$PID" 2>/dev/null; then
    stop_pid "$PID"
    echo "Stopped Spectrum GUI PID file process (pid $PID)."
    STOPPED=1
  fi
  rm -f "$PID_FILE"
fi

if command -v lsof >/dev/null 2>&1; then
  PORT_PIDS="$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
  for pid in $PORT_PIDS; do
    stop_pid "$pid"
    echo "Stopped Spectrum GUI port listener on $PORT (pid $pid)."
    STOPPED=1
  done
fi

if [[ "$STOPPED" -eq 0 ]]; then
  if pkill -f "spectrum_cli/main.py gui.*--port $PORT" 2>/dev/null; then
    echo "Stopped Spectrum GUI process matching spectrum_cli on port $PORT."
    STOPPED=1
  fi
fi

if [[ "$STOPPED" -eq 0 ]]; then
  echo "No Spectrum GUI server found on port $PORT."
fi
