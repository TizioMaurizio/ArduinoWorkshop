"""OpenCV USB camera MJPEG streaming server.

Streams from the first available USB camera over HTTP:
  - GET /              → simple HTML page with live <img> feed
  - GET /stream        → multipart MJPEG stream
  - GET /frame         → single JPEG snapshot (for polling)
  - GET /frame?format=json → base64-encoded JPEG + metadata as JSON

Usage:
    python scripts/camera_server.py [--camera auto] [--port 8766] [--width 640] [--height 480]

Camera auto-discovery probes indices 0-9, reads a test frame from each,
and selects the first camera that actually delivers frames (skipping
internal/broken cameras that open but fail to read).

The server binds to 127.0.0.1 only (localhost).
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

import cv2
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("camera_server")


# ---------------------------------------------------------------------------
# Camera auto-discovery
# ---------------------------------------------------------------------------

def discover_cameras(max_index: int = 10) -> list[dict]:
    """Probe camera indices and return info for each that can deliver frames.

    Each entry: {index, width, height, backend, working, is_virtual}
    'working' means cv2.read() returned valid frames on multiple attempts
    (catches intermittent cameras that open but fail sporadically).
    'is_virtual' flags likely virtual cameras (OBS, ManyCam, etc.) detected
    by DSHOW-only availability or static frame content.
    """
    results: list[dict] = []
    for idx in range(max_index):
        cap = cv2.VideoCapture(idx)
        if not cap.isOpened():
            continue
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        backend = cap.getBackendName()
        # Test multiple reads — internal cameras sometimes succeed once then fail
        success_count = 0
        frames_collected = []
        for _ in range(3):
            ret, frame = cap.read()
            if ret and frame is not None and frame.size > 0:
                success_count += 1
                frames_collected.append(frame)
        cap.release()
        working = success_count >= 2  # at least 2/3 reads must succeed

        # Detect virtual cameras:
        # 1. DSHOW-only cameras on Windows are often virtual (OBS, ManyCam)
        #    Real hardware cameras use MSMF as the default backend
        is_virtual = False
        if backend == "DSHOW":
            is_virtual = True

        # 2. Check for static frames (virtual cameras often show a logo)
        #    Compare frame variance — real cameras have sensor noise
        if working and len(frames_collected) >= 2 and not is_virtual:
            diff = cv2.absdiff(frames_collected[0], frames_collected[-1])
            mean_diff = diff.mean()
            if mean_diff < 0.5:  # nearly identical frames = likely static source
                is_virtual = True

        entry = {
            "index": idx, "width": w, "height": h,
            "backend": backend, "working": working,
            "is_virtual": is_virtual,
        }
        results.append(entry)
        virt_tag = " [VIRTUAL]" if is_virtual else ""
        status = f"OK ({success_count}/3 reads)" if working else f"UNRELIABLE ({success_count}/3 reads)"
        logger.info(f"  Camera {idx}: {w}x{h} [{backend}]{virt_tag} — {status}")
    return results


def auto_select_camera(max_index: int = 10) -> int:
    """Auto-discover and return the index of the first working USB camera.

    Strategy:
      1. Probe indices 0..max_index-1
      2. Skip cameras that can't deliver frames (broken)
      3. Skip virtual cameras (OBS, ManyCam) detected by DSHOW backend
      4. Among real hardware cameras (MSMF), prefer higher indices — USB
         cameras enumerate after built-in webcams on Windows
      5. Fall back to any working camera if no real hardware found

    Raises RuntimeError if no working camera is found.
    """
    logger.info(f"Auto-discovering cameras (indices 0-{max_index - 1})...")
    cams = discover_cameras(max_index)
    working = [c for c in cams if c["working"]]
    if not working:
        raise RuntimeError(
            f"No working camera found (probed indices 0-{max_index - 1}). "
            f"{len(cams)} camera(s) opened but none delivered frames."
        )

    # Prefer real hardware cameras (not virtual)
    real = [c for c in working if not c["is_virtual"]]
    if real:
        # Among real cameras, prefer highest index (USB > internal)
        best = max(real, key=lambda c: c["index"])
    else:
        # Fall back to any working camera
        logger.warning("No real hardware cameras found — falling back to virtual camera")
        best = working[0]

    logger.info(
        f"Auto-selected camera {best['index']}: "
        f"{best['width']}x{best['height']} [{best['backend']}]"
        f"{' [VIRTUAL]' if best['is_virtual'] else ''}"
    )
    return best["index"]


class CameraCapture:
    """Thread-safe camera capture wrapper."""

    def __init__(self, camera_index: int, width: int, height: int) -> None:
        self._cap = cv2.VideoCapture(camera_index)
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open camera index {camera_index}")
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        actual_w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        logger.info(f"Camera {camera_index} opened: {actual_w}x{actual_h}")

        self._lock = threading.Lock()
        self._frame: np.ndarray | None = None
        self._jpeg: bytes = b""
        self._timestamp: float = 0.0
        self._running = True

        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def _capture_loop(self) -> None:
        while self._running:
            ret, frame = self._cap.read()
            if not ret:
                time.sleep(0.01)
                continue
            _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            with self._lock:
                self._frame = frame
                self._jpeg = jpeg.tobytes()
                self._timestamp = time.time()

    def get_jpeg(self) -> tuple[bytes, float]:
        """Return (jpeg_bytes, timestamp)."""
        with self._lock:
            return self._jpeg, self._timestamp

    def get_frame(self) -> tuple[np.ndarray | None, float]:
        """Return (BGR numpy array, timestamp)."""
        with self._lock:
            return self._frame.copy() if self._frame is not None else None, self._timestamp

    def release(self) -> None:
        self._running = False
        self._thread.join(timeout=2.0)
        self._cap.release()


class CameraHandler(BaseHTTPRequestHandler):
    """HTTP handler for camera endpoints."""

    camera: CameraCapture  # set by factory

    def log_message(self, format: str, *args: object) -> None:
        logger.debug(format, *args)

    def do_GET(self) -> None:
        if self.path == "/":
            self._serve_index()
        elif self.path == "/stream":
            self._serve_mjpeg()
        elif self.path.startswith("/frame"):
            self._serve_frame()
        elif self.path == "/health":
            self._serve_json({"status": "ok"})
        else:
            self.send_error(404)

    def _serve_index(self) -> None:
        html = b"""<!DOCTYPE html>
<html><head><title>Camera</title></head>
<body style="margin:0;background:#111">
<img src="/stream" style="width:100vw;height:100vh;object-fit:contain">
</body></html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)

    def _serve_mjpeg(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        try:
            while True:
                jpeg, _ = self.camera.get_jpeg()
                if not jpeg:
                    time.sleep(0.03)
                    continue
                self.wfile.write(b"--frame\r\n")
                self.wfile.write(b"Content-Type: image/jpeg\r\n")
                self.wfile.write(f"Content-Length: {len(jpeg)}\r\n\r\n".encode())
                self.wfile.write(jpeg)
                self.wfile.write(b"\r\n")
                time.sleep(0.033)  # ~30 fps cap
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _serve_frame(self) -> None:
        jpeg, ts = self.camera.get_jpeg()
        if not jpeg:
            self.send_error(503, "No frame available")
            return

        if "format=json" in self.path:
            payload = {
                "timestamp": ts,
                "jpeg_b64": base64.b64encode(jpeg).decode("ascii"),
                "size": len(jpeg),
            }
            self._serve_json(payload)
        else:
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(jpeg)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(jpeg)

    def _serve_json(self, data: dict) -> None:
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """HTTP server that handles each request in a new thread."""
    daemon_threads = True


def make_handler(camera: CameraCapture) -> type:
    """Create a handler class bound to this camera instance."""

    class BoundHandler(CameraHandler):
        pass

    BoundHandler.camera = camera  # type: ignore[attr-defined]
    return BoundHandler


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenCV USB Camera MJPEG Server")
    parser.add_argument(
        "--camera", default="auto",
        help="Camera index (integer) or 'auto' to discover first working USB camera (default: auto)",
    )
    parser.add_argument("--port", type=int, default=8766, help="HTTP port (default: 8766)")
    parser.add_argument("--width", type=int, default=640, help="Capture width")
    parser.add_argument("--height", type=int, default=480, help="Capture height")
    parser.add_argument("--list", action="store_true", help="List all cameras and exit")
    args = parser.parse_args()

    if args.list:
        print("Probing cameras...")
        cams = discover_cameras()
        if not cams:
            print("No cameras found.")
        else:
            for c in cams:
                virt = " [VIRTUAL]" if c.get("is_virtual") else ""
                status = "WORKING" if c["working"] else "UNRELIABLE"
                print(f"  [{c['index']}] {c['width']}x{c['height']} "
                      f"[{c['backend']}]{virt} — {status}")
        return

    if args.camera == "auto":
        camera_index = auto_select_camera()
    else:
        camera_index = int(args.camera)

    camera = CameraCapture(camera_index, args.width, args.height)
    handler = make_handler(camera)
    server = ThreadedHTTPServer(("127.0.0.1", args.port), handler)
    logger.info(f"Camera server on http://127.0.0.1:{args.port}")
    logger.info(f"  Stream:   http://127.0.0.1:{args.port}/stream")
    logger.info(f"  Snapshot: http://127.0.0.1:{args.port}/frame")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down")
    finally:
        camera.release()
        server.server_close()


if __name__ == "__main__":
    main()
