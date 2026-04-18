#!/usr/bin/env python3
"""Arduino + PCA9685 + Servo Digital Twin.

A pure-Python simulation of the full servo chain. No hardware needed.
Listens for UDP angle packets (from Godot or test sender) on the same
port the ESP32 would, parses them like the Arduino firmware, and shows
animated servo positions in the terminal.

This validates that Godot sends correct packets without ANY hardware.

Architecture simulated:
    Godot  →  [UDP :9685]  →  This script (ESP32 + Arduino + servos)

Usage:
    python test_digital_twin.py                    # listen for Godot
    python test_digital_twin.py --self-test        # generate own test angles
    python test_digital_twin.py --port 9685        # custom port

Requires: pip install pyserial (only if --serial used)
"""

import argparse
import socket
import sys
import time
import threading
import os

# Fix Windows console encoding for Unicode box-drawing characters
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


# ---------------------------------------------------------------------------
#  Servo simulation
# ---------------------------------------------------------------------------
MAX_CHANNELS = 16
MAX_ANGLE = 180

class ServoState:
    def __init__(self):
        self.positions = [90] * MAX_CHANNELS
        self.targets = [90] * MAX_CHANNELS
        self.update_count = [0] * MAX_CHANNELS
        self.last_update = [0.0] * MAX_CHANNELS
        self.total_ok = 0
        self.total_err = 0
        self.log = []  # last N messages
        self.start_time = time.time()

    def parse_command(self, line: str) -> str:
        """Exact mirror of Arduino parse_and_execute()."""
        line = line.strip()
        if not line:
            return None

        comma = line.find(',')
        if comma < 0:
            self.total_err += 1
            self._log(f"ERR:no comma  ← {line!r}")
            return "ERR:no comma"

        try:
            channel = int(line[:comma])
        except ValueError:
            self.total_err += 1
            self._log(f"ERR:bad ch    ← {line!r}")
            return "ERR:bad channel"

        try:
            angle = int(line[comma + 1:])
        except ValueError:
            self.total_err += 1
            self._log(f"ERR:bad angle ← {line!r}")
            return "ERR:bad angle"

        if channel < 0 or channel >= MAX_CHANNELS:
            self.total_err += 1
            self._log(f"ERR:ch 0-15   ← ch={channel}")
            return "ERR:ch 0-15"

        if angle < 0 or angle > MAX_ANGLE:
            self.total_err += 1
            self._log(f"ERR:ang 0-180 ← ang={angle}")
            return "ERR:ang 0-180"

        old = self.positions[channel]
        self.positions[channel] = angle
        self.targets[channel] = angle
        self.update_count[channel] += 1
        self.last_update[channel] = time.time()
        self.total_ok += 1
        self._log(f"OK  ch{channel}={old:>3d}°→{angle:>3d}°")
        return "OK"

    def _log(self, msg):
        self.log.append(msg)
        if len(self.log) > 8:
            self.log.pop(0)


def render_servo(label: str, angle: int, width: int = 40) -> str:
    """Render a single servo as an ASCII gauge."""
    pos = int(angle / 180 * width)
    bar = '─' * pos + '◆' + '─' * (width - pos)
    return f"  {label}  0°├{bar}┤180°  {angle:>3d}°"


def render_dashboard(state: ServoState) -> str:
    """Render the full dashboard."""
    elapsed = time.time() - state.start_time
    hz = state.total_ok / elapsed if elapsed > 0 else 0

    lines = []

    # Clear screen
    lines.append("\033[2J\033[H")

    lines.append("╔══════════════════════════════════════════════════════════════╗")
    lines.append("║          ARDUINO + PCA9685 DIGITAL TWIN                     ║")
    lines.append("╠══════════════════════════════════════════════════════════════╣")
    lines.append(f"║  Commands: {state.total_ok:>5d} OK  {state.total_err:>3d} ERR  "
                 f"│  Rate: {hz:>5.1f} cmd/s  │  {elapsed:>5.0f}s    ║")
    lines.append("╠══════════════════════════════════════════════════════════════╣")

    # Show active servos
    active = [(ch, state.positions[ch], state.update_count[ch])
              for ch in range(MAX_CHANNELS) if state.update_count[ch] > 0]

    if not active:
        lines.append("║                                                              ║")
        lines.append("║   Waiting for angle commands on UDP...                       ║")
        lines.append("║   Start Godot or use --self-test                             ║")
        lines.append("║                                                              ║")
    else:
        for ch, pos, count in active:
            name = {0: "YAW  ", 3: "PITCH"}.get(ch, f"CH{ch:>2d} ")
            lines.append(f"║{render_servo(name, pos, 38)}  n={count:<5d}║")
            lines.append("║                                                              ║")

    # Log
    lines.append("╠══════════════════════════════════════════════════════════════╣")
    lines.append("║  Recent:                                                     ║")
    for msg in state.log[-6:]:
        lines.append(f"║    {msg:<58s}║")
    for _ in range(6 - len(state.log[-6:])):
        lines.append(f"║{'':60s}  ║")
    lines.append("╚══════════════════════════════════════════════════════════════╝")

    return '\n'.join(lines)


# ---------------------------------------------------------------------------
#  UDP listener (simulates ESP32 receiving + forwarding)
# ---------------------------------------------------------------------------
def udp_listener(port: int, state: ServoState):
    """Listen for UDP angle packets just like the ESP32 does."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", port))
    sock.settimeout(0.1)

    while True:
        try:
            data, addr = sock.recvfrom(256)
            text = data.decode("utf-8", errors="replace")
            # A single UDP packet may contain multiple lines
            for line in text.split('\n'):
                line = line.strip()
                if line:
                    state.parse_command(line)
        except socket.timeout:
            continue
        except OSError:
            break


# ---------------------------------------------------------------------------
#  Self-test: generate sweep patterns
# ---------------------------------------------------------------------------
def self_test_sender(port: int, interval: float):
    """Send sweeping angle commands to localhost UDP (simulates Godot)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    yaw = 90
    pitch = 90
    yaw_dir = 2
    pitch_dir = 1
    time.sleep(1.0)  # let listener start

    try:
        while True:
            sock.sendto(f"0,{yaw}\n".encode(), ("127.0.0.1", port))
            sock.sendto(f"3,{pitch}\n".encode(), ("127.0.0.1", port))

            yaw += yaw_dir
            if yaw >= 180 or yaw <= 0:
                yaw_dir = -yaw_dir
                yaw += yaw_dir

            pitch += pitch_dir
            if pitch >= 135 or pitch <= 45:
                pitch_dir = -pitch_dir
                pitch += pitch_dir

            time.sleep(interval)
    except KeyboardInterrupt:
        sock.close()


# ---------------------------------------------------------------------------
#  Optional: also listen on a real serial port (for testing with ESP hardware)
# ---------------------------------------------------------------------------
def serial_listener(port_name: str, baud: int, state: ServoState):
    """Read angle commands from a serial port (e.g. ESP32 via Arduino passthrough)."""
    import serial
    ser = serial.Serial(port_name, baud, timeout=0.5)
    time.sleep(1.0)
    ser.read(ser.in_waiting)  # discard boot

    while True:
        raw = ser.readline()
        if raw:
            line = raw.decode("utf-8", errors="replace").strip()
            if line:
                resp = state.parse_command(line)
                if resp:
                    ser.write(f"{resp}\n".encode())
                    ser.flush()


# ---------------------------------------------------------------------------
#  Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Arduino + PCA9685 digital twin with visual servos")
    parser.add_argument("--port", type=int, default=9685,
                        help="UDP port to listen on (default 9685)")
    parser.add_argument("--self-test", action="store_true",
                        help="Generate test angle sweeps (no Godot needed)")
    parser.add_argument("--serial", metavar="COM_PORT", default=None,
                        help="Also listen on serial (e.g. COM4 for ESP32 passthrough)")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--fps", type=float, default=10,
                        help="Dashboard refresh rate (default 10)")
    args = parser.parse_args()

    state = ServoState()

    # Start UDP listener
    t_udp = threading.Thread(target=udp_listener, args=(args.port, state), daemon=True)
    t_udp.start()

    # Optional serial listener
    if args.serial:
        t_ser = threading.Thread(target=serial_listener,
                                 args=(args.serial, args.baud, state), daemon=True)
        t_ser.start()

    # Optional self-test sender
    if args.self_test:
        t_test = threading.Thread(target=self_test_sender,
                                  args=(args.port, 0.05), daemon=True)
        t_test.start()

    print(f"[TWIN] Listening on UDP :{args.port}")
    if args.serial:
        print(f"[TWIN] Also listening on serial {args.serial}")
    if args.self_test:
        print(f"[TWIN] Self-test mode: generating sweep patterns")
    print(f"[TWIN] Press Ctrl+C to stop\n")
    time.sleep(0.5)

    try:
        while True:
            dashboard = render_dashboard(state)
            sys.stdout.write(dashboard)
            sys.stdout.flush()
            time.sleep(1.0 / args.fps)
    except KeyboardInterrupt:
        print("\n[TWIN] Stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
