# 3D Printer Tracker — Vision-Guided Marlin Controller

Vision-guided control of a Marlin-compatible FDM printer. A USB camera watches the build plate, OpenCV tracks a colored target, and the printer's extruder is driven to follow it in real time. A browser-based **Digital Twin UI at [http://127.0.0.1:8767/twin](http://127.0.0.1:8767/twin)** is the primary interface for live monitoring, manual jog, recording, and replay.

> **Python is the authority.** All printer control, safety checks, command queueing, and serial handling live in Python. The browser twin and Godot visualizer are read-only/command-relay clients.

---

## ⚠️ Safety Warnings

- **USB G-code control moves motors immediately.** There is no confirmation step.
- **Wrong bed dimensions in `config.yaml` can crash the printer.**
- **Test homing carefully** — make sure axes have room to move.
- **Cold extrusion is blocked by default.**
- **Keep a hand near the power switch** during first runs.
- **Start with `--mock` mode** to verify controls without a real printer.
- **Never leave the printer unattended** while controlled by this program.

---

## One-Click Launch (Windows)

```bat
.\printer_tracker.bat
```

This script (in this folder) starts:

| Service | Port | Purpose |
|---------|------|---------|
| **Camera server** | `8766` | Captures USB webcam, exposes MJPEG and frame API |
| **Backend** | `8765` | Marlin serial driver, REST + WebSocket control |
| **Visual servo** | `8767` | Color tracker, twin UI, MJPEG with overlays |

When everything is up, open **[http://127.0.0.1:8767/twin](http://127.0.0.1:8767/twin)**.

The launcher uses Windows Job Objects so closing the parent window terminates all child processes cleanly.

---

## The Digital Twin UI — `http://127.0.0.1:8767/twin`

The twin is a single-page browser app that combines a live 3D Three.js scene of the printer with the annotated camera feed and full control surface. It is the primary way to drive the system once it is running.

### Layout

```
┌─────────────────────────────────────────────────────────────┐
│  AUTO/MANUAL pill   X..Y..Z..   tracking status             │  ← top HUD
│            ● ● ● ● ●    target color picker (horizontal)    │
│                                                             │
│           [ 3D Twin viewport — drag to orbit ]              │
│                                                             │
│                                              ┌────────────┐ │
│                                              │ Jog        │ │
│                                              │ Actions    │ │
│                                              │ G-code     │ │
│                                              │ Settings   │ │
│                                              │ Recording  │ │
│                                              └────────────┘ │
│  [ camera feed — click to enlarge ]                         │
└─────────────────────────────────────────────────────────────┘
```

### Controls

**Top bar — target color picker.** Click a colored dot to select what the camera should track (red, green, yellow, blue, white). Switching colors **resets all accumulated belief**: the ghost anchor, target lock, and tracker memory are dropped so the extruder can re-acquire a fresh target.

**3D viewport.** Live digital twin of the printer bed with:
- Yellow box: extruder position
- Red dot: tracked target (in printer coordinates, projected from the camera)
- Camera frustum at the configured mounting angle
- Orbit with mouse drag, zoom with scroll

**Mode pill (top-left).** Click or press `Space` to toggle between `AUTO` (visual servoing active) and `MANUAL` (servo paused, you drive). Any jog command auto-switches to MANUAL.

**Jog Controls panel.**
- X/Y arrow grid + Z up/down
- Configurable step (0.1 / 1 / 5 / 10 / 50 mm)
- Keyboard shortcuts: `WASD` for XY, `Q`/`E` for Z, `+`/`−` to change step, `H` to home, `Space` to toggle AUTO/MANUAL

**Actions panel.** AUTO toggle, HOME, and a red E-STOP that sends `M410` (and `M112` if held).

**G-code panel.** Type any raw G-code (e.g. `G1 X100 F3000`) and dispatch it. A scrolling log shows recent commands with replies.

**Settings panel.**
- Extruder color (the color of the marker stuck to your hot end)
- Invert X / Invert Y (axis-mapping fixes)
- Visual Only mode (camera tracks but printer does not move)

**Recording panel.**
- `● Record` — starts capturing every move (manual jog or auto-tracking) with absolute coordinates
- `■ Stop` — opens an inline name input; type a name and `Save` to persist
- Dropdown lists saved recordings (`name (N pts)`)
- `▶ Play` — replays a recording: raises Z to a safe height, moves Y to clearance, travels to the recording start, then walks through every captured point
- `✕ Del` — deletes the selected recording
- Recordings persist to `scripts/.servo_recordings.json` and survive restarts

**Camera feed (bottom-left).** The annotated MJPEG stream from the visual servo — shows the target contour, the extruder marker, distance, and the **ghost anchor** overlay (see below). **Click the feed to toggle enlarged**; click again to shrink.

### The Ghost Anchor

When the extruder moves over the target the camera loses sight of it. To preserve the system's belief about where the target is, the tracker maintains a **ghost anchor**:

1. Every accepted detection in the last 2 seconds is recorded with its area and the printer position at the time.
2. The largest-area entry in that window is selected as the anchor.
3. While the live detection is missing or its area drops below 50% of the anchor, the tracker projects the anchor pixel position by the printer motion since it was captured (negated, since the camera is mounted on the moving extruder so static objects shift opposite to printer motion).
4. The projected position is drawn on the camera feed as a **magenta dashed circle labeled `GHOST (area px²)`** and used as a soft anchor for re-acquisition lock.
5. Once the target is re-detected, the ghost deactivates and the history is allowed to update again.

The ghost persists indefinitely while the target stays lost — only the sliding window for picking the anchor is time-limited.

---

## Manual Setup (without the launcher)

Useful if you want to run pieces individually, for example on Linux/macOS.

```bash
cd Projects/3D_Printer/printer_controller
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### Mock mode (no printer)

```bash
python -m backend.main --mock
```

Starts terminal WASD jog controller, WebSocket state at `ws://127.0.0.1:8765/ws/state`, REST at `http://127.0.0.1:8765`.

### Real printer

```bash
python -m backend.main --list-ports
python -m backend.main --port COM3        # or /dev/ttyUSB0
python -m backend.main --auto             # auto-detect
```

### Visual servo + twin UI

```bash
python scripts/camera_server.py --camera 0          # USB webcam
python -m backend.main --auto                       # printer
python scripts/visual_servo.py                      # tracker + twin UI on :8767
```

Open `http://127.0.0.1:8767/twin`.

### Watch mode (auto-reload visual servo)

```bash
python scripts/watch_servo.py
```

Hot-reloads `visual_servo.py` whenever it changes.

---

## Configuration

Copy `config.example.yaml` to `config.yaml` and adjust:

```yaml
printer:
  name: "my_printer"
  baud_candidates: [115200, 250000]
  bed:
    x_max: 220
    y_max: 220
    z_max: 250
```

**Do not hard-code bed dimensions.** Always use the config file.

The visual servo persists its own runtime state to `scripts/.servo_settings.json` (target color, extruder color, camera mount angle) and `scripts/.servo_recordings.json` (saved sequences). Both are gitignored.

---

## Terminal Controls (backend WASD)

```
W/S         Y +/-
A/D         X -/+
Shift+W/S   Z +/-
Ctrl+W/S    E +/- (extrude/retract)
H           Home all axes
X/Y/Z       Home single axis
P           Query position (M114)
T           Query temperature (M105)
G           Enter raw G-code
+/-         Change jog step size
SPACE       Emergency stop (M112)
ESC/Q       Quit
```

> On Windows Terminal, `Ctrl+W` may close the tab. Use `cmd.exe` or remap.

---

## API Endpoints

### Backend (`:8765`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/state` | Current printer state JSON |
| GET | `/ports` | Available serial ports |
| POST | `/connect` | Connect to serial port |
| POST | `/disconnect` | Disconnect |
| POST | `/home` | Home axes |
| POST | `/jog` | Jog movement |
| POST | `/gcode` | Send raw G-code |
| POST | `/emergency-stop` | Emergency stop (M112) |
| WS | `/ws/state` | Live state broadcast |

### Visual servo + twin (`:8767`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/twin` | Digital twin web UI |
| GET | `/stream` | MJPEG of annotated camera frames |
| GET | `/api/state` | Tracking + printer state JSON |
| GET | `/api/events` | Server-sent event stream |
| GET | `/api/records` | List saved recordings |
| POST | `/api/jog` | Manual jog (auto-switches to MANUAL) |
| POST | `/api/gcode` | Send raw G-code |
| POST | `/api/home` | Home all axes |
| POST | `/api/stop` | Pause auto-tracking (M410) |
| POST | `/api/resume` | Resume auto-tracking |
| POST | `/api/settings` | Update target/extruder colors (resets belief) |
| POST | `/api/record/start` | Begin recording moves |
| POST | `/api/record/stop` | Stop and save with a name |
| POST | `/api/record/play` | Replay a saved recording |
| POST | `/api/record/delete` | Delete a recording |

### Camera server (`:8766`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/stream` | Raw MJPEG from webcam |
| GET | `/frame.jpg` | Single JPEG snapshot |
| GET | `/health` | Camera health check |

---

## Architecture

```
printer_controller/
├─ backend/                  # Python printer authority
│  ├─ main.py                # CLI entry
│  ├─ app.py                 # FastAPI + WebSocket
│  ├─ serial_worker.py       # Serial connection + queue
│  ├─ printer_state.py       # State + Marlin response parsers
│  ├─ gcode.py               # G-code builders
│  ├─ jog.py                 # Terminal WASD controller
│  ├─ safety.py              # Soft limits, cold-extrusion guard
│  └─ config.py
├─ scripts/
│  ├─ visual_servo.py        # Tracker + twin UI server (port 8767)
│  ├─ camera_server.py       # USB webcam MJPEG (port 8766)
│  ├─ launcher.py            # Job-object process supervisor
│  ├─ watch_servo.py         # Hot-reload visual_servo on edit
│  ├─ test_movements.py      # 17-step end-to-end movement test
│  ├─ diagnose_quick.py      # Serial diagnostics
│  └─ draw_circle.py         # Demo follower
├─ react_visualizer/         # React + Three.js shadow (alt UI)
├─ godot_visualizer/         # Godot 4 read-only viewer
├─ docs/                     # Design notes
├─ tests/                    # pytest suite
├─ printer_tracker.bat       # One-click Windows launcher
├─ config.example.yaml
├─ requirements.txt
└─ README.md
```

### Design rule

- Python sends G-code; visualizers never open the serial port.
- Every command passes through the safety layer.
- The twin UI dispatches commands via the visual-servo HTTP API, which forwards safe-checked requests to the backend.

---

## React Visualizer (alternative UI)

A React + Three.js shadow at `http://localhost:5173` is also available.

```bash
cd react_visualizer
npm install
npm run dev
```

The React app supports keyboard jog (WASD/QE), mouse-drag positioning on the bed, and **Ctrl+drag for Z-axis** control via a vertical control plane facing the camera.

---

## Tests

```bash
pytest tests/ -v
```

---

## Supported Printers

Any Marlin-compatible FDM printer over USB serial. Tested on Elegoo and Geeetech (A10) printers. Configure your specific bed/feedrate in `config.yaml`.

---

## License

Internal project — ArduinoWorkshop.
