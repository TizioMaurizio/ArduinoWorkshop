"""Reverse-engineer the CRC by computing it and finding the XOR-out constant.
If CRC = computed_crc XOR xorout, then xorout = computed_crc XOR received_crc.
If this is consistent across all packets → we found the algorithm!"""

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

def crc16_ref(data, init, poly):
    """Reflected CRC (process LSB first)."""
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

print("=" * 70)
print("REVERSE-ENGINEERING CRC XOR-OUT")
print("=" * 70)
print("Method: xorout = crc16(data) XOR received_crc")
print("If xorout is CONSTANT → we found the CRC!\n")

# Try many combinations
polys = [0x8005, 0x1021, 0x0589, 0x3D65, 0x8BB7, 0xA097, 0xC867, 0xD175]
inits = [0x0000, 0xFFFF, 0xB5D2, 0x1D0F, 0x89EC, 0x5AA5, 0xA55A, 0xDEAD, 0xBEEF, 0x1234, 0x4321]

found = False

# Test with raw bytes (what my Arduino code does)
print("=== RAW BYTES fed to CRC (standard XN297 approach) ===")
for crc_pos in [15, 16, 17, 18]:  # Try different CRC positions
    for poly in polys:
        for init in inits:
            xorouts = set()
            for pkt in packets_B:
                data = pkt[:crc_pos]
                rcrc = (pkt[crc_pos] << 8) | pkt[crc_pos + 1]
                computed = crc16(data, init, poly)
                xorout = (computed ^ rcrc) & 0xFFFF
                xorouts.add(xorout)
            if len(xorouts) == 1:
                print(f"  MATCH! CRC@{crc_pos} poly=0x{poly:04X} init=0x{init:04X} xorout=0x{list(xorouts)[0]:04X}")
                found = True

# Also try: CRC over bit-reversed raw bytes
print("\n=== BIT-REVERSED raw bytes fed to CRC ===")
for crc_pos in [15, 16, 17, 18]:
    for poly in polys:
        for init in inits:
            xorouts = set()
            for pkt in packets_B:
                data = [bit_reverse(b) for b in pkt[:crc_pos]]
                rcrc = (pkt[crc_pos] << 8) | pkt[crc_pos + 1]
                computed = crc16(data, init, poly)
                xorout = (computed ^ rcrc) & 0xFFFF
                xorouts.add(xorout)
            if len(xorouts) == 1:
                print(f"  MATCH! CRC@{crc_pos} poly=0x{poly:04X} init=0x{init:04X} xorout=0x{list(xorouts)[0]:04X}")
                found = True

# Try: CRC over descrambled bytes
print("\n=== DESCRAMBLED bytes (XOR scramble + bit-reverse) fed to CRC ===")
for addr_len in [4, 5]:
    for crc_byte_pos in [15, 16, 17, 18]:  # raw byte position of CRC
        pay_len = crc_byte_pos - addr_len
        for poly in polys:
            for init in inits:
                xorouts = set()
                for pkt in packets_B:
                    # Build descrambled data
                    data = []
                    # Address: reverse byte order + XOR scramble
                    for i in range(addr_len):
                        data.append(pkt[addr_len-1-i] ^ scramble[addr_len-1-i])
                    # Payload: XOR scramble + bit-reverse
                    for i in range(addr_len, crc_byte_pos):
                        data.append(bit_reverse(pkt[i] ^ scramble[i]))
                    
                    # CRC at raw position
                    rcrc = (pkt[crc_byte_pos] << 8) | pkt[crc_byte_pos + 1]
                    computed = crc16(data, init, poly)
                    xorout = (computed ^ rcrc) & 0xFFFF
                    xorouts.add(xorout)
                if len(xorouts) == 1:
                    print(f"  MATCH! addr={addr_len} CRC@raw[{crc_byte_pos}] poly=0x{poly:04X} init=0x{init:04X} xorout=0x{list(xorouts)[0]:04X}")
                    found = True

# Try: CRC over descrambled bytes, CRC itself descrambled
print("\n=== DESCRAMBLED bytes, DESCRAMBLED CRC ===")
for addr_len in [4, 5]:
    for crc_descr_pos in [10, 11, 12, 13]:  # descrambled payload position of CRC
        crc_raw_pos = addr_len + crc_descr_pos
        if crc_raw_pos + 2 > 20:
            continue
        for poly in polys:
            for init in inits:
                xorouts = set()
                valid = True
                for pkt in packets_B:
                    # Build descrambled payload
                    pay = []
                    for i in range(addr_len, crc_raw_pos):
                        pay.append(bit_reverse(pkt[i] ^ scramble[i]))
                    
                    # Descrambled CRC bytes
                    crc_b1 = bit_reverse(pkt[crc_raw_pos] ^ scramble[crc_raw_pos])
                    crc_b2 = bit_reverse(pkt[crc_raw_pos + 1] ^ scramble[crc_raw_pos + 1])
                    rcrc = (crc_b1 << 8) | crc_b2
                    
                    computed = crc16(pay, init, poly)
                    xorout = (computed ^ rcrc) & 0xFFFF
                    xorouts.add(xorout)
                if len(xorouts) == 1:
                    print(f"  MATCH! addr={addr_len} descr_crc@{crc_descr_pos} poly=0x{poly:04X} init=0x{init:04X} xorout=0x{list(xorouts)[0]:04X}")
                    found = True

# Try reflected CRC variants
print("\n=== REFLECTED CRC on raw bytes ===")
ref_polys = [0xA001, 0x8408, 0x9CB2, 0xAC9A]
for crc_pos in [15, 16, 17, 18]:
    for poly in ref_polys:
        for init in inits:
            xorouts = set()
            for pkt in packets_B:
                data = pkt[:crc_pos]
                rcrc = (pkt[crc_pos] << 8) | pkt[crc_pos + 1]
                computed = crc16_ref(data, init, poly)
                xorout = (computed ^ rcrc) & 0xFFFF
                xorouts.add(xorout)
            if len(xorouts) == 1:
                print(f"  MATCH! CRC@{crc_pos} poly=0x{poly:04X} init=0x{init:04X} xorout=0x{list(xorouts)[0]:04X}")
                found = True

if not found:
    print("\n\n*** NO CRC ALGORITHM FOUND ***")
    print("\nThis strongly suggests either:")
    print("1. The CRC uses a truly exotic polynomial not in our search")
    print("2. The CRC includes additional data not visible in our capture")
    print("   (e.g., a frame counter that increments between packets)")
    print("3. There is NO CRC - bytes 12-13 are something else entirely")
    print("\nLet's check hypothesis 2: maybe byte[7] in the raw packet is")
    print("actually a sequence counter that's part of the CRC input:")
    
    # Check if any raw byte pattern correlates with time/sequence
    print("\nRaw bytes that we assumed constant but might be counter:")
    for pos in [5, 6, 7, 12, 13, 14, 15, 16]:
        vals = [pkt[pos] for pkt in packets_B]
        if len(set(vals)) == 1:
            print(f"  Byte {pos}: always 0x{vals[0]:02X}")
        else:
            print(f"  Byte {pos}: varies: {' '.join(f'{v:02X}' for v in vals)}")
    
    print("\nConclusion: bytes 17-18 clearly correlate with bytes 8-11 changes")
    print("This IS a CRC/hash but uses non-standard parameters.")
    print("\nNEXT STEPS:")
    print("1. We don't NEED the CRC to transmit! Many receivers accept without CRC")
    print("2. We know the address, data format, channels, and scramble")
    print("3. Let's try transmitting with the protocol we've decoded!")
