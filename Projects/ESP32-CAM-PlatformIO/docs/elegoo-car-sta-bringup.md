# ELEGOO Smart Robot Car V4.0 — STA Mode Bringup Log

**Date:** 2026-04-18  
**Goal:** Replace the car's default WiFi AP mode with STA mode so it joins an existing network, enabling a Godot VR application to control the car over TCP from a PC on the same LAN.

---

## 1. Starting Point

The ELEGOO Smart Robot Car V4.0 has a two-MCU architecture:

- **ESP32 module** (on top): runs WiFi, camera, and TCP server. Ships as a WiFi Access Point ("ELEGOO-XXXX"), accepts one TCP client on port 100, and bridges JSON commands over UART to the Arduino.
- **Arduino UNO** (on bottom): reads JSON commands from Serial at 9600 baud, drives motors (DRV8835), reads sensors (ultrasonic, IR line-follow), and sends responses back over the same Serial.

The stock flow: **ELEGOO phone app → WiFi AP → TCP:100 → ESP32 → UART@9600 → Arduino UNO → motors.**

We needed to change the ESP32 from AP mode to STA mode so the car joins our lab network ("Physical Metaverse 2.4GHz2"), making it reachable from the same PC running Godot VR.

---

## 2. Writing the STA Firmware

Created `src/elegoo_car_main.cpp` — a clean rewrite of the ESP32 firmware:

- **WiFi STA** with auto-reconnect, connecting to SSID "Physical Metaverse 2.4GHz2" / password "earthbound".
- **TCP server on port 100** — same JSON wire protocol as the stock ELEGOO app, so the Arduino UNO's firmware doesn't need any changes.
- **mDNS** advertising `elegoo-car.local`.
- **UDP discovery broadcast** on port 9999 every 2 seconds — JSON payload with IP, port, and camera port, so Godot can auto-discover the car without hardcoding an IP.
- **Serial2 bridge** to the Arduino UNO at 9600 baud — bidirectional pass-through of JSON commands and responses.
- **Heartbeat** — `{Heartbeat}` exchanged every 1 second, same as original. Three missed heartbeats → disconnect and emergency stop.
- **Emergency stop** — sends `{"N":100}` to Arduino whenever the TCP client disconnects.

Added a PlatformIO environment `[env:elegoo_car]` in `platformio.ini`.

---

## 3. Discovery: the Chip is ESP32-S3, Not ESP32-WROVER

First flash attempt revealed `esptool` couldn't detect the chip. The error indicated the car's newer hardware revision (V2) replaced the original ESP32-WROVER with an **ESP32-S3-WROOM-1** (no PSRAM).

**Fix:** Changed the board target in `platformio.ini` from `esp32cam` to `esp32-s3-devkitc-1`.

---

## 4. Camera Crash — Guru Meditation Error

After fixing the board target, the firmware booted but immediately crashed in a loop:

```
Guru Meditation Error: Core 1 panic'ed (LoadProhibited)
```

The crash occurred inside `esp_camera_init()` because the code used M5STACK_WIDE camera pin definitions (from the original WROVER firmware), which reference GPIOs that don't exist on the S3-WROOM-1.

**Fix:** Disabled camera entirely — commented out `#include "esp_camera.h"`, `init_camera()`, `startCameraServer()`, and excluded `app_httpd.cpp` from the build via `build_src_filter`. Motor control doesn't need the camera.

---

## 5. USB CDC Serial Issues

The ESP32-S3-WROOM-1 uses **native USB CDC** (GPIO 19/20) instead of a traditional UART-to-USB bridge. This caused several problems:

1. **No serial output after flash.** The `Serial` object writes to USB CDC, which requires specific build flags.  
   **Fix:** Added `-DARDUINO_USB_CDC_ON_BOOT=1` and `-DARDUINO_USB_MODE=1` to `build_flags`.

2. **COM9 disappears on reset.** Unlike a CH340-based board, USB CDC disconnects from Windows whenever the S3 resets, then re-enumerates as a new USB device. PlatformIO's serial monitor can't reconnect.  
   **Fix:** Not truly fixable — it's inherent to USB CDC. Workaround: after flashing, press RESET and quickly reopen the monitor.

3. **Blank serial monitor for the first few seconds.** USB CDC enumeration takes time after boot; early `Serial.print()` calls are lost.  
   **Fix:** Added a startup wait loop:
   ```cpp
   while (!Serial && millis() - usb_wait < 3000) delay(10);
   ```

---

## 6. WiFi and TCP Working

After resolving the crash and serial issues, the firmware booted cleanly:

```
[WiFi] Connected — IP: 10.192.119.9  RSSI: -40 dBm
[mDNS] elegoo-car.local
[TCP]  Listening on port 100
```

Created `scripts/test_car_protocol.py` — a Python TCP client that tests the full protocol:
1. TCP connection
2. Heartbeat exchange
3. Forward/backward/left/right at speed 30 with stop between each
4. Final stop
5. Rapid 10 Hz burst (simulating joystick input)

**Result: 8/8 tests passed.** TCP pipeline was solid.

---

## 7. Wheels Don't Move — Wrong UART Pins

Despite 8/8 TCP tests passing, the car's wheels never moved. The TCP connection was fine, but Serial2 wasn't reaching the Arduino UNO.

**Root cause:** The original WROVER firmware used `Serial2.begin(9600, SERIAL_8N1, 33, 4)` — GPIO 33 for RX, GPIO 4 for TX. But on the ESP32-S3-WROOM-1, **GPIO 26–32 are not exposed** (they're used internally for flash/PSRAM). GPIO 33 literally doesn't exist as an external pin.

Tried GPIO 43/44 (S3 default UART0 pins) as a guess — still no response from the Arduino.

---

## 8. Building a WiFi-Based UART Pin Scanner

The problem: we didn't know which GPIO pins on the S3-WROOM-1 V2 PCB are physically routed to the Arduino UNO's UART. ELEGOO doesn't publish the V2 schematic.

**Approach:** Brute-force scan all 33 candidate GPIO pins (every safe S3 GPIO except 0, 19, 20, and 26–32) by trying every possible TX/RX pair, sending a known command, and checking for a response.

**Why WiFi-based:** An earlier serial-based scanner (`uart_scan.cpp`) was unreliable because USB CDC timing made the serial monitor miss output. Instead, we built `wifi_uart_scan.cpp` — a firmware that:

1. Boots and connects to WiFi.
2. Starts a TCP server on port 100.
3. Waits for a client to connect.
4. On connection, iterates through all 1,056 GPIO pairs (33 × 32):
   - Opens `Serial1` at 9600 baud with the candidate TX/RX pins.
   - Sends `{Factory}` (a command the Arduino UNO's stock firmware responds to).
   - Waits 200 ms for a response.
   - If any printable characters are received, reports a `*** HIT ***` line over TCP.
   - Closes `Serial1` and moves to the next pair.
5. Reports total hits and closes.

A companion Python script (`scripts/read_scan.py`) connects to the scanner's TCP server and prints results in real time.

**Flash procedure for ESP32-S3 native USB:**
1. Unplug USB from the car.
2. Hold the BOOT button on the ESP32-S3 module.
3. Plug USB back in (while holding BOOT).
4. Release BOOT. COM9 appears in download mode.
5. Run `pio run -e wifi_uart_scan -t upload --upload-port COM9`.
6. Press RESET after flash completes.

---

## 9. Scan Result — GPIO 40 TX, GPIO 3 RX

The scan took approximately 3.5 minutes and produced exactly one hit:

```
=== UART Pin Scanner ===
Scanning 33 candidate pins at 9600 baud

[progress] TX GPIO 5 (5/33)
[progress] TX GPIO 10 (10/33)
[progress] TX GPIO 15 (15/33)
[progress] TX GPIO 35 (20/33)
*** HIT *** TX=GPIO40 RX=GPIO3 Response: error:deserializeJson
[progress] TX GPIO 40 (25/33)
[progress] TX GPIO 45 (30/33)

=== Scan complete: 1 hits ===
```

The Arduino UNO responded with `error:deserializeJson` — it received our `{Factory}` string, attempted to parse it as JSON (its normal command format), and returned a parse error. This confirms **bidirectional UART communication** on those pins.

| Direction | ESP32-S3 GPIO | Arduino UNO Pin |
|-----------|---------------|-----------------|
| ESP32 → Arduino (TX) | **GPIO 40** | Pin 0 (RX) |
| Arduino → ESP32 (RX) | **GPIO 3** | Pin 1 (TX) |

For reference, the original WROVER mapping was GPIO 4 (TX) / GPIO 33 (RX).

---

## 10. Final Flash and Verification

Updated `elegoo_car_main.cpp`:

```cpp
#define RXD2 3   // GPIO 3 — Arduino UNO TX → ESP32-S3 RX
#define TXD2 40  // GPIO 40 — ESP32-S3 TX → Arduino UNO RX
```

Built and flashed the `elegoo_car` environment:

```
pio run -e elegoo_car -t upload --upload-port COM9
```

After pressing RESET, the firmware booted, connected to WiFi at 10.192.119.9, and started the TCP server.

Ran the protocol test:

```
python scripts/test_car_protocol.py --ip 10.192.119.9
```

```
[OK] TCP connect — 10.192.119.9:100
[OK] Heartbeat — sent {Heartbeat}
[OK] Move forward — {"N":3,"D1":3,"D2":30,"H":"1"}
[OK] Move backward — {"N":3,"D1":4,"D2":30,"H":"3"}
[OK] Move left — {"N":3,"D1":1,"D2":30,"H":"5"}
[OK] Move right — {"N":3,"D1":2,"D2":30,"H":"7"}
[OK] Final stop — {"N":100,"H":"9"}
[OK] Rapid 10Hz burst — 10 commands, counter=20

[RESULT] 8/8 passed
```

**The wheels moved.** Forward, backward, left, right — all confirmed visually.

---

## 11. Final Architecture

```
Godot VR (PC)
    │
    ├─ UDP:9999 ← discovery broadcast from ESP32-S3
    │
    └─ TCP:100 → ESP32-S3-WROOM-1 V2 (WiFi STA, 10.192.119.9)
                    │
                    ├─ mDNS: elegoo-car.local
                    │
                    └─ UART 9600 baud (GPIO 40 TX / GPIO 3 RX)
                          │
                          └─ Arduino UNO (stock ELEGOO firmware)
                                │
                                ├─ DRV8835 motor driver → 4 wheels
                                ├─ Ultrasonic sensor
                                ├─ IR line-following sensors
                                └─ Servo (camera pan)
```

---

## 12. Key Files

| File | Purpose |
|------|---------|
| `src/elegoo_car_main.cpp` | Main car firmware — WiFi STA, TCP bridge, mDNS, UDP discovery |
| `src/wifi_uart_scan.cpp` | Temporary — WiFi-based GPIO pair scanner (found TX=40, RX=3) |
| `src/uart_scan.cpp` | Temporary — serial-based scanner (superseded by WiFi version) |
| `platformio.ini` | Build environments: esp32cam, elegoo_car, uart_scan, wifi_uart_scan |
| `scripts/test_car_protocol.py` | TCP protocol test — 8 tests, all movement commands |
| `scripts/read_scan.py` | TCP client for reading WiFi scanner results |

---

## 13. Lessons Learned

1. **Never assume the chip.** The ELEGOO V4.0 has at least two hardware revisions. The V2 uses ESP32-S3-WROOM-1 (not ESP32-WROVER). There is no visual marking on the box — you find out when esptool reports `Chip is ESP32-S3`.

2. **ESP32-S3 USB CDC is fragile.** COM port disappears on every reset. Serial monitor loses connection. Early boot output is lost. You need the `while (!Serial)` wait and the USB CDC build flags.

3. **GPIO maps change between chip variants.** The WROVER's GPIO 33/4 UART pins don't exist on the S3-WROOM-1. Never assume pin assignments carry over between ESP32 variants.

4. **Brute-force pin scanning works.** When the schematic is unavailable, scanning all candidate GPIO pairs with a known command/response protocol reliably finds the correct UART pins. The WiFi-based approach (reporting results over TCP instead of serial) avoids USB CDC timing issues.

5. **Camera can be disabled safely.** The motor control TCP bridge works independently of the camera. Disabling camera avoids crashes from wrong pin mappings and saves flash/RAM.

6. **The Arduino UNO firmware doesn't need changes.** The stock ELEGOO firmware on the UNO parses JSON from Serial at 9600 baud regardless of what's on the other end. Replacing only the ESP32 firmware is sufficient to change the networking model.

---

## 14. Arm Servo Not Moving — Godot Troubleshooting (2026-04-19)

### Symptom

Camera video streamed successfully from the ESP32-CAM arm to Godot VR, but head-tracking servo commands had no effect — the robot arm did not move.

### Investigation

**Layer 1 — Network reachability:**
The phone hotspot (Physical Metaverse 2.4GHz2) had changed its DHCP subnet from `10.192.119.x` to `10.224.248.x` between sessions. A full-subnet TCP scan on the new range found:
- **Car** at `10.224.248.9` (port 100 open — TCP bridge) ✅
- **Arm** at `10.224.248.157` (ports 80/81 open — HTTP + MJPEG stream) ✅

Both devices had reconnected to WiFi after a power cycle, but at new DHCP addresses on the new subnet.

**Layer 2 — Firmware UDP→UART pipeline:**
Sent servo commands directly from Python to the arm ESP32-CAM:

```
python -c "import socket,time; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); \
  [s.sendto(f'{ch},{a}\n'.encode(),('10.224.248.157',9685)) or time.sleep(2) \
   for ch,a in [(0,0),(0,180),(0,90),(3,45),(3,135),(3,90)]]"
```

Servos on channels 0 (yaw) and 3 (pitch) moved correctly. The full pipeline — PC → UDP → ESP32-CAM (port 9685) → UART GPIO 13 @ 4800 baud → Arduino UNO SoftwareSerial → PCA9685 → servos — was confirmed working.

**Layer 3 — Godot client code:**
Inspected `Godot/servo_controller.gd` line 14:

```gdscript
@export var bridge_host: String = "10.192.119.157"  # ← STALE IP
```

Because `bridge_host` was non-empty, the script skips UDP auto-discovery entirely (line 80: `if bridge_host != "": _connect_udp(); return`) and sends all servo commands to the old subnet address. UDP is connectionless — `connect_to_host()` succeeds silently even when the destination is unreachable. No error is raised; packets are simply lost.

Similarly, `Godot/camera_stream.gd` line 6 had the same stale IP, but its auto-discovery fallback happened to find the arm on the new subnet, which is why video worked while servos didn't.

### Root Cause

Hardcoded IP addresses in two Godot scripts pointed at the previous DHCP subnet. The camera script's discovery fallback masked the problem for video, but the servo script had no such fallback when `bridge_host` is set.

### Fix

Updated both scripts to the current arm IP:

| File | Field | Old | New |
|------|-------|-----|-----|
| `Godot/servo_controller.gd:14` | `bridge_host` | `10.192.119.157` | `10.224.248.157` |
| `Godot/camera_stream.gd:6` | `esp_ip` | `10.192.119.157` | `10.224.248.157` |

### Verification

After restarting Godot with the corrected IPs, head-tracking servo commands reached the arm and servos moved in real time.

### Lesson

7. **UDP is silently lossy.** Unlike TCP, a UDP `connect_to_host()` does not verify reachability. Packets sent to a stale IP vanish without error. Always verify the destination is alive (e.g., with a discovery handshake or periodic health check) before assuming UDP delivery.

8. **Hardcoded IPs break on DHCP subnet changes.** Phone hotspots frequently reassign subnets. Prefer auto-discovery (UDP broadcast listener on port 9999) over static IPs. If a static IP must be used, document that it will need updating when the network changes.

9. **Isolate layers when diagnosing.** Testing the firmware pipeline with Python (bypassing Godot) immediately proved the servos worked. This narrowed the fault to the Godot client in one step, avoiding a lengthy firmware debugging detour.
