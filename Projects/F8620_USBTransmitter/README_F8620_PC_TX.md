# F8620 PC-Controlled Transmitter

## Architecture

```
PC (pc_control.py)
  │ USB Serial (115200 baud)
  ▼
Arduino Uno (f8620_usb_tx.ino)
  │ SPI
  ▼
nRF24L01+ Module
  │ 2.4 GHz RF (channels 72-77, 1 Mbps)
  ▼
F8620 Drone (C3-7-RX receiver)
```

## ⚠️ SAFETY — READ FIRST

**REMOVE ALL PROPELLERS before any binding or motor test.**

- Default throttle is zero/safe.
- Motors will NOT spin unless you explicitly send `ARM 1`.
- If serial communication stops for >250 ms, failsafe activates (zero throttle).
- Always have a way to disconnect drone battery quickly.

## Hardware Required

| Item | Notes |
|------|-------|
| Arduino Uno (or Elegoo Uno) | CH340 USB-serial |
| nRF24L01+ module | With or without PA+LNA |
| 3.3V adapter or 10µF cap | nRF24 needs clean 3.3V |
| F8620 quadcopter drone | Your own drone only |
| USB cable | For Arduino ↔ PC |

## Wiring

| nRF24L01+ Pin | Arduino Uno Pin | Notes |
|---------------|-----------------|-------|
| VCC | 3.3V | **NOT 5V!** Use adapter if needed |
| GND | GND | |
| CE | D9 | |
| CSN | D10 | |
| MOSI | D11 | |
| MISO | D12 | |
| SCK | D13 | |
| IRQ | (not connected) | |

**Tip**: Add a 10µF electrolytic capacitor between VCC and GND on the nRF24 module to prevent power glitches.

## Software Required

- Arduino IDE or `arduino-cli`
- RF24 library by TMRh20 (install via Library Manager)
- Python 3.x with `pyserial` (`pip install pyserial`)

## File Overview

| File | Purpose |
|------|---------|
| `nrf24_check/nrf24_check.ino` | Hardware test — verifies SPI communication |
| `f8620_usb_tx/f8620_usb_tx.ino` | Main transmitter with serial command interface |
| `pc_control.py` | PC keyboard controller |
| `verify_f8620_packets.py` | Offline packet verification (no hardware needed) |

## Step-by-Step Test Procedure

### Step 1: Verify Packet Generation (no hardware)

```
cd Projects/F8620_USBTransmitter
python verify_f8620_packets.py
```

Expected output: `ALL TESTS PASSED`

If this fails, the protocol implementation has a bug — do not proceed.

### Step 2: Test nRF24 Hardware

Upload `nrf24_check.ino`:

```
arduino-cli compile --fqbn arduino:avr:uno nrf24_check
arduino-cli upload -p COM4 --fqbn arduino:avr:uno nrf24_check
```

Open serial monitor at **115200 baud**. Expected:
```
=== nRF24L01+ HARDWARE CHECK ===
radio.begin(): OK
isChipConnected(): YES
...
=== HARDWARE CHECK PASSED ===
```

If it says FAILED, check wiring (especially VCC=3.3V, not 5V).

### Step 3: Upload Transmitter

```
arduino-cli compile --fqbn arduino:avr:uno f8620_usb_tx
arduino-cli upload -p COM4 --fqbn arduino:avr:uno f8620_usb_tx
```

Open serial monitor at **115200 baud**. Expected:
```
=== F8620 PC TX — XN297 Protocol ===
*** REMOVE PROPELLERS BEFORE TESTING ***
Radio OK. PA=LOW.
```

### Step 4: Bind Test

1. **Remove propellers** from drone
2. Power on the drone (connect battery)
3. Drone LED should blink (searching for TX)
4. In serial monitor, type: `BIND` + Enter
5. Wait 4 seconds (bind packets sent)
6. After bind completes, Arduino sends safe data packets

**Signs of success:**
- Drone LED changes from fast blink to slow blink or solid
- Drone may beep or motors may twitch briefly

**If bind fails**, try these serial commands:
```
MODE DATA_ONLY
MODE BIND_REPLAY
MODE BIND_THEN_DATA
MODE REPEATED
CH 76
CH HOP
```

### Step 5: PC Controller

```
python pc_control.py COM4
```

Controls:
- `b` = send BIND
- `a` = toggle ARM/DISARM
- `SPACE` = immediate SAFE
- `r`/`f` = throttle up/down
- `w`/`s` = pitch
- `q`/`e` = yaw
- `d`/left-`a` = roll (when armed)
- `ESC` = safe exit

### Step 6: Motor Test (propellers removed!)

1. Confirm bind is successful (drone LED changed)
2. Press `a` to arm
3. Press `r` slowly to increase throttle
4. Motors should spin (propellers removed!)
5. Press `SPACE` to immediately stop

## Serial Command Reference

| Command | Description |
|---------|-------------|
| `STATUS` | Print current state, mode, values |
| `SAFE` | Zero throttle, neutral axes, disarm |
| `BIND` | Start 4-second bind sequence |
| `ARM 1` | Enable motor commands |
| `ARM 0` | Disarm, force safe |
| `SET T Y P R` | Set axes (T:0-100, YPR:-100..100) |
| `RAW t y p r f1 f2 f3` | Set raw protocol bytes (0-255) |
| `MODE BIND_REPLAY` | Replay captured bind frames |
| `MODE DATA_ONLY` | Skip bind, data packets only |
| `MODE BIND_THEN_DATA` | Bind then data (default) |
| `MODE REPEATED` | Alternate bind and data |
| `CH HOP` | Hop channels 72-77 (default) |
| `CH 72` | Fixed channel 72 |
| `CH 76` | Fixed channel 76 |

## Troubleshooting

### nRF24 not detected
- Check VCC is 3.3V (5V damages the module)
- Check all SPI wires: MOSI=D11, MISO=D12, SCK=D13
- Check CE=D9, CSN=D10
- Add 10µF capacitor on VCC/GND
- Try shorter wires

### No bind (drone keeps blinking)
- Try `MODE BIND_REPLAY` — uses exact captured bind frames
- Try `MODE DATA_ONLY` — maybe drone is already bound from original TX
- Try `CH 76` — maybe drone listens on single channel during bind
- Power-cycle drone between attempts
- Try `RAW 240 5 57 57 0 64 0` — original center values (F0 05 39 39 00 40 00)
- Increase PA: edit sketch, change `RF24_PA_LOW` to `RF24_PA_MAX`

### Drone responds but behaves wrong
- Axis mapping may be incorrect (throttle/yaw/pitch/roll order)
- Try `RAW` command to send specific byte values
- Values 0x00 for throttle should be safe/no-spin
- Value 0xF0 was observed center on original TX — may be needed for "idle" state

### Verification script fails
- Protocol implementation bug
- Compare against captured packets in `protocol_final.py`
- Ensure scramble table matches exactly

## Protocol Summary

- **Type**: Custom XN297-compatible (NOT Bayang)
- **Channels**: 72, 73, 74, 75, 76, 77
- **Data rate**: 1 Mbps
- **CRC**: CRC-16/CCITT (poly=0x1021, init=0x0000, xorout=0x4358)
- **Scramble**: Standard XN297 scramble table
- **Address**: Scrambled `B7 98 D8 58 EF` (descrambled: `54 29 93 B2 6A`)
- **Payload**: 12 bytes (header + 4 axes + 3 flags + padding)

## Known Unknowns

1. **Axis mapping**: byte[3] is likely throttle, [4] yaw, [5] pitch, [6] roll — but not 100% confirmed by joystick movement tests.
2. **Throttle safe value**: 0x00 assumed safe; original TX sent ~0xF0 at rest. The drone may require 0xF0 to mean "connected but idle" rather than 0x00.
3. **Bind CRC**: Pattern A (bind) packets use a different CRC variant not yet decoded. We replay captured frames directly.
4. **Flag bytes**: byte[8]=0x40 may be required for normal operation. Try with and without.
