---
mode: agent
description: Plan a new firmware feature with constraints, affected modules, compile targets, test strategy, and documentation changes.
---

# New Feature Planning

You are planning a new firmware feature for this embedded project. Follow this structure rigorously.

## Context Gathering

1. Read the feature request or user description.
2. Search the repository for related existing code, modules, and board configurations.
3. Identify the target board(s) and their constraints (RAM, flash, peripherals).

## Deliverable

Produce a structured plan with these sections:

### Feature Scope
- What the feature does (one paragraph).
- What it explicitly does NOT do (constraints and non-goals).

### Affected Modules
| Module | Path | Change Type |
|--------|------|-------------|
| ... | ... | new / modified / none |

### Hardware Requirements
- Required peripherals, pins, buses.
- Pin mapping source (cite board definition file).
- Power implications.

### Constraints
- RAM budget impact (estimate bytes).
- Flash budget impact (estimate bytes).
- Timing requirements (latency, frequency).
- Compatibility: which boards support this, which don't, and why.

### Implementation Order
Numbered steps, each assigned to a specialist agent:
1. (Agent) Task description
2. ...

### Test Strategy
- Host-side tests: what logic to test, what to mock.
- Compile checks: which boards.
- On-device tests: what to verify, expected serial output.

### Documentation Changes
- README updates needed.
- Wiring diagram changes.
- API documentation additions.

### Open Questions
List anything ambiguous that needs user input before proceeding.
