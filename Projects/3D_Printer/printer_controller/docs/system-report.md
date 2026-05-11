# 3D Printer Controller — System Report

**Date**: 2026-05-12
**Printer**: Geeetech A10, Marlin 1.1.8, CH340 USB (COM11 @ 250000 baud)
**Build volume**: 220 × 220 × 260 mm

---

## 1. What Was Built

A real-time 3D printer teleoperation system with three layers:

1. **Python backend** — serial protocol engine, ok-gated command queue, REST + WebSocket API, safety validation, follower loop
2. **React frontend** — Three.js 3D digital shadow with keyboard, mouse, and WebSocket-driven control at 60 fps
3. **Godot visualizer** — read-only 3D state viewer (legacy, replaced by React for interactive use)

The system lets a user move the printer tool head in real time through a browser, terminal WASD keys, REST API calls, or Godot client — with the backend enforcing safety on every command.

### 1.1 Development History (Commits)

| Commit | Description |
|--------|-------------|
| `10ce9d7` | Initial USB G-code controller with React 3D digital shadow |
| `78c483d` | `send_latest` slot, priority swap, `queue_empty` flag |
| `f62a0a6` | WebSocket follower loop with position polling |
| `9d69711` | Real-time actuator control with keyboard and mouse |
| `ce3bc6b` | Diagnostic and movement test scripts |
| `2e0ec33` | Serial communication learnings doc and config updates |
| `c7d7a16` | Ignore benign SD-card errors from Marlin |
| `c9c9116` | Launch instructions, controls reference, and `start.bat` |
| `6be62ef` | Architecture tree update (scripts/, docs/) |

### 1.2 Codebase Size

| Component | Files | Lines (approx) |
|-----------|-------|-----------------|
| Python backend | 9 modules | ~2,500 |
| React frontend | 7 components/hooks | ~850 |
| Tests (pytest) | 5 files, 80 tests | ~600 |
| Scripts (diagnostic/E2E) | 5 files | ~800 |
| Documentation | 2 files | ~500 |
| **Total** | **~28 files** | **~5,250** |

---

## 2. Architecture

```
Browser (React)                    Terminal (WASD)
    │ WebSocket (/ws/state)            │ stdin
    │  ↕ target + state                │
    ▼                                  ▼
┌─────────────────────────────────────────┐
│              FastAPI (app.py)            │
│  ┌──────────┐ ┌──────────┐ ┌─────────┐ │
│  │ Follower │ │ Broadcast│ │ M114    │ │
│  │ Loop     │ │ Loop     │ │ Poll    │ │
│  │ (100ms)  │ │ (100ms)  │ │ (500ms) │ │
│  └────┬─────┘ └──────────┘ └────┬────┘ │
│       │                         │       │
│  ┌────▼─────────────────────────▼────┐  │
│  │        SafetyValidator            │  │
│  │  (bounds, denylist, rate limit)   │  │
│  └──────────────┬────────────────────┘  │
│                 │                       │
│  ┌──────────────▼────────────────────┐  │
│  │        SerialWorker               │  │
│  │  ┌─────────┐ ┌───────┐ ┌──────┐  │  │
│  │  │ Queue   │ │Latest │ │Immed │  │  │
│  │  │ (FIFO)  │ │(slot) │ │(M112)│  │  │
│  │  └────┬────┘ └───┬───┘ └──┬───┘  │  │
│  │       └─────┬─────┘       │      │  │
│  │         send_loop ◄── ok-gate    │  │
│  │         read_loop ──► parsers    │  │
│  └──────────────┬────────────────────┘  │
└─────────────────┼───────────────────────┘
                  │ USB serial
                  ▼
            ┌───────────┐
            │  Marlin    │
            │  Firmware  │
            └───────────┘
```

### 2.1 Three-Channel Command Dispatch

| Channel | Purpose | Used by |
|---------|---------|---------|
| **Queue** (FIFO) | Sequential commands | M114, M105, G28, raw G-code |
| **Latest** (single-slot overwrite) | Time-critical motion | Follower loop G1 commands |
| **Immediate** (bypass) | Emergency stop | M112 only |

The send loop checks the latest slot first, then the queue. This prevents informational queries from blocking motion updates.

### 2.2 Ok-Gate Protocol

Every command waits for Marlin's `ok` response before the next one sends. This respects Marlin's ~128-byte serial buffer and prevents command overflow. The gate uses a `threading.Event` that the read loop sets when `ok` arrives.

### 2.3 Follower Loop

The React frontend sends target positions via WebSocket at 100 ms intervals. The backend's follower loop:

1. Reads the latest target (consumes dirty flag)
2. Compares against the last-*sent* position (not M114 — avoids stale feedback)
3. If delta > 0.1 mm (deadband), validates against bed limits
4. Sends G1 via `send_latest()` at F12000 (200 mm/s XY) or F300 (5 mm/s Z-only)

### 2.4 Predicted vs. Actual Visualization

| Layer | Source | Rendering | Latency |
|-------|--------|-----------|---------|
| **Predicted** (solid actuator) | Local keyboard/mouse input | Updated at 60 fps via refs | ~0 ms |
| **Actual** (ghost actuator) | M114 via WebSocket | Trails behind with exponential decay | 100–500 ms |

When the user releases keys, predicted gently converges toward actual. If divergence exceeds 50 mm (e.g., homing), predicted snaps rapidly.

---

## 3. Key Problems Solved

### 3.1 M114 Pile-Up During Homing

**Problem**: `_position_poll_loop` sent M114 every 500 ms regardless. During G28 homing (~12 s), ~24 M114 queries piled up in the queue. After homing, the printer wasted ~10 s processing stale M114s before accepting new commands.

**Fix**: Added `_processing` flag and `queue_empty` property. The poll loop only sends M114 when `queue_empty` is True (no command waiting for `ok`).

**Evidence**: X move after homing dropped from 10.2 s to 1.3 s.

### 3.2 Priority Inversion in Send Loop

**Problem**: The send loop checked the FIFO queue before the latest slot. If M114 queries were queued, a time-critical G1 from the follower loop would wait behind them.

**Fix**: Reversed priority — send loop checks latest slot first, then queue.

### 3.3 Visual Jumpiness in React

**Problem**: Position updates triggered React re-renders, causing the actuator to jump between frames.

**Fix**: Moved all position state to `useRef` (no re-renders). The `useFrame` callback at 60 fps reads refs directly and applies exponential lerp for smooth motion.

### 3.4 Follower Loop Feedrate

**Problem**: Initial F3000 (50 mm/s) caused planner buffer accumulation — targets arrived faster than the printer could execute them, creating growing positional lag.

**Fix**: Changed to F12000 (200 mm/s). At 100 ms ticks, max segment is ~20 mm, well within printer capability and planner buffer.

### 3.5 Benign SD-Card Error Locking

**Problem**: Marlin sends `Error:volume.init failed` at boot when no SD card is present. The error parser treated all `Error:` lines as critical and locked the controller.

**Fix**: Added `_IGNORABLE_ERRORS` tuple matching known-harmless SD-card messages. Matching errors are logged as info and acknowledged without locking.

### 3.6 Queue Wake Delay

**Problem**: After `send()` enqueued a command, the send loop might sleep up to 100 ms before checking the queue (it was waiting on the latest-slot event with a timeout).

**Fix**: `send()` now calls `self._latest_event.set()` to wake the send loop immediately.

---

## 4. Safety Layer

### 4.1 Validation Gates

Every movement passes through `SafetyValidator`:

- **Jog validation**: connection, lock state, rate limit (5 Hz), cold extrusion guard (min 180°C), homing requirement, soft limits
- **Raw G-code**: denylist (M502, M500, M851, M301, M304, M92, M206, M428), comment stripping
- **Move validation**: G0/G1 regex parsing with bounds checking against config
- **Absolute position**: bed limit check (0–220 XY, 0–260 Z)

### 4.2 Denied Commands

| Command | Reason |
|---------|--------|
| M502 | Factory reset — erases EEPROM calibration |
| M500 | Save to EEPROM — unintended persistent changes |
| M851 | Z probe offset — risks bed collision |
| M301/M304 | PID tuning — thermal safety implications |
| M92 | Steps/mm — movement calibration corruption |
| M206/M428 | Home offsets — movement origin corruption |

### 4.3 E-Stop

M112 bypasses all queues via `send_immediate()` — direct serial write with no ok-wait.

---

## 5. Test Coverage

### 5.1 Unit Tests (80 tests, all passing)

| Module | Tests | Coverage |
|--------|-------|----------|
| `test_state.py` | 16 | M114/M105/firmware parsing, ThreadSafeState |
| `test_serial_mock.py` | 12 | Mock printer, command dispatch, E-stop |
| `test_safety.py` | 30 | Jog limits, denylist, cold extrusion, bounds |
| `test_gcode.py` | 15 | Move builders, precision, mode switching |
| `test_backend_api.py` | 7 | REST endpoints, mock fixtures |

### 5.2 End-to-End Movement Tests (17 checks, all passing)

| Phase | Checks | What it verifies |
|-------|--------|------------------|
| Connectivity | 2 | API reachable, printer connected |
| Auto Home (G28) | 3 | Each axis homed, timing |
| Single Axis Moves | 4 | X→50, Y→50, Z→10, move to center |
| WebSocket Circle | 5 | Connection, 20-target circle, position updates, final accuracy, interval |
| Safety Rejection | 2 | Negative X blocked, Y>220 blocked |
| Return Home | 1 | Precise return to origin |

### 5.3 Measured Performance

| Metric | Measured Value |
|--------|----------------|
| X move 110 mm | 1.3 s |
| Y move 110 mm | 1.0 s |
| Z move 10 mm | 2.4 s |
| Homing (G28 all) | 3.7 s (warm) to 12 s (cold) |
| Follower update interval | 306 ms average |
| State broadcast rate | ~10 Hz (version-gated) |
| M114 poll rate | 2 Hz (when queue empty) |
| React render | 60 fps |

---

## 6. System Limits

### 6.1 Protocol Limits

| Limit | Description | Impact |
|-------|-------------|--------|
| **No line numbering** | Commands sent without `N` prefix or checksum | A corrupted byte over serial is silently executed or silently lost. Safe over short USB cables; risky over serial extenders or noisy environments. |
| **No Marlin buffer awareness** | System does not read `ADVANCED_OK` or buffer-free-slot reports | Cannot optimally fill the 16-slot planner buffer. Commands are strictly one-at-a-time (ok-gated), which is safe but sacrifices potential throughput. |
| **10 s response timeout** | `RESPONSE_TIMEOUT_S = 10.0` is hardcoded | G28 homing on a large printer with slow endstop approach may exceed 10 s. Would need per-command timeouts. |
| **No M400 synchronization** | M114 returns the target position, not the physical position | The "actual" display shows where Marlin thinks the head is going, not necessarily where it physically is. For precise positional feedback, M400 (wait for moves to finish) should precede M114. |

### 6.2 Motion Limits

| Limit | Description | Impact |
|-------|-------------|--------|
| **No acceleration profiling** | Backend sends G1 with fixed feedrate; relies on Marlin's internal acceleration | At rapid direction changes (mouse drag zigzag), the planner handles acceleration safety. Motion may feel jerky at high input rates. |
| **100 ms follower tick** | Target position is sent at most 10×/s | At 200 mm/s feedrate, each segment can be up to 20 mm. Very rapid mouse sweeps produce coarse segments. |
| **No curved moves** | Only linear G1 supported | Arcs (G2/G3), splines, and complex paths are not available through the UI. Must use raw G-code. |
| **Z mouse control absent** | Mouse interaction targets XY bed plane only | Z must be controlled via keyboard (Shift+W/S). No scroll-wheel or multi-touch Z input. |
| **Single printer only** | One serial connection per backend instance | Cannot control multiple printers from one server. |

### 6.3 Safety Limits

| Limit | Description | Impact |
|-------|-------------|--------|
| **Soft limits only** | Bounds checking is in software against config values | If config values are wrong, the printer can crash into mechanical limits. Marlin's own endstops are the last line of defense. |
| **No acceleration limit enforcement** | Backend does not check if feedrate exceeds printer capability | F12000 (200 mm/s) may exceed the hardware max on some printers. Marlin clamps internally, but the user gets no warning. |
| **Denylist is hardcoded** | Cannot add/remove commands from the safety denylist via config | Requires code change to block additional commands. |
| **Jog rate limit is global** | 5 Hz limit applies across all axes collectively | A burst of X, Y, Z jogs in quick succession could send 3 commands in one 200 ms window. |
| **No thermal runaway monitoring** | Backend reads temps but does not act on thermal anomalies | Relies entirely on Marlin firmware for thermal safety shutdowns. |

### 6.4 Network & Frontend Limits

| Limit | Description | Impact |
|-------|-------------|--------|
| **No authentication** | REST and WebSocket endpoints are unauthenticated | Anyone on localhost can control the printer. Acceptable for single-user desktop use; dangerous if exposed to a network. |
| **No WebSocket heartbeat** | No ping/pong mechanism | A silently dropped connection is only detected on the next failed send. The 3 s reconnect delay is fixed (no exponential backoff). |
| **No state compression** | Full state JSON sent on every broadcast (~10 Hz) | Wastes bandwidth when only position changed. Differential updates would reduce payload. |
| **Localhost-only CORS** | Backend accepts requests from `localhost:3000`, `5173`, `5174` only | Cannot serve the UI from a different machine without modifying CORS settings. |
| **Hardcoded backend URL** | React app connects to `ws://127.0.0.1:8765` | No runtime configuration for remote backend address. |

### 6.5 Operational Limits

| Limit | Description | Impact |
|-------|-------------|--------|
| **No graceful shutdown** | Server relies on Ctrl+C / KeyboardInterrupt | Serial port may not be cleanly released on crash. Restarting may require unplugging USB. |
| **No persistent state** | Position and homing status are lost on restart | Printer must be re-homed after every backend restart. |
| **No print file support** | Cannot load, parse, or stream .gcode files | The system is a real-time jog controller, not a print server. For actual printing, use OctoPrint or similar. |
| **Single config profile** | One `config.yaml` per run; no printer profile switching | Changing printers requires editing the config file and restarting. |
| **No undo** | Once a G-code command is sent, it cannot be recalled | Only E-stop (M112) can halt execution. There is no "move back to previous position" command. |
| **Windows-primary** | `start.bat` is Windows-only; terminal jog uses `msvcrt` on Windows | Linux/macOS terminal jog is supported via `select`/`tty` but not tested. No `start.sh` equivalent exists. |

### 6.6 Visualization Limits

| Limit | Description | Impact |
|-------|-------------|--------|
| **No printer geometry** | The 3D scene shows bed + toolhead only | Frame, rods, belts, and mechanical structure are not rendered. No collision visualization. |
| **No filament/extrusion visualization** | E-axis changes are not rendered | Cannot preview deposited material or extrusion paths. |
| **Fixed camera defaults** | Camera starts at a hardcoded elevated angle | No saved camera presets or configurable default viewpoint. |
| **No multi-tool support** | Single actuator visualization only | Printers with dual extruders or tool changers are not represented. |

---

## 7. File Map

```
printer_controller/
├── backend/
│   ├── main.py              CLI entry, logging, startup
│   ├── app.py               FastAPI + WebSocket + 3 async loops
│   ├── serial_worker.py     USB serial, ok-gate, 3-channel dispatch
│   ├── printer_state.py     State model + Marlin response parsers
│   ├── safety.py            Bounds, denylist, rate limit, extrusion guard
│   ├── gcode.py             G-code builder functions
│   ├── config.py            YAML config → nested dataclasses
│   └── jog.py               Terminal WASD controller
├── react_visualizer/
│   └── src/
│       ├── App.tsx           Root component, mode toggle
│       ├── PrinterScene.tsx  3D bed, volume, actuator, ghost
│       ├── useActuatorControl.ts  60fps input + reconciliation
│       ├── MouseControl.tsx  Bed-plane click/drag
│       ├── usePrinterState.ts  WebSocket state + target send
│       ├── useKeyboardJog.ts  Keyboard input handler
│       ├── api.ts            REST wrapper
│       ├── StatusOverlay.tsx  Connection/state HUD
│       └── ControlsOverlay.tsx  Key bindings HUD
├── scripts/
│   ├── test_movements.py    17-check E2E movement test
│   ├── diagnose_quick.py    Quick serial diagnostics
│   ├── diagnose_timing.py   Command timing analysis
│   ├── draw_circle.py       WebSocket follower circle demo
│   └── debug_move_timing.py Move timing profiler
├── tests/
│   ├── test_state.py        Parser + state tests (16)
│   ├── test_serial_mock.py  Mock serial tests (12)
│   ├── test_safety.py       Safety validation tests (30)
│   ├── test_gcode.py        G-code builder tests (15)
│   └── test_backend_api.py  API route tests (7)
├── docs/
│   ├── learning-to-talk-to-a-printer.md  Protocol learnings
│   └── system-report.md     This file
├── godot_visualizer/         Legacy 3D visualizer (read-only)
├── config.example.yaml       Template configuration
├── requirements.txt          Python dependencies
└── README.md                 User-facing documentation
../start.bat                  One-click Windows launcher
```

---

## 8. Dependencies

### Python

| Package | Purpose |
|---------|---------|
| fastapi | Async REST + WebSocket server |
| uvicorn | ASGI server |
| pyserial | USB serial port access |
| pydantic | Data validation |
| pyyaml | Config file parsing |
| pytest | Test framework |
| pytest-asyncio | Async test support |
| httpx | HTTP client for API tests |
| rich | Terminal formatting |

### React

| Package | Purpose |
|---------|---------|
| react 19.x | UI framework |
| @react-three/fiber 9.x | Three.js React renderer |
| @react-three/drei 10.x | Camera controls, helpers |
| three 0.184 | 3D graphics engine |
| vite 8.x | Build tool + dev server |
| typescript 6.x | Type checking |

---

## 9. What This System Is Not

- **Not a print server.** It cannot load, slice, or stream .gcode files. Use OctoPrint, PrusaSlicer, or Klipper for actual printing.
- **Not a CAM tool.** It does not generate toolpaths from 3D models.
- **Not a monitoring system.** It reads temperatures but does not act on thermal anomalies, track print progress, or send alerts.
- **Not network-safe.** It has no authentication, encryption, or access control. It must only run on localhost or a trusted local network.
- **Not firmware.** It runs on a PC and talks to Marlin over USB. It does not modify, flash, or configure the printer firmware.
