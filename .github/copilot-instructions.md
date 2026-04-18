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

## Mental Experiment Protocol

Every agent in this system is required to perform **executable mental experiments** (thought experiments backed by simulation tools) before proposing architectural changes, accepting designs, or dispatching implementation work. The goal is to transform every thought experiment into something **executable, reproducible, and auditable** — suitable for PhD-level research evidence.

### Why

This is a research system. Claims about system behavior — latency, safety, coherence, user experience — must be verifiable through simulation, not asserted by opinion. "It should work" is never an acceptable conclusion. Every hypothesis must be testable.

### How

Every mental experiment must follow this structure:

1. **Question**: State the hypothesis or invariant being tested (e.g., "Does the system remain safe under 200ms network jitter?").
2. **Model**: Specify what is being simulated and at what fidelity (discrete events, continuous physics, human behavior, network topology).
3. **Tool**: Name the specific simulation tool or framework used (SimPy, UPPAAL, PyBullet, ns-3, Monte Carlo in Python, pomdp_py, etc.).
4. **Execution**: The experiment must be runnable — a script, a config file, a notebook. Not a paragraph of prose.
5. **Output**: Quantitative results: state-space coverage, latency distributions, failure rates, Pareto fronts.
6. **Verdict**: Does the hypothesis hold? With what confidence? Under what assumptions?

### Where

Simulation artifacts live in:
```
test/simulations/<agent-domain>/
├── <experiment-name>.py           # executable simulation script
├── <experiment-name>.md           # experiment description, parameters, results
└── <experiment-name>_results/     # output data, plots, logs
```

### Shared Simulation Infrastructure

All agents can connect their simulations through:
- **Event Bus**: Kafka / Redis Streams for cross-agent event exchange during co-simulation
- **DES Core**: `SimPy` (Python) as the default discrete-event simulation engine
- **Digital Twin**: Godot / Unreal Engine 5 for visual and physical simulation
- **Log Replay**: Event-sourced logs for deterministic replay and regression testing
- **Formal Models**: UPPAAL (timed automata), Supremica/libFAUDES (supervisory control), PIPE/WoPeD (Petri nets)

Each agent's mental experiment section specifies the tools relevant to its domain.

## Test Mandate

**Every agent must write tests when the situation warrants it.** This is not optional — it is a professional obligation with no exceptions.

When to write tests:
- When implementing a new feature or fixing a bug.
- When a mental experiment reveals a failure mode that should be caught by CI.
- When modifying behavior that other subsystems depend on.
- When the change cannot be trivially verified by inspection alone.
- When a simulation discovers a boundary condition or edge case.

Test types by agent domain:
- **Firmware agents** (`firmware-architect`, `esp-integrator`, `driver-implementer`): host-side unit tests, compile checks, on-device smoke tests, RTOS/timing simulation tests.
- **Simulation agents** (`simulation-twin`, `systems-architect`): deterministic replay tests, state-space regression tests, co-simulation reproducibility tests.
- **VR/Godot agents** (`vr-specialist`, `godot-specialist`): scene validation, GDScript type checks, frame timing regression tests, automated viewport capture tests.
- **Perception agents** (`perception-cv`): pipeline tests with synthetic data, replay regression on known-difficult inputs, confidence calibration tests.
- **Network agents** (`network-specialist`): protocol conformance tests, latency simulation assertions, reconnect/backpressure tests.
- **Controls agents** (`robotics-controls`): safety envelope tests, stability boundary tests, motion profile regression tests.
- **Human factors agents** (`interaction-ux`, `narrative-translation`, `vr-specialist`): walkthrough scenario tests, translation fidelity tests, comfort metric regression tests.
- **Evaluation agents** (`evaluation-studies`): analysis pipeline validation with known-answer data, power analysis tests.
- **Documentation agents** (`docs-release`, `docs-research`): example compilation verification, link/reference checking, claim-to-evidence traceability.
- **Integration agents** (`integration-qa`, `test-harness`): end-to-end scenario tests, adversarial fuzzing, chaos injection tests.
- **Workflow agents** (`git-specialist`): build matrix dry-run, simulation config regression verification.

Tests are reported using the scientific protocol: Observation → Methodology → Result → Next Steps.

## Complete Agent Registry

All agents can call all other agents. No agent is isolated. Communication follows the protocol in `.github/agents/protocols/inter-agent-protocol.md`. Delegation rules are in `.github/agents/protocols/delegation-rules.md`.

### Embedded Firmware Team

| Agent | Domain |
|-------|--------|
| `firmware-architect` | Task decomposition, module boundaries, timing/memory constraints |
| `esp-integrator` | ESP32/ESP8266 platform, Wi-Fi, BLE, MQTT, OTA, NVS |
| `driver-implementer` | Sensors, displays, I2C/SPI/UART/OneWire drivers |
| `network-specialist` | HTTP, TCP/UDP, WebSocket, mDNS, TLS, streaming |
| `godot-specialist` | Godot 4.x, GDScript, XR/VR, MCU↔Godot bridge |
| `test-harness` | Unit tests, CI, mocks, regressions |
| `power-optimizer` | Sleep, wake, RAM/flash, boot time, duty cycling |
| `docs-release` | READMEs, changelogs, wiring docs, releases |
| `git-specialist` | Git workflow, reviews, commits, branches, merges |

### Embodied Interaction Team

| Agent | Domain |
|-------|--------|
| `systems-architect` | End-to-end architecture, latency budgets, module boundaries |
| `vr-specialist` | VR experience, camera rigs, comfort, embodiment |
| `simulation-twin` | Digital twin, physics fidelity, environment legibility |
| `perception-cv` | Sensing pipelines, tracking, detection stability |
| `robotics-controls` | Actuators, motion planning, safety, teleoperation |
| `interaction-ux` | Affordances, feedback design, social signal legibility |
| `narrative-translation` | Sensory translation, nonverbal meaning preservation |
| `evaluation-studies` | User studies, metrics, measurement methodology |
| `docs-research` | Research writing, dual-layer documentation |
| `integration-qa` | End-to-end testing, confusion paths, recovery paths |

### Cross-Cutting Infrastructure

| Agent | Domain |
|-------|--------|
| `hardware-systems` | Physical circuits, wiring, voltage/current safety, GPIO constraints, bus routing |
| `mediation-gate` | Invariant enforcement, action validation, safety gating, audit trail |
| `orchestrator` | Task routing, conflict resolution, multi-agent synthesis, termination guarantees |

## Inter-Agent Communication

All 22 agents communicate as peers using the protocol in `.github/agents/protocols/inter-agent-protocol.md`.

**Key rules:**
- Any agent can call any other agent directly using `@agent-name`.
- Recursive delegation is allowed with a default maximum depth of 3.
- Loop prevention: the `dependency_chain` tracks consulted agents; no agent may be re-called in the same chain.
- All outputs must separate **facts**, **assumptions**, **conclusions**, and **recommendations**.
- Safety-critical findings must be flagged with `[SAFETY]` and escalated to `@mediation-gate` before action.
- When the right agent is unclear, ask `@orchestrator` for routing.
- Collaboration playbooks in `.github/agents/playbooks/` show end-to-end multi-agent scenarios.

## Operating Principles

1. **No agent invents hardware facts** without stating them as assumptions. Pin capabilities, voltage levels, and current limits must be verified against datasheets or board definitions.
2. **Unsafe hardware suggestions must be flagged** with `[SAFETY]` prefix and escalated to `@hardware-systems` and `@mediation-gate`.
3. **Uncertainty must always be explicit.** Use confidence levels: certain / likely / speculative.
4. **Outputs must separate** facts (verified), assumptions (taken as true), conclusions (inferred), and recommendations (proposed actions).
5. **Prefer testable, bounded recommendations** over open-ended suggestions. If the recommendation can be simulated, simulate it.
6. **When confidence is low, suggest simulation or physical validation** before proceeding with implementation.
7. **Every claim about system behavior must be traceable** to evidence: code, measurement, datasheet, or simulation result.
8. **Physical safety is non-negotiable.** Overcurrent, overvoltage, and mechanical hazards are never acceptable trade-offs.

## Project Layout Convention

```
Projects/<Name>/             — standalone Arduino/PlatformIO projects
K5--37 sensor kit.../        — sensor kit example code
boards/                      — board pin maps and variant definitions
lib/                         — shared reusable driver libraries
include/                     — shared headers
test/                        — host-side and on-device tests
test/simulations/            — executable mental experiments (per-agent domain)
scripts/                     — build, flash, monitor, and CI utilities
docs/                        — wiring diagrams, READMEs, release notes
hardware/                    — circuit schematics, BOMs, wiring validation scripts
.github/agents/              — agent definitions (.agent.md)
.github/agents/protocols/    — inter-agent communication schemas
.github/agents/playbooks/    — multi-agent collaboration scenarios
.github/skills/              — reusable skill procedures
```

## Code Style

- Use `snake_case` for C functions and variables.
- Use `PascalCase` for C++ classes and Arduino sketch names.
- Use `UPPER_SNAKE_CASE` for constants and pin definitions.
- Prefer `constexpr` or `const` over `#define` where the toolchain supports it.
- Group includes: system → library → project-local.
- One logical change per commit. Commit messages follow [Conventional Commits v1.0.0](https://www.conventionalcommits.org/en/v1.0.0/): `<type>(<scope>): <description>` (e.g., `fix(wifi): resolve reconnect timeout`).
