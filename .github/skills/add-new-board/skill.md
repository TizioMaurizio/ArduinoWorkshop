---
name: add-new-board
description: Add support for a new microcontroller board — pin map, build config, blink test, smoke test, and documentation.
---

# Add New Board

## When to Use
When adding support for a new Arduino or ESP-class microcontroller board to the project.

## Steps

### 1. Create Board Directory
- Duplicate the most similar existing board from `boards/`.
- Rename the directory to `boards/<new-board-name>/`.

### 2. Define Pin Map
- Create `boards/<new-board-name>/pins.h`.
- Define all GPIO pins as `constexpr uint8_t` constants, grouped by function.
- Add comments for: strapping pins, input-only pins, ADC/DAC/touch-capable pins.
- Link to the official pinout diagram or datasheet in a comment.

### 3. Create Board Config
- Create `boards/<new-board-name>/board_config.h`.
- Define: CPU frequency, flash size, RAM size, PSRAM (if any), default serial baud rate.
- For ESP32: include partition table reference.

### 4. Add Build Configuration
- Create PlatformIO env snippet or arduino-cli board config.
- Add the board to the compile matrix in `scripts/build-all.sh`.

### 5. Create Blink Test
- Write a minimal blink sketch that uses the board's status LED pin from `pins.h`.
- This validates: pin map is correct, build config compiles, basic GPIO works.

### 6. Create Smoke Test
- Write `test/device/smoke_<board-name>.ino` that:
  - Prints board name and chip info to Serial
  - Tests basic GPIO (LED on/off)
  - Tests Serial communication
  - For ESP32: prints Wi-Fi MAC address

### 7. Update Documentation
- Create `boards/<new-board-name>/README.md` with:
  - Board name, manufacturer, purchase links
  - Key specs (CPU, flash, RAM, wireless)
  - Pinout diagram or link
  - Known issues and boot-mode notes
  - Required USB driver (if non-standard)

### 8. Verify
- Compile blink test for the new board.
- Run `scripts/build-all.sh` to ensure no regressions.
- Update the root project README board compatibility table.

## Acceptance Criteria
- Pin map compiles without warnings.
- Blink test compiles and (if hardware available) runs correctly.
- Smoke test compiles.
- Board is included in compile matrix.
- README exists with all required sections.
