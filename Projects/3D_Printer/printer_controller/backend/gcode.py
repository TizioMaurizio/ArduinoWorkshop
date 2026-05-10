"""G-code builder functions for Marlin-compatible printers.

All printer commands are constructed here.  Call sites should never
format G-code strings manually.
"""

from __future__ import annotations


def g90_absolute_positioning() -> str:
    return "G90"


def g91_relative_positioning() -> str:
    return "G91"


def m82_absolute_extrusion() -> str:
    return "M82"


def m83_relative_extrusion() -> str:
    return "M83"


def home_all() -> str:
    """G28 — home all axes."""
    return "G28"


def home_axis(axis: str) -> str:
    """G28 X / Y / Z — home a single axis."""
    axis = axis.upper()
    if axis not in ("X", "Y", "Z"):
        raise ValueError(f"Invalid axis for homing: {axis}")
    return f"G28 {axis}"


def get_position() -> str:
    """M114 — report current position."""
    return "M114"


def get_temperature() -> str:
    """M105 — report temperatures."""
    return "M105"


def emergency_stop() -> str:
    """M112 — emergency stop (firmware kill)."""
    return "M112"


def motors_off() -> str:
    """M84 — disable stepper motors."""
    return "M84"


def fan_on(speed: int = 255) -> str:
    """M106 — set part-cooling fan speed (0-255)."""
    speed = max(0, min(255, speed))
    return f"M106 S{speed}"


def fan_off() -> str:
    """M107 — turn off part-cooling fan."""
    return "M107"


def move_relative(
    x: float = 0,
    y: float = 0,
    z: float = 0,
    e: float = 0,
    feedrate: int = 1500,
) -> list[str]:
    """Build a safe relative-move G-code sequence.

    * Axis-only moves use G91/G1/G90/M114.
    * Extruder-only moves use M83/G1/M82.
    * Mixed moves are split: axes first, then extruder.
    """
    has_axis = x != 0 or y != 0 or z != 0
    has_extrude = e != 0

    if not has_axis and not has_extrude:
        return []

    commands: list[str] = []

    if has_axis and not has_extrude:
        commands.append("G91")
        parts = ["G1"]
        if x != 0:
            parts.append(f"X{x:.3f}")
        if y != 0:
            parts.append(f"Y{y:.3f}")
        if z != 0:
            parts.append(f"Z{z:.3f}")
        parts.append(f"F{feedrate}")
        commands.append(" ".join(parts))
        commands.append("G90")
        commands.append("M114")

    elif has_extrude and not has_axis:
        commands.append("M83")
        commands.append(f"G1 E{e:.3f} F{feedrate}")
        commands.append("M82")

    else:
        # Split: axes first, then extrusion
        commands.append("G91")
        parts = ["G1"]
        if x != 0:
            parts.append(f"X{x:.3f}")
        if y != 0:
            parts.append(f"Y{y:.3f}")
        if z != 0:
            parts.append(f"Z{z:.3f}")
        parts.append(f"F{feedrate}")
        commands.append(" ".join(parts))
        commands.append("G90")
        commands.append("M83")
        commands.append(f"G1 E{e:.3f} F{feedrate}")
        commands.append("M82")
        commands.append("M114")

    return commands
