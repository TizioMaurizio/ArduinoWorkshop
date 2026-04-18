#!/usr/bin/env python3
"""Test 1: Simulate ESP32 — listen for Godot UDP angle commands.

Run this on the PC, then run the Godot project. This script plays
the role of the ESP32: it listens on UDP_PORT and prints every
packet it receives. Use it to verify Godot is sending correctly
WITHOUT needing the ESP32 powered on.

Usage:
    python test_udp_listener.py [--port 9685]

Expected output when Godot is running and head is moving:
    [UDP] 0,90
    [UDP] 3,45
    [UDP] 0,91
"""

import argparse
import socket
import sys


def main():
    parser = argparse.ArgumentParser(description="Simulate ESP32 UDP listener")
    parser.add_argument("--port", type=int, default=9685, help="UDP port (default 9685)")
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", args.port))
    print(f"[TEST] Listening on UDP :{args.port}  (Ctrl+C to stop)")
    print(f"[TEST] Set Godot bridge_host to this PC's IP, bridge_port to {args.port}")
    print()

    count = 0
    try:
        while True:
            data, addr = sock.recvfrom(256)
            text = data.decode("utf-8", errors="replace").strip()
            count += 1

            # Validate format: "<int>,<int>"
            parts = text.split(",")
            ok = (
                len(parts) == 2
                and parts[0].strip().isdigit()
                and parts[1].strip().isdigit()
            )
            ch = int(parts[0]) if ok else -1
            ang = int(parts[1]) if ok else -1
            valid_ch = ch in (0, 3)
            valid_ang = 0 <= ang <= 180

            status = "OK" if (ok and valid_ch and valid_ang) else "BAD"
            print(f"[{status}] #{count:>4d} from {addr[0]}:{addr[1]}  →  {text!r}", end="")
            if not ok:
                print("  ← parse error", end="")
            elif not valid_ch:
                print(f"  ← unexpected channel {ch}", end="")
            elif not valid_ang:
                print(f"  ← angle {ang} out of 0-180", end="")
            print()
    except KeyboardInterrupt:
        print(f"\n[TEST] Received {count} packets total")
        sys.exit(0)


if __name__ == "__main__":
    main()
