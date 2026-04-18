#!/usr/bin/env python3
"""Test 2: Send angle commands directly to Arduino over serial.

Bypasses ESP32 entirely. Connect your PC directly to the Arduino's
USB port and run this script. It sends channel/angle pairs and
checks for OK/ERR responses.

Usage:
    python test_serial_arduino.py COM5          # Windows
    python test_serial_arduino.py /dev/ttyUSB0  # Linux

Requires: pip install pyserial
"""

import argparse
import sys
import time

try:
    import serial
except ImportError:
    print("ERROR: pyserial not installed. Run:  pip install pyserial")
    sys.exit(1)


# Test vectors: (description, command, expected_response_prefix)
TEST_CASES = [
    ("centre ch0",       "0,90\n",   "OK"),
    ("centre ch3",       "3,90\n",   "OK"),
    ("min angle ch0",    "0,0\n",    "OK"),
    ("max angle ch0",    "0,180\n",  "OK"),
    ("min angle ch3",    "3,0\n",    "OK"),
    ("max angle ch3",    "3,180\n",  "OK"),
    # Error cases — Arduino should reject these
    ("bad channel 99",   "99,90\n",  "ERR"),
    ("negative angle",   "0,-1\n",   "ERR"),
    ("angle 181",        "0,181\n",  "ERR"),
    ("no comma",         "hello\n",  "ERR"),
    ("empty line",       "\n",       None),   # ignored, no response
    # Recovery — valid command after errors
    ("recover ch0",      "0,90\n",   "OK"),
]


def main():
    parser = argparse.ArgumentParser(description="Test Arduino PCA9685 serial protocol")
    parser.add_argument("port", help="Serial port (e.g. COM5, /dev/ttyUSB0)")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--timeout", type=float, default=2.0)
    args = parser.parse_args()

    print(f"[TEST] Opening {args.port} @ {args.baud} baud")
    try:
        ser = serial.Serial(args.port, args.baud, timeout=args.timeout)
    except serial.SerialException as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    # Wait for Arduino boot + "PCA9685 ready" message
    time.sleep(2.5)
    boot_msg = ser.read(ser.in_waiting).decode("utf-8", errors="replace")
    print(f"[BOOT] {boot_msg.strip()}")
    if "PCA9685 ready" not in boot_msg:
        print("[WARN] Did not see 'PCA9685 ready' — Arduino may not be running the right firmware")
    print()

    passed = 0
    failed = 0

    for desc, cmd, expected in TEST_CASES:
        ser.reset_input_buffer()
        ser.write(cmd.encode("utf-8"))
        ser.flush()

        if expected is None:
            # No response expected — brief wait then check
            time.sleep(0.1)
            leftover = ser.read(ser.in_waiting).decode("utf-8", errors="replace").strip()
            if leftover == "":
                print(f"  PASS  {desc:20s}  sent={cmd.strip()!r:12s}  (no response, as expected)")
                passed += 1
            else:
                print(f"  FAIL  {desc:20s}  sent={cmd.strip()!r:12s}  unexpected: {leftover!r}")
                failed += 1
            continue

        # Read response line
        response = ser.readline().decode("utf-8", errors="replace").strip()

        if response.startswith(expected):
            print(f"  PASS  {desc:20s}  sent={cmd.strip()!r:12s}  got={response!r}")
            passed += 1
        else:
            print(f"  FAIL  {desc:20s}  sent={cmd.strip()!r:12s}  expected={expected!r}  got={response!r}")
            failed += 1

    ser.close()
    print(f"\n[TEST] {passed} passed, {failed} failed out of {passed + failed}")
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
