"""
F8620 Protocol Analyzer — Bitstream Analysis
Captures raw demodulated data from nRF24 and finds repeating patterns.

Strategy:
1. Capture many frames from the Arduino (binary protocol)
2. Convert to bitstreams
3. Find common bit patterns via frequency analysis
4. Identify sync word and packet structure
"""

import serial
import time
import sys
from collections import Counter, defaultdict

PORT = 'COM4'
BAUD = 115200
CAPTURE_SECONDS = 15


def capture_frames(port, baud, duration):
    """Capture binary frames from Arduino."""
    frames = []  # list of (channel, bytes[32])
    
    s = serial.Serial(port, baud, timeout=1)
    time.sleep(2)
    
    # Wait for READY
    while True:
        line = s.readline().decode('utf-8', errors='replace').strip()
        if 'READY' in line:
            print("Arduino ready.")
            break
        if 'FAIL' in line:
            print("nRF24 FAIL!")
            s.close()
            return []
    
    print(f"Capturing for {duration} seconds...")
    s.read(s.in_waiting)  # flush
    
    buf = bytearray()
    start = time.time()
    
    while time.time() - start < duration:
        chunk = s.read(s.in_waiting or 256)
        if chunk:
            buf.extend(chunk)
        else:
            time.sleep(0.01)
    
    s.close()
    
    # Parse frames from buffer
    i = 0
    while i < len(buf) - 34:
        if buf[i] == 0xFF and buf[i+1] == 0x00:
            ch = buf[i+2]
            data = bytes(buf[i+3:i+35])
            if ch in (72, 73, 74, 75, 76, 77):
                frames.append((ch, data))
            i += 35
        else:
            i += 1
    
    return frames


def bytes_to_bits(data):
    """Convert bytes to bit string."""
    bits = ''
    for b in data:
        bits += format(b, '08b')
    return bits


def find_ngram_patterns(frames, n_bytes=3):
    """Find most common N-byte sequences across all frames."""
    counter = Counter()
    for ch, data in frames:
        for i in range(len(data) - n_bytes + 1):
            ngram = data[i:i+n_bytes]
            counter[ngram] += 1
    return counter.most_common(30)


def find_bit_transitions(frames):
    """Find where the bit pattern transitions from preamble to data."""
    transition_positions = Counter()
    
    for ch, data in frames:
        bits = bytes_to_bits(data)
        # Find where alternating pattern (1010... or 0101...) breaks
        for i in range(2, len(bits) - 1):
            # Check if previous bits were alternating
            if i >= 4:
                prev4 = bits[i-4:i]
                if prev4 in ('1010', '0101'):
                    # Check if pattern breaks here
                    expected = '1' if bits[i-1] == '0' else '0'
                    if bits[i] != expected:
                        transition_positions[i] += 1
    
    return transition_positions.most_common(20)


def analyze_per_channel(frames):
    """Analyze patterns per channel."""
    by_channel = defaultdict(list)
    for ch, data in frames:
        by_channel[ch].append(data)
    
    print("\n=== Per-Channel Statistics ===")
    for ch in sorted(by_channel.keys()):
        ch_frames = by_channel[ch]
        print(f"\nChannel {ch}: {len(ch_frames)} frames")
        
        # Byte-level frequency for first 10 bytes
        for pos in range(min(10, 32)):
            counter = Counter()
            for f in ch_frames:
                counter[f[pos]] += 1
            top3 = counter.most_common(3)
            total = len(ch_frames)
            desc = ', '.join(f"0x{v:02X}({c}/{total}={100*c//total}%)" for v, c in top3)
            dominant_pct = 100 * top3[0][1] // total if top3 else 0
            flag = " <<<" if dominant_pct > 40 else ""
            print(f"  Byte[{pos}]: {desc}{flag}")


def find_consistent_transitions(frames):
    """Look for byte values that consistently follow 0xAA bytes."""
    # After the preamble (0xAA), what byte appears?
    after_preamble = Counter()
    
    for ch, data in frames:
        # Find last 0xAA in the run, then record next byte
        for i in range(len(data) - 1):
            if data[i] == 0xAA and data[i+1] != 0xAA:
                after_preamble[data[i+1]] += 1
                break
    
    print("\n=== Byte After Preamble (first non-0xAA) ===")
    for val, count in after_preamble.most_common(15):
        bits = format(val, '08b')
        print(f"  0x{val:02X} ({bits}): {count} times")


def find_packet_structure(frames):
    """Try to identify packet boundaries by looking for repeated sequences."""
    # Concatenate all data from strongest channel
    by_channel = defaultdict(list)
    for ch, data in frames:
        by_channel[ch].append(data)
    
    # Use channel with most frames
    best_ch = max(by_channel, key=lambda c: len(by_channel[c]))
    print(f"\n=== Packet Structure Analysis (CH{best_ch}, {len(by_channel[best_ch])} frames) ===")
    
    # Concatenate to bitstream
    all_bits = ''
    for data in by_channel[best_ch][:100]:  # first 100 frames
        all_bits += bytes_to_bits(data)
    
    print(f"Total bits: {len(all_bits)}")
    
    # Look for 8-16 bit patterns that repeat often
    for pattern_len in [8, 12, 16]:
        pattern_counter = Counter()
        for i in range(len(all_bits) - pattern_len):
            pattern = all_bits[i:i+pattern_len]
            # Skip all-same patterns
            if pattern == '1' * pattern_len or pattern == '0' * pattern_len:
                continue
            if pattern == '10' * (pattern_len // 2) or pattern == '01' * (pattern_len // 2):
                continue
            pattern_counter[pattern] += 1
        
        top10 = pattern_counter.most_common(10)
        print(f"\n  Top {pattern_len}-bit patterns (excluding preamble):")
        for pat, count in top10:
            hex_val = int(pat, 2)
            print(f"    {pat} (0x{hex_val:0{pattern_len//4}X}): {count} occurrences")


def try_different_sync_words(frames):
    """Try aligning data to different potential sync words."""
    print("\n=== Sync Word Detection ===")
    
    # Common sync words in toy drone protocols
    sync_candidates = [
        (bytes([0xAA, 0xA0]), "AAA0"),
        (bytes([0xAA, 0xA8]), "AAA8"),
        (bytes([0xAA, 0x80]), "AA80"),
        (bytes([0xA8, 0x00]), "A800"),
        (bytes([0xA0, 0x00]), "A000"),
        (bytes([0x55, 0x55]), "5555"),
        (bytes([0x2A, 0xAA]), "2AAA"),
    ]
    
    for sync, name in sync_candidates:
        matches = 0
        payloads = []
        for ch, data in frames:
            idx = data.find(sync)
            if idx >= 0 and idx + len(sync) + 8 <= len(data):
                matches += 1
                payload = data[idx + len(sync):idx + len(sync) + 8]
                payloads.append(payload)
        
        if matches > 5:
            print(f"\n  Sync '{name}' (0x{sync.hex()}): {matches} matches")
            # Show first few payloads after sync
            for i, p in enumerate(payloads[:5]):
                print(f"    [{i}]: {p.hex()}")
            
            # Check if payloads have structure (low entropy in some positions)
            if len(payloads) > 10:
                for pos in range(min(8, len(payloads[0]))):
                    vals = [p[pos] for p in payloads]
                    counter = Counter(vals)
                    top = counter.most_common(1)[0]
                    pct = 100 * top[1] // len(payloads)
                    if pct > 30:
                        print(f"    Byte[{pos}]: 0x{top[0]:02X} dominates at {pct}%")


def main():
    print("F8620 Protocol Analyzer")
    print("=" * 50)
    
    frames = capture_frames(PORT, BAUD, CAPTURE_SECONDS)
    
    if not frames:
        print("No frames captured!")
        return
    
    print(f"\nCaptured {len(frames)} frames total")
    
    # Run analyses
    analyze_per_channel(frames)
    find_consistent_transitions(frames)
    find_packet_structure(frames)
    try_different_sync_words(frames)
    
    # N-gram analysis
    print("\n=== Most Common 3-byte Sequences ===")
    for ngram, count in find_ngram_patterns(frames, 3)[:15]:
        print(f"  {ngram.hex()}: {count}")
    
    print("\n=== Most Common 4-byte Sequences ===")
    for ngram, count in find_ngram_patterns(frames, 4)[:10]:
        print(f"  {ngram.hex()}: {count}")
    
    # Bit transition analysis
    print("\n=== Bit Transition Points (preamble→data) ===")
    transitions = find_bit_transitions(frames)
    for pos, count in transitions[:10]:
        print(f"  Bit position {pos} (byte {pos//8}.{pos%8}): {count} transitions")


if __name__ == '__main__':
    main()
