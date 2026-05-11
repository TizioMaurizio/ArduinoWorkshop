"""Safety validation layer for printer commands.

Every movement command must pass through this module before reaching
the serial queue.  Safety is mandatory — no bypass path exists.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

from .config import AppConfig
from .printer_state import PrinterState

# Raw G-code commands denied by default (risk of bricking/miscalibration)
DENIED_COMMANDS = frozenset(
    {
        "M502",  # factory reset
        "M500",  # save settings
        "M851",  # Z probe offset
        "M301",  # PID hotend tuning
        "M304",  # PID bed tuning
        "M92",  # steps/mm
        "M206",  # home offset
        "M428",  # set home offsets
    }
)


@dataclass
class SafetyResult:
    allowed: bool
    reason: str = ""


class SafetyValidator:
    """Validates jog, raw G-code, and move commands against safety rules."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._last_jog_time: float = 0.0

    def validate_jog(
        self,
        state: PrinterState,
        axis: str,
        distance_mm: float,
    ) -> SafetyResult:
        """Validate a jog movement request."""
        cfg = self._config.printer

        if not state.connected:
            return SafetyResult(False, "Printer not connected")

        if state.locked:
            return SafetyResult(
                False, "Controller locked after error. Reconnect required."
            )

        # Rate limit
        now = time.monotonic()
        if cfg.safety.max_jog_rate_hz > 0:
            min_interval = 1.0 / cfg.safety.max_jog_rate_hz
            if (now - self._last_jog_time) < min_interval:
                return SafetyResult(False, "Jog rate limit exceeded")

        axis = axis.upper()

        # Cold extrusion guard
        if axis == "E":
            if not cfg.extruder.cold_extrusion_allowed:
                temp = state.hotend_temp_c
                if temp is None or temp < cfg.extruder.minimum_extrude_temp_c:
                    return SafetyResult(
                        False,
                        f"Cold extrusion blocked: hotend "
                        f"{temp}\u00b0C < {cfg.extruder.minimum_extrude_temp_c}\u00b0C",
                    )
            self._last_jog_time = now
            return SafetyResult(True)

        # Homing check for relative jogs
        homed = {"X": state.homed_x, "Y": state.homed_y, "Z": state.homed_z}
        if axis in homed and not homed[axis]:
            if not cfg.safety.allow_unhomed_relative_jog:
                return SafetyResult(False, f"{axis} axis not homed")

        # Soft-limit check (only when position is known)
        pos_map = {"X": state.x, "Y": state.y, "Z": state.z}
        current = pos_map.get(axis)
        if current is not None:
            new_pos = current + distance_mm
            limits = {
                "X": (cfg.bed.x_min, cfg.bed.x_max),
                "Y": (cfg.bed.y_min, cfg.bed.y_max),
                "Z": (cfg.bed.z_min, cfg.bed.z_max),
            }
            if axis in limits:
                lo, hi = limits[axis]
                if new_pos < lo or new_pos > hi:
                    return SafetyResult(
                        False,
                        f"Move would exceed {axis} limits: "
                        f"{new_pos:.2f} not in [{lo}, {hi}]",
                    )

        self._last_jog_time = now
        return SafetyResult(True)

    def validate_raw_gcode(self, command: str) -> SafetyResult:
        """Validate a raw G-code command string."""
        stripped = command.strip()
        if not stripped:
            return SafetyResult(False, "Empty command")

        # Strip comments
        if ";" in stripped:
            stripped = stripped[: stripped.index(";")].strip()
        if not stripped:
            return SafetyResult(False, "Empty command after stripping comments")

        # Emergency stop always allowed
        if stripped.upper() == "M112":
            return SafetyResult(True)

        # Denylist
        cmd_code = stripped.split()[0].upper()
        if cmd_code in DENIED_COMMANDS:
            return SafetyResult(False, f"Command {cmd_code} is denied for safety")

        return SafetyResult(True)

    def validate_raw_move(
        self,
        state: PrinterState,
        command: str,
    ) -> SafetyResult:
        """Additional soft-limit check for raw G0/G1 commands."""
        if not state.connected:
            return SafetyResult(False, "Printer not connected")
        if state.locked:
            return SafetyResult(False, "Controller locked")

        cmd_upper = command.strip().upper()
        if not (cmd_upper.startswith("G0 ") or cmd_upper.startswith("G1 ")):
            return SafetyResult(True)

        cfg = self._config.printer
        for axis_letter, (lo, hi) in [
            ("X", (cfg.bed.x_min, cfg.bed.x_max)),
            ("Y", (cfg.bed.y_min, cfg.bed.y_max)),
            ("Z", (cfg.bed.z_min, cfg.bed.z_max)),
        ]:
            m = re.search(rf"{axis_letter}(-?[\d.]+)", cmd_upper)
            if m:
                val = float(m.group(1))
                if val < lo or val > hi:
                    return SafetyResult(
                        False,
                        f"Raw move {axis_letter}{val} exceeds limits [{lo}, {hi}]",
                    )

        return SafetyResult(True)

    def can_emergency_stop(self, state: PrinterState) -> SafetyResult:
        """Emergency stop is always permitted regardless of state."""
        return SafetyResult(True)

    def validate_absolute_position(
        self,
        state: PrinterState,
        x: float | None,
        y: float | None,
        z: float | None,
    ) -> SafetyResult:
        """Validate an absolute target position against bed limits."""
        if not state.connected:
            return SafetyResult(False, "Printer not connected")
        if state.locked:
            return SafetyResult(False, "Controller locked after error")

        cfg = self._config.printer
        for label, val, lo, hi in [
            ("X", x, cfg.bed.x_min, cfg.bed.x_max),
            ("Y", y, cfg.bed.y_min, cfg.bed.y_max),
            ("Z", z, cfg.bed.z_min, cfg.bed.z_max),
        ]:
            if val is not None and (val < lo or val > hi):
                return SafetyResult(
                    False,
                    f"{label}={val:.2f} exceeds limits [{lo}, {hi}]",
                )
        return SafetyResult(True)
