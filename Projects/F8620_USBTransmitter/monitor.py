"""Monitor the XN297 dump sketch output for 30 seconds."""
import serial
import time

s = serial.Serial('COM4', 1000000, timeout=0.5)
time.sleep(2)

# Read startup
data = s.read(s.in_waiting)
print(data.decode('utf-8', errors='replace'))
print("=" * 50)
print("MONITORING FOR 30 SECONDS - TX MUST BE ON!")
print("=" * 50)
print()

start = time.time()
while time.time() - start < 30:
    d = s.readline()
    if d.strip():
        line = d.decode('utf-8', errors='replace').strip()
        print(f"[{time.time()-start:5.1f}s] {line}")

s.close()
print("\nDone.")
