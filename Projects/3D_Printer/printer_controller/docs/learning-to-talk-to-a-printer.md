# Learning to Talk to a 3D Printer

How an AI agent learned to communicate with a Geeetech A10 (Marlin 1.1.8) over USB serial — from first byte to smooth real-time teleoperation.

---

## 1. The Physical Setup

| Component | Detail |
|-----------|--------|
| Printer | Geeetech A10, Marlin 1.1.8 firmware |
| USB bridge | CH340 (QinHeng), VID `0x1A86` |
| Port | COM11 on Windows |
| Baud rate | 250000 |
| Build volume | 220 × 220 × 260 mm |
| Max feedrate | XY: 300 mm/s (F18000), Z: 5 mm/s (F300) |

The printer connects via a USB-to-serial bridge chip (CH340). When the host opens the serial port, the CH340 toggles DTR, which resets the ATmega2560. The board takes ~2 seconds to boot and emit a startup banner before it's ready for commands.

---

## 2. The Protocol: Marlin G-code over Serial

Marlin speaks a line-based text protocol. Every command is a single line ending in `\n`. Every command gets a response — either `ok` (success), `ok T:25.0 /0.0` (success with inline data), or `Error:` / `Resend:` (failure).

The fundamental rule I learned:

> **You must wait for `ok` before sending the next command.**

This is the ok-gate. Marlin has a small serial input buffer (~128 bytes on most boards). If you blast commands without waiting, the buffer overflows and commands get corrupted. The entire serial layer is built around this constraint.

### The Handshake

After opening the port and waiting for boot (~2s), the first exchange identifies the printer:

```
→ M115
← FIRMWARE_NAME:Marlin 1.1.8 (Github)
← ok
→ M105
← ok T:22.5 /0.0 B:21.3 /0.0
→ M114
← X:0.00 Y:0.00 Z:0.00 E:0.00 Count X:0 Y:0 Z:0
← ok
```

Three commands, three `ok` responses. Now we know: it's Marlin 1.1.8, the nozzle is at 22.5°C, and the head is at the origin.

### Key Commands

| Command | Purpose | Response |
|---------|---------|----------|
| `M115` | Identify firmware | `FIRMWARE_NAME:...` then `ok` |
| `M114` | Report position | `X:10.00 Y:20.00 Z:0.30 E:0.00` then `ok` |
| `M105` | Report temperatures | `ok T:22.5 /0.0 B:21.3 /0.0` |
| `G28` | Home all axes | `ok` (after physical homing, 10-15s) |
| `G28 X` | Home single axis | `ok` |
| `G90` | Absolute positioning mode | `ok` |
| `G91` | Relative positioning mode | `ok` |
| `G1 X50 Y50 F3000` | Linear move to (50, 50) at 50 mm/s | `ok` (immediately, when accepted into planner) |
| `M112` | Emergency stop | Halts firmware, no `ok` |

### The Position Paradox

A critical subtlety: **`ok` for G1 means "accepted into the motion planner", not "move complete."**

Marlin has a 16-slot motion planner buffer. When you send `G1 X100 F3000`, Marlin parses it, plans the trapezoid acceleration profile, adds it to the planner queue, and immediately sends `ok`. The head hasn't moved yet — it may not start moving for several more milliseconds.

This means:
- `M114` after a G1 may return the *commanded* position, not the *physical* position
- Multiple G1 commands pile up in the planner and execute sequentially
- You cannot determine "has the physical move finished" from serial alone

### The Coordinate System

After homing (`G28`), this Geeetech A10 reports position as `X:-15.00 Y:-8.00 Z:0.00`. This is because the homing endstops are offset from the origin — the nozzle physically homes into the corner, then Marlin applies the configured offset. The usable build volume runs from (0, 0, 0) to (220, 220, 250).

---

## 3. Architecture: Two Threads, Three Channels

The serial worker uses two background threads and three command channels:

```
                    ┌─────────────────────────────────┐
   send("M114") ──►│  Queue (FIFO)                   │
                    │  handshake, M114 polls,          │
                    │  user gcode, G90, G28            │
                    ├─────────────────────────────────┤
 send_latest(G1) ──►│  Latest Slot (single, overwrites)│──► send_loop ──► serial ──► printer
                    │  follower G1 commands             │      ▲
                    ├─────────────────────────────────┤      │
send_immediate() ──►│  Bypass (direct write)           │      │ ok
                    │  M112 emergency stop only         │      │
                    └─────────────────────────────────┘      ▼
                                                        read_loop ◄── serial ◄── printer
```

**Reader thread**: Continuously reads lines from serial. Parses `M114` position, `M105` temperature, firmware identification, errors, busy signals, and `ok` acknowledgements. Sets a threading Event on `ok`.

**Sender thread** (`send_loop`): Waits for commands from either channel, sends one, waits for `ok`, repeats. Priority order:
1. **Latest slot** (motion G1) — time-critical, always the freshest target
2. **Queue** (everything else) — FIFO order

This priority order was a hard-won lesson (see section 5).

---

## 4. Parsing Marlin's Responses

Marlin's responses are regex-parseable but have quirks:

```python
# Position: "X:10.00 Y:20.00 Z:0.30 E:0.00 Count X:800 Y:1600 Z:120"
_M114_PATTERN = re.compile(
    r"X:\s*(-?[\d.]+)\s+Y:\s*(-?[\d.]+)\s+Z:\s*(-?[\d.]+)\s+E:\s*(-?[\d.]+)"
)

# Temperature: "ok T:200.1 /200.0 B:60.2 /60.0"
_M105_PATTERN = re.compile(r"T:\s*(-?[\d.]+)\s*/\s*(-?[\d.]+)")

# Firmware: "FIRMWARE_NAME:Marlin 1.1.8 (Github) SOURCE_CODE_URL:..."
_FIRMWARE_PATTERN = re.compile(
    r"FIRMWARE_NAME:\s*(.+?)(?:\s+SOURCE_CODE_URL|\s+PROTOCOL_VERSION|$)"
)
```

Gotchas encountered:
- `ok` can carry inline temperature data: `ok T:22.5 /0.0 B:21.3 /0.0`
- `M114` sends the position line *then* `ok` on the next line (two lines for one command)
- `echo:busy` lines appear during long operations like homing — they are NOT errors, and they are NOT `ok`
- `Error: Printer halted. kill() called!` — this means M112 was received; the printer must be power-cycled

---

## 5. Lessons Learned the Hard Way

### Lesson 1: M114 in the Queue Blocks Motion

**Problem**: Position queries (`M114`) and motion commands (`G1`) were both going through the same FIFO queue. The send_loop processed queue items one at a time, waiting for `ok` between each. An M114 between two G1 commands would:
1. Send G1 → ok (instant, planner accepts it)
2. Send M114 → ok (must wait for printer to respond with position)
3. Send next G1 → ok

The M114 response took 10-50ms, during which no new motion commands could be sent.

**Solution**: Separate channels. Motion G1 goes through `send_latest()` (single-slot overwrite — only the newest target matters). M114 goes through `send()` (queue). The send_loop checks the latest slot *first*, so motion always has priority.

### Lesson 2: The Queue Pile-Up During Homing

**Problem**: `G28` (home all axes) takes 10-15 seconds. During that time, the periodic M114 poll loop was queuing one M114 every 500ms. When G28 finished, there were ~30 M114 commands stacked in the queue. Any user command sent after homing had to wait behind all 30 M114s (~300ms each = 9 seconds of delay).

**Solution**: Track a `_processing` flag that's True while the send_loop is waiting for `ok`. The M114 poll loop checks `queue_empty` (which includes `_processing`) and skips enqueuing M114 when any command is in flight.

### Lesson 3: `ok` Means "Accepted", Not "Done"

**Problem**: The follower loop compared the *last-sent position* against the *M114 reported position* to decide if the printer had arrived. But M114 returns the logical target position (what Marlin thinks it's heading toward), not the physical position. For moves that are still in the planner, M114 may show the end position before the stepper has arrived.

**Insight**: For real-time control, compare against what you *sent*, not what M114 reports. M114 is for UI display, not for closed-loop feedback.

### Lesson 4: send_latest() — The Key to Smooth Motion

**Problem**: During continuous control (holding a key), the frontend sends target positions at 100ms intervals (10 per second). If each target becomes a separate G1 in the queue, they pile up. The printer visits every intermediate point sequentially, causing jerky motion and growing latency.

**Solution**: `send_latest()` writes to a single-slot variable (protected by a lock). Every write *overwrites* the previous command. The send_loop picks it up on the next ok-cycle and sends only the most recent target. Old intermediate positions are silently discarded. The printer jumps directly toward wherever the user is pointing *now*.

### Lesson 5: Feedrate Matters for Following

**Problem**: The follower used the jog feedrate (F3000 = 50 mm/s). At 100ms ticks, targets can be up to 5mm apart. At 50 mm/s, a 5mm segment takes 100ms — just barely keeping up. But with acceleration and deceleration, the actual time is longer, causing the planner to accumulate segments and the printer to fall behind.

**Solution**: Use a high follower feedrate (F12000 = 200 mm/s). The printer reaches each intermediate target well within the 100ms tick. For Z-only moves, constrain to the safe Z feedrate (F300 = 5 mm/s) because the Z axis has a leadscrew with much lower max speed.

### Lesson 6: DTR Reset on Connect

When you open a serial port to a CH340-based board, the DTR line toggles, resetting the microcontroller. You must wait ~2 seconds for the bootloader to pass control to Marlin, then drain any startup banner bytes before sending commands. Without this wait, your first commands arrive during boot and get ignored or garbled.

### Lesson 7: Emergency Stop Is Fire-and-Forget

`M112` (emergency stop) must bypass the queue entirely. If the queue has 10 pending commands, you don't want to wait for them to process before the stop reaches the printer. `send_immediate()` writes directly to the serial port, no ok-gating, no queue. The printer halts immediately and enters an error state that requires a power cycle.

---

## 6. The Real-Time Control Architecture

The final architecture for smooth real-time control:

```
React (60fps)                    Python Backend                     Printer
─────────────                    ──────────────                     ───────
useFrame loop                    target_follower_loop (100ms)
  │                                │
  ├─ advance predicted pos         ├─ consume latest target
  │   (keyboard/mouse input)       ├─ deadband check (0.1mm)
  │                                ├─ safety validation
  ├─ send target via WebSocket ──► ├─ build G1 command
  │   every 100ms                  ├─ send_latest(G1) ──────────► serial ──► stepper motors
  │                                │
  ├─ receive state via WS ◄──── broadcast_loop (100ms)
  │                                │
  │                              position_poll_loop (500ms)
  ├─ update actual position        ├─ M114 via send() ──────────► serial
  │   (ghost actuator)             └─ parse response ◄──────────  serial
  │
  └─ render both positions
      at 60fps with lerp
```

Key design decisions:
- **Predicted position** lives in a React ref — no re-renders, just useFrame reading the ref at 60fps
- **Actual position** comes from M114 polls at 500ms — drives a semi-transparent "ghost" actuator
- **Reconciliation**: When the user stops moving and predicted is within 2mm of actual, gently converge predicted toward actual using exponential decay (`1 - e^(-3t)`)
- **Mouse control**: Sets predicted position directly on the XZ plane, marks `userActiveRef = true` to suppress reconciliation during drag

---

## 7. Safety Boundaries

Every absolute position is validated before sending:

```python
# Bed limits from config.yaml
x: [0.0, 220.0]
y: [0.0, 220.0]
z: [0.0, 250.0]
```

The React frontend clamps predicted positions to these limits. The Python backend validates again before generating G1. Raw G-code sent via the REST API is also parsed for axis values and rejected if out of bounds.

Emergency stop (`M112`) always goes through `send_immediate()` — no queue, no validation, no ok-gate.

---

## 8. What I Would Do Differently

1. **Use Marlin's `M400` (wait for moves to finish)** before `M114` to get accurate physical position instead of logical target position. This would make the ghost actuator much more accurate but at the cost of blocking the serial line.

2. **Implement line numbering and checksums** (`N123 G1 X50*cs`). Marlin supports this for reliable communication over noisy serial links. We skip it because the USB connection is reliable, but it would catch any rare corruption.

3. **Use the Marlin planner buffer report** (`M154` auto-report position, or `ADVANCED_OK` with planner buffer count) to know when the planner has space, instead of relying solely on ok-gating. This would allow sending commands slightly ahead without overflow.

4. **Explore `M154 S1` (auto-report position)** instead of polling with M114. Some Marlin builds support automatically sending position updates at a configurable interval, eliminating the poll loop entirely.

---

## 9. Command Reference Used

```gcode
; Identification & Status
M115                    ; Report firmware version
M114                    ; Report current position
M105                    ; Report temperatures

; Homing
G28                     ; Home all axes (10-15s, blocks until complete)
G28 X                   ; Home X axis only

; Positioning Mode
G90                     ; Absolute positioning (default)
G91                     ; Relative positioning

; Movement
G1 X50 Y50 Z10 F3000   ; Linear move, feedrate in mm/min
G1 X50 F12000           ; Single axis, high speed (200mm/s)

; Safety
M112                    ; Emergency stop (kills firmware, needs power cycle)

; Temperature (not used in motion control, but parsed)
M104 S200               ; Set hotend target
M140 S60                ; Set bed target
```

---

## 10. File Map

| File | Role |
|------|------|
| `backend/serial_worker.py` | Serial port management, ok-gating, send_loop, read_loop, mock printer |
| `backend/printer_state.py` | State model, Marlin response parsers (M114, M105, M115) |
| `backend/gcode.py` | G-code builder functions (never format G-code strings manually) |
| `backend/app.py` | FastAPI server, WebSocket, follower loop, position poll loop |
| `backend/safety.py` | Bed limit validation, jog safety, raw gcode checks |
| `backend/config.py` | Config loader (bed limits, baud rates, jog defaults) |
| `react_visualizer/src/useActuatorControl.ts` | 60fps predicted position, keyboard/mouse input |
| `react_visualizer/src/PrinterScene.tsx` | Three.js scene, actuator + ghost rendering |
| `react_visualizer/src/usePrinterState.ts` | WebSocket connection, state/target transport |
| `scripts/test_movements.py` | End-to-end movement test (home, axes, circle, safety) |
| `scripts/diagnose_quick.py` | Quick diagnostic (home + WebSocket follower circle) |
| `tests/` | 80 unit tests covering serial, state, safety, API, config |
