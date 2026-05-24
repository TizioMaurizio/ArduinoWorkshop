"""Quick verification that the TX logic produces correct output."""
scramble = [0xE3, 0xB1, 0x4B, 0xEA, 0x85, 0xBC, 0xE5, 0x66,
            0x0D, 0xAE, 0x8C, 0x88, 0x12, 0x69, 0xEE, 0x1F, 0xC7, 0x62, 0x97, 0xD5]

def bit_reverse(b):
    b = ((b & 0xF0) >> 4) | ((b & 0x0F) << 4)
    b = ((b & 0xCC) >> 2) | ((b & 0x33) << 2)
    b = ((b & 0xAA) >> 1) | ((b & 0x55) << 1)
    return b

def crc16_ccitt(data):
    crc = 0x0000
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc ^ 0x4358

# Test with PKT3 payload: [00 00 93 F0 05 39 39 00 40 00 AA AA]
payload = [0x00, 0x00, 0x93, 0xF0, 0x05, 0x39, 0x39, 0x00, 0x40, 0x00, 0xAA, 0xAA]
addr_scrambled = [0xB7, 0x98, 0xD8, 0x58, 0xEF]

# Scramble payload
scr_pay = [bit_reverse(payload[i]) ^ scramble[5 + i] for i in range(12)]

# Full CRC data
crc_data = addr_scrambled + scr_pay
crc = crc16_ccitt(crc_data)

# Expected from capture (PKT3)
expected_raw = [0xB7, 0x98, 0xD8, 0x58, 0xEF, 0xBC, 0xE5, 0xAF, 0x02, 0x0E, 0x10, 0x14, 0x12, 0x6B, 0xEE, 0x4A, 0x92]
expected_crc = 0xC5E0

print("Scrambled payload verification:")
for i in range(12):
    ok = "✓" if scr_pay[i] == expected_raw[5+i] else "✗"
    print(f"  [{i:2d}] pay={payload[i]:02X} → rev={bit_reverse(payload[i]):02X} → ^scr={scr_pay[i]:02X} expected={expected_raw[5+i]:02X} {ok}")

print(f"\nCRC: computed=0x{crc:04X} expected=0x{expected_crc:04X} {'✓' if crc == expected_crc else '✗'}")

# What the nRF24 sends as payload (16 bytes)
nrf_payload = [addr_scrambled[3], addr_scrambled[4]] + scr_pay + [crc >> 8, crc & 0xFF]
print(f"\nnRF24 on-air address: 71 0F B7 98 D8")
print(f"nRF24 payload (16 bytes): {' '.join(f'{b:02X}' for b in nrf_payload)}")
print(f"\nFull on-air (after auto preamble 55):")
print(f"  55 71 0F B7 98 D8 {' '.join(f'{b:02X}' for b in nrf_payload)}")
print(f"\nExpected from capture:")
print(f"  55 71 0F B7 98 D8 58 EF BC E5 AF 02 0E 10 14 12 6B EE 4A 92 C5 E0")
