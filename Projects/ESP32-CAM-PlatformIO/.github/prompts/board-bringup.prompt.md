---
mode: agent
description: Bring up a new board — read board definitions, analyze boot logs, produce a bring-up checklist, identify likely failure points, and propose the smallest safe patch.
---

# Board Bring-Up

You are bringing up a new or unfamiliar microcontroller board. Proceed carefully — incorrect configuration can damage hardware.

## Context Gathering

1. Read the board definition files in `boards/` (pin map, board config, partition table).
2. If boot logs are provided, parse them for: reset reason, boot mode, flash detection, clock speed, memory info.
3. Search the repo for the most similar board that's already working.

## Bring-Up Checklist

### Phase 1: Identity
- [ ] Board detected by USB (COM port appears)
- [ ] Correct USB driver installed (`lsusb` / Device Manager check)
- [ ] `esptool.py chip_id` or `arduino-cli board list` identifies the chip
- [ ] Flash size detected correctly

### Phase 2: Basic Flash
- [ ] Blink sketch compiles for this board
- [ ] Flash upload succeeds without errors
- [ ] Serial output appears at correct baud rate
- [ ] Board resets cleanly after flash (no boot loop)

### Phase 3: Peripherals
- [ ] Status LED works (validates basic GPIO and pin map)
- [ ] Serial TX/RX works (validates UART config)
- [ ] I2C scanner finds expected devices (validates I2C pins and pull-ups)
- [ ] SPI device responds (if applicable)
- [ ] ADC reads sane values on known pin

### Phase 4: Connectivity (ESP only)
- [ ] WiFi scan finds networks
- [ ] WiFi connects to known AP
- [ ] BLE advertise works (if supported)
- [ ] OTA upload works (if partition table supports it)

## Failure Point Analysis

For each phase, identify the most likely failure and its fix:

| Phase | Likely Failure | Root Cause | Fix |
|-------|---------------|------------|-----|
| 1 | No COM port | Missing USB driver | Install CP2102/CH340 driver |
| 2 | Upload fails | Wrong boot mode | Hold BOOT + press EN |
| 2 | Garbage on serial | Baud mismatch | Try 115200 / 74880 |
| 3 | I2C no devices | Wrong SDA/SCL pins | Check board pin map |
| 4 | WiFi won't connect | Antenna not connected | Check u.FL connector |

## Deliverable

Produce:
1. Board identity confirmation (chip, flash size, MAC)
2. Checklist with pass/fail for each item tested
3. Failure analysis table for any failures encountered
4. Smallest safe patch to get the board to a working baseline
5. Open questions or untestable items (missing hardware, peripherals not available)
