# Delegation Rules

## Purpose

Prevent infinite loops, enforce termination, and ensure efficient multi-agent collaboration.

---

## Rules

### 1. Maximum Depth

Default `max_call_depth`: **3**. Each delegation decrements by 1. At depth 0, the agent must answer directly without further delegation.

### 2. No Cycles

The `dependency_chain` is append-only. If agent X is already in the chain, no agent downstream may call X again for the same task. Reference X's prior findings from context instead.

### 3. Explicit Justification

Every delegation must include a one-sentence reason: "I am calling @agent-name because [specific reason this agent's expertise is needed]."

### 4. Single Responsibility per Call

Each delegation should request ONE specific thing. Do not ask an agent to "review everything" — specify what aspect needs their expertise.

### 5. Response Obligation

A called agent MUST respond. Acceptable responses include:
- Full answer with findings
- Partial answer with explicit "I need more information: [specifics]"
- Referral: "This is outside my domain; suggest calling @other-agent because [reason]"

An agent may NOT silently ignore a request.

### 6. Context Integrity

When passing context downstream:
- Include all prior findings from the dependency chain
- Include relevant file paths and line numbers
- Include any safety flags from prior agents
- Do NOT summarize away details that downstream agents might need

### 7. Conflict Resolution

When two agents provide contradictory findings:
1. The original caller (or `@orchestrator`) identifies the contradiction
2. Both agents are asked to state their **facts** and **assumptions** separately
3. The contradiction is traced to a differing assumption or missing fact
4. The agent with the stronger evidence (datasheet > code > speculation) wins
5. If evidence is equal, `@mediation-gate` adjudicates based on safety

### 8. Termination Guarantee

A task terminates when:
- The original caller has received all needed responses
- OR `max_call_depth` reaches 0 with no further questions
- OR `@orchestrator` declares the task complete
- OR a `[SAFETY]` block halts the task pending review

### 9. Audit Trail

Every delegation chain produces an implicit log:
```
[1] @firmware-architect → @hardware-systems: "Validate GPIO12 safety"
[2] @hardware-systems → @esp-integrator: "Confirm strapping pin behavior"
[3] @esp-integrator responds: findings...
[2] @hardware-systems responds: findings...
[1] @firmware-architect synthesizes final answer
```

This chain must be reconstructable from the conversation history.

---

## Anti-Patterns

- **Shotgun delegation**: Calling 5 agents at once "just in case." Call the most relevant agent first; they'll suggest further delegations if needed.
- **Echo chamber**: Agent A calls B, B calls C, C rephrases A's question. Each call must add new expertise, not just relay.
- **Authority laundering**: "Agent X said it's fine" without verifying X's assumptions apply to your context. Always check assumptions.
- **Depth hoarding**: Setting `max_call_depth: 0` to prevent any delegation. Use depth limits to bound, not prevent, collaboration.
