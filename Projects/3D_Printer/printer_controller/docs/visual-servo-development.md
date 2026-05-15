# Visual Servo — Development History

How we built a closed-loop visual servoing system that tracks a colored object with a USB camera and drives a 3D printer extruder toward it, with a browser-based live visualization and 3D digital twin.

**Date**: 2026-05-14 – 2026-05-15
**Printer**: Geeetech A10, Marlin 1.1.8, CH340 USB (COM11 @ 250000 baud)
**Camera**: NewEye 62 USB webcam (index 1, MSMF backend), 640×480

---

## 1. The Problem

We had a 3D printer we could already control in real time through a REST API (the backend built in earlier sessions). The next question: **can the printer track a physical object using computer vision?**

The idea: mount a fixed USB camera overlooking the print bed, place a colored target on the bed, and have the system move the extruder toward it using proportional control — visual servoing.

This is harder than it sounds. The camera doesn't know which way the printer axes run. The printer moves in millimeters, the camera sees pixels. And Marlin's motion planner stutters if you feed it commands wrong.

---

## 2. Architecture Decisions

### 2.1 Three-Process Design

We split the system into three independent processes:

```
┌─────────────┐    HTTP/MJPEG    ┌──────────────┐    HTTP/REST     ┌──────────────┐
│  Camera      │ ──────────────→ │  Visual       │ ──────────────→ │  Printer     │
│  Server      │  port 8766      │  Servo        │  port 8765      │  Backend     │
│  (OpenCV)    │                 │  (controller) │                 │  (serial)    │
└─────────────┘                 └──────┬───────┘                 └──────────────┘
                                       │
                                       │ HTTP port 8767
                                       ▼
                              ┌────────────────┐
                              │  Browser UI     │
                              │  Live streams   │
                              │  3D Twin        │
                              │  Manual controls│
                              └────────────────┘
```

**Why separate processes?**
- The camera server can survive servo restarts (no dropped USB handle)
- The printer backend can be used independently for manual control
- The servo can hot-reload during development without losing camera or serial state

### 2.2 Camera is Fixed, Marker Tracks the Extruder

**Critical design choice**: The camera is NOT mounted on the extruder. It's a fixed external webcam looking down at the bed. We detect **two** colored objects:

- **Blue LEGO bricks** physically attached to the extruder → marker for "where is the tool head?"
- **Red LEGO plate** placed on the bed → target to track

The offset between blue (extruder) and red (target) in pixel space tells us which direction and how far to move. This avoids needing camera calibration or a known camera-to-printer transform — we just minimize the pixel offset.

### 2.3 HTTP Everywhere

Every component talks HTTP. The camera streams MJPEG. The printer backend serves REST endpoints. The servo controller fetches frames via HTTP and sends G-code commands via HTTP. This makes debugging trivial — you can `curl` any endpoint, open any stream in a browser, and swap components independently.

---

## 3. Building the Camera Server

**File**: `scripts/camera_server.py` (329 lines)

The first component we built. A minimal OpenCV MJPEG streamer:

1. **CameraCapture class**: Background thread grabs frames from `cv2.VideoCapture` in a loop, encodes them as JPEG (quality 80), and stores the latest under a lock.

2. **HTTP server**: ThreadedHTTPServer serves three endpoints:
   - `/` — HTML page with an `<img>` pointing at `/stream`
   - `/stream` — Multipart MJPEG: `Content-Type: multipart/x-mixed-replace; boundary=frame`
   - `/frame.jpg` — Single latest JPEG

3. **Auto-detection**: The `--camera auto` flag iterates camera indices 0–9 with the MSMF backend (Windows), testing `cap.read()` until a working camera is found. Our NewEye 62 webcam consistently lands on index 1.

**Lesson learned**: On Windows, OpenCV defaults to DirectShow, which sometimes fails. Forcing `cv2.CAP_MSMF` backend resolved reliability issues.

---

## 4. Color Detection Pipeline

### 4.1 Why HSV, Not RGB

Red in RGB is fragile — it overlaps with skin, wood, and warm lighting. In HSV, red occupies two narrow hue bands (0°–10° and 165°–180°) with high saturation. Under varying lighting, hue stays stable while RGB shifts dramatically.

### 4.2 Red Detection — Dual-Range Thresholding

```python
# Red wraps around the hue circle
mask1 = cv2.inRange(hsv, [0, 50, 50],   [10, 255, 255])   # low red
mask2 = cv2.inRange(hsv, [165, 50, 50], [180, 255, 255])   # high red
mask  = cv2.bitwise_or(mask1, mask2)

# Clean up: 7×7 elliptical kernel
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)   # remove specks
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)  # fill holes
```

**The saturation/value floor of 50** is deliberately low. Our red LEGO plate sometimes appears dark under shadow. A higher floor would lose it. The morphological opening cleans up noise instead.

### 4.3 Blue Detection

```python
mask = cv2.inRange(hsv, [95, 80, 50], [130, 255, 255])
```

Blue is simpler — one contiguous hue range, and the blue LEGO bricks on the extruder are always well-lit (they sit on top, facing the camera). We pick the **largest blue contour** — no target lock needed since there's only one blue object.

### 4.4 The Dual-Threshold Problem

Early testing revealed a problem: when the red target was far away, its contour was small (~500 px²). When the extruder moved close, reflections and secondary red objects appeared as similar-sized contours. We needed to be strict during acquisition but lenient once locked on.

**Solution: two thresholds**
- `MIN_CONTOUR_AREA_ACQUIRE = 1500` px² — used when re-acquiring (no lock)
- `MIN_CONTOUR_AREA = 300` px² — used when target is locked (known position)

This lets the system acquire only confident detections, then track them even as they shrink or partially occlude.

### 4.5 Target Lock with Scoring

When multiple red contours are visible, which one is "the target"? We use a lock-radius scoring system:

```python
score = contour_area / (distance_to_lock + 1.0)
```

Within `TARGET_LOCK_RADIUS_PX = 200` pixels of the last known position, the largest and closest contour wins. Beyond 200px, we reject and wait for re-acquisition. After 30 consecutive misses, the lock drops and re-acquisition uses the strict threshold.

---

## 5. The Markov Temporal Filter

### 5.1 Why We Needed It

Pure per-frame detection wasn't enough. Three failure modes emerged:

1. **Area drops**: The red LEGO partially occludes behind the gantry crossbar. The visible contour shrinks to 200 px² — technically above MIN_CONTOUR_AREA, but it's a sliver of the real object. Following it sends the extruder into the frame.

2. **Position jumps**: A second red object (cable, reflection) appears 300px away. The target lock catches it sometimes if the real target is momentarily invisible.

3. **Co-movement**: The worst failure. Red reflections on the extruder itself appear as a "red object" that moves perfectly with the blue marker. The servo then thinks it's already at the target and stops. Or worse, chases its own reflection.

### 5.2 The RedTracker Class

We built a three-gate validation filter inspired by Markov chains (state prediction from recent history):

**Gate 1 — Area consistency**:
```
median_area = median(last 15 areas)
if new_area < median_area × 0.35 → REJECT "area_drop"
```
Catches partial occlusions. A 65% area drop means something is wrong.

**Gate 2 — Position prediction gate**:
```
predicted = last_position + velocity × dt
if |detected - predicted| > 150 px → REJECT "position_gate"
```
Velocity is an EMA (α=0.4) of frame-to-frame displacement. A 150px jump means we probably locked onto a different object.

**Gate 3 — Co-movement detection**:
```
offsets = [(red_x - blue_x, red_y - blue_y) for last 20 frames]
if std(offsets_x) < 8 px AND std(offsets_y) < 8 px → REJECT "comovement"
```
If the red-blue pixel offset stays constant while both move, the "red" is physically attached to the extruder. This is the cleverest gate — it detects reflections, shadows, or actual red objects riding the tool head.

**When a gate rejects**: The target lock drops, the tracker resets, and the system re-acquires with the strict 1500 px² threshold. This prevents cascading errors.

### 5.3 Results

The co-movement gate worked reliably. At frame 21 in a typical run, it detected `std_x=5.5, std_y=4.6` and correctly rejected a false red detection that was riding the extruder. The area drop gate caught partial occlusions at distances around 200px. The position gate prevented lock jumps when multiple red objects were visible.

---

## 6. Motion Control — Making the Printer Move Smoothly

### 6.1 Proportional Control

The controller is purely proportional (no I or D terms). Given the pixel offset from blue to red:

```python
dist_px = sqrt(dx² + dy²)
scale = min(2.0, dist_px / 100.0)       # ramp: 0→2× at 200px

if dist_px < 60:                          # fine approach
    scale *= dist_px / 60.0              # linear taper to 0

move_x = (dx/dist) × scale × step_mm × axis_sign
move_y = (dy/dist) × scale × step_mm × axis_sign
```

**Why no I term?** The camera is always looking. If there's steady-state error, the proportional term will keep nudging. An integral term would wind up during occlusion (when red disappears) and cause overshoot when it reappears.

**Why no D term?** The 7×7 morphological filter already smooths centroid jitter. Adding derivative control made movements twitchy.

### 6.2 Axis Mapping

The camera doesn't know which way is "printer X+." We encode this as a sign:

```python
cam_right_to_printer_x = -1.0   # camera right = printer X-
cam_down_to_printer_y  = +1.0   # camera down  = printer Y+
```

These signs depend on how the camera is mounted relative to the printer. We hardcoded them after manual testing, but the `--calibrate` flag can auto-detect them by moving the printer and observing which way the blue marker shifts.

### 6.3 The Stepper Stutter Problem

Our first implementation sent G1 commands directly from the tracking loop at 30Hz. The result: horrible stuttering. The extruder would move-stop-move-stop with audible stepper clicks.

**Root cause**: Marlin's motion planner decelerates to zero at the end of each segment if the next segment isn't already in the buffer. At 30Hz, each segment is tiny (~0.5mm), and Marlin fully decelerates before the next one arrives.

**The fix had three parts:**

1. **Lower acceleration limits**: We send `M201 X800 Y800` (max acceleration 800 mm/s²), `M204 T800` (travel acceleration 800), and `M205 X10 Y10` (jerk 10 mm/s) before tracking starts. Lower acceleration means gentler transitions between segments.

2. **EMA trajectory smoothing** (PrinterSender class): Instead of sending the raw target position each frame, we apply exponential smoothing (α=0.25). The sent position trails the target by ~0.5s, creating a smooth curve that Marlin's planner can blend.

3. **Adaptive feedrate**: Each 50ms segment gets a feedrate matched to its length:
   ```
   feedrate = clamp(300, 2000, segment_mm / 0.05s × 60)
   ```
   Short segments get slow feedrates (gentle), long segments get fast ones. This keeps the planner buffer fed without overruns.

4. **20Hz command rate**: The PrinterSender runs its own thread at 20Hz (50ms interval), decoupled from the 30Hz camera loop. Segments shorter than 0.05mm are skipped entirely.

**Result**: The user described the motion as "very nice and smooth movement!" — the stuttering was completely eliminated.

### 6.4 Bounds Clamping

Every move is clamped to safe limits before sending:
```python
new_x = clamp(printer_x + move_x, 5.0, 195.0)   # 5mm margin from edges
new_y = clamp(printer_y + move_y, 5.0, 215.0)    # 5mm margin
```

The 220mm bed has 5mm safety margins on each side. The printer never hits the physical limits.

---

## 7. Browser Visualization

### 7.1 Why a Built-in Web Server

We needed to see what the camera sees, annotated with detection overlays, from any device on the LAN. Rather than a separate frontend project, we embedded an HTTP server directly in the servo process:

- `VisualizationServer` uses Python's `HTTPServer` with `ThreadingMixIn`
- It binds `0.0.0.0` so it's accessible from phones, tablets, other PCs
- HTML pages are embedded as Python string constants (no external files to deploy)

### 7.2 The Tracking UI (`/`)

A single-page app with:

- **Dual MJPEG streams**: annotated tracking view (with detection overlays, HUD, arrows) and raw camera feed
- **Manual controls**: jog buttons (XY grid + Z), step size selector, G-code input
- **Keyboard shortcuts**: WASD for jogging, Space for pause, Enter for G-code
- **Real-time state**: SSE (Server-Sent Events) pushes position, phase, distance, and status to the browser at frame rate
- **Live/Paused indicator**: blinking pill, color-coded by phase

### 7.3 Server-Sent Events (SSE)

We chose SSE over WebSocket because:
- It's unidirectional (server → client), which is all we need for state sync
- It auto-reconnects on connection drops
- It works through proxies and firewalls better than WebSocket

**Implementation**: A `threading.Condition` variable broadcasts state changes. All SSE client threads wait on the condition, wake up when a new frame is processed, and push the JSON state to their client.

### 7.4 The HUD Overlay

The OpenCV-rendered annotation on each frame includes:
- Blue marker: bright yellow crosshair + circle (drawn in contrasting color for visibility)
- Red target: green bounding circle + centroid dot
- Movement arrow: cyan line from blue to red showing intended direction
- Top-left panel: phase, iteration, distance, printer position, Markov filter status
- "NO RED DETECTED" warning when target is lost

---

## 8. The 3D Digital Twin

### 8.1 Why a Twin

The 2D camera view doesn't show depth. When the extruder is at Z=10mm moving in Y, the camera sees lateral motion but can't show how far above the bed the nozzle is. A 3D twin gives spatial awareness.

### 8.2 Three.js Scene

The twin renders the printer geometry at `/twin`:

- **Bed**: 220×220mm green surface with 10mm grid
- **Frame**: Two uprights, a top bar, Z-rods, Y-rails — proportioned like the Geeetech A10
- **Gantry**: Moves vertically (printer Z axis)
- **Extruder**: Moves horizontally on the gantry (printer X), with Z-position mapped to forward/backward (printer Y)
- **Blue LEGO marker**: Sits on top of the extruder, with a pulsing blue ring
- **Red target**: Positioned on the bed surface, with a glowing red ring
- **Green laser line**: Drawn from the nozzle tip to the estimated red target position
- **Breadcrumb trail**: Blue dots showing the extruder's path history (last 500 points)
- **PiP camera feed**: Small picture-in-picture of the live annotated stream in the bottom-right corner
- **OrbitControls**: Mouse-drag to rotate, scroll to zoom

### 8.3 Coordinate Mapping

Three.js Y is "up," but printer Y is "forward." The mapping:
```
Three.js X = Printer X     (left-right)
Three.js Y = Printer Z     (height)
Three.js Z = Printer Y     (forward-backward)
```

### 8.4 Dynamic Red Target Estimation

The twin doesn't know the red target's 3D position (the camera gives 2D pixels). We estimate it:

1. Take the current move direction (dx, dy from the controller)
2. Scale by the pixel distance × a mm-per-pixel constant (0.5 mm/px)
3. Add to the current printer position
4. EMA-smooth the result to prevent jitter
5. Clamp to bed bounds

This produces a plausible 3D position that updates in real time as the servo converges.

### 8.5 Bed-Centric Layout

The first twin version had the frame at Z=0 and the bed sliding away — geometrically wrong. We fixed it with a **bed-centric layout**: the bed is fixed at the origin, and all moving parts (gantry, extruder) move relative to it. This matches the physical Geeetech A10 where the bed is on Y-rails and the gantry is on Z-rods.

---

## 9. The Watcher — Hot-Reload for Development

**File**: `scripts/watch_servo.py` (87 lines)

During development, we edited `visual_servo.py` constantly. Manually stopping and restarting was painful. The watcher:

1. Polls the file's mtime every 1 second
2. When it changes, runs `ast.parse()` to check syntax
3. If syntax is valid, kills the old process and starts a new one
4. If the process crashes (any exit code), restarts after 2 seconds

**Key design choice**: After we fixed the iteration counting, the servo exits cleanly after completion (instead of blocking forever). The watcher detects the exit and restarts, creating an automatic retry loop.

---

## 10. Iteration Counting — The Budget Fix

### 10.1 The Problem

The servo has a `MAX_ITERATIONS = 6000` safety limit. Originally, every frame counted — including "No red detected — holding position" frames. In practice, the red target was often occluded for hundreds of frames. A typical run:

- Frames 1–120: Active tracking (red visible, extruder moving)
- Frames 121–6000: "No red detected" — holding position

The system would exhaust its 6000-frame budget while doing nothing useful for 98% of the time.

### 10.2 The Fix

We split the counting:
- `tracking.iteration` — total frame counter (for logging, HUD display)
- `active_iters` — only incremented when red is detected AND a move command is issued

The loop condition uses `active_iters`:
```python
while active_iters < MAX_ITERATIONS:
    ...
    sender.set_move(new_x, new_y)
    active_iters += 1   # only here, after a real move
```

Now the 6000-move budget is spent entirely on actual tracking attempts.

---

## 11. Physical Challenges — What Software Can't Fix

### 11.1 Gantry Occlusion

The biggest unsolved problem. The red LEGO target sits on the bed, but the gantry's metal crossbar runs between the camera and the bed at a certain Y position. As the extruder moves toward the target along Y, the crossbar eventually blocks the camera's line of sight to the red LEGO.

The Markov filter correctly rejects the diminished detections, and the system holds position. But it can't converge because it can't see the target.

**Fix**: Reposition the target to an area of the bed that remains visible throughout the approach, or reposition the camera.

### 11.2 Y-Axis Saturation

The extruder reaches `Y_MAX = 215mm` and can't go further. If the target is near the front edge of the bed, the system saturates — it wants to move but is clamped. Combined with occlusion, this creates a dead zone near Y=215.

### 11.3 Reflections and False Reds

Under certain lighting, the extruder's metal parts produce reddish reflections. The co-movement gate catches these, but they waste frames during rejection and reset cycles.

---

## 12. Files and Sizes

| File | Lines | Purpose |
|------|-------|---------|
| `scripts/visual_servo.py` | 2,381 | Main controller, detection, tracking, visualization, twin |
| `scripts/camera_server.py` | 329 | USB camera MJPEG server |
| `scripts/watch_servo.py` | 87 | Hot-reload watcher |
| `printer_tracker.bat` | 31 | One-click launcher |
| `backend/app.py` | ~900 | REST API (position poll rate increased to 200ms) |
| `backend/main.py` | ~250 | CLI entry point (added API-only mode) |

---

## 13. Commit History

| Commit | Description |
|--------|-------------|
| `8b9edfe` | `feat(backend)`: Increase position poll rate to 200ms, add API-only mode |
| `5983f54` | `feat(camera)`: USB camera MJPEG streaming server |
| `949fc92` | `feat(servo)`: Visual servoing system with browser UI and 3D digital twin |
| `6cdc392` | `feat(servo)`: File-watching auto-restart wrapper |
| `257e547` | `feat(launcher)`: printer_tracker.bat and direct_control.bat |

---

## 14. What We Learned

1. **Separate your concerns into processes.** The camera, backend, and servo being independent made development and debugging drastically easier.

2. **HSV dual-range for red is essential.** Red wraps the hue circle. Missing the second range loses half your detections.

3. **Temporal filtering matters more than per-frame accuracy.** A perfect single-frame detector still fails when reflections co-move with the extruder. The Markov filter with co-movement detection solved our hardest false-positive problem.

4. **Marlin's planner needs feeding, not flooding.** The EMA + adaptive feedrate + 20Hz rate limiting transformed stuttery motion into smooth curves. The key insight: each G1 segment must arrive before the planner finishes the previous one, but not so fast that the buffer overflows.

5. **Don't count idle frames as work.** When your system spends 98% of its time waiting for a target to appear, counting those frames against a budget means the budget is meaningless.

6. **Embed your debugging tools.** The browser visualization wasn't a "nice to have" — it was essential for understanding detection failures, tuning thresholds, and demonstrating the system to others.

7. **Physical constraints dominate.** The cleverest software can't see through a metal crossbar. Camera placement and target positioning matter as much as the detection algorithm.
