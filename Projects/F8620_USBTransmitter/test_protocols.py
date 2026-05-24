import serial, time

s = serial.Serial('COM4', 115200, timeout=2)
time.sleep(2)
s.read(s.in_waiting)

protocols = [
    ('1', 'Bayang'),
    ('2', 'E010/JJRC H36'),
    ('3', 'CX-10'),
    ('4', 'Syma X5C'),
    ('5', 'H8 mini/H20'),
    ('6', 'MJX'),
]

print('=== F8620 Protocol Discovery ===')
print('For each protocol:')
print('  - Bind packets transmit for ~2 sec')
print('  - Then data packets for ~5 sec')
print('  - If drone LED goes solid during data phase = SUCCESS')
print()
print('IMPORTANT: Power-cycle drone before EACH attempt!')
print('I will pause 8 seconds between protocols for you to power-cycle.')
print()

for num, name in protocols:
    print(f'--- [{num}/6] {name} ---')
    print(f'  >> Power-cycle drone NOW (off then on)')
    time.sleep(8)

    s.write(b's\n')
    time.sleep(0.5)
    s.read(s.in_waiting)

    s.write(f'{num}\n'.encode())
    time.sleep(2)
    data = s.read(s.in_waiting)

    time.sleep(5)
    data += s.read(s.in_waiting)
    output = data.decode('utf-8', errors='replace')

    if 'Bind phase complete' in output:
        print(f'  << Bind packets sent, now transmitting data')
        print(f'  << CHECK DRONE LED NOW: solid = {name} WORKS!')
    else:
        print(f'  << Response: {output.strip()[:80]}')
    print()

s.write(b's\n')
time.sleep(0.5)
s.close()
print('=== Done. Which protocol made the drone LED go solid? ===')
print('Tell me the number (1-6) or none if all failed.')
