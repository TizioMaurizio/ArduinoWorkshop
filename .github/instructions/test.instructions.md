---
applyTo: "test/**/*"
---

# Test Instructions

These instructions apply to all test code in `test/`.

## Test Tiers

1. **Host-side unit tests** (`test/host/`): Run on x86 without hardware. Test logic, state machines, parsers, data conversion. Must be deterministic and fast.
2. **Compile checks** (`test/compile/`): Verify that all sketches and examples compile for each target board. No execution needed.
3. **On-device smoke tests** (`test/device/`): Run on real hardware. Produce serial output that can be checked manually or by a serial log parser.

## Host-Side Tests

- Use a test framework: Unity (PlatformIO native), GoogleTest, or ArduinoFake.
- Mock only what you must. Prefer fakes (simple implementations) over heavy mock frameworks.
- Fake the hardware abstraction layer, not individual library calls. Example: fake `Wire` at the transport level, not individual register reads.
- Tests must be deterministic — no real time, no real I/O, no randomness.
- Use fake clocks for time-dependent logic. Inject `millis()` as a function pointer or template parameter.
- Name test files `test_<module>.cpp`. Name test functions `test_<module>_<behavior>`.

## Regression Tests

- Every bug fix should include a regression test that:
  1. Reproduces the failure condition (would fail without the fix).
  2. Passes with the fix applied.
- If the bug is hardware-only and cannot be reproduced in a host test, document the manual reproduction steps in a comment.

## Compile Checks

- Maintain a list of all board targets in a CI config or script.
- Every example sketch must be included in the compile matrix.
- Compile checks should use the same compiler flags as production builds.

## Serial Log Assertions

- For on-device tests, define expected serial output patterns.
- Use grep-compatible patterns: `[PASS]`, `[FAIL]`, `[ERROR]`, with module and test name.
- Example: `[PASS] dht11_read_temperature: 23.5C within range`

## Test Organization

```
test/
├── host/          # x86 unit tests
│   ├── test_state_machine.cpp
│   ├── test_parser.cpp
│   └── fakes/
│       ├── fake_wire.h
│       └── fake_gpio.h
├── compile/       # compile-only verification
│   └── boards.txt # list of board targets
└── device/        # on-device smoke tests
    ├── smoke_wifi_reconnect.ino
    └── smoke_sensor_read.ino
```

## Anti-Patterns

- Do not write tests that test the mock implementation instead of the real code.
- Do not use `delay()` or `sleep()` in host tests.
- Do not assert on exact floating-point equality. Use epsilon comparisons.
- Do not skip error-path testing — most bugs live in error handling.
