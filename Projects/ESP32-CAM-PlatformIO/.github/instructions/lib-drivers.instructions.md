---
applyTo: "lib/**/*"
---

# Library & Driver Instructions

These instructions apply to all shared driver libraries in `lib/`.

## Interface Design

- Every driver must expose a clean C++ class or C API that can be used without knowing the bus implementation details.
- Separate the **transport layer** (I2C read/write, SPI transfer) from the **device logic** (register interpretation, data conversion).
- Transport functions should be injectable or overridable to allow mocking in host-side tests.

## Bus Protocols

### I2C
- Always check `Wire.endTransmission()` return value. Non-zero means error.
- Always check `Wire.requestFrom()` return value matches expected byte count.
- Add configurable retry with backoff for transient NACKs (default: 3 retries, 1ms backoff).
- Document the I2C address (7-bit) and supported clock speeds in the class header comment.

### SPI
- Document SPI mode (0–3), max clock speed, and bit order in the class header.
- Always assert and deassert chip select explicitly. Do not rely on library defaults.
- For multi-device SPI buses, use `SPI.beginTransaction()` / `SPI.endTransaction()` to prevent interleaving.

### UART
- Document baud rate, data bits, parity, and stop bits.
- Implement a packet parser with timeout — do not assume complete packets arrive in a single `Serial.available()` check.
- Use a ring buffer for incoming data. Size the buffer for at least 2x the largest expected packet.

### OneWire
- Always verify CRC on reads. Reject corrupted data.
- Handle the case where no devices are found on the bus.

## Pin Mapping

- **Never hardcode pin numbers in library code.** Accept pins as constructor or `begin()` parameters.
- Default pin values may be provided only if they reference a named constant from a board definition.
- Document which pins are required and which are optional in the class header.

## Timing

- Document minimum and maximum timing requirements in comments.
- For bit-banged protocols, use `delayMicroseconds()` and document the minimum CPU clock speed required.
- For sensors with conversion times (e.g., ADC, temperature), provide both blocking and non-blocking read options.

## Error Reporting

- Return error codes or use a `last_error()` method. Do not silently swallow errors.
- Define an enum for error codes: `OK`, `TIMEOUT`, `NACK`, `CRC_ERROR`, `NOT_FOUND`, etc.
- Never `Serial.println()` errors from inside a library. Let the caller decide how to report.
