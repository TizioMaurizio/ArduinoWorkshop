"""USB serial connection, G-code command queue, and mock printer.

The serial worker runs two background threads:
  - Reader: continuously reads lines from the serial port and parses them.
  - Sender: dequeues one G-code command at a time, sends it, and waits
    for an ``ok`` before sending the next.
"""

from __future__ import annotations

import logging
import queue
import re
import threading
import time
from dataclasses import dataclass
from typing import Callable, Protocol

import serial
import serial.tools.list_ports

from .config import AppConfig
from .printer_state import (
    ThreadSafeState,
    parse_firmware,
    parse_m105,
    parse_m114,
)

logger = logging.getLogger("serial_worker")

RESPONSE_TIMEOUT_S = 10.0


# ---------------------------------------------------------------------------
# Port helpers
# ---------------------------------------------------------------------------

# USB descriptor keywords that suggest a 3D printer / Arduino board
_PRINTER_KEYWORDS = (
    "marlin",
    "3d printer",
    "ch340",
    "ch341",
    "cp210",
    "cp2102",
    "ftdi",
    "arduino",
    "mega",
    "ramps",
    "elegoo",
    "geeetech",
    "creality",
    "ender",
    "prusa",
    "anet",
    "anycubic",
    "tronxy",
    "biqu",
    "skr",
    "mks",
    "wemos",
)


@dataclass
class PortInfo:
    """Structured info about a serial port for display and ranking."""
    device: str
    description: str
    hwid: str
    vid: int | None
    pid: int | None
    manufacturer: str | None
    serial_number: str | None
    score: int  # higher = more likely to be a 3D printer


def list_serial_ports() -> list[str]:
    """Return device names of all available serial ports."""
    return [p.device for p in serial.tools.list_ports.comports()]


def list_serial_ports_detailed() -> list[PortInfo]:
    """Return detailed info for all serial ports, ranked by printer likelihood."""
    ports: list[PortInfo] = []
    for p in serial.tools.list_ports.comports():
        score = _score_port(p)
        ports.append(
            PortInfo(
                device=p.device,
                description=p.description or "",
                hwid=p.hwid or "",
                vid=p.vid,
                pid=p.pid,
                manufacturer=p.manufacturer,
                serial_number=p.serial_number,
                score=score,
            )
        )
    # Sort by score descending so most-likely printer is first
    ports.sort(key=lambda p: p.score, reverse=True)
    return ports


def _score_port(p: serial.tools.list_ports_common.ListPortInfo) -> int:
    """Heuristic score for how likely a port is a 3D printer.

    Higher = more likely.  Pure heuristic — probe_port() confirms.
    """
    score = 0
    searchable = " ".join(
        [
            (p.description or ""),
            (p.manufacturer or ""),
            (p.hwid or ""),
            p.device,
        ]
    ).lower()

    for kw in _PRINTER_KEYWORDS:
        if kw in searchable:
            score += 10

    # USB ports are much more likely than built-in COM1/COM2
    if p.vid is not None:
        score += 5

    # Common 3D-printer USB bridge chips by VID:PID
    if p.vid == 0x1A86:  # QinHeng CH340/CH341
        score += 15
    elif p.vid == 0x10C4:  # Silicon Labs CP210x
        score += 15
    elif p.vid == 0x0403:  # FTDI
        score += 10
    elif p.vid == 0x2341:  # Arduino
        score += 12
    elif p.vid == 0x1D50:  # OpenMoko (some printer boards)
        score += 8
    elif p.vid == 0x2C99:  # Prusa
        score += 20
    elif p.vid == 0x0483:  # STMicroelectronics (SKR, BTT)
        score += 12

    # Penalise bluetooth serial ports
    if "bluetooth" in searchable or "bt" in (p.description or "").lower():
        score -= 20

    return score


def probe_port(
    port: str,
    baud_candidates: list[int],
    timeout_s: float = 2.0,
    boot_wait_s: float = 2.5,
) -> tuple[int | None, str | None]:
    """Open *port*, send M115, and check for Marlin firmware response.

    Returns ``(baud, firmware_name)`` on success, ``(None, None)`` on failure.
    The port is closed before returning.
    """
    for baud in baud_candidates:
        ser: serial.Serial | None = None
        try:
            ser = serial.Serial(
                port=port,
                baudrate=baud,
                timeout=timeout_s,
                write_timeout=timeout_s,
            )
            # Wait for board reset (DTR toggle) and boot
            time.sleep(boot_wait_s)
            # Drain startup banner
            while ser.in_waiting:
                ser.readline()

            # Send M115 firmware identification
            ser.write(b"M115\n")

            # Read lines for up to 5 seconds looking for FIRMWARE_NAME
            deadline = time.monotonic() + 5.0
            firmware: str | None = None
            got_ok = False
            while time.monotonic() < deadline:
                raw = ser.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue

                from .printer_state import parse_firmware
                fw = parse_firmware(line)
                if fw:
                    firmware = fw
                if line == "ok" or line.startswith("ok "):
                    got_ok = True
                if firmware and got_ok:
                    break

            ser.close()
            ser = None

            if firmware:
                logger.info(
                    "Probe success: %s @ %d → %s", port, baud, firmware
                )
                return baud, firmware

        except serial.SerialException as exc:
            logger.debug("Probe failed %s @ %d: %s", port, baud, exc)
        finally:
            if ser and ser.is_open:
                ser.close()

    return None, None


def auto_discover(
    baud_candidates: list[int],
    timeout_s: float = 2.0,
) -> tuple[str | None, int | None, str | None]:
    """Scan all serial ports, rank them, and probe for a Marlin printer.

    Returns ``(port, baud, firmware_name)`` on success,
    ``(None, None, None)`` if no printer found.
    """
    ports = list_serial_ports_detailed()
    if not ports:
        logger.warning("No serial ports found")
        return None, None, None

    logger.info(
        "Auto-discovery: %d port(s) found, probing in ranked order…",
        len(ports),
    )
    for info in ports:
        # Skip ports with very negative scores (e.g. Bluetooth)
        if info.score < 0:
            logger.debug(
                "Skipping %s (score %d): %s",
                info.device, info.score, info.description,
            )
            continue

        logger.info(
            "Probing %s (score %d, %s)…",
            info.device, info.score, info.description,
        )
        baud, firmware = probe_port(
            info.device, baud_candidates, timeout_s=timeout_s
        )
        if baud is not None and firmware is not None:
            return info.device, baud, firmware

    return None, None, None


# ---------------------------------------------------------------------------
# Serial port protocol (real and mock share this interface)
# ---------------------------------------------------------------------------

class SerialPort(Protocol):
    def write(self, data: bytes) -> int: ...
    def readline(self) -> bytes: ...
    def close(self) -> None: ...
    @property
    def is_open(self) -> bool: ...
    @property
    def in_waiting(self) -> int: ...


# ---------------------------------------------------------------------------
# Mock serial for development / testing
# ---------------------------------------------------------------------------

class MockSerialPort:
    """Simulates a Marlin printer over serial for offline development."""

    def __init__(self) -> None:
        self._is_open = True
        self._response_queue: queue.Queue[str] = queue.Queue()
        self._x = 0.0
        self._y = 0.0
        self._z = 0.0
        self._e = 0.0
        self._relative = False
        self._halted = False
        # Startup banner
        self._response_queue.put("start")
        self._response_queue.put("echo: Mock Marlin ready")

    @property
    def is_open(self) -> bool:
        return self._is_open

    @property
    def in_waiting(self) -> int:
        return self._response_queue.qsize()

    def write(self, data: bytes) -> int:
        cmd = data.decode("ascii", errors="replace").strip()
        self._process_command(cmd)
        return len(data)

    def readline(self) -> bytes:
        try:
            line = self._response_queue.get(timeout=0.1)
            return (line + "\n").encode("ascii")
        except queue.Empty:
            return b""

    def close(self) -> None:
        self._is_open = False

    def _process_command(self, cmd: str) -> None:
        upper = cmd.upper().strip()

        if self._halted and upper != "M112":
            self._response_queue.put("Error: Printer halted. kill() called!")
            return

        if upper == "M115":
            self._response_queue.put("FIRMWARE_NAME:Mock Marlin 2.0.0")
            self._response_queue.put("ok")
        elif upper == "M105":
            self._response_queue.put("ok T:25.0 /0.0 B:25.0 /0.0")
        elif upper == "M114":
            self._response_queue.put(
                f"X:{self._x:.2f} Y:{self._y:.2f} "
                f"Z:{self._z:.2f} E:{self._e:.2f} "
                f"Count X:0 Y:0 Z:0"
            )
            self._response_queue.put("ok")
        elif upper == "G28":
            self._x = self._y = self._z = 0.0
            self._response_queue.put("ok")
        elif upper.startswith("G28 "):
            if "X" in upper:
                self._x = 0.0
            if "Y" in upper:
                self._y = 0.0
            if "Z" in upper:
                self._z = 0.0
            self._response_queue.put("ok")
        elif upper == "G91":
            self._relative = True
            self._response_queue.put("ok")
        elif upper == "G90":
            self._relative = False
            self._response_queue.put("ok")
        elif upper in ("M82", "M83", "M84"):
            self._response_queue.put("ok")
        elif upper.startswith("G1 ") or upper.startswith("G0 "):
            self._apply_move(upper)
            self._response_queue.put("ok")
        elif upper == "M112":
            self._halted = True
            self._response_queue.put("Error: Printer halted. kill() called!")
        elif upper.startswith("M106") or upper == "M107":
            self._response_queue.put("ok")
        else:
            self._response_queue.put("ok")

    def _apply_move(self, upper: str) -> None:
        """Apply axis movement (always relative for simplicity in mock)."""
        for letter, attr in [("X", "_x"), ("Y", "_y"), ("Z", "_z"), ("E", "_e")]:
            m = re.search(rf"{letter}(-?[\d.]+)", upper)
            if m:
                delta = float(m.group(1))
                if self._relative or letter == "E":
                    setattr(self, attr, getattr(self, attr) + delta)
                else:
                    setattr(self, attr, delta)


# ---------------------------------------------------------------------------
# Serial worker
# ---------------------------------------------------------------------------

LogCallback = Callable[[str, str, str], None]  # (level, message, detail)


class SerialWorker:
    """Manages serial communication with a Marlin printer.

    Thread-safe.  Call ``send()`` from any thread to enqueue a command.
    """

    def __init__(
        self,
        state: ThreadSafeState,
        config: AppConfig,
        on_log: LogCallback | None = None,
    ) -> None:
        self._state = state
        self._config = config
        self._on_log = on_log
        self._on_ok_callbacks: list[Callable[[], None]] = []
        self._serial: SerialPort | None = None
        self._cmd_queue: queue.Queue[str] = queue.Queue()
        self._running = False
        self._thread: threading.Thread | None = None
        self._read_thread: threading.Thread | None = None
        self._got_ok = threading.Event()
        self._processing = False  # True while send_loop is waiting for ok
        # Single-slot "latest" command — always overwrites, never queues
        self._latest_cmd: str | None = None
        self._latest_lock = threading.Lock()
        self._latest_event = threading.Event()

    # -- connection ---------------------------------------------------------

    def connect(self, port: str, baud: int | None = None) -> bool:
        """Open a real serial port.  Tries baud candidates if *baud* is None."""
        if self._serial and self._serial.is_open:
            self.disconnect()

        baud_list = [baud] if baud else self._config.printer.baud_candidates

        for rate in baud_list:
            try:
                self._log("info", f"Trying {port} @ {rate}\u2026")
                ser = serial.Serial(
                    port=port,
                    baudrate=rate,
                    timeout=self._config.printer.serial.timeout_s,
                    write_timeout=self._config.printer.serial.write_timeout_s,
                )
                # Many Marlin boards reset on DTR — wait for boot
                time.sleep(2.0)
                while ser.in_waiting:
                    ser.readline()

                self._serial = ser  # type: ignore[assignment]
                self._state.update(
                    connected=True, port=port, locked=False, last_error=None
                )
                self._running = True
                self._start_threads()
                self._handshake()
                self._log("info", f"Connected to {port} @ {rate}")
                return True
            except serial.SerialException as exc:
                self._log("warning", f"Failed {port} @ {rate}: {exc}")
                continue

        self._log("error", f"Could not connect to {port}")
        return False

    def connect_mock(self) -> bool:
        """Connect using the built-in mock printer."""
        self._serial = MockSerialPort()  # type: ignore[assignment]
        self._state.update(connected=True, port="MOCK", locked=False, last_error=None)
        self._running = True
        self._start_threads()
        time.sleep(0.3)
        self._handshake()
        self._log("info", "Connected to mock printer")
        return True

    def disconnect(self) -> None:
        self._running = False
        self._got_ok.set()  # unblock sender
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None
        if self._read_thread:
            self._read_thread.join(timeout=3.0)
            self._read_thread = None
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._serial = None
        self._state.update(connected=False, port=None, firmware=None)
        self._log("info", "Disconnected")

    @property
    def is_connected(self) -> bool:
        return self._serial is not None and self._serial.is_open

    def register_ok_callback(self, cb: Callable[[], None]) -> None:
        """Register a callback invoked on every 'ok' from the printer."""
        self._on_ok_callbacks.append(cb)

    # -- command API --------------------------------------------------------

    def send(self, command: str) -> None:
        """Enqueue a G-code command for sequential sending."""
        self._cmd_queue.put(command.strip())
        self._latest_event.set()  # wake send_loop to process queue

    @property
    def queue_empty(self) -> bool:
        """True if the command queue has no pending items and no command
        is currently being processed (waiting for ok)."""
        return self._cmd_queue.empty() and not self._processing

    def send_immediate(self, command: str) -> None:
        """Send a command immediately, bypassing the queue (for M112)."""
        if self._serial and self._serial.is_open:
            line = command.strip() + "\n"
            try:
                self._serial.write(line.encode("ascii"))
                self._log("info", f"Sent immediate: {command.strip()}")
            except Exception as exc:
                self._log("error", f"Failed immediate send: {exc}")

    def send_latest(self, command: str) -> None:
        """Set a single-slot 'latest' command that replaces any pending one.

        Unlike send() which queues, this always overwrites the previous
        unsent command.  The send loop picks it up on the next ok-gated
        cycle.  Use this for continuous motion (jog/follow) where only
        the most recent target matters.
        """
        with self._latest_lock:
            self._latest_cmd = command.strip()
        self._latest_event.set()

    # -- internal threads ---------------------------------------------------

    def _start_threads(self) -> None:
        self._read_thread = threading.Thread(
            target=self._read_loop, daemon=True, name="serial-reader"
        )
        self._thread = threading.Thread(
            target=self._send_loop, daemon=True, name="serial-sender"
        )
        self._read_thread.start()
        self._thread.start()

    def _handshake(self) -> None:
        """Identify the printer after connection."""
        self.send("M115")
        self.send("M105")
        self.send("M114")

    def _send_loop(self) -> None:
        """Send commands one at a time, waiting for ``ok`` between each.

        Priority: latest (motion G1) first, then queued commands.
        Motion is time-critical; informational queries (M114) can wait.
        The latest-slot always holds only the most recent motion command,
        so continuous movement never builds up a backlog.
        """
        while self._running:
            cmd: str | None = None

            # Priority 1: single-slot latest command (follower G1 — time-critical)
            with self._latest_lock:
                if self._latest_cmd is not None:
                    cmd = self._latest_cmd
                    self._latest_cmd = None
            if cmd is not None:
                self._latest_event.clear()

            # Priority 2: queued commands (handshake, M114, user gcode, etc.)
            if cmd is None:
                try:
                    cmd = self._cmd_queue.get_nowait()
                except queue.Empty:
                    pass

            if cmd is None:
                # Wait for either a queue item or a latest-slot write
                self._latest_event.wait(timeout=0.2)
                continue

            if not self._serial or not self._serial.is_open:
                break

            self._processing = True
            self._got_ok.clear()
            line = cmd + "\n"
            try:
                self._serial.write(line.encode("ascii"))
                self._log("info", f"Sent: {cmd}", cmd)
            except Exception as exc:
                self._processing = False
                self._log("error", f"Write error: {exc}")
                break

            if not self._got_ok.wait(timeout=RESPONSE_TIMEOUT_S):
                self._log("warning", f"Timeout waiting for response to: {cmd}")
            self._processing = False

    def _read_loop(self) -> None:
        """Read and parse serial responses continuously."""
        while self._running:
            if not self._serial or not self._serial.is_open:
                time.sleep(0.1)
                continue
            try:
                raw = self._serial.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                self._log("debug", f"Recv: {line}")
                self._process_response(line)
            except Exception as exc:
                if self._running:
                    self._log("error", f"Read error: {exc}")
                    time.sleep(0.1)

    # -- response parsing ---------------------------------------------------

    # Benign Marlin errors that should NOT lock the controller
    _IGNORABLE_ERRORS = (
        "volume.init failed",      # No SD card — harmless over USB
        "openroot failed",         # SD card directory unreadable
        "sd init fail",            # SD card init timeout
        "cannot open subdir",      # SD card subdirectory issue
    )

    def _process_response(self, line: str) -> None:
        # Critical errors (but skip benign SD-card noise)
        if line.startswith("Error:") or "Printer halted" in line:
            lower = line.lower()
            if any(ign in lower for ign in self._IGNORABLE_ERRORS):
                self._log("info", f"Ignoring benign error: {line}")
                self._got_ok.set()
                return
            self._state.update(locked=True, last_error=line, busy=False)
            self._log("error", f"Printer error: {line}")
            self._got_ok.set()
            return

        if "echo:busy" in line:
            self._state.update(busy=True)
            return

        if line.startswith("Resend:"):
            self._log("warning", f"Resend requested: {line}")
            self._got_ok.set()
            return

        if "thermal runaway" in line.lower():
            self._state.update(locked=True, last_error=line)
            self._log("error", f"Thermal error: {line}")
            self._got_ok.set()
            return

        # Firmware identification
        fw = parse_firmware(line)
        if fw:
            self._state.update(firmware=fw)

        # Position
        pos = parse_m114(line)
        if pos:
            self._state.update(**pos)

        # Temperature
        temp = parse_m105(line)
        if temp:
            self._state.update(**temp)

        # ok acknowledgement (may carry inline temperature data)
        if line == "ok" or line.startswith("ok "):
            self._state.update(busy=False)
            if len(line) > 2:
                temp2 = parse_m105(line)
                if temp2:
                    self._state.update(**temp2)
            self._got_ok.set()
            # Notify registered ok callbacks (e.g. jog buffer)
            for cb in self._on_ok_callbacks:
                try:
                    cb()
                except Exception:
                    pass

    # -- logging ------------------------------------------------------------

    def _log(
        self, level: str, message: str, command: str | None = None
    ) -> None:
        getattr(logger, level, logger.info)(message)
        if self._on_log:
            self._on_log(level, message, command or "")
