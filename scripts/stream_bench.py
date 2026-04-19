#!/usr/bin/env python3
"""Measure ESP32-CAM MJPEG stream performance — frame timing, sizes, FPS.
Bypasses Godot entirely to isolate ESP32 vs client bottleneck.

Usage: python scripts/stream_bench.py [IP] [DURATION_SEC]
"""
import socket
import sys
import time

ESP_IP = sys.argv[1] if len(sys.argv) > 1 else "10.224.248.157"
ESP_PORT = 81
DURATION = int(sys.argv[2]) if len(sys.argv) > 2 else 10

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(10)
s.connect((ESP_IP, ESP_PORT))
s.sendall(("GET /stream HTTP/1.0\r\nHost: %s\r\n\r\n" % ESP_IP).encode())

buf = b""
header_skipped = False
frames = []
start = time.time()
frame_count = 0
last_frame_time = time.time()

print("Connected to %s:%d — measuring for %ds..." % (ESP_IP, ESP_PORT, DURATION))
print("%5s %8s %8s %6s %8s" % ("Frame", "Size(B)", "dt(ms)", "FPS", "Elapsed"))
print("-" * 45)

try:
    while time.time() - start < DURATION:
        chunk = s.recv(8192)
        if not chunk:
            print("Connection closed by ESP32")
            break
        buf += chunk

        if not header_skipped:
            idx = buf.find(b"\r\n\r\n")
            if idx >= 0:
                buf = buf[idx + 4:]
                header_skipped = True
            continue

        # Scan for complete JPEG frames (SOI=FFD8, EOI=FFD9)
        while True:
            soi = buf.find(b"\xff\xd8")
            if soi < 0:
                break
            eoi = buf.find(b"\xff\xd9", soi + 2)
            if eoi < 0:
                break
            frame_end = eoi + 2
            frame_data = buf[soi:frame_end]
            buf = buf[frame_end:]

            now = time.time()
            dt = (now - last_frame_time) * 1000
            frame_count += 1
            elapsed = now - start
            fps = frame_count / elapsed if elapsed > 0 else 0

            frames.append({"size": len(frame_data), "dt_ms": dt, "time": now})
            if frame_count <= 30 or frame_count % 20 == 0:
                print("%5d %8d %8.1f %6.1f %8.2f" % (
                    frame_count, len(frame_data), dt, fps, elapsed))
            last_frame_time = now

except socket.timeout:
    print("Socket timeout")
except Exception as e:
    print("Error: %s" % e)

s.close()

# Summary
if frames:
    sizes = [f["size"] for f in frames]
    dts = [f["dt_ms"] for f in frames[1:]]  # skip first dt
    total_time = frames[-1]["time"] - frames[0]["time"] if len(frames) > 1 else 0
    avg_fps = (len(frames) - 1) / total_time if total_time > 0 else 0

    print()
    print("=" * 45)
    print("Frames received:  %d" % len(frames))
    print("Total time:       %.2fs" % total_time)
    print("Average FPS:      %.1f" % avg_fps)
    print("Frame size:       min=%d avg=%d max=%d bytes" % (
        min(sizes), sum(sizes) // len(sizes), max(sizes)))
    if dts:
        dts_sorted = sorted(dts)
        n = len(dts)
        print("Frame interval:   min=%.1f avg=%.1f max=%.1f ms" % (
            min(dts), sum(dts) / n, max(dts)))
        print("  p50=%.1f  p90=%.1f  p99=%.1f ms" % (
            dts_sorted[n // 2],
            dts_sorted[int(n * 0.9)],
            dts_sorted[min(int(n * 0.99), n - 1)]))
        slow = [d for d in dts if d > 200]
        print("Frames > 200ms:   %d (%.1f%%)" % (len(slow), 100 * len(slow) / n))
    if total_time > 0:
        print("Throughput:       %.1f KB/s" % (sum(sizes) / 1024 / total_time))
else:
    print("No frames received")
