#!/usr/bin/env bash
# monitor.sh — Open serial monitor for a connected board.
# Usage: ./scripts/monitor.sh --port <COM_PORT> [--baud <BAUD>]
#
# Requires: arduino-cli, minicom, screen, or python3 (pyserial)

set -euo pipefail

PORT=""
BAUD="115200"
LOGFILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --baud) BAUD="$2"; shift 2 ;;
    --log) LOGFILE="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

if [[ -z "$PORT" ]]; then
  echo "Usage: monitor.sh --port <PORT> [--baud <BAUD>] [--log <FILE>]"
  echo ""
  echo "Example:"
  echo "  ./scripts/monitor.sh --port COM3 --baud 115200"
  echo "  ./scripts/monitor.sh --port /dev/ttyUSB0 --baud 115200 --log output.log"
  exit 1
fi

echo "=== Serial Monitor ==="
echo "Port: $PORT"
echo "Baud: $BAUD"
if [[ -n "$LOGFILE" ]]; then
  echo "Log:  $LOGFILE"
fi
echo "Press Ctrl+C to exit."
echo ""

if command -v arduino-cli &>/dev/null; then
  if [[ -n "$LOGFILE" ]]; then
    arduino-cli monitor --port "$PORT" --config "baudrate=$BAUD" | tee "$LOGFILE"
  else
    arduino-cli monitor --port "$PORT" --config "baudrate=$BAUD"
  fi
elif command -v python3 &>/dev/null && python3 -c "import serial" 2>/dev/null; then
  if [[ -n "$LOGFILE" ]]; then
    python3 -m serial.tools.miniterm "$PORT" "$BAUD" | tee "$LOGFILE"
  else
    python3 -m serial.tools.miniterm "$PORT" "$BAUD"
  fi
elif command -v minicom &>/dev/null; then
  minicom -D "$PORT" -b "$BAUD"
else
  echo "ERROR: No serial monitor tool found."
  echo "Install one of: arduino-cli, pyserial (pip install pyserial), minicom"
  exit 1
fi
