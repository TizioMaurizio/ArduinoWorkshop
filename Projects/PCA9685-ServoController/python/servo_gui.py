"""
PCA9685 Servo Controller GUI
Sends angle commands to Arduino over serial.
Protocol: "<channel>,<angle>\n"
"""

import sys
import tkinter as tk
from tkinter import ttk
import serial
import serial.tools.list_ports

NUM_CHANNELS = 16
DEFAULT_ANGLE = 90
BAUD_RATE = 115200


class ServoGui:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("PCA9685 Servo Controller")
        self.ser: serial.Serial | None = None
        self.sliders: list[tk.Scale] = []
        self.angle_vars: list[tk.IntVar] = []

        self._build_port_frame()
        self._build_slider_frame()
        self._build_status_bar()

    # --- UI construction ------------------------------------------------------

    def _build_port_frame(self):
        frame = ttk.LabelFrame(self.root, text="Serial Port")
        frame.pack(fill="x", padx=8, pady=(8, 4))

        self.port_var = tk.StringVar()
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo = ttk.Combobox(
            frame, textvariable=self.port_var, values=ports, width=20
        )
        self.port_combo.pack(side="left", padx=4, pady=4)
        if ports:
            self.port_combo.current(0)

        self.refresh_btn = ttk.Button(
            frame, text="Refresh", command=self._refresh_ports
        )
        self.refresh_btn.pack(side="left", padx=4)

        self.connect_btn = ttk.Button(
            frame, text="Connect", command=self._toggle_connection
        )
        self.connect_btn.pack(side="left", padx=4)

    def _build_slider_frame(self):
        frame = ttk.LabelFrame(self.root, text="Servo Channels (0–180°)")
        frame.pack(fill="both", expand=True, padx=8, pady=4)

        # Arrange in 4 columns × 4 rows
        for ch in range(NUM_CHANNELS):
            row, col = divmod(ch, 4)

            var = tk.IntVar(value=DEFAULT_ANGLE)
            self.angle_vars.append(var)

            container = ttk.Frame(frame)
            container.grid(row=row, column=col, padx=6, pady=4, sticky="nsew")
            frame.columnconfigure(col, weight=1)

            label = ttk.Label(container, text=f"CH {ch}")
            label.pack()

            slider = tk.Scale(
                container,
                from_=0,
                to=180,
                orient="horizontal",
                variable=var,
                length=160,
                command=lambda val, c=ch: self._on_slider(c, int(val)),
            )
            slider.pack()
            self.sliders.append(slider)

            val_label = ttk.Label(container, textvariable=var, width=4)
            val_label.pack()

    def _build_status_bar(self):
        self.status_var = tk.StringVar(value="Disconnected")
        bar = ttk.Label(
            self.root, textvariable=self.status_var, relief="sunken", anchor="w"
        )
        bar.pack(fill="x", padx=8, pady=(0, 8))

    # --- Serial ---------------------------------------------------------------

    def _refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo["values"] = ports
        if ports:
            self.port_combo.current(0)

    def _toggle_connection(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.ser = None
            self.connect_btn.config(text="Connect")
            self.status_var.set("Disconnected")
            return

        port = self.port_var.get()
        if not port:
            self.status_var.set("No port selected")
            return

        try:
            self.ser = serial.Serial(port, BAUD_RATE, timeout=1)
            self.connect_btn.config(text="Disconnect")
            self.status_var.set(f"Connected to {port}")
            # Read the "PCA9685 ready" greeting
            self.root.after(500, self._read_greeting)
        except serial.SerialException as exc:
            self.status_var.set(f"Error: {exc}")
            self.ser = None

    def _read_greeting(self):
        if self.ser and self.ser.is_open and self.ser.in_waiting:
            try:
                line = self.ser.readline().decode("ascii", errors="replace").strip()
                if line:
                    self.status_var.set(f"Arduino: {line}")
            except serial.SerialException:
                pass

    def _send_command(self, channel: int, angle: int):
        if not self.ser or not self.ser.is_open:
            return
        msg = f"{channel},{angle}\n"
        try:
            self.ser.write(msg.encode("ascii"))
            # Read response non-blocking
            self.root.after(20, self._read_response)
        except serial.SerialException as exc:
            self.status_var.set(f"Send error: {exc}")

    def _read_response(self):
        if not self.ser or not self.ser.is_open:
            return
        try:
            if self.ser.in_waiting:
                line = self.ser.readline().decode("ascii", errors="replace").strip()
                if line.startswith("ERR"):
                    self.status_var.set(f"Arduino: {line}")
        except serial.SerialException:
            pass

    # --- Slider callback ------------------------------------------------------

    def _on_slider(self, channel: int, angle: int):
        self._send_command(channel, angle)


def main():
    root = tk.Tk()
    root.resizable(True, True)
    ServoGui(root)
    root.mainloop()


if __name__ == "__main__":
    main()
