"""
Servo Controller GUI
Sends angle values (0-180) over serial to Arduino Uno on COM4.
Wiring: D9~ → Servo Signal, 5V → VCC, GND → GND
"""

import tkinter as tk
from tkinter import ttk, simpledialog
import serial
import serial.tools.list_ports
import threading

PORT = "COM4"
BAUD = 115200


class ServoControllerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Servo Controller")
        self.root.resizable(False, False)
        self.root.configure(bg="#1e1e2e")

        self.ser: serial.Serial | None = None
        self.angle_var = tk.IntVar(value=90)
        self.status_var = tk.StringVar(value="Disconnected")
        self.presets: list[int] = [0, 45, 90, 135, 180]

        self._build_ui()
        self._connect()

    # ── UI ────────────────────────────────────────────────

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TLabel", background="#1e1e2e", foreground="#cdd6f4", font=("Segoe UI", 11))
        style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"), foreground="#89b4fa")
        style.configure("Angle.TLabel", font=("Consolas", 48, "bold"), foreground="#f5c542")
        style.configure("Status.TLabel", font=("Segoe UI", 9), foreground="#a6adc8")
        style.configure("TButton", font=("Segoe UI", 10))
        style.configure("TScale", background="#1e1e2e")

        main = ttk.Frame(self.root, padding=20)
        main.configure(style="TFrame")
        style.configure("TFrame", background="#1e1e2e")
        main.pack(fill="both", expand=True)

        ttk.Label(main, text="Servo Controller", style="Title.TLabel").pack(pady=(0, 10))

        # Angle display
        self.angle_label = ttk.Label(main, text="90°", style="Angle.TLabel")
        self.angle_label.pack(pady=(0, 5))

        # Slider
        slider_frame = ttk.Frame(main)
        slider_frame.pack(fill="x", pady=5)
        ttk.Label(slider_frame, text="0°").pack(side="left")
        self.slider = tk.Scale(
            slider_frame, from_=0, to=180, orient="horizontal",
            variable=self.angle_var, command=self._on_slider,
            bg="#313244", fg="#cdd6f4", troughcolor="#45475a",
            highlightthickness=0, length=300, sliderlength=20,
            font=("Consolas", 9),
        )
        self.slider.pack(side="left", fill="x", expand=True, padx=5)
        ttk.Label(slider_frame, text="180°").pack(side="left")

        # Preset buttons
        self.preset_frame = ttk.Frame(main)
        self.preset_frame.pack(pady=10)
        self._rebuild_presets()

        # Add preset button
        add_frame = ttk.Frame(main)
        add_frame.pack(pady=(0, 5))
        ttk.Button(add_frame, text="+ Add Preset", command=self._add_preset).pack()
        ttk.Label(add_frame, text="Right-click a preset to edit/delete",
                  style="Status.TLabel").pack(pady=(4, 0))

        # Status bar
        ttk.Label(main, textvariable=self.status_var, style="Status.TLabel").pack(pady=(10, 0))

    # ── Serial ────────────────────────────────────────────

    def _connect(self):
        try:
            self.ser = serial.Serial(PORT, BAUD, timeout=1)
            self.status_var.set(f"Connected to {PORT}")
            # Start reader thread
            t = threading.Thread(target=self._reader, daemon=True)
            t.start()
        except serial.SerialException as e:
            self.status_var.set(f"Error: {e}")

    def _reader(self):
        """Read serial responses in background."""
        while self.ser and self.ser.is_open:
            try:
                line = self.ser.readline().decode("utf-8", errors="replace").strip()
                if line:
                    self.root.after(0, self.status_var.set, f"{PORT}: {line}")
            except Exception:
                break

    def _send_angle(self, angle: int):
        if self.ser and self.ser.is_open:
            self.ser.write(f"{angle}\n".encode())

    # ── Callbacks ─────────────────────────────────────────

    def _on_slider(self, _val: str):
        angle = self.angle_var.get()
        self.angle_label.config(text=f"{angle}°")
        self._send_angle(angle)

    def _set_angle(self, angle: int):
        self.angle_var.set(angle)
        self.angle_label.config(text=f"{angle}°")
        self._send_angle(angle)

    # ── Preset management ─────────────────────────────────

    def _rebuild_presets(self):
        for w in self.preset_frame.winfo_children():
            w.destroy()
        for i, angle in enumerate(self.presets):
            btn = ttk.Button(self.preset_frame, text=f"{angle}°",
                             command=lambda a=angle: self._set_angle(a))
            btn.pack(side="left", padx=4)
            btn.bind("<Button-3>", lambda e, idx=i: self._preset_context_menu(e, idx))

    def _preset_context_menu(self, event: tk.Event, idx: int):
        menu = tk.Menu(self.root, tearoff=0, bg="#313244", fg="#cdd6f4",
                       activebackground="#45475a", activeforeground="#cdd6f4")
        menu.add_command(label="Edit", command=lambda: self._edit_preset(idx))
        menu.add_command(label="Delete", command=lambda: self._delete_preset(idx))
        menu.tk_popup(event.x_root, event.y_root)

    def _add_preset(self):
        val = simpledialog.askinteger("Add Preset", "Angle (0–180):",
                                     minvalue=0, maxvalue=180, parent=self.root)
        if val is not None:
            self.presets.append(val)
            self.presets.sort()
            self._rebuild_presets()

    def _edit_preset(self, idx: int):
        val = simpledialog.askinteger("Edit Preset", "New angle (0–180):",
                                     initialvalue=self.presets[idx],
                                     minvalue=0, maxvalue=180, parent=self.root)
        if val is not None:
            self.presets[idx] = val
            self.presets.sort()
            self._rebuild_presets()

    def _delete_preset(self, idx: int):
        del self.presets[idx]
        self._rebuild_presets()

    def destroy(self):
        if self.ser and self.ser.is_open:
            self.ser.close()


def main():
    root = tk.Tk()
    app = ServoControllerApp(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.destroy(), root.destroy()))
    root.mainloop()


if __name__ == "__main__":
    main()
