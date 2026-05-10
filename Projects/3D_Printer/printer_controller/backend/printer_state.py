"""Printer state model and Marlin response parsers."""

from __future__ import annotations

import re
import threading
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class PrinterState:
    connected: bool = False
    port: str | None = None
    firmware: str | None = None

    x: float | None = None
    y: float | None = None
    z: float | None = None
    e: float | None = None

    homed_x: bool = False
    homed_y: bool = False
    homed_z: bool = False

    hotend_temp_c: float | None = None
    hotend_target_c: float | None = None
    bed_temp_c: float | None = None
    bed_target_c: float | None = None

    busy: bool = False
    locked: bool = False
    last_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ThreadSafeState:
    """Thread-safe wrapper around PrinterState.

    All field updates go through update() which acquires the lock
    and bumps a version counter for change detection.
    """

    def __init__(self) -> None:
        self._state = PrinterState()
        self._lock = threading.Lock()
        self._version = 0

    @property
    def version(self) -> int:
        with self._lock:
            return self._version

    def get(self) -> PrinterState:
        """Return a snapshot copy of the current state."""
        with self._lock:
            return PrinterState(**asdict(self._state))

    def update(self, **kwargs: Any) -> None:
        """Update one or more state fields atomically."""
        with self._lock:
            for k, v in kwargs.items():
                if hasattr(self._state, k):
                    setattr(self._state, k, v)
            self._version += 1

    def to_dict(self) -> dict[str, Any]:
        with self._lock:
            return asdict(self._state)


# ---------------------------------------------------------------------------
# Response parsers for Marlin firmware
# ---------------------------------------------------------------------------

_M114_PATTERN = re.compile(
    r"X:\s*(-?[\d.]+)\s+Y:\s*(-?[\d.]+)\s+Z:\s*(-?[\d.]+)\s+E:\s*(-?[\d.]+)"
)

_M105_PATTERN = re.compile(r"T:\s*(-?[\d.]+)\s*/\s*(-?[\d.]+)")

_M105_BED_PATTERN = re.compile(r"B:\s*(-?[\d.]+)\s*/\s*(-?[\d.]+)")

_FIRMWARE_PATTERN = re.compile(
    r"FIRMWARE_NAME:\s*(.+?)(?:\s+SOURCE_CODE_URL|\s+PROTOCOL_VERSION|$)"
)


def parse_m114(line: str) -> dict[str, float] | None:
    """Parse M114 position response.

    Example input:
        X:10.00 Y:20.00 Z:0.30 E:0.00 Count X:800 Y:1600 Z:120
    """
    m = _M114_PATTERN.search(line)
    if m:
        return {
            "x": float(m.group(1)),
            "y": float(m.group(2)),
            "z": float(m.group(3)),
            "e": float(m.group(4)),
        }
    return None


def parse_m105(line: str) -> dict[str, float] | None:
    """Parse M105 temperature response.

    Example input:
        ok T:200.1 /200.0 B:60.2 /60.0
    """
    result: dict[str, float] = {}
    m = _M105_PATTERN.search(line)
    if m:
        result["hotend_temp_c"] = float(m.group(1))
        result["hotend_target_c"] = float(m.group(2))
    mb = _M105_BED_PATTERN.search(line)
    if mb:
        result["bed_temp_c"] = float(mb.group(1))
        result["bed_target_c"] = float(mb.group(2))
    return result if result else None


def parse_firmware(line: str) -> str | None:
    """Parse M115 firmware identification response.

    Example input:
        FIRMWARE_NAME:Marlin 2.1.2 SOURCE_CODE_URL:...
    """
    m = _FIRMWARE_PATTERN.search(line)
    if m:
        return m.group(1).strip()
    return None
