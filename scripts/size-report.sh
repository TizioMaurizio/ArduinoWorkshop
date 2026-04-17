#!/usr/bin/env bash
# size-report.sh — Generate binary size report for compiled firmware.
# Usage: ./scripts/size-report.sh --sketch <PATH> --board <FQBN>
#
# Requires: arduino-cli

set -euo pipefail

SKETCH=""
BOARD=""
ALL_BOARDS=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --sketch) SKETCH="$2"; shift 2 ;;
    --board) BOARD="$2"; shift 2 ;;
    --all) ALL_BOARDS=true; shift ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

if [[ -z "$SKETCH" ]]; then
  echo "Usage: size-report.sh --sketch <SKETCH_PATH> --board <FQBN>"
  echo "       size-report.sh --sketch <SKETCH_PATH> --all"
  exit 1
fi

BOARDS_LIST=(
  "esp32:esp32:esp32"
  "esp32:esp32:esp32cam"
  "arduino:avr:uno"
  "arduino:avr:mega"
  "arduino:avr:nano"
)

if [[ "$ALL_BOARDS" == false && -z "$BOARD" ]]; then
  echo "Specify --board <FQBN> or --all"
  exit 1
fi

if [[ "$ALL_BOARDS" == false ]]; then
  BOARDS_LIST=("$BOARD")
fi

echo "=== Size Report ==="
echo "Sketch: $SKETCH"
echo ""
printf "%-30s %10s %10s %10s %10s\n" "Board" "Flash" "Flash%" "RAM" "RAM%"
printf "%-30s %10s %10s %10s %10s\n" "-----" "-----" "------" "---" "----"

for b in "${BOARDS_LIST[@]}"; do
  output=$(arduino-cli compile --fqbn "$b" "$SKETCH" --show-properties 2>/dev/null || true)
  size_output=$(arduino-cli compile --fqbn "$b" "$SKETCH" 2>&1 || true)

  flash_used=$(echo "$size_output" | grep -oP 'Sketch uses \K[0-9]+' || echo "?")
  flash_max=$(echo "$size_output" | grep -oP 'of \K[0-9]+(?= bytes)' | head -1 || echo "?")
  ram_used=$(echo "$size_output" | grep -oP 'Global variables use \K[0-9]+' || echo "?")
  ram_max=$(echo "$size_output" | grep -oP 'of \K[0-9]+(?= bytes)' | tail -1 || echo "?")

  if [[ "$flash_used" != "?" && "$flash_max" != "?" ]]; then
    flash_pct=$((flash_used * 100 / flash_max))
  else
    flash_pct="?"
  fi

  if [[ "$ram_used" != "?" && "$ram_max" != "?" ]]; then
    ram_pct=$((ram_used * 100 / ram_max))
  else
    ram_pct="?"
  fi

  printf "%-30s %10s %9s%% %10s %9s%%\n" "$b" "$flash_used" "$flash_pct" "$ram_used" "$ram_pct"
done

echo ""
echo "Done."
