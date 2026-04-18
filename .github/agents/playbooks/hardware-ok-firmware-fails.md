# Playbook: Hardware Works but Firmware Fails

## Scenario
An LED strip (WS2812B) lights up when powered but doesn't respond to firmware commands. Multimeter shows correct voltage. The user suspects a firmware bug.

## Agent Call Chain

```
[1] User → @firmware-architect
    "WS2812B powered on and white, but my sketch doesn't control it. Hardware seems OK."

[2] @firmware-architect (triage)
    ├── Identifies: LED driver code + GPIO assignment + timing-critical protocol
    ├── Delegates to @hardware-systems: "Verify data pin wiring and signal integrity"
    ├── Delegates to @driver-implementer: "Review WS2812B driver code and timing"
    └── Sets max_call_depth: 2

[3] @hardware-systems
    ├── Checks: data pin connected to correct GPIO? Which GPIO in code vs physical wire?
    ├── Checks: 3.3V logic from ESP32 → WS2812B needs 0.7×VCC = 3.5V for HIGH
    ├── [CAUTION] 3.3V logic driving 5V WS2812B: marginal. First LED may work, chain may not.
    ├── Recommends: level shifter (74HCT125) or 3.3V-tolerant WS2812B variant
    └── Returns: "Signal level is marginal. Add a level shifter or try a 470Ω series resistor + shorter wire."

[4] @driver-implementer
    ├── Checks: library used (FastLED? Adafruit NeoPixel?)
    ├── Checks: is the correct GPIO number in code? Does it match `pins.h`?
    ├── Checks: timing — ESP32 needs RMT peripheral for WS2812B (not bit-bang)
    ├── Checks: is WiFi interfering? (WiFi disables some timing-critical operations)
    ├── Delegates to @esp-integrator: "Does WiFi affect RMT timing for NeoPixels?"
    └── Returns: "Use FastLED with RMT driver. Verify GPIO number matches physical connection."

[5] @esp-integrator
    ├── Confirms: ESP32 WiFi does NOT affect RMT-based LED drivers
    ├── But: if using bit-bang (not RMT), WiFi interrupts WILL corrupt timing
    ├── Checks: FastLED ESP32 defaults to RMT — should be fine
    └── Returns: "RMT is safe with WiFi. Ensure FastLED is using RMT (default on ESP32)."

[6] @firmware-architect synthesizes
```

## Final Output

### Root Causes (Priority Order)
1. **Logic level mismatch (likely)**: ESP32 3.3V output is below WS2812B VIH threshold (3.5V at 5V VCC). First LED may flicker, rest stay white.
2. **GPIO mismatch (check)**: pin number in code may not match physical wire.
3. **Library config (unlikely)**: FastLED on ESP32 uses RMT by default — should be fine.

### Fix Procedure
1. **Verify pin match**: compare `LED_PIN` in code with physical wire connection
2. **Add level shifter**: 74HCT125 on data line (3.3V input → 5V output) OR use a single sacrificial WS2812B LED as level shifter at VCC=3.3V
3. **Add 470Ω series resistor** on data line (reduces ringing)
4. **Add 1000µF capacitor** across LED strip VCC/GND (inrush protection)
5. **Compile and flash** with `-DFASTLED_ESP32_I2S` if using many LEDs (alternative driver)

### Agents Involved
| Agent | Contribution |
|-------|-------------|
| @firmware-architect | Triage, task decomposition, final synthesis |
| @hardware-systems | Voltage level analysis, signal integrity |
| @driver-implementer | Library config, RMT driver verification |
| @esp-integrator | WiFi + RMT compatibility confirmation |
