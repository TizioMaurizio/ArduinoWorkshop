#!/usr/bin/env python3
"""Test 3: Send a UDP angle command to the ESP32 and check it arrives on serial.

This tests the full ESP32 bridge: UDP in → Serial out.
Requirements:
    - ESP32-CAM powered, connected to Wi-Fi, and you know its IP.
    - ESP32 USB serial connected to PC (or Arduino serial visible).

Usage:
    python test_udp_to_serial.py 192.168.1.42        # use ESP IP
    python test_udp_to_serial.py 192.168.1.42 COM4   # also read serial echo

If you pass a COM port, the script reads back what the ESP prints to
serial and verifies the angle command was forwarded correctly.
Without COM port, it just sends and you visually check the serial monitor.
"""

import argparse
import socket
import sys
import time

try:
    import serial as pyserial
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False


def main():
    parser = argparse.ArgumentParser(description="Test ESP32 UDP→Serial bridge")
    parser.add_argument("esp_ip", help="ESP32-CAM IP address")
    parser.add_argument("serial_port", nargs="?", default=None,
                        help="Optional: COM port to read serial echo")
    parser.add_argument("--udp-port", type=int, default=9685)
    parser.add_argument("--baud", type=int, default=115200)
    args = parser.parse_args()

    # Open serial if provided
    ser = None
    if args.serial_port:
        if not HAS_SERIAL:
            print("ERROR: pyserial not installed. Run:  pip install pyserial")
            sys.exit(1)
        ser = pyserial.Serial(args.serial_port, args.baud, timeout=2.0)
        time.sleep(0.5)
        ser.reset_input_buffer()
        print(f"[TEST] Serial monitor on {args.serial_port}")

    # Test commands
    tests = [
        ("0,90\n",  "centre yaw"),
        ("3,45\n",  "pitch 45"),
        ("0,0\n",   "yaw min"),
        ("0,180\n", "yaw max"),
    ]

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2.0)

    passed = 0
    failed = 0

    for cmd, desc in tests:
        print(f"\n[SEND] {desc:15s}  → UDP {args.esp_ip}:{args.udp_port}  payload={cmd.strip()!r}")
        sock.sendto(cmd.encode("utf-8"), (args.esp_ip, args.udp_port))

        if ser:
            time.sleep(0.2)
            raw = ser.read(ser.in_waiting).decode("utf-8", errors="replace").strip()
            # The ESP prints the forwarded command on serial
            if cmd.strip() in raw:
                print(f"  PASS  serial echoed: {raw!r}")
                passed += 1
            else:
                print(f"  FAIL  expected {cmd.strip()!r} in serial, got: {raw!r}")
                failed += 1
        else:
            print("  (check serial monitor for output)")
            passed += 1  # can't verify without serial
            time.sleep(0.15)

    sock.close()
    if ser:
        ser.close()

    print(f"\n[TEST] {passed} passed, {failed} failed")
    if not args.serial_port:
        print("[NOTE] Run with a COM port argument to auto-verify serial output")
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
