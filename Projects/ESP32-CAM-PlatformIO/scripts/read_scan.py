"""Read UART scan results from ESP32-S3 over TCP."""
import socket, sys

ip = sys.argv[1] if len(sys.argv) > 1 else "10.192.119.9"
s = socket.socket()
s.settimeout(300)
s.connect((ip, 100))
print(f"Connected to {ip}:100, waiting for scan results...")

buf = b""
while True:
    try:
        chunk = s.recv(4096)
        if not chunk:
            break
        buf += chunk
        # Print lines as they arrive
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            print(line.decode(errors="replace"))
        if b"Scan complete" in buf + chunk:
            print(buf.decode(errors="replace"))
            break
    except socket.timeout:
        print("Timeout waiting for data")
        break

s.close()
