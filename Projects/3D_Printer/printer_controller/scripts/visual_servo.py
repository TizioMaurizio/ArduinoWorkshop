"""Visual servo controller — track a red object via camera and move the printer toward it.

Workflow:
  1. Verify printer backend is running and connected
  2. Verify camera server is streaming
  3. Auto-home the printer (G28)
  4. Raise Z to 100 mm (safe clearance)
  5. Move to bed center (110, 110)
  6. Enter tracking loop:
     - Poll a frame from the camera server
     - Detect the red object centroid in the frame
     - Compute XY movement direction to move the extruder toward the red object
     - Send movement commands via the printer REST API
     - Verify direction is correct by checking that the red centroid moves
       toward the expected corner (the extruder position in the frame)
  7. Stop when the red centroid is under the extruder (frame center) or timeout

Usage:
    # First, start the printer backend and camera server:
    #   cd printer_controller && python -m backend.main
    #   python scripts/camera_server.py --camera 0
    # Then run:
    python scripts/visual_servo.py [--camera-url http://127.0.0.1:8766]
                                   [--printer-url http://127.0.0.1:8765]
                                   [--step 5.0] [--timeout 120]
                                   [--save-frames]

Assumptions:
  - Camera is mounted above the bed looking down (bird's-eye approximately)
  - Red object is on the bed, visible in the camera FOV
  - Extruder moves to the RIGHT in camera frame → positive X in printer coords
  - Extruder moves DOWN in camera frame → positive Y in printer coords
  - These axis mappings are calibrated on first run if --calibrate is set
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import math
import os
import socket
import sys
import time
import threading
from collections import deque
from dataclasses import dataclass, field
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

import cv2
import numpy as np
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("visual_servo")

# Persistent HTTP sessions for connection reuse (set up once, used everywhere)
_cam_session: requests.Session | None = None
_printer_session: requests.Session | None = None


def _get_cam_session() -> requests.Session:
    global _cam_session
    if _cam_session is None:
        _cam_session = requests.Session()
    return _cam_session


def _get_printer_session() -> requests.Session:
    global _printer_session
    if _printer_session is None:
        _printer_session = requests.Session()
    return _printer_session

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PRINTER_URL = "http://127.0.0.1:8765"
CAMERA_URL = "http://127.0.0.1:8766"

# Red detection HSV ranges (wraps around 0/180 in OpenCV HSV)
# Range 1: low red (0-10)
RED_LOW1 = np.array([0, 50, 50])
RED_HIGH1 = np.array([10, 255, 255])
# Range 2: high red (165-180)
RED_LOW2 = np.array([165, 50, 50])
RED_HIGH2 = np.array([180, 255, 255])

# Blue detection HSV range (extruder marker)
BLUE_LOW = np.array([95, 80, 50])
BLUE_HIGH = np.array([130, 255, 255])

# Minimum contour area (pixels).
# Initial acquisition requires a large blob; once locked, allow smaller (partial occlusion).
MIN_CONTOUR_AREA = 300           # floor for any detection
MIN_CONTOUR_AREA_ACQUIRE = 1500  # floor to acquire a NEW target (no lock)

# When red centroid is within this many pixels of blue (extruder) marker, we've arrived
ARRIVAL_THRESHOLD_PX = 40

# Movement step size in mm per iteration
STEP_MM = 1.0

# Z height for operation (mm above bed)
OPERATING_Z_MM = 10.0

# Target loop rate (Hz) and derived interval
TARGET_FPS = 30
POLL_INTERVAL_S = 1.0 / TARGET_FPS  # ~33ms

# Maximum tracking iterations before giving up
MAX_ITERATIONS = 6000

# Timeout for HTTP requests (seconds)
HTTP_TIMEOUT_S = 2

# Log every Nth tracking iteration to avoid spam at 30fps
LOG_EVERY_N = 15  # ~every 0.5s

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class RedDetection:
    """Result of red object detection in a single frame."""
    found: bool
    centroid_x: int = 0       # pixel x in frame
    centroid_y: int = 0       # pixel y in frame
    area: float = 0.0         # contour area in pixels
    frame_w: int = 0
    frame_h: int = 0
    mask: np.ndarray | None = None

    @property
    def normalized_x(self) -> float:
        """Centroid X as fraction of frame width, 0=left, 1=right."""
        return self.centroid_x / self.frame_w if self.frame_w > 0 else 0.5

    @property
    def normalized_y(self) -> float:
        """Centroid Y as fraction of frame height, 0=top, 1=bottom."""
        return self.centroid_y / self.frame_h if self.frame_h > 0 else 0.5

    @property
    def offset_from_center_px(self) -> tuple[int, int]:
        """(dx, dy) from frame center in pixels. Positive = right/down."""
        cx = self.frame_w // 2
        cy = self.frame_h // 2
        return (self.centroid_x - cx, self.centroid_y - cy)


@dataclass
class BlueDetection:
    """Result of blue marker (extruder) detection in a single frame."""
    found: bool
    centroid_x: int = 0
    centroid_y: int = 0
    area: float = 0.0
    mask: np.ndarray | None = None


@dataclass
class AxisMapping:
    """Maps camera pixel directions to printer axis directions.

    camera_right_is_printer_x_positive: if True, moving right in camera
        means increasing printer X. If False, it means decreasing.
    camera_down_is_printer_y_positive: same for Y axis.
    """
    cam_right_to_printer_x: float = -1.0   # +1 or -1  (camera-right = printer X-)
    cam_down_to_printer_y: float = 1.0      # +1 or -1


@dataclass
class TrackingState:
    """State across tracking iterations."""
    iteration: int = 0
    detections: list[RedDetection] = field(default_factory=list)
    printer_positions: list[tuple[float, float, float]] = field(default_factory=list)
    converging: bool = True
    last_distance_px: float = float("inf")
    stall_count: int = 0
    phase: str = "INIT"         # INIT, HOMING, RAISING_Z, CENTERING, CALIBRATING, TRACKING, DONE
    printer_x: float = 0.0
    printer_y: float = 0.0
    printer_z: float = 0.0
    move_dx: float = 0.0        # last commanded move in mm
    move_dy: float = 0.0
    distance_history: list[float] = field(default_factory=list)
    status_msg: str = ""
    arrived: bool = False
    # Manual control
    stopped: bool = False       # pause auto-tracking
    manual_queue: list[dict] = field(default_factory=list)  # pending manual commands


# ---------------------------------------------------------------------------
# Visualization server — streams annotated frames over MJPEG
# ---------------------------------------------------------------------------

class _ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    allow_reuse_port = True


class VisualizationServer:
    """Background HTTP server that streams annotated tracking frames.

    Endpoints:
        GET /            HTML page with embedded video + HUD
        GET /stream      MJPEG stream of annotated frames
        GET /raw         MJPEG stream of raw camera (passthrough)
        GET /api/state   JSON snapshot
        GET /api/events  SSE stream — pushes state to all clients in real-time
    """

    def __init__(self, port: int = 8767) -> None:
        self._lock = threading.Lock()
        self._annotated_jpeg: bytes = b""
        self._raw_jpeg: bytes = b""
        self._port = port
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        # SSE: condition variable wakes all waiting /api/events handlers
        self._state_cond = threading.Condition()
        self._state_seq = 0  # incremented on every state change

    def update(self, annotated_frame: np.ndarray, raw_frame: np.ndarray | None = None) -> None:
        """Push new annotated (and optionally raw) frame."""
        _, buf = cv2.imencode(".jpg", annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        annotated_bytes = buf.tobytes()
        raw_bytes = b""
        if raw_frame is not None:
            _, rb = cv2.imencode(".jpg", raw_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            raw_bytes = rb.tobytes()
        with self._lock:
            self._annotated_jpeg = annotated_bytes
            if raw_bytes:
                self._raw_jpeg = raw_bytes
        # Notify SSE clients of new state
        self._notify_state_change()

    def _notify_state_change(self) -> None:
        with self._state_cond:
            self._state_seq += 1
            self._state_cond.notify_all()

    def get_annotated(self) -> bytes:
        with self._lock:
            return self._annotated_jpeg

    def get_raw(self) -> bytes:
        with self._lock:
            return self._raw_jpeg

    def set_tracking(self, tracking: TrackingState) -> None:
        self._tracking = tracking

    def set_printer_url(self, url: str) -> None:
        self._printer_url = url

    def start(self) -> None:
        viz = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt: str, *args: object) -> None:
                pass  # suppress request logs

            def _cors_headers(self) -> None:
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")

            def do_OPTIONS(self) -> None:
                self.send_response(204)
                self._cors_headers()
                self.end_headers()

            def do_GET(self) -> None:
                if self.path == "/":
                    self._serve_page()
                elif self.path == "/twin":
                    self._serve_twin()
                elif self.path == "/stream":
                    self._serve_mjpeg(viz.get_annotated)
                elif self.path == "/raw":
                    self._serve_mjpeg(viz.get_raw)
                elif self.path == "/api/state":
                    self._json_response(viz._get_api_state())
                elif self.path == "/api/events":
                    self._serve_sse()
                elif self.path == "/health":
                    self._json_response({"status": "ok"})
                else:
                    self.send_error(404)

            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length) if length else b"{}"
                try:
                    data = json.loads(body) if body.strip() else {}
                except json.JSONDecodeError:
                    data = {}

                if self.path == "/api/stop":
                    tracking = getattr(viz, "_tracking", None)
                    if tracking:
                        tracking.stopped = not tracking.stopped
                        # Flush printer motion buffer on stop
                        if tracking.stopped:
                            sender = getattr(viz, "_sender", None)
                            if sender:
                                sender.halt()
                            else:
                                url = getattr(viz, "_printer_url", None)
                                if url:
                                    try:
                                        printer_send_gcode(url, "M410")
                                    except Exception:
                                        pass
                        status = "paused" if tracking.stopped else "resumed"
                        logger.info(f"Manual control: {status}")
                        viz._notify_state_change()
                        self._json_response({"status": status, "stopped": tracking.stopped})
                    else:
                        self._json_response({"error": "no tracking"}, 500)

                elif self.path == "/api/jog":
                    dx = float(data.get("x", 0))
                    dy = float(data.get("y", 0))
                    dz = float(data.get("z", 0))
                    tracking = getattr(viz, "_tracking", None)
                    if tracking:
                        tracking.manual_queue.append({"type": "jog", "x": dx, "y": dy, "z": dz})
                        self._json_response({"status": "queued", "x": dx, "y": dy, "z": dz})
                    else:
                        self._json_response({"error": "no tracking"}, 500)

                elif self.path == "/api/gcode":
                    cmd = data.get("command", "").strip()
                    if not cmd:
                        self._json_response({"error": "empty command"}, 400)
                        return
                    url = getattr(viz, "_printer_url", None)
                    if url:
                        try:
                            r = requests.post(f"{url}/gcode", json={"command": cmd}, timeout=5)
                            self._json_response(r.json())
                        except Exception as e:
                            self._json_response({"error": str(e)}, 500)
                    else:
                        self._json_response({"error": "no printer url"}, 500)

                elif self.path == "/api/home":
                    url = getattr(viz, "_printer_url", None)
                    if url:
                        try:
                            r = requests.post(f"{url}/home", timeout=30)
                            self._json_response(r.json())
                        except Exception as e:
                            self._json_response({"error": str(e)}, 500)
                    else:
                        self._json_response({"error": "no printer url"}, 500)

                else:
                    self.send_error(404)

            def _json_response(self, data: dict, code: int = 200) -> None:
                body = json.dumps(data).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self._cors_headers()
                self.end_headers()
                self.wfile.write(body)

            def _serve_page(self) -> None:
                html = VIS_HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(html)))
                self.end_headers()
                self.wfile.write(html)

            def _serve_twin(self) -> None:
                html = TWIN_HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(html)))
                self.end_headers()
                self.wfile.write(html)

            def _serve_mjpeg(self, getter) -> None:
                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self._cors_headers()
                self.end_headers()
                try:
                    while True:
                        jpeg = getter()
                        if not jpeg:
                            time.sleep(0.05)
                            continue
                        self.wfile.write(b"--frame\r\n")
                        self.wfile.write(b"Content-Type: image/jpeg\r\n")
                        self.wfile.write(f"Content-Length: {len(jpeg)}\r\n\r\n".encode())
                        self.wfile.write(jpeg)
                        self.wfile.write(b"\r\n")
                        time.sleep(0.033)  # ~30fps
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass

            def _serve_sse(self) -> None:
                """Server-Sent Events — push state to client whenever it changes."""
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self._cors_headers()
                self.end_headers()
                last_seq = 0
                try:
                    while True:
                        with viz._state_cond:
                            viz._state_cond.wait(timeout=1.0)
                            seq = viz._state_seq
                        if seq != last_seq:
                            last_seq = seq
                            data = json.dumps(viz._get_api_state())
                            self.wfile.write(f"data: {data}\n\n".encode())
                            self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass

        self._server = _ThreadedHTTPServer(("0.0.0.0", self._port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        lan_ip = _get_lan_ip()
        logger.info(f"Visualization server: http://127.0.0.1:{self._port}")
        logger.info(f"  LAN access: http://{lan_ip}:{self._port}")

    def _get_api_state(self) -> dict:
        t = getattr(self, "_tracking", None)
        if not t:
            return {}
        # Latest detection info for 3D twin
        last_det = t.detections[-1] if t.detections else None
        return {
            "phase": t.phase, "iteration": t.iteration,
            "stopped": t.stopped, "arrived": t.arrived,
            "x": t.printer_x, "y": t.printer_y, "z": t.printer_z,
            "dx": t.move_dx, "dy": t.move_dy,
            "status": t.status_msg,
            "distance": t.distance_history[-1] if t.distance_history else None,
            "red_found": last_det.found if last_det else False,
            "red_x": last_det.centroid_x if (last_det and last_det.found) else None,
            "red_y": last_det.centroid_y if (last_det and last_det.found) else None,
            "red_area": last_det.area if (last_det and last_det.found) else None,
        }

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()


def _get_lan_ip() -> str:
    """Best-effort LAN IPv4 address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# HTML page served at /
VIS_HTML = r"""<!DOCTYPE html>
<html>
<head>
<title>Visual Servo - Live Tracking</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #111; color: #eee; font-family: 'Consolas', 'SF Mono', monospace; }
  .container { display: flex; flex-direction: column; height: 100vh; }
  .header { padding: 8px 16px; background: #1a1a2e; border-bottom: 1px solid #333;
            display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
  .header h1 { font-size: 14px; font-weight: 600; color: #0f0; }
  .header .pill { padding: 2px 10px; border-radius: 10px; font-size: 11px;
                  background: #333; color: #aaa; }
  .header .pill.live { background: #900; color: #fff; animation: pulse 1.5s infinite; }
  .header .pill.paused { background: #960; color: #fff; animation: none; }
  @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.5; } }
  .main { flex: 1; display: flex; min-height: 0; }
  .streams { flex: 1; display: flex; flex-direction: column; gap: 2px; padding: 2px; min-height: 0; }
  .stream-box { flex: 1; position: relative; background: #000; overflow: hidden;
                border-radius: 4px; }
  .stream-box img { width: 100%; height: 100%; object-fit: contain; }
  .stream-box .label { position: absolute; top: 6px; left: 8px;
                       font-size: 11px; color: #0f0; background: rgba(0,0,0,0.6);
                       padding: 2px 8px; border-radius: 3px; }
  /* Control panel */
  .controls { width: 260px; background: #1a1a2e; border-left: 1px solid #333;
              padding: 12px; display: flex; flex-direction: column; gap: 12px;
              overflow-y: auto; }
  .ctrl-section { border: 1px solid #333; border-radius: 6px; padding: 10px; }
  .ctrl-section h3 { font-size: 11px; color: #0f0; margin-bottom: 8px;
                     text-transform: uppercase; letter-spacing: 1px; }
  .btn { background: #2a2a4a; border: 1px solid #444; color: #eee; padding: 8px 12px;
         border-radius: 4px; cursor: pointer; font-family: inherit; font-size: 12px;
         transition: background 0.15s; }
  .btn:hover { background: #3a3a5a; }
  .btn:active { background: #4a4a6a; }
  .btn.stop { background: #900; border-color: #c00; }
  .btn.stop:hover { background: #b00; }
  .btn.stop.paused { background: #960; border-color: #cc0; }
  .btn.home { background: #036; border-color: #069; }
  .btn.home:hover { background: #048; }
  .btn-stop-row { display: flex; gap: 6px; }
  .btn-stop-row .btn { flex: 1; text-align: center; font-size: 13px; font-weight: bold; padding: 10px; }
  /* Arrow pad */
  .arrow-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 4px; }
  .arrow-grid .btn { text-align: center; font-size: 16px; padding: 10px 0; }
  .arrow-grid .btn.center { font-size: 11px; }
  .step-row { display: flex; align-items: center; gap: 6px; margin-top: 6px; }
  .step-row label { font-size: 11px; color: #aaa; }
  .step-row input { width: 50px; background: #222; border: 1px solid #444; color: #eee;
                    padding: 4px 6px; border-radius: 3px; font-family: inherit; font-size: 11px;
                    text-align: center; }
  .z-row { display: flex; gap: 4px; margin-top: 4px; }
  .z-row .btn { flex: 1; text-align: center; }
  /* G-code input */
  .gcode-row { display: flex; gap: 4px; }
  .gcode-row input { flex: 1; background: #222; border: 1px solid #444; color: #0f0;
                     padding: 6px 8px; border-radius: 3px; font-family: inherit;
                     font-size: 12px; }
  .gcode-row input::placeholder { color: #555; }
  .gcode-row .btn { padding: 6px 10px; }
  /* Status */
  .status-bar { font-size: 11px; color: #888; padding: 4px 0; }
  .status-bar .pos { color: #0f0; }
  .log { font-size: 10px; color: #666; max-height: 120px; overflow-y: auto;
         background: #0a0a0a; border-radius: 3px; padding: 4px 6px; }
  .log div { padding: 1px 0; border-bottom: 1px solid #1a1a1a; }
  .log .ok { color: #0a0; }
  .log .err { color: #f44; }
  .footer { padding: 6px 16px; background: #1a1a2e; border-top: 1px solid #333;
            font-size: 11px; color: #666; text-align: center; }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>VISUAL SERVO</h1>
    <span class="pill live" id="livePill">LIVE</span>
    <span class="pill" id="phasePill">--</span>
    <span class="pill" id="fps">-- fps</span>
    <span class="pill" id="posPill">X-- Y-- Z--</span>
  </div>
  <div class="main">
    <div class="streams">
      <div class="stream-box">
        <span class="label">ANNOTATED - Tracking Overlay</span>
        <img id="annotated" src="/stream">
      </div>
      <div class="stream-box">
        <span class="label">RAW - Camera Feed</span>
        <img id="raw" src="/raw">
      </div>
    </div>
    <div class="controls">
      <div class="ctrl-section">
        <h3>Control</h3>
        <div class="btn-stop-row">
          <button class="btn stop" id="btnStop" onclick="toggleStop()">STOP</button>
          <button class="btn home" onclick="sendHome()">HOME</button>
        </div>
      </div>
      <div class="ctrl-section">
        <h3>Jog XY</h3>
        <div class="arrow-grid">
          <div></div>
          <button class="btn" onclick="jog(0,-1,0)">&#9650; Y-</button>
          <div></div>
          <button class="btn" onclick="jog(-1,0,0)">&#9664; X-</button>
          <button class="btn center" onclick="jog(0,0,0)">&#8226;</button>
          <button class="btn" onclick="jog(1,0,0)">X+ &#9654;</button>
          <div></div>
          <button class="btn" onclick="jog(0,1,0)">Y+ &#9660;</button>
          <div></div>
        </div>
        <div class="z-row">
          <button class="btn" onclick="jog(0,0,1)">Z &#9650;</button>
          <button class="btn" onclick="jog(0,0,-1)">Z &#9660;</button>
        </div>
        <div class="step-row">
          <label>Step (mm):</label>
          <input type="number" id="stepSize" value="5" min="0.1" max="50" step="0.5">
        </div>
      </div>
      <div class="ctrl-section">
        <h3>G-code</h3>
        <div class="gcode-row">
          <input type="text" id="gcodeInput" placeholder="G1 X100 Y100 F3000"
                 onkeydown="if(event.key==='Enter')sendGcode()">
          <button class="btn" onclick="sendGcode()">&#9654;</button>
        </div>
      </div>
      <div class="ctrl-section">
        <h3>Status</h3>
        <div class="status-bar" id="statusBar">Connecting...</div>
      </div>
      <div class="ctrl-section">
        <h3>Log</h3>
        <div class="log" id="logBox"></div>
      </div>
    </div>
  </div>
  <div class="footer">
    Visual Servo Tracker &mdash; Red object detection + manual control
    &mdash; Keys: <b>WASD</b>=XY  <b>Q/E</b>=Z  <b>Space</b>=Stop  <b>Enter</b>=Send G-code
  </div>
</div>
<script>
const $ = id => document.getElementById(id);
let stopped = false;

function logMsg(msg, cls) {
  const d = document.createElement('div');
  d.textContent = msg;
  if (cls) d.className = cls;
  $('logBox').prepend(d);
  while ($('logBox').children.length > 50) $('logBox').lastChild.remove();
}

async function api(path, data) {
  try {
    const r = await fetch(path, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data||{})});
    const j = await r.json();
    return j;
  } catch(e) { logMsg('ERR: '+e.message, 'err'); return null; }
}

async function toggleStop() {
  const r = await api('/api/stop');
  if (r) {
    stopped = r.stopped;
    $('btnStop').textContent = stopped ? 'RESUME' : 'STOP';
    $('btnStop').classList.toggle('paused', stopped);
    $('livePill').className = stopped ? 'pill paused' : 'pill live';
    $('livePill').textContent = stopped ? 'PAUSED' : 'LIVE';
    logMsg(stopped ? 'Tracking paused' : 'Tracking resumed', 'ok');
  }
}

async function jog(dx, dy, dz) {
  const step = parseFloat($('stepSize').value) || 5;
  const r = await api('/api/jog', {x: dx*step, y: dy*step, z: dz*step});
  if (r && r.status === 'queued') logMsg('Jog: X'+(dx*step>0?'+':'')+(dx*step)+' Y'+(dy*step>0?'+':'')+(dy*step)+' Z'+(dz*step>0?'+':'')+(dz*step), 'ok');
}

async function sendGcode() {
  const cmd = $('gcodeInput').value.trim();
  if (!cmd) return;
  const r = await api('/api/gcode', {command: cmd});
  if (r) { logMsg('> '+cmd + ' -> ' + (r.status||r.error||''), r.error?'err':'ok'); }
  $('gcodeInput').value = '';
}

async function sendHome() {
  logMsg('Homing...', 'ok');
  const r = await api('/api/home');
  if (r) logMsg('Home: ' + (r.status||r.error||''), r.error?'err':'ok');
}

// Keyboard shortcuts
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT') return;
  const step = parseFloat($('stepSize').value) || 5;
  switch(e.key.toLowerCase()) {
    case 'w': jog(0,-1,0); break;
    case 's': jog(0,1,0); break;
    case 'a': jog(-1,0,0); break;
    case 'd': jog(1,0,0); break;
    case 'q': jog(0,0,1); break;
    case 'e': jog(0,0,-1); break;
    case ' ': e.preventDefault(); toggleStop(); break;
    case 'arrowup': e.preventDefault(); jog(0,-1,0); break;
    case 'arrowdown': e.preventDefault(); jog(0,1,0); break;
    case 'arrowleft': e.preventDefault(); jog(-1,0,0); break;
    case 'arrowright': e.preventDefault(); jog(1,0,0); break;
  }
});

// Real-time state sync via Server-Sent Events (all clients see same state instantly)
const evtSource = new EventSource('/api/events');
evtSource.onmessage = (e) => {
  try {
    const s = JSON.parse(e.data);
    $('phasePill').textContent = s.phase || '--';
    $('posPill').textContent = 'X'+((s.x||0).toFixed(1))+' Y'+((s.y||0).toFixed(1))+' Z'+((s.z||0).toFixed(1));
    $('statusBar').innerHTML = '<span class="pos">['+s.phase+']</span> ' + (s.status||'') +
      (s.distance != null ? ' | dist='+s.distance.toFixed(0)+'px' : '') +
      ' | iter='+s.iteration;
    stopped = s.stopped;
    $('btnStop').textContent = stopped ? 'RESUME' : 'STOP';
    $('btnStop').classList.toggle('paused', stopped);
    $('livePill').className = stopped ? 'pill paused' : 'pill live';
    $('livePill').textContent = stopped ? 'PAUSED' : 'LIVE';
  } catch(err) {}
};
evtSource.onerror = () => {
  $('statusBar').textContent = 'SSE disconnected -- reconnecting...';
};

// FPS counter
let frames=0, last=performance.now();
new MutationObserver(()=>{frames++;
  let now=performance.now(); if(now-last>1000){$('fps').textContent=frames+' fps';frames=0;last=now;}
}).observe($('annotated'),{attributes:true});
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# 3D Digital Twin HTML (served at /twin)
# ---------------------------------------------------------------------------
TWIN_HTML = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Digital Twin - 3D Printer</title>
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  body{background:#0a0a0a;overflow:hidden;font-family:'Consolas','SF Mono',monospace;color:#eee}
  canvas{display:block}
  #hud{position:absolute;top:10px;left:10px;pointer-events:none;z-index:10}
  #hud div{background:rgba(0,0,0,0.7);padding:4px 10px;margin-bottom:3px;
           border-radius:4px;font-size:12px;display:inline-block}
  #hud .title{font-size:14px;font-weight:bold;color:#0f0}
  #hud .pos{color:#0df}
  #hud .status{color:#fa0}
  #modePill{padding:4px 14px;border-radius:12px;font-weight:bold;font-size:13px;
            cursor:pointer;pointer-events:auto;transition:all 0.2s;user-select:none}
  #modePill.auto{background:#1a6622;color:#4f4;border:1px solid #4f4}
  #modePill.manual{background:#663300;color:#fa0;border:1px solid #fa0;animation:pulse-manual 1s infinite}
  @keyframes pulse-manual{0%,100%{opacity:1}50%{opacity:0.7}}
  #camFeed{position:absolute;bottom:10px;left:10px;width:260px;border:2px solid #333;
           border-radius:6px;opacity:0.85;transition:width 0.3s,opacity 0.2s;z-index:5}
  #camFeed:hover{opacity:1;width:380px}
  #legend{position:absolute;bottom:10px;left:280px;background:rgba(0,0,0,0.7);
          padding:8px 12px;border-radius:6px;font-size:11px;pointer-events:none;z-index:10}
  #legend span{margin-right:12px}
  .cBlue{color:#4488ff} .cRed{color:#ff4444} .cGreen{color:#44ff44} .cYellow{color:#ffff00}
  /* ── Control panel ──────────────────────────────── */
  #ctrlPanel{position:absolute;top:10px;right:10px;width:180px;z-index:20;
             font-size:11px;user-select:none;
             max-height:calc(100vh - 20px);overflow-y:auto;overflow-x:hidden;
             scrollbar-width:thin;scrollbar-color:#333 transparent}
  #ctrlPanel::-webkit-scrollbar{width:4px}
  #ctrlPanel::-webkit-scrollbar-thumb{background:#444;border-radius:2px}
  #ctrlPanel .section{background:rgba(0,0,0,0.8);border:1px solid #333;
                      border-radius:5px;padding:6px 8px;margin-bottom:4px}
  #ctrlPanel h4{color:#888;font-size:9px;text-transform:uppercase;letter-spacing:1px;margin-bottom:5px}
  .jog-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:2px;margin-bottom:4px}
  .jog-grid button,.ctrl-btn{background:#1a1a2e;border:1px solid #444;color:#ccc;
    padding:5px 0;border-radius:3px;cursor:pointer;font-size:11px;font-family:inherit;transition:all 0.1s}
  .jog-grid button:hover,.ctrl-btn:hover{background:#2a2a4e;border-color:#888;color:#fff}
  .jog-grid button:active,.ctrl-btn:active{background:#3a3a6e;transform:scale(0.95)}
  .jog-grid button.empty{visibility:hidden}
  .z-row{display:flex;gap:2px;margin-bottom:4px}
  .z-row button{flex:1}
  .step-row{display:flex;align-items:center;gap:4px;margin-bottom:3px}
  .step-row label{color:#888;font-size:9px;white-space:nowrap}
  .step-row input{width:48px;background:#111;border:1px solid #444;color:#0df;
    padding:2px 4px;border-radius:3px;font-family:inherit;font-size:11px;text-align:center}
  .step-btns{display:flex;gap:2px}
  .step-btns button{padding:2px 6px;font-size:10px}
  .action-row{display:flex;gap:3px}
  .action-row button{flex:1}
  .btn-home{color:#4af!important;border-color:#4af!important}
  .btn-auto{color:#4f4!important;border-color:#4f4!important}
  .btn-estop{background:#600!important;color:#f44!important;border-color:#f44!important;font-weight:bold}
  .gcode-row{display:flex;gap:2px}
  .gcode-row input{flex:1;background:#111;border:1px solid #444;color:#eee;
    padding:3px 5px;border-radius:3px;font-family:inherit;font-size:10px}
  .gcode-row button{padding:3px 6px}
  #ctrlLog{max-height:48px;overflow-y:auto;font-size:9px;color:#666;margin-top:3px}
  #ctrlLog div{padding:1px 0}
  #ctrlLog .ok{color:#4a4} #ctrlLog .err{color:#f44}
  .keys-hint{color:#555;font-size:8px;text-align:center;margin-top:3px;line-height:1.3}
  /* ── Settings & info ────────────────────────── */
  .toggle-row{display:flex;align-items:center;justify-content:space-between;margin-bottom:3px}
  .toggle-row label{color:#aaa;font-size:10px}
  .toggle{position:relative;width:32px;height:18px;flex-shrink:0}
  .toggle input{opacity:0;width:0;height:0}
  .toggle .slider{position:absolute;inset:0;background:#333;border-radius:10px;cursor:pointer;transition:.2s}
  .toggle .slider::before{content:'';position:absolute;height:12px;width:12px;left:3px;bottom:3px;
    background:#888;border-radius:50%;transition:.2s}
  .toggle input:checked+.slider{background:#1a6622}
  .toggle input:checked+.slider::before{transform:translateX(14px);background:#4f4}
  .info-toggle{color:#4af;font-size:9px;cursor:pointer;text-align:center;padding:3px 0;
    border-top:1px solid #222;margin-top:3px;user-select:none}
  .info-toggle:hover{color:#8cf}
  #controlsInfo{display:none;font-size:9px;line-height:1.5;color:#aaa}
  #controlsInfo.open{display:block}
  #controlsInfo table{width:100%;border-collapse:collapse;margin-top:3px}
  #controlsInfo th{text-align:left;color:#888;font-size:8px;text-transform:uppercase;padding:1px 0;
    border-bottom:1px solid #222}
  #controlsInfo td{padding:1px 0}
  #controlsInfo td:first-child{color:#0df;font-weight:bold;width:38%}
  #controlsInfo .cat{color:#fa0;font-size:8px;text-transform:uppercase;padding-top:4px}
</style>
</head>
<body>
<div id="hud">
  <div class="title">DIGITAL TWIN - Geeetech A10</div>
  <div id="modePill" class="auto" onclick="toggleMode()" title="Click or press Space to toggle">AUTO</div>
  <div class="pos" id="posHud">X-- Y-- Z--</div>
  <div class="status" id="statusHud">Connecting...</div>
  <div id="distHud" style="color:#ff0">--</div>
</div>
<div id="ctrlPanel">
  <div class="section">
    <h4>Jog Controls</h4>
    <div class="jog-grid">
      <button class="empty"></button>
      <button onclick="jog(0,-1,0)" title="Y-">&#9650; Y-</button>
      <button class="empty"></button>
      <button onclick="jog(-1,0,0)" title="X-">&#9664; X-</button>
      <button onclick="jog(0,0,0)" style="font-size:8px;color:#666">&#8226;</button>
      <button onclick="jog(1,0,0)" title="X+">X+ &#9654;</button>
      <button class="empty"></button>
      <button onclick="jog(0,1,0)" title="Y+">Y+ &#9660;</button>
      <button class="empty"></button>
    </div>
    <div class="z-row">
      <button class="ctrl-btn" onclick="jog(0,0,1)" title="Z up">Z &#9650;</button>
      <button class="ctrl-btn" onclick="jog(0,0,-1)" title="Z down">Z &#9660;</button>
    </div>
    <div class="step-row">
      <label>Step:</label>
      <input type="number" id="stepSize" value="5" min="0.1" max="50" step="0.5">
      <span style="color:#888;font-size:10px">mm</span>
    </div>
    <div class="step-btns">
      <button class="ctrl-btn" onclick="setStep(0.1)">0.1</button>
      <button class="ctrl-btn" onclick="setStep(1)">1</button>
      <button class="ctrl-btn" onclick="setStep(5)">5</button>
      <button class="ctrl-btn" onclick="setStep(10)">10</button>
      <button class="ctrl-btn" onclick="setStep(50)">50</button>
    </div>
  </div>
  <div class="section">
    <h4>Actions</h4>
    <div class="action-row" style="margin-bottom:4px">
      <button class="ctrl-btn btn-auto" id="btnMode" onclick="toggleMode()">&#9654; AUTO</button>
      <button class="ctrl-btn btn-home" onclick="sendHome()">&#8962; HOME</button>
    </div>
    <div class="action-row">
      <button class="ctrl-btn btn-estop" onclick="emergencyStop()">&#9724; E-STOP</button>
    </div>
  </div>
  <div class="section">
    <h4>G-code</h4>
    <div class="gcode-row">
      <input type="text" id="gcodeInput" placeholder="G1 X100 F3000"
             onkeydown="if(event.key==='Enter'){sendGcode();event.stopPropagation()}">
      <button class="ctrl-btn" onclick="sendGcode()">&#9654;</button>
    </div>
    <div id="ctrlLog"></div>
  </div>
  <div class="section">
    <h4>Settings</h4>
    <div class="toggle-row">
      <label>Invert X</label>
      <label class="toggle"><input type="checkbox" id="invertX"><span class="slider"></span></label>
    </div>
    <div class="toggle-row">
      <label>Invert Y</label>
      <label class="toggle"><input type="checkbox" id="invertY"><span class="slider"></span></label>
    </div>
    <div class="keys-hint">
      <b>WASD</b>=XY &nbsp;<b>Q/E</b>=Z &nbsp;<b>+/-</b>=Step<br>
      <b>Space</b>=Toggle &nbsp;<b>H</b>=Home<br>
      Any jog key → MANUAL
    </div>
    <div class="info-toggle" id="infoToggle" onclick="toggleInfo()">&#9660; Controls Info</div>
    <div id="controlsInfo">
      <table>
        <tr><td colspan="2" class="cat">Movement</td></tr>
        <tr><td>W / ▲</td><td>Jog Y−</td></tr>
        <tr><td>S / ▼</td><td>Jog Y+</td></tr>
        <tr><td>A / ◀</td><td>Jog X−</td></tr>
        <tr><td>D / ▶</td><td>Jog X+</td></tr>
        <tr><td>Q</td><td>Jog Z up</td></tr>
        <tr><td>E</td><td>Jog Z down</td></tr>
        <tr><td colspan="2" class="cat">Mode</td></tr>
        <tr><td>Space</td><td>Toggle Auto / Manual</td></tr>
        <tr><td>H</td><td>Home all axes</td></tr>
        <tr><td colspan="2" class="cat">Step size</td></tr>
        <tr><td>+ / =</td><td>Increase step</td></tr>
        <tr><td>−</td><td>Decrease step</td></tr>
        <tr><td colspan="2" class="cat">Other</td></tr>
        <tr><td>Enter</td><td>Send G-code (in input)</td></tr>
        <tr><td>Click bed</td><td>Orbit / rotate view</td></tr>
        <tr><td>Scroll</td><td>Zoom in / out</td></tr>
      </table>
    </div>
  </div>
</div>
<img id="camFeed" src="/stream" title="Live annotated feed">
<div id="legend">
  <span class="cBlue">&#9632; Extruder</span>
  <span class="cRed">&#9632; Target</span>
  <span class="cGreen">&#9632; Bed</span>
  <span class="cYellow">&#9632; Camera</span>
</div>
<script type="importmap">
{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.164.1/build/three.module.js","three/addons/":"https://cdn.jsdelivr.net/npm/three@0.164.1/examples/jsm/"}}
</script>
<script type="module">
import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';

// ── Printer dimensions (mm, 1:1 in Three.js units) ─────────────────────
// Geeetech A10: 220x220mm bed, 250mm Z travel
// Coordinate mapping: Three.js X = printer X, Y = up (printer Z), Z = printer Y
const BED=220, BED_T=4, Z_MAX=250;
const FRAME_H=300, UPRIGHT=20, ROD_R=4;
const EXT_W=30, EXT_H=45, EXT_D=30;  // extruder carriage
const LEGO=16, LEGO_H=10;

// ── Scene ───────────────────────────────────────────────────────────────
const scene=new THREE.Scene();
scene.background=new THREE.Color(0x0a0a14);
scene.fog=new THREE.FogExp2(0x0a0a14,0.0006);

const camera=new THREE.PerspectiveCamera(50,innerWidth/innerHeight,1,2000);
camera.position.set(320, 280, 380);

const renderer=new THREE.WebGLRenderer({antialias:true});
renderer.setSize(innerWidth,innerHeight);
renderer.setPixelRatio(Math.min(devicePixelRatio,2));
renderer.shadowMap.enabled=true;
renderer.shadowMap.type=THREE.PCFSoftShadowMap;
document.body.appendChild(renderer.domElement);

const controls=new OrbitControls(camera,renderer.domElement);
controls.target.set(BED/2, 30, BED/2);
controls.enableDamping=true;
controls.dampingFactor=0.08;
controls.minDistance=80;
controls.maxDistance=900;
controls.update();

// ── Lights ──────────────────────────────────────────────────────────────
scene.add(new THREE.AmbientLight(0x404060, 1.2));
const sun=new THREE.DirectionalLight(0xffffff, 1.5);
sun.position.set(200, 400, 150);
sun.castShadow=true;
sun.shadow.mapSize.set(1024, 1024);
sun.shadow.camera.left=-300; sun.shadow.camera.right=300;
sun.shadow.camera.top=300; sun.shadow.camera.bottom=-300;
scene.add(sun);
scene.add(new THREE.PointLight(0x3366ff, 0.4, 600).translateX(-100).translateY(200));

// ── Materials ───────────────────────────────────────────────────────────
const matFrame =new THREE.MeshStandardMaterial({color:0x222228,metalness:0.6,roughness:0.4});
const matBed   =new THREE.MeshStandardMaterial({color:0x1a6622,metalness:0.2,roughness:0.7});
const matExt   =new THREE.MeshStandardMaterial({color:0x888888,metalness:0.5,roughness:0.3});
const matBlue  =new THREE.MeshStandardMaterial({color:0x2266ff,emissive:0x112244,roughness:0.6});
const matRed   =new THREE.MeshStandardMaterial({color:0xff2222,emissive:0x441111,roughness:0.6});
const matRod   =new THREE.MeshStandardMaterial({color:0x999999,metalness:0.8,roughness:0.15});
const matCam   =new THREE.MeshStandardMaterial({color:0xdddd00,emissive:0x333300,roughness:0.5});

function box(w,h,d,mat){const m=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),mat);m.castShadow=m.receiveShadow=true;return m}
function cyl(r,h,mat,s=16){const m=new THREE.Mesh(new THREE.CylinderGeometry(r,r,h,s),mat);m.castShadow=true;return m}

// ── Ground + grid ───────────────────────────────────────────────────────
const ground=new THREE.Mesh(new THREE.PlaneGeometry(1200,1200),
  new THREE.MeshStandardMaterial({color:0x0d0d12,roughness:0.9}));
ground.rotation.x=-Math.PI/2; ground.receiveShadow=true;
scene.add(ground);
const grid=new THREE.GridHelper(600,30,0x222233,0x181822);
grid.position.y=0.1; scene.add(grid);

// ── Bed (fixed at origin, printer XY plane) ─────────────────────────────
// Three.js: bed spans X=[0,220], Z=[0,220], surface at Y=BED_T
const bedMesh=box(BED, BED_T, BED, matBed);
bedMesh.position.set(BED/2, BED_T/2, BED/2);
bedMesh.receiveShadow=true;
scene.add(bedMesh);

// Bed grid lines (10mm spacing)
const gridMat=new THREE.LineBasicMaterial({color:0x225522,transparent:true,opacity:0.25});
for(let i=0;i<=BED;i+=20){
  const lx=new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(i,BED_T+0.2,0),new THREE.Vector3(i,BED_T+0.2,BED)]);
  scene.add(new THREE.Line(lx,gridMat));
  const lz=new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0,BED_T+0.2,i),new THREE.Vector3(BED,BED_T+0.2,i)]);
  scene.add(new THREE.Line(lz,gridMat));
}

// Bed origin marker (0,0 corner)
const originMark=new THREE.AxesHelper(25);
originMark.position.set(0, BED_T+0.5, 0);
scene.add(originMark);

// ── Frame (portal behind the bed, at Z=0) ───────────────────────────────
// Prusa i3 style: vertical frame at the back, bed extends forward
const fOff=-10; // frame z offset (slightly behind bed)
const fLeft=-15, fRight=BED+15; // frame extends beyond bed edges
const upL=box(UPRIGHT,FRAME_H,UPRIGHT,matFrame);
upL.position.set(fLeft, FRAME_H/2, fOff);
scene.add(upL);
const upR=box(UPRIGHT,FRAME_H,UPRIGHT,matFrame);
upR.position.set(fRight, FRAME_H/2, fOff);
scene.add(upR);
const topBar=box(fRight-fLeft+UPRIGHT, UPRIGHT, UPRIGHT, matFrame);
topBar.position.set((fLeft+fRight)/2, FRAME_H, fOff);
scene.add(topBar);
// Base bar
const baseBar=box(fRight-fLeft+UPRIGHT, 8, BED+40, matFrame);
baseBar.position.set((fLeft+fRight)/2, 4, BED/2-10);
scene.add(baseBar);

// Z rods
const zRodL=cyl(ROD_R, FRAME_H-20, matRod);
zRodL.position.set(fLeft+UPRIGHT+6, FRAME_H/2, fOff);
scene.add(zRodL);
const zRodR=cyl(ROD_R, FRAME_H-20, matRod);
zRodR.position.set(fRight-UPRIGHT-6, FRAME_H/2, fOff);
scene.add(zRodR);

// Y-axis rails (along Z, under the bed)
const yRailL=cyl(ROD_R-1, BED+30, matRod);
yRailL.rotation.x=Math.PI/2;
yRailL.position.set(15, 6, BED/2);
scene.add(yRailL);
const yRailR=cyl(ROD_R-1, BED+30, matRod);
yRailR.rotation.x=Math.PI/2;
yRailR.position.set(BED-15, 6, BED/2);
scene.add(yRailR);

// ── Gantry (X crossbar, moves in Y = printer Z) ────────────────────────
const gantryGroup=new THREE.Group();
const xRod1=cyl(ROD_R+1, fRight-fLeft-2*UPRIGHT, matRod);
xRod1.rotation.z=Math.PI/2;
xRod1.position.set((fLeft+fRight)/2, 0, 0);
gantryGroup.add(xRod1);
const xRod2=cyl(ROD_R, fRight-fLeft-2*UPRIGHT, matRod);
xRod2.rotation.z=Math.PI/2;
xRod2.position.set((fLeft+fRight)/2, -15, 10);
gantryGroup.add(xRod2);
// Gantry starts at a default Z height, moves with printer Z
gantryGroup.position.set(0, FRAME_H-20, fOff);
scene.add(gantryGroup);

// ── Extruder (moves on gantry in X, reaches over bed) ──────────────────
const extruderGroup=new THREE.Group();
const ebody=box(EXT_W, EXT_H, EXT_D, matExt);
ebody.position.set(0, -EXT_H/2, EXT_D/2+5);
extruderGroup.add(ebody);
// Nozzle
const nozzle=cyl(2, 12, matRod);
nozzle.position.set(0, -EXT_H-6, EXT_D/2+5);
extruderGroup.add(nozzle);
// Blue LEGO on extruder
const blueMarker=box(LEGO, LEGO_H, LEGO, matBlue);
blueMarker.position.set(0, LEGO_H/2+2, EXT_D/2+5);
extruderGroup.add(blueMarker);
// Glow ring
const blueRing=new THREE.Mesh(
  new THREE.TorusGeometry(LEGO*0.7, 1.5, 8, 24),
  new THREE.MeshBasicMaterial({color:0x4488ff,transparent:true,opacity:0.5})
);
blueRing.rotation.x=Math.PI/2;
blueRing.position.set(0, LEGO_H+4, EXT_D/2+5);
extruderGroup.add(blueRing);
gantryGroup.add(extruderGroup);

// ── Red target (moves on bed based on estimated position) ───────────────
const redTarget=box(LEGO*2, LEGO_H, LEGO*2, matRed);
redTarget.position.set(BED/2, BED_T+LEGO_H/2, BED/2);
scene.add(redTarget);
const redRing=new THREE.Mesh(
  new THREE.TorusGeometry(LEGO*1.5, 1.5, 8, 24),
  new THREE.MeshBasicMaterial({color:0xff4444,transparent:true,opacity:0.4})
);
redRing.rotation.x=Math.PI/2;
redRing.position.set(BED/2, BED_T+LEGO_H+2, BED/2);
scene.add(redRing);

// ── Camera model ────────────────────────────────────────────────────────
const camGroup=new THREE.Group();
camGroup.add(box(20,15,20,matCam));
const lens=cyl(6,10,new THREE.MeshStandardMaterial({color:0x445566,metalness:0.8,roughness:0.2}),12);
lens.rotation.x=Math.PI/2; lens.position.set(0,-2,12);
camGroup.add(lens);
camGroup.position.set(BED+60, FRAME_H+40, BED+80);
camGroup.lookAt(BED/2, 30, BED/2);
scene.add(camGroup);

// ── Laser line (extruder to target) ─────────────────────────────────────
const laserGeo=new THREE.BufferGeometry();
const laserMat=new THREE.LineBasicMaterial({color:0x00ffaa,transparent:true,opacity:0.6});
const laserLine=new THREE.Line(laserGeo,laserMat);
scene.add(laserLine);

// ── Trail (breadcrumb path the extruder has taken) ──────────────────────
const trailPts=[];
const trailGeo=new THREE.BufferGeometry();
const trailMat=new THREE.LineBasicMaterial({color:0x4488ff,transparent:true,opacity:0.3});
const trailLine=new THREE.Line(trailGeo,trailMat);
scene.add(trailLine);
let lastTrailX=-1, lastTrailZ=-1;

// ── State ───────────────────────────────────────────────────────────────
let pState={x:0,y:0,z:10,dx:0,dy:0,phase:'--',status:'',distance:null,
            stopped:false,red_found:false,iteration:0};

// Estimated red target position on bed (mm)
let targetEstX=BED/2, targetEstY=BED/2;
const MM_PER_PX=0.5;  // rough camera-to-mm scale

function updateScene(){
  const t=performance.now()*0.003;

  // ── Gantry height (printer Z -> Three.js Y) ──────────────────────
  // Bed surface at Y=BED_T, gantry above that
  gantryGroup.position.y = BED_T + pState.z + EXT_H + 25;

  // ── Extruder X position ──────────────────────────────────────────
  extruderGroup.position.x = pState.x;

  // ── Extruder Z position (reaches over bed at printer Y) ──────────
  // The extruder reaches out from the frame (at fOff) to printer Y position
  extruderGroup.position.z = pState.y - fOff;

  // ── Red target estimated position ────────────────────────────────
  // When we have move commands, the target is roughly where the extruder
  // is heading. We accumulate with EMA for smooth motion.
  if(pState.red_found && pState.dx !== undefined && pState.dy !== undefined){
    // Target = current position + remaining offset (opposite of move direction)
    // The extruder moves BY (dx,dy) each step TOWARD the target
    // If distance_px is known, estimate total remaining distance
    const distMm = (pState.distance||0) * MM_PER_PX;
    if(distMm > 5){
      // Direction from move commands (normalized)
      const moveMag = Math.sqrt(pState.dx*pState.dx + pState.dy*pState.dy);
      if(moveMag > 0.01){
        const estX = pState.x + (pState.dx/moveMag) * distMm;
        const estY = pState.y + (pState.dy/moveMag) * distMm;
        // EMA smooth
        targetEstX = 0.1*Math.max(0,Math.min(BED,estX)) + 0.9*targetEstX;
        targetEstY = 0.1*Math.max(0,Math.min(BED,estY)) + 0.9*targetEstY;
      }
    } else {
      // Close to target, snap to printer position
      targetEstX = 0.2*pState.x + 0.8*targetEstX;
      targetEstY = 0.2*pState.y + 0.8*targetEstY;
    }
  }
  // Red cube on bed surface: X=targetEstX, Z=targetEstY (printer Y -> Three.js Z)
  redTarget.position.set(targetEstX, BED_T+LEGO_H/2, targetEstY);
  redRing.position.set(targetEstX, BED_T+LEGO_H+2, targetEstY);

  // ── Glow animations ──────────────────────────────────────────────
  blueRing.material.opacity=0.3+0.2*Math.sin(t);
  blueRing.rotation.z=t*0.5;
  if(pState.red_found){
    redRing.material.opacity=0.3+0.3*Math.sin(t*1.5);
    redRing.rotation.z=-t*0.3;
    redTarget.material.emissive.setHex(0x441111);
  } else {
    redRing.material.opacity=0.1;
    redTarget.material.emissive.setHex(0x220808);
  }

  // ── Laser line (nozzle tip to red target) ────────────────────────
  const nozzleTipY = gantryGroup.position.y - EXT_H - 12;
  const nozzleX = extruderGroup.position.x;
  const nozzleZ = gantryGroup.position.z + extruderGroup.position.z;
  const ep=new THREE.Vector3(nozzleX, nozzleTipY, nozzleZ);
  const rp=new THREE.Vector3(targetEstX, BED_T+LEGO_H, targetEstY);
  laserGeo.setFromPoints([ep, rp]);
  laserMat.opacity = pState.red_found ? 0.6 : 0.15;

  // ── Breadcrumb trail ─────────────────────────────────────────────
  if(pState.phase==='TRACKING'){
    const tx=pState.x, tz=pState.y;
    if(Math.abs(tx-lastTrailX)>1 || Math.abs(tz-lastTrailZ)>1){
      trailPts.push(new THREE.Vector3(tx, BED_T+1, tz));
      if(trailPts.length>500) trailPts.shift();
      trailGeo.setFromPoints(trailPts);
      lastTrailX=tx; lastTrailZ=tz;
    }
  }

  // ── HUD ──────────────────────────────────────────────────────────
  document.getElementById('posHud').textContent =
    'X'+pState.x.toFixed(1)+' Y'+pState.y.toFixed(1)+' Z'+pState.z.toFixed(1);
  document.getElementById('statusHud').textContent =
    '['+pState.phase+'] '+(pState.status||'');
  document.getElementById('distHud').textContent =
    pState.distance!=null ? 'Distance: '+pState.distance.toFixed(0)+'px | iter='+pState.iteration : '';

  // ── Mode pill ──────────────────────────────────────────────────────
  const mp=document.getElementById('modePill');
  if(pState.stopped){
    mp.className='manual'; mp.textContent='MANUAL';
    document.getElementById('btnMode').textContent='\u25B6 AUTO';
  } else {
    mp.className='auto'; mp.textContent='AUTO';
    document.getElementById('btnMode').textContent='\u23F8 MANUAL';
  }
}

// ── Control helpers ─────────────────────────────────────────────────────
const $=id=>document.getElementById(id);

function ctrlLog(msg, cls){
  const d=document.createElement('div');
  d.textContent=msg; if(cls)d.className=cls;
  $('ctrlLog').prepend(d);
  while($('ctrlLog').children.length>20)$('ctrlLog').lastChild.remove();
}

async function api(path, data){
  try{
    const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},
                              body:JSON.stringify(data||{})});
    return await r.json();
  }catch(e){ctrlLog('ERR: '+e.message,'err');return null;}
}

// Switch to manual mode: pause auto-tracking
async function switchToManual(){
  if(!pState.stopped){
    const r=await api('/api/stop');
    if(r) pState.stopped=r.stopped;
  }
}

// Switch to auto mode: resume auto-tracking
async function switchToAuto(){
  if(pState.stopped){
    const r=await api('/api/stop');
    if(r) pState.stopped=r.stopped;
    ctrlLog('Resumed auto-tracking','ok');
  }
}

// Toggle between modes
async function toggleMode(){
  if(pState.stopped) await switchToAuto();
  else await switchToManual();
}
// Expose to onclick
window.toggleMode=toggleMode;

// Jog: any jog immediately switches to manual mode
async function jog(dx,dy,dz){
  await switchToManual();
  const step=parseFloat($('stepSize').value)||5;
  const r=await api('/api/jog',{x:dx*step, y:dy*step, z:dz*step});
  if(r&&r.status==='queued'){
    ctrlLog('Jog X'+(dx*step>0?'+':'')+(dx*step)+' Y'+(dy*step>0?'+':'')+(dy*step)+
            ' Z'+(dz*step>0?'+':'')+(dz*step),'ok');
  }
}
window.jog=jog;

function setStep(v){$('stepSize').value=v;}
window.setStep=setStep;

async function sendHome(){
  await switchToManual();
  ctrlLog('Homing...','ok');
  const r=await api('/api/home');
  if(r) ctrlLog('Home: '+(r.status||r.error||''), r.error?'err':'ok');
}
window.sendHome=sendHome;

async function emergencyStop(){
  await switchToManual();
  await api('/api/gcode',{command:'M410'});
  await api('/api/gcode',{command:'M112'});
  ctrlLog('EMERGENCY STOP','err');
}
window.emergencyStop=emergencyStop;

async function sendGcode(){
  const cmd=$('gcodeInput').value.trim();
  if(!cmd)return;
  await switchToManual();
  const r=await api('/api/gcode',{command:cmd});
  if(r) ctrlLog('> '+cmd+' -> '+(r.status||r.error||''), r.error?'err':'ok');
  $('gcodeInput').value='';
}
window.sendGcode=sendGcode;

function toggleInfo(){
  const el=$('controlsInfo'), btn=$('infoToggle');
  el.classList.toggle('open');
  btn.innerHTML=el.classList.contains('open')?'&#9650; Controls Info':'&#9660; Controls Info';
}
window.toggleInfo=toggleInfo;

// Step size presets
const STEPS=[0.1, 0.5, 1, 5, 10, 50];
function stepChange(delta){
  const cur=parseFloat($('stepSize').value)||5;
  let idx=STEPS.findIndex(s=>s>=cur);
  if(idx<0)idx=STEPS.length-1;
  idx=Math.max(0,Math.min(STEPS.length-1, idx+delta));
  $('stepSize').value=STEPS[idx];
}

// ── Keyboard ────────────────────────────────────────────────────────────
document.addEventListener('keydown',(e)=>{
  // Skip if typing in input
  if(e.target.tagName==='INPUT'||e.target.tagName==='TEXTAREA')return;

  const ix=$('invertX')&&$('invertX').checked?-1:1;
  const iy=$('invertY')&&$('invertY').checked?-1:1;
  switch(e.key.toLowerCase()){
    case 'w': jog(0,-1*iy,0); e.preventDefault(); break;
    case 's': jog(0,1*iy,0); e.preventDefault(); break;
    case 'a': jog(-1*ix,0,0); e.preventDefault(); break;
    case 'd': jog(1*ix,0,0); e.preventDefault(); break;
    case 'q': jog(0,0,1); e.preventDefault(); break;
    case 'e': jog(0,0,-1); e.preventDefault(); break;
    case 'h': sendHome(); e.preventDefault(); break;
    case ' ': toggleMode(); e.preventDefault(); break;
    case '+': case '=': stepChange(1); e.preventDefault(); break;
    case '-': stepChange(-1); e.preventDefault(); break;
    case 'arrowup': jog(0,-1*iy,0); e.preventDefault(); break;
    case 'arrowdown': jog(0,1*iy,0); e.preventDefault(); break;
    case 'arrowleft': jog(-1*ix,0,0); e.preventDefault(); break;
    case 'arrowright': jog(1*ix,0,0); e.preventDefault(); break;
  }
});

// ── SSE ─────────────────────────────────────────────────────────────────
const evtSource=new EventSource('/api/events');
evtSource.onmessage=(e)=>{
  try{
    const s=JSON.parse(e.data);
    pState.x=s.x||0; pState.y=s.y||0; pState.z=s.z||10;
    pState.dx=s.dx||0; pState.dy=s.dy||0;
    pState.phase=s.phase||'--';
    pState.status=s.status||'';
    pState.distance=s.distance;
    pState.stopped=s.stopped;
    pState.red_found=s.red_found||false;
    pState.iteration=s.iteration||0;
  }catch(err){}
};
evtSource.onerror=()=>{
  document.getElementById('statusHud').textContent='SSE disconnected...';
};

// ── Resize ──────────────────────────────────────────────────────────────
window.addEventListener('resize',()=>{
  camera.aspect=innerWidth/innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth,innerHeight);
});

// ── Render loop ─────────────────────────────────────────────────────────
function animate(){
  requestAnimationFrame(animate);
  controls.update();
  updateScene();
  renderer.render(scene,camera);
}
animate();
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Camera client
# ---------------------------------------------------------------------------

def fetch_frame(camera_url: str) -> np.ndarray | None:
    """Fetch a single JPEG frame from the camera server and decode it."""
    try:
        resp = _get_cam_session().get(f"{camera_url}/frame", timeout=HTTP_TIMEOUT_S)
        if resp.status_code != 200:
            logger.warning(f"Camera returned {resp.status_code}")
            return None
        arr = np.frombuffer(resp.content, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return frame
    except requests.RequestException as e:
        logger.error(f"Camera fetch failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Temporal consistency filter (Markov)
# ---------------------------------------------------------------------------

class RedTracker:
    """Markov-style temporal filter for red detections.

    Maintains a state model of the red target's position, velocity, and area.
    Rejects detections that are inconsistent with the tracked state:
      1. Area consistency — reject if area drops below 40% of running median
      2. Co-movement — if red-blue offset is frozen, red is on the extruder
      3. Position prediction — reject if detection deviates from predicted position
    """

    WINDOW = 15             # frames of history
    AREA_DROP_RATIO = 0.35  # reject if area < 35% of median
    COMOVEMENT_FRAMES = 20  # frames to detect co-movement
    COMOVEMENT_PX = 8.0     # if offset std-dev < this, flag co-movement
    GATE_PX = 150.0         # max deviation from predicted position

    def __init__(self) -> None:
        self.positions: deque[tuple[int, int]] = deque(maxlen=self.WINDOW)
        self.areas: deque[float] = deque(maxlen=self.WINDOW)
        self.offsets: deque[tuple[int, int]] = deque(maxlen=self.COMOVEMENT_FRAMES)
        self.vx: float = 0.0
        self.vy: float = 0.0
        self._comovement_flagged: bool = False

    @property
    def has_history(self) -> bool:
        return len(self.positions) >= 3

    @property
    def comovement_flagged(self) -> bool:
        return self._comovement_flagged

    def predict(self) -> tuple[float, float] | None:
        """Predict next position from recent velocity."""
        if not self.positions:
            return None
        lx, ly = self.positions[-1]
        return lx + self.vx, ly + self.vy

    def _update_velocity(self, cx: int, cy: int) -> None:
        if len(self.positions) >= 2:
            px, py = self.positions[-1]
            alpha = 0.4  # EMA smoothing
            self.vx = alpha * (cx - px) + (1 - alpha) * self.vx
            self.vy = alpha * (cy - py) + (1 - alpha) * self.vy

    def _median_area(self) -> float:
        if not self.areas:
            return 0.0
        s = sorted(self.areas)
        n = len(s)
        return s[n // 2]

    def validate(self, det: RedDetection,
                 blue: BlueDetection | None = None) -> tuple[bool, str]:
        """Check if a detection is temporally consistent.

        Returns (accept, reason) — reason explains rejection.
        """
        if not det.found:
            return False, "not_found"

        cx, cy, area = det.centroid_x, det.centroid_y, det.area

        # --- Area consistency ---
        if self.has_history:
            med = self._median_area()
            if med > 0 and area < med * self.AREA_DROP_RATIO:
                return False, f"area_drop({area:.0f}<{med*self.AREA_DROP_RATIO:.0f})"

        # --- Position gate (Mahalanobis-lite) ---
        pred = self.predict()
        if pred is not None:
            px, py = pred
            dev = math.sqrt((cx - px) ** 2 + (cy - py) ** 2)
            if dev > self.GATE_PX:
                return False, f"position_gate({dev:.0f}>{self.GATE_PX:.0f})"

        # --- Co-movement with blue ---
        if blue is not None and blue.found and len(self.offsets) >= self.COMOVEMENT_FRAMES:
            ox_arr = [o[0] for o in self.offsets]
            oy_arr = [o[1] for o in self.offsets]
            std_x = np.std(ox_arr)
            std_y = np.std(oy_arr)
            if std_x < self.COMOVEMENT_PX and std_y < self.COMOVEMENT_PX:
                self._comovement_flagged = True
                return False, f"comovement(std_x={std_x:.1f},std_y={std_y:.1f})"
            else:
                self._comovement_flagged = False

        return True, "ok"

    def update(self, det: RedDetection,
               blue: BlueDetection | None = None) -> None:
        """Record an accepted detection into the state model."""
        cx, cy = det.centroid_x, det.centroid_y
        self._update_velocity(cx, cy)
        self.positions.append((cx, cy))
        self.areas.append(det.area)
        if blue is not None and blue.found:
            self.offsets.append((det.centroid_x - blue.centroid_x,
                                det.centroid_y - blue.centroid_y))

    def reset(self) -> None:
        """Clear all state — forces re-acquisition."""
        self.positions.clear()
        self.areas.clear()
        self.offsets.clear()
        self.vx = self.vy = 0.0
        self._comovement_flagged = False


# Maximum pixel jump between frames to accept as same target
TARGET_LOCK_RADIUS_PX = 200


def detect_red(frame: np.ndarray,
               last_cx: int | None = None,
               last_cy: int | None = None) -> RedDetection:
    """Detect a red region in a BGR frame.

    If last_cx/last_cy are given (target lock), prefer contours near the
    locked position, weighted by area so larger blobs win over tiny noise.
    Reject detections that jump more than TARGET_LOCK_RADIUS_PX.
    """
    h, w = frame.shape[:2]

    # Convert to HSV
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # Red wraps around HSV hue, so combine two ranges
    mask1 = cv2.inRange(hsv, RED_LOW1, RED_HIGH1)
    mask2 = cv2.inRange(hsv, RED_LOW2, RED_HIGH2)
    mask = cv2.bitwise_or(mask1, mask2)

    # Morphological cleanup
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    # Find contours
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return RedDetection(found=False, frame_w=w, frame_h=h, mask=mask)

    # Filter by minimum area — use stricter threshold when acquiring new target
    area_thresh = MIN_CONTOUR_AREA if (last_cx is not None) else MIN_CONTOUR_AREA_ACQUIRE
    valid = [(c, cv2.contourArea(c)) for c in contours if cv2.contourArea(c) >= area_thresh]
    if not valid:
        return RedDetection(found=False, frame_w=w, frame_h=h, mask=mask)

    # Pick best contour: closest to last known position if locked, else largest
    best_contour = None
    best_area = 0.0
    best_cx, best_cy = 0, 0

    if last_cx is not None and last_cy is not None:
        # Target-lock mode: score = area / (distance + 1)
        # Favours large contours near the locked position
        best_score = -1.0
        best_dist = float("inf")
        for c, area in valid:
            M = cv2.moments(c)
            if M["m00"] == 0:
                continue
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            d = math.sqrt((cx - last_cx) ** 2 + (cy - last_cy) ** 2)
            if d > TARGET_LOCK_RADIUS_PX:
                continue
            score = area / (d + 1.0)
            if score > best_score:
                best_score = score
                best_dist = d
                best_contour, best_area = c, area
                best_cx, best_cy = cx, cy
    else:
        # No lock — pick largest contour
        largest_c, largest_a = max(valid, key=lambda x: x[1])
        M = cv2.moments(largest_c)
        if M["m00"] == 0:
            return RedDetection(found=False, frame_w=w, frame_h=h, mask=mask)
        best_contour, best_area = largest_c, largest_a
        best_cx = int(M["m10"] / M["m00"])
        best_cy = int(M["m01"] / M["m00"])

    if best_contour is None:
        return RedDetection(found=False, frame_w=w, frame_h=h, mask=mask)

    return RedDetection(
        found=True,
        centroid_x=best_cx,
        centroid_y=best_cy,
        area=best_area,
        frame_w=w,
        frame_h=h,
        mask=mask,
    )


def detect_blue(frame: np.ndarray) -> BlueDetection:
    """Detect the blue extruder marker in a BGR frame. Returns largest blue contour."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, BLUE_LOW, BLUE_HIGH)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return BlueDetection(found=False, mask=mask)

    valid = [(c, cv2.contourArea(c)) for c in contours if cv2.contourArea(c) >= MIN_CONTOUR_AREA]
    if not valid:
        return BlueDetection(found=False, mask=mask)

    largest_c, largest_a = max(valid, key=lambda x: x[1])
    M = cv2.moments(largest_c)
    if M["m00"] == 0:
        return BlueDetection(found=False, mask=mask)

    cx = int(M["m10"] / M["m00"])
    cy = int(M["m01"] / M["m00"])
    return BlueDetection(found=True, centroid_x=cx, centroid_y=cy, area=largest_a, mask=mask)


# ---------------------------------------------------------------------------
# Printer client
# ---------------------------------------------------------------------------

def printer_health(url: str) -> bool:
    try:
        r = requests.get(f"{url}/health", timeout=HTTP_TIMEOUT_S)
        return r.status_code == 200 and r.json().get("status") == "ok"
    except Exception:
        return False


def printer_state(url: str) -> dict:
    r = _get_printer_session().get(f"{url}/state", timeout=HTTP_TIMEOUT_S)
    r.raise_for_status()
    return r.json()


def printer_home(url: str) -> None:
    logger.info("Homing all axes (G28)...")
    r = _get_printer_session().post(f"{url}/home", timeout=30)
    r.raise_for_status()
    logger.info(f"Home command sent: {r.json()}")


def printer_send_gcode(url: str, cmd: str) -> dict:
    r = _get_printer_session().post(f"{url}/gcode", json={"command": cmd}, timeout=HTTP_TIMEOUT_S)
    r.raise_for_status()
    return r.json()


def printer_jog(url: str, axis: str, distance_mm: float, feedrate: int | None = None) -> dict:
    payload: dict = {"axis": axis, "distance_mm": distance_mm}
    if feedrate is not None:
        payload["feedrate"] = feedrate
    r = requests.post(f"{url}/jog", json=payload, timeout=HTTP_TIMEOUT_S)
    r.raise_for_status()
    return r.json()


def printer_move_absolute(url: str, x: float | None = None, y: float | None = None,
                          z: float | None = None, feedrate: int = 6000) -> None:
    """Send absolute move via raw G-code.  Assumes G90 is already active."""
    parts = []
    if x is not None:
        parts.append(f"X{x:.2f}")
    if y is not None:
        parts.append(f"Y{y:.2f}")
    if z is not None:
        parts.append(f"Z{z:.2f}")
    if not parts:
        return
    cmd = f"G1 {' '.join(parts)} F{feedrate}"
    result = printer_send_gcode(url, cmd)
    if "error" in result:
        logger.warning(f"Move rejected: {result['error']}")


def wait_for_move(url: str, target_x: float, target_y: float, target_z: float,
                  tolerance: float = 2.0, timeout: float = 15.0) -> bool:
    """Poll printer state until position is within tolerance or timeout."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = printer_state(url)
        dx = abs(s.get("x", 0) - target_x)
        dy = abs(s.get("y", 0) - target_y)
        dz = abs(s.get("z", 0) - target_z)
        if dx < tolerance and dy < tolerance and dz < tolerance:
            return True
        time.sleep(0.3)
    return False


class PrinterSender:
    """Background thread that sends only the LATEST move command to the printer.

    The tracking loop calls `set_move()` every frame.  This class discards
    all intermediate commands and only sends the most recent one.  This
    prevents Marlin's command buffer from filling up with stale moves and
    ensures the printer always heads toward the latest target.

    Smooth-motion strategy:
    - EMA trajectory filter smooths the target position.
    - 20 Hz command rate keeps Marlin's 16-slot planner buffer fed so the
      look-ahead algorithm can produce smooth acceleration profiles.
    - Adaptive feedrate: each segment's speed is set so it takes ~50 ms to
      execute, matching the send cadence.  This prevents buffer underruns
      (stutter) and overruns (ignored commands).
    """

    SEND_INTERVAL_S = 0.050  # 20 Hz command rate → 50 ms between G1s
    EMA_ALPHA = 0.25         # gentle smoothing (0 = frozen, 1 = raw)
    MIN_FEEDRATE = 300       # mm/min floor (5 mm/s) — prevents stalls
    MAX_FEEDRATE = 2000      # mm/min cap (33 mm/s) — keeps motion gentle
    MIN_SEGMENT_MM = 0.05    # skip segments shorter than this

    def __init__(self, url: str) -> None:
        self._url = url
        self._lock = threading.Lock()
        self._target_x: float | None = None
        self._target_y: float | None = None
        self._smooth_x: float | None = None
        self._smooth_y: float | None = None
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def set_move(self, x: float, y: float, feedrate: int = 2000) -> None:
        """Set the latest desired position; EMA smoothing is applied in the sender thread."""
        with self._lock:
            self._target_x = x
            self._target_y = y

    def halt(self) -> None:
        """Clear pending command and send M410 quickstop to flush Marlin buffer."""
        with self._lock:
            self._target_x = None
            self._target_y = None
            self._smooth_x = None
            self._smooth_y = None
        try:
            printer_send_gcode(self._url, "M410")
        except Exception:
            pass

    def _run(self) -> None:
        while self._running:
            with self._lock:
                tx, ty = self._target_x, self._target_y
            if tx is not None and ty is not None:
                # EMA smooth toward target
                a = self.EMA_ALPHA
                feedrate = self.MAX_FEEDRATE  # default for first segment
                if self._smooth_x is None:
                    self._smooth_x, self._smooth_y = tx, ty
                else:
                    prev_x, prev_y = self._smooth_x, self._smooth_y
                    self._smooth_x = a * tx + (1 - a) * prev_x
                    self._smooth_y = a * ty + (1 - a) * prev_y

                    # Adaptive feedrate: aim for each segment to take ~50ms
                    seg_mm = math.sqrt((self._smooth_x - prev_x) ** 2 +
                                       (self._smooth_y - prev_y) ** 2)
                    if seg_mm < self.MIN_SEGMENT_MM:
                        # Segment too short — skip to avoid planner churn
                        time.sleep(self.SEND_INTERVAL_S)
                        continue
                    # feedrate (mm/min) = distance / time * 60
                    feedrate = int(min(self.MAX_FEEDRATE,
                                       max(self.MIN_FEEDRATE,
                                           seg_mm / self.SEND_INTERVAL_S * 60)))

                cmd = f"G1 X{self._smooth_x:.2f} Y{self._smooth_y:.2f} F{feedrate}"
                try:
                    printer_send_gcode(self._url, cmd)
                except Exception as e:
                    logger.warning(f"Printer send failed: {e}")
                time.sleep(self.SEND_INTERVAL_S)
            else:
                time.sleep(0.005)  # avoid busy-wait when idle

    def stop(self) -> None:
        self._running = False
        self._thread.join(timeout=2.0)


# ---------------------------------------------------------------------------
# Axis calibration (optional)
# ---------------------------------------------------------------------------

def calibrate_axes(printer_url: str, camera_url: str) -> AxisMapping:
    """Move the printer a small amount and observe camera change to determine axis mapping.

    Methodology:
    1. Capture baseline frame, detect red centroid
    2. Jog printer +10mm in X
    3. Capture frame, detect red — see which direction the background moved
       (red should appear to shift opposite to extruder movement if camera is
       mounted on the extruder, or same direction if camera is fixed)
    4. Repeat for Y
    5. Return mapping

    For a fixed overhead camera watching the bed:
    - Printer X+ moves extruder RIGHT → extruder moves right in frame
    - We want the extruder to cover the red object
    - So if red is to the RIGHT of center, we need to move printer X+
    """
    logger.info("Calibrating axis mapping...")
    mapping = AxisMapping()

    # Capture baseline
    time.sleep(0.5)
    frame1 = fetch_frame(camera_url)
    if frame1 is None:
        logger.warning("Cannot calibrate — no camera frame. Using defaults.")
        return mapping

    det1 = detect_red(frame1)

    # Jog +10 X
    printer_jog(printer_url, "X", 10.0)
    time.sleep(2.0)  # wait for move

    frame2 = fetch_frame(camera_url)
    if frame2 is not None:
        det2 = detect_red(frame2)
        if det1.found and det2.found:
            dx_px = det2.centroid_x - det1.centroid_x
            # If red moved LEFT (dx_px < 0), the extruder moved RIGHT relative to red
            # which is correct for printer X+. The extruder should chase red.
            # For fixed camera: extruder moves right, red appears to stay, image shifts
            # For our purpose: if we move printer +X and red moves LEFT in frame,
            # then to move extruder TOWARD red-on-the-right, we need +X
            # So cam_right_to_printer_x = +1 if moving +X made red shift left (extruder moved right)
            if abs(dx_px) > 5:
                # If red shifted left (dx_px < 0), printer +X = camera right
                mapping.cam_right_to_printer_x = 1.0 if dx_px < 0 else -1.0
                logger.info(f"X calibration: red shifted {dx_px}px → "
                            f"cam_right = printer {'X+' if mapping.cam_right_to_printer_x > 0 else 'X-'}")
            else:
                logger.info(f"X calibration: red shift too small ({dx_px}px), using default")

    # Return to center and jog +10 Y
    printer_jog(printer_url, "X", -10.0)
    time.sleep(2.0)

    frame3 = fetch_frame(camera_url)
    det3 = detect_red(frame3) if frame3 is not None else None

    printer_jog(printer_url, "Y", 10.0)
    time.sleep(2.0)

    frame4 = fetch_frame(camera_url)
    if frame4 is not None and det3 is not None and det3.found:
        det4 = detect_red(frame4)
        if det4.found:
            dy_px = det4.centroid_y - det3.centroid_y
            if abs(dy_px) > 5:
                mapping.cam_down_to_printer_y = 1.0 if dy_px < 0 else -1.0
                logger.info(f"Y calibration: red shifted {dy_px}px → "
                            f"cam_down = printer {'Y+' if mapping.cam_down_to_printer_y > 0 else 'Y-'}")
            else:
                logger.info(f"Y calibration: red shift too small ({dy_px}px), using default")

    # Return Y
    printer_jog(printer_url, "Y", -10.0)
    time.sleep(1.0)

    logger.info(f"Axis mapping: cam_right→printer_x={mapping.cam_right_to_printer_x:+.0f}, "
                f"cam_down→printer_y={mapping.cam_down_to_printer_y:+.0f}")
    return mapping

# ---------------------------------------------------------------------------
# Visual servo loop
# ---------------------------------------------------------------------------

def compute_movement(det: RedDetection, mapping: AxisMapping,
                     step_mm: float,
                     ref_x: int | None = None,
                     ref_y: int | None = None) -> tuple[float, float]:
    """Compute printer XY movement to bring extruder toward the red object.

    If ref_x/ref_y are given (blue marker position), the offset is computed
    from that reference point.  Otherwise falls back to frame center.

    Returns (dx_mm, dy_mm) in printer coordinates.
    """
    if ref_x is not None and ref_y is not None:
        dx_px = det.centroid_x - ref_x
        dy_px = det.centroid_y - ref_y
    else:
        dx_px, dy_px = det.offset_from_center_px
    dist_px = math.sqrt(dx_px ** 2 + dy_px ** 2)

    if dist_px < 1:
        return 0.0, 0.0

    # Proportional look-ahead: smooth ramp — max 2× step_mm even at large offsets
    scale = min(2.0, dist_px / 100.0)
    # Fine approach: extra reduction below arrival threshold
    if dist_px < 60:
        scale *= dist_px / 60.0
    move_px_x = (dx_px / dist_px) * scale
    move_px_y = (dy_px / dist_px) * scale

    # Map camera pixel directions to printer axes
    printer_dx = move_px_x * mapping.cam_right_to_printer_x * step_mm
    printer_dy = move_px_y * mapping.cam_down_to_printer_y * step_mm

    return printer_dx, printer_dy


def annotate_frame(frame: np.ndarray, det: RedDetection,
                   tracking: TrackingState, mapping: AxisMapping | None = None,
                   blue: BlueDetection | None = None,
                   markov_reason: str = "") -> np.ndarray:
    """Draw full tracking visualization on a frame.

    Layers drawn:
      1. Semi-transparent red mask overlay (shows what the detector sees)
      2. Largest contour outline (green)
      3. Blue marker (extruder) + crosshair + arrival zone around it
      4. Direction arrow from blue marker to red centroid
      5. Movement command arrow (printer coords)
      6. Top HUD: phase, iteration, distance, area
      7. Right HUD: printer position, axis mapping
      8. Bottom: distance history sparkline
    """
    out = frame.copy()
    h, w = out.shape[:2]

    # Reference point: blue marker if detected, else frame center
    if blue is not None and blue.found:
        rx, ry = blue.centroid_x, blue.centroid_y
    else:
        rx, ry = w // 2, h // 2

    # ── 1. Red mask overlay ────────────────────────────────────────────
    if det.mask is not None:
        red_overlay = np.zeros_like(out)
        red_overlay[:, :, 2] = det.mask  # red channel
        cv2.addWeighted(red_overlay, 0.25, out, 1.0, 0, out)

    # ── 1b. Blue mask overlay ──────────────────────────────────────────
    BLUE_VIZ = (0, 255, 255)  # bright yellow in BGR — high contrast
    if blue is not None and blue.mask is not None:
        blue_overlay = np.zeros_like(out)
        blue_overlay[:, :, 0] = blue.mask  # blue channel
        cv2.addWeighted(blue_overlay, 0.25, out, 1.0, 0, out)
        # Draw blue contour outline
        b_contours, _ = cv2.findContours(blue.mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if b_contours:
            b_largest = max(b_contours, key=cv2.contourArea)
            cv2.drawContours(out, [b_largest], -1, BLUE_VIZ, 3)
            bx, by, bw, bh = cv2.boundingRect(b_largest)
            cv2.rectangle(out, (bx, by), (bx + bw, by + bh), BLUE_VIZ, 2)

    # ── 2. Contour outline ─────────────────────────────────────────────
    if det.found and det.mask is not None:
        contours, _ = cv2.findContours(det.mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            largest = max(contours, key=cv2.contourArea)
            cv2.drawContours(out, [largest], -1, (0, 255, 0), 2)
            bx, by, bw, bh = cv2.boundingRect(largest)
            cv2.rectangle(out, (bx, by), (bx + bw, by + bh), (0, 200, 0), 1)

    # ── 3. Blue marker (extruder) + crosshair ──────────────────────────
    if blue is not None and blue.found:
        # Bright yellow crosshair — highly visible
        cv2.circle(out, (rx, ry), 16, BLUE_VIZ, 3)
        cv2.circle(out, (rx, ry), 4, BLUE_VIZ, -1)
        cross_size = 28
        cv2.line(out, (rx - cross_size, ry), (rx + cross_size, ry), BLUE_VIZ, 3)
        cv2.line(out, (rx, ry - cross_size), (rx, ry + cross_size), BLUE_VIZ, 3)
        # Label with dark background for readability
        label = "EXTRUDER"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        lx, ly = rx + 20, ry - 20
        cv2.rectangle(out, (lx - 2, ly - th - 4), (lx + tw + 2, ly + 4), (0, 0, 0), -1)
        cv2.putText(out, label, (lx, ly),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, BLUE_VIZ, 2, cv2.LINE_AA)
    else:
        # Fallback: frame center crosshair (gray, dimmed)
        fcx, fcy = w // 2, h // 2
        cross_size = 25
        cv2.line(out, (fcx - cross_size, fcy), (fcx + cross_size, fcy), (100, 100, 100), 1)
        cv2.line(out, (fcx, fcy - cross_size), (fcx, fcy + cross_size), (100, 100, 100), 1)
        cv2.putText(out, "BLUE NOT FOUND", (fcx - 60, fcy + 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 100, 255), 1, cv2.LINE_AA)

    # Arrival zone circle around reference point
    cv2.circle(out, (rx, ry), ARRIVAL_THRESHOLD_PX, (0, 255, 0), 1, cv2.LINE_AA)
    cv2.putText(out, "arrival zone", (rx + ARRIVAL_THRESHOLD_PX + 4, ry + 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 180, 0), 1, cv2.LINE_AA)

    if det.found:
        # ── 4. Centroid + direction line ───────────────────────────────
        cv2.circle(out, (det.centroid_x, det.centroid_y), 8, (0, 0, 255), -1)
        cv2.circle(out, (det.centroid_x, det.centroid_y), 8, (255, 255, 255), 1)
        # Direction line from blue marker (or center) to red centroid
        cv2.line(out, (rx, ry), (det.centroid_x, det.centroid_y), (0, 255, 255), 2, cv2.LINE_AA)

        # ── 5. Movement arrow ──────────────────────────────────────────
        if abs(tracking.move_dx) > 0.01 or abs(tracking.move_dy) > 0.01:
            arrow_scale = 6.0
            ax = int(rx + tracking.move_dx * arrow_scale)
            ay = int(ry + tracking.move_dy * arrow_scale)
            ax = max(10, min(w - 10, ax))
            ay = max(10, min(h - 10, ay))
            cv2.arrowedLine(out, (rx, ry), (ax, ay), (255, 0, 255), 3, cv2.LINE_AA, tipLength=0.3)
            cv2.putText(out, f"cmd: dX={tracking.move_dx:+.1f} dY={tracking.move_dy:+.1f}mm",
                        (ax + 5, ay), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 255), 1, cv2.LINE_AA)

        # Distance label on the direction line
        dx_px = det.centroid_x - rx
        dy_px = det.centroid_y - ry
        dist_px = math.sqrt(dx_px ** 2 + dy_px ** 2)
        mid_x = (rx + det.centroid_x) // 2
        mid_y = (ry + det.centroid_y) // 2
        cv2.putText(out, f"{dist_px:.0f}px", (mid_x + 5, mid_y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1, cv2.LINE_AA)
    else:
        cv2.putText(out, "NO RED DETECTED", (rx - 90, ry + 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA)

    # ── 6. Top HUD panel ───────────────────────────────────────────────
    _draw_hud_panel(out, tracking, det, markov_reason=markov_reason)

    # ── 7. Right HUD — printer position ────────────────────────────────
    _draw_printer_hud(out, tracking, mapping)

    # ── 8. Bottom sparkline — distance history ─────────────────────────
    _draw_distance_sparkline(out, tracking)

    return out


def _draw_hud_panel(out: np.ndarray, tracking: TrackingState, det: RedDetection,
                    markov_reason: str = "") -> None:
    """Top-left HUD with phase, iteration, distance, area."""
    h, w = out.shape[:2]
    # Semi-transparent background
    overlay = out.copy()
    cv2.rectangle(overlay, (0, 0), (280, 110), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, out, 0.4, 0, out)

    y0 = 18
    line_h = 20
    font = cv2.FONT_HERSHEY_SIMPLEX
    fs = 0.45
    thick = 1

    # Phase
    phase_colors = {
        "INIT": (150, 150, 150), "HOMING": (0, 200, 255), "RAISING_Z": (0, 200, 255),
        "CENTERING": (0, 200, 255), "CALIBRATING": (255, 200, 0),
        "TRACKING": (0, 255, 0), "DONE": (0, 255, 255),
    }
    pc = phase_colors.get(tracking.phase, (200, 200, 200))
    cv2.putText(out, f"PHASE: {tracking.phase}", (8, y0), font, fs, pc, thick, cv2.LINE_AA)

    cv2.putText(out, f"Iteration: {tracking.iteration}", (8, y0 + line_h),
                font, fs, (200, 200, 200), thick, cv2.LINE_AA)

    dist_str = f"{tracking.last_distance_px:.0f}px" if tracking.last_distance_px < 9999 else "--"
    dist_color = (0, 255, 0) if tracking.last_distance_px < ARRIVAL_THRESHOLD_PX else (0, 200, 255)
    cv2.putText(out, f"Distance: {dist_str}", (8, y0 + line_h * 2),
                font, fs, dist_color, thick, cv2.LINE_AA)

    area_str = f"{det.area:.0f}px^2" if det.found else "--"
    cv2.putText(out, f"Area: {area_str}", (8, y0 + line_h * 3),
                font, fs, (200, 200, 200), thick, cv2.LINE_AA)

    if tracking.status_msg:
        cv2.putText(out, tracking.status_msg, (8, y0 + line_h * 4),
                    font, 0.4, (180, 180, 180), 1, cv2.LINE_AA)

    if markov_reason and markov_reason != "ok":
        cv2.putText(out, f"MARKOV: {markov_reason}", (8, y0 + line_h * 5),
                    font, 0.45, (0, 0, 255), 1, cv2.LINE_AA)


def _draw_printer_hud(out: np.ndarray, tracking: TrackingState,
                      mapping: AxisMapping | None) -> None:
    """Right-side HUD with printer position and mapping."""
    h, w = out.shape[:2]
    overlay = out.copy()
    cv2.rectangle(overlay, (w - 200, 0), (w, 100), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, out, 0.4, 0, out)

    font = cv2.FONT_HERSHEY_SIMPLEX
    fs = 0.4
    x0 = w - 192
    y0 = 16
    line_h = 18

    cv2.putText(out, "PRINTER", (x0, y0), font, fs, (0, 200, 255), 1, cv2.LINE_AA)
    cv2.putText(out, f"X: {tracking.printer_x:.1f} mm", (x0, y0 + line_h),
                font, fs, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.putText(out, f"Y: {tracking.printer_y:.1f} mm", (x0, y0 + line_h * 2),
                font, fs, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.putText(out, f"Z: {tracking.printer_z:.1f} mm", (x0, y0 + line_h * 3),
                font, fs, (200, 200, 200), 1, cv2.LINE_AA)
    if mapping:
        map_str = f"X{'+'if mapping.cam_right_to_printer_x>0 else'-'} Y{'+'if mapping.cam_down_to_printer_y>0 else'-'}"
        cv2.putText(out, f"Map: {map_str}", (x0, y0 + line_h * 4),
                    font, 0.35, (150, 150, 150), 1, cv2.LINE_AA)


def _draw_distance_sparkline(out: np.ndarray, tracking: TrackingState) -> None:
    """Bottom-center sparkline chart of distance history."""
    h, w = out.shape[:2]
    hist = tracking.distance_history
    if len(hist) < 2:
        return

    chart_w = min(400, w - 40)
    chart_h = 50
    x0 = (w - chart_w) // 2
    y0 = h - chart_h - 10

    # Background
    overlay = out.copy()
    cv2.rectangle(overlay, (x0 - 5, y0 - 18), (x0 + chart_w + 5, y0 + chart_h + 5), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.5, out, 0.5, 0, out)

    cv2.putText(out, "Distance (px)", (x0, y0 - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.35, (150, 150, 150), 1, cv2.LINE_AA)

    # Use last N points
    n = min(len(hist), chart_w)
    data = hist[-n:]
    max_val = max(max(data), 1)

    # Arrival threshold line
    thresh_y = int(y0 + chart_h - (ARRIVAL_THRESHOLD_PX / max_val) * chart_h)
    if y0 <= thresh_y <= y0 + chart_h:
        cv2.line(out, (x0, thresh_y), (x0 + chart_w, thresh_y), (0, 100, 0), 1, cv2.LINE_AA)
        cv2.putText(out, f"{ARRIVAL_THRESHOLD_PX}px", (x0 + chart_w + 3, thresh_y + 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 150, 0), 1, cv2.LINE_AA)

    # Plot line
    pts = []
    for i, v in enumerate(data):
        px = x0 + int(i * chart_w / max(n - 1, 1))
        py = int(y0 + chart_h - (v / max_val) * chart_h)
        py = max(y0, min(y0 + chart_h, py))
        pts.append((px, py))

    for i in range(len(pts) - 1):
        # Color: green when below threshold, yellow/red when above
        val = data[i + 1]
        if val < ARRIVAL_THRESHOLD_PX:
            color = (0, 255, 0)
        elif val < ARRIVAL_THRESHOLD_PX * 3:
            color = (0, 200, 255)
        else:
            color = (0, 100, 255)
        cv2.line(out, pts[i], pts[i + 1], color, 2, cv2.LINE_AA)

    # Current value dot
    if pts:
        cv2.circle(out, pts[-1], 4, (255, 255, 255), -1)


def save_debug_frame(frame: np.ndarray, det: RedDetection, iteration: int,
                     save_dir: str, tracking: TrackingState | None = None,
                     mapping: AxisMapping | None = None) -> None:
    """Save an annotated debug frame."""
    if tracking:
        annotated = annotate_frame(frame, det, tracking, mapping)
    else:
        annotated = frame.copy()
    path = os.path.join(save_dir, f"frame_{iteration:04d}.jpg")
    cv2.imwrite(path, annotated)


def _sleep_remainder(loop_start: float) -> None:
    """Sleep the remaining time in a frame to maintain TARGET_FPS."""
    elapsed = time.monotonic() - loop_start
    remaining = POLL_INTERVAL_S - elapsed
    if remaining > 0.001:
        time.sleep(remaining)


def run_visual_servo(
    printer_url: str = PRINTER_URL,
    camera_url: str = CAMERA_URL,
    step_mm: float = STEP_MM,
    timeout_s: float = 120.0,
    save_frames: bool = False,
    do_calibrate: bool = False,
    viz_port: int = 8767,
    z_height: float = OPERATING_Z_MM,
) -> None:
    """Main visual servoing routine."""

    save_dir = ""
    if save_frames:
        save_dir = os.path.join(
            os.path.dirname(__file__), "..", "logs", "visual_servo_frames"
        )
        os.makedirs(save_dir, exist_ok=True)
        logger.info(f"Saving debug frames to {save_dir}")

    # Start visualization server
    viz = VisualizationServer(port=viz_port)
    viz.start()

    # ── 1. Verify printer backend ──────────────────────────────────────
    logger.info("Checking printer backend...")
    if not printer_health(printer_url):
        logger.error(f"Printer backend not reachable at {printer_url}")
        sys.exit(1)

    state = printer_state(printer_url)
    if not state.get("connected"):
        logger.error("Printer not connected. Connect via the backend first.")
        sys.exit(1)
    logger.info(f"Printer connected. Position: X={state.get('x')}, "
                f"Y={state.get('y')}, Z={state.get('z')}")

    # ── 2. Verify camera server ────────────────────────────────────────
    logger.info("Checking camera server...")
    frame = fetch_frame(camera_url)
    if frame is None:
        logger.error(f"Camera server not reachable at {camera_url}")
        sys.exit(1)
    logger.info(f"Camera OK: {frame.shape[1]}x{frame.shape[0]}")

    # Create tracking state for visualization during setup phases
    tracking = TrackingState(phase="HOMING")
    mapping: AxisMapping | None = None
    viz.set_tracking(tracking)
    viz.set_printer_url(printer_url)

    def _viz_update_idle() -> None:
        """Push a camera frame with current HUD while not in tracking loop."""
        f = fetch_frame(camera_url)
        if f is not None:
            det = detect_red(f)
            blue_idle = detect_blue(f)
            ann = annotate_frame(f, det, tracking, mapping, blue=blue_idle)
            viz.update(ann, f)

    # ── 3. Auto-home ───────────────────────────────────────────────────
    logger.info("=" * 50)
    logger.info("PHASE 1: Auto-homing (G28)")
    logger.info("=" * 50)
    tracking.phase = "HOMING"
    tracking.status_msg = "Homing all axes..."
    _viz_update_idle()
    printer_home(printer_url)
    # Wait for homing to complete — poll position stability
    logger.info("Waiting for homing to complete...")
    time.sleep(3.0)  # G28 takes time to begin
    last_pos = None
    stable_count = 0
    for _ in range(60):  # max 30s
        s = printer_state(printer_url)
        pos = (s.get("x", 0), s.get("y", 0), s.get("z", 0))
        tracking.printer_x, tracking.printer_y, tracking.printer_z = pos
        _viz_update_idle()
        if last_pos is not None and all(abs(a - b) < 0.5 for a, b in zip(pos, last_pos)):
            stable_count += 1
            if stable_count >= 3:
                break
        else:
            stable_count = 0
        last_pos = pos
        time.sleep(0.5)
    s = printer_state(printer_url)
    logger.info(f"Homing complete. Position: X={s.get('x')}, Y={s.get('y')}, Z={s.get('z')}")

    # ── 4. Raise Z ─────────────────────────────────────────────────────
    logger.info("=" * 50)
    logger.info(f"PHASE 2: Raising Z to {z_height} mm")
    logger.info("=" * 50)
    tracking.phase = "RAISING_Z"
    tracking.status_msg = f"Raising Z to {z_height}mm..."
    _viz_update_idle()
    printer_move_absolute(printer_url, z=z_height, feedrate=300)
    time.sleep(3.0)
    # Wait for Z move
    for _ in range(40):
        s = printer_state(printer_url)
        tracking.printer_z = s.get("z", 0)
        _viz_update_idle()
        if abs(s.get("z", 0) - z_height) < 2.0:
            break
        time.sleep(0.5)
    logger.info(f"Z at {s.get('z', 0):.1f} mm")

    # ── 5. Read current position (skip centering) ──────────────────────
    s = printer_state(printer_url)
    tracking.printer_x = s.get("x", 0)
    tracking.printer_y = s.get("y", 0)
    logger.info(f"Starting from current position: X={s.get('x'):.1f}, Y={s.get('y'):.1f}, Z={s.get('z'):.1f}")

    # ── 6. Calibrate axes (optional) ───────────────────────────────────
    if do_calibrate:
        tracking.phase = "CALIBRATING"
        tracking.status_msg = "Calibrating axis mapping..."
        _viz_update_idle()
        mapping = calibrate_axes(printer_url, camera_url)
    else:
        # Default: camera right = printer X+, camera down = printer Y+
        mapping = AxisMapping(cam_right_to_printer_x=-1.0, cam_down_to_printer_y=1.0)
        logger.info("Using default axis mapping (cam right=X-, cam down=Y+). "
                     "Use --calibrate to auto-detect.")

    # ── 7. Tracking loop ───────────────────────────────────────────────
    logger.info("=" * 50)
    logger.info("PHASE 3: Visual tracking — moving toward red object")
    logger.info("=" * 50)

    tracking.phase = "TRACKING"
    tracking.status_msg = "Tracking red object..."
    tracking.iteration = 0
    tracking.last_distance_px = float("inf")
    t_start = time.time()

    # Get initial frame to check for red + blue — wait until both appear
    blue_det = BlueDetection(found=False)
    frame = fetch_frame(camera_url)
    if frame is not None:
        det = detect_red(frame)
        blue_det = detect_blue(frame)
        annotated = annotate_frame(frame, det, tracking, mapping, blue=blue_det)
        viz.update(annotated, frame)
        if blue_det.found:
            logger.info(f"Blue marker (extruder) at ({blue_det.centroid_x}, {blue_det.centroid_y}), area={blue_det.area:.0f}px²")
        else:
            logger.warning("Blue marker not detected — place blue square on extruder.")
        if not det.found:
            logger.warning("No red object detected in initial frame. "
                           "Place a red object in the camera view.")
            logger.info(f"Visualization live at http://127.0.0.1:{viz_port} — "
                        "watch the stream to position the object.")
            tracking.status_msg = "Waiting for red object..."
            while True:
                time.sleep(0.5)
                elapsed = time.time() - t_start
                if elapsed > timeout_s:
                    logger.warning(f"Timeout waiting for red object after {elapsed:.0f}s")
                    break
                frame = fetch_frame(camera_url)
                if frame is not None:
                    det = detect_red(frame)
                    blue_det = detect_blue(frame)
                    annotated = annotate_frame(frame, det, tracking, mapping, blue=blue_det)
                    viz.update(annotated, frame)
                    if det.found:
                        logger.info(f"Red detected! Centroid at ({det.centroid_x}, {det.centroid_y}), "
                                    f"area={det.area:.0f}px²")
                        tracking.status_msg = "Red found — starting tracking"
                        break

    # Set absolute positioning mode and tune motion for smooth servo tracking
    printer_send_gcode(printer_url, "G90")
    # Lower acceleration → gentle speed ramps (default ~3000, we use 800)
    printer_send_gcode(printer_url, "M201 X800 Y800")
    # Travel acceleration (no print accel needed)
    printer_send_gcode(printer_url, "M204 T800")
    # Jerk: moderate value lets segments blend without full stops
    printer_send_gcode(printer_url, "M205 X10 Y10")
    logger.info("Motion tuned: M201 X800 Y800, M204 T800, M205 X10 Y10")

    # Non-blocking printer sender — EMA smoothing + rate limiting
    sender = PrinterSender(printer_url)
    viz._sender = sender  # expose to STOP handler

    # Target lock: remember last detected centroid to reject jumping between two red objects
    last_cx: int | None = det.centroid_x if (frame is not None and det.found) else None
    last_cy: int | None = det.centroid_y if (frame is not None and det.found) else None
    red_lost_count: int = 0
    red_tracker = RedTracker()
    if frame is not None and det.found:
        red_tracker.update(det)

    active_iters = 0   # frames where red was detected and system moved

    while active_iters < MAX_ITERATIONS:
        loop_start = time.monotonic()

        elapsed = time.time() - t_start
        if elapsed > timeout_s:
            logger.warning(f"Timeout after {elapsed:.0f}s")
            break

        # Process manual jog commands
        while tracking.manual_queue:
            cmd = tracking.manual_queue.pop(0)
            if cmd["type"] == "jog":
                nx = max(5.0, min(195.0, tracking.printer_x + cmd["x"]))
                ny = max(5.0, min(215.0, tracking.printer_y + cmd["y"]))
                nz = max(0.0, min(250.0, tracking.printer_z + cmd["z"]))
                logger.info(f"[manual] Jog dX={cmd['x']:+.1f} dY={cmd['y']:+.1f} dZ={cmd['z']:+.1f} -> ({nx:.1f}, {ny:.1f}, {nz:.1f})")
                # For manual jog, send directly (blocking) since user expects immediate response
                printer_move_absolute(printer_url, x=nx, y=ny, z=nz)
                tracking.printer_x, tracking.printer_y, tracking.printer_z = nx, ny, nz

        # If stopped, keep streaming but don't auto-move.
        # NOTE: M410 is sent ONCE by the /api/stop handler when entering
        # manual mode.  Do NOT call sender.halt() here — it sends M410
        # every iteration (~30 Hz) which floods the serial queue and
        # blocks manual jog commands.
        if tracking.stopped:
            frame = fetch_frame(camera_url)
            if frame is not None:
                det = detect_red(frame, last_cx, last_cy)
                blue_det = detect_blue(frame)
                if det.found:
                    last_cx, last_cy = det.centroid_x, det.centroid_y
                tracking.detections.append(det)
                annotated = annotate_frame(frame, det, tracking, mapping, blue=blue_det)
                viz.update(annotated, frame)
            tracking.status_msg = "PAUSED -- manual control active"
            _sleep_remainder(loop_start)
            continue

        tracking.iteration += 1
        should_log = (tracking.iteration % LOG_EVERY_N == 0) or tracking.iteration <= 3

        # Poll frame
        frame = fetch_frame(camera_url)
        if frame is None:
            if should_log:
                logger.warning(f"[{tracking.iteration}] No frame, retrying...")
            _sleep_remainder(loop_start)
            continue

        # Detect red (with target lock) and blue (extruder marker)
        det = detect_red(frame, last_cx, last_cy)
        blue_det = detect_blue(frame)

        # --- Markov temporal consistency filter ---
        markov_reason = ""
        if det.found:
            accept, markov_reason = red_tracker.validate(det, blue_det)
            if accept:
                red_tracker.update(det, blue_det)
                last_cx, last_cy = det.centroid_x, det.centroid_y
                red_lost_count = 0
            else:
                if should_log or markov_reason.startswith("comovement"):
                    logger.info(f"[{tracking.iteration}] Markov REJECT: {markov_reason} "
                                f"(cx={det.centroid_x},cy={det.centroid_y},area={det.area:.0f})")
                if markov_reason.startswith("comovement") or markov_reason.startswith("area_drop"):
                    # Drop lock and reset tracker — force full re-acquisition
                    last_cx, last_cy = None, None
                    red_tracker.reset()
                    red_lost_count += 1
                    if should_log:
                        logger.info(f"[{tracking.iteration}] Lock dropped by Markov filter, "
                                    f"re-acquiring with strict threshold")
                det = RedDetection(found=False, frame_w=det.frame_w, frame_h=det.frame_h)
        else:
            red_lost_count += 1
            # After 30 consecutive misses, drop lock so re-acquisition uses stricter threshold
            if red_lost_count > 30 and last_cx is not None:
                logger.info(f"[{tracking.iteration}] Dropping target lock after {red_lost_count} misses")
                last_cx, last_cy = None, None
                red_tracker.reset()
        tracking.detections.append(det)

        # Annotate and push to visualization server
        annotated = annotate_frame(frame, det, tracking, mapping, blue=blue_det,
                                   markov_reason=markov_reason)
        viz.update(annotated, frame)

        if save_frames and save_dir and should_log:
            save_debug_frame(frame, det, tracking.iteration, save_dir, tracking, mapping)

        if not det.found:
            if should_log:
                logger.info(f"[{tracking.iteration}] No red detected -- holding position")
            _sleep_remainder(loop_start)
            continue

        if not blue_det.found:
            if should_log:
                logger.info(f"[{tracking.iteration}] No blue marker -- holding position")
            _sleep_remainder(loop_start)
            continue

        # Compute distance from blue marker (extruder) to red target
        dx_px = det.centroid_x - blue_det.centroid_x
        dy_px = det.centroid_y - blue_det.centroid_y
        distance_px = math.sqrt(dx_px ** 2 + dy_px ** 2)

        if should_log:
            logger.info(
                f"[{tracking.iteration}] Blue({blue_det.centroid_x},{blue_det.centroid_y}) "
                f"Red({det.centroid_x},{det.centroid_y}), "
                f"offset=({dx_px:+d}, {dy_px:+d})px, dist={distance_px:.0f}px, "
                f"area={det.area:.0f}px^2"
            )

        # Check arrival
        if distance_px < ARRIVAL_THRESHOLD_PX:
            logger.info(f"ARRIVED! Red within {ARRIVAL_THRESHOLD_PX}px of blue marker (extruder).")
            tracking.arrived = True
            tracking.status_msg = "ARRIVED -- target reached!"
            annotated = annotate_frame(frame, det, tracking, mapping, blue=blue_det)
            viz.update(annotated, frame)
            tracking.last_distance_px = distance_px
            tracking.distance_history.append(distance_px)
            break

        # Check convergence (compare with PREVIOUS distance, before updating)
        if distance_px >= tracking.last_distance_px:
            tracking.stall_count += 1
            if tracking.stall_count >= 20 * LOG_EVERY_N:
                # Last resort: flip axis if stuck for a very long time
                if abs(dx_px) >= abs(dy_px):
                    mapping.cam_right_to_printer_x *= -1
                    logger.warning(f"Stall: flipping X axis -> X={mapping.cam_right_to_printer_x:+.0f}")
                else:
                    mapping.cam_down_to_printer_y *= -1
                    logger.warning(f"Stall: flipping Y axis -> Y={mapping.cam_down_to_printer_y:+.0f}")
                tracking.stall_count = 0
        else:
            tracking.stall_count = max(0, tracking.stall_count - 2)

        # NOW update tracking distance (after comparison)
        tracking.last_distance_px = distance_px
        tracking.distance_history.append(distance_px)

        # Compute movement (offset from blue marker to red target)
        move_x, move_y = compute_movement(det, mapping, step_mm,
                                          ref_x=blue_det.centroid_x,
                                          ref_y=blue_det.centroid_y)

        # Use locally tracked position for bounds check (avoid extra HTTP call)
        cur_x = tracking.printer_x
        cur_y = tracking.printer_y
        new_x = max(5.0, min(195.0, cur_x + move_x))
        new_y = max(5.0, min(215.0, cur_y + move_y))
        actual_dx = new_x - cur_x
        actual_dy = new_y - cur_y

        if abs(actual_dx) < 0.01 and abs(actual_dy) < 0.01:
            _sleep_remainder(loop_start)
            continue

        tracking.move_dx = actual_dx
        tracking.move_dy = actual_dy
        tracking.status_msg = f"Moving dX={actual_dx:+.1f} dY={actual_dy:+.1f}mm"

        if should_log:
            logger.info(f"[{tracking.iteration}] Moving: dX={actual_dx:+.1f}mm, dY={actual_dy:+.1f}mm "
                         f"-> ({new_x:.1f}, {new_y:.1f})")

        sender.set_move(new_x, new_y)
        tracking.printer_positions.append((new_x, new_y, z_height))
        tracking.printer_x = new_x
        tracking.printer_y = new_y
        active_iters += 1

        # Update viz with movement arrow
        annotated = annotate_frame(frame, det, tracking, mapping, blue=blue_det)
        viz.update(annotated, frame)

        # Frame-rate regulation: sleep only the remaining time to hit target fps
        _sleep_remainder(loop_start)

    # ── 8. Summary ─────────────────────────────────────────────────────
    sender.stop()
    elapsed = time.time() - t_start
    tracking.phase = "DONE"
    result_ok = tracking.last_distance_px < ARRIVAL_THRESHOLD_PX
    tracking.status_msg = ("SUCCESS — target reached" if result_ok
                           else "INCOMPLETE — did not converge")
    # Final viz update
    _viz_update_idle()

    logger.info("=" * 50)
    logger.info("VISUAL SERVO COMPLETE")
    logger.info(f"  Frames: {tracking.iteration}, Active moves: {active_iters}")
    logger.info(f"  Elapsed: {elapsed:.1f}s")
    logger.info(f"  Final distance: {tracking.last_distance_px:.0f}px")
    s = printer_state(printer_url)
    logger.info(f"  Final position: X={s.get('x'):.1f}, Y={s.get('y'):.1f}, Z={s.get('z'):.1f}")
    if result_ok:
        logger.info("  Result: SUCCESS — extruder reached the red object")
    else:
        logger.info("  Result: INCOMPLETE — did not converge")
    logger.info("=" * 50)
    logger.info(f"  Visualization still live at http://127.0.0.1:{viz_port}")
    logger.info("  Exiting in 5s (watcher will restart)...")
    # Keep viz alive briefly so user sees the final state, then exit for watcher to restart
    try:
        for _ in range(10):
            _viz_update_idle()
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    viz.stop()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Visual servo — track red object with printer")
    parser.add_argument("--printer-url", default=PRINTER_URL, help="Printer backend URL")
    parser.add_argument("--camera-url", default=CAMERA_URL, help="Camera server URL")
    parser.add_argument("--step", type=float, default=STEP_MM, help="Step size in mm (default: 1.0)")
    parser.add_argument("--timeout", type=float, default=120.0, help="Max runtime in seconds")
    parser.add_argument("--save-frames", action="store_true", help="Save annotated debug frames")
    parser.add_argument("--calibrate", action="store_true", help="Run axis calibration first")
    parser.add_argument("--viz-port", type=int, default=8767, help="Visualization server port")
    parser.add_argument("--camera", type=int, default=None,
                        help="If set, also starts the camera server on this index")
    parser.add_argument("--camera-port", type=int, default=8766, help="Camera server port")
    parser.add_argument("--z-height", type=float, default=OPERATING_Z_MM, help="Z height in mm (default: 10)")
    args = parser.parse_args()

    # Optionally start the camera server in a background thread
    if args.camera is not None:
        logger.info(f"Starting embedded camera server (camera={args.camera}, port={args.camera_port})...")
        from scripts.camera_server import CameraCapture, make_handler, ThreadedHTTPServer
        import threading

        cam = CameraCapture(args.camera, 640, 480)
        handler = make_handler(cam)
        srv = ThreadedHTTPServer(("127.0.0.1", args.camera_port), handler)
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        args.camera_url = f"http://127.0.0.1:{args.camera_port}"
        time.sleep(1.0)  # let it start

    run_visual_servo(
        printer_url=args.printer_url,
        camera_url=args.camera_url,
        step_mm=args.step,
        timeout_s=args.timeout,
        save_frames=args.save_frames,
        do_calibrate=args.calibrate,
        viz_port=args.viz_port,
        z_height=args.z_height,
    )


if __name__ == "__main__":
    main()
