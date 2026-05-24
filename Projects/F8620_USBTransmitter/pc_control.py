"""
F8620 PC Controller — sends commands to f8620_usb_tx.ino over serial.

Usage:
    python pc_control.py [COM_PORT]
    python pc_control.py COM4

Controls (keyboard):
    b       = BIND (send bind sequence)
    a       = toggle ARM/DISARM
    SPACE   = immediate SAFE
    x       = emergency SAFE
    r / f   = throttle up / down
    w / s   = pitch forward / back
    a / d   = (when armed) roll left / right  [overrides 'a' for arm when armed]
    q / e   = yaw left / right
    1       = MODE BIND_REPLAY
    2       = MODE DATA_ONLY
    3       = MODE BIND_THEN_DATA
    4       = MODE REPEATED
    ESC     = SAFE and exit
    Ctrl+C  = SAFE and exit

*** REMOVE PROPELLERS BEFORE TESTING ***
"""

import sys
import time
import threading
import serial

# Try to import msvcrt for Windows keyboard input
try:
    import msvcrt
    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False

# ============================= CONFIG ========================================

DEFAULT_PORT = "COM4"
BAUD_RATE = 115200
SEND_RATE_HZ = 40  # Commands per second

# ============================= STATE =========================================

throttle = 0      # 0..100
yaw = 0           # -100..100
pitch = 0         # -100..100
roll = 0          # -100..100
armed = False
running = True

# ============================= SERIAL ========================================

def open_serial(port):
    try:
        s = serial.Serial(port, BAUD_RATE, timeout=0.1)
        time.sleep(2)  # Wait for Arduino reset
        s.read(s.in_waiting)  # Flush startup messages
        return s
    except serial.SerialException as e:
        print(f"ERROR: Cannot open {port}: {e}")
        sys.exit(1)

def send_cmd(ser, cmd):
    ser.write((cmd + "\n").encode())

def read_responses(ser):
    """Read and print any responses from Arduino (non-blocking)."""
    while ser.in_waiting:
        line = ser.readline().decode("utf-8", errors="replace").strip()
        if line:
            print(f"  [ARD] {line}")

# ============================= KEYBOARD ======================================

def get_key():
    """Get a single keypress (Windows only via msvcrt)."""
    if not HAS_MSVCRT:
        return None
    if msvcrt.kbhit():
        ch = msvcrt.getch()
        if ch == b'\x1b':  # ESC
            return 'ESC'
        if ch == b' ':
            return 'SPACE'
        if ch == b'\x03':  # Ctrl+C
            return 'ESC'
        try:
            return ch.decode('utf-8')
        except UnicodeDecodeError:
            return None
    return None

# ============================= MAIN ==========================================

def main():
    global throttle, yaw, pitch, roll, armed, running

    port = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PORT
    print(f"F8620 PC Controller")
    print(f"Port: {port} @ {BAUD_RATE}")
    print(f"*** REMOVE PROPELLERS BEFORE TESTING ***")
    print()

    if not HAS_MSVCRT:
        print("WARNING: msvcrt not available (non-Windows). Keyboard control disabled.")
        print("You can still type commands manually followed by Enter.")
        print()

    ser = open_serial(port)
    print("Connected. Reading startup...")
    time.sleep(0.5)
    read_responses(ser)

    send_cmd(ser, "STATUS")
    time.sleep(0.1)
    read_responses(ser)

    print()
    print("Controls: b=bind a=arm SPACE=safe r/f=thr w/s=pitch q/e=yaw ESC=exit")
    print("          1=BIND_REPLAY 2=DATA_ONLY 3=BIND_THEN_DATA 4=REPEATED")
    print()

    interval = 1.0 / SEND_RATE_HZ
    last_send = 0
    last_print = 0

    try:
        while running:
            now = time.time()

            # Process keyboard
            key = get_key()
            if key == 'ESC':
                print("\nExiting safely...")
                running = False
                break
            elif key == 'SPACE' or key == 'x':
                throttle = 0
                yaw = 0
                pitch = 0
                roll = 0
                armed = False
                send_cmd(ser, "SAFE")
                print(">>> SAFE")
            elif key == 'b':
                send_cmd(ser, "BIND")
                print(">>> BIND")
            elif key == 'a':
                if not armed:
                    armed = True
                    send_cmd(ser, "ARM 1")
                    print(">>> ARMED (throttle still 0)")
                else:
                    armed = False
                    throttle = 0
                    send_cmd(ser, "ARM 0")
                    print(">>> DISARMED")
            elif key == 'r':
                throttle = min(100, throttle + 5)
            elif key == 'f':
                throttle = max(0, throttle - 5)
            elif key == 'w':
                pitch = min(100, pitch + 10)
            elif key == 's':
                pitch = max(-100, pitch - 10)
            elif key == 'q':
                yaw = max(-100, yaw - 10)
            elif key == 'e':
                yaw = min(100, yaw + 10)
            elif key == 'd':
                roll = min(100, roll + 10)
            # 'a' is overloaded: arm toggle when not armed, roll left when armed
            elif key == 'a' and armed:
                roll = max(-100, roll - 10)
            elif key == '1':
                send_cmd(ser, "MODE BIND_REPLAY")
                print(">>> MODE BIND_REPLAY")
            elif key == '2':
                send_cmd(ser, "MODE DATA_ONLY")
                print(">>> MODE DATA_ONLY")
            elif key == '3':
                send_cmd(ser, "MODE BIND_THEN_DATA")
                print(">>> MODE BIND_THEN_DATA")
            elif key == '4':
                send_cmd(ser, "MODE REPEATED")
                print(">>> MODE REPEATED")

            # Send SET at target rate
            if now - last_send >= interval:
                if armed:
                    send_cmd(ser, f"SET {throttle} {yaw} {pitch} {roll}")
                last_send = now

            # Print state periodically
            if now - last_print >= 1.0:
                arm_str = "ARMED" if armed else "disarmed"
                print(f"  [{arm_str}] T={throttle:3d} Y={yaw:4d} P={pitch:4d} R={roll:4d}")
                last_print = now

            # Read Arduino responses
            read_responses(ser)

            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nCtrl+C — exiting safely...")

    # Cleanup
    send_cmd(ser, "SAFE")
    time.sleep(0.1)
    read_responses(ser)
    ser.close()
    print("Serial closed. Done.")

if __name__ == "__main__":
    main()
