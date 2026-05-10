"""Tkinter GUI for the 3D printer controller.

Provides jog controls, connection management, temperature/position
readout, raw G-code input, emergency stop, and a scrolling log — all
without needing any extra Python packages beyond the standard library.
"""

from __future__ import annotations

import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from typing import Optional

from .config import AppConfig
from .gcode import (
    emergency_stop,
    get_position,
    get_temperature,
    home_all,
    home_axis,
    move_relative,
    motors_off,
    fan_on,
    fan_off,
)
from .printer_state import ThreadSafeState
from .safety import SafetyValidator
from .serial_worker import (
    SerialWorker,
    auto_discover,
    list_serial_ports_detailed,
)

# Step sizes available in the GUI
STEP_OPTIONS = [0.1, 0.5, 1.0, 5.0, 10.0, 50.0]
Z_STEP_OPTIONS = [0.05, 0.1, 0.5, 1.0, 5.0, 10.0]
E_STEP_OPTIONS = [0.5, 1.0, 2.0, 5.0, 10.0]

# Colours
CLR_BG = "#1e1e2e"
CLR_FRAME = "#2a2a3d"
CLR_BTN = "#3a3a55"
CLR_BTN_ACTIVE = "#50507a"
CLR_ESTOP = "#cc2222"
CLR_ESTOP_ACTIVE = "#ff3333"
CLR_CONNECT = "#22aa44"
CLR_DISCONNECT = "#cc8822"
CLR_TEXT = "#e0e0e0"
CLR_DIM = "#888899"
CLR_ACCENT = "#5599ff"
CLR_WARN = "#ffaa22"
CLR_ERR = "#ff4444"
CLR_OK = "#44cc66"


# ---------------------------------------------------------------------------
# Jog coalescing buffer
# ---------------------------------------------------------------------------

class JogBuffer:
    """Coalesces rapid jog requests so only one move is in-flight at a time.

    When a new jog is requested while one is already in-flight, the distances
    are accumulated per-axis. When the in-flight move completes, the
    accumulated delta is sent as a single command. This prevents command queue
    flooding from rapid button presses or key repeats.
    """

    def __init__(
        self,
        worker: SerialWorker,
        state: ThreadSafeState,
        safety: SafetyValidator,
        config: AppConfig,
        log_fn: object,
    ) -> None:
        self._worker = worker
        self._state = state
        self._safety = safety
        self._config = config
        self._log_fn = log_fn
        self._lock = threading.Lock()

        # Pending distances per axis (accumulated while in-flight)
        self._pending: dict[str, float] = {"X": 0.0, "Y": 0.0, "Z": 0.0, "E": 0.0}

        # Whether a jog move is currently being executed by the printer
        self._in_flight = False

        # How many ok's we expect before the current jog batch is "done"
        self._oks_remaining = 0

    def request_jog(self, axis: str, distance_mm: float, feedrate: int) -> None:
        """Request a jog move.  May be coalesced with pending moves."""
        axis = axis.upper()

        with self._lock:
            self._pending[axis] += distance_mm

            if self._in_flight:
                # Move already in progress — just accumulate
                self._log_fn(
                    f"Jog {axis} {'+' if distance_mm > 0 else ''}{distance_mm:.3f} mm (buffered)",
                    "debug",
                )
                return

        # Nothing in flight — dispatch immediately
        self._dispatch()

    def on_ok_received(self) -> None:
        """Called by the serial worker when an 'ok' is received.

        Decrements the expected ok count. When all ok's for the current
        jog batch are received, dispatches the next pending batch (if any).
        """
        with self._lock:
            if not self._in_flight:
                return
            self._oks_remaining -= 1
            if self._oks_remaining <= 0:
                self._in_flight = False

        # Check if there's more pending work
        self._dispatch()

    def cancel(self) -> None:
        """Cancel all pending jog commands (e.g. on emergency stop)."""
        with self._lock:
            self._pending = {"X": 0.0, "Y": 0.0, "Z": 0.0, "E": 0.0}
            self._in_flight = False
            self._oks_remaining = 0

    def _dispatch(self) -> None:
        """Send the accumulated pending jog as a single move if any."""
        with self._lock:
            # Collect non-zero axes
            to_send: dict[str, float] = {}
            for ax in ("X", "Y", "Z", "E"):
                if abs(self._pending[ax]) > 0.0001:
                    to_send[ax] = self._pending[ax]
                    self._pending[ax] = 0.0

            if not to_send:
                return

            self._in_flight = True

        # Validate the coalesced move
        snap = self._state.get()
        for axis, dist in list(to_send.items()):
            result = self._safety.validate_jog(snap, axis, dist)
            if not result.allowed:
                self._log_fn(f"BLOCKED: {result.reason}", "warning")
                # Remove this axis from the dispatch
                del to_send[axis]

        if not to_send:
            with self._lock:
                self._in_flight = False
            return

        # Build and send G-code
        # Split axes and extruder for proper G-code sequences
        axis_move = {k.lower(): v for k, v in to_send.items() if k in ("X", "Y", "Z")}
        e_move = to_send.get("E", 0.0)

        cmds: list[str] = []
        if axis_move:
            feedrate = self._best_feedrate(to_send)
            cmds.extend(move_relative(feedrate=feedrate, **axis_move))
        if abs(e_move) > 0.0001:
            feedrate_e = self._config.printer.jog.feedrate_e
            cmds.extend(move_relative(feedrate=feedrate_e, e=e_move))

        with self._lock:
            self._oks_remaining = sum(1 for c in cmds if self._expects_ok(c))

        for cmd in cmds:
            self._worker.send(cmd)

        # Log the coalesced move
        parts = [f"{ax}{'+' if d > 0 else ''}{d:.3f}" for ax, d in to_send.items()]
        self._log_fn(f"Jog sent: {' '.join(parts)} mm")

    def _best_feedrate(self, axes: dict[str, float]) -> int:
        """Pick the slowest feedrate among requested axes."""
        jog = self._config.printer.jog
        rates = []
        if "X" in axes or "Y" in axes:
            rates.append(jog.feedrate_xy)
        if "Z" in axes:
            rates.append(jog.feedrate_z)
        return min(rates) if rates else jog.feedrate_xy

    @staticmethod
    def _expects_ok(cmd: str) -> bool:
        """Return True if this command will produce an 'ok' response."""
        # All G/M commands produce an ok in Marlin
        upper = cmd.strip().upper()
        return upper.startswith("G") or upper.startswith("M")


class PrinterGUI:
    """Main GUI window — runs the tkinter mainloop on the calling thread."""

    def __init__(
        self,
        state: ThreadSafeState,
        worker: SerialWorker,
        safety: SafetyValidator,
        config: AppConfig,
    ) -> None:
        self._state = state
        self._worker = worker
        self._safety = safety
        self._config = config

        self._root = tk.Tk()
        self._root.title("3D Printer Controller")
        self._root.configure(bg=CLR_BG)
        self._root.minsize(920, 660)
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Keyboard bindings for jog — bind_all so it fires regardless of
        # which widget has focus (buttons, comboboxes, etc.)
        self._root.bind_all("<KeyPress>", self._on_key)

        # Reclaim focus after mouse clicks on non-entry widgets so that
        # subsequent key presses continue to fire jog commands.
        self._root.bind_all("<ButtonRelease-1>", self._reclaim_focus)

        # Variables
        self._port_var = tk.StringVar()
        self._xy_step_var = tk.DoubleVar(value=1.0)
        self._z_step_var = tk.DoubleVar(value=0.1)
        self._e_step_var = tk.DoubleVar(value=1.0)
        self._gcode_var = tk.StringVar()

        self._build_ui()

        # Jog buffer (must be created after _build_ui so _log is available)
        self._jog_buffer = JogBuffer(
            worker, state, safety, config, log_fn=self._log,
        )

        # Register ok callback so jog buffer knows when moves complete
        self._worker.register_ok_callback(self._jog_buffer.on_ok_received)

        # Periodic state refresh
        self._poll_state()

    # -----------------------------------------------------------------------
    # UI construction
    # -----------------------------------------------------------------------

    def _build_ui(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background=CLR_BG)
        style.configure("Card.TFrame", background=CLR_FRAME, relief="flat")
        style.configure("TLabel", background=CLR_BG, foreground=CLR_TEXT, font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 11, "bold"), foreground=CLR_ACCENT)
        style.configure("Status.TLabel", font=("Consolas", 10))
        style.configure("Dim.TLabel", foreground=CLR_DIM)
        style.configure("Warn.TLabel", foreground=CLR_WARN)
        style.configure("Err.TLabel", foreground=CLR_ERR)
        style.configure("Ok.TLabel", foreground=CLR_OK)
        style.configure("TButton", font=("Segoe UI", 10))
        style.configure("TCombobox", font=("Segoe UI", 10))

        # Root grid: 2 columns — left (controls), right (log)
        self._root.columnconfigure(0, weight=1)
        self._root.columnconfigure(1, weight=1)
        self._root.rowconfigure(0, weight=1)

        left = ttk.Frame(self._root)
        left.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)
        left.columnconfigure(0, weight=1)

        right = ttk.Frame(self._root)
        right.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=8)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        self._build_log_frame(right)

        self._build_connection_frame(left)
        self._build_status_frame(left)
        self._build_jog_frame(left)
        self._build_actions_frame(left)
        self._build_gcode_frame(left)
        self._build_estop_button(left)

    # -- Connection ---------------------------------------------------------

    def _build_connection_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="  Connection  ", style="Card.TFrame")
        frame.grid(sticky="ew", pady=(0, 6))
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Port:", style="TLabel").grid(row=0, column=0, padx=6, pady=4)
        self._port_combo = ttk.Combobox(
            frame, textvariable=self._port_var, width=18, state="readonly"
        )
        self._port_combo.grid(row=0, column=1, padx=4, pady=4, sticky="ew")

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=0, column=2, padx=4, pady=4)

        self._refresh_btn = tk.Button(
            btn_frame, text="↻", width=3, command=self._refresh_ports,
            bg=CLR_BTN, fg=CLR_TEXT, activebackground=CLR_BTN_ACTIVE,
            relief="flat", font=("Segoe UI", 10),
        )
        self._refresh_btn.pack(side="left", padx=2)

        self._connect_btn = tk.Button(
            btn_frame, text="Connect", width=9, command=self._connect,
            bg=CLR_CONNECT, fg="white", activebackground="#33bb55",
            relief="flat", font=("Segoe UI", 10, "bold"),
        )
        self._connect_btn.pack(side="left", padx=2)

        self._disconnect_btn = tk.Button(
            btn_frame, text="Disconnect", width=9, command=self._disconnect,
            bg=CLR_DISCONNECT, fg="white", activebackground="#ddaa33",
            relief="flat", font=("Segoe UI", 10),
            state="disabled",
        )
        self._disconnect_btn.pack(side="left", padx=2)

        # Auto-discover button
        self._auto_btn = tk.Button(
            frame, text="Auto-Discover", command=self._auto_discover,
            bg=CLR_ACCENT, fg="white", activebackground="#6688ff",
            relief="flat", font=("Segoe UI", 10, "bold"),
        )
        self._auto_btn.grid(row=1, column=0, columnspan=2, padx=6, pady=(0, 6), sticky="ew")

        # Mock button
        self._mock_btn = tk.Button(
            frame, text="Mock Printer", command=self._connect_mock,
            bg=CLR_BTN, fg=CLR_TEXT, activebackground=CLR_BTN_ACTIVE,
            relief="flat", font=("Segoe UI", 10),
        )
        self._mock_btn.grid(row=1, column=2, padx=4, pady=(0, 6), sticky="ew")

        self._conn_status = ttk.Label(frame, text="Disconnected", style="Warn.TLabel")
        self._conn_status.grid(row=2, column=0, columnspan=3, padx=6, pady=(0, 6))

        self._refresh_ports()

    # -- Status -------------------------------------------------------------

    def _build_status_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="  Printer Status  ", style="Card.TFrame")
        frame.grid(sticky="ew", pady=(0, 6))
        frame.columnconfigure(1, weight=1)

        labels = [
            ("Firmware:", "fw_lbl"),
            ("Position:", "pos_lbl"),
            ("Hotend:", "hotend_lbl"),
            ("Bed:", "bed_lbl"),
            ("State:", "state_lbl"),
        ]
        for i, (text, attr) in enumerate(labels):
            ttk.Label(frame, text=text, style="TLabel").grid(
                row=i, column=0, padx=6, pady=2, sticky="w"
            )
            lbl = ttk.Label(frame, text="—", style="Status.TLabel")
            lbl.grid(row=i, column=1, padx=6, pady=2, sticky="w")
            setattr(self, f"_{attr}", lbl)

    # -- Jog controls -------------------------------------------------------

    def _build_jog_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="  Jog Controls  ", style="Card.TFrame")
        frame.grid(sticky="ew", pady=(0, 6))

        # --- Step size selectors ---
        step_frame = ttk.Frame(frame)
        step_frame.grid(row=0, column=0, columnspan=3, padx=6, pady=(4, 2), sticky="ew")

        ttk.Label(step_frame, text="XY step:").pack(side="left", padx=(0, 4))
        xy_combo = ttk.Combobox(
            step_frame, textvariable=self._xy_step_var,
            values=[str(s) for s in STEP_OPTIONS], width=6, state="readonly",
        )
        xy_combo.pack(side="left", padx=(0, 12))
        xy_combo.set("1.0")

        ttk.Label(step_frame, text="Z step:").pack(side="left", padx=(0, 4))
        z_combo = ttk.Combobox(
            step_frame, textvariable=self._z_step_var,
            values=[str(s) for s in Z_STEP_OPTIONS], width=6, state="readonly",
        )
        z_combo.pack(side="left", padx=(0, 12))
        z_combo.set("0.1")

        ttk.Label(step_frame, text="E step:").pack(side="left", padx=(0, 4))
        e_combo = ttk.Combobox(
            step_frame, textvariable=self._e_step_var,
            values=[str(s) for s in E_STEP_OPTIONS], width=6, state="readonly",
        )
        e_combo.pack(side="left")
        e_combo.set("1.0")

        # --- XY pad ---
        xy_frame = ttk.Frame(frame)
        xy_frame.grid(row=1, column=0, padx=6, pady=4)

        ttk.Label(xy_frame, text="XY", style="Title.TLabel").grid(row=0, column=0, columnspan=3)
        self._jog_btn(xy_frame, "Y+", 1, 1, lambda: self._jog("Y", 1))
        self._jog_btn(xy_frame, "X-", 2, 0, lambda: self._jog("X", -1))
        self._jog_btn(xy_frame, "⌂",  2, 1, lambda: self._home_all(), width=5)
        self._jog_btn(xy_frame, "X+", 2, 2, lambda: self._jog("X", 1))
        self._jog_btn(xy_frame, "Y-", 3, 1, lambda: self._jog("Y", -1))

        # --- Z pad ---
        z_frame = ttk.Frame(frame)
        z_frame.grid(row=1, column=1, padx=12, pady=4)

        ttk.Label(z_frame, text="Z", style="Title.TLabel").grid(row=0, column=0)
        self._jog_btn(z_frame, "Z+", 1, 0, lambda: self._jog("Z", 1))
        self._jog_btn(z_frame, "Z-", 2, 0, lambda: self._jog("Z", -1))

        # --- E pad ---
        e_frame = ttk.Frame(frame)
        e_frame.grid(row=1, column=2, padx=6, pady=4)

        ttk.Label(e_frame, text="Extruder", style="Title.TLabel").grid(row=0, column=0)
        self._jog_btn(e_frame, "E+", 1, 0, lambda: self._jog("E", 1))
        self._jog_btn(e_frame, "E-", 2, 0, lambda: self._jog("E", -1))

    def _jog_btn(
        self, parent: ttk.Frame, text: str, row: int, col: int,
        cmd: object, width: int = 5,
    ) -> tk.Button:
        btn = tk.Button(
            parent, text=text, width=width, command=cmd,
            bg=CLR_BTN, fg=CLR_TEXT, activebackground=CLR_BTN_ACTIVE,
            relief="flat", font=("Segoe UI", 11, "bold"),
        )
        btn.grid(row=row, column=col, padx=2, pady=2)
        return btn

    # -- Action buttons -----------------------------------------------------

    def _build_actions_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="  Actions  ", style="Card.TFrame")
        frame.grid(sticky="ew", pady=(0, 6))

        btns = [
            ("Home All", self._home_all),
            ("Home X", lambda: self._home_axis("X")),
            ("Home Y", lambda: self._home_axis("Y")),
            ("Home Z", lambda: self._home_axis("Z")),
            ("Get Pos", self._query_position),
            ("Get Temp", self._query_temp),
            ("Motors Off", self._motors_off),
            ("Fan On", self._fan_on),
            ("Fan Off", self._fan_off),
        ]
        for i, (text, cmd) in enumerate(btns):
            tk.Button(
                frame, text=text, width=9, command=cmd,
                bg=CLR_BTN, fg=CLR_TEXT, activebackground=CLR_BTN_ACTIVE,
                relief="flat", font=("Segoe UI", 9),
            ).grid(row=i // 5, column=i % 5, padx=3, pady=3)

    # -- Raw G-code ---------------------------------------------------------

    def _build_gcode_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="  Raw G-code  ", style="Card.TFrame")
        frame.grid(sticky="ew", pady=(0, 6))
        frame.columnconfigure(0, weight=1)

        entry = ttk.Entry(frame, textvariable=self._gcode_var, font=("Consolas", 11))
        entry.grid(row=0, column=0, padx=6, pady=6, sticky="ew")
        entry.bind("<Return>", lambda _: self._send_raw_gcode())

        tk.Button(
            frame, text="Send", width=8, command=self._send_raw_gcode,
            bg=CLR_ACCENT, fg="white", activebackground="#6688ff",
            relief="flat", font=("Segoe UI", 10, "bold"),
        ).grid(row=0, column=1, padx=(0, 6), pady=6)

    # -- Emergency stop -----------------------------------------------------

    def _build_estop_button(self, parent: ttk.Frame) -> None:
        self._estop_btn = tk.Button(
            parent, text="⚠  EMERGENCY STOP  ⚠", command=self._emergency_stop,
            bg=CLR_ESTOP, fg="white", activebackground=CLR_ESTOP_ACTIVE,
            relief="flat", font=("Segoe UI", 14, "bold"), height=2,
        )
        self._estop_btn.grid(sticky="ew", pady=(0, 4))

    # -- Log panel ----------------------------------------------------------

    def _build_log_frame(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Log", style="Title.TLabel").grid(
            row=0, column=0, sticky="w", padx=4
        )
        self._log_text = scrolledtext.ScrolledText(
            parent, wrap="word", font=("Consolas", 9),
            bg="#181825", fg=CLR_TEXT, insertbackground=CLR_TEXT,
            relief="flat", state="disabled", height=30,
        )
        self._log_text.grid(row=1, column=0, sticky="nsew", pady=(2, 0))
        self._log_text.tag_configure("info", foreground=CLR_TEXT)
        self._log_text.tag_configure("warning", foreground=CLR_WARN)
        self._log_text.tag_configure("error", foreground=CLR_ERR)
        self._log_text.tag_configure("debug", foreground=CLR_DIM)

    # -----------------------------------------------------------------------
    # Actions
    # -----------------------------------------------------------------------

    def _log(self, message: str, level: str = "info") -> None:
        ts = time.strftime("%H:%M:%S")
        self._log_text.configure(state="normal")
        self._log_text.insert("end", f"[{ts}] {message}\n", level)
        self._log_text.see("end")
        self._log_text.configure(state="disabled")

    def _refresh_ports(self) -> None:
        ports = list_serial_ports_detailed()
        display = [f"{p.device} — {p.description} (score {p.score})" for p in ports]
        devices = [p.device for p in ports]
        self._port_combo["values"] = display
        self._port_devices = devices
        if display:
            self._port_combo.current(0)
        self._log(f"Found {len(ports)} serial port(s)")

    def _selected_port(self) -> Optional[str]:
        idx = self._port_combo.current()
        if idx < 0 or idx >= len(self._port_devices):
            return None
        return self._port_devices[idx]

    def _connect(self) -> None:
        port = self._selected_port()
        if not port:
            self._log("No port selected", "warning")
            return
        self._log(f"Connecting to {port}…")
        self._set_buttons_connecting()

        def _do() -> None:
            ok = self._worker.connect(port)
            self._root.after(0, lambda: self._on_connected(ok, port))

        threading.Thread(target=_do, daemon=True).start()

    def _connect_mock(self) -> None:
        self._log("Starting mock printer…")
        self._set_buttons_connecting()

        def _do() -> None:
            ok = self._worker.connect_mock()
            self._root.after(0, lambda: self._on_connected(ok, "MOCK"))

        threading.Thread(target=_do, daemon=True).start()

    def _auto_discover(self) -> None:
        self._log("Auto-discovering printer… (this may take 10-20 s)")
        self._set_buttons_connecting()

        def _do() -> None:
            port, baud, firmware = auto_discover(
                self._config.printer.baud_candidates,
                timeout_s=self._config.printer.serial.timeout_s,
            )
            if port and baud:
                self._root.after(0, lambda: self._log(
                    f"Discovered {firmware} on {port} @ {baud}", "info"
                ))
                ok = self._worker.connect(port, baud)
                self._root.after(0, lambda: self._on_connected(ok, port))
            else:
                self._root.after(0, lambda: self._on_discover_failed())

        threading.Thread(target=_do, daemon=True).start()

    def _on_connected(self, ok: bool, port: str) -> None:
        if ok:
            self._conn_status.configure(text=f"Connected: {port}", style="Ok.TLabel")
            self._connect_btn.configure(state="disabled")
            self._auto_btn.configure(state="disabled")
            self._mock_btn.configure(state="disabled")
            self._disconnect_btn.configure(state="normal")
            self._log(f"Connected to {port}", "info")
        else:
            self._conn_status.configure(text="Connection failed", style="Err.TLabel")
            self._set_buttons_disconnected()
            self._log(f"Failed to connect to {port}", "error")

    def _on_discover_failed(self) -> None:
        self._conn_status.configure(text="No printer found", style="Err.TLabel")
        self._set_buttons_disconnected()
        self._log("Auto-discovery found no Marlin printer", "error")

    def _disconnect(self) -> None:
        self._worker.disconnect()
        self._conn_status.configure(text="Disconnected", style="Warn.TLabel")
        self._set_buttons_disconnected()
        self._log("Disconnected")

    def _set_buttons_connecting(self) -> None:
        self._connect_btn.configure(state="disabled")
        self._auto_btn.configure(state="disabled")
        self._mock_btn.configure(state="disabled")
        self._disconnect_btn.configure(state="disabled")
        self._conn_status.configure(text="Connecting…", style="TLabel")

    def _set_buttons_disconnected(self) -> None:
        self._connect_btn.configure(state="normal")
        self._auto_btn.configure(state="normal")
        self._mock_btn.configure(state="normal")
        self._disconnect_btn.configure(state="disabled")

    # -- Jog ----------------------------------------------------------------

    def _jog(self, axis: str, direction: int) -> None:
        axis = axis.upper()
        if axis in ("X", "Y"):
            step = self._xy_step_var.get() * direction
        elif axis == "Z":
            step = self._z_step_var.get() * direction
        else:
            step = self._e_step_var.get() * direction

        feedrate = self._feedrate_for(axis)
        self._jog_buffer.request_jog(axis, step, feedrate)

    def _feedrate_for(self, axis: str) -> int:
        jog = self._config.printer.jog
        if axis in ("X", "Y"):
            return jog.feedrate_xy
        if axis == "Z":
            return jog.feedrate_z
        return jog.feedrate_e

    # -- Homing / queries ---------------------------------------------------

    def _home_all(self) -> None:
        self._worker.send(home_all())
        self._state.update(homed_x=True, homed_y=True, homed_z=True)
        self._log("Homing all axes")

    def _home_axis(self, axis: str) -> None:
        self._worker.send(home_axis(axis))
        self._state.update(**{f"homed_{axis.lower()}": True})
        self._log(f"Homing {axis}")

    def _query_position(self) -> None:
        self._worker.send(get_position())

    def _query_temp(self) -> None:
        self._worker.send(get_temperature())

    def _motors_off(self) -> None:
        self._worker.send(motors_off())
        self._log("Motors disabled")

    def _fan_on(self) -> None:
        self._worker.send(fan_on())
        self._log("Fan ON (255)")

    def _fan_off(self) -> None:
        self._worker.send(fan_off())
        self._log("Fan OFF")

    # -- Raw G-code ---------------------------------------------------------

    def _send_raw_gcode(self) -> None:
        raw = self._gcode_var.get().strip()
        if not raw:
            return
        result = self._safety.validate_raw_gcode(raw)
        if not result.allowed:
            self._log(f"DENIED: {result.reason}", "warning")
            return
        snap = self._state.get()
        result2 = self._safety.validate_raw_move(snap, raw)
        if not result2.allowed:
            self._log(f"DENIED: {result2.reason}", "warning")
            return
        self._worker.send(raw)
        self._log(f"Sent: {raw}")
        self._gcode_var.set("")

    # -- Emergency stop -----------------------------------------------------

    def _emergency_stop(self) -> None:
        self._jog_buffer.cancel()
        self._worker.send_immediate(emergency_stop())
        self._state.update(locked=True, last_error="Emergency stop (M112)")
        self._log("⚠ EMERGENCY STOP ⚠", "error")

    # -- Keyboard bindings --------------------------------------------------

    def _on_key(self, event: tk.Event) -> None:
        # Don't capture when typing in an Entry, Text, or open Combobox
        w = event.widget
        if isinstance(w, (tk.Entry, ttk.Entry, ttk.Combobox, tk.Text,
                          scrolledtext.ScrolledText)):
            return

        key = event.keysym
        ctrl = bool(event.state & 0x0004)
        shift = bool(event.state & 0x0001)

        if key == "space":
            self._emergency_stop()
        elif key == "Escape":
            self._emergency_stop()
        elif key.lower() == "w":
            if ctrl:
                self._jog("E", 1)
            elif shift:
                self._jog("Z", 1)
            else:
                self._jog("Y", 1)
        elif key.lower() == "s":
            if ctrl:
                self._jog("E", -1)
            elif shift:
                self._jog("Z", -1)
            else:
                self._jog("Y", -1)
        elif key.lower() == "a":
            self._jog("X", -1)
        elif key.lower() == "d":
            self._jog("X", 1)
        elif key.lower() == "h":
            self._home_all()
        elif key.lower() == "p":
            self._query_position()
        elif key.lower() == "t":
            self._query_temp()

    def _reclaim_focus(self, event: tk.Event) -> None:
        """Return focus to root after clicking non-input widgets."""
        w = event.widget
        if not isinstance(w, (tk.Entry, ttk.Entry, ttk.Combobox, tk.Text,
                              scrolledtext.ScrolledText)):
            self._root.focus_set()

    # -- Periodic state refresh ---------------------------------------------

    def _poll_state(self) -> None:
        s = self._state.get()

        # Firmware
        self._fw_lbl.configure(text=s.firmware or "—")

        # Position
        x = f"{s.x:.2f}" if s.x is not None else "?"
        y = f"{s.y:.2f}" if s.y is not None else "?"
        z = f"{s.z:.2f}" if s.z is not None else "?"
        e = f"{s.e:.2f}" if s.e is not None else "?"
        self._pos_lbl.configure(text=f"X={x}  Y={y}  Z={z}  E={e}")

        # Temperatures
        ht = f"{s.hotend_temp_c:.1f}" if s.hotend_temp_c is not None else "?"
        htt = f"{s.hotend_target_c:.1f}" if s.hotend_target_c is not None else "?"
        self._hotend_lbl.configure(text=f"{ht} / {htt} °C")

        bt = f"{s.bed_temp_c:.1f}" if s.bed_temp_c is not None else "?"
        btt = f"{s.bed_target_c:.1f}" if s.bed_target_c is not None else "?"
        self._bed_lbl.configure(text=f"{bt} / {btt} °C")

        # State
        if s.locked:
            self._state_lbl.configure(
                text=f"LOCKED: {s.last_error or 'unknown'}", style="Err.TLabel"
            )
        elif s.busy:
            self._state_lbl.configure(text="Busy", style="Warn.TLabel")
        elif s.connected:
            homed = []
            if s.homed_x:
                homed.append("X")
            if s.homed_y:
                homed.append("Y")
            if s.homed_z:
                homed.append("Z")
            h_str = ",".join(homed) if homed else "none"
            self._state_lbl.configure(text=f"Ready — homed: {h_str}", style="Ok.TLabel")
        else:
            self._state_lbl.configure(text="Disconnected", style="Warn.TLabel")

        # Connection status sync
        if s.connected and "Disconnect" in self._conn_status.cget("text"):
            pass  # already shows disconnect
        elif s.connected and "Connected" not in self._conn_status.cget("text"):
            port_str = s.port or "?"
            self._conn_status.configure(text=f"Connected: {port_str}", style="Ok.TLabel")
            self._connect_btn.configure(state="disabled")
            self._auto_btn.configure(state="disabled")
            self._mock_btn.configure(state="disabled")
            self._disconnect_btn.configure(state="normal")

        self._root.after(200, self._poll_state)

    # -----------------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------------

    def _on_close(self) -> None:
        if self._worker.is_connected:
            if not messagebox.askokcancel(
                "Quit", "Printer is still connected. Disconnect and quit?"
            ):
                return
            self._worker.disconnect()
        self._root.destroy()

    def run(self) -> None:
        """Start the tkinter mainloop (blocking)."""
        self._root.mainloop()
