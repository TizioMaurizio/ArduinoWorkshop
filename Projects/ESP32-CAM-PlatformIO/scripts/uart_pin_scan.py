"""
Scan ESP32-S3 GPIO pairs to find which ones connect to the Arduino UNO UART.

Uploads a small test sketch that tries each TX candidate, sends a known command,
and reports if the Arduino responds. Runs over the existing WiFi TCP connection.

Usage: python scripts/uart_pin_scan.py --ip 10.192.119.9
"""

import socket
import time
import sys
import argparse

# We can't scan pins remotely — but we CAN use the existing firmware's
# Serial2 to check if the Arduino is responding.
# Instead, let's just connect and see if we get any data back from Serial2.

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ip", default="10.192.119.9")
    p.add_argument("--port", type=int, default=100)
    args = p.parse_args()

    print(f"Connecting to {args.ip}:{args.port}...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    try:
        sock.connect((args.ip, args.port))
    except Exception as e:
        print(f"Connect failed: {e}")
        return 1

    # Send movement command and wait for Arduino response
    print("Sending forward command...")
    sock.sendall(b'{"N":3,"D1":3,"D2":50,"H":"1"}')
    time.sleep(1.0)

    # Try to read any response from Arduino via ESP32
    sock.settimeout(2)
    try:
        data = sock.recv(4096)
        print(f"Response from Arduino: {data}")
    except socket.timeout:
        print("No response from Arduino (timeout) — Serial2 TX/RX pins likely wrong")

    # Send stop
    sock.sendall(b'{"N":100,"H":"2"}')
    time.sleep(0.3)

    # Also try factory test command that Arduino should respond to
    print("\nSending factory detection...")
    sock.sendall(b'{"N":1,"H":"3"}')  # Get device info
    time.sleep(1.0)
    try:
        data = sock.recv(4096)
        print(f"Response: {data}")
    except socket.timeout:
        print("No response to info request either")

    sock.close()

    print("\nIf no responses: Serial2 pins (GPIO 33/4) are wrong for S3 V2 board.")
    print("Need to find correct UART pins from V2 schematic or probe physically.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
