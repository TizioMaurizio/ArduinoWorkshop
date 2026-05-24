"""
F8620 Drone — PC Serial Controller
Sends control commands to Arduino USB Transmitter over serial.

Usage:
  python drone_control.py         # keyboard control (WASD + arrows)
  python drone_control.py --port COM3  # specify port

Keyboard controls:
  W/S         = Throttle up/down
  A/D         = Yaw left/right
  Arrow Up/Dn = Pitch forward/back
  Arrow L/R   = Roll left/right
  Space       = STOP (zero all)
  B           = Re-bind
  Q/Esc       = Quit

[SAFETY] REMOVE PROPELLERS during testing.
[SAFETY] Throttle starts at 0. Increments by 50 per keypress.
"""

import serial
import serial.tools.list_ports
import sys
import time
import threading

# Attempt to import keyboard input library
try:
    import msvcrt  # Windows
    PLATFORM = "windows"
except ImportError:
    import tty
    import termios
    PLATFORM = "unix"


def find_arduino_port():
    """Auto-detect Arduino on USB serial."""
    ports = serial.tools.list_ports.comports()
    for p in ports:
        desc = (p.description or "").lower()
        if "ch340" in desc or "arduino" in desc or "usb-serial" in desc:
            return p.device
    # Fallback: show available ports
    print("Available COM ports:")
    for p in ports:
        print(f"  {p.device}: {p.description}")
    return None


def get_key_windows():
    """Non-blocking key read on Windows."""
    if msvcrt.kbhit():
        key = msvcrt.getch()
        if key == b'\xe0' or key == b'\x00':
            # Arrow keys (extended)
            key2 = msvcrt.getch()
            return {b'H': 'UP', b'P': 'DOWN', b'K': 'LEFT', b'M': 'RIGHT'}.get(key2, None)
        return key.decode('utf-8', errors='ignore').lower()
    return None


def main():
    import argparse
    parser = argparse.ArgumentParser(description="F8620 Drone PC Controller")
    parser.add_argument("--port", help="Serial port (e.g., COM3)")
    parser.add_argument("--baud", type=int, default=115200)
    args = parser.parse_args()

    port = args.port or find_arduino_port()
    if not port:
        print("No Arduino found. Specify with --port COM3")
        sys.exit(1)

    print(f"Connecting to {port} at {args.baud} baud...")
    try:
        ser = serial.Serial(port, args.baud, timeout=0.1)
    except serial.SerialException as e:
        print(f"Cannot open {port}: {e}")
        sys.exit(1)

    time.sleep(2)  # Wait for Arduino reset

    # Read and print Arduino startup messages
    while ser.in_waiting:
        line = ser.readline().decode('utf-8', errors='replace').strip()
        if line:
            print(f"  Arduino: {line}")

    print()
    print("=== F8620 Drone Controller ===")
    print("[SAFETY] PROPELLERS REMOVED?")
    print()
    print("Controls:")
    print("  W/S       = Throttle up/down (step: 50)")
    print("  A/D       = Yaw left/right")
    print("  Arrows    = Pitch/Roll")
    print("  Space     = STOP (zero all)")
    print("  B         = Re-bind")
    print("  Q / Esc   = Quit")
    print()

    throttle = 0
    yaw = 0
    pitch = 0
    roll = 0

    THROTTLE_STEP = 50
    AXIS_STEP = 100
    AXIS_MAX = 500

    last_send = 0
    SEND_INTERVAL = 0.05  # 20 Hz command rate

    running = True

    # Background thread to read Arduino responses
    def read_serial():
        while running:
            try:
                if ser.in_waiting:
                    line = ser.readline().decode('utf-8', errors='replace').strip()
                    if line:
                        print(f"  << {line}")
            except Exception:
                break
            time.sleep(0.05)

    reader = threading.Thread(target=read_serial, daemon=True)
    reader.start()

    try:
        while running:
            key = get_key_windows() if PLATFORM == "windows" else None

            if key:
                if key == 'q' or key == '\x1b':
                    break
                elif key == 'w':
                    throttle = min(throttle + THROTTLE_STEP, 1000)
                elif key == 's':
                    throttle = max(throttle - THROTTLE_STEP, 0)
                elif key == 'a':
                    yaw = max(yaw - AXIS_STEP, -AXIS_MAX)
                elif key == 'd':
                    yaw = min(yaw + AXIS_STEP, AXIS_MAX)
                elif key == 'UP':
                    pitch = min(pitch + AXIS_STEP, AXIS_MAX)
                elif key == 'DOWN':
                    pitch = max(pitch - AXIS_STEP, -AXIS_MAX)
                elif key == 'LEFT':
                    roll = max(roll - AXIS_STEP, -AXIS_MAX)
                elif key == 'RIGHT':
                    roll = min(roll + AXIS_STEP, AXIS_MAX)
                elif key == ' ':
                    throttle = 0
                    yaw = 0
                    pitch = 0
                    roll = 0
                    ser.write(b'STOP\n')
                elif key == 'b':
                    ser.write(b'BIND\n')
                    throttle = 0
                    yaw = 0
                    pitch = 0
                    roll = 0
                    print("  >> BIND")

                # Return axes to center when not held (simple auto-center)
                # Yaw/pitch/roll decay toward 0
            else:
                # Auto-center axes (decay)
                if yaw > 0:
                    yaw = max(yaw - 20, 0)
                elif yaw < 0:
                    yaw = min(yaw + 20, 0)
                if pitch > 0:
                    pitch = max(pitch - 20, 0)
                elif pitch < 0:
                    pitch = min(pitch + 20, 0)
                if roll > 0:
                    roll = max(roll - 20, 0)
                elif roll < 0:
                    roll = min(roll + 20, 0)

            # Send command at interval
            now = time.time()
            if now - last_send >= SEND_INTERVAL:
                cmd = f"T{throttle} Y{yaw} P{pitch} R{roll}\n"
                ser.write(cmd.encode())
                last_send = now

                # Status line
                bar = "█" * (throttle // 50)
                sys.stdout.write(
                    f"\r  T={throttle:4d} Y={yaw:+4d} P={pitch:+4d} R={roll:+4d}"
                    f"  [{bar:<20}]   "
                )
                sys.stdout.flush()

            time.sleep(0.02)

    except KeyboardInterrupt:
        pass
    finally:
        running = False
        # Safety: send stop
        ser.write(b'STOP\n')
        time.sleep(0.1)
        ser.close()
        print("\n\nDisconnected. Motors stopped.")


if __name__ == "__main__":
    main()
