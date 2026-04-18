#!/usr/bin/env python3
"""Simulate Arduino on ESP32-CAM USB serial (COM port).

Reads from the ESP32-CAM's USB serial port (UART0) and looks for:
  - Boot/debug messages → displayed as [DEBUG]
  - Forwarded angle commands "<ch>,<angle>" → displayed as [ANGLE], replies "OK"

This script tests that the ESP32 is:
  1. Booting and connecting to Wi-Fi
  2. Receiving UDP packets from Godot
  3. Forwarding them via Serial.printf("[FWD] ...")

NOTE: This reads the USB debug serial (UART0), which shows [FWD] echos.
The actual Arduino data goes out GPIO 13 (UART2), which is not on USB.
To fully simulate the Arduino receiving data, connect a USB-to-serial
adapter to GPIO 13 and use test_serial_arduino.py instead.

Usage:
    python test_esp_serial_monitor.py COM4
    python test_esp_serial_monitor.py COM4 --send-udp 10.105.54.157
"""

import argparse
import socket
import sys
import time
import threading

try:
    import serial
except ImportError:
    print("ERROR: pyserial not installed. Run:  pip install pyserial")
    sys.exit(1)


def udp_sender(esp_ip: str, port: int, interval: float):
    """Send test angle commands via UDP to the ESP32."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    angles = [(0, 45), (3, 90), (0, 135), (3, 45), (0, 90), (3, 135)]
    idx = 0
    print(f"[UDP-TX] Sending test angles to {esp_ip}:{port} every {interval}s")
    try:
        while True:
            ch, ang = angles[idx % len(angles)]
            msg = f"{ch},{ang}\n"
            sock.sendto(msg.encode(), (esp_ip, port))
            print(f"[UDP-TX] Sent: {msg.strip()!r}")
            idx += 1
            time.sleep(interval)
    except KeyboardInterrupt:
        sock.close()


def main():
    parser = argparse.ArgumentParser(
        description="Monitor ESP32-CAM USB serial and optionally send test UDP angles")
    parser.add_argument("port", help="Serial port (e.g. COM4)")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--send-udp", metavar="ESP_IP", default=None,
                        help="Also send test UDP angle packets to this IP")
    parser.add_argument("--udp-port", type=int, default=9685)
    parser.add_argument("--udp-interval", type=float, default=0.5,
                        help="Seconds between UDP test packets (default 0.5)")
    args = parser.parse_args()

    print(f"[SERIAL] Opening {args.port} @ {args.baud} baud")
    try:
        ser = serial.Serial(args.port, args.baud, timeout=1)
    except serial.SerialException as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    # Start UDP sender thread if requested
    if args.send_udp:
        t = threading.Thread(target=udp_sender,
                             args=(args.send_udp, args.udp_port, args.udp_interval),
                             daemon=True)
        t.start()

    print("[SERIAL] Listening... (Ctrl+C to stop)")
    print()

    fwd_count = 0
    debug_count = 0

    try:
        while True:
            raw = ser.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue

            if line.startswith("[FWD]"):
                fwd_count += 1
                # Extract the angle command from "[FWD] 0,90"
                payload = line[5:].strip()
                parts = payload.split(",")
                ok = (len(parts) == 2
                      and parts[0].strip().isdigit()
                      and parts[1].strip().isdigit())
                if ok:
                    ch, ang = int(parts[0]), int(parts[1])
                    valid = ch in (0, 3) and 0 <= ang <= 180
                    tag = "OK" if valid else "BAD"
                    print(f"  [ANGLE-{tag}] #{fwd_count:>4d}  ch={ch} angle={ang}")
                else:
                    print(f"  [ANGLE-ERR] #{fwd_count:>4d}  parse failed: {payload!r}")
            else:
                debug_count += 1
                print(f"  [DEBUG] {line}")

    except KeyboardInterrupt:
        print(f"\n[DONE] {fwd_count} angle commands, {debug_count} debug messages")
        ser.close()


if __name__ == "__main__":
    main()
