"""
F8620 RF Capture + Replay System
Phase 1: CAPTURE — records all RF packets with timing to a binary file
Phase 2: REPLAY — plays back the exact sequence

Usage:
  python capture_replay.py capture    — Record RF (uses handshake capture sketch)
  python capture_replay.py replay     — Replay saved sequence (uses replay sketch)
  python capture_replay.py replay --loop  — Replay in loop

Capture file format (.rf_capture):
  Header: "RF_CAP\\x01" (7 bytes)
  Records: [uint32_le timestamp_ms] [uint8 channel] [uint8 length] [payload bytes...]
  Footer: "END\\x00" (4 bytes)
"""

import sys
import serial
import struct
import time
import os

SERIAL_PORT = "COM4"
BAUD_RATE = 1000000  # Must match Arduino sketch
CAPTURE_FILE = "single_ch76_capture.rf_capture"


def capture_mode(output_file=None):
    """Record all RF packets from the handshake capture sketch."""
    outfile = output_file or CAPTURE_FILE
    print("=== RF CAPTURE MODE ===")
    print(f"Port: {SERIAL_PORT} @ {BAUD_RATE}")
    print(f"Output: {outfile}")
    print()
    print("Instructions:")
    print("  1. Drone should be ON (waiting for bind)")
    print("  2. Original TX should be OFF")
    print("  3. Press ENTER to start recording...")
    input()
    
    print("Recording started! Now turn ON the original TX.")
    print("Press Ctrl+C to stop recording when binding is complete.")
    print()
    
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    time.sleep(2)
    ser.read(ser.in_waiting)  # flush
    
    # Open capture file
    f = open(outfile, "wb")
    f.write(b"RF_CAP\x01")  # header
    
    pkt_count = 0
    start_time = time.time()
    buffer = ""
    
    try:
        while True:
            raw = ser.read(ser.in_waiting or 1)
            if raw:
                buffer += raw.decode("utf-8", errors="replace")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    
                    # Parse: #count timestamp channel | hex_bytes
                    if "|" in line and "#" in line:
                        try:
                            parts = line.split("|")
                            header = parts[0].strip()
                            hex_part = parts[1].strip()
                            
                            tokens = header.split()
                            timestamp_ms = int(tokens[1])
                            channel = int(tokens[2])
                            
                            hex_bytes = hex_part.split()
                            payload = bytes([int(h, 16) for h in hex_bytes])
                            length = len(payload)
                            
                            # Write record: timestamp(4) + channel(1) + length(1) + payload
                            f.write(struct.pack("<IBB", timestamp_ms, channel, length))
                            f.write(payload)
                            
                            pkt_count += 1
                            elapsed = time.time() - start_time
                            
                            if pkt_count <= 5 or pkt_count % 50 == 0:
                                print(f"  [{elapsed:.1f}s] #{pkt_count} ch={channel} "
                                      f"t={timestamp_ms}ms len={length}")
                        except (ValueError, IndexError):
                            pass
            else:
                time.sleep(0.01)
                
    except KeyboardInterrupt:
        pass
    
    f.write(b"END\x00")
    f.close()
    ser.close()
    
    elapsed = time.time() - start_time
    file_size = os.path.getsize(outfile)
    print(f"\n=== CAPTURE COMPLETE ===")
    print(f"  Duration: {elapsed:.1f}s")
    print(f"  Packets:  {pkt_count}")
    print(f"  File:     {outfile} ({file_size} bytes)")
    print(f"  Rate:     {pkt_count/elapsed:.1f} pkt/s")


def load_capture(filename):
    """Load capture file, return list of (timestamp_ms, channel, payload)."""
    with open(filename, "rb") as f:
        header = f.read(7)
        if header != b"RF_CAP\x01":
            raise ValueError(f"Invalid capture file header: {header}")
        
        packets = []
        while True:
            rec_header = f.read(6)
            if len(rec_header) < 6:
                break
            if rec_header[:4] == b"END\x00":
                break
                
            timestamp_ms, channel, length = struct.unpack("<IBB", rec_header)
            payload = f.read(length)
            if len(payload) < length:
                break
            packets.append((timestamp_ms, channel, payload))
    
    return packets


def replay_mode(loop=False):
    """Replay captured sequence through the replay Arduino sketch."""
    print("=== RF REPLAY MODE ===")
    print(f"Port: {SERIAL_PORT} @ {BAUD_RATE}")
    print(f"Input: {CAPTURE_FILE}")
    if loop:
        print("Mode: LOOP (repeats until Ctrl+C)")
    print()
    
    # Load capture
    if not os.path.exists(CAPTURE_FILE):
        print(f"ERROR: Capture file not found: {CAPTURE_FILE}")
        print("Run 'capture' mode first.")
        return
    
    packets = load_capture(CAPTURE_FILE)
    print(f"Loaded {len(packets)} packets")
    
    if not packets:
        print("ERROR: No packets in capture file!")
        return
    
    # Calculate timing
    first_ts = packets[0][0]
    last_ts = packets[-1][0]
    duration = (last_ts - first_ts) / 1000.0
    print(f"Sequence duration: {duration:.2f}s")
    print()
    
    # Connect to Arduino
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    time.sleep(2)
    
    # Wait for READY
    ready_data = ser.read(ser.in_waiting or 100)
    print(f"Arduino: {ready_data.decode('utf-8', errors='replace').strip()}")
    
    print()
    print("Press ENTER to start replay (drone must be ON)...")
    input()
    
    try:
        iteration = 0
        while True:
            iteration += 1
            print(f"--- Replay #{iteration} starting ---")
            
            replay_start = time.time()
            sent = 0
            
            for i, (ts_ms, channel, payload) in enumerate(packets):
                # Calculate when to send this packet (relative to first)
                target_offset = (ts_ms - first_ts) / 1000.0
                
                # Wait until the right time
                while True:
                    elapsed = time.time() - replay_start
                    if elapsed >= target_offset:
                        break
                    remaining = target_offset - elapsed
                    if remaining > 0.001:
                        time.sleep(0.0005)
                
                # Send packet: [0xFF] [channel] [length] [payload...]
                frame = bytes([0xFF, channel, len(payload)]) + payload
                ser.write(frame)
                sent += 1
                
                # Wait for ACK (non-blocking, drain buffer)
                if ser.in_waiting:
                    ser.read(ser.in_waiting)
                
                # Progress
                if sent <= 3 or sent % 100 == 0:
                    print(f"  Sent {sent}/{len(packets)} "
                          f"t={target_offset:.2f}s ch={channel}")
            
            elapsed = time.time() - replay_start
            print(f"--- Replay #{iteration} complete: {sent} pkts in {elapsed:.2f}s ---")
            print()
            
            if not loop:
                break
            
            print("Looping in 1 second...")
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopped.")
    
    # Get final status
    ser.write(b'S')
    time.sleep(0.3)
    if ser.in_waiting:
        print(f"Arduino: {ser.read(ser.in_waiting).decode('utf-8', errors='replace').strip()}")
    
    ser.close()
    print("Done.")


def info_mode():
    """Show info about a capture file."""
    if not os.path.exists(CAPTURE_FILE):
        print(f"No capture file: {CAPTURE_FILE}")
        return
    
    packets = load_capture(CAPTURE_FILE)
    print(f"File: {CAPTURE_FILE}")
    print(f"Size: {os.path.getsize(CAPTURE_FILE)} bytes")
    print(f"Packets: {len(packets)}")
    
    if packets:
        first_ts = packets[0][0]
        last_ts = packets[-1][0]
        print(f"Duration: {(last_ts - first_ts)/1000:.2f}s")
        
        # Channel distribution
        ch_counts = {}
        for ts, ch, pay in packets:
            ch_counts[ch] = ch_counts.get(ch, 0) + 1
        print(f"Channels: {dict(sorted(ch_counts.items()))}")
        
        # Show first and last packets
        print(f"\nFirst 5 packets:")
        for ts, ch, pay in packets[:5]:
            print(f"  t={ts}ms ch={ch} [{' '.join(f'{b:02X}' for b in pay[:16])}...]")
        print(f"\nLast 5 packets:")
        for ts, ch, pay in packets[-5:]:
            print(f"  t={ts}ms ch={ch} [{' '.join(f'{b:02X}' for b in pay[:16])}...]")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python capture_replay.py capture   — Record binding sequence")
        print("  python capture_replay.py replay    — Play back once")
        print("  python capture_replay.py replay --loop  — Play in loop")
        print("  python capture_replay.py info      — Show capture file info")
        sys.exit(1)
    
    cmd = sys.argv[1].lower()
    
    if cmd == "capture":
        out = None
        for i, a in enumerate(sys.argv):
            if a == "--output" and i + 1 < len(sys.argv):
                out = sys.argv[i + 1]
        capture_mode(output_file=out)
    elif cmd == "replay":
        loop = "--loop" in sys.argv
        replay_mode(loop=loop)
    elif cmd == "info":
        info_mode()
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
