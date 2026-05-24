"""Verify XN297 CRC on captured raw packets to determine protocol structure."""

# XN297 scramble table
scramble = [
    0xE3, 0xB1, 0x4B, 0xEA, 0x85, 0xBC, 0xE5, 0x66,
    0x0D, 0xAE, 0x8C, 0x88, 0x12, 0x69, 0xEE, 0x1F,
    0xC7, 0x62, 0x97, 0xD5, 0x0B, 0x79, 0xCA, 0xCC,
    0x1B, 0x5D, 0x19, 0x10, 0x24, 0xD3, 0xDC, 0x3F,
    0x8E, 0xC5, 0x2F, 0xAA, 0x16, 0xF3, 0x95
]

# CRC XOR-out tables
xorout_scrambled = [
    0x0000, 0x3448, 0x9BA7, 0x8BBB, 0x85E1, 0x3E8C,
    0x451E, 0x18E6, 0x6B24, 0xE7AB, 0x3828, 0x814B,
    0xD461, 0xF494, 0x2503, 0x691D, 0xFE8B, 0x9BA7,
    0x8B17, 0x2920, 0x8B5F, 0x61B1, 0xD391, 0x7401,
    0x2138, 0x129F, 0xB3A0, 0x2988, 0x23CA, 0xC0CB,
    0x0C6C, 0xB329, 0xA0A1, 0x0A16, 0xA9D0
]

xorout_unscrambled = [
    0x0000, 0x3D5F, 0xA6F1, 0x3A23, 0xAA16, 0x1CAF,
    0x62B2, 0xE0EB, 0x0821, 0xBE07, 0x5F1A, 0xAF15,
    0x4F0A, 0xAD24, 0x5E48, 0xED34, 0x068C, 0xF2C9,
    0x1852, 0xDF36, 0x129D, 0xB17C, 0xD5F5, 0x70D7,
    0xB798, 0x5133, 0x67DB, 0xD94E, 0x0A5B, 0xE445,
    0xE6A5, 0x26E7, 0xBDAB, 0xC379, 0x8E20
]

# Enhanced mode xorout tables (from multi-protocol source)
xorout_scrambled_enhanced = [
    0x0000, 0x7EBF, 0x3ECE, 0x07A4, 0xCA52, 0x343B,
    0x1F2D, 0x7ACD, 0x04D1, 0x1F9C, 0x070A, 0xB440,
    0x9F5F, 0x1A21, 0x5AA1, 0xFFC2, 0xB6E3, 0x5E28
]

xorout_unscrambled_enhanced = [
    0x0000, 0x4351, 0x5765, 0xA959, 0xB863, 0x9ECF,
    0x9E0A, 0xFB60, 0xB863, 0x3D87, 0x1785, 0x4E4B,
    0xE4C7, 0x3B97, 0xBAA9, 0xB0C3, 0xAC29, 0xA8B4
]

def crc16(data, init=0xB5D2, poly=0x8005):
    """Compute CRC-16 with XN297 parameters."""
    crc = init
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ poly) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc

def bit_reverse(b):
    """Reverse bits in a byte."""
    b = ((b & 0xF0) >> 4) | ((b & 0x0F) << 4)
    b = ((b & 0xCC) >> 2) | ((b & 0x33) << 2)
    b = ((b & 0xAA) >> 1) | ((b & 0x55) << 1)
    return b

def try_decode(raw, verbose=False):
    """Try all addr_len/payload_len combos to find valid CRC."""
    results = []
    
    for addr_len in range(3, 6):
        for pay_len in range(1, len(raw) - addr_len - 1):
            xorout_idx = addr_len + pay_len - 3
            if xorout_idx >= 35:
                break
            
            data = raw[:addr_len + pay_len]
            received_crc = (raw[addr_len + pay_len] << 8) | raw[addr_len + pay_len + 1]
            computed_crc = crc16(data)
            
            # Try unscrambled standard
            if xorout_idx < len(xorout_unscrambled):
                check = (computed_crc ^ xorout_unscrambled[xorout_idx]) & 0xFFFF
                if check == received_crc:
                    results.append(('unscrambled_std', addr_len, pay_len, data, received_crc))
            
            # Try scrambled standard
            if xorout_idx < len(xorout_scrambled):
                check = (computed_crc ^ xorout_scrambled[xorout_idx]) & 0xFFFF
                if check == received_crc:
                    results.append(('scrambled_std', addr_len, pay_len, data, received_crc))
            
            # Try enhanced scrambled
            enh_idx = addr_len + pay_len - 3  # same index?
            # Enhanced mode uses different indexing: just payload_len - 1
            enh_idx2 = pay_len - 1
            if enh_idx2 < len(xorout_scrambled_enhanced):
                check = (computed_crc ^ xorout_scrambled_enhanced[enh_idx2]) & 0xFFFF
                if check == received_crc:
                    results.append(('scrambled_enh', addr_len, pay_len, data, received_crc))
            if enh_idx2 < len(xorout_unscrambled_enhanced):
                check = (computed_crc ^ xorout_unscrambled_enhanced[enh_idx2]) & 0xFFFF
                if check == received_crc:
                    results.append(('unscrambled_enh', addr_len, pay_len, data, received_crc))
            
            # Try NO xorout (raw CRC match)
            if computed_crc == received_crc:
                results.append(('no_xorout', addr_len, pay_len, data, received_crc))
    
    return results

def descramble_packet(raw, addr_len, pay_len, scrambled):
    """Descramble a valid packet."""
    # Address: reverse byte order, optionally XOR with scramble
    addr = []
    for i in range(addr_len):
        if scrambled:
            addr.append(raw[addr_len - 1 - i] ^ scramble[addr_len - 1 - i])
        else:
            addr.append(raw[addr_len - 1 - i])
    
    # Payload: XOR with scramble then bit-reverse (if scrambled), or just bit-reverse
    payload = []
    for i in range(pay_len):
        if scrambled:
            payload.append(bit_reverse(raw[addr_len + i] ^ scramble[addr_len + i]))
        else:
            payload.append(bit_reverse(raw[addr_len + i]))
    
    return addr, payload

# Raw packets captured from Mode 0 (after XN297 preamble {55 0F 71})
# Pattern B packets (most consistent, likely data packets)
packets_B = [
    [0xB7, 0x98, 0xD8, 0x58, 0xEF, 0xBC, 0xE5, 0xAF, 0x2A, 0xBE, 0x60, 0xE4, 0x12, 0x6B, 0xEE, 0x4A, 0x92, 0xE5, 0x63, 0xAF],
    [0xB7, 0x98, 0xD8, 0x58, 0xEF, 0xBC, 0xE5, 0xAF, 0x0A, 0x3E, 0x20, 0x24, 0x12, 0x6B, 0xEE, 0x4A, 0x92, 0xDC, 0xC2, 0xAF],
    [0xB7, 0x98, 0xD8, 0x58, 0xEF, 0xBC, 0xE5, 0xAF, 0x7A, 0x0E, 0x10, 0x14, 0x12, 0x6B, 0xEE, 0x4A, 0x92, 0x47, 0xC4, 0xAF],
    [0xB7, 0x98, 0xD8, 0x58, 0xEF, 0xBC, 0xE5, 0xAF, 0x02, 0x0E, 0x10, 0x14, 0x12, 0x6B, 0xEE, 0x4A, 0x92, 0xC5, 0xE0, 0xAF],
    [0xB7, 0x98, 0xD8, 0x58, 0xEF, 0xBC, 0xE5, 0xAF, 0x42, 0x8E, 0xD0, 0xD4, 0x12, 0x6B, 0xEE, 0x4A, 0x92, 0xAF, 0x9D, 0xAF],
    [0xB7, 0x98, 0xD8, 0x58, 0xEF, 0xBC, 0xE5, 0xAF, 0x02, 0x8E, 0x10, 0x14, 0x12, 0x6B, 0xEE, 0x4A, 0x92, 0x38, 0x61, 0xAF],
    [0xB7, 0x98, 0xD8, 0x58, 0xEF, 0xBC, 0xE5, 0xAF, 0x22, 0x6E, 0x50, 0xD4, 0x12, 0x6B, 0xEE, 0x4A, 0x92, 0x8C, 0x78, 0xAF],
]

# Pattern A packets (address = scramble table → real addr = 00000)
packets_A = [
    [0xE3, 0xB1, 0x4B, 0xEA, 0x85, 0xBC, 0xD4, 0x89, 0xD4, 0x0F, 0x4D, 0x59, 0x7A, 0xEA, 0x9F, 0xCC, 0x70, 0xED, 0xE5, 0xD6],
    [0xE3, 0xB1, 0x4B, 0xEA, 0x85, 0xBC, 0x5C, 0x99, 0x54, 0x0F, 0x5C, 0xAD, 0x49, 0x8D, 0x7C, 0xB1, 0x6A, 0x7A, 0x96, 0x6E],
    [0xE3, 0xB1, 0x4B, 0xEA, 0x85, 0xBD, 0x4C, 0xB8, 0x54, 0x0F, 0x28, 0xDD, 0xC9, 0x5B, 0xB2, 0x10, 0xE2, 0xBA, 0x9E, 0x3B],
    [0xE3, 0xB1, 0x4B, 0xEA, 0x85, 0xBC, 0xD4, 0x89, 0xD4, 0x0F, 0x9D, 0x68, 0x92, 0x24, 0x92, 0x51, 0x4B, 0x55, 0x4A, 0xA5],
    [0xE3, 0xB1, 0x4B, 0xEA, 0x85, 0xBD, 0x4C, 0xB8, 0x54, 0x0E, 0xA5, 0x58, 0x1A, 0xA0, 0x2A, 0x69, 0x09, 0xAD, 0x2A, 0xF9],
    [0xE3, 0xB1, 0x4B, 0xEA, 0x85, 0xBC, 0xD4, 0x89, 0xD4, 0x08, 0xF3, 0x29, 0xE9, 0x77, 0x4D, 0x59, 0x5E, 0x6C, 0xF9, 0x64],
    [0xE3, 0xB1, 0x4B, 0xEA, 0x85, 0xBD, 0xC4, 0xA8, 0xD4, 0x0A, 0xA2, 0x7D, 0xA1, 0x74, 0x55, 0xAC, 0xFE, 0x56, 0x9F, 0xF3],
]

# Also try with the one oddball Pattern B packet
packets_B_odd = [
    [0xB7, 0x98, 0xD8, 0x58, 0xEF, 0xBC, 0x80, 0x00, 0x02, 0x0A, 0x50, 0x02, 0x11, 0x0A, 0x2A, 0x4A, 0x92, 0x8C, 0x78, 0xAF],
]

print("=" * 70)
print("XN297 CRC VERIFICATION")
print("=" * 70)

print("\n--- PATTERN B (common data packets) ---")
for i, pkt in enumerate(packets_B):
    results = try_decode(pkt)
    if results:
        for mode, alen, plen, data, rcrc in results:
            addr, payload = descramble_packet(pkt, alen, plen, 'scrambled' in mode)
            print(f"PKT {i}: {mode} addr_len={alen} pay_len={plen}")
            print(f"  Addr: {' '.join(f'{b:02X}' for b in addr)}")
            print(f"  Pay:  {' '.join(f'{b:02X}' for b in payload)}")
    else:
        print(f"PKT {i}: NO VALID CRC FOUND")

print("\n--- PATTERN A (possible bind packets) ---")
for i, pkt in enumerate(packets_A):
    results = try_decode(pkt)
    if results:
        for mode, alen, plen, data, rcrc in results:
            addr, payload = descramble_packet(pkt, alen, plen, 'scrambled' in mode)
            print(f"PKT {i}: {mode} addr_len={alen} pay_len={plen}")
            print(f"  Addr: {' '.join(f'{b:02X}' for b in addr)}")
            print(f"  Pay:  {' '.join(f'{b:02X}' for b in payload)}")
    else:
        print(f"PKT {i}: NO VALID CRC FOUND")

print("\n--- PATTERN B ODD ---")
for i, pkt in enumerate(packets_B_odd):
    results = try_decode(pkt)
    if results:
        for mode, alen, plen, data, rcrc in results:
            addr, payload = descramble_packet(pkt, alen, plen, 'scrambled' in mode)
            print(f"PKT {i}: {mode} addr_len={alen} pay_len={plen}")
            print(f"  Addr: {' '.join(f'{b:02X}' for b in addr)}")
            print(f"  Pay:  {' '.join(f'{b:02X}' for b in payload)}")
    else:
        print(f"PKT {i}: NO VALID CRC FOUND")

# If no matches, try alternative CRC parameters
print("\n\n--- BRUTE FORCE CRC INIT SEARCH ---")
print("Testing Pattern B pkt 0 with different CRC init values...")
pkt = packets_B[0]
# Try common init values
for init in [0x0000, 0xFFFF, 0xB5D2, 0x3D5F, 0x1234, 0xABCD]:
    for addr_len in [4, 5]:
        for pay_len in range(8, 16):
            if addr_len + pay_len + 2 > len(pkt):
                continue
            data = pkt[:addr_len + pay_len]
            received_crc = (pkt[addr_len + pay_len] << 8) | pkt[addr_len + pay_len + 1]
            computed = crc16(data, init=init)
            # Try raw match (no xorout)
            if computed == received_crc:
                print(f"  MATCH! init=0x{init:04X} addr_len={addr_len} pay_len={pay_len} CRC=0x{received_crc:04X}")

# Try every possible CRC position for Pattern B
print("\n--- TRYING ALL CRC POSITIONS for Pattern B pkt 0 ---")
pkt = packets_B[0]
for crc_pos in range(6, 19):  # CRC at positions 6..18
    received_crc = (pkt[crc_pos] << 8) | pkt[crc_pos + 1]
    for addr_len in [3, 4, 5]:
        if addr_len >= crc_pos:
            continue
        pay_len = crc_pos - addr_len
        data = pkt[:crc_pos]
        computed = crc16(data)
        xorout_idx = addr_len + pay_len - 3
        
        # Check with all xorout tables
        if xorout_idx < len(xorout_scrambled):
            if (computed ^ xorout_scrambled[xorout_idx]) & 0xFFFF == received_crc:
                print(f"  CRC@{crc_pos}: scrambled_std addr={addr_len} pay={pay_len}")
            if (computed ^ xorout_unscrambled[xorout_idx]) & 0xFFFF == received_crc:
                print(f"  CRC@{crc_pos}: unscrambled_std addr={addr_len} pay={pay_len}")
        
        # Enhanced
        enh_idx = pay_len - 1
        if enh_idx < len(xorout_scrambled_enhanced):
            if (computed ^ xorout_scrambled_enhanced[enh_idx]) & 0xFFFF == received_crc:
                print(f"  CRC@{crc_pos}: scrambled_enh addr={addr_len} pay={pay_len}")
            if (computed ^ xorout_unscrambled_enhanced[enh_idx]) & 0xFFFF == received_crc:
                print(f"  CRC@{crc_pos}: unscrambled_enh addr={addr_len} pay={pay_len}")
        
        # No xorout
        if computed == received_crc:
            print(f"  CRC@{crc_pos}: no_xorout addr={addr_len} pay={pay_len}")

print("\n--- MANUAL DESCRAMBLE (assuming 5-byte addr, scrambled) ---")
print("Pattern B (first constant packet):")
pkt = packets_B[3]  # 02 0E 10 14 - near center
addr_descr = [pkt[4-i] ^ scramble[4-i] for i in range(5)]
print(f"  Addr (reversed+XOR): {' '.join(f'{b:02X}' for b in addr_descr)}")

# Payload descramble
print(f"  Raw payload bytes 5-16:")
for i in range(5, 17):
    xored = pkt[i] ^ scramble[i]
    rev = bit_reverse(xored)
    print(f"    [{i:2d}] raw={pkt[i]:02X} ^scr={scramble[i]:02X} = {xored:02X} rev={rev:02X}")
