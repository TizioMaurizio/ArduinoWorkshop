"""
F8620 RF Traffic Visualizer
Shows a scrolling bitmap where each row = one packet, each column = one byte.
Color encodes the byte value. Helps visually identify repeating patterns
(real signal) vs random noise.

Color mapping:
  0x00 = black
  0xFF = white
  0xAA = bright green (preamble)
  0x55 = bright magenta (alt preamble)
  Other = hue mapped from blue(low) to red(high)

Left margin: channel number colored by channel
Right side: 20-byte packet visualized as colored squares
"""

import tkinter as tk
from tkinter import Canvas
import serial
import colorsys
import threading
import queue
import time

# --- Config ---
SERIAL_PORT = "COM4"
BAUD_RATE = 230400
NUM_BYTES = 20        # bytes per packet to show
CELL_SIZE = 12        # pixel size of each square
ROWS_VISIBLE = 80     # rows visible in window
MARGIN_LEFT = 40      # space for channel label
MARGIN_RIGHT = 10
LOG_FILE = "handshake_capture.log"

# --- Color mapping ---
def byte_to_rgb(val):
    """Map byte value to RGB color."""
    if val == 0x00:
        return (0, 0, 0)           # black
    elif val == 0xFF:
        return (255, 255, 255)     # white
    elif val == 0xAA:
        return (0, 220, 80)        # green (preamble)
    elif val == 0x55:
        return (220, 0, 220)       # magenta (alt preamble)
    else:
        # HSV color wheel: blue(0x01) -> cyan -> green -> yellow -> red(0xFE)
        hue = (1.0 - val / 255.0) * 0.7  # 0.7 = blue to red range
        r, g, b = colorsys.hsv_to_rgb(hue, 0.9, 0.9)
        return (int(r * 255), int(g * 255), int(b * 255))

CHANNEL_COLORS = {
    72: "#FF4444",
    73: "#FF8800",
    74: "#FFFF00",
    75: "#44FF44",
    76: "#4488FF",
    77: "#AA44FF",
}

# --- Serial reader thread ---
def serial_reader(port, baud, pkt_queue, stop_event):
    """Read serial, parse packets, push to queue."""
    try:
        ser = serial.Serial(port, baud, timeout=0.5)
        time.sleep(2)
        ser.read(ser.in_waiting)  # flush
    except Exception as e:
        pkt_queue.put(("ERROR", str(e)))
        return

    # Open log file
    log = open(LOG_FILE, "w")
    log.write("# F8620 Handshake Capture\n")
    log.write("# Format: pkt_num timestamp_ms channel | hex_bytes\n")
    log.flush()

    buffer = ""
    while not stop_event.is_set():
        try:
            raw = ser.read(ser.in_waiting or 1)
            if raw:
                buffer += raw.decode("utf-8", errors="replace")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()

                    # Log ALL lines from Arduino
                    if line:
                        log.write(line + "\n")
                        log.flush()

                    # Parse: #count timestamp channel | hex_bytes
                    if "|" in line and "#" in line:
                        try:
                            parts = line.split("|")
                            header = parts[0].strip()
                            hex_part = parts[1].strip()

                            # Extract channel from header tokens
                            tokens = header.split()
                            # tokens: ['#1234', '5678', '75']
                            ch = int(tokens[-1])

                            # Extract bytes
                            hex_bytes = hex_part.split()[:NUM_BYTES]
                            byte_vals = [int(h, 16) for h in hex_bytes]
                            if len(byte_vals) >= 10:
                                pkt_queue.put(("PKT", ch, byte_vals))
                        except (ValueError, IndexError):
                            pass
            else:
                time.sleep(0.01)
        except Exception:
            if not stop_event.is_set():
                time.sleep(0.1)

    log.close()
    ser.close()


# --- Main GUI ---
class RFVisualizer:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("F8620 RF Traffic Visualizer")

        width = MARGIN_LEFT + NUM_BYTES * CELL_SIZE + MARGIN_RIGHT
        height = ROWS_VISIBLE * CELL_SIZE

        # Top info bar
        self.info_frame = tk.Frame(self.root)
        self.info_frame.pack(fill=tk.X)

        self.status_label = tk.Label(
            self.info_frame, text="Connecting...", font=("Consolas", 10),
            anchor="w"
        )
        self.status_label.pack(side=tk.LEFT, padx=5)

        self.count_label = tk.Label(
            self.info_frame, text="Packets: 0", font=("Consolas", 10),
            anchor="e"
        )
        self.count_label.pack(side=tk.RIGHT, padx=5)

        # Legend
        legend_frame = tk.Frame(self.root)
        legend_frame.pack(fill=tk.X, pady=2)
        tk.Label(legend_frame, text="Legend:", font=("Consolas", 8)).pack(side=tk.LEFT, padx=3)
        for val, name, color in [
            (0x00, "0x00", "#000000"),
            (0xAA, "0xAA", "#00DC50"),
            (0x55, "0x55", "#DC00DC"),
            (0xFF, "0xFF", "#FFFFFF"),
        ]:
            tk.Label(
                legend_frame, text=f" {name} ", bg=color,
                fg="white" if val < 0x80 else "black",
                font=("Consolas", 8)
            ).pack(side=tk.LEFT, padx=1)

        # Channel legend
        tk.Label(legend_frame, text="  Ch:", font=("Consolas", 8)).pack(side=tk.LEFT)
        for ch, color in CHANNEL_COLORS.items():
            tk.Label(
                legend_frame, text=f" {ch} ", bg=color, fg="black",
                font=("Consolas", 8)
            ).pack(side=tk.LEFT, padx=1)

        # Canvas
        self.canvas = Canvas(
            self.root, width=width, height=height, bg="#1a1a1a"
        )
        self.canvas.pack()

        # Byte position header
        header_canvas = Canvas(self.root, width=width, height=16, bg="#333333")
        header_canvas.pack()
        for i in range(NUM_BYTES):
            x = MARGIN_LEFT + i * CELL_SIZE + CELL_SIZE // 2
            header_canvas.create_text(
                x, 8, text=str(i), fill="#aaaaaa", font=("Consolas", 7)
            )

        # Data
        self.rows = []  # list of (channel, [byte_vals])
        self.pkt_count = 0
        self.pkt_queue = queue.Queue()
        self.stop_event = threading.Event()

        # Start serial thread
        self.serial_thread = threading.Thread(
            target=serial_reader,
            args=(SERIAL_PORT, BAUD_RATE, self.pkt_queue, self.stop_event),
            daemon=True,
        )
        self.serial_thread.start()
        self.status_label.config(text=f"Listening on {SERIAL_PORT}...")

        # Periodic GUI update
        self.root.after(50, self.update_gui)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def update_gui(self):
        """Process queued packets and redraw."""
        new_packets = 0
        while not self.pkt_queue.empty():
            try:
                item = self.pkt_queue.get_nowait()
                if item[0] == "ERROR":
                    self.status_label.config(text=f"ERROR: {item[1]}")
                    return
                elif item[0] == "PKT":
                    _, ch, byte_vals = item
                    self.rows.append((ch, byte_vals))
                    self.pkt_count += 1
                    new_packets += 1
                    # Keep only visible rows
                    if len(self.rows) > ROWS_VISIBLE:
                        self.rows = self.rows[-ROWS_VISIBLE:]
            except queue.Empty:
                break

        if new_packets > 0:
            self.redraw()
            self.count_label.config(text=f"Packets: {self.pkt_count}")

        self.root.after(50, self.update_gui)

    def redraw(self):
        """Redraw the entire canvas."""
        self.canvas.delete("all")
        for row_idx, (ch, byte_vals) in enumerate(self.rows):
            y = row_idx * CELL_SIZE

            # Channel indicator
            ch_color = CHANNEL_COLORS.get(ch, "#888888")
            self.canvas.create_rectangle(
                2, y + 1, MARGIN_LEFT - 4, y + CELL_SIZE - 1,
                fill=ch_color, outline=""
            )
            self.canvas.create_text(
                MARGIN_LEFT // 2, y + CELL_SIZE // 2,
                text=str(ch), fill="black", font=("Consolas", 7)
            )

            # Byte squares
            for col_idx, val in enumerate(byte_vals):
                x = MARGIN_LEFT + col_idx * CELL_SIZE
                r, g, b = byte_to_rgb(val)
                color = f"#{r:02x}{g:02x}{b:02x}"
                self.canvas.create_rectangle(
                    x, y, x + CELL_SIZE - 1, y + CELL_SIZE - 1,
                    fill=color, outline=""
                )

    def on_close(self):
        self.stop_event.set()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = RFVisualizer()
    app.run()
