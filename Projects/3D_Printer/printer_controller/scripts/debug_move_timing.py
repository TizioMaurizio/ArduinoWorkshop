"""Investigate why single-axis move takes 10s after homing."""
import requests, time

BASE = "http://127.0.0.1:8765"

# First, home
print("Homing...")
t_home = time.time()
requests.post(f"{BASE}/home", timeout=30)
# Wait for homing to complete
last_pos = None
stable = 0
while time.time() - t_home < 25:
    s = requests.get(f"{BASE}/state").json()
    pos = (s["x"], s["y"], s["z"])
    if pos == last_pos:
        stable += 1
        if stable >= 3:
            break
    else:
        stable = 0
        last_pos = pos
    time.sleep(0.5)
s = requests.get(f"{BASE}/state").json()
print(f"Homed in {time.time()-t_home:.1f}s: X={s['x']:.2f} Y={s['y']:.2f} Z={s['z']:.2f}")

# Now send G90 + G1 X50 with precise timing
print("\nSending G90...")
t0 = time.time()
r = requests.post(f"{BASE}/gcode", json={"command": "G90"})
print(f"  G90 sent ({(time.time()-t0)*1000:.0f}ms)")

print("Sending G1 X50 F3000...")
t1 = time.time()
r = requests.post(f"{BASE}/gcode", json={"command": "G1 X50 F3000"})
print(f"  G1 sent ({(time.time()-t1)*1000:.0f}ms)")

# Poll for position with timestamps
target_y = s["y"]
target_z = s["z"]
print(f"  Waiting for X=50 (Y={target_y:.1f}, Z={target_z:.1f})...")
for i in range(40):
    time.sleep(0.3)
    s = requests.get(f"{BASE}/state").json()
    elapsed = (time.time() - t1) * 1000
    print(f"  [{elapsed:6.0f}ms] X={s['x']:.2f} Y={s['y']:.2f} Z={s['z']:.2f}")
    if abs(s["x"] - 50) < 1.5 and abs(s["y"] - target_y) < 1.5:
        print(f"  REACHED in {elapsed:.0f}ms")
        break

# Return
print("Returning to origin...")
requests.post(f"{BASE}/gcode", json={"command": "G1 X0 Y0 Z0 F3000"})
