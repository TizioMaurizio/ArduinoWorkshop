"""
Systematic bind attempt: cycle through all CRC, address width, and payload size combos.
Sends commands to the 15_bind_hopping sketch.
User watches drone LEDs and presses Ctrl+C if binding occurs.
"""
import serial
import time

COMBOS = [
    # (crc_cmd, addr_cmd, size_cmd, description)
    ('0', '5', 'G', 'CRC=OFF addr=5 pay=32'),
    ('1', '5', 'G', 'CRC=8 addr=5 pay=32'),
    ('2', '5', 'G', 'CRC=16 addr=5 pay=32'),
    ('0', '5', 'F', 'CRC=OFF addr=5 pay=15'),
    ('1', '5', 'F', 'CRC=8 addr=5 pay=15'),
    ('2', '5', 'F', 'CRC=16 addr=5 pay=15'),
    ('0', '5', 'A', 'CRC=OFF addr=5 pay=10'),
    ('1', '5', 'A', 'CRC=8 addr=5 pay=10'),
    ('2', '5', 'A', 'CRC=16 addr=5 pay=10'),
    ('0', '4', 'F', 'CRC=OFF addr=4 pay=15'),
    ('1', '4', 'F', 'CRC=8 addr=4 pay=15'),
    ('2', '4', 'F', 'CRC=16 addr=4 pay=15'),
    ('0', '4', 'A', 'CRC=OFF addr=4 pay=10'),
    ('1', '4', 'A', 'CRC=8 addr=4 pay=10'),
    ('2', '4', 'A', 'CRC=16 addr=4 pay=10'),
    ('0', '3', 'F', 'CRC=OFF addr=3 pay=15'),
    ('1', '3', 'F', 'CRC=8 addr=3 pay=15'),
    ('2', '3', 'F', 'CRC=16 addr=3 pay=15'),
    ('0', '3', 'A', 'CRC=OFF addr=3 pay=10'),
    ('1', '3', 'A', 'CRC=8 addr=3 pay=10'),
    ('2', '3', 'A', 'CRC=16 addr=3 pay=10'),
    ('0', '4', 'G', 'CRC=OFF addr=4 pay=32'),
    ('1', '4', 'G', 'CRC=8 addr=4 pay=32'),
    ('2', '4', 'G', 'CRC=16 addr=4 pay=32'),
    ('0', '3', 'G', 'CRC=OFF addr=3 pay=32'),
    ('1', '3', 'G', 'CRC=8 addr=3 pay=32'),
    ('2', '3', 'G', 'CRC=16 addr=3 pay=32'),
    ('0', '4', '8', 'CRC=OFF addr=4 pay=8'),
    ('1', '4', '8', 'CRC=8 addr=4 pay=8'),
    ('2', '4', '8', 'CRC=16 addr=4 pay=8'),
    ('0', '3', '8', 'CRC=OFF addr=3 pay=8'),
    ('1', '3', '8', 'CRC=8 addr=3 pay=8'),
    ('2', '3', '8', 'CRC=16 addr=3 pay=8'),
    ('0', '5', '8', 'CRC=OFF addr=5 pay=8'),
    ('1', '5', '8', 'CRC=8 addr=5 pay=8'),
    ('2', '5', '8', 'CRC=16 addr=5 pay=8'),
]

DWELL_TIME = 5  # seconds per combination

ser = serial.Serial('COM4', 1000000, timeout=0.5)
time.sleep(2)
startup = ser.read(ser.in_waiting).decode('utf-8', 'replace')
print(startup)

print(f"\n=== SYSTEMATIC BIND SWEEP ({len(COMBOS)} combos, {DWELL_TIME}s each) ===")
print(f"Total time: ~{len(COMBOS) * DWELL_TIME // 60}min {len(COMBOS) * DWELL_TIME % 60}s")
print("Watch drone LEDs! Press Ctrl+C if binding occurs.\n")

try:
    for i, (crc, addr, size, desc) in enumerate(COMBOS):
        # Send commands
        ser.write(crc.encode())
        time.sleep(0.1)
        ser.write(addr.encode())
        time.sleep(0.1)
        ser.write(size.encode())
        time.sleep(0.1)
        
        # Read responses
        time.sleep(0.3)
        resp = ser.read(ser.in_waiting).decode('utf-8', 'replace').strip()
        
        print(f"[{i+1}/{len(COMBOS)}] {desc}")
        if resp:
            for line in resp.split('\n'):
                if line.strip() and 'TX:' not in line:
                    print(f"       {line.strip()}")
        
        # Dwell
        time.sleep(DWELL_TIME)
        
        # Drain serial
        ser.read(ser.in_waiting)

except KeyboardInterrupt:
    print(f"\n\n*** STOPPED at combo #{i+1}: {desc} ***")
    print("If drone bound, this is the working configuration!")

ser.close()
print("\nDone.")
