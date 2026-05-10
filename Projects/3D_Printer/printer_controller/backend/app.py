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
    move_relative,
)
from .printer_state import ThreadSafeState
from .safety import SafetyValidator
from .serial_worker import SerialWorker, list_serial_ports, list_serial_ports_detailed

logger = logging.getLogger("app")

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

    @asynccontextmanager
    async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
        # Start the state-broadcast loop
        task = asyncio.create_task(_state_broadcast_loop(state))
        yield
        task.cancel()

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

            # Keep alive — read messages (none expected from Godot)
            while True:
                await ws.receive_text()
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
