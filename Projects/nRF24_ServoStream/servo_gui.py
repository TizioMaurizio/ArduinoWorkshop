"""
nRF24 Servo Stream GUI
Slider sends angle (0-180) to ESP8266 via Serial, which streams it over nRF24 to Uno.
"""

import tkinter as tk
from tkinter import ttk
import serial
import serial.tools.list_ports
import threading
import time


def find_esp_port():
    """Auto-detect ESP8266 (CP2102 or CH340) port."""
    for p in serial.tools.list_ports.comports():
        desc = (p.description or "").lower()
        if "cp210" in desc or "ch340" in desc or "usb" in desc.lower():
            # Skip Arduino Uno (usually CH340 on COM4)
            if "arduino" in desc.lower():
                continue
            return p.device
    # Fallback: try COM11
    return "COM11"


class ServoStreamGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("nRF24 Servo Stream")
        self.root.geometry("500x350")
        self.root.resizable(False, False)

        self.ser = None
        self.running = True
        self.current_angle = 90
        self.last_sent = -1
        self.tx_count = 0

        self._build_ui()
        self._connect_serial()
        self._start_sender()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        # Title
        tk.Label(self.root, text="nRF24 Servo Controller",
                 font=("Segoe UI", 16, "bold")).pack(pady=10)

        # Connection status
        self.status_var = tk.StringVar(value="Connecting...")
        self.status_label = tk.Label(self.root, textvariable=self.status_var,
                                     font=("Segoe UI", 10))
        self.status_label.pack()

        # Angle display
        self.angle_var = tk.StringVar(value="90°")
        tk.Label(self.root, textvariable=self.angle_var,
                 font=("Segoe UI", 48, "bold"), fg="#2196F3").pack(pady=10)

        # Slider
        self.slider = ttk.Scale(self.root, from_=0, to=180,
                                orient=tk.HORIZONTAL, length=400,
                                command=self._on_slider)
        self.slider.set(90)
        self.slider.pack(pady=10)

        # Labels under slider
        frame = tk.Frame(self.root)
        frame.pack(fill=tk.X, padx=50)
        tk.Label(frame, text="0°").pack(side=tk.LEFT)
        tk.Label(frame, text="90°").pack(side=tk.LEFT, expand=True)
        tk.Label(frame, text="180°").pack(side=tk.RIGHT)

        # Preset buttons
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=10)
        for angle in [0, 45, 90, 135, 180]:
            tk.Button(btn_frame, text=f"{angle}°", width=5,
                      command=lambda a=angle: self._set_angle(a)).pack(side=tk.LEFT, padx=5)

        # Stats
        self.stats_var = tk.StringVar(value="TX: 0 packets")
        tk.Label(self.root, textvariable=self.stats_var,
                 font=("Segoe UI", 9), fg="gray").pack(side=tk.BOTTOM, pady=5)

    def _connect_serial(self):
        port = find_esp_port()
        try:
            self.ser = serial.Serial(port, 115200, timeout=0.1)
            time.sleep(0.5)
            self.status_var.set(f"● Connected: {port}")
            self.status_label.config(fg="green")
        except Exception as e:
            self.status_var.set(f"✗ Cannot open {port}: {e}")
            self.status_label.config(fg="red")

    def _on_slider(self, val):
        self.current_angle = int(float(val))
        self.angle_var.set(f"{self.current_angle}°")

    def _set_angle(self, angle):
        self.slider.set(angle)
        self.current_angle = angle
        self.angle_var.set(f"{angle}°")

    def _start_sender(self):
        def sender_loop():
            while self.running:
                if self.ser and self.ser.is_open:
                    angle = self.current_angle
                    if angle != self.last_sent:
                        try:
                            self.ser.write(f"{angle}\n".encode())
                            self.last_sent = angle
                            self.tx_count += 1
                            self.stats_var.set(f"TX: {self.tx_count} updates sent")
                        except Exception:
                            pass
                time.sleep(0.02)  # 50Hz max update rate

        t = threading.Thread(target=sender_loop, daemon=True)
        t.start()

    def _on_close(self):
        self.running = False
        time.sleep(0.1)
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = ServoStreamGUI()
    app.run()
