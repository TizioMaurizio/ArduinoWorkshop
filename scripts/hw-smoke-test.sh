#!/usr/bin/env bash
# hw-smoke-test.sh — Run on-device smoke tests and parse serial output for PASS/FAIL.
# Usage: ./scripts/hw-smoke-test.sh --port <COM_PORT> [--baud <BAUD>] [--timeout <SEC>]
#
# Expects serial output lines matching: [PASS] or [FAIL]
# Requires: python3 with pyserial, or arduino-cli

set -euo pipefail

PORT=""
BAUD="115200"
TIMEOUT=30

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --baud) BAUD="$2"; shift 2 ;;
    --timeout) TIMEOUT="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

if [[ -z "$PORT" ]]; then
  echo "Usage: hw-smoke-test.sh --port <PORT> [--baud <BAUD>] [--timeout <SEC>]"
  echo ""
  echo "Flash the smoke test sketch first, then run this script to capture and parse output."
  echo "The sketch should print lines containing [PASS], [FAIL], or [DONE]."
  exit 1
fi

TMPLOG=$(mktemp)
trap "rm -f $TMPLOG" EXIT

echo "=== Hardware Smoke Test ==="
echo "Port:    $PORT"
echo "Baud:    $BAUD"
echo "Timeout: ${TIMEOUT}s"
echo ""
echo "Capturing serial output..."

# Use python3 + pyserial for timed capture
python3 -c "
import serial, time, sys

port = '$PORT'
baud = int('$BAUD')
timeout = int('$TIMEOUT')

try:
    ser = serial.Serial(port, baud, timeout=1)
except Exception as e:
    print(f'ERROR: Cannot open {port}: {e}', file=sys.stderr)
    sys.exit(1)

start = time.time()
lines = []
while time.time() - start < timeout:
    line = ser.readline().decode('utf-8', errors='replace').strip()
    if line:
        print(line)
        lines.append(line)
    if '[DONE]' in line:
        break

ser.close()

with open('$TMPLOG', 'w') as f:
    f.write('\n'.join(lines))
" 2>&1

echo ""
echo "=== Results ==="

PASS_COUNT=$(grep -c '\[PASS\]' "$TMPLOG" 2>/dev/null || echo 0)
FAIL_COUNT=$(grep -c '\[FAIL\]' "$TMPLOG" 2>/dev/null || echo 0)
ERROR_COUNT=$(grep -c '\[ERROR\]' "$TMPLOG" 2>/dev/null || echo 0)

echo "Pass:   $PASS_COUNT"
echo "Fail:   $FAIL_COUNT"
echo "Errors: $ERROR_COUNT"

if [[ "$FAIL_COUNT" -gt 0 || "$ERROR_COUNT" -gt 0 ]]; then
  echo ""
  echo "=== Failed Tests ==="
  grep -E '\[FAIL\]|\[ERROR\]' "$TMPLOG" || true
  exit 1
fi

if [[ "$PASS_COUNT" -eq 0 ]]; then
  echo ""
  echo "WARNING: No [PASS] lines detected. Check that the smoke test sketch is flashed and producing output."
  exit 1
fi

echo ""
echo "All tests passed."
exit 0
