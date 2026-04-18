"""
Test the ELEGOO Smart Robot Car V4.0 TCP protocol independently.

Usage:
  python test_car_protocol.py [--ip 192.168.4.1] [--port 100]

Tests:
1. TCP connection to car WiFi AP
2. Heartbeat keep-alive
3. Movement commands (N:3 forward/back/left/right)
4. Stop command (N:100)
5. Command sequencing (H field)

Requires: PC connected to the car's WiFi AP (default SSID: ESP32_xxxx).
"""

import socket
import json
import time
import argparse
import sys


def send_cmd(sock: socket.socket, cmd: dict, counter: list[int]) -> str:
    """Send a JSON command and return the payload string."""
    counter[0] += 1
    cmd["H"] = str(counter[0])
    payload = json.dumps(cmd, separators=(",", ":"))
    sock.sendall(payload.encode("utf-8"))
    return payload


def main() -> int:
    p = argparse.ArgumentParser(description="Test ELEGOO car TCP protocol")
    p.add_argument("--ip", default="192.168.4.1", help="Car IP (default: 192.168.4.1)")
    p.add_argument("--port", type=int, default=100, help="Car TCP port (default: 100)")
    p.add_argument("--dry-run", action="store_true", help="Don't actually connect")
    args = p.parse_args()

    counter = [0]
    results = []

    def report(name: str, ok: bool, detail: str = "") -> None:
        status = "OK" if ok else "FAIL"
        msg = f"[{status}] {name}"
        if detail:
            msg += f" — {detail}"
        print(msg)
        results.append(ok)

    if args.dry_run:
        print("[DRY RUN] Would connect to %s:%d" % (args.ip, args.port))
        # Test JSON generation only
        cmds = [
            ("forward", {"N": 3, "D1": 3, "D2": 40}),
            ("backward", {"N": 3, "D1": 4, "D2": 40}),
            ("left", {"N": 3, "D1": 1, "D2": 40}),
            ("right", {"N": 3, "D1": 2, "D2": 40}),
            ("stop", {"N": 100}),
        ]
        for name, cmd in cmds:
            cmd_copy = dict(cmd)
            counter[0] += 1
            cmd_copy["H"] = str(counter[0])
            payload = json.dumps(cmd_copy, separators=(",", ":"))
            print(f"  {name}: {payload}")
            report(f"JSON {name}", '"N":' in payload and '"H":' in payload, payload)
        total = len(results)
        passed = sum(results)
        print(f"\n[RESULT] {passed}/{total} passed (dry run)")
        return 0 if all(results) else 1

    # --- Test 1: TCP connection ---
    print(f"Connecting to {args.ip}:{args.port}...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    try:
        sock.connect((args.ip, args.port))
        report("TCP connect", True, f"{args.ip}:{args.port}")
    except (OSError, TimeoutError) as e:
        report("TCP connect", False, str(e))
        print("\nIs the PC connected to the car's WiFi AP?")
        return 1

    # --- Test 2: Heartbeat ---
    try:
        sock.sendall(b"{Heartbeat}")
        time.sleep(0.3)
        report("Heartbeat", True, "sent {Heartbeat}")
    except OSError as e:
        report("Heartbeat", False, str(e))

    # --- Test 3: Movement commands (short bursts) ---
    directions = [
        ("forward", 3, 30),
        ("backward", 4, 30),
        ("left", 1, 30),
        ("right", 2, 30),
    ]
    for name, d1, speed in directions:
        try:
            payload = send_cmd(sock, {"N": 3, "D1": d1, "D2": speed}, counter)
            time.sleep(0.5)
            # Stop after each movement
            send_cmd(sock, {"N": 100}, counter)
            time.sleep(0.3)
            report(f"Move {name}", True, payload)
        except OSError as e:
            report(f"Move {name}", False, str(e))

    # --- Test 4: Final stop ---
    try:
        payload = send_cmd(sock, {"N": 100}, counter)
        report("Final stop", True, payload)
    except OSError as e:
        report("Final stop", False, str(e))

    # --- Test 5: Rapid commands (simulate 10 Hz joystick) ---
    try:
        for i in range(10):
            send_cmd(sock, {"N": 3, "D1": 3, "D2": 20}, counter)
            time.sleep(0.1)
        send_cmd(sock, {"N": 100}, counter)
        report("Rapid 10Hz burst", True, f"10 commands, counter={counter[0]}")
    except OSError as e:
        report("Rapid 10Hz burst", False, str(e))

    sock.close()

    # --- Summary ---
    total = len(results)
    passed = sum(results)
    print(f"\n[RESULT] {passed}/{total} passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
