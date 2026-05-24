"""
nRF24 Ping-Pong GUI Monitor
Displays real-time communication between Arduino Uno and ESP8266 NodeMCU
Works even if only one device is connected.
"""
import tkinter as tk
from tkinter import ttk, scrolledtext
import serial
import serial.tools.list_ports
import threading
import time
import re
from collections import deque

# Will auto-detect, but these are fallbacks
UNO_PORT = "COM4"
ESP_PORT = "COM11"
BAUD = 115200


def find_ports():
    """Try to find Uno and ESP ports automatically."""
    uno, esp = None, None
    for p in serial.tools.list_ports.comports():
        desc = (p.description or "").lower()
        hwid = (p.hwid or "").lower()
        # Arduino Uno (CH340 or ATmega16U2)
        if "arduino" in desc or "ch340" in desc and p.device == "COM4":
            uno = p.device
        elif "ch340" in desc or "cp210" in desc or "usb" in desc.lower():
            if not uno and p.device == "COM4":
                uno = p.device
            elif not esp:
                esp = p.device
    return uno or UNO_PORT, esp or ESP_PORT


class PingPongGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("nRF24 Ping-Pong Monitor")
        self.root.geometry("900x600")
        self.root.configure(bg="#1e1e2e")

        self.uno_serial = None
        self.esp_serial = None
        self.running = False

        self.ping_count = 0
        self.pong_count = 0
        self.fail_count = 0
        self.rtt_history = deque(maxlen=50)

        self._build_ui()
        self._start_serial()

    def _build_ui(self):
        # Top stats bar
        stats_frame = tk.Frame(self.root, bg="#313244", height=80)
        stats_frame.pack(fill=tk.X, padx=10, pady=(10, 5))
        stats_frame.pack_propagate(False)

        self.lbl_status = tk.Label(stats_frame, text="● CONNECTING...",
                                   font=("Consolas", 14, "bold"),
                                   fg="#f9e2af", bg="#313244")
        self.lbl_status.pack(side=tk.LEFT, padx=20)

        self.lbl_stats = tk.Label(stats_frame,
                                  text="PING: 0 | PONG: 0 | FAIL: 0 | RTT: --ms",
                                  font=("Consolas", 12),
                                  fg="#cdd6f4", bg="#313244")
        self.lbl_stats.pack(side=tk.RIGHT, padx=20)

        # RTT bar canvas
        rtt_frame = tk.Frame(self.root, bg="#1e1e2e")
        rtt_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(rtt_frame, text="RTT (ms)", font=("Consolas", 9),
                 fg="#6c7086", bg="#1e1e2e").pack(anchor=tk.W)
        self.rtt_canvas = tk.Canvas(rtt_frame, height=60, bg="#181825",
                                    highlightthickness=0)
        self.rtt_canvas.pack(fill=tk.X)

        # Middle: two serial panels side by side
        panels = tk.Frame(self.root, bg="#1e1e2e")
        panels.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Uno panel
        uno_frame = tk.LabelFrame(panels, text=" Arduino Uno (COM4) — PING ",
                                  font=("Consolas", 10, "bold"),
                                  fg="#89b4fa", bg="#1e1e2e")
        uno_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        self.uno_text = scrolledtext.ScrolledText(
            uno_frame, height=15, bg="#11111b", fg="#a6e3a1",
            font=("Consolas", 9), state=tk.DISABLED, wrap=tk.WORD)
        self.uno_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # ESP panel
        esp_frame = tk.LabelFrame(panels, text=" ESP8266 NodeMCU (COM11) — PONG ",
                                  font=("Consolas", 10, "bold"),
                                  fg="#f38ba8", bg="#1e1e2e")
        esp_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))

        self.esp_text = scrolledtext.ScrolledText(
            esp_frame, height=15, bg="#11111b", fg="#f9e2af",
            font=("Consolas", 9), state=tk.DISABLED, wrap=tk.WORD)
        self.esp_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Animation indicator
        anim_frame = tk.Frame(self.root, bg="#1e1e2e", height=40)
        anim_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        self.anim_canvas = tk.Canvas(anim_frame, height=36, bg="#181825",
                                     highlightthickness=0)
        self.anim_canvas.pack(fill=tk.X)
        self._draw_idle_animation()

    def _draw_idle_animation(self):
        self.anim_canvas.delete("all")
        w = self.anim_canvas.winfo_width() or 880
        # Uno side
        self.anim_canvas.create_text(50, 18, text="UNO", fill="#89b4fa",
                                     font=("Consolas", 10, "bold"))
        # ESP side
        self.anim_canvas.create_text(w - 50, 18, text="ESP",
                                     fill="#f38ba8", font=("Consolas", 10, "bold"))
        # Line
        self.anim_canvas.create_line(90, 18, w - 90, 18, fill="#45475a",
                                     width=2, dash=(4, 4))

    def _draw_ping(self):
        self.anim_canvas.delete("all")
        w = self.anim_canvas.winfo_width() or 880
        self.anim_canvas.create_text(50, 18, text="UNO", fill="#89b4fa",
                                     font=("Consolas", 10, "bold"))
        self.anim_canvas.create_text(w - 50, 18, text="ESP",
                                     fill="#f38ba8", font=("Consolas", 10, "bold"))
        # Arrow right (PING)
        self.anim_canvas.create_line(90, 14, w - 90, 14, fill="#a6e3a1",
                                     width=2, arrow=tk.LAST)
        self.anim_canvas.create_text(w // 2, 8, text="PING →",
                                     fill="#a6e3a1", font=("Consolas", 9))
        # Arrow left (PONG)
        self.anim_canvas.create_line(w - 90, 24, 90, 24, fill="#f9e2af",
                                     width=2, arrow=tk.LAST)
        self.anim_canvas.create_text(w // 2, 30, text="← PONG",
                                     fill="#f9e2af", font=("Consolas", 9))

    def _draw_fail(self):
        self.anim_canvas.delete("all")
        w = self.anim_canvas.winfo_width() or 880
        self.anim_canvas.create_text(50, 18, text="UNO", fill="#89b4fa",
                                     font=("Consolas", 10, "bold"))
        self.anim_canvas.create_text(w - 50, 18, text="ESP",
                                     fill="#f38ba8", font=("Consolas", 10, "bold"))
        self.anim_canvas.create_line(90, 18, w - 90, 18, fill="#f38ba8",
                                     width=2, dash=(2, 6))
        self.anim_canvas.create_text(w // 2, 18, text="✗ NO ACK",
                                     fill="#f38ba8", font=("Consolas", 10, "bold"))

    def _update_stats(self):
        avg_rtt = sum(self.rtt_history) / len(self.rtt_history) if self.rtt_history else 0
        self.lbl_stats.config(
            text=f"PING: {self.ping_count} | PONG: {self.pong_count} | "
                 f"FAIL: {self.fail_count} | RTT: {avg_rtt:.1f}ms")

    def _draw_rtt_bars(self):
        self.rtt_canvas.delete("all")
        if not self.rtt_history:
            return
        w = self.rtt_canvas.winfo_width() or 880
        h = 55
        n = len(self.rtt_history)
        bar_w = max(2, w // 50)
        max_rtt = max(max(self.rtt_history), 10)

        for i, rtt in enumerate(self.rtt_history):
            x = w - (n - i) * (bar_w + 2)
            bar_h = max(2, int(rtt / max_rtt * h))
            color = "#a6e3a1" if rtt < 10 else "#f9e2af" if rtt < 50 else "#f38ba8"
            self.rtt_canvas.create_rectangle(x, h - bar_h, x + bar_w, h,
                                             fill=color, outline="")

    def _append_text(self, widget, text):
        widget.config(state=tk.NORMAL)
        widget.insert(tk.END, text + "\n")
        widget.see(tk.END)
        widget.config(state=tk.DISABLED)

    def _start_serial(self):
        self.running = True
        uno_port, esp_port = find_ports()

        try:
            self.uno_serial = serial.Serial(uno_port, BAUD, timeout=0.5)
            self._append_text(self.uno_text, f"[Connected to {uno_port}]")
            time.sleep(0.1)
        except Exception as e:
            self._append_text(self.uno_text, f"[{uno_port} not available: {e}]")
            self.uno_serial = None

        try:
            self.esp_serial = serial.Serial(esp_port, BAUD, timeout=0.5)
            self._append_text(self.esp_text, f"[Connected to {esp_port}]")
            time.sleep(0.1)
        except Exception as e:
            self._append_text(self.esp_text, f"[{esp_port} not available: {e}]")
            self.esp_serial = None

        if self.uno_serial and self.esp_serial:
            self.lbl_status.config(text="● BOTH CONNECTED", fg="#a6e3a1")
        elif self.uno_serial:
            self.lbl_status.config(text="● UNO only (ESP not found)", fg="#f9e2af")
        elif self.esp_serial:
            self.lbl_status.config(text="● ESP only (UNO not found)", fg="#f9e2af")
        else:
            self.lbl_status.config(text="● NO DEVICES", fg="#f38ba8")

        # Reader threads
        if self.uno_serial:
            t = threading.Thread(target=self._read_serial,
                                 args=(self.uno_serial, "uno"), daemon=True)
            t.start()
        if self.esp_serial:
            t = threading.Thread(target=self._read_serial,
                                 args=(self.esp_serial, "esp"), daemon=True)
            t.start()

    def _read_serial(self, ser, source):
        while self.running:
            try:
                line = ser.readline().decode("utf-8", errors="replace").strip()
                if line:
                    self.root.after(0, self._process_line, source, line)
            except Exception:
                if not self.running:
                    break
                time.sleep(0.1)

    def _process_line(self, source, line):
        if not self.running:
            return
        try:
            if source == "uno":
                self._append_text(self.uno_text, line)
                # Parse ping/pong/fail
                if "PING #" in line and "sent" in line:
                    self.ping_count += 1
                if "PONG!" in line:
                    self.pong_count += 1
                    m = re.search(r"RTT=(\d+)ms", line)
                    if m:
                        self.rtt_history.append(int(m.group(1)))
                    self._draw_ping()
                    self.root.after(800, self._draw_idle_animation)
                if "FAILED" in line or "timeout" in line:
                    self.fail_count += 1
                    self._draw_fail()
                    self.root.after(800, self._draw_idle_animation)
            else:
                self._append_text(self.esp_text, line)

            self._update_stats()
            self._draw_rtt_bars()
        except Exception:
            pass

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self._on_close()

    def _on_close(self):
        self.running = False
        time.sleep(0.3)
        try:
            if self.uno_serial and self.uno_serial.is_open:
                self.uno_serial.close()
        except Exception:
            pass
        try:
            if self.esp_serial and self.esp_serial.is_open:
                self.esp_serial.close()
        except Exception:
            pass
        self.root.destroy()


if __name__ == "__main__":
    app = PingPongGUI()
    app.run()
