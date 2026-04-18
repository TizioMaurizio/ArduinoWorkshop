# Playbook: ESP32 + Sensor Wiring Issue

## Scenario
An I2C sensor (e.g., BME280) connected to an ESP32-CAM is returning garbage data or not responding. The breadboard wiring looks correct to the user.

## Agent Call Chain

```
[1] User → @hardware-systems
    "BME280 on ESP32-CAM not responding. I2C scan shows no devices."
    
[2] @hardware-systems (primary diagnostic)
    ├── Checks: pull-up resistors present? (4.7kΩ to 3.3V on SDA/SCL)
    ├── Checks: correct pins? (ESP32-CAM: SDA=GPIO14, SCL=GPIO15? Or user-defined?)
    ├── Checks: GPIO15 is a strapping pin — is it loaded at boot?
    ├── Checks: power supply — is 3.3V stable under sensor load?
    ├── Checks: common ground between sensor breakout and ESP32
    ├── [SAFETY] GPIO15 has boot-time constraint (controls boot log output)
    └── Delegates to @esp-integrator: "Confirm GPIO15 strapping behavior with I2C pull-up"

[3] @esp-integrator
    ├── Confirms: GPIO15 with external pull-up (4.7kΩ to 3.3V) = HIGH at boot
    ├── Effect: suppresses boot log output on UART0 — usually acceptable
    ├── But: if GPIO14/15 are used by camera module, conflict exists
    ├── Checks: ESP32-CAM pinout — which GPIOs are free?
    └── Returns: "GPIO14/15 may conflict with camera HSYNC/VSYNC. Use GPIO13/GPIO16 instead."

[4] @hardware-systems → @driver-implementer
    "Verify BME280 I2C address and initialization sequence"
    
[5] @driver-implementer
    ├── BME280 default I2C address: 0x76 (SDO→GND) or 0x77 (SDO→VCC)
    ├── Checks: is SDO pin connected or floating?
    ├── Checks: chip ID register 0xD0 should return 0x60
    └── Returns: "SDO floating = address unstable. Connect SDO to GND for 0x76."

[6] @hardware-systems synthesizes final answer
```

## Final Output

### Observation
BME280 not responding on I2C scan. Wiring uses GPIO14 (SDA) and GPIO15 (SCL) on ESP32-CAM.

### Root Causes Found
1. **GPIO conflict (certain)**: GPIO14/15 are used by the camera module on ESP32-CAM. They cannot be shared with I2C.
2. **SDO floating (likely)**: BME280 SDO pin not connected → I2C address unstable.
3. **Pull-up present but on wrong pins (certain)**: Pull-ups are wired but the pins themselves are unavailable.

### Recommended Fix
1. Move SDA to GPIO13, SCL to GPIO16 (or other free GPIOs per ESP32-CAM pinout)
2. Connect BME280 SDO to GND (fixes address to 0x76)
3. Add 4.7kΩ pull-ups on the NEW SDA/SCL lines to 3.3V
4. Update `boards/esp32-cam/pins.h` with new I2C pin definitions
5. Run I2C scan sketch to verify: expect 0x76

### Agents Involved
| Agent | Contribution |
|-------|-------------|
| @hardware-systems | Wiring review, pull-up verification, GPIO conflict detection |
| @esp-integrator | Strapping pin behavior, camera module pin conflicts |
| @driver-implementer | BME280 address config, initialization protocol |
