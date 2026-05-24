"""Deep CRC analysis - try many CRC variants to crack the protocol."""

# XN297 scramble table
scramble = [
    0xE3, 0xB1, 0x4B, 0xEA, 0x85, 0xBC, 0xE5, 0x66,
    0x0D, 0xAE, 0x8C, 0x88, 0x12, 0x69, 0xEE, 0x1F,
    0xC7, 0x62, 0x97, 0xD5, 0x0B, 0x79, 0xCA, 0xCC,
    0x1B, 0x5D, 0x19, 0x10, 0x24, 0xD3, 0xDC, 0x3F,
    0x8E, 0xC5, 0x2F, 0xAA, 0x16, 0xF3, 0x95
]

def bit_reverse(b):
    b = ((b & 0xF0) >> 4) | ((b & 0x0F) << 4)
    b = ((b & 0xCC) >> 2) | ((b & 0x33) << 2)
    b = ((b & 0xAA) >> 1) | ((b & 0x55) << 1)
    return b

def crc16(data, init=0xB5D2, poly=0x8005):
    crc = init
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ poly) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc

def crc16_reflected(data, init=0xB5D2, poly=0x8005):
    """CRC with reflected input (bit-reverse each byte before feeding)."""
    crc = init
    for byte in data:
        byte = bit_reverse(byte)
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ poly) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc

def crc8(data, init=0x00, poly=0x07):
    crc = init
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ poly) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc

def checksum8(data):
    return sum(data) & 0xFF

def checksum16(data):
    return sum(data) & 0xFFFF

# Pattern B packets (most consistent)
packets_B = [
    [0xB7, 0x98, 0xD8, 0x58, 0xEF, 0xBC, 0xE5, 0xAF, 0x2A, 0xBE, 0x60, 0xE4, 0x12, 0x6B, 0xEE, 0x4A, 0x92, 0xE5, 0x63, 0xAF],
    [0xB7, 0x98, 0xD8, 0x58, 0xEF, 0xBC, 0xE5, 0xAF, 0x0A, 0x3E, 0x20, 0x24, 0x12, 0x6B, 0xEE, 0x4A, 0x92, 0xDC, 0xC2, 0xAF],
    [0xB7, 0x98, 0xD8, 0x58, 0xEF, 0xBC, 0xE5, 0xAF, 0x7A, 0x0E, 0x10, 0x14, 0x12, 0x6B, 0xEE, 0x4A, 0x92, 0x47, 0xC4, 0xAF],
    [0xB7, 0x98, 0xD8, 0x58, 0xEF, 0xBC, 0xE5, 0xAF, 0x02, 0x0E, 0x10, 0x14, 0x12, 0x6B, 0xEE, 0x4A, 0x92, 0xC5, 0xE0, 0xAF],
    [0xB7, 0x98, 0xD8, 0x58, 0xEF, 0xBC, 0xE5, 0xAF, 0x42, 0x8E, 0xD0, 0xD4, 0x12, 0x6B, 0xEE, 0x4A, 0x92, 0xAF, 0x9D, 0xAF],
    [0xB7, 0x98, 0xD8, 0x58, 0xEF, 0xBC, 0xE5, 0xAF, 0x02, 0x8E, 0x10, 0x14, 0x12, 0x6B, 0xEE, 0x4A, 0x92, 0x38, 0x61, 0xAF],
    [0xB7, 0x98, 0xD8, 0x58, 0xEF, 0xBC, 0xE5, 0xAF, 0x22, 0x6E, 0x50, 0xD4, 0x12, 0x6B, 0xEE, 0x4A, 0x92, 0x8C, 0x78, 0xAF],
]

print("=" * 70)
print("DEEP CRC ANALYSIS")
print("=" * 70)

# First, let's determine where the CRC is by looking at what bytes correlate
# with the changing data bytes (8-11)
print("\n--- BYTE ANALYSIS (Pattern B) ---")
print("Byte positions that VARY across packets:")
for pos in range(20):
    values = set(pkt[pos] for pkt in packets_B)
    if len(values) > 1:
        print(f"  Byte {pos:2d}: {' '.join(f'{pkt[pos]:02X}' for pkt in packets_B)}")

# Try CRC-16 with many different polynomials and init values
print("\n--- EXHAUSTIVE CRC-16 POLYNOMIAL SEARCH ---")
print("Testing: data = bytes[0:N], CRC = bytes[N:N+2]")
polys = [0x8005, 0x1021, 0x0589, 0x3D65, 0xC867, 0xA097, 0x8BB7, 0xD175]
inits = [0x0000, 0xFFFF, 0xB5D2, 0x1D0F, 0xBEEF, 0x5AA5, 0xA55A]

found_any = False
for data_end in range(8, 19):  # CRC at different positions
    for poly in polys:
        for init in inits:
            # Check if CRC matches for ALL packets
            all_match = True
            for pkt in packets_B[:4]:  # Test first 4 packets
                data = pkt[:data_end]
                rcrc = (pkt[data_end] << 8) | pkt[data_end + 1]
                computed = crc16(data, init, poly)
                if computed != rcrc:
                    all_match = False
                    break
            if all_match:
                print(f"  MATCH: poly=0x{poly:04X} init=0x{init:04X} data[0:{data_end}] CRC@{data_end}")
                found_any = True

# Also try with descrambled data fed to CRC
print("\n--- CRC ON DESCRAMBLED DATA ---")
for addr_len in [4, 5]:
    for data_end in range(addr_len + 2, 19):
        pay_len = data_end - addr_len
        for poly in [0x8005, 0x1021]:
            for init in [0x0000, 0xFFFF, 0xB5D2]:
                all_match = True
                for pkt in packets_B[:4]:
                    # Descramble: addr reversed + payload XOR + bit-reversed
                    descr = []
                    for i in range(addr_len):
                        descr.append(pkt[addr_len - 1 - i] ^ scramble[addr_len - 1 - i])
                    for i in range(addr_len, data_end):
                        descr.append(bit_reverse(pkt[i] ^ scramble[i]))
                    
                    rcrc = (pkt[data_end] << 8) | pkt[data_end + 1]
                    computed = crc16(descr, init, poly)
                    if computed != rcrc:
                        all_match = False
                        break
                if all_match:
                    print(f"  MATCH: poly=0x{poly:04X} init=0x{init:04X} addr_len={addr_len} pay_len={pay_len}")
                    found_any = True

# Try CRC-8
print("\n--- CRC-8 SEARCH ---")
for data_end in range(8, 20):
    for poly in [0x07, 0x31, 0x1D, 0x9B, 0x39, 0xD5]:
        for init in [0x00, 0xFF, 0xB5]:
            all_match = True
            for pkt in packets_B[:4]:
                data = pkt[:data_end]
                rcrc = pkt[data_end]
                computed = crc8(data, init, poly)
                if computed != rcrc:
                    all_match = False
                    break
            if all_match:
                print(f"  MATCH: poly=0x{poly:02X} init=0x{init:02X} data[0:{data_end}] CRC@{data_end}")
                found_any = True

# Try simple checksum
print("\n--- CHECKSUM SEARCH ---")
for data_start in range(0, 8):
    for data_end in range(data_start + 4, 19):
        # 8-bit checksum
        all_match_8 = True
        all_match_neg = True
        for pkt in packets_B[:4]:
            data = pkt[data_start:data_end]
            cksum = checksum8(data)
            if cksum != pkt[data_end]:
                all_match_8 = False
            if (0x100 - cksum) & 0xFF != pkt[data_end]:
                all_match_neg = False
        if all_match_8:
            print(f"  SUM8 MATCH: data[{data_start}:{data_end}] check@{data_end}")
            found_any = True
        if all_match_neg:
            print(f"  NEG_SUM8 MATCH: data[{data_start}:{data_end}] check@{data_end}")
            found_any = True

# Try XOR checksum
print("\n--- XOR CHECKSUM ---")
for data_start in range(0, 8):
    for data_end in range(data_start + 4, 19):
        all_match = True
        for pkt in packets_B[:4]:
            xor_val = 0
            for b in pkt[data_start:data_end]:
                xor_val ^= b
            if xor_val != pkt[data_end]:
                all_match = False
                break
        if all_match:
            print(f"  XOR MATCH: data[{data_start}:{data_end}] check@{data_end}")
            found_any = True

if not found_any:
    print("\n*** NO STANDARD CRC/CHECKSUM FOUND ***")
    print("Possibilities:")
    print("  1. Protocol has NO CRC (all bytes are payload)")
    print("  2. CRC uses non-standard polynomial")
    print("  3. CRC is computed on differently-processed data")
    print("  4. This is NOT XN297 - might be BK2421/nRF24 with matching preamble")

# Let's also check: what if bytes 17-18 are NOT CRC but just more payload?
# And there IS no CRC at all? Let's see if the descrambled values make sense
print("\n\n--- FULL DESCRAMBLE (no CRC, 5-byte addr, 15-byte payload) ---")
for i, pkt in enumerate(packets_B):
    addr = [pkt[4-j] ^ scramble[4-j] for j in range(5)]
    pay = [bit_reverse(pkt[5+j] ^ scramble[5+j]) for j in range(15)]
    print(f"PKT{i}: addr={' '.join(f'{b:02X}' for b in addr)}  pay={' '.join(f'{b:02X}' for b in pay)}")

print("\n--- FULL DESCRAMBLE (no CRC, 4-byte addr, 16-byte payload) ---")
for i, pkt in enumerate(packets_B):
    addr = [pkt[3-j] ^ scramble[3-j] for j in range(4)]
    pay = [bit_reverse(pkt[4+j] ^ scramble[4+j]) for j in range(16)]
    print(f"PKT{i}: addr={' '.join(f'{b:02X}' for b in addr)}  pay={' '.join(f'{b:02X}' for b in pay)}")

# Also consider: maybe the packet is shorter and the trailing bytes are just noise
# If so, what if it's addr=5 + payload=10 + CRC=2 = 17 bytes total?
print("\n--- HYPOTHESIS: 5-byte addr + 10-byte payload + 2-byte CRC (17 bytes) ---")
# Then bytes 15-16 = CRC, bytes 17-19 = noise
print("CRC candidates (bytes 15-16):")
for i, pkt in enumerate(packets_B):
    print(f"  PKT{i}: CRC = {pkt[15]:02X} {pkt[16]:02X}")
# Bytes 15 is always 4A, byte 16 is always 92 — CONSTANT → not CRC!

# If addr=5 + payload=12 + CRC=2 = 19 bytes
print("\n--- HYPOTHESIS: 5-byte addr + 12-byte payload + 2-byte CRC (19 bytes) ---")
print("CRC candidates (bytes 17-18):")
for i, pkt in enumerate(packets_B):
    print(f"  PKT{i}: data changes=[{pkt[8]:02X} {pkt[9]:02X} {pkt[10]:02X} {pkt[11]:02X}] CRC = {pkt[17]:02X} {pkt[18]:02X}")

# The CRC hypothesis for 12-byte payload makes sense since bytes 17-18 vary
# Let me try CRC with XN297 params but EXCLUDING address from CRC
print("\n--- CRC ON PAYLOAD ONLY (excluding address) ---")
for addr_len in [4, 5]:
    for pay_end_offset in [12, 13, 14]:
        pay_start = addr_len
        pay_end = pay_start + pay_end_offset
        if pay_end + 2 > 20:
            continue
        for poly in [0x8005, 0x1021]:
            for init in [0x0000, 0xFFFF, 0xB5D2]:
                all_match = True
                for pkt in packets_B[:4]:
                    data = pkt[pay_start:pay_end]
                    rcrc = (pkt[pay_end] << 8) | pkt[pay_end + 1]
                    computed = crc16(data, init, poly)
                    if computed != rcrc:
                        all_match = False
                        break
                if all_match:
                    print(f"  MATCH: poly=0x{poly:04X} init=0x{init:04X} addr={addr_len} payload bytes [{pay_start}:{pay_end}]")
                    found_any = True
