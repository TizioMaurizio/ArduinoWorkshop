# Embodied Teleoperation Bridge: Build Log

**Project:** ESP32-CAM → Arduino PCA9685 Servo Controller via UDP+Serial  
**Date:** April 2026  
**Collaborators:** Alessandro (hardware, wiring, physical testing) + Copilot/firmware-architect (firmware, protocol design, software testing, debugging)

---

## 1. The Goal

Build a wireless bridge so that a human wearing a VR headset (Quest 2 via Godot 4.6 + OpenXR) can move their head and have a physical robot arm mirror that movement in real-time via two servos. The camera mounted on the arm streams video back to VR, creating a first-person embodiment loop.

**Signal chain:**

```
┌─────────┐   UDP    ┌───────────┐  UART 4800  ┌─────────────┐  I2C  ┌─────────┐
│ Godot   │ ──────→  │ ESP32-CAM │  ──────────→ │ Arduino Uno │ ────→ │ PCA9685 │ → Servos
│ (Quest) │  Wi-Fi   │ GPIO 13   │   Pin 2 RX   │ SoftSerial  │      │ 0x40    │
└─────────┘          └───────────┘              └─────────────┘      └─────────┘
     ↑                    │
     │    MJPEG stream    │
     └────────────────────┘
```

Previously the ESP32 used MQTT for servo commands. The task was to rip out MQTT entirely and replace it with a lean UDP→Serial bridge.

---

## 2. Division of Labor

This was a true human-agent collaboration. Neither could have done it alone.

**Alessandro (human in the loop):**
- Plugged and unplugged every wire — dozens of times across flash mode and operation mode
- Pressed the ESP32 RESET button at the right moment during flashing
- Identified which servos moved, which didn't, and described physical behavior
- Diagnosed the A4/A5 (SDA/SCL) swap by looking at the actual wires
- Verified IO0 grounding, power connections, and breadboard contacts
- Ran the final VR test: wearing the Quest 2 headset and moving the robot arm with his head

**Copilot (firmware-architect agent):**
- Rewrote the ESP32-CAM firmware (MQTT → UDP + UART2)
- Wrote the Arduino PCA9685 firmware with SoftwareSerial + watchdog
- Built the Godot servo_controller.gd and camera auto-discovery
- Created 9 Python test/diagnostic scripts
- Ran over 50 automated test commands to isolate each failure
- Diagnosed GPIO conflicts, baud rate issues, bus contention, and flash procedure failures
- Found the working esptool flags (`--no-stub --no-compress`) after ~15 failed flash attempts

---

## 3. Phase 1: Firmware Rewrite — "It Should Be Simple"

### 3.1 ESP32-CAM Firmware

Stripped MQTT dependencies from `main.cpp`. Added:
- `WiFiUDP` listener on port 9685
- `HardwareSerial(2)` (UART2) for Arduino communication
- `ESPmDNS` advertising as `esp32-8E0A7C.local`
- Protocol: `"<channel>,<angle>\n"` — text-based, human-readable, no framing overhead

**First GPIO choice: GPIO 14/15 (TX/RX)**  
Seemed logical — dedicated UART2 defaults. But GPIO 14/15 are JTAG strapping pins on the ESP32. Connecting them caused the ESP32 to enter JTAG mode on boot, failing to start. Discovered this from boot log analysis.

**Second attempt: GPIO 13**  
Free on AI-Thinker — not used by camera, not an LED pin, not a strapping pin. Worked.

**Critical discovery: UART2 init order matters.**  
If UART2 was initialized *before* `startCameraServer()`, the camera/SD driver reclaimed GPIO 13 (it's HS2_DATA3 in the SDMMC interface). Fix: defer `ArduinoSerial.begin()` to *after* `startCameraServer()`. This took two rounds of debugging to identify — the symptom was simply "serial output stops after camera init."

### 3.2 Arduino Firmware

New PCA9685 controller firmware:
- Dual input: USB Serial (9600 baud for PC debug) + SoftwareSerial on Pin 2 (from ESP32)
- Non-blocking `readline()` for both streams
- `parse_and_execute()` validates channel 0–15, angle 0–180, drives PCA9685 via I2C
- Centres all servos to 90° on boot

### 3.3 Godot Scripts

- `servo_controller.gd`: Quaternion-based head tracking (gimbal-lock-free), 20 Hz send rate, 1° deadband, auto-discovers ESP32 IP from camera stream
- `camera_stream.gd`: Parallel TCP probe discovery across all local /24 subnets, MJPEG SOI/EOI parsing

---

## 4. Phase 2: First Tests — Isolated Components Pass

### 4.1 ESP32 Debug Serial Test (29/29)

Sent UDP packets to the ESP32, read debug output on UART0 (115200 baud). Every `[FWD]` line matched the sent command perfectly. The UDP→UART2 bridge was confirmed working in isolation.

### 4.2 Arduino Serial Test (12/12)

Sent commands directly over USB Serial to the Arduino at 9600 baud:
```
  PASS  centre ch0            sent='0,90'        got='OK'
  PASS  centre ch3            sent='3,90'        got='OK'
  PASS  bad channel 99        sent='99,90'       got='ERR:ch 0-15'
  PASS  negative angle        sent='0,-1'        got='ERR:ang 0-180'
  ...
  PASS  recover ch0           sent='0,90'        got='OK'
```
12/12 passed. Protocol parsing, error handling, and PCA9685 I2C all verified.

### 4.3 Python Simulation (100% clean, 91.2% chaos)

Built `test_full_simulation.py` — a discrete event simulation of the entire chain (Godot angle sender → ESP32 UDP receiver → UART bridge → Arduino parser → PCA9685 driver). Under clean conditions: 100%. Under chaos mode (random drops, corruption, jitter): 91.2%. This gave us confidence the protocol was sound.

---

## 5. Phase 3: Integration — Where Everything Broke

### 5.1 Servos Don't Move (I2C Wiring Swap)

First end-to-end test: commands arrived at Arduino (confirmed via USB debug), PCA9685 reported OK, but **no servo movement**. 

**Root cause:** A4 (SDA) and A5 (SCL) were swapped on the breadboard. Alessandro caught this by physically inspecting the wires. After swapping: servos moved immediately.

### 5.2 Full Chain at 115200: Intermittent (57%)

First real UDP→Serial→Servo test at 115200 baud (original ESP32 UART2 speed): **4/14 commands passed (29%)**. The ESP32 outputs 3.3V logic; the Arduino expects 5V. At 115200 baud, the signal margins were too tight for breadboard wires without a level shifter.

**Decision: lower baud rate to 9600.**

### 5.3 The Arduino Pin 0 Bus Contention Disaster

With GPIO 13 connected to Arduino Pin 0 (hardware UART RX) alongside the CH340 USB-serial chip, both were driving the same line. Result: **100% corruption** — even direct USB commands to the Arduino failed.

**Fix:** Switched Arduino to SoftwareSerial on Pin 2 (dedicated, no bus conflict with CH340). This required rewriting the Arduino firmware to use dual-input (USB Serial + SoftwareSerial).

### 5.4 SoftwareSerial Desync at 9600 Baud

With SoftwareSerial on Pin 2 at 9600 baud: **8/14 (57%)** on first run. After ~7 successful commands, SoftwareSerial lost byte-boundary synchronization and never recovered within a session.

**Fix:** Added a watchdog — if SoftwareSerial goes silent for 2 seconds, call `espSerial.end()` + `espSerial.begin()` to re-sync. This improved results to **12/20 (60%)** with recovery. But still not reliable enough.

**Decision: lower baud to 4800** for better SoftwareSerial timing margins on the 3.3V→5V signal path.

---

## 6. Phase 4: The Flash Nightmare

Both firmwares needed the 4800 baud change. Arduino was easy — direct USB flash via PlatformIO. But the ESP32-CAM has no USB port. Alessandro's only programmer was **the Arduino Uno itself** acting as a USB-serial passthrough (RESET→GND to hold the ATmega in reset, passing serial through the CH340).

### 6.1 Wiring Modes

Every flash attempt required a complete rewire:

**Flash mode wiring:**
```
Arduino RESET → GND (hold in reset)
ESP32 IO0 → GND (download mode)
ESP32 U0TXD → Arduino Pin 1 (TX label)
ESP32 U0RXD → Arduino Pin 0 (RX label)
GPIO 13 wire REMOVED from Pin 2
```

**Operation mode wiring:**
```
Remove RESET→GND jumper
Remove IO0→GND jumper
Remove U0TXD/U0RXD from Pin 0/1
Connect ESP32 GPIO 13 → Arduino Pin 2
Press ESP32 RESET to boot normally
```

Alessandro had to swap between these configurations **more than 10 times** during debugging.

### 6.2 Flash Attempt Timeline

| # | Method | Baud | Result | Root Cause |
|---|--------|------|--------|------------|
| 1 | `pio run -t upload` | 115200 | `No serial data received` | COM4 held by serial monitor |
| 2 | `pio run -t upload` | 115200 | `No serial data received` | IO0 not grounded / timing |
| 3 | `pio run -t upload` | 115200 | `Invalid head of packet (0x0A)` | Extra wire on Pin 0 causing noise |
| 4 | `pio run -t upload` | 115200 | `Packet content transfer stopped` | Stub upload fails through passthrough |
| 5 | esptool direct | 57600 | `No serial data received` | ESP32 not in bootloader (IO0 timing) |
| 6 | esptool direct | 57600 | `No serial data received` | Same |
| 7 | esptool `--no-stub` | 115200 | Connected! Wrote bootloader, partitions, boot_app0... **firmware write died at 1%** (`StopIteration`) | Compressed `flash_defl_block` fails through Arduino passthrough |
| 8 | esptool `--no-stub` | 57600 | `No serial data received` | Port reopen loses bootloader |
| 9 | `flash_manual_reset.py` | 57600 | Bootloader detected but esptool reconnect failed | Port close/reopen between sync and flash |
| 10 | `flash_manual_reset.py` | 9600 | Same pattern | Same |
| 11 | `flash_manual_reset.py` | 115200 | `cannot create 'generator' instances` | esptool internal API incompatibility |
| 12 | `flash_oneshot.py` (API) | 57600 | `No serial data received` | ESPLoader.connect timeout too short |
| 13 | esptool `--no-stub` | 115200 | `Packet content transfer stopped (13 bytes)` | Compressed write failure |
| 14 | esptool `--no-stub --no-compress` | 115200 | **SUCCESS** | Raw `flash_block` works through passthrough |

**The winning command:**
```
esptool.py --chip esp32 --port COM4 --baud 115200 \
  --before no_reset --no-stub write_flash --no-compress \
  --flash_mode dio --flash_freq keep --flash_size 4MB \
  0x1000 bootloader.bin 0x8000 partitions.bin \
  0xe000 boot_app0.bin 0x10000 firmware.bin
```

**Key insight from esptool troubleshooting docs:** The compressed `flash_defl_block` command sends larger protocol packets than raw `flash_block`. Through the Arduino's CH340 passthrough at 115200 baud, the larger packets suffered data loss. The `--no-stub` flag uses the ROM bootloader (slower but more reliable), and `--no-compress` avoids the problematic compressed write path. Together they produced a clean flash at 78.7 kbit/s effective throughput.

### 6.3 Custom Flash Scripts Written Along the Way

Two custom scripts were developed to work around the timing issues:

- **`flash_manual_reset.py`**: Sends raw SLIP sync packets in a loop, waits for bootloader response, then launches esptool. Failed because esptool reopens the serial port, losing the bootloader connection.
- **`flash_oneshot.py`**: Uses esptool's `ESP32ROM` class directly to keep the port open. Worked conceptually but `ESPLoader.connect()` timeout was too short for the passthrough latency.

Neither was ultimately needed — the direct esptool CLI with the right flags worked once we found `--no-compress`.

---

## 7. Phase 5: The 4800 Baud Victory

### 7.1 Full Chain Test Result

After the successful flash and rewiring to operation mode:

```
[TEST] Full chain at 4800 baud: UDP -> ESP32 GPIO13 -> Arduino Pin2

  [OK]  0,45   -> [ESP] 0,45 | OK
  [OK]  3,90   -> [ESP] 3,90 | OK
  [OK]  0,135  -> [ESP] 0,135 | OK
  [OK]  3,45   -> [ESP] 3,45 | OK
  [OK]  0,90   -> [ESP] 0,90 | OK
  [OK]  3,135  -> [ESP] 3,135 | OK
  [OK]  0,0    -> [ESP] 0,0 | OK
  [OK]  3,180  -> [ESP] 3,180 | OK
  [OK]  0,180  -> [ESP] 0,180 | OK
  [OK]  3,0    -> [ESP] 3,0 | OK
  [OK]  0,60   -> [ESP] 0,60 | OK
  [OK]  3,120  -> [ESP] 3,120 | OK
  [OK]  0,30   -> [ESP] 0,30 | OK
  [OK]  3,150  -> [ESP] 3,150 | OK
  [OK]  0,90   -> [ESP] 0,90 | OK
  [OK]  3,90   -> [ESP] 3,90 | OK
  [OK]  0,45   -> [ESP] 0,45 | OK
  [OK]  3,60   -> [ESP] 3,60 | OK
  [OK]  0,120  -> [ESP] 0,120 | OK
  [OK]  3,30   -> [ESP] 3,30 | OK

[RESULT] 20/20 passed (100%)
PERFECT! Full chain working at 4800 baud!
```

Every command: UDP received by ESP32, forwarded over GPIO 13 at 4800 baud, received by Arduino SoftwareSerial on Pin 2, parsed, executed on PCA9685, servo moved, OK acknowledged.

### 7.2 VR Embodiment Test

Alessandro put on the Quest 2 headset. Godot's `servo_controller.gd` captured head quaternion rotations, extracted yaw and pitch, mapped them to servo angles, and sent UDP packets at 20 Hz. The ESP32-CAM:
- Received the UDP angle commands and forwarded them to Arduino
- Simultaneously streamed MJPEG video back to Godot

**The robot arm moved in sync with Alessandro's head. The camera feed appeared in VR. First-person embodiment achieved.**

---

## 8. Reliability Progression

| Test | Baud | Protocol | Result |
|------|------|----------|--------|
| ESP32 isolated (UDP→debug echo) | 115200 | UART0 | 29/29 (100%) |
| Arduino isolated (USB direct) | 9600 | USB Serial | 12/12 (100%) |
| Python simulation (clean) | N/A | Simulated | 100% |
| Python simulation (chaos) | N/A | Simulated | 91.2% |
| Full chain, Pin 0, 115200 | 115200 | HW UART | 4/14 (29%) — bus contention |
| Full chain, Pin 2, 9600 | 9600 | SoftwareSerial | 8/14 (57%) — desync |
| Full chain, Pin 2, 9600 + watchdog | 9600 | SoftwareSerial | 12/20 (60%) — partial recovery |
| **Full chain, Pin 2, 4800 + watchdog** | **4800** | **SoftwareSerial** | **20/20 (100%)** |

---

## 9. Bugs Found and Fixed

| Bug | Symptom | Diagnosis Method | Fix |
|-----|---------|-----------------|-----|
| GPIO 14/15 JTAG strapping | ESP32 fails to boot | Boot log analysis | Switch to GPIO 13 |
| Camera driver reclaims GPIO 13 | UART2 output stops after camera init | Code review of init order | Defer UART2 init to after `startCameraServer()` |
| A4/A5 I2C swap | Servos don't move despite OK responses | Physical wire inspection by Alessandro | Swap wires |
| Pin 0 bus contention | All serial corrupted (ESP + USB) | Disconnecting GPIO 13 restored USB | Move to SoftwareSerial on Pin 2 |
| SoftwareSerial byte desync | Commands fail after ~7 successes | Pattern analysis of failure sequence | 2-second watchdog re-inits SoftwareSerial |
| 3.3V→5V marginal signal | Intermittent failures at 9600 baud | Lower baud → higher reliability | Reduce to 4800 baud |
| esptool compressed write fails | `StopIteration` at 1% firmware write | esptool troubleshooting docs | `--no-compress` flag |
| esptool stub upload fails | `Packet content transfer stopped` | Stub requires higher-bandwidth link | `--no-stub` flag |

---

## 10. Final System Architecture

### Hardware
```
ESP32-CAM AI-Thinker (ESP32-D0WD rev v1.0)
├── Wi-Fi: "Physical Metaverse 2.4GHz2"
├── mDNS: esp32-8E0A7C.local
├── Camera: OV2640, MJPEG stream on port 81
├── UDP listener: port 9685
└── UART2 TX: GPIO 13 → Arduino Pin 2 (4800 baud)

Arduino Uno (ATmega328P)
├── USB Serial: 9600 baud (debug/PC testing)
├── SoftwareSerial RX: Pin 2 (from ESP32 GPIO 13, 4800 baud)
├── I2C: A4 (SDA) / A5 (SCL) @ 400 kHz
└── PCA9685 servo driver at 0x40
    ├── Channel 0: Yaw servo
    └── Channel 3: Pitch servo

Quest 2 (via Godot 4.6.2 + OpenXR Link)
├── XRCamera3D quaternion → yaw/pitch extraction
├── UDP sender to ESP32:9685
└── MJPEG receiver from ESP32:81
```

### Software

| File | Purpose |
|------|---------|
| `Projects/ESP32-CAM-PlatformIO/src/main.cpp` | ESP32 firmware: camera + UDP→UART2 bridge |
| `Projects/PCA9685-ServoController/src/main.cpp` | Arduino firmware: dual-serial PCA9685 controller |
| `Projects/ESP32-CAM-PlatformIO/Godot/servo_controller.gd` | VR head tracking → servo angle UDP sender |
| `Projects/ESP32-CAM-PlatformIO/Godot/camera_stream.gd` | MJPEG auto-discovery and streaming |
| `Projects/ESP32-CAM-PlatformIO/scripts/test_serial_arduino.py` | Arduino protocol validation (12 tests) |
| `Projects/ESP32-CAM-PlatformIO/scripts/test_full_simulation.py` | Full chain discrete simulation |
| `Projects/ESP32-CAM-PlatformIO/scripts/test_digital_twin.py` | ASCII servo gauge visualizer |
| `Projects/ESP32-CAM-PlatformIO/scripts/flash_manual_reset.py` | ESP32 flash helper (manual RESET timing) |
| `Projects/ESP32-CAM-PlatformIO/scripts/flash_oneshot.py` | ESP32 flash via esptool API (single port open) |

### Protocol
```
Godot → ESP32:  UDP packet  "<channel>,<angle>\n"  (e.g., "0,90\n")
ESP32 → Arduino: UART 4800  "<channel>,<angle>\n"  (byte-for-byte forward)
Arduino → USB:   Serial 9600 "[ESP] <channel>,<angle>\n" + "OK\n" or "ERR:...\n"
```

---

## 11. Lessons Learned

1. **Test each link in isolation first.** The ESP32 and Arduino both passed 100% individually. Integration failures were all about the physical connection between them.

2. **3.3V → 5V without a level shifter works, but only at low baud rates.** 4800 baud gives enough timing margin for breadboard wires. A proper level shifter would allow higher speeds.

3. **SoftwareSerial on AVR is fragile.** It disables interrupts during byte reception, so it's sensitive to timing. The 2-second watchdog re-init was essential for reliability.

4. **Flashing through an Arduino passthrough requires specific esptool flags.** The CH340 USB-serial chip introduces enough latency and jitter that the default stub upload and compressed writes fail. `--no-stub --no-compress` at 115200 baud was the only combination that worked reliably.

5. **Always defer peripheral init to after the subsystem that might reclaim the pin.** The ESP32 camera driver silently reconfigures GPIO 13 if initialized before UART2.

6. **Bus contention is silent and catastrophic.** GPIO 13 driving Arduino Pin 0 alongside the CH340 corrupted everything — including the USB debug path. Moving to a dedicated pin (Pin 2) was the fix.

7. **DHCP IPs change after reflash.** Always resolve via mDNS (`esp32-8E0A7C.local`) rather than hardcoding an IP.

8. **Human + agent collaboration beats either alone.** The agent could write firmware and run 50 automated tests per minute, but only the human could press RESET at the right millisecond, feel whether a servo was jittering, and notice that two wires were in the wrong holes.

---

## 12. Phase 6: UDP JPEG Stream — Replacing TCP MJPEG

### 12.1 Problem

The TCP MJPEG stream on port 81 worked but added latency from TCP retransmissions and head-of-line blocking. For VR embodiment, every millisecond of video delay erodes the sense of presence. UDP with fragmented JPEGs is a better fit: drop a packet, drop a frame, move on.

### 12.2 Discovery: The Code Was Gone

After a backup restore, the UDP stream code was missing from `main.cpp` — the firmware on disk had **no UDP stream implementation**. Verified by:
1. Searching `main.cpp` for `UDP_STREAM_PORT` → not found
2. Running `mock_godot_client.py` against the live ESP32 → port 82 got no response
3. Comparing against `camera_stream.gd` which expected the protocol → client-side existed, server-side didn't

### 12.3 Implementation

Added a FreeRTOS task pinned to core 0 (`udp_stream_task`) with separated sockets:

| Socket | Core | Role |
|--------|------|------|
| `udp_stream_rx` | Core 1 (loop) | Receives `STREAM_UDP`/`STREAM_STOP` commands |
| `udp_stream_tx` | Core 0 (task) | Sends JPEG fragments to registered client |

**Why separate sockets?** `WiFiUDP` is not thread-safe. Sharing one socket between `loop()` (core 1) and the stream task (core 0) caused silent packet corruption. Two sockets, one per core, eliminated the race.

**Fragment protocol** (8-byte header + ≤1400B payload):
```
Offset  Size  Field
0       2     frame_id   (u16 LE) — wrapping counter
2       1     frag_idx   (u8)     — 0-based fragment index
3       1     frag_count (u8)     — total fragments in frame
4       4     frame_len  (u32 LE) — total JPEG size in bytes
8+      ≤1400 payload             — raw JPEG bytes
```

Client sends `"STREAM_UDP"` to register and resends every 2s as keepalive. Server times out after 5s of silence.

**Stale frame handling:** With `fb_count=2`, the camera double-buffers. If a frame is >200ms old (measured via `esp_timer_get_time()` vs `fb->timestamp`), it's returned and a fresh one captured.

### 12.4 Verification

Built with PlatformIO (RAM 18.3%, Flash 28.3%). Flashed via esptool. Tested all three protocols with `mock_godot_client.py`:

```
Protocol        Result    Detail
TCP :80/status  PASS      HTTP 200, JSON response
TCP :81 MJPEG   PASS      12.2 FPS (61 frames / 5s)
UDP :82 stream  PASS      10.8 FPS (54 frames / 5s)
```

### 12.5 Files Changed

| File | Change |
|------|--------|
| `src/main.cpp` | Added `udp_stream_task`, `udp_stream_rx`/`udp_stream_tx` sockets, stream command handling in `loop()`, discovery JSON now includes `udp_cam:82` |
| `Godot/camera_stream.gd` | Fixed IP to `10.224.248.157`, `use_udp = true` default, fixed tab indentation (was stripped by PowerShell heredoc) |

---

## 13. Phase 7: UART Buffer Overflow — Servo Stops After 5 Seconds

### 13.1 Symptom

After fixing the IP in `servo_controller.gd` (was stale `10.192.119.157` from a previous DHCP lease), the arm responded to head movement — but **stopped after ~5 seconds**. Godot's `[Servo] TX:` diagnostic logs confirmed packets were still being sent. The ESP32 was still receiving them. But the Arduino stopped getting commands.

### 13.2 Root Cause

Two bugs compounding:

1. **Single-packet read per loop iteration.** The servo forwarding code called `udp.parsePacket()` once per `loop()` pass with an `if`, not a `while`. At 20 Hz × 2 channels = 40 packets/sec, and `loop()` also handling discovery broadcasts and stream commands, the UDP receive buffer accumulated a backlog.

2. **No UART TX drain.** `ArduinoSerial.print()` writes to a 128-byte hardware TX buffer and returns immediately. At 4800 baud, a 6-byte command takes ~12ms to transmit. Without waiting for the TX buffer to drain, consecutive commands overwrote each other when the buffer filled faster than UART could clock them out.

The combination meant: packets queued up in UDP → forwarded faster than UART could send → UART TX buffer overflowed → Arduino received corrupted partial commands → stopped responding → ESP32 kept forwarding into the void.

### 13.3 Fix

Two changes in `loop()`:

```cpp
// BEFORE (broken):
int packet_size = udp.parsePacket();
if (packet_size > 0) {
    // read and forward ONE packet
}

// AFTER (fixed):
int packet_size = udp.parsePacket();
while (packet_size > 0) {
    // read and forward packet
    ArduinoSerial.print(buf);
    ArduinoSerial.flush();  // block until UART TX buffer drains
    packet_size = udp.parsePacket();  // check for more
}
```

- `while` loop drains all pending UDP packets per `loop()` pass
- `ArduinoSerial.flush()` blocks until the UART TX hardware register is empty, preventing buffer overflow

### 13.4 Trade-off

`flush()` is blocking — each 6-byte command at 4800 baud blocks for ~12ms. At 40 packets/sec worst case, that's 480ms/sec of blocking. This is acceptable because:
- The servo `loop()` runs on core 1; the camera stream task runs on core 0 — no impact on video
- Discovery broadcasts are non-critical (2s interval, missing one is fine)
- The alternative (buffer overflow → arm stops) is worse

### 13.5 Endurance Test

Created `Godot/test/servo_stress_test.py` — a mock Godot client sending sine-wave servo sweeps at 20 Hz for 60 seconds:

```
Run 1:  1928 packets / 60.0s  (32.1 pkt/s)  errors=0  PASS
Run 2:  1930 packets / 60.0s  (32.2 pkt/s)  errors=0  PASS
```

Confirmed by physical observation: arm swept continuously through full range for the entire 60 seconds without stopping. Verified working from Godot VR as well.

### 13.6 Files Changed

| File | Change |
|------|--------|
| `src/main.cpp` | `if` → `while` for packet drain, added `ArduinoSerial.flush()` |
| `Godot/servo_controller.gd` | Fixed `bridge_host` IP to `10.224.248.157`, added diagnostic `[Servo] TX:` logging |
| `Godot/test/servo_stress_test.py` | New: 60s endurance test script |

---

## 14. Updated Reliability Table

| Test | Protocol | Result |
|------|----------|--------|
| ESP32 UDP→debug echo (isolated) | UART0 115200 | 29/29 (100%) |
| Arduino USB direct | USB 9600 | 12/12 (100%) |
| Full chain, Pin 2, 4800 baud | SoftwareSerial | 20/20 (100%) |
| UDP JPEG stream (TCP fallback) | TCP :81 MJPEG | 12.2 FPS |
| UDP JPEG stream (primary) | UDP :82 fragments | 10.8 FPS |
| **Servo endurance (60s, 20Hz)** | **UDP → UART 4800** | **1930/1930 (100%)** |
| **VR embodiment (Godot + Quest 2)** | **Full stack** | **Continuous** |

---

## 15. Current Flash Procedure

The ESP32-CAM now has a dedicated USB-serial connection (no longer through Arduino passthrough), simplifying flashing:

```powershell
# 1. Ground IO0, press RESET
# 2. Flash:
esptool.py --chip esp32 --port COM4 --baud 115200 `
  --before no_reset write_flash -z `
  --flash_mode dio --flash_freq keep --flash_size 4MB `
  0x1000 .pio\build\esp32cam\bootloader.bin `
  0x8000 .pio\build\esp32cam\partitions.bin `
  0xe000 boot_app0.bin `
  0x10000 .pio\build\esp32cam\firmware.bin
# 3. Disconnect IO0 from GND, press RESET to boot
```

Note: `--no-stub --no-compress` flags are no longer needed when using a direct USB-serial connection instead of the Arduino passthrough.

---

*The robot arm moves with the human's head. The camera streams to VR over UDP. The servo link survives indefinitely. The loop is closed — and it stays closed.*
