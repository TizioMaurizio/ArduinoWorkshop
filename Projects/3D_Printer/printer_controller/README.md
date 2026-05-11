# 3D Printer USB G-code Controller

Python USB G-code controller for Marlin-compatible FDM printers with a Godot 4 3D visualizer.

**Python is the authority.** All printer control, safety checks, command queueing, and serial handling live in Python. Godot is a read-only visualization client.

---

## ⚠️ Safety Warnings

- **USB G-code control can move motors immediately.** There is no confirmation step once a command is sent.
- **Wrong bed dimensions can crash the printer.** Verify `config.yaml` matches your printer exactly.
- **Homing should be tested carefully.** Make sure axes have room to move before pressing H.
- **Cold extrusion is blocked by default.** Do not override unless you know what you're doing.
- **Keep a hand near the printer power switch** during first tests.
- **Start with `--mock` mode** to verify controls without a real printer.
- **Then test with no filament loaded.**
- **Then test with very small jog distances** (0.1 mm).
- **Never leave the printer unattended** while controlled by this program.

---

## Quick Start

```bash
cd Projects/3D_Printer/printer_controller

python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### Mock mode (no printer needed)

```bash
python -m backend.main --mock
```

This starts:
- Terminal WASD jog controller
- WebSocket state server at `ws://127.0.0.1:8765/ws/state`
- REST API at `http://127.0.0.1:8765`

### One-click launcher (Windows)

Double-click `start.bat` in `Projects/3D_Printer/`. It starts both backend and frontend in separate windows.

### Real printer

```bash
python -m backend.main --list-ports
python -m backend.main --port COM3
```

Linux:

```bash
python -m backend.main --port /dev/ttyUSB0
```

Auto-detect:

```bash
python -m backend.main --auto
```

### Godot visualizer

Open in Godot 4.x:

```
godot_visualizer/project.godot
```

The visualizer connects to the Python backend via WebSocket and shows the printer bed, nozzle position, and status. It does **not** send any G-code.

---

## Terminal Controls

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

### Terminal notes (Windows)

- **Ctrl+W** may close the tab in Windows Terminal. Use cmd.exe or configure your terminal to pass through Ctrl+W.
- **Ctrl+S** may freeze output in legacy cmd.exe. This does not affect modern terminals.

---

## API Endpoints

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

---

## Configuration

Copy `config.example.yaml` to `config.yaml` and adjust for your printer:

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

---

## Architecture

```
printer_controller/
├─ backend/
│  ├─ main.py            # CLI entry point
│  ├─ app.py             # FastAPI + WebSocket server
│  ├─ serial_worker.py   # USB serial connection + command queue
│  ├─ printer_state.py   # State model + Marlin response parsers
│  ├─ gcode.py           # G-code builder functions
│  ├─ jog.py             # Terminal WASD controller
│  ├─ safety.py          # Soft limits, cold extrusion guard
│  └─ config.py          # Config loader
├─ react_visualizer/     # React + Three.js 3D digital shadow
├─ godot_visualizer/     # Read-only 3D visualizer (Godot 4)
├─ scripts/              # Diagnostic and test scripts
│  ├─ test_movements.py  # 17-check end-to-end movement test
│  ├─ diagnose_quick.py  # Quick serial diagnostics
│  └─ draw_circle.py     # WebSocket follower circle demo
├─ docs/                 # Design docs and learnings
├─ tests/                # Unit tests (pytest)
├─ config.example.yaml
├─ requirements.txt
└─ README.md
../start.bat             # One-click Windows launcher
```

### Design rule

- Python sends G-code to the printer.
- Python validates every command through the safety layer.
- Visualizers (React, Godot) only receive state via WebSocket and render it.
- Visualizers never open the serial port, generate G-code, or decide safety.

---

## React 3D Digital Shadow

The React visualizer shows a real-time 3D digital shadow of the actuator (tool head) position with interactive control. It connects to the Python backend via WebSocket for bidirectional communication.

### Launch (both backend + frontend)

**Terminal 1 — Python backend:**

```bash
cd Projects/3D_Printer/printer_controller

# Activate venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Linux/macOS

# Real printer (auto-detect or specify port)
python -m backend.main --auto
python -m backend.main --port COM11 --baud 250000

# Mock (no printer)
python -m backend.main --mock
```

**Terminal 2 — React frontend:**

```bash
cd Projects/3D_Printer/printer_controller/react_visualizer
npm install    # first time only
npm run dev
```

Open `http://localhost:5173` in a browser. Both terminals must stay running.

### Real-time controls

The React app sends target positions to the backend via WebSocket. The backend's follower loop converts these into ok-gated G1 commands at 100ms intervals.

| Input | Action |
|-------|--------|
| W / S | Move Y +/- |
| A / D | Move X -/+ |
| Shift+W / Shift+S | Move Z +/- |
| H | Home all axes |
| Space | Emergency stop (M112) |
| +/- | Change jog step size |
| Mouse mode button | Toggle click-drag on build plate |

**Keyboard** moves are continuous (hold-to-move at 50 mm/s XY, 5 mm/s Z). The 3D scene updates at 60fps locally; the physical printer follows at 100ms ticks.

**Mouse mode** lets you click and drag on the build plate to position the tool head. Toggle with the button at the bottom-left of the viewport.

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Supported Printers

Any Marlin-compatible FDM printer connected over USB serial. Tested targets include Elegoo and Geeetech printers. Configure your specific printer profile in `config.yaml`.

---

## License

Internal project — ArduinoWorkshop.
