"""
Diagnostic: Timestamped serial timing analysis.

Tests the round-trip latency of:
  1. Single G1 moves (with ok-gated flow)
  2. Rapid successive G1 moves (simulating follower loop)
  3. G1 with M114 interleaved (position query impact)

Prints detailed timing for each command to understand where stutters originate.
"""

import math
import time
import requests
import json
import threading
import websocket  # pip install websocket-client

BASE = "http://127.0.0.1:8765"
WS_URL = "ws://127.0.0.1:8765/ws/state"


def ts() -> str:
    """Millisecond-resolution timestamp."""
    return f"[{time.perf_counter()*1000:.1f}ms]"


def send_gcode(cmd: str) -> tuple[dict, float]:
    """Send G-code, return (response, round_trip_ms)."""
    t0 = time.perf_counter()
    r = requests.post(f"{BASE}/gcode", json={"command": cmd}, timeout=10)
    dt = (time.perf_counter() - t0) * 1000
    return r.json(), dt


def get_state() -> dict:
    r = requests.get(f"{BASE}/state", timeout=5)
    return r.json()


def wait_ready():
    """Wait for backend + printer."""
    print(f"{ts()} Waiting for backend...")
    for _ in range(20):
        try:
            r = requests.get(f"{BASE}/health", timeout=2)
            if r.status_code == 200:
                break
        except:
            pass
        time.sleep(1)

    print(f"{ts()} Waiting for printer...")
    for _ in range(20):
        s = get_state()
        if s.get("connected"):
            print(f"{ts()} Connected: {s.get('firmware')}")
            return s
        time.sleep(1)
    raise RuntimeError("Printer not ready")


def test_single_moves():
    """Test 5 individual G1 moves with timing."""
    print(f"\n{'='*60}")
    print(f"{ts()} TEST 1: Single G1 moves (REST API round-trip)")
    print(f"{'='*60}")

    send_gcode("G90")
    send_gcode("G1 X50 Y50 F3000")
    time.sleep(2)

    for i in range(5):
        x = 60 + i * 10
        cmd = f"G1 X{x} Y{60 + i*5} F3000"
        t0 = time.perf_counter()
        resp, dt = send_gcode(cmd)
        print(f"  {ts()} {cmd:30s} → API RT: {dt:.1f}ms  resp: {resp.get('status', resp.get('error'))}")
        time.sleep(0.5)  # let printer move


def test_rapid_sequence():
    """Test rapid G1 moves simulating the follower loop timing."""
    print(f"\n{'='*60}")
    print(f"{ts()} TEST 2: Rapid G1 sequence (200ms intervals, follower-like)")
    print(f"{'='*60}")

    send_gcode("G90")
    send_gcode("G1 X110 Y110 F3000")
    time.sleep(2)

    # Simulate follower loop: circle at 200ms intervals
    times = []
    SEGMENTS = 20
    RADIUS = 20
    INTERVAL = 0.200  # 200ms tick

    print(f"  Sending {SEGMENTS} G1 moves at {INTERVAL*1000:.0f}ms intervals...")
    t_start = time.perf_counter()

    for i in range(SEGMENTS):
        angle = 2 * math.pi * i / SEGMENTS
        x = 110 + RADIUS * math.cos(angle)
        y = 110 + RADIUS * math.sin(angle)
        cmd = f"G1 X{x:.2f} Y{y:.2f} F3000"

        t0 = time.perf_counter()
        resp, dt = send_gcode(cmd)
        elapsed = (time.perf_counter() - t_start) * 1000
        times.append(dt)
        print(f"  {ts()} [{elapsed:7.1f}ms] {cmd:35s} → {dt:.1f}ms")

        # Wait remaining time in tick
        used = time.perf_counter() - t0
        remain = INTERVAL - used
        if remain > 0:
            time.sleep(remain)

    avg = sum(times) / len(times)
    mx = max(times)
    mn = min(times)
    print(f"\n  Stats: avg={avg:.1f}ms  min={mn:.1f}ms  max={mx:.1f}ms")


def test_websocket_target():
    """Test sending targets via WebSocket (actual follower path)."""
    print(f"\n{'='*60}")
    print(f"{ts()} TEST 3: WebSocket target messages (actual follower path)")
    print(f"{'='*60}")

    # Connect WS and monitor state updates
    positions = []
    ws_connected = threading.Event()

    def on_message(ws, message):
        data = json.loads(message)
        if data.get("type") == "state":
            x = data.get("x")
            y = data.get("y")
            if x is not None:
                positions.append((time.perf_counter(), x, y))

    def on_open(ws):
        ws_connected.set()

    ws = websocket.WebSocketApp(
        WS_URL,
        on_message=on_message,
        on_open=on_open,
    )
    ws_thread = threading.Thread(target=ws.run_forever, daemon=True)
    ws_thread.start()
    ws_connected.wait(timeout=5)

    if not ws_connected.is_set():
        print(f"  {ts()} ERROR: WebSocket did not connect")
        return

    print(f"  {ts()} WebSocket connected, sending target circle via WS...")

    # First home to known position
    send_gcode("G90")
    send_gcode("G1 X110 Y110 F3000")
    time.sleep(3)
    positions.clear()

    # Send targets at 200ms intervals via WebSocket
    SEGMENTS = 20
    RADIUS = 25
    INTERVAL = 0.200
    t_start = time.perf_counter()

    for i in range(SEGMENTS):
        angle = 2 * math.pi * i / SEGMENTS
        x = 110 + RADIUS * math.cos(angle)
        y = 110 + RADIUS * math.sin(angle)

        target_msg = json.dumps({"type": "target", "x": x, "y": y, "z": 5.0})
        ws.send(target_msg)

        elapsed = (time.perf_counter() - t_start) * 1000
        print(f"  {ts()} [{elapsed:7.1f}ms] Sent target X={x:.1f} Y={y:.1f}")
        time.sleep(INTERVAL)

    # Wait for printer to finish
    total_send_time = (time.perf_counter() - t_start) * 1000
    print(f"\n  {ts()} All targets sent in {total_send_time:.0f}ms, waiting 5s for motion...")
    time.sleep(5)

    ws.close()

    # Analyze position updates
    if positions:
        print(f"\n  Position updates received: {len(positions)}")
        t0 = positions[0][0]
        for i, (t, x, y) in enumerate(positions[:15]):
            print(f"    [{(t-t0)*1000:7.1f}ms] X={x:.2f} Y={y:.2f}")
        if len(positions) > 15:
            print(f"    ... ({len(positions) - 15} more)")
        last_t = positions[-1][0]
        print(f"    Total tracking time: {(last_t-t0)*1000:.0f}ms")
        print(f"    Avg update interval: {(last_t-t0)*1000/len(positions):.0f}ms")
    else:
        print(f"  WARNING: No position updates received!")


def main():
    wait_ready()

    s = get_state()
    print(f"\n{ts()} Printer state:")
    print(f"  Position: X={s.get('x')} Y={s.get('y')} Z={s.get('z')}")
    print(f"  Homed: X={s.get('homed_x')} Y={s.get('homed_y')} Z={s.get('homed_z')}")
    print(f"  Busy: {s.get('busy')}  Locked: {s.get('locked')}")

    if not (s.get("homed_x") and s.get("homed_y") and s.get("homed_z")):
        print(f"\n{ts()} Homing...")
        requests.post(f"{BASE}/home", timeout=30)
        time.sleep(15)
        print(f"{ts()} Homed.")

    test_single_moves()
    test_rapid_sequence()
    test_websocket_target()

    print(f"\n{'='*60}")
    print(f"{ts()} DIAGNOSTIC COMPLETE")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
