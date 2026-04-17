---
mode: agent
description: Review firmware code for correctness, safety, resource usage, and embedded best practices.
---

# Firmware Code Review

You are reviewing embedded firmware code. Apply rigorous embedded engineering standards.

## Review Dimensions

### 1. Correctness
- Does the code do what it claims?
- Are state machines complete — every state has defined transitions and no dead-end states?
- Are edge cases handled: empty input, max values, zero values, overflow?
- Are return values from all I/O functions checked?

### 2. Safety
- Are ISRs minimal (flag set, enqueue, timestamp only)?
- Are shared variables between ISR and main loop declared `volatile`?
- Are there race conditions between tasks or between ISR and main context?
- Is there a safe state for error conditions (motors stopped, outputs off)?
- Are watchdogs fed in all long-running loops?

### 3. Resource Usage
- Estimated RAM impact: stack depth, global buffers, heap allocations.
- Any `String` usage in loops or ISRs? (flag for replacement with `char[]`)
- Any `delay()` in main loop? (flag for replacement with `millis()`-based timing)
- Any dynamic allocation (`new`, `malloc`) in hot paths?

### 4. Hardware Assumptions
- Are pin numbers hardcoded or from board definitions?
- Are I2C addresses verified against datasheets?
- Are timing assumptions documented and within spec?
- Are strapping/boot pins avoided for general-purpose use?

### 5. Maintainability
- Is hardware-specific code separated from logic?
- Can the logic be tested without hardware (mockable interfaces)?
- Are magic numbers replaced with named constants?
- Are error codes defined as enums, not bare integers?

## Review Output Format

For each issue found:

```
[SEVERITY] file.cpp:LINE — CATEGORY
  Issue: description
  Evidence: what you observed
  Fix: suggested change
```

Severity levels:
- **CRITICAL**: will cause crash, data corruption, hardware damage, or security issue
- **HIGH**: will cause incorrect behavior under normal conditions
- **MEDIUM**: will cause problems under edge conditions or degrades maintainability
- **LOW**: style, consistency, or minor improvement

Finish with a summary:
- Total issues by severity
- Overall assessment: ready to merge / needs fixes / needs redesign
- Confidence level for each finding
