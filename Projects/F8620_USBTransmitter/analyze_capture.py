"""Quick analysis of single-channel capture."""
from capture_replay import load_capture
from collections import Counter

packets = load_capture('single_ch76_capture.rf_capture')
print(f'Packets: {len(packets)}')
print(f'Duration: {(packets[-1][0] - packets[0][0])/1000:.2f}s')
print(f'Rate: {len(packets) / ((packets[-1][0] - packets[0][0])/1000):.1f} pkt/s')
print()

print('First 10 packets:')
for ts, ch, pay in packets[:10]:
    hex_str = ' '.join(f'{b:02X}' for b in pay[:20])
    print(f'  t={ts:6d}ms  {hex_str}')

print()
print('Last 5 packets:')
for ts, ch, pay in packets[-5:]:
    hex_str = ' '.join(f'{b:02X}' for b in pay[:20])
    print(f'  t={ts:6d}ms  {hex_str}')

# Check for unique patterns
patterns = Counter()
for ts, ch, pay in packets:
    patterns[pay[:4]] += 1
print(f'\nUnique first-4-byte patterns: {len(patterns)}')
for pat, count in patterns.most_common(10):
    print(f'  {" ".join(f"{b:02X}" for b in pat)}: {count}x')
