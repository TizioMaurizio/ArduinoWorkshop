---
name: diagnose-serial-boot-issue
description: Diagnose ESP32/ESP8266 serial and boot problems — baud mismatch, boot mode, reset loops, partition corruption, and flash failures.
---

# Diagnose Serial Boot Issue

## When to Use
When an ESP32 or ESP8266 board is:
- Printing garbage on Serial
- Boot-looping (repeated reset)
- Not responding to flash upload
- Showing unexpected boot messages
- Crashing with guru meditation errors or stack traces

## Diagnostic Steps

### 1. Capture the Raw Output
- Open serial monitor at 115200 (default ESP32 boot baud) and 74880 (ESP8266 boot baud).
- Capture at least 3 full boot cycles.
- Save the raw output — do not paraphrase.

### 2. Check Baud Rate
- ESP32 bootloader always outputs at 115200.
- ESP8266 bootloader outputs at 74880, then switches to sketch baud.
- If output is garbage at all baud rates, check: USB cable (data vs charge-only), USB driver, COM port assignment.

### 3. Analyze Boot Messages
Look for these patterns:

| Pattern | Meaning |
|---------|---------|
| `rst:0x1 (POWERON_RESET)` | Normal power-on |
| `rst:0x3 (SW_RESET)` | Software reset (OTA, `ESP.restart()`) |
| `rst:0xc (SW_CPU_RESET)` | Task watchdog or panic |
| `rst:0x10 (RTCWDT_RTC_RESET)` | RTC watchdog — deep sleep wake or hang |
| `boot:0x13 (SPI_FAST_FLASH_BOOT)` | Normal boot from flash |
| `boot:0x33` | Download mode (GPIO0 held low) |
| `Guru Meditation Error` | CPU exception — decode the backtrace |
| `Task watchdog got triggered` | A task blocked too long |
| `Brownout detector was triggered` | Insufficient power supply |

### 4. Decode Stack Traces
- For ESP32: use `xtensa-esp32-elf-addr2line` or PlatformIO's exception decoder.
- For ESP8266: use ESP Exception Decoder Arduino plugin.
- Map addresses back to source file and line number.

### 5. Check Strapping Pins
ESP32 strapping pins that affect boot:
- **GPIO0**: LOW = download mode, HIGH = normal boot
- **GPIO2**: Must be LOW or floating for download mode
- **GPIO12 (MTDI)**: Sets flash voltage (HIGH = 1.8V — usually wrong for most modules)
- **GPIO15 (MTDO)**: Controls boot log output

If any strapping pin has an unexpected load (sensor, pull-up/down), it can prevent boot.

### 6. Check Partition Table
- Verify the partition table matches what was flashed.
- `esptool.py read_flash 0x8000 0xC00 partition_backup.bin` to read current partition table.
- Compare against the expected CSV.
- Mismatched partitions cause boot failures or corrupted OTA.

### 7. Check Flash Integrity
- `esptool.py verify_flash` to compare flash contents against binary.
- `esptool.py flash_id` to verify flash chip size matches board config.
- If flash size is misdetected, the bootloader will read garbage.

### 8. Reset Loop Diagnosis
Common causes:
1. **Stack overflow**: increase task stack size, check for deep recursion.
2. **Watchdog timeout**: find the blocking code. Add `yield()` or `vTaskDelay()`.
3. **Brownout**: use a better power supply, add bulk capacitor (100µF+) on 3.3V.
4. **Failed OTA**: partition mismatch, incomplete write. Reflash factory image.
5. **Corrupted NVS**: erase NVS partition with `esptool.py erase_region`.

### 9. Simulate the Boot Sequence (When Applicable)
If the issue is complex or recurring:
- Model the boot state machine in SimPy or as a timed automaton (UPPAAL).
- Include: bootloader → partition check → app init → WiFi → main loop.
- Inject the observed fault (e.g., corrupted partition, strapping pin conflict, brownout at specific phase).
- Verify the model reproduces the observed behavior.
- Store in `test/simulations/esp-platform/boot_diag_<issue>.py`.
- Use the simulation to predict whether the proposed fix addresses all failure paths.

## Report Template

### Observation
Raw serial output and identified patterns.

### Methodology
Which baud rates tested, which tools used (exception decoder, esptool), which strapping pins checked.

### Result
Root cause with confidence level. Evidence (specific boot message, decoded stack trace, pin measurement).

### Next Steps
Fix procedure (reflash, change wiring, modify code). Verification method.
