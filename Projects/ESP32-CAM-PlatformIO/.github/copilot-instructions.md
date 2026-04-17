# ArduinoWorkshop — Copilot Team Rules

## Team Mission

Build a hybrid physical-virtual system where a human Controller interacts through VR with a physical or virtual avatar, using sensory translation to support nonverbal goal-oriented interaction with another human in a shared environment. The repository spans VR, simulation, robotics, perception, human-avatar interaction, and research materials.

**THE HUMAN EXPERIENCE IS A CORE ENGINEERING REQUIREMENT.**

Every agent, every change, every review must evaluate impact on: sense of agency, self-location, proxy body ownership, nonverbal intelligibility, social presence, user comfort, task understanding, recoverability from confusion, trust in the system, and consistency between physical and virtual behavior.

## Scope

This repository contains embedded firmware (Arduino, ESP32), Godot 4.x VR applications, digital twin simulations, perception pipelines, robot control systems, sensory translation logic, user evaluation instruments, and research materials. All Copilot activity must respect both the constraints of resource-limited embedded targets and the human-experience requirements of embodied teleoperation.

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

## Design Philosophy

- Embodied interaction over abstract UI
- Legibility over cleverness
- Stable feedback over flashy ambiguity
- Recoverability over brittle optimization
- Meaningful multimodal reinforcement over isolated cues
- Clear task affordances over hidden system logic
- End-to-end coherence over local module perfection
- Semantic fidelity in translation over raw data forwarding
- Measured human experience over assumed human experience

## Global Human-Experience Overlay

Every agent must answer these six questions for every proposal, implementation, review, or refactor:

1. **What will the user perceive?** — Describe the sensory consequence of this change.
2. **What will the user infer?** — What will they think is happening, and is that correct?
3. **What will the user try next?** — Does the system support their likely next action?
4. **What could confuse, fatigue, frustrate, or mislead them?** — Identify risks.
5. **How does this affect agency, orientation, comfort, and social understanding?** — Map to the core experience dimensions.
6. **How can we measure whether this improved or degraded the experience?** — Every change must be instrumentable.

No agent may declare work "done" unless the human impact has been explicitly considered and documented.

## Agent Catalog

### Embodied Interaction Team (new)
| Agent | Domain |
|-------|--------|
| **@systems-architect** | Architecture, latency budgets, module boundaries, end-to-end coherence |
| **@vr-specialist** | Camera rigs, movement, comfort, embodiment, onboarding, instrumentation |
| **@simulation-twin** | Digital twin, physics fidelity, environment legibility |
| **@perception-cv** | Sensing, tracking, detection stability, confidence signals |
| **@robotics-controls** | Actuators, motion planning, safety, readable robot behavior |
| **@interaction-ux** | Affordances, feedback, social signals, task legibility |
| **@narrative-translation** | Sensory translation rules, nonverbal meaning preservation |
| **@evaluation-studies** | User studies, metrics, measurement methodology |
| **@docs-research** | Documentation, research writing, technical + human explanations |
| **@integration-qa** | End-to-end testing, confusion paths, recovery, first-use |

### Embedded Firmware Team (retained)
| Agent | Domain |
|-------|--------|
| **@firmware-architect** | Firmware architecture, task decomposition, constraints |
| **@esp-integrator** | ESP32/ESP8266 platform, Wi-Fi, BLE, MQTT, OTA, NVS |
| **@driver-implementer** | Sensors, displays, I2C/SPI/UART, pin maps |
| **@test-harness** | Host-side unit tests, CI, compile checks |
| **@power-optimizer** | Sleep, wake, RAM/flash, power profiling |
| **@docs-release** | Firmware READMEs, changelogs, flash instructions |
| **@git-specialist** | Git workflow, review coordination, commit hygiene |

Cross-team rule: when a firmware change affects what the user perceives (stream format, latency, protocol), the embodied interaction team must be consulted.

## Review Checklists

### VR Changes
- [ ] Comfort impact assessed (safe / caution / risk)
- [ ] Motion sickness vectors checked (vection, acceleration, rotation mismatch)
- [ ] Agency preserved — user actions produce expected results within latency budget
- [ ] Orientation maintained — user knows where they are after the change
- [ ] First-use comprehension considered — new user can understand what changed
- [ ] Degraded-condition handling (tracking loss, stream stall, latency spike)
- [ ] No blocking calls in `_process()` or `_physics_process()`
- [ ] Frame budget met on target hardware
- [ ] Instrumentation for experience measurement in place

### Perception Changes
- [ ] Output temporal stability verified (no visible jitter in VR)
- [ ] Confidence signal exposed to downstream consumers
- [ ] Graceful degradation under occlusion, blur, low light
- [ ] Pipeline latency measured and within budget
- [ ] VR Specialist consulted for embodiment artifact risk
- [ ] False positive/negative consequences documented from user perspective

### Robot Control Changes
- [ ] Motion is smooth and bounded within joint/speed limits
- [ ] VR user can predict robot behavior from their input
- [ ] Bystander can read robot intent from its motion
- [ ] Communication loss → safe stop, visible to VR user
- [ ] Workspace limits communicated before the user hits them
- [ ] Watchdog / safety verified

### Simulation Changes
- [ ] Virtual environment matches physical setup spatially
- [ ] Object behavior matches user expectations
- [ ] No silent divergence between twin and physical world
- [ ] Scale is correct (1 unit = 1 meter)
- [ ] Performance within VR frame budget
- [ ] VR Specialist confirmed no orientation/comfort regression

### User Study Changes
- [ ] Metrics map to specific constructs (agency, comfort, presence, task understanding)
- [ ] Analysis plan specified before data collection
- [ ] Instrumentation requirements communicated to all subsystem agents
- [ ] Comfort checks included in study protocol
- [ ] Results report includes effect sizes, confidence intervals, limitations

## Merge / Release Criteria

A change may be merged when:
1. All relevant review checklists are satisfied.
2. The human-experience overlay questions have been answered.
3. The VR Specialist has been consulted for any change affecting agency, comfort, orientation, or embodiment.
4. The change compiles/runs for all affected targets.
5. Integration tests pass (unit + at least one end-to-end scenario).
6. Documentation has been updated to reflect both technical mechanism and human effect.
7. Commit messages follow Conventional Commits v1.0.0.

A release may be tagged when:
1. All merge criteria are met for all included changes.
2. At least one end-to-end user walkthrough has been completed.
3. Known issues are documented with user-facing impact description.
4. The evaluation agent has reviewed instrumentation coverage for study readiness.
