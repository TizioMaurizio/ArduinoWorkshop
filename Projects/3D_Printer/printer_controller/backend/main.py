"""Main entry point for the 3D printer controller.

Usage:
    python -m backend.main --mock
    python -m backend.main --port COM3
    python -m backend.main --auto
    python -m backend.main --list-ports
    python -m backend.main --config config.yaml
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import uvicorn

from .app import broadcast_log, create_app
from .config import AppConfig, load_config
from .jog import run_jog_loop
from .printer_state import ThreadSafeState
from .safety import SafetyValidator
from .serial_worker import SerialWorker, auto_discover, list_serial_ports, list_serial_ports_detailed


# ---------------------------------------------------------------------------
# Structured JSON log formatter
# ---------------------------------------------------------------------------

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "source": record.name,
            "message": record.getMessage(),
        }
        return json.dumps(entry)


def _setup_logging() -> None:
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    file_handler = logging.FileHandler(log_dir / "controller.log", encoding="utf-8")
    file_handler.setFormatter(JsonFormatter())
    file_handler.setLevel(logging.DEBUG)

    # Console handler (minimal, since the jog display owns the terminal)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    logging.basicConfig(level=logging.DEBUG, handlers=[file_handler, console_handler])


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="3D Printer USB G-code Controller"
    )
    p.add_argument("--port", help="Serial port (e.g. COM3, /dev/ttyUSB0)")
    p.add_argument("--baud", type=int, help="Baud rate override")
    p.add_argument("--auto", action="store_true", help="Auto-detect serial port")
    p.add_argument("--mock", action="store_true", help="Run with mock printer")
    p.add_argument("--list-ports", action="store_true", help="List serial ports and exit")
    p.add_argument("--config", default=None, help="Config YAML path")
    p.add_argument("--no-terminal", action="store_true", help="API-only, no terminal jog UI")
    p.add_argument("--gui", action="store_true", help="Launch graphical UI instead of terminal")
    p.add_argument("--reload", action="store_true", help="Watch backend/ for changes and auto-restart")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = _parse_args()

    # Auto-reload mode: re-launch this process under watchfiles
    if args.reload:
        try:
            from watchfiles import run_process
        except ImportError:
            print("Install watchfiles for --reload: pip install watchfiles")
            sys.exit(1)

        import subprocess
        import shlex

        watch_dir = str(Path(__file__).resolve().parent)
        # Rebuild argv without --reload to avoid recursion
        child_args = [a for a in sys.argv if a != "--reload"]
        cmd = [sys.executable, "-m", "backend.main"] + child_args[1:]

        print(f"Watching {watch_dir} for changes …")
        print(f"Press Ctrl+C to stop.\n")

        while True:
            try:
                proc = subprocess.Popen(cmd, env={**__import__("os").environ})
                from watchfiles import watch
                for changes in watch(watch_dir):
                    print(f"\n⟳ File change detected, restarting …")
                    proc.terminate()
                    proc.wait(timeout=5)
                    break
            except KeyboardInterrupt:
                proc.terminate()
                proc.wait(timeout=5)
                print("\nStopped.")
                break
        return

    # List ports and exit
    if args.list_ports:
        ports = list_serial_ports_detailed()
        if ports:
            print("Available serial ports (ranked by printer likelihood):\n")
            for p in ports:
                vid_pid = ""
                if p.vid is not None:
                    vid_pid = f"  VID:PID={p.vid:04X}:{(p.pid or 0):04X}"
                mfr = f"  [{p.manufacturer}]" if p.manufacturer else ""
                print(f"  {p.device:12s} score={p.score:3d}  {p.description}{vid_pid}{mfr}")
            print()
            print("Use --auto to probe and connect to the highest-ranked printer.")
        else:
            print("No serial ports found.")
        return

    _setup_logging()
    logger = logging.getLogger("main")

    config = load_config(args.config)
    state = ThreadSafeState()
    safety = SafetyValidator(config)

    # Log callback that bridges serial events to the async WebSocket broadcaster
    _loop_ref: asyncio.AbstractEventLoop | None = None

    def _on_serial_log(level: str, message: str, _detail: str) -> None:
        if _loop_ref and _loop_ref.is_running():
            asyncio.run_coroutine_threadsafe(
                broadcast_log(level, message), _loop_ref
            )

    worker = SerialWorker(state, config, on_log=_on_serial_log)

    # Connect
    if args.mock:
        if not worker.connect_mock():
            logger.error("Failed to start mock printer")
            sys.exit(1)
    elif args.port:
        if not worker.connect(args.port, args.baud):
            logger.error(f"Failed to connect to {args.port}")
            sys.exit(1)
    elif args.auto:
        print("Scanning serial ports for Marlin printer…")
        port, baud, firmware = auto_discover(
            config.printer.baud_candidates,
            timeout_s=config.printer.serial.timeout_s,
        )
        if port is None or baud is None:
            logger.error("Auto-discovery found no Marlin printer on any port")
            print(
                "\nNo Marlin printer found.  Run --list-ports to see available ports,\n"
                "or specify --port manually."
            )
            sys.exit(1)
        print(f"Found printer on {port} @ {baud}: {firmware}")
        if not worker.connect(port, baud):
            logger.error(f"Failed to connect to discovered port {port}")
            sys.exit(1)
    else:
        if args.gui:
            # GUI mode doesn't require pre-connection — user connects from the UI
            pass
        else:
            print("Specify --port, --auto, or --mock.  Use --list-ports to see ports.")
            sys.exit(1)

    # Build FastAPI app
    app = create_app(state, worker, safety, config)

    # Start uvicorn in a background thread
    uvi_config = uvicorn.Config(
        app,
        host=config.server.host,
        port=config.server.port,
        log_level="warning",
    )
    server = uvicorn.Server(uvi_config)

    def _run_server() -> None:
        nonlocal _loop_ref
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        _loop_ref = loop
        loop.run_until_complete(server.serve())

    server_thread = threading.Thread(target=_run_server, daemon=True, name="uvicorn")
    server_thread.start()

    # Wait briefly for uvicorn to start
    time.sleep(0.5)
    logger.info(
        f"API server running at http://{config.server.host}:{config.server.port}"
    )

    # Terminal jog UI (blocks until quit)
    if args.gui:
        from .gui import PrinterGUI
        gui = PrinterGUI(state, worker, safety, config)
        gui.run()
    elif not args.no_terminal:
        try:
            run_jog_loop(state, worker, safety, config)
        except KeyboardInterrupt:
            pass
    else:
        # API-only mode: block until Ctrl+C
        print(f"API server running at http://{config.server.host}:{config.server.port}")
        print("Press Ctrl+C to stop.")
        try:
            server_thread.join()
        except KeyboardInterrupt:
            pass

    # Shutdown
    logger.info("Shutting down…")
    worker.disconnect()
    server.should_exit = True
    server_thread.join(timeout=3.0)


if __name__ == "__main__":
    main()
