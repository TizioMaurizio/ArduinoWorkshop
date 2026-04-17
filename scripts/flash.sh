#!/usr/bin/env bash
# flash.sh — Flash a compiled binary to a connected board.
# Usage: ./scripts/flash.sh --port <COM_PORT> --board <BOARD> --sketch <PATH>
#
# Requires: arduino-cli or esptool.py

set -euo pipefail

PORT=""
BOARD=""
SKETCH=""
BAUD="921600"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --board) BOARD="$2"; shift 2 ;;
    --sketch) SKETCH="$2"; shift 2 ;;
    --baud) BAUD="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

if [[ -z "$PORT" || -z "$BOARD" || -z "$SKETCH" ]]; then
  echo "Usage: flash.sh --port <PORT> --board <FQBN> --sketch <SKETCH_PATH>"
  echo ""
  echo "Example:"
  echo "  ./scripts/flash.sh --port COM3 --board esp32:esp32:esp32 --sketch Projects/MyProject/MyProject.ino"
  exit 1
fi

echo "=== Flash ==="
echo "Port:   $PORT"
echo "Board:  $BOARD"
echo "Sketch: $SKETCH"
echo "Baud:   $BAUD"
echo ""

if command -v arduino-cli &>/dev/null; then
  echo "Compiling and uploading with arduino-cli..."
  arduino-cli compile --fqbn "$BOARD" "$SKETCH"
  arduino-cli upload --fqbn "$BOARD" --port "$PORT" "$SKETCH"
  echo ""
  echo "Upload complete. Open serial monitor with:"
  echo "  arduino-cli monitor --port $PORT --config baudrate=115200"
elif command -v esptool.py &>/dev/null; then
  echo "NOTE: esptool.py requires a pre-compiled .bin file."
  echo "Specify the .bin path as --sketch when using esptool."
  esptool.py --chip esp32 --port "$PORT" --baud "$BAUD" \
    write_flash -z 0x10000 "$SKETCH"
else
  echo "ERROR: Neither arduino-cli nor esptool.py found."
  exit 1
fi

echo "Done."
