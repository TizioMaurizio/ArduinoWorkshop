# Playbook: Digital Twin Diverges from Reality

## Scenario
The robot arm in Godot shows the arm at 90° but the physical arm is at 45°. The divergence appeared gradually over a testing session. No single command seems to have caused it.

## Agent Call Chain

```
[1] User → @simulation-twin
    "Godot twin shows 90° but physical arm is at 45°. Diverged slowly over time."

[2] @simulation-twin (primary diagnostic)
    ├── Hypothesis 1: cumulative drift from dropped/reordered commands
    ├── Hypothesis 2: servo reached physical limit but twin didn't enforce it
    ├── Hypothesis 3: feedback loop missing — twin doesn't read actual position
    ├── Checks: is the twin open-loop (command echo only) or closed-loop (reads actual)?
    ├── Delegates to @robotics-controls: "Does the servo report actual position back?"
    ├── Delegates to @network-specialist: "Are UDP commands being lost or reordered?"
    └── Delegates to @godot-specialist: "How does the twin update its angle state?"

[3] @robotics-controls
    ├── PCA9685 servos are open-loop: you send a PWM, there's no position feedback
    ├── If a servo stalls (physical obstruction), the twin won't know
    ├── Servo may have different actual range vs commanded range (calibration)
    ├── Some servos have signal feedback wire but PCA9685 doesn't read it
    └── Returns: "No position feedback exists. Twin is purely command-echo. Drift is guaranteed."

[4] @network-specialist
    ├── UDP is unreliable: packets can be lost, especially at high command rates
    ├── If twin duplicates a packet the servo didn't receive, they diverge by 1 step
    ├── Over 1000 commands, even 1% loss = 10° cumulative drift
    ├── Test: add sequence numbers to commands, log gaps
    └── Returns: "UDP loss causes cumulative drift. Add sequence numbers and gap detection."

[5] @godot-specialist
    ├── Checks: twin updates on sending command (optimistic) vs on receiving ACK
    ├── If optimistic: twin is always ahead of reality by network latency
    ├── Over time: any dropped command → permanent divergence
    ├── Fix: twin should track COMMANDED state and CONFIRMED state separately
    └── Returns: "Twin uses optimistic update. Add command tracking with ACK reconciliation."

[6] @simulation-twin → @systems-architect
    "How should we architect closed-loop twin synchronization?"

[7] @systems-architect
    ├── Design: command → ESP32 → ACK with sequence number → twin reconciles
    ├── For servos without feedback: ACK means "command received" not "position reached"
    ├── For true closed-loop: add servo feedback (analog read on servo signal wire)
    ├── Proposes three tiers:
    │   ├── Tier 1: ACK-based reconciliation (no hardware change)
    │   ├── Tier 2: periodic calibration command (servo sweeps to known position)
    │   └── Tier 3: position feedback via ADC (hardware change, most accurate)
    └── Returns: "Implement Tier 1 immediately (ACK), plan Tier 3 for production."

[8] @simulation-twin → @mediation-gate
    "Validate that command reconciliation doesn't violate latency budget."

[9] @mediation-gate
    ├── ACK adds one UDP packet per command: ~1ms additional latency
    ├── Invariant: total latency < 100ms for agency
    ├── Current budget: ~50ms used → 50ms headroom → 1ms ACK is fine
    ├── Verdict: APPROVED
    └── Condition: "ACK must be non-blocking. Twin shows commanded position immediately, reconciles on ACK."

[10] @simulation-twin synthesizes
```

## Final Output

### Root Cause
Cumulative drift from UDP packet loss + open-loop servo control + optimistic twin update. Over time, each lost command adds permanent angular error.

### Fix (Tier 1 — Software Only)
1. Add sequence numbers to all servo commands: `seq,ch,angle\n`
2. ESP32 responds with ACK: `ACK,seq\n`
3. Godot twin tracks two states:
   - `commanded_angle`: updates immediately on send (for responsive UX)
   - `confirmed_angle`: updates only on ACK receipt
4. If ACK not received within 200ms: resend command
5. If gap in sequence numbers detected: resync all channels
6. Log all gaps to `test/simulations/digital-twin/sync_gaps.csv`

### Fix (Tier 3 — Hardware, Future)
1. Use servo feedback wire (center pin on 3-wire servo connector)
2. Read actual position via ESP32 ADC (dedicate analog pins per servo)
3. Send actual positions back to Godot for true closed-loop twin

### Simulation
- `test/simulations/digital-twin/drift_simulation.py` — SimPy model of UDP loss → cumulative drift
- `test/simulations/digital-twin/ack_reconciliation.py` — SimPy model of Tier 1 fix effectiveness

### Agents Involved
| Agent | Contribution |
|-------|-------------|
| @simulation-twin | Divergence diagnosis, synchronization architecture |
| @robotics-controls | Open-loop servo analysis, feedback options |
| @network-specialist | UDP loss quantification, sequence number proposal |
| @godot-specialist | Twin update logic analysis, reconciliation design |
| @systems-architect | Tier 1/2/3 architecture, closed-loop design |
| @mediation-gate | Latency budget validation for ACK overhead |
