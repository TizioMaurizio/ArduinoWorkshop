"""
Bit-alignment analysis of captured packets.
The nRF24 captured data aligned to its own 0xAA*5 address.
The REAL packet starts somewhere inside our captured bytes, shifted by 0-7 bits.
This script tries all 8 bit shifts and looks for consistent patterns.
"""
from capture_replay import load_capture
from collections import Counter

packets = load_capture('single_ch76_capture.rf_capture')
print(f"Analyzing {len(packets)} packets...")
print()

def shift_bits(data, shift):
    """Shift entire byte array left by 'shift' bits (0-7)."""
    if shift == 0:
        return data
    result = bytearray(len(data))
    for i in range(len(data) - 1):
        result[i] = ((data[i] << shift) | (data[i+1] >> (8 - shift))) & 0xFF
    result[-1] = (data[-1] << shift) & 0xFF
    return bytes(result)

# For each bit shift, look at what the first non-0xAA bytes look like
print("=== Bit shift analysis ===")
print("Looking for consistent pattern after preamble ends...")
print()

for shift in range(8):
    patterns = Counter()
    post_preamble = Counter()
    
    for ts, ch, pay in packets:
        shifted = shift_bits(pay, shift)
        
        # Find where preamble (0xAA) ends
        preamble_end = 0
        for i, b in enumerate(shifted):
            if b != 0xAA:
                preamble_end = i
                break
        
        # Capture the first 4 bytes after preamble
        if preamble_end < len(shifted) - 4:
            key = shifted[preamble_end:preamble_end+4]
            post_preamble[key] += 1
    
    # Show top patterns for this shift
    top = post_preamble.most_common(5)
    total_top = sum(c for _, c in top[:3])
    print(f"Shift {shift} bits: top patterns cover {total_top}/{len(packets)} packets")
    for pat, count in top:
        pct = count * 100 / len(packets)
        print(f"  {' '.join(f'{b:02X}' for b in pat)}: {count}x ({pct:.1f}%)")
    print()

# Also try: skip the AA preamble, then look for repeating byte sequences
print("\n=== Looking for sync word candidates ===")
print("If TX uses a non-AA sync word, it will appear consistently after preamble")
print()

# Try each shift and look at raw byte 2-6 (after likely preamble)
for shift in range(8):
    byte_freq = [Counter() for _ in range(10)]
    
    for ts, ch, pay in packets:
        shifted = shift_bits(pay, shift)
        # Look at bytes 2-11 (after the AA AA preamble we know exists)
        for i in range(10):
            if i + 2 < len(shifted):
                byte_freq[i][shifted[i+2]] += 1
    
    # Calculate entropy-like measure: how concentrated is each byte position?
    consistency = []
    for i in range(10):
        if byte_freq[i]:
            top_count = byte_freq[i].most_common(1)[0][1]
            consistency.append(top_count / len(packets))
        else:
            consistency.append(0)
    
    # If there's a clear sync word, bytes 0-3 after preamble will have high consistency
    avg_first4 = sum(consistency[:4]) / 4
    if avg_first4 > 0.3:  # At least 30% consistency
        print(f"Shift {shift}: avg consistency of bytes 2-5 = {avg_first4:.2f}")
        print(f"  Byte positions 2-11 top values:")
        for i in range(10):
            top_val, top_count = byte_freq[i].most_common(1)[0]
            pct = top_count * 100 / len(packets)
            print(f"    pos {i+2}: 0x{top_val:02X} ({pct:.0f}%)")
        print()

# New approach: look for the TRANSITION from preamble to data
# The first non-0xAA byte after the preamble is part of the sync word
print("\n=== Transition byte analysis ===")
print("First non-0xAA byte in raw captures:")
transition = Counter()
for ts, ch, pay in packets:
    for i, b in enumerate(pay):
        if b != 0xAA:
            transition[(i, b)] += 1
            break

for (pos, val), count in transition.most_common(15):
    pct = count * 100 / len(packets)
    # Show binary to see bit pattern
    print(f"  pos={pos} val=0x{val:02X} ({val:08b}): {count}x ({pct:.1f}%)")
