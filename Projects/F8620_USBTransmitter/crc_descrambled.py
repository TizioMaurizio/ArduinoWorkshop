"""Try CRC on descrambled payload - the CRC is likely computed BEFORE scrambling."""

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

def crc16(data, init, poly):
    crc = init
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ poly) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc

def crc16_reflected(data, init, poly):
    """CRC with reflected algorithm (LSB first)."""
    crc = init
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ poly
            else:
                crc >>= 1
    return crc & 0xFFFF

# Pattern B raw packets
packets_B = [
    [0xB7, 0x98, 0xD8, 0x58, 0xEF, 0xBC, 0xE5, 0xAF, 0x2A, 0xBE, 0x60, 0xE4, 0x12, 0x6B, 0xEE, 0x4A, 0x92, 0xE5, 0x63, 0xAF],
    [0xB7, 0x98, 0xD8, 0x58, 0xEF, 0xBC, 0xE5, 0xAF, 0x0A, 0x3E, 0x20, 0x24, 0x12, 0x6B, 0xEE, 0x4A, 0x92, 0xDC, 0xC2, 0xAF],
    [0xB7, 0x98, 0xD8, 0x58, 0xEF, 0xBC, 0xE5, 0xAF, 0x7A, 0x0E, 0x10, 0x14, 0x12, 0x6B, 0xEE, 0x4A, 0x92, 0x47, 0xC4, 0xAF],
    [0xB7, 0x98, 0xD8, 0x58, 0xEF, 0xBC, 0xE5, 0xAF, 0x02, 0x0E, 0x10, 0x14, 0x12, 0x6B, 0xEE, 0x4A, 0x92, 0xC5, 0xE0, 0xAF],
    [0xB7, 0x98, 0xD8, 0x58, 0xEF, 0xBC, 0xE5, 0xAF, 0x42, 0x8E, 0xD0, 0xD4, 0x12, 0x6B, 0xEE, 0x4A, 0x92, 0xAF, 0x9D, 0xAF],
    [0xB7, 0x98, 0xD8, 0x58, 0xEF, 0xBC, 0xE5, 0xAF, 0x02, 0x8E, 0x10, 0x14, 0x12, 0x6B, 0xEE, 0x4A, 0x92, 0x38, 0x61, 0xAF],
    [0xB7, 0x98, 0xD8, 0x58, 0xEF, 0xBC, 0xE5, 0xAF, 0x22, 0x6E, 0x50, 0xD4, 0x12, 0x6B, 0xEE, 0x4A, 0x92, 0x8C, 0x78, 0xAF],
]

# Descramble all packets (5-byte addr assumption)
ADDR_LEN = 5
descrambled = []
for pkt in packets_B:
    # Payload bytes (after 5-byte address)
    pay = []
    for i in range(ADDR_LEN, 20):
        pay.append(bit_reverse(pkt[i] ^ scramble[i]))
    descrambled.append(pay)

print("Descrambled payloads (15 bytes each):")
for i, pay in enumerate(descrambled):
    print(f"  PKT{i}: {' '.join(f'{b:02X}' for b in pay)}")

# The last byte (index 14) is always 0x5E - likely after the real packet
# CRC candidate: bytes 12-13 (vary), data: bytes 0-11
print("\n" + "=" * 70)
print("TRYING CRC ON DESCRAMBLED PAYLOAD (bytes 0-11 → CRC at 12-13)")
print("=" * 70)

# Broad polynomial search
polys_16 = {
    0x8005: "CRC-16-IBM",
    0x1021: "CRC-16-CCITT",
    0x0589: "CRC-16-DECT",
    0x3D65: "CRC-16-DNP",
    0xC867: "CRC-16-CDMA",
    0x8BB7: "CRC-16-T10",
    0xA097: "CRC-16-TELEDISK",
    0xD175: "CRC-16-USB",
    0x755B: "CRC-16-755B",
    0x5935: "CRC-16-5935",
    0x6F63: "CRC-16-6F63",
    0xAEB7: "CRC-AEB7",
}

found = False
for data_len in [10, 11, 12, 13]:
    for poly_val, poly_name in polys_16.items():
        for init in range(0, 0x10000, 0x0101):  # Sample init values
            all_match = True
            for pay in descrambled[:4]:
                data = pay[:data_len]
                expected = (pay[data_len] << 8) | pay[data_len + 1]
                computed = crc16(data, init, poly_val)
                if computed != expected:
                    all_match = False
                    break
            if all_match:
                # Verify with remaining packets
                remaining_match = all(
                    crc16(pay[:data_len], init, poly_val) == (pay[data_len] << 8) | pay[data_len + 1]
                    for pay in descrambled[4:]
                )
                if remaining_match:
                    print(f"  *** FULL MATCH: {poly_name} (0x{poly_val:04X}) init=0x{init:04X} data_len={data_len}")
                    found = True
                else:
                    print(f"  partial: {poly_name} (0x{poly_val:04X}) init=0x{init:04X} data_len={data_len} (4/7 match)")

# Try reflected CRC too
print("\n--- Trying reflected CRC ---")
reflected_polys = {
    0xA001: "CRC-16-IBM-ref",
    0x8408: "CRC-16-CCITT-ref",
    0xC002: "CRC-16-DECT-ref",
}
for data_len in [10, 11, 12, 13]:
    for poly_val, poly_name in reflected_polys.items():
        for init in range(0, 0x10000, 0x0101):
            all_match = True
            for pay in descrambled[:4]:
                data = pay[:data_len]
                expected = (pay[data_len] << 8) | pay[data_len + 1]
                computed = crc16_reflected(data, init, poly_val)
                if computed != expected:
                    all_match = False
                    break
            if all_match:
                remaining_match = all(
                    crc16_reflected(pay[:data_len], init, poly_val) == (pay[data_len] << 8) | pay[data_len + 1]
                    for pay in descrambled[4:]
                )
                if remaining_match:
                    print(f"  *** FULL MATCH: {poly_name} (0x{poly_val:04X}) init=0x{init:04X} data_len={data_len}")
                    found = True

# Try byte-swapped CRC (maybe CRC is stored little-endian)
print("\n--- Trying byte-swapped CRC (LE) ---")
for data_len in [10, 11, 12, 13]:
    for poly_val, poly_name in polys_16.items():
        for init in range(0, 0x10000, 0x0101):
            all_match = True
            for pay in descrambled[:4]:
                data = pay[:data_len]
                expected = (pay[data_len + 1] << 8) | pay[data_len]  # byte-swapped!
                computed = crc16(data, init, poly_val)
                if computed != expected:
                    all_match = False
                    break
            if all_match:
                remaining_match = all(
                    crc16(pay[:data_len], init, poly_val) == (pay[data_len + 1] << 8) | pay[data_len]
                    for pay in descrambled[4:]
                )
                if remaining_match:
                    print(f"  *** FULL MATCH (LE): {poly_name} (0x{poly_val:04X}) init=0x{init:04X} data_len={data_len}")
                    found = True

# If nothing found with sampled inits, try exhaustive for most likely polys
if not found:
    print("\n--- EXHAUSTIVE init search for poly 0x8005 and 0x1021, data_len=12 ---")
    for poly_val in [0x8005, 0x1021]:
        for init in range(0x10000):
            all_match = True
            for pay in descrambled[:4]:
                data = pay[:12]
                expected = (pay[12] << 8) | pay[13]
                computed = crc16(data, init, poly_val)
                if computed != expected:
                    all_match = False
                    break
            if all_match:
                remaining_match = all(
                    crc16(pay[:12], init, poly_val) == (pay[12] << 8) | pay[13]
                    for pay in descrambled[4:]
                )
                if remaining_match:
                    print(f"  *** FOUND: poly=0x{poly_val:04X} init=0x{init:04X}")
                    found = True
                    break
        if found:
            break
    
    if not found:
        # Try with data_len=10 (excluding AA AA bytes)
        print("--- EXHAUSTIVE init search for poly 0x8005 and 0x1021, data_len=10 ---")
        for poly_val in [0x8005, 0x1021]:
            for init in range(0x10000):
                all_match = True
                for pay in descrambled[:4]:
                    data = pay[:10]
                    expected = (pay[12] << 8) | pay[13]  # CRC at 12-13, skipping AA AA
                    computed = crc16(data, init, poly_val)
                    if computed != expected:
                        all_match = False
                        break
                if all_match:
                    remaining_match = all(
                        crc16(pay[:10], init, poly_val) == (pay[12] << 8) | pay[13]
                        for pay in descrambled[4:]
                    )
                    if remaining_match:
                        print(f"  *** FOUND: poly=0x{poly_val:04X} init=0x{init:04X} (CRC over first 10, at pos 12-13)")
                        found = True
                        break
            if found:
                break

if not found:
    print("\n\n*** STILL NO CRC MATCH ***")
    print("\nLet me check: maybe there's no CRC and bytes 12-13 are a counter/sequence?")
    print("Descrambled bytes 12-13 from all packets:")
    for i, pay in enumerate(descrambled):
        b12_13 = (pay[12] << 8) | pay[13]
        print(f"  PKT{i}: 0x{b12_13:04X} = {b12_13}")
    
    print("\nDifferences between consecutive:")
    for i in range(1, len(descrambled)):
        v_prev = (descrambled[i-1][12] << 8) | descrambled[i-1][13]
        v_curr = (descrambled[i][12] << 8) | descrambled[i][13]
        print(f"  PKT{i-1}→{i}: {v_curr - v_prev:+d} (0x{v_curr:04X} - 0x{v_prev:04X})")
