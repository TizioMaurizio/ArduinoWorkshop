# F8620 USB Transmitter

Reverse-engineering toolkit to drive the F8620 quadcopter from an Arduino Uno + RF24 module without the original remote. Includes:

- `02_protocol_finder.ino` — try several toy-drone protocols and binds
- Python tools (`capture_replay.py`, `analyze_bitstream.py`, `crc_descrambled.py`, etc.) for capture and analysis

[SAFETY] Always remove propellers during testing.
