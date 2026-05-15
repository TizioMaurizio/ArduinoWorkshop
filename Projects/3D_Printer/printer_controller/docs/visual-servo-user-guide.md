# Visual Servo — User Guide

Track a colored object on the print bed using a USB camera and move the extruder toward it automatically, with live browser visualization and a 3D digital twin.

---

## Quick Start

### Prerequisites

- **Python 3.10+** with `opencv-python`, `numpy`, `requests` installed
- **Geeetech A10** (or any Marlin printer) connected via USB
- **USB webcam** overlooking the print bed
- **Blue LEGO bricks** attached to the extruder (tracking marker)
- **Red LEGO plate** (or any red object) placed on the bed (target)

### One-Click Launch

Double-click **`printer_tracker.bat`** in the `printer_controller/` folder.

It starts three services in order:
1. Camera server → `http://127.0.0.1:8766`
2. Printer backend → `http://127.0.0.1:8765`
3. Visual servo → `http://127.0.0.1:8767`

Then open your browser:

| URL | What it shows |
|-----|---------------|
| `http://127.0.0.1:8767` | Live tracking UI with video, controls, jog buttons |
| `http://127.0.0.1:8767/twin` | 3D digital twin with extruder, target, laser line |
| `http://127.0.0.1:8766` | Raw camera feed (no annotations) |

All URLs also work from other devices on the LAN — replace `127.0.0.1` with the PC's IP address (shown at startup).

### Manual Launch

If you need more control, start each component separately:

```bash
# Terminal 1 — Camera
cd printer_controller
python scripts/camera_server.py --camera auto --port 8766

# Terminal 2 — Printer backend
cd printer_controller
python -m backend.main --auto

# Terminal 3 — Visual servo (with file watcher for hot-reload)
cd printer_controller
python scripts/watch_servo.py -- \
  --printer-url http://127.0.0.1:8765 \
  --camera-url http://127.0.0.1:8766 \
  --step 1.0 \
  --save-frames \
  --timeout 600 \
  --viz-port 8767 \
  --z-height 10
```

Or run the servo directly (no hot-reload):
```bash
python scripts/visual_servo.py \
  --printer-url http://127.0.0.1:8765 \
  --camera-url http://127.0.0.1:8766 \
  --step 1.0 \
  --timeout 120
```

---

## Physical Setup

### Camera Placement

The camera must be **fixed** and must have a clear view of the print bed. Mount it above and slightly behind the printer, angled down. The entire bed should be visible in the frame.

```
        [Camera] ← fixed, looking down
            \
             \
    ┌─────────\─────────┐
    │          ↓         │
    │  [Red]     [Blue]  │  ← print bed
    │  target    marker  │
    └────────────────────┘
```

**Important**: The camera must see both the blue marker (extruder) and the red target simultaneously. If the gantry crossbar blocks the camera's view at certain Y positions, move the target away from the obstruction zone.

### Blue Marker (Extruder)

Attach 1–2 blue LEGO bricks on top of the extruder carriage where the camera can see them. The system detects blue in HSV range \[95–130, 80–255, 50–255\]. Standard bright blue LEGO works well.

### Red Target (Goal)

Place a red object on the bed. The system detects red in HSV ranges \[0–10\] and \[165–180\] hue with saturation/value ≥ 50. A red LEGO plate, red card, or red tape works. Size should be at least 30×30mm for reliable detection.

**Best position**: Center of the bed, away from edges and gantry crossbar. Avoid placing the target where the gantry would occlude it from the camera's angle as the extruder approaches.

---

## Tracking Phases

The system runs through these phases automatically:

| Phase | What happens |
|-------|-------------|
| **HOMING** | Sends G28, homes all axes. Wait for endstops. |
| **RAISING Z** | Moves Z to safe height (default 10mm above bed) |
| **TRACKING** | Detects red/blue, computes offset, moves extruder toward target |
| **DONE** | Either arrived (distance < 40px) or exhausted move budget (6000 active moves) |

After DONE, the process exits and the watcher restarts it automatically.

---

## Browser UI — Tracking Page (`/`)

### Video Streams

- **Top stream**: Annotated view — detection overlays, HUD panel, movement arrows
- **Bottom stream**: Raw camera feed — unprocessed video for comparison

### HUD Overlay (on annotated stream)

The top-left panel shows:
- **Phase**: TRACKING, DONE, PAUSED
- **Iteration**: frame number / active moves
- **Distance**: pixel distance from blue marker to red target
- **Position**: current printer X, Y, Z in mm
- **Markov**: filter status (if a detection was rejected, shows reason)

### Manual Controls (right panel)

| Control | Action |
|---------|--------|
| **STOP** button | Pause/resume auto-tracking. Extruder holds position. |
| **HOME** button | Send G28 (home all axes) |
| **Jog arrows** | Move extruder manually (XY grid + Z up/down) |
| **Step size** | Set jog increment: 0.1–50 mm |
| **G-code input** | Send any raw G-code command to the printer |

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `W` / `S` | Jog Y+ / Y- |
| `A` / `D` | Jog X- / X+ |
| `Q` / `E` | Jog Z+ / Z- |
| `Arrow keys` | Jog (alternate) |
| `Space` | Toggle STOP / RESUME |
| `Enter` | Send G-code from input field |

---

## 3D Digital Twin (`/twin`)

The twin shows a 3D model of the printer with real-time tracking state:

- **Green bed**: 220×220mm with grid lines
- **Blue extruder**: Moves in X/Y/Z matching the real printer
- **Pulsing blue ring**: Marks the extruder position
- **Red target**: Estimated position on the bed
- **Pulsing red ring**: Glows brighter when target is detected
- **Green laser line**: Points from nozzle tip to estimated target
- **Blue trail**: Breadcrumb path of where the extruder has been
- **PiP feed**: Small live camera view in the corner

### Mouse Controls

| Action | Effect |
|--------|--------|
| Left-drag | Rotate view |
| Right-drag | Pan view |
| Scroll | Zoom in/out |

---

## Command-Line Options

### `visual_servo.py`

| Flag | Default | Description |
|------|---------|-------------|
| `--printer-url` | `http://127.0.0.1:8765` | Printer backend URL |
| `--camera-url` | `http://127.0.0.1:8766` | Camera server URL |
| `--step` | `1.0` | Max step size per move (mm) |
| `--timeout` | `120` | Max runtime (seconds) |
| `--save-frames` | off | Save annotated debug frames to `logs/` |
| `--calibrate` | off | Run axis calibration before tracking |
| `--viz-port` | `8767` | Browser visualization port |
| `--z-height` | `10.0` | Operating Z height above bed (mm) |
| `--camera` | none | If set, starts camera server internally on this index |
| `--camera-port` | `8766` | Camera server port (if `--camera` used) |

### `camera_server.py`

| Flag | Default | Description |
|------|---------|-------------|
| `--camera` | `auto` | Camera index or `auto` to scan |
| `--port` | `8766` | HTTP port |
| `--width` | `640` | Capture width |
| `--height` | `480` | Capture height |

### `watch_servo.py`

Pass all `visual_servo.py` arguments after `--`:
```bash
python scripts/watch_servo.py -- --step 1.0 --timeout 600
```

The watcher:
- Restarts the servo when `visual_servo.py` is edited (hot-reload)
- Restarts on crash or normal completion
- Checks syntax before restarting (avoids crash loops from typos)

---

## Tuning Parameters

### Detection Thresholds

Edit the constants near the top of `visual_servo.py`:

| Parameter | Default | Effect |
|-----------|---------|--------|
| `RED_LOW1/HIGH1` | `[0,50,50]`–`[10,255,255]` | Low red hue range |
| `RED_LOW2/HIGH2` | `[165,50,50]`–`[180,255,255]` | High red hue range |
| `BLUE_LOW/HIGH` | `[95,80,50]`–`[130,255,255]` | Blue marker range |
| `MIN_CONTOUR_AREA` | `300` px² | Minimum contour when locked |
| `MIN_CONTOUR_AREA_ACQUIRE` | `1500` px² | Minimum contour for re-acquisition |
| `ARRIVAL_THRESHOLD_PX` | `40` px | Distance to declare "arrived" |

**Tip**: If the system doesn't detect your target, open `http://127.0.0.1:8766` to see the raw camera feed, then adjust HSV ranges. You can test ranges with an OpenCV HSV picker.

### Motion Parameters

| Parameter | Default | Effect |
|-----------|---------|--------|
| `STEP_MM` | `1.0` mm | Base step size per tracking move |
| `MAX_ITERATIONS` | `6000` | Max active moves before restart |
| `TARGET_FPS` | `30` | Camera poll rate |

### Markov Filter

| Parameter | Default | Effect |
|-----------|---------|--------|
| `RedTracker.WINDOW` | `15` | History buffer size |
| `RedTracker.AREA_DROP_RATIO` | `0.35` | Area drop rejection threshold |
| `RedTracker.COMOVEMENT_FRAMES` | `20` | Co-movement lookback window |
| `RedTracker.COMOVEMENT_PX` | `8.0` | Co-movement std-dev threshold |
| `RedTracker.GATE_PX` | `150.0` | Max position jump allowed |

### Printer Motion Tuning

Sent automatically before tracking starts:
```
M201 X800 Y800       — max acceleration 800 mm/s²
M204 T800             — travel acceleration 800 mm/s²
M205 X10 Y10         — jerk limits 10 mm/s
```

These values work well for smooth visual servo motion on the Geeetech A10. If your printer stutters, try lowering the acceleration. If it's too slow, raise it.

---

## Troubleshooting

### "Printer backend not reachable"

The backend isn't running or hasn't connected to the printer yet.
- Check that the printer is plugged in via USB
- Run `python -m backend.main --list-ports` to see available serial ports
- Start the backend with `python -m backend.main --auto` or `--port COM11`

### "No red object detected in initial frame"

The camera can't see a red object meeting the acquisition threshold (1500 px²).
- Check the raw camera feed at `http://127.0.0.1:8766`
- Make sure the red object is well-lit and at least 30×30mm
- Adjust `RED_LOW`/`RED_HIGH` HSV ranges if your red is different

### Camera shows black or no stream

- Check that no other application is using the webcam
- Try different camera indices: `python scripts/camera_server.py --camera 0`
- On Windows, verify MSMF backend is available

### Extruder moves the wrong direction

The axis mapping is inverted for your camera mounting.
- Run with `--calibrate` to auto-detect axis directions
- Or manually flip the signs in `AxisMapping`:
  - `cam_right_to_printer_x`: set to `+1` or `-1`
  - `cam_down_to_printer_y`: set to `+1` or `-1`

### Motion is stuttery

- Check that motion tuning commands were sent (look for "Motion tuned" in the log)
- Lower acceleration: change M201/M204 values in the code
- Increase EMA smoothing: reduce `PrinterSender.EMA_ALPHA` (e.g., 0.15)

### "No red detected" for long periods

The target is occluded or outside the camera's view.
- Check the camera feed — can you see the red object?
- If the gantry blocks the view, reposition the target toward the bed center
- If lighting changed, readjust HSV thresholds

### System keeps restarting

The watcher restarts the servo after completion or crashes. This is normal behavior — each restart homes the printer and tries again. Check the terminal log for error messages if it keeps crashing.

---

## API Reference

All endpoints are on the visualization server (default port 8767).

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Tracking UI page |
| `/twin` | GET | 3D digital twin page |
| `/stream` | GET | MJPEG annotated video stream |
| `/raw` | GET | MJPEG raw camera stream |
| `/api/state` | GET | JSON: `{phase, iteration, x, y, z, distance, red_found, ...}` |
| `/api/events` | GET | SSE: real-time state push (JSON per event) |
| `/api/stop` | POST | Toggle pause/resume tracking |
| `/api/jog` | POST | Manual jog: `{"x": 5, "y": 0, "z": 0}` |
| `/api/gcode` | POST | Send raw G-code: `{"command": "G28"}` |
| `/api/home` | POST | Home all axes (G28) |
| `/health` | GET | `{"status": "ok"}` |

### State Object (from `/api/state` or `/api/events`)

```json
{
  "phase": "TRACKING",
  "iteration": 450,
  "stopped": false,
  "arrived": false,
  "x": 85.3,
  "y": 142.7,
  "z": 10.0,
  "dx": -0.8,
  "dy": 1.2,
  "status": "Moving dX=-0.8 dY=+1.2mm",
  "distance": 156.3,
  "red_found": true,
  "red_x": 320,
  "red_y": 280,
  "red_area": 4500
}
```

---

## File Structure

```
printer_controller/
├── printer_tracker.bat              ← one-click launcher
├── scripts/
│   ├── visual_servo.py              ← main controller (2381 lines)
│   ├── camera_server.py             ← USB camera MJPEG server (329 lines)
│   └── watch_servo.py               ← hot-reload watcher (87 lines)
├── backend/
│   ├── main.py                      ← CLI entry point
│   └── app.py                       ← REST API server
├── docs/
│   ├── visual-servo-development.md  ← how it was built
│   └── visual-servo-user-guide.md   ← this file
└── logs/
    └── visual_servo_frames/         ← debug frames (if --save-frames)
```
