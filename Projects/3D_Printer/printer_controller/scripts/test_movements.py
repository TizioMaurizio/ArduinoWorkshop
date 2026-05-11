"""End-to-end movement test: home, axis moves, follower circle, timing check."""
import time, json, math, threading, sys
import requests, websocket

BASE = "http://127.0.0.1:8765"
WS   = "ws://127.0.0.1:8765/ws/state"
PASS = 0
FAIL = 0

def check(name: str, ok: bool, detail: str = ""):
    global PASS, FAIL
    tag = "PASS" if ok else "FAIL"
    if not ok:
        FAIL += 1
    else:
        PASS += 1
    msg = f"  [{tag}] {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)

def get_state():
    return requests.get(f"{BASE}/state", timeout=5).json()

def send_gcode(cmd):
    return requests.post(f"{BASE}/gcode", json={"command": cmd}, timeout=5).json()

def wait_for_position(target_x, target_y, target_z, tol=2.0, timeout=15):
    """Poll state until printer reaches target within tolerance."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = get_state()
        dx = abs(s["x"] - target_x)
        dy = abs(s["y"] - target_y)
        dz = abs(s["z"] - target_z)
        if dx < tol and dy < tol and dz < tol:
            return s, time.time() - t0
        time.sleep(0.3)
    return get_state(), time.time() - t0

# ── 0. Connectivity ──────────────────────────────────────────────────
print("=" * 60)
print("TEST 0: Connectivity")
print("=" * 60)
try:
    h = requests.get(f"{BASE}/health", timeout=3).json()
    check("API reachable", h.get("status") == "ok")
except Exception as e:
    check("API reachable", False, str(e))
    sys.exit(1)

s = get_state()
check("Printer connected", s.get("connected") is True, f"connected={s.get('connected')}")
if not s.get("connected"):
    print("  Cannot proceed without printer connection.")
    sys.exit(1)

# ── 1. Auto Home ─────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("TEST 1: Auto Home (G28)")
print("=" * 60)
print("  Sending G28...")
t0 = time.time()
initial_pos = (s["x"], s["y"], s["z"]) if (s := get_state()) else (0, 0, 0)
requests.post(f"{BASE}/home", timeout=30)

# Phase 1: Wait for homing to actually start (position changes or busy flag)
# G28 is queued — it may take a moment before the send_loop processes it.
started = False
while time.time() - t0 < 25:
    s = get_state()
    pos = (s["x"], s["y"], s["z"])
    if pos != initial_pos or s.get("busy"):
        started = True
        break
    time.sleep(0.5)

# Phase 2: Wait for homing to complete (position stabilizes)
if started:
    last_pos = None
    stable_count = 0
    while time.time() - t0 < 25:
        s = get_state()
        pos = (s["x"], s["y"], s["z"])
        if last_pos == pos:
            stable_count += 1
            if stable_count >= 3:
                break
        else:
            stable_count = 0
            last_pos = pos
        time.sleep(0.5)
else:
    # Homing may have returned to same position; just wait a fixed time
    time.sleep(12)
    s = get_state()

elapsed = time.time() - t0
s = get_state()
# Marlin may report small offsets after homing; check homed flags
check("Homed X", s.get("homed_x") is True)
check("Homed Y", s.get("homed_y") is True)
check("Homed Z", s.get("homed_z") is True)
print(f"  Position after home: X={s['x']:.1f} Y={s['y']:.1f} Z={s['z']:.1f} (took {elapsed:.1f}s)")

# ── 2. Single axis moves ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("TEST 2: Single Axis Moves")
print("=" * 60)

# First move to a known start position (0,0,0) so individual axis tests
# have predictable Y/Z values to compare against
send_gcode("G90")
send_gcode("G1 X0 Y0 Z0 F3000")
s, t = wait_for_position(0, 0, 0, tol=2.0, timeout=15)
print(f"  Start position: X={s['x']:.1f} Y={s['y']:.1f} Z={s['z']:.1f} ({t:.1f}s)")

# Move X to 50
send_gcode("G1 X50 F3000")
s, t = wait_for_position(50, 0, 0, tol=1.5, timeout=10)
check("X move to 50", abs(s["x"] - 50) < 1.5, f"X={s['x']:.2f} ({t:.1f}s)")

# Move Y to 50
send_gcode("G1 Y50 F3000")
s, t = wait_for_position(50, 50, s["z"], tol=1.5, timeout=10)
check("Y move to 50", abs(s["y"] - 50) < 1.5, f"Y={s['y']:.2f} ({t:.1f}s)")

# Move Z to 10
send_gcode("G1 Z10 F300")
s, t = wait_for_position(50, 50, 10, tol=1.5, timeout=15)
check("Z move to 10", abs(s["z"] - 10) < 1.5, f"Z={s['z']:.2f} ({t:.1f}s)")

# Move to center
send_gcode("G1 X110 Y110 Z5 F3000")
s, t = wait_for_position(110, 110, 5, tol=1.5, timeout=10)
check("Move to center", abs(s["x"] - 110) < 1.5 and abs(s["y"] - 110) < 1.5,
      f"X={s['x']:.1f} Y={s['y']:.1f} Z={s['z']:.1f} ({t:.1f}s)")

# ── 3. WebSocket follower circle ─────────────────────────────────────
print("\n" + "=" * 60)
print("TEST 3: Follower Loop — WebSocket Circle")
print("=" * 60)

positions = []
ws_ready = threading.Event()

def on_msg(ws_app, m):
    d = json.loads(m)
    if d.get("type") == "state" and d.get("x") is not None:
        positions.append((time.perf_counter(), d["x"], d["y"], d.get("z", 0)))

def on_open(ws_app):
    ws_ready.set()

ws = websocket.WebSocketApp(WS, on_message=on_msg, on_open=on_open)
threading.Thread(target=ws.run_forever, daemon=True).start()
ws_ready.wait(5)
check("WebSocket connected", ws_ready.is_set())
time.sleep(0.5)
positions.clear()

# Send circle targets — 20 segments, R=25mm around center, 100ms apart
SEGS = 20
R = 25.0
CX, CY = 110.0, 110.0
circle_points = []
t0 = time.perf_counter()
for i in range(SEGS):
    a = 2 * math.pi * i / SEGS
    x = CX + R * math.cos(a)
    y = CY + R * math.sin(a)
    circle_points.append((x, y))
    ws.send(json.dumps({"type": "target", "x": round(x, 3), "y": round(y, 3), "z": 5.0}))
    time.sleep(0.1)

send_elapsed = time.perf_counter() - t0
print(f"  Sent {SEGS} targets in {send_elapsed*1000:.0f}ms")

# Wait for printer to finish moving
time.sleep(6)
ws.close()

# Analyze position tracking
if len(positions) > 0:
    t_start = positions[0][0]
    t_end = positions[-1][0]
    tracking_time = t_end - t_start

    # Count distinct positions (deduplicate consecutive same values)
    distinct = [(positions[0][1], positions[0][2])]
    for _, x, y, _ in positions[1:]:
        if abs(x - distinct[-1][0]) > 0.5 or abs(y - distinct[-1][1]) > 0.5:
            distinct.append((x, y))

    check("Position updates received", len(positions) >= 5,
          f"{len(positions)} updates over {tracking_time:.1f}s")
    check("Distinct positions tracked", len(distinct) >= 3,
          f"{len(distinct)} distinct positions")

    # Check that the final position is near the last circle point
    last_x, last_y = circle_points[-1]
    final_s = get_state()
    fx, fy = final_s["x"], final_s["y"]
    check("Final position near last target",
          abs(fx - last_x) < 5 and abs(fy - last_y) < 5,
          f"target=({last_x:.1f},{last_y:.1f}) actual=({fx:.1f},{fy:.1f})")

    # Print timeline
    print(f"\n  Position timeline ({len(positions)} samples):")
    for ts, x, y, z in positions[:20]:
        print(f"    [{(ts - t_start)*1000:7.0f}ms] X={x:.2f} Y={y:.2f}")
    if len(positions) > 20:
        print(f"    ...({len(positions)-20} more)")
    avg_interval = tracking_time * 1000 / max(len(positions) - 1, 1)
    print(f"  Avg update interval: {avg_interval:.0f}ms")
    check("Update interval reasonable", avg_interval < 600,
          f"{avg_interval:.0f}ms (want <600ms)")
else:
    check("Position updates received", False, "no updates!")

# ── 4. Safety — out of bounds ─────────────────────────────────────────
print("\n" + "=" * 60)
print("TEST 4: Safety — Out-of-Bounds Rejection")
print("=" * 60)
r = send_gcode("G1 X-10 Y0 Z0 F1000")
check("Negative X rejected", "error" in r, f"response={r}")
r = send_gcode("G1 X0 Y300 Z0 F1000")
check("Y>220 rejected", "error" in r, f"response={r}")

# ── 5. Return home ───────────────────────────────────────────────────
print("\n" + "=" * 60)
print("TEST 5: Return Home")
print("=" * 60)
send_gcode("G1 X0 Y0 Z0 F3000")
s, t = wait_for_position(0, 0, 0, tol=2, timeout=15)
check("Returned to origin", abs(s["x"]) < 2 and abs(s["y"]) < 2,
      f"X={s['x']:.1f} Y={s['y']:.1f} Z={s['z']:.1f} ({t:.1f}s)")

# ── Summary ──────────────────────────────────────────────────────────
print("\n" + "=" * 60)
total = PASS + FAIL
print(f"RESULTS: {PASS}/{total} passed, {FAIL} failed")
print("=" * 60)
sys.exit(1 if FAIL > 0 else 0)
