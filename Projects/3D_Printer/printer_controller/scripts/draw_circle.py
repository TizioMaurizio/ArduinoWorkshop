"""
Draw a circle at the center of the bed.

Steps:
  1. Wait for backend to be ready
  2. Home all axes (G28)
  3. Move to center at safe Z height
  4. Draw a circle using segmented G1 moves
  5. Return to center
  6. Print final position

Uses the REST API at http://127.0.0.1:8765
"""

import math
import time
import requests

BASE = "http://127.0.0.1:8765"

# ── Circle parameters ─────────────────────────────────────────────────
CENTER_X = 110.0   # mm — center of 220mm bed
CENTER_Y = 110.0
RADIUS = 30.0      # mm
Z_HEIGHT = 5.0     # mm above bed
SEGMENTS = 72      # number of line segments (5° each)
FEEDRATE_XY = 2000  # mm/min for circle
FEEDRATE_TRAVEL = 3000


def send_gcode(cmd: str) -> dict:
    """Send a raw G-code command via REST API."""
    r = requests.post(f"{BASE}/gcode", json={"command": cmd}, timeout=10)
    data = r.json()
    if "error" in data:
        print(f"  ✗ {cmd} → ERROR: {data['error']}")
    else:
        print(f"  ✓ {cmd}")
    return data


def get_state() -> dict:
    """Fetch current printer state."""
    r = requests.get(f"{BASE}/state", timeout=5)
    return r.json()


def wait_for_backend():
    """Wait until the backend is up and printer is connected."""
    print("Waiting for backend...")
    for _ in range(30):
        try:
            r = requests.get(f"{BASE}/health", timeout=2)
            if r.status_code == 200:
                print("  Backend is up.")
                break
        except requests.ConnectionError:
            pass
        time.sleep(1)
    else:
        raise RuntimeError("Backend not reachable after 30s")

    print("Waiting for printer connection...")
    for _ in range(30):
        s = get_state()
        if s.get("connected"):
            print(f"  Connected: {s.get('firmware', 'unknown')}")
            return s
        time.sleep(1)
    raise RuntimeError("Printer not connected after 30s")


def home_all():
    """Home all axes via REST endpoint and wait for completion."""
    print("\n── Homing all axes ──")
    r = requests.post(f"{BASE}/home", timeout=30)
    data = r.json()
    print(f"  Home response: {data}")

    # Wait for homing to finish (busy → not busy, position resets to 0)
    print("  Waiting for homing to complete...")
    for _ in range(60):
        time.sleep(1)
        s = get_state()
        if s.get("homed_x") and s.get("homed_y") and s.get("homed_z"):
            if not s.get("busy"):
                print(f"  Homed! Position: X={s['x']}, Y={s['y']}, Z={s['z']}")
                return s
    raise RuntimeError("Homing did not complete in 60s")


def print_position(label: str = "Position"):
    """Query and print current position."""
    send_gcode("M114")
    time.sleep(0.5)
    s = get_state()
    print(f"  {label}: X={s.get('x', '?'):.2f}  Y={s.get('y', '?'):.2f}  Z={s.get('z', '?'):.2f}")
    return s


def draw_circle():
    """Draw a circle using segmented G1 absolute moves."""
    print(f"\n── Drawing circle: center=({CENTER_X},{CENTER_Y}), R={RADIUS}mm, Z={Z_HEIGHT}mm ──")

    # Ensure absolute positioning
    send_gcode("G90")

    # Move to Z height first (safe travel)
    print("\n  Moving to safe Z height...")
    send_gcode(f"G1 Z{Z_HEIGHT:.1f} F{FEEDRATE_TRAVEL}")
    time.sleep(1)

    # Move to start of circle (0° = center + radius on X axis)
    start_x = CENTER_X + RADIUS
    start_y = CENTER_Y
    print(f"  Moving to circle start ({start_x:.1f}, {start_y:.1f})...")
    send_gcode(f"G1 X{start_x:.1f} Y{start_y:.1f} F{FEEDRATE_TRAVEL}")
    time.sleep(2)

    print_position("At circle start")

    # Draw circle segments
    print(f"\n  Drawing {SEGMENTS} segments...")
    t_start = time.time()

    for i in range(1, SEGMENTS + 1):
        angle = 2 * math.pi * i / SEGMENTS
        x = CENTER_X + RADIUS * math.cos(angle)
        y = CENTER_Y + RADIUS * math.sin(angle)
        send_gcode(f"G1 X{x:.3f} Y{y:.3f} F{FEEDRATE_XY}")

        # Print position feedback every 12 segments (60°)
        if i % 12 == 0:
            time.sleep(0.3)
            print_position(f"  Progress {i}/{SEGMENTS} ({360*i//SEGMENTS}°)")

    elapsed = time.time() - t_start
    print(f"\n  Circle complete in {elapsed:.1f}s")

    # Wait for motion to finish
    time.sleep(3)
    print_position("After circle")

    # Return to center
    print("\n  Returning to center...")
    send_gcode(f"G1 X{CENTER_X:.1f} Y{CENTER_Y:.1f} F{FEEDRATE_TRAVEL}")
    time.sleep(2)
    print_position("Final position")


def main():
    wait_for_backend()
    state = home_all()

    # Report printer info
    print(f"\n── Printer info ──")
    print(f"  Firmware:  {state.get('firmware', '?')}")
    print(f"  Hotend:    {state.get('hotend_temp_c', '?')}°C")
    print(f"  Bed:       {state.get('bed_temp_c', '?')}°C")

    draw_circle()

    print("\n── Done ──")


if __name__ == "__main__":
    main()
