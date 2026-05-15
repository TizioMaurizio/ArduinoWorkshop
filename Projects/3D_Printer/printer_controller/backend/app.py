"""FastAPI application — local-only REST + WebSocket state server.

Godot (and any other client) connects here to receive printer state.
All control logic stays in Python; Godot is read-only.
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import AppConfig
from .gcode import (
    emergency_stop,
    get_position,
    get_temperature,
    home_all,
    home_axis,
    move_absolute,
    move_relative,
)
from .printer_state import ThreadSafeState
from .safety import SafetyValidator
from .serial_worker import SerialWorker, list_serial_ports, list_serial_ports_detailed

logger = logging.getLogger("app")

# ---------------------------------------------------------------------------
# Thread-safe target position (set by React, consumed by follower loop)
# ---------------------------------------------------------------------------

import threading

class TargetPosition:
    """Stores the desired absolute position sent by the React visualizer."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._x: float | None = None
        self._y: float | None = None
        self._z: float | None = None
        self._dirty = False  # True = new target received since last consume

    def set(self, x: float | None, y: float | None, z: float | None) -> None:
        with self._lock:
            if x is not None:
                self._x = x
            if y is not None:
                self._y = y
            if z is not None:
                self._z = z
            self._dirty = True

    def consume(self) -> tuple[float | None, float | None, float | None, bool]:
        """Return (x, y, z, was_dirty) and clear the dirty flag."""
        with self._lock:
            dirty = self._dirty
            self._dirty = False
            return self._x, self._y, self._z, dirty

    @property
    def is_dirty(self) -> bool:
        """Check if there's a pending target without consuming it."""
        with self._lock:
            return self._dirty

    def clear(self) -> None:
        with self._lock:
            self._x = None
            self._y = None
            self._z = None
            self._dirty = False

# ---------------------------------------------------------------------------
# WebSocket client registry
# ---------------------------------------------------------------------------

_ws_clients: set[WebSocket] = set()


async def broadcast_state(state: ThreadSafeState) -> None:
    """Push current state to all connected WebSocket clients."""
    data = state.to_dict()
    data["type"] = "state"
    payload = json.dumps(data)
    stale: list[WebSocket] = []
    for ws in _ws_clients:
        try:
            await ws.send_text(payload)
        except Exception:
            stale.append(ws)
    for ws in stale:
        _ws_clients.discard(ws)


async def broadcast_log(level: str, message: str) -> None:
    """Push a log event to WebSocket clients."""
    payload = json.dumps({"type": "log", "level": level, "message": message})
    stale: list[WebSocket] = []
    for ws in _ws_clients:
        try:
            await ws.send_text(payload)
        except Exception:
            stale.append(ws)
    for ws in stale:
        _ws_clients.discard(ws)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class JogRequest(BaseModel):
    axis: str
    distance_mm: float
    feedrate: Optional[int] = None


class GcodeRequest(BaseModel):
    command: str


class ConnectRequest(BaseModel):
    port: str
    baud: Optional[int] = None


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app(
    state: ThreadSafeState,
    worker: SerialWorker,
    safety: SafetyValidator,
    config: AppConfig,
) -> FastAPI:
    """Build and return the FastAPI application."""

    target = TargetPosition()

    # Minimum distance (mm) before we bother sending a new absolute move
    FOLLOW_DEADBAND_MM = 0.1
    # How often the follower loop checks for a new target (seconds)
    FOLLOW_TICK_S = 0.10
    # Feedrate for follower moves — high so printer reaches target before
    # the next tick arrives, preventing Marlin planner accumulation.
    # F12000 = 200mm/s; at 100ms tick that's 20mm max per segment.
    FOLLOW_FEEDRATE = 12000

    @asynccontextmanager
    async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
        # Start the state-broadcast loop and target-follower loop
        broadcast_task = asyncio.create_task(_state_broadcast_loop(state))
        follower_task = asyncio.create_task(
            _target_follower_loop(
                target, state, worker, safety, config,
                FOLLOW_DEADBAND_MM, FOLLOW_TICK_S, FOLLOW_FEEDRATE,
            )
        )
        position_task = asyncio.create_task(
            _position_poll_loop(state, worker)
        )
        yield
        broadcast_task.cancel()
        follower_task.cancel()
        position_task.cancel()

    app = FastAPI(title="3D Printer Controller", lifespan=lifespan)

    # Allow React dev server and local builds to reach the API
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000",
                        "http://localhost:5173", "http://127.0.0.1:5173",
                        "http://localhost:5174", "http://127.0.0.1:5174"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -- health -------------------------------------------------------------

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # -- state --------------------------------------------------------------

    @app.get("/state")
    async def get_state() -> dict[str, Any]:
        return state.to_dict()

    # -- ports --------------------------------------------------------------

    @app.get("/ports")
    async def ports() -> dict[str, Any]:
        detailed = list_serial_ports_detailed()
        return {
            "ports": [p.device for p in detailed],
            "detailed": [
                {
                    "device": p.device,
                    "description": p.description,
                    "manufacturer": p.manufacturer,
                    "vid": p.vid,
                    "pid": p.pid,
                    "score": p.score,
                }
                for p in detailed
            ],
        }

    # -- connect / disconnect -----------------------------------------------

    @app.post("/connect")
    async def connect(req: ConnectRequest) -> dict[str, Any]:
        loop = asyncio.get_event_loop()
        ok = await loop.run_in_executor(
            None, lambda: worker.connect(req.port, req.baud)
        )
        return {"connected": ok, "state": state.to_dict()}

    @app.post("/disconnect")
    async def disconnect() -> dict[str, str]:
        worker.disconnect()
        return {"status": "disconnected"}

    # -- home ---------------------------------------------------------------

    @app.post("/home")
    async def home(axis: Optional[str] = None) -> dict[str, str]:
        if axis:
            a = axis.upper()
            worker.send(home_axis(a))
            state.update(**{f"homed_{a.lower()}": True})
        else:
            worker.send(home_all())
            state.update(homed_x=True, homed_y=True, homed_z=True)
        return {"status": "homing"}

    # -- jog ----------------------------------------------------------------

    @app.post("/jog")
    async def jog(req: JogRequest) -> dict[str, Any]:
        snap = state.get()
        result = safety.validate_jog(snap, req.axis, req.distance_mm)
        if not result.allowed:
            return {"error": result.reason}

        axis = req.axis.upper()
        cfg = config.printer.jog
        feedrate = req.feedrate
        if feedrate is None:
            if axis in ("X", "Y"):
                feedrate = cfg.feedrate_xy
            elif axis == "Z":
                feedrate = cfg.feedrate_z
            else:
                feedrate = cfg.feedrate_e

        kwargs = {axis.lower(): req.distance_mm}
        cmds = move_relative(feedrate=feedrate, **kwargs)
        for cmd in cmds:
            worker.send(cmd)
        return {"status": "jogging", "commands": cmds}

    # -- raw gcode ----------------------------------------------------------

    @app.post("/gcode")
    async def gcode(req: GcodeRequest) -> dict[str, Any]:
        result = safety.validate_raw_gcode(req.command)
        if not result.allowed:
            return {"error": result.reason}
        snap = state.get()
        result2 = safety.validate_raw_move(snap, req.command)
        if not result2.allowed:
            return {"error": result2.reason}
        worker.send(req.command)
        return {"status": "sent", "command": req.command}

    # -- emergency stop -----------------------------------------------------

    @app.post("/emergency-stop")
    async def estop() -> dict[str, str]:
        worker.send_immediate(emergency_stop())
        state.update(locked=True, last_error="Emergency stop (M112)")
        return {"status": "emergency_stop_sent"}

    # -- websocket ----------------------------------------------------------

    @app.websocket("/ws/state")
    async def ws_state(ws: WebSocket) -> None:
        await ws.accept()
        _ws_clients.add(ws)
        logger.info("WebSocket client connected")
        try:
            # Send initial state + bed config
            init = state.to_dict()
            init["type"] = "state"
            init["bed"] = {
                "x_min": config.printer.bed.x_min,
                "x_max": config.printer.bed.x_max,
                "y_min": config.printer.bed.y_min,
                "y_max": config.printer.bed.y_max,
                "z_min": config.printer.bed.z_min,
                "z_max": config.printer.bed.z_max,
            }
            await ws.send_text(json.dumps(init))

            # Read messages — React sends target position updates
            while True:
                text = await ws.receive_text()
                try:
                    msg = json.loads(text)
                    if msg.get("type") == "target":
                        target.set(
                            msg.get("x"),
                            msg.get("y"),
                            msg.get("z"),
                        )
                except (json.JSONDecodeError, KeyError, TypeError):
                    pass
        except WebSocketDisconnect:
            pass
        finally:
            _ws_clients.discard(ws)
            logger.info("WebSocket client disconnected")

    return app


async def _state_broadcast_loop(state: ThreadSafeState) -> None:
    """Periodically broadcast state to all WebSocket clients."""
    last_version = -1
    while True:
        await asyncio.sleep(0.1)
        v = state.version
        if v != last_version and _ws_clients:
            last_version = v
            await broadcast_state(state)


async def _target_follower_loop(
    target: TargetPosition,
    state: ThreadSafeState,
    worker: SerialWorker,
    safety: SafetyValidator,
    config: AppConfig,
    deadband_mm: float,
    tick_s: float,
    feedrate: int = 12000,
) -> None:
    """Periodically send G1 to track the latest target position.

    Key design choices:
    - Compares against the LAST SENT position, not M114 actual (which lags)
    - Uses send_latest() so only the freshest G1 is pending in serial
    - G90 sent once; M114 handled by a separate poll loop
    - High feedrate (F12000=200mm/s) so printer reaches target within one tick,
      preventing Marlin planner buffer accumulation
    """
    loop = asyncio.get_event_loop()
    g90_sent = False

    # Track what we last sent — avoids comparing against stale M114
    last_sent_x: float = 0.0
    last_sent_y: float = 0.0
    last_sent_z: float = 0.0

    while True:
        await asyncio.sleep(tick_s)

        tx, ty, tz, dirty = target.consume()
        if not dirty:
            continue

        snap = state.get()
        if not snap.connected:
            g90_sent = False
            continue

        # Use last-sent position for deadband comparison (not M114)
        send_x = tx if (tx is not None and abs(tx - last_sent_x) > deadband_mm) else None
        send_y = ty if (ty is not None and abs(ty - last_sent_y) > deadband_mm) else None
        send_z = tz if (tz is not None and abs(tz - last_sent_z) > deadband_mm) else None

        if send_x is None and send_y is None and send_z is None:
            continue

        # Safety validation (use full target values for limit checking)
        check_x = tx if tx is not None else last_sent_x
        check_y = ty if ty is not None else last_sent_y
        check_z = tz if tz is not None else last_sent_z
        result = safety.validate_absolute_position(snap, check_x, check_y, check_z)
        if not result.allowed:
            logger.warning(f"Target rejected: {result.reason}")
            await broadcast_log("warning", f"BLOCKED: {result.reason}")
            continue

        # Always send ALL axes (so Marlin has the full target, not partial)
        final_x = tx if tx is not None else last_sent_x
        final_y = ty if ty is not None else last_sent_y
        final_z = tz if tz is not None else last_sent_z

        # Use high follower feedrate for XY; constrain Z to safe speed
        cfg = config.printer.jog
        if send_z is not None and send_x is None and send_y is None:
            f = cfg.feedrate_z
        else:
            f = feedrate

        g1_cmd = f"G1 X{final_x:.3f} Y{final_y:.3f} Z{final_z:.3f} F{f}"

        # Update last-sent tracking
        last_sent_x = final_x
        last_sent_y = final_y
        last_sent_z = final_z

        def _send(
            cmd: str = g1_cmd,
            ensure_g90: bool = not g90_sent,
        ) -> None:
            if ensure_g90:
                worker.send("G90")
            worker.send_latest(cmd)

        g90_sent = True
        await loop.run_in_executor(None, _send)


async def _position_poll_loop(
    state: ThreadSafeState,
    worker: SerialWorker,
) -> None:
    """Periodically query M114 for position display.

    Since the send_loop prioritizes latest (motion G1) over queue,
    M114 never blocks motion — safe to poll at a steady rate.
    We only enqueue M114 when the queue is empty to prevent pile-up
    during long-running commands (e.g. G28 homing takes 10-15s and
    would otherwise accumulate ~30 stale M114 in the queue).
    """
    loop = asyncio.get_event_loop()

    while True:
        await asyncio.sleep(0.2)

        snap = state.get()
        if not snap.connected:
            continue

        # Skip if queue already has pending commands — don't pile up M114
        if not worker.queue_empty:
            continue

        def _poll() -> None:
            worker.send("M114")

        await loop.run_in_executor(None, _poll)
