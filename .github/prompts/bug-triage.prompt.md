---
mode: agent
description: Triage a firmware bug — reproduce from logs, isolate the hardware/software boundary, propose regression test, then patch minimally.
---

# Bug Triage

You are triaging a firmware bug. Be methodical. Do not guess.

## Input Required
- Bug description or symptom
- Serial logs (if available)
- Board and firmware version
- Steps to reproduce (if known)

## Diagnostic Procedure

### 1. Reproduce
- Parse serial logs for error signatures: stack traces, watchdog triggers, assertion failures, unexpected values.
- If no logs: determine what serial output the code should produce and what's missing.
- Identify the exact point of failure (file, function, line) if possible.

### 2. Isolate
Determine if this is:
- **Software logic bug**: incorrect state machine, wrong calculation, race condition.
- **Hardware interaction bug**: wrong pin, timing violation, bus error, power issue.
- **Configuration bug**: wrong build flag, partition mismatch, wrong board selected.
- **Environmental**: power supply, wiring, interference, temperature.

### 3. Root Cause
- State the root cause with evidence.
- Confidence: certain / likely / speculative.
- If speculative, state what additional information would confirm or deny.

### 4. Minimal Patch
- Propose the smallest code change that fixes the issue.
- Do not refactor unrelated code.
- Do not add features.
- Show before/after for the critical lines.

### 5. Regression Test
- Write a test that would have caught this bug.
- If host-testable: provide the test code.
- If hardware-only: document the manual test procedure.

### 6. Report
Structure as:
- **Observation**: symptoms and evidence
- **Methodology**: diagnostic steps taken
- **Result**: root cause, fix, confidence level
- **Next Steps**: test plan, related areas to audit, open questions
