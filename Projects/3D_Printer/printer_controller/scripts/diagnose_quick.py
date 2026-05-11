"""Quick diagnostic: home then send circle via WebSocket target."""
import time, json, math, threading, requests, websocket

BASE = "http://127.0.0.1:8765"
WS = "ws://127.0.0.1:8765/ws/state"

# HOME FIRST
print("Homing...")
requests.post(f"{BASE}/home", timeout=30)
time.sleep(15)
s = requests.get(f"{BASE}/state").json()
print(f"Homed: X={s['homed_x']} Y={s['homed_y']} Z={s['homed_z']}  Pos: X={s['x']} Y={s['y']} Z={s['z']}")

# Move to center
requests.post(f"{BASE}/gcode", json={"command": "G90"})
requests.post(f"{BASE}/gcode", json={"command": "G1 X110 Y110 Z5 F3000"})
time.sleep(4)
s = requests.get(f"{BASE}/state").json()
print(f"At center: X={s['x']} Y={s['y']} Z={s['z']}")

# WebSocket tracking
positions = []
ws_ready = threading.Event()

def on_msg(ws_app, m):
    d = json.loads(m)
    if d.get("type") == "state" and d.get("x") is not None:
        positions.append((time.perf_counter(), d["x"], d["y"]))

def on_open(ws_app):
    ws_ready.set()

ws = websocket.WebSocketApp(WS, on_message=on_msg, on_open=on_open)
threading.Thread(target=ws.run_forever, daemon=True).start()
ws_ready.wait(5)
positions.clear()

# Send circle targets at 100ms intervals
SEGS = 20
R = 25
t0 = time.perf_counter()
for i in range(SEGS):
    a = 2 * math.pi * i / SEGS
    x = 110 + R * math.cos(a)
    y = 110 + R * math.sin(a)
    ws.send(json.dumps({"type": "target", "x": x, "y": y, "z": 5.0}))
    time.sleep(0.1)

print(f"Sent {SEGS} targets in {(time.perf_counter()-t0)*1000:.0f}ms")
time.sleep(6)
ws.close()

print(f"\nPosition updates: {len(positions)}")
if positions:
    p0 = positions[0][0]
    for t, x, y in positions[:30]:
        print(f"  [{(t-p0)*1000:6.0f}ms] X={x:.2f} Y={y:.2f}")
    if len(positions) > 30:
        print(f"  ...({len(positions)-30} more)")
    print(f"  Avg interval: {(positions[-1][0]-p0)*1000/len(positions):.0f}ms")
