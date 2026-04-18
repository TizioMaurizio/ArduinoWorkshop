---
name: optimize-deep-sleep
description: Optimize deep sleep configuration — remove wake blockers, configure RTC memory, reduce duty cycle, and profile power consumption.
---

# Optimize Deep Sleep

## When to Use
When a battery-powered or energy-constrained ESP32/ESP8266 project needs to:
- Reduce average power consumption
- Maximize battery life
- Implement proper sleep/wake duty cycling
- Debug unexpected wake-ups or failure to sleep

## Steps

### 1. Audit Current Power Profile
- Search for `delay()`, `while(true)`, busy loops, always-on peripherals, unnecessary Serial output.
- Check if Wi-Fi/BLE is left on when not needed.
- Identify the duty cycle: how often does the device need to wake, do work, and sleep?
- Estimate current consumption in each state (active, modem sleep, light sleep, deep sleep).

### 2. Identify Wake Blockers
Common reasons deep sleep fails or draws excess current:
- **USB-UART bridge** (CP2102, CH340) draws 5-20mA even in sleep. Cannot be fixed in software if USB is connected.
- **LDO regulator** quiescent current (AMS1117: ~5mA, HT7333: ~8µA). Board selection matters.
- **LEDs** tied to always-on rails — desolder or cut trace if needed.
- **Pull-up/pull-down resistors** on GPIO lines creating current paths.
- **Floating inputs** on GPIO pins not in RTC domain — set unused pins to `INPUT_PULLDOWN` or `INPUT_PULLUP` before sleep.
- **Peripherals** left powered (sensors, displays, radios).

### 3. Configure Wake Sources
ESP32 wake sources:
- **Timer**: `esp_sleep_enable_timer_wakeup(us)` — most common for duty cycling.
- **ext0**: single GPIO (RTC domain only: GPIO 0,2,4,12-15,25-27,32-39).
- **ext1**: multiple GPIOs with AND/OR logic.
- **Touch**: capacitive touch pins.
- **ULP**: Ultra-Low-Power coprocessor can monitor ADC/GPIO while main CPU sleeps.

ESP8266 wake sources:
- **Timer**: `ESP.deepSleep(us)` — requires GPIO16 connected to RST.
- **External reset**: RST pin pulled low.

### 4. RTC Memory Usage
- ESP32 RTC memory: 8KB total. Use `RTC_DATA_ATTR` for variables that persist across deep sleep.
- Store: boot count, last sensor reading, WiFi channel + BSSID (for fast reconnect), state machine state.
- Validate RTC data on wake — check a magic number or CRC to detect cold boot vs warm wake.

### 5. Fast Wi-Fi Reconnect
If the device wakes to send data over Wi-Fi:
- Save WiFi channel and BSSID to RTC memory before sleep.
- On wake, connect with saved channel + BSSID to skip the scan (saves 2-4 seconds and ~100mA).
- Fall back to full scan if fast connect fails.

### 6. Peripheral Power Management
- Power sensors from a GPIO pin so they can be turned off during sleep.
- Use `gpio_hold_en()` to maintain GPIO state during deep sleep (ESP32).
- Disable ADC, DAC, and other unused peripherals before sleeping.
- For I2C/SPI devices with sleep modes, put them to sleep before putting the MCU to sleep.

### 7. Measure and Validate
- Measure current with a µA-capable meter (or INA219/INA226 current sensor).
- Expected deep sleep currents:
  - ESP32 bare module: ~10µA
  - ESP32 DevKit with USB bridge: ~5-20mA (bridge dominates)
  - ESP8266 bare module: ~20µA
- If measured current >> expected, systematically disconnect peripherals to find the draw.

### 8. Energy Model Simulation
Before finalizing the optimization, validate with a decision-theoretic energy simulation:
- Create `test/simulations/power/sleep_<project>.py` using SimPy with energy cost model.
- Model the full duty cycle: boot → init → sense → transmit → sleep → wake.
- Assign energy cost per phase (from datasheet or measurements).
- Sweep parameters: sleep duration, sensor read count, transmit batch size.
- Generate: battery life estimate, Pareto front (energy vs. data freshness), value-of-information curve.
- For POMDP scenarios (adaptive sensing): use `pomdp_py` to find optimal wake policy.
- Store results in `test/simulations/power/sleep_<project>_results/`.

## Report Template

### Observation
Current power profile: measured or estimated mA in each state. Identified wake blockers and inefficiencies. Files and lines cited.

### Methodology
How you identified the issues — what code patterns you searched for, what hardware you considered, what reference currents you used. Include simulation parameters and energy model assumptions.

### Result
Optimizations ranked by impact:
| Change | Est. Savings | Tradeoff | Confidence |
|--------|-------------|----------|------------|
| ... | ... | ... | ... |

Battery life projection from simulation: `X days at Y% duty cycle` (cite simulation script).

### Next Steps
Measurement plan, hardware modifications needed, remaining questions. Simulation re-run conditions.
