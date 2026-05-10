"""Terminal WASD jog controller.

Reads keypresses and converts them into high-level JogIntents.

# pyright: reportMissingModuleSource=false
Intents are validated by the safety layer and then dispatched as
G-code through the serial worker.  No G-code is sent directly from
a keypress callback.

Platform support:
  - Windows: msvcrt  (primary)
  - Unix:    tty/termios/select

Key mapping (with msvcrt, Shift produces uppercase, Ctrl produces
control codes)::

  w / s       Y+ / Y-
  a / d       X- / X+
  W / S       Z+ / Z-    (Shift held)
  Ctrl+W/S    E+ / E-    (Ctrl held)
  h           Home all
  x / y / z   Home single axis
  p           Query position  (M114)
  t           Query temperature (M105)
  g           Enter raw G-code prompt
  + / -       Increase / decrease jog step
  SPACE       Emergency stop  (M112)
  ESC / q     Quit
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass

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
from .serial_worker import SerialWorker

# Step multipliers
STEP_OPTIONS = [0.1, 0.5, 1.0, 5.0, 10.0, 50.0]


@dataclass
class JogIntent:
    axis: str
    distance_mm: float


# ---------------------------------------------------------------------------
# Platform key reader
# ---------------------------------------------------------------------------

if sys.platform == "win32":
    import msvcrt

    def _read_key() -> str | None:
        """Non-blocking key read on Windows."""
        if not msvcrt.kbhit():
            return None
        ch = msvcrt.getch()
        # Extended / special keys (arrows etc.) — consume second byte, ignore
        if ch in (b"\x00", b"\xe0"):
            msvcrt.getch()
            return None
        return ch.decode("latin-1")

else:
    import select
    import termios
    import tty

    _old_settings = None

    def _enter_raw() -> None:
        global _old_settings
        _old_settings = termios.tcgetattr(sys.stdin)
        tty.setcbreak(sys.stdin.fileno())

    def _leave_raw() -> None:
        if _old_settings:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, _old_settings)

    def _read_key() -> str | None:
        if select.select([sys.stdin], [], [], 0.0)[0]:
            return sys.stdin.read(1)
        return None


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def _clear_screen() -> None:
    if sys.platform == "win32":
        os.system("cls")
    else:
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()


def _render_status(
    state: ThreadSafeState,
    step_idx: int,
    config: AppConfig,
    messages: list[str],
) -> None:
    """Re-draw the terminal status screen."""
    s = state.get()
    cfg = config.printer.jog
    step_xy = STEP_OPTIONS[step_idx]
    step_z = config.printer.jog.z_step_mm * (step_xy / cfg.xy_step_mm)

    _clear_screen()

    port_str = s.port or "N/A"
    fw_str = s.firmware or "unknown"
    pos = (
        f"X={s.x or 0:.2f}  Y={s.y or 0:.2f}  "
        f"Z={s.z or 0:.2f}  E={s.e or 0:.2f}"
    )
    hotend = f"{s.hotend_temp_c or 0:.1f} / {s.hotend_target_c or 0:.1f} \u00b0C"
    bed = f"{s.bed_temp_c or 0:.1f} / {s.bed_target_c or 0:.1f} \u00b0C"

    lines = [
        f"  Connected: {port_str}   Firmware: {fw_str}",
        f"  Position:  {pos}",
        f"  Hotend:    {hotend}",
        f"  Bed:       {bed}",
        f"  Jog step:  XY={step_xy:.1f}mm  Z={step_z:.2f}mm  E={cfg.e_step_mm:.1f}mm",
        "",
    ]

    if s.locked:
        lines.append(f"  *** LOCKED: {s.last_error} ***")
        lines.append("")

    lines += [
        "  Controls:",
        "    W/S         Y +/-",
        "    A/D         X -/+",
        "    Shift+W/S   Z +/-",
        "    Ctrl+W/S    E +/-",
        "    H           Home all",
        "    X/Y/Z       Home single axis",
        "    P           Query position",
        "    T           Query temperature",
        "    G           Type raw G-code",
        "    +/-         Change jog step",
        "    SPACE       Emergency stop",
        "    ESC/Q       Quit",
        "",
    ]

    # Recent messages (last 6)
    if messages:
        lines.append("  Log:")
        for m in messages[-6:]:
            lines.append(f"    {m}")

    sys.stdout.write("\n".join(lines) + "\n")
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# Main jog loop
# ---------------------------------------------------------------------------

def run_jog_loop(
    state: ThreadSafeState,
    worker: SerialWorker,
    safety: SafetyValidator,
    config: AppConfig,
) -> None:
    """Blocking terminal control loop.  Call from a dedicated thread."""
    step_idx = 2  # default 1.0 mm
    messages: list[str] = []
    running = True
    last_render = 0.0

    if sys.platform != "win32":
        _enter_raw()

    def _msg(text: str) -> None:
        messages.append(text)
        if len(messages) > 50:
            messages.pop(0)

    try:
        while running:
            # Render at ~4 Hz
            now = time.monotonic()
            if now - last_render > 0.25:
                _render_status(state, step_idx, config, messages)
                last_render = now

            ch = _read_key()
            if ch is None:
                time.sleep(0.02)
                continue

            cfg = config.printer.jog
            step_xy = STEP_OPTIONS[step_idx]
            step_z = cfg.z_step_mm * (step_xy / cfg.xy_step_mm)
            intent: JogIntent | None = None

            # --- movement keys ------------------------------------------------
            if ch == "w":
                intent = JogIntent("Y", step_xy)
            elif ch == "s":
                intent = JogIntent("Y", -step_xy)
            elif ch == "a":
                intent = JogIntent("X", -step_xy)
            elif ch == "d":
                intent = JogIntent("X", step_xy)
            elif ch == "W":  # Shift+W
                intent = JogIntent("Z", step_z)
            elif ch == "S":  # Shift+S
                intent = JogIntent("Z", -step_z)
            elif ch == "\x17":  # Ctrl+W
                intent = JogIntent("E", cfg.e_step_mm)
            elif ch == "\x13":  # Ctrl+S
                intent = JogIntent("E", -cfg.e_step_mm)

            # --- homing -------------------------------------------------------
            elif ch == "h":
                worker.send(home_all())
                state.update(homed_x=True, homed_y=True, homed_z=True)
                _msg("Homing all axes")
            elif ch == "x":
                worker.send(home_axis("X"))
                state.update(homed_x=True)
                _msg("Homing X")
            elif ch == "y":
                worker.send(home_axis("Y"))
                state.update(homed_y=True)
                _msg("Homing Y")
            elif ch == "z":
                worker.send(home_axis("Z"))
                state.update(homed_z=True)
                _msg("Homing Z")

            # --- queries ------------------------------------------------------
            elif ch == "p":
                worker.send(get_position())
            elif ch == "t":
                worker.send(get_temperature())

            # --- step size ----------------------------------------------------
            elif ch in ("+", "="):
                step_idx = min(step_idx + 1, len(STEP_OPTIONS) - 1)
                _msg(f"Jog step -> {STEP_OPTIONS[step_idx]:.1f} mm")
            elif ch in ("-", "_"):
                step_idx = max(step_idx - 1, 0)
                _msg(f"Jog step -> {STEP_OPTIONS[step_idx]:.1f} mm")

            # --- raw G-code ---------------------------------------------------
            elif ch == "g":
                _enter_gcode_prompt(worker, safety, state, _msg)

            # --- emergency stop -----------------------------------------------
            elif ch == " ":
                worker.send_immediate(emergency_stop())
                state.update(locked=True, last_error="Emergency stop (M112)")
                _msg("EMERGENCY STOP sent")

            # --- quit ---------------------------------------------------------
            elif ch in ("\x1b", "q"):
                running = False
                continue

            # --- process jog intent -------------------------------------------
            if intent:
                snap = state.get()
                result = safety.validate_jog(snap, intent.axis, intent.distance_mm)
                if result.allowed:
                    feedrate = _feedrate_for(intent.axis, config)
                    kwargs = {intent.axis.lower(): intent.distance_mm}
                    cmds = move_relative(feedrate=feedrate, **kwargs)
                    for cmd in cmds:
                        worker.send(cmd)
                    _msg(
                        f"Jog {intent.axis} "
                        f"{'+' if intent.distance_mm > 0 else ''}"
                        f"{intent.distance_mm:.3f} mm"
                    )
                else:
                    _msg(f"BLOCKED: {result.reason}")
    finally:
        if sys.platform != "win32":
            _leave_raw()


def _feedrate_for(axis: str, config: AppConfig) -> int:
    axis = axis.upper()
    jog = config.printer.jog
    if axis in ("X", "Y"):
        return jog.feedrate_xy
    if axis == "Z":
        return jog.feedrate_z
    return jog.feedrate_e


def _enter_gcode_prompt(
    worker: SerialWorker,
    safety: SafetyValidator,
    state: ThreadSafeState,
    msg_fn: object,
) -> None:
    """Temporarily switch to line-input mode for raw G-code entry."""
    _clear_screen()
    sys.stdout.write("  Raw G-code mode (type command, ENTER to send, empty to cancel)\n\n")
    sys.stdout.flush()

    if sys.platform != "win32":
        _leave_raw()

    try:
        line = input("  gcode> ").strip()
    except (EOFError, KeyboardInterrupt):
        line = ""

    if sys.platform != "win32":
        _enter_raw()

    if not line:
        return

    result = safety.validate_raw_gcode(line)
    if not result.allowed:
        msg_fn(f"RAW BLOCKED: {result.reason}")  # type: ignore[operator]
        return

    snap = state.get()
    result2 = safety.validate_raw_move(snap, line)
    if not result2.allowed:
        msg_fn(f"RAW BLOCKED: {result2.reason}")  # type: ignore[operator]
        return

    worker.send(line)
    msg_fn(f"RAW: {line}")  # type: ignore[operator]
