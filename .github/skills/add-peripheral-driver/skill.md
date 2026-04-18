---
name: add-peripheral-driver
description: Scaffold a new peripheral driver with interface, bus layer, mock, example sketch, and error handling.
---

# Add Peripheral Driver

## When to Use
When adding support for a new sensor, display, actuator, or any I2C/SPI/UART/OneWire device.

## Inputs Required
- Device name and model number
- Communication protocol (I2C, SPI, UART, OneWire, GPIO)
- Datasheet link or key register map
- Target board(s)

## Steps

### 1. Research the Device
- Locate or request the datasheet.
- Identify: I2C address (or SPI mode), key registers, initialization sequence, data format, timing requirements.
- Check if an existing Arduino library already handles this device — reuse if high quality, wrap if not.

### 2. Scaffold the Driver
Create in `lib/<DeviceName>/`:
```
lib/<DeviceName>/
├── <DeviceName>.h        # public interface
├── <DeviceName>.cpp      # implementation
├── <DeviceName>_defs.h   # register addresses, bit masks, constants
└── README.md             # usage, wiring, datasheet link
```

### 3. Design the Interface
- Constructor accepts pin numbers and optional bus instance.
- `begin()` method initializes the device and returns success/failure.
- Public methods for primary operations (e.g., `read_temperature()`, `set_color()`).
- `last_error()` method returns the most recent error code.
- Transport layer (bus reads/writes) is in a separate protected/private section for mockability.

### 4. Implement Error Handling
- Define error enum: `OK`, `TIMEOUT`, `NACK`, `CRC_ERROR`, `NOT_FOUND`, `INVALID_DATA`.
- Check every bus transaction return value.
- Add retry logic (default 3 attempts) for transient errors.
- Never call `Serial.print()` from inside the driver. Return errors to the caller.

### 5. Create Mock
Create `test/host/fakes/fake_<device_name>.h`:
- Implement the same interface as the real driver.
- Allow test code to inject fake register values and simulate errors.
- Track method call counts for verification.

### 6. Write Example Sketch
Create `Projects/<DeviceName>Example/<DeviceName>Example.ino`:
- Initialize Serial and the driver.
- Read data in a loop with proper error checking.
- Print results to Serial in a parseable format.
- Include wiring instructions in a comment header.

### 7. Add Host-Side Test
Create `test/host/test_<device_name>.cpp`:
- Test data parsing and conversion with known fake register values.
- Test error handling: NACK, timeout, CRC failure.
- Test initialization sequence.

### 8. Run Fault Simulation
Before considering the driver complete, run a fault resilience simulation:
- Create `test/simulations/drivers/<device_name>_faults.py` using SimPy.
- Model the bus transaction sequence (init → read → parse → retry on error).
- Inject faults: consecutive NACKs, timeout, CRC mismatch, mid-transaction reset.
- Record: max consecutive faults before recovery fails, recovery time, fallback trigger.
- Convert any discovered unhandled fault into a new host-side test case.

### 9. Document
- Write `lib/<DeviceName>/README.md` with: wiring table, API reference, example usage, known limitations.
- Update project-level docs if this driver is part of a larger feature.

## Acceptance Criteria
- Driver compiles for all target boards without warnings.
- Example sketch compiles and demonstrates basic usage.
- Host-side test passes with fake data.
- Error paths are tested (including simulation-discovered faults).
- Fault simulation script exists in `test/simulations/drivers/`.
- README includes wiring table and API reference.
