# Playbook: Network Latency Breaks Control Loop

## Scenario
The VR user moves their hand but the robot arm responds with visible delay (~500ms). The system worked at <100ms latency on the local network but degrades on the university WiFi.

## Agent Call Chain

```
[1] User → @systems-architect
    "Robot arm delay is ~500ms on university WiFi. Was fine at home."

[2] @systems-architect (triage and latency budget)
    ├── Maps the full loop: VR controller → WiFi → PC → UDP → ESP32 → PCA9685 → Servo
    ├── Latency budget: target <100ms total for agency-preserving teleoperation
    ├── Identifies segments to measure: VR→PC, PC→ESP32, ESP32→servo, total round-trip
    ├── Delegates to @network-specialist: "Measure and diagnose WiFi latency on university network"
    ├── Delegates to @robotics-controls: "Can control loop compensate for 500ms latency?"
    └── Delegates to @vr-specialist: "What's the agency impact of 500ms teleoperation delay?"

[3] @network-specialist
    ├── Diagnoses: university WiFi likely has high contention + client isolation
    ├── UDP packets may be deprioritized or even blocked on managed networks
    ├── Checks: is ESP32 in STA mode on university SSID? WPA2-Enterprise?
    ├── Test: measure RTT with UDP echo server on ESP32
    ├── Proposes: run ns-3 simulation with congestion model
    ├── Immediate fixes: ESP32 AP mode (direct connection), or USB serial fallback
    └── Returns: "University WiFi adds 200-400ms jitter. Use ESP32 AP mode or dedicated router."

[4] @robotics-controls
    ├── At 500ms latency: motion is not perceived as responsive, breaks agency
    ├── Compensation options:
    │   ├── Predictive: extrapolate intent from velocity (risky with jitter)
    │   ├── Speed limiting: cap motion speed to make delay less visible
    │   └── Visual feedback: show predicted position in VR while waiting for physical
    ├── Safety: 500ms old command may be invalid (user already moved elsewhere)
    ├── Recommends: command timeout + stale command rejection (>200ms = drop)
    └── Returns: "Add 200ms command freshness check. Stale commands → hold position."

[5] @vr-specialist
    ├── 500ms motion-to-visual delay: severe agency degradation
    ├── Users will feel the robot is "not theirs" — breaks proxy body ownership
    ├── Threshold: agency starts degrading at ~150ms, breaks at ~300ms
    ├── Mitigation: show predicted ghost arm in VR at user's actual hand position
    ├── Real arm lags behind ghost → visual gap reveals latency honestly
    └── Returns: "500ms breaks agency. Show predictive ghost overlay. Target <100ms for real fix."

[6] @systems-architect → @hardware-systems
    "Is a dedicated WiFi access point feasible? Power and placement constraints?"

[7] @hardware-systems
    ├── ESP32 in AP mode: no external hardware needed, range ~10m indoor
    ├── Dedicated micro-router (GL.iNet GL-MT300N): 5V USB powered, <$25
    ├── Power: both options work from USB 5V (check total USB current budget)
    └── Returns: "ESP32 AP mode for immediate fix. Dedicated router for production."

[8] @systems-architect synthesizes final latency budget:
```

## Final Output

### Root Cause
University WiFi introduces 200-400ms variable latency due to network contention and managed AP infrastructure. UDP may be deprioritized or buffered.

### Immediate Fix (minutes)
1. Switch ESP32 to AP mode: direct WiFi connection, expected latency <20ms
2. Connect PC to ESP32's AP SSID
3. Update Godot client's `esp_ip` to `192.168.4.1`

### Production Fix (hours)
1. Dedicated micro-router for the project's VLAN (isolated network)
2. Add command freshness check in ESP32 firmware (reject commands >200ms old)
3. Add predictive ghost overlay in VR (shows user's hand while real arm catches up)

### Simulation
- `test/simulations/network/university_wifi_latency.py` — ns-3 model of contention
- `test/simulations/robotics-controls/stale_command_rejection.py` — SimPy model of command freshness

### Agents Involved
| Agent | Contribution |
|-------|-------------|
| @systems-architect | Latency budget analysis, end-to-end loop mapping |
| @network-specialist | WiFi diagnosis, latency measurement, AP mode recommendation |
| @robotics-controls | Command freshness, safety analysis, stale command handling |
| @vr-specialist | Agency impact assessment, ghost overlay mitigation |
| @hardware-systems | AP mode feasibility, power budget |
