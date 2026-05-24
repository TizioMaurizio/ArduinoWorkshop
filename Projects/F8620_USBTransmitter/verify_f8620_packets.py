"""
F8620 Packet Verification Script

Verifies that the transmitter logic produces byte-for-byte correct output
matching the captured original TX packets.

Known captured data packet (full on-air):
  55 71 0F B7 98 D8 58 EF BC E5 AF 02 0E 10 14 12 6B EE 4A 92 C5 E0

Expected nRF24 TX address: D8 98 B7 0F 71
Expected nRF24 payload (16 bytes): 58 EF BC E5 AF 02 0E 10 14 12 6B EE 4A 92 C5 E0
"""

import sys

# ==================== PROTOCOL IMPLEMENTATION ====================

SCRAMBLE = [
    0xE3, 0xB1, 0x4B, 0xEA, 0x85, 0xBC, 0xE5, 0x66,
    0x0D, 0xAE, 0x8C, 0x88, 0x12, 0x69, 0xEE, 0x1F,
    0xC7, 0x62, 0x97, 0xD5, 0x0B, 0x79, 0xCA, 0xCC
]

DATA_ADDR_SCRAMBLED = [0xB7, 0x98, 0xD8, 0x58, 0xEF]
BIND_ADDR_SCRAMBLED = [0xE3, 0xB1, 0x4B, 0xEA, 0x85]

CRC_INIT = 0x0000
CRC_POLY = 0x1021
CRC_XOROUT = 0x4358


def bit_reverse(b):
    b = ((b & 0xF0) >> 4) | ((b & 0x0F) << 4)
    b = ((b & 0xCC) >> 2) | ((b & 0x33) << 2)
    b = ((b & 0xAA) >> 1) | ((b & 0x55) << 1)
    return b


def crc16_ccitt(data):
    crc = CRC_INIT
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ CRC_POLY) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc ^ CRC_XOROUT


def scramble_payload(plaintext_12):
    """Scramble 12-byte payload: bit_reverse(byte) XOR scramble[5+i]"""
    result = []
    for i in range(12):
        result.append(bit_reverse(plaintext_12[i]) ^ SCRAMBLE[5 + i])
    return result


def build_data_raw_frame(plaintext_payload_12):
    """Build 19-byte raw XN297 frame."""
    raw = list(DATA_ADDR_SCRAMBLED)  # [0:5]
    raw += scramble_payload(plaintext_payload_12)  # [5:17]
    crc = crc16_ccitt(raw[:17])
    raw.append(crc >> 8)   # [17]
    raw.append(crc & 0xFF) # [18]
    return raw


def get_nrf_address(raw19):
    """Get nRF24 TX address from raw frame."""
    return [raw19[2], raw19[1], raw19[0], 0x0F, 0x71]


def get_nrf_payload(raw19):
    """Get nRF24 16-byte payload from raw frame."""
    return raw19[3:19]


# ==================== VERIFICATION ====================

def verify_known_packet():
    """Verify against the known captured packet."""
    print("=" * 70)
    print("F8620 PACKET VERIFICATION")
    print("=" * 70)

    # Known plaintext payload that produces the captured packet
    # This was decoded from PKT3: [00 00 93 F0 05 39 39 00 40 00 AA AA]
    plaintext = [0x00, 0x00, 0x93, 0xF0, 0x05, 0x39, 0x39, 0x00, 0x40, 0x00, 0xAA, 0xAA]

    # Expected full on-air (after nRF24 auto-preamble 0x55)
    expected_on_air = [
        0x55, 0x71, 0x0F,
        0xB7, 0x98, 0xD8, 0x58, 0xEF,
        0xBC, 0xE5, 0xAF, 0x02, 0x0E, 0x10, 0x14, 0x12, 0x6B, 0xEE, 0x4A, 0x92,
        0xC5, 0xE0
    ]
    expected_nrf_addr = [0xD8, 0x98, 0xB7, 0x0F, 0x71]
    expected_nrf_payload = [0x58, 0xEF, 0xBC, 0xE5, 0xAF, 0x02, 0x0E, 0x10,
                           0x14, 0x12, 0x6B, 0xEE, 0x4A, 0x92, 0xC5, 0xE0]

    all_pass = True

    # Build frame
    raw = build_data_raw_frame(plaintext)

    # 1. Verify scrambled payload
    print("\n--- Scrambled Payload ---")
    expected_scr_pay = expected_on_air[8:20]  # bytes after address
    actual_scr_pay = raw[5:17]
    for i in range(12):
        ok = actual_scr_pay[i] == expected_scr_pay[i]
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False
        print(f"  [{i:2d}] plain={plaintext[i]:02X} → scrambled={actual_scr_pay[i]:02X}"
              f"  expected={expected_scr_pay[i]:02X}  {status}")

    # 2. Verify CRC
    print("\n--- CRC ---")
    actual_crc = (raw[17] << 8) | raw[18]
    expected_crc = (expected_on_air[20] << 8) | expected_on_air[21]
    crc_ok = actual_crc == expected_crc
    if not crc_ok:
        all_pass = False
    print(f"  Computed: 0x{actual_crc:04X}  Expected: 0x{expected_crc:04X}  {'PASS' if crc_ok else 'FAIL'}")

    # 3. Verify nRF24 address
    print("\n--- nRF24 TX Address ---")
    actual_addr = get_nrf_address(raw)
    addr_ok = actual_addr == expected_nrf_addr
    if not addr_ok:
        all_pass = False
    print(f"  Computed: {' '.join(f'{b:02X}' for b in actual_addr)}")
    print(f"  Expected: {' '.join(f'{b:02X}' for b in expected_nrf_addr)}")
    print(f"  {'PASS' if addr_ok else 'FAIL'}")

    # 4. Verify nRF24 payload
    print("\n--- nRF24 Payload (16 bytes) ---")
    actual_nrf_pay = get_nrf_payload(raw)
    pay_ok = actual_nrf_pay == expected_nrf_payload
    if not pay_ok:
        all_pass = False
    print(f"  Computed: {' '.join(f'{b:02X}' for b in actual_nrf_pay)}")
    print(f"  Expected: {' '.join(f'{b:02X}' for b in expected_nrf_payload)}")
    print(f"  {'PASS' if pay_ok else 'FAIL'}")

    # 5. Verify full on-air
    print("\n--- Full On-Air Frame ---")
    actual_on_air = [0x55, 0x71, 0x0F] + raw
    oa_ok = actual_on_air == expected_on_air
    if not oa_ok:
        all_pass = False
    print(f"  Computed: {' '.join(f'{b:02X}' for b in actual_on_air)}")
    print(f"  Expected: {' '.join(f'{b:02X}' for b in expected_on_air)}")
    print(f"  {'PASS' if oa_ok else 'FAIL'}")

    # Summary
    print("\n" + "=" * 70)
    if all_pass:
        print("ALL TESTS PASSED — packet generation is byte-for-byte correct")
    else:
        print("*** SOME TESTS FAILED ***")
    print("=" * 70)

    return all_pass


def verify_multiple_captured_packets():
    """Verify CRC against all 7 captured data packets."""
    print("\n\n--- CRC Verification: All 7 Captured Packets ---")

    packets_B = [
        [0xB7, 0x98, 0xD8, 0x58, 0xEF, 0xBC, 0xE5, 0xAF, 0x2A, 0xBE, 0x60, 0xE4, 0x12, 0x6B, 0xEE, 0x4A, 0x92, 0xE5, 0x63],
        [0xB7, 0x98, 0xD8, 0x58, 0xEF, 0xBC, 0xE5, 0xAF, 0x0A, 0x3E, 0x20, 0x24, 0x12, 0x6B, 0xEE, 0x4A, 0x92, 0xDC, 0xC2],
        [0xB7, 0x98, 0xD8, 0x58, 0xEF, 0xBC, 0xE5, 0xAF, 0x7A, 0x0E, 0x10, 0x14, 0x12, 0x6B, 0xEE, 0x4A, 0x92, 0x47, 0xC4],
        [0xB7, 0x98, 0xD8, 0x58, 0xEF, 0xBC, 0xE5, 0xAF, 0x02, 0x0E, 0x10, 0x14, 0x12, 0x6B, 0xEE, 0x4A, 0x92, 0xC5, 0xE0],
        [0xB7, 0x98, 0xD8, 0x58, 0xEF, 0xBC, 0xE5, 0xAF, 0x42, 0x8E, 0xD0, 0xD4, 0x12, 0x6B, 0xEE, 0x4A, 0x92, 0xAF, 0x9D],
        [0xB7, 0x98, 0xD8, 0x58, 0xEF, 0xBC, 0xE5, 0xAF, 0x02, 0x8E, 0x10, 0x14, 0x12, 0x6B, 0xEE, 0x4A, 0x92, 0x38, 0x61],
        [0xB7, 0x98, 0xD8, 0x58, 0xEF, 0xBC, 0xE5, 0xAF, 0x22, 0x6E, 0x50, 0xD4, 0x12, 0x6B, 0xEE, 0x4A, 0x92, 0x8C, 0x78],
    ]

    all_ok = True
    for i, pkt in enumerate(packets_B):
        data = pkt[:17]
        received_crc = (pkt[17] << 8) | pkt[18]
        computed_crc = crc16_ccitt(data)
        ok = computed_crc == received_crc
        if not ok:
            all_ok = False
        print(f"  PKT{i}: computed=0x{computed_crc:04X} captured=0x{received_crc:04X} {'PASS' if ok else 'FAIL'}")

    print(f"\n  All 7 packets: {'PASS' if all_ok else 'FAIL'}")
    return all_ok


if __name__ == "__main__":
    ok1 = verify_known_packet()
    ok2 = verify_multiple_captured_packets()
    sys.exit(0 if (ok1 and ok2) else 1)
