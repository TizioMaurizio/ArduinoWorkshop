#!/usr/bin/env bash
# build-all.sh — Compile all projects for all supported board targets.
# Usage: ./scripts/build-all.sh [--board <fqbn>] [--project <path>]
#
# Requires: arduino-cli or platformio (auto-detected)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# Default board targets — extend as boards are added
BOARDS=(
  "esp32:esp32:esp32"
  "esp32:esp32:esp32cam"
  "arduino:avr:uno"
  "arduino:avr:mega"
  "arduino:avr:nano"
)

FILTER_BOARD=""
FILTER_PROJECT=""
PASS=0
FAIL=0
SKIP=0
FAILURES=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --board) FILTER_BOARD="$2"; shift 2 ;;
    --project) FILTER_PROJECT="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

detect_tool() {
  if command -v platformio &>/dev/null; then
    echo "platformio"
  elif command -v arduino-cli &>/dev/null; then
    echo "arduino-cli"
  else
    echo "none"
  fi
}

compile_arduino_cli() {
  local sketch="$1"
  local board="$2"
  arduino-cli compile --fqbn "$board" "$sketch" 2>&1
}

compile_platformio() {
  local project_dir="$1"
  local env="$2"
  platformio run -d "$project_dir" -e "$env" 2>&1
}

TOOL=$(detect_tool)
if [[ "$TOOL" == "none" ]]; then
  echo "ERROR: Neither arduino-cli nor platformio found in PATH."
  exit 1
fi

echo "=== Build All ==="
echo "Tool: $TOOL"
echo "Repo: $REPO_ROOT"
echo ""

# Find all .ino sketches
while IFS= read -r -d '' sketch; do
  sketch_dir="$(dirname "$sketch")"
  sketch_name="$(basename "$sketch_dir")"

  if [[ -n "$FILTER_PROJECT" && "$sketch_dir" != *"$FILTER_PROJECT"* ]]; then
    continue
  fi

  for board in "${BOARDS[@]}"; do
    if [[ -n "$FILTER_BOARD" && "$board" != "$FILTER_BOARD" ]]; then
      continue
    fi

    echo -n "[$sketch_name] $board ... "

    if output=$(compile_arduino_cli "$sketch" "$board" 2>&1); then
      echo "PASS"
      ((PASS++))
    else
      echo "FAIL"
      ((FAIL++))
      FAILURES+=("$sketch_name ($board)")
    fi
  done
done < <(find "$REPO_ROOT/Projects" -name "*.ino" -print0 2>/dev/null)

echo ""
echo "=== Results ==="
echo "Pass: $PASS"
echo "Fail: $FAIL"
echo "Skip: $SKIP"

if [[ ${#FAILURES[@]} -gt 0 ]]; then
  echo ""
  echo "=== Failures ==="
  for f in "${FAILURES[@]}"; do
    echo "  - $f"
  done
  exit 1
fi

exit 0
