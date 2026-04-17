"""
UDP-to-Serial bridge for Godot → Arduino PCA9685 servo control.

Listens on UDP localhost:9685 for ASCII packets "<channel>,<angle>\n"
and forwards them to the Arduino over serial.

Usage:
    python serial_bridge.py COM3
    python serial_bridge.py /dev/ttyUSB0 --baud 115200 --port 9685
"""

import argparse
import socket
import sys

import serial


def main() -> None:
    parser = argparse.ArgumentParser(description="UDP-to-Serial bridge")
    parser.add_argument("serial_port", help="Arduino serial port (e.g. COM3)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate")
    parser.add_argument("--port", type=int, default=9685, help="UDP listen port")
    args = parser.parse_args()

    ser = serial.Serial(args.serial_port, args.baud, timeout=0.1)
    print(f"Serial: {args.serial_port} @ {args.baud}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", args.port))
    sock.settimeout(0.05)
    print(f"UDP listening on 127.0.0.1:{args.port}")

    # Read Arduino greeting
    greeting = ser.readline().decode("ascii", errors="replace").strip()
    if greeting:
        print(f"Arduino: {greeting}")

    try:
        while True:
            # Forward UDP → Serial
            try:
                data, addr = sock.recvfrom(256)
                if data:
                    ser.write(data)
                    # Read Arduino response
                    resp = ser.readline().decode("ascii", errors="replace").strip()
                    if resp and resp.startswith("ERR"):
                        print(f"Arduino error: {resp}")
            except socket.timeout:
                pass

            # Print any unsolicited serial data
            if ser.in_waiting:
                line = ser.readline().decode("ascii", errors="replace").strip()
                if line:
                    print(f"Arduino: {line}")

    except KeyboardInterrupt:
        print("\nStopping bridge.")
    finally:
        sock.close()
        ser.close()


if __name__ == "__main__":
    main()
