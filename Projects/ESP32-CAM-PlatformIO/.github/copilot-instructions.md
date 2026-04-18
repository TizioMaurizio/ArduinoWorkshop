# Embedded Firmware Rules — ArduinoWorkshop

## Scope

This repository contains Arduino and ESP-class microcontroller projects, sensor kit examples, and learning materials. All Copilot activity must respect the constraints of resource-limited embedded targets.

## Universal Rules

- Target: Arduino (AVR, SAMD) and ESP32/ESP8266 microcontrollers.
- Prefer deterministic, readable firmware over clever abstractions.
- Never invent pin maps, board capabilities, memory sizes, or peripherals. Use board definitions in `/boards` or project-local configs as the source of truth.
- Keep hardware-specific code isolated from portable logic.
- Avoid dynamic allocation in hot paths. Never allocate in ISRs.
- Keep ISRs minimal: set flags, enqueue, or capture timestamps only.
- Prefer non-blocking state machines over long `delay()` usage.
- Add or update tests for all bug fixes where practical.
- All changes must compile for the affected board targets before being considered complete.
- When modifying protocol or hardware behavior, update docs and examples.
- If requirements are ambiguous, propose assumptions explicitly in comments or PR notes—never silently guess.

## Communication Standard

When reporting findings, conclusions, or recommendations to the user, behave like a research scientist:
- State the **observation** (what you measured or found).
- State the **methodology** (how you arrived at the conclusion).
- State the **result** with confidence level (certain / likely / speculative).
- State **next steps** or open questions.
- Cite specific files, line numbers, datasheets, or error messages as evidence.

Do not hand-wave. Do not say "it should work." Show your work.

## Project Layout Convention

```
Projects/<Name>/          — standalone Arduino/PlatformIO projects
K5--37 sensor kit.../     — sensor kit example code
boards/                   — board pin maps and variant definitions
lib/                      — shared reusable driver libraries
include/                  — shared headers
test/                     — host-side and on-device tests
scripts/                  — build, flash, monitor, and CI utilities
docs/                     — wiring diagrams, READMEs, release notes
```

## Code Style

- Use `snake_case` for C functions and variables.
- Use `PascalCase` for C++ classes and Arduino sketch names.
- Use `UPPER_SNAKE_CASE` for constants and pin definitions.
- Prefer `constexpr` or `const` over `#define` where the toolchain supports it.
- Group includes: system → library → project-local.
- One logical change per commit. Commit messages follow [Conventional Commits v1.0.0](https://www.conventionalcommits.org/en/v1.0.0/): `<type>(<scope>): <description>` (e.g., `fix(wifi): resolve reconnect timeout`).
