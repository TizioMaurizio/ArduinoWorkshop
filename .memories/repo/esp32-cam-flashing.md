# ESP32-CAM Flashing via Arduino UNO Passthrough

## Hardware Setup
- **Board**: ESP32-CAM AI-Thinker (ESP32-D0WD rev v1.0), MAC `c8:2b:96:8e:0a:7c`
- **Adapter**: Arduino UNO used as USB-to-serial passthrough on **COM4**

## Wiring (UNO as passthrough — labels are same-to-same)
| Arduino UNO | ESP32-CAM |
|---|---|
| Pin 0 (RX) | RX (U0RXD / GPIO3) |
| Pin 1 (TX) | TX (U0TXD / GPIO1) |
| GND | GND |
| 5V | 5V |

**UNO RESET → GND** (wire jumper) to hold ATmega in reset so USB-serial chip talks directly.

> **Why same-to-same?** With ATmega held in reset, UNO Pin 0 carries the PC's TX (through CH340/ATmega16U2), and Pin 1 carries PC's RX. The labels refer to the disabled ATmega, not the USB-serial chip.

## Jumpers for Download Mode
- **IO0 → GND** on ESP32-CAM (enables UART download boot)

## Procedure
1. Wire UNO to ESP32-CAM (same-to-same + RESET→GND + IO0→GND)
2. Start the flash command (see below)
3. When output shows `Connecting...`, **press and release ESP32-CAM RESET button**
4. Wait for flash to complete (~50s for full firmware)
5. **Remove IO0→GND jumper**, press RESET to boot normally

## Flash Command (working)
```powershell
C:\Users\Alessandro\.platformio\penv\Scripts\python.exe `
  C:\Users\Alessandro\.platformio\packages\tool-esptoolpy\esptool.py `
  --port COM4 --baud 115200 --before no_reset --chip esp32 `
  write_flash -z --flash_mode dio --flash_freq 40m --flash_size 4MB `
  0x1000 .pio\build\esp32cam\bootloader.bin `
  0x8000 .pio\build\esp32cam\partitions.bin `
  0xe000 C:\Users\Alessandro\.platformio\packages\framework-arduinoespressif32\tools\partitions\boot_app0.bin `
  0x10000 .pio\build\esp32cam\firmware.bin
```

Run from: `Projects/ESP32-CAM-PlatformIO/`

## Key Flags
- `--before no_reset` — **required** because DTR/RTS reset the Arduino, not the ESP32
- `--baud 115200` — works reliably (57600 also works but slower; bootloader outputs at 115200)
- PlatformIO `pio run -t upload` does NOT work because it ignores `upload_flags` for `--before`

## Troubleshooting
- **"No serial data received"**: IO0 not grounded, or you didn't press RESET during `Connecting...`
- **Boot output shows `boot:0x13 (SPI_FAST_FLASH_BOOT)`**: IO0 is NOT grounded — normal boot, not download mode
- **Boot output shows `boot:0x3 (DOWNLOAD_BOOT(UART`**: IO0 IS grounded — correct for flashing
- **COM4 "Access denied"**: Previous process still holds port. Wait a few seconds or close other serial monitors.
- **Zero bytes on serial probe**: TX/RX wires swapped — connect same-labeled pins, not crossed

## Diagnostic: Check boot mode
```powershell
python -c "import serial,time;s=serial.Serial('COM4',115200,timeout=0.1);print('Press RESET');start=time.time();buf=b''
while time.time()-start<8:
 d=s.read(256)
 if d:buf+=d;print(f'[{time.time()-start:.1f}s] {repr(d[:80])}')
if not buf:print('NO DATA')
s.close()"
```
