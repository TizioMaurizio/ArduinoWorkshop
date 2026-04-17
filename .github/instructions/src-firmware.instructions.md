---
applyTo: "Projects/**/*, src/**/*"
---

# Firmware Source Instructions

These instructions apply to all firmware source code in `Projects/` and `src/`.

## Architecture

- Use non-blocking state machines for main loop logic. Each state should have a clear entry condition, action, and exit transition.
- Separate hardware interaction (pin reads, bus transactions) from logic (state evaluation, data processing).
- Use `millis()`-based timing instead of `delay()` for all waits longer than 10µs in non-setup code.
- ISRs must only: set a `volatile` flag, enqueue a value to a ring buffer, or capture a timestamp. No Serial, no Wire, no SPI, no malloc inside ISRs.

## RTOS / Tasking (ESP32)

- When using FreeRTOS tasks, specify stack size explicitly based on measured requirements (not guesses).
- Use queues or semaphores for inter-task communication. Never share raw globals between tasks without synchronization.
- Pin time-critical tasks to a specific core if needed. Document why.

## Memory

- Avoid `String` in loops or ISRs. Use fixed `char[]` buffers with explicit size.
- Prefer stack allocation. Use `static` for large buffers that persist across calls.
- Document the RAM budget for the target board in a comment at the top of the main sketch.

## Error Handling

- Check return values from all I/O operations (Wire, SPI, Serial, WiFi).
- Use timeout guards on all blocking waits. Define timeout constants, don't use magic numbers.
- On unrecoverable error, log the failure and enter a safe state (stop motors, turn off heaters, etc.). Do not silently continue.

## Compilation

- Code must compile with `-Wall -Wextra` without warnings for the target platform.
- Every sketch must declare its target board in a comment or config file.
