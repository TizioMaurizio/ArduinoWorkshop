#!/usr/bin/env python3
"""Digital twin of the Arduino PCA9685-ServoController.

Connects to the ESP32-CAM's USB serial (UART0 debug output via Arduino
passthrough) and behaves exactly like the real Arduino firmware:

  - Parses "<channel>,<angle>\n" lines
  - Validates channel 0-15, angle 0-180
  - Replies "OK\n" or "ERR:<message>\n"
  - Tracks servo positions and prints a live dashboard

Additionally sends test UDP angle packets to the ESP32 so you can verify
the full chain:  Python UDP → ESP32 WiFi → ESP32 UART2 (GPIO 13) →
Arduino pin 0 (RX) → here via USB passthrough.

Wiring for this test (Arduino in passthrough mode):
  - Arduino RESET → GND  (disables ATmega, USB chip becomes passthrough)
  - ESP32 GPIO 13 → Arduino pin 0 (RX)  — ESP32 UART2 TX
  - Arduino USB → PC (COM port)
  - ESP32 powered via its own USB or 5V pin

Usage:
    python test_arduino_twin.py COM4                          # listen only
    python test_arduino_twin.py COM4 --send-udp 10.105.54.157 # send + listen
    python test_arduino_twin.py COM4 --send-udp 10.105.54.157 --godot
        (--godot skips built-in UDP sender, waits for Godot to send packets)

Requires: pip install pyserial
"""

import argparse
import socket
import sys
import time
import threading
import os

try:
    import serial
except ImportError:
    print("ERROR: pyserial not installed. Run:  pip install pyserial")
    sys.exit(1)


# ---------------------------------------------------------------------------
#  Servo state (mirrors PCA9685-ServoController)
# ---------------------------------------------------------------------------
MAX_CHANNELS = 16
MAX_ANGLE = 180
servo_positions = [90] * MAX_CHANNELS  # all start at centre like real firmware
servo_update_count = [0] * MAX_CHANNELS
last_update_time = [0.0] * MAX_CHANNELS
total_commands = 0
total_errors = 0
start_time = 0.0


def parse_and_respond(line: str) -> str:
    """Mirror of parse_and_execute() from PCA9685-ServoController firmware.
    Returns the response string."""
    global total_commands, total_errors

    if not line.strip():
        return None  # empty line, no response (matches firmware)

    comma_idx = line.find(',')
    if comma_idx < 0:
        total_errors += 1
        return "ERR:no comma"

    try:
        channel = int(line[:comma_idx])
    except ValueError:
        total_errors += 1
        return "ERR:bad channel"

    try:
        angle = int(line[comma_idx + 1:])
    except ValueError:
        total_errors += 1
        return "ERR:bad angle"

    if channel < 0 or channel >= MAX_CHANNELS:
        total_errors += 1
        return "ERR:ch 0-15"

    if angle < 0 or angle > MAX_ANGLE:
        total_errors += 1
        return "ERR:ang 0-180"

    # Valid command — update servo state
    old = servo_positions[channel]
    servo_positions[channel] = angle
    servo_update_count[channel] += 1
    last_update_time[channel] = time.time()
    total_commands += 1

    return "OK"


def print_dashboard():
    """Print a compact servo state dashboard."""
    elapsed = time.time() - start_time
    hz = total_commands / elapsed if elapsed > 0 else 0

    # Only show channels that received at least one command
    active = [(ch, servo_positions[ch], servo_update_count[ch])
              for ch in range(MAX_CHANNELS) if servo_update_count[ch] > 0]

    lines = []
    lines.append(f"\n{'═' * 60}")
    lines.append(f"  ARDUINO TWIN  │  {total_commands} cmds  {total_errors} errs  "
                 f"{hz:.1f} cmd/s  {elapsed:.0f}s uptime")
    lines.append(f"{'─' * 60}")

    if not active:
        lines.append("  (no servo commands received yet)")
    else:
        for ch, pos, count in active:
            bar_len = 30
            filled = int(pos / 180 * bar_len)
            bar = '█' * filled + '░' * (bar_len - filled)
            lines.append(f"  CH{ch:>2d}  [{bar}] {pos:>3d}°  ({count} updates)")

    lines.append(f"{'═' * 60}")
    print('\n'.join(lines))


# ---------------------------------------------------------------------------
#  UDP sender (sends test angles to ESP32)
# ---------------------------------------------------------------------------
def udp_sender(esp_ip: str, port: int, interval: float):
    """Send sweeping test angle commands via UDP to the ESP32."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # Sweep pattern: yaw 0→180, pitch 45→135
    print(f"[UDP-TX] Sending sweep to {esp_ip}:{port} every {interval}s")
    yaw = 0
    pitch = 45
    yaw_dir = 3    # degrees per step
    pitch_dir = 2

    try:
        while True:
            # Send yaw
            msg_yaw = f"0,{yaw}\n"
            sock.sendto(msg_yaw.encode(), (esp_ip, port))

            # Send pitch
            msg_pitch = f"3,{pitch}\n"
            sock.sendto(msg_pitch.encode(), (esp_ip, port))

            # Bounce
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
#  Main serial loop
# ---------------------------------------------------------------------------
def main():
    global start_time

    parser = argparse.ArgumentParser(
        description="Arduino PCA9685 digital twin — test ESP32 angle bridge")
    parser.add_argument("port", help="Serial port (e.g. COM4, /dev/ttyUSB0)")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--send-udp", metavar="ESP_IP", default=None,
                        help="Send test UDP angle sweeps to this ESP32 IP")
    parser.add_argument("--udp-port", type=int, default=9685)
    parser.add_argument("--udp-interval", type=float, default=0.1,
                        help="Seconds between UDP test packets (default 0.1)")
    parser.add_argument("--godot", action="store_true",
                        help="Skip built-in UDP sender; wait for Godot to send")
    parser.add_argument("--dashboard-interval", type=float, default=2.0,
                        help="Seconds between dashboard refreshes (default 2)")
    args = parser.parse_args()

    print(f"[TWIN] Opening {args.port} @ {args.baud} baud")
    try:
        ser = serial.Serial(args.port, args.baud, timeout=0.5)
    except serial.SerialException as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    # Wait for settled serial
    time.sleep(1.0)
    boot = ser.read(ser.in_waiting).decode("utf-8", errors="replace").strip()
    if boot:
        print(f"[BOOT] {boot}")

    # Start UDP sender if requested (and not --godot)
    if args.send_udp and not args.godot:
        t = threading.Thread(target=udp_sender,
                             args=(args.send_udp, args.udp_port, args.udp_interval),
                             daemon=True)
        t.start()
    elif args.godot:
        print("[TWIN] Waiting for Godot to send UDP packets to ESP32...")

    print(f"[TWIN] Arduino digital twin running on {args.port}")
    print(f"[TWIN] Parsing '<ch>,<angle>' commands, replying OK/ERR")
    print(f"[TWIN] Press Ctrl+C to stop\n")

    start_time = time.time()
    last_dashboard = time.time()

    try:
        while True:
            # Read a line from serial
            raw = ser.readline()
            if raw:
                line = raw.decode("utf-8", errors="replace").strip()
                if line:
                    response = parse_and_respond(line)
                    if response:
                        # Print the exchange
                        tag = "OK" if response == "OK" else "ERR"
                        print(f"  [RX] {line!r:20s}  → [{tag}] {response}")

                        # Send response back (like real Arduino)
                        ser.write(f"{response}\n".encode("utf-8"))
                        ser.flush()

            # Periodic dashboard
            now = time.time()
            if now - last_dashboard >= args.dashboard_interval:
                print_dashboard()
                last_dashboard = now

    except KeyboardInterrupt:
        print_dashboard()
        print(f"\n[TWIN] Stopped. {total_commands} valid commands, "
              f"{total_errors} errors in {time.time() - start_time:.1f}s")
        ser.close()


if __name__ == "__main__":
    main()
