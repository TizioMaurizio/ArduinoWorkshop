# Inter-Agent Protocol v1.0

## Purpose

This protocol defines how any agent communicates with any other agent in the ArduinoWorkshop multi-agent system. All 22 agents are peers — no agent is isolated and no communication path is restricted.

## Scope

Applies to all agents defined in `.github/agents/*.agent.md`. The authoritative agent registry is maintained in `.github/copilot-instructions.md`.

---

## Request Schema

When calling another agent via `@agent-name`, structure the request with these fields.

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `caller_agent` | string | The agent making the request |
| `target_agent` | string | The agent being called |
| `task_summary` | string | One-paragraph description of what is needed |
| `system_context` | string | Relevant system state: files, recent findings, hardware setup |
| `constraints` | list | Hard constraints the response must respect |
| `expected_output` | string | What form the answer should take |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `request_id` | string | auto | Unique identifier: `<caller>-<target>-<YYYYMMDD>-<seq>` |
| `assumptions` | list | `[]` | Assumptions the caller is making (target should validate) |
| `artifacts` | list | `[]` | File paths or references relevant to the request |
| `uncertainty_level` | enum | `medium` | `low` / `medium` / `high` — caller's confidence in the framing |
| `urgency` | enum | `important` | `blocking` / `important` / `background` |
| `max_call_depth` | int | `3` | Maximum further delegation depth allowed |
| `dependency_chain` | list | `[caller]` | Agents already consulted in this request chain |

---

## Response Schema

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `findings` | string | What the agent found or concluded |
| `confidence` | enum | `certain` / `likely` / `speculative` |
| `facts` | list | Verified information from code, datasheets, measurements |
| `assumptions_made` | list | Things taken as true but not verified |
| `conclusions` | list | Inferences drawn from facts + assumptions |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `unresolved_uncertainties` | list | Questions that remain open |
| `risks` | list | Risks identified in the analysis |
| `recommended_actions` | list | Concrete next steps |
| `suggested_delegations` | list | Other agents that should be consulted next |
| `artifacts_produced` | list | Files created or modified |
| `simulation_required` | bool | Whether a mental experiment is needed before acting |

---

## Communication Rules

### 1. Peer-to-Peer Communication

Any agent can call any other agent directly with `@agent-name`. No routing through a central authority is required. The `@orchestrator` may be used when beneficial for complex multi-agent tasks but is not mandatory.

### 2. Recursive Delegation

Agents may delegate to other agents, who may delegate further. The `max_call_depth` field prevents unbounded chains.

| Depth | Meaning |
|-------|---------|
| 0 | No further delegation allowed — you must answer directly |
| 1 | You may call one more agent, who must answer directly |
| 2 | Two more levels of delegation possible |
| 3 (default) | Standard depth for most requests |

When delegating, decrement `max_call_depth` by 1 and append yourself to `dependency_chain`.

### 3. Loop Prevention

The `dependency_chain` tracks which agents have been consulted. **An agent MUST NOT call an agent already in the dependency chain for the same task.** If you need input from an agent already consulted, reference their previous findings from the context instead.

### 4. Context Passing

When delegating, pass the full `system_context` plus any new findings. Never strip context — downstream agents need the full picture to avoid re-discovering known information.

### 5. Content Separation

All agent outputs MUST clearly separate:

1. **Facts**: Verified information from code, datasheets, measurements, simulation results
2. **Assumptions**: Things taken as true but not independently verified
3. **Conclusions**: Inferences drawn from facts + assumptions
4. **Recommendations**: Proposed actions with stated confidence

### 6. Final Synthesis

The original caller (or `@orchestrator` if involved) is responsible for synthesizing responses from all consulted agents into a final answer for the user.

---

## Safety Escalation Protocol

If any agent detects a potentially unsafe condition:

1. **Flag immediately** with `[SAFETY]` prefix in the response
2. **Call `@mediation-gate`** for invariant validation before proceeding
3. **Call `@hardware-systems`** if the risk is electrical or physical
4. **Do NOT proceed** with the unsafe action — wait for clearance

Unsafe conditions include:
- Electrical hazard (overcurrent, overvoltage, short circuit risk)
- Data loss or corruption risk
- Physical safety (motor runaway, servo overtravel, thermal)
- Invariant violation (system enters undefined state)

---

## Example Exchange

```
@hardware-systems request:
  caller_agent: firmware-architect
  target_agent: hardware-systems
  task_summary: "Validate GPIO12 as SPI MISO on ESP32-CAM with current breadboard wiring"
  system_context: "ESP32-CAM project, GPIO12 is a strapping pin (MTDI, sets flash voltage)"
  constraints: ["Must not interfere with boot", "3.3V logic only"]
  assumptions: ["No external pull-up on GPIO12"]
  expected_output: "Safety assessment with go/no-go and alternative if unsafe"
  uncertainty_level: medium
  max_call_depth: 2
  dependency_chain: [firmware-architect]
```

```
@firmware-architect response:
  findings: "GPIO12 is unsafe for SPI MISO if any SPI device pulls it HIGH during boot..."
  confidence: certain
  facts: ["GPIO12 (MTDI) sets flash voltage: HIGH=1.8V, LOW=3.3V", "ESP32 datasheet §2.4"]
  assumptions_made: ["Module uses 3.3V flash (most common)"]
  conclusions: ["Using GPIO12 as SPI MISO will cause boot failure if MISO is HIGH at reset"]
  risks: ["Boot into wrong flash voltage → corrupt reads → crash loop"]
  recommended_actions: ["Use GPIO13 or GPIO14 instead", "If GPIO12 is required, add 10kΩ pull-down"]
  suggested_delegations: ["@esp-integrator for strapping pin configuration alternatives"]
```
