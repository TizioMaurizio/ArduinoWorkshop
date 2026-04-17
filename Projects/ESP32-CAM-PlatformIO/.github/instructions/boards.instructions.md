---
applyTo: "boards/**/*"
---

# Board Definition Instructions

These instructions apply to all board definitions, pin maps, and variant configurations in `boards/`.

## Pin Maps

- Each board must have a pin map file that defines all used GPIO pins as named constants.
- Use `constexpr uint8_t` (or `const int` for Arduino compatibility) — not `#define`.
- Group pins by function: `// --- Communication ---`, `// --- Sensors ---`, `// --- Actuators ---`, `// --- Status LEDs ---`.
- Document the physical pin / header pin mapping in comments where the silkscreen label differs from GPIO number.
- Include a comment linking to the board's official pinout diagram or datasheet.

## Board Manifest Format

Each board directory should contain:
```
boards/<board-name>/
├── pins.h              # pin definitions
├── board_config.h      # board-specific constants (clock speed, flash size, RAM, etc.)
├── platformio_env.ini  # PlatformIO environment snippet (or equivalent build config)
└── README.md           # board description, pinout link, known issues
```

## Variant Definitions

- When adding a new board variant, duplicate an existing board directory and modify — do not start from scratch.
- Update the build configuration to register the new board in the compile matrix.
- Include a blink test that verifies the status LED pin is correct.

## Partition Tables (ESP32)

- Store custom partition CSVs in the board directory: `boards/<board-name>/partitions.csv`.
- Document the partition layout in the board's README: name, type, subtype, offset, size.
- Never modify a partition table without documenting why and what the previous layout was.

## Build Flags

- Board-specific build flags go in `board_config.h` or the PlatformIO env snippet.
- Do not scatter `-D` flags across multiple files. Centralize per board.
- Document each non-obvious build flag with a one-line comment.

## Safety

- Never assume GPIO capabilities (ADC, DAC, touch, RTC) without checking the datasheet.
- Mark pins that are unsafe to use during boot (e.g., ESP32 strapping pins: GPIO0, GPIO2, GPIO12, GPIO15) with a warning comment.
- Mark pins that are input-only (e.g., ESP32 GPIO34–39) in the pin map.
