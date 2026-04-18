# Playbook: Perception Uncertainty Leads to Wrong Decision

## Scenario
The ESP32-CAM detects a person (via object detection in the Godot client), but intermittent false positives cause the robot arm to wave at empty space. The user wants reliable person detection.

## Agent Call Chain

```
[1] User → @perception-cv
    "Person detection is triggering on empty frames. Robot waves at nothing."

[2] @perception-cv (primary diagnostic)
    ├── Checks: detection confidence threshold (too low → false positives)
    ├── Checks: frame quality (underexposed, motion blur, JPEG artifacts)
    ├── Checks: temporal consistency (single-frame detection vs sustained tracking)
    ├── Mental experiment: Monte Carlo simulation of false positive rate vs threshold
    ├── Recommends: raise confidence threshold from 0.3 to 0.6, add 3-frame persistence
    ├── Delegates to @network-specialist: "Is MJPEG stream dropping frames or delivering corrupt JPEGs?"
    └── Delegates to @robotics-controls: "Can the wave command be gated on sustained detection?"

[3] @network-specialist
    ├── Checks: MJPEG stream quality — are partial frames being delivered?
    ├── Checks: TCP backpressure — is the client reading slower than ESP32 sends?
    ├── Checks: frame rate — if stream stutters, same frame gets re-detected
    └── Returns: "Stream delivers ~10 fps with occasional partial frames. Add SOI/EOI validation in consumer."

[4] @robotics-controls
    ├── Confirms: wave command should require sustained detection (≥500ms, ≥3 frames)
    ├── Checks: current implementation — is there any debounce or persistence filter?
    ├── Recommends: state machine: IDLE → DETECTING → CONFIRMED → WAVING
    ├── With timeouts: DETECTING→IDLE after 500ms without detection
    └── Returns: "Add detection state machine with 500ms confirmation window."

[5] @perception-cv → @simulation-twin
    "Can we replay recorded frames through the detector to calibrate the threshold?"

[6] @simulation-twin
    ├── Proposes: record 60 seconds of stream, label frames (person/no-person)
    ├── Replay through detector at different thresholds
    ├── Compute ROC curve: false positive rate vs true positive rate
    └── Returns: "Create replay pipeline in test/simulations/perception-cv/"

[7] @perception-cv → @mediation-gate
    "Validate that raising threshold to 0.6 doesn't miss real detections."

[8] @mediation-gate
    ├── Invariant: "Robot must respond to person within 2 seconds"
    ├── Checks: at threshold 0.6, what is the detection latency?
    ├── With 3-frame persistence at 10fps: 300ms confirmation + network latency ≈ 500ms total
    ├── Verdict: APPROVED (500ms < 2s invariant)
    └── Condition: "Monitor false negative rate. If >10% of real people are missed, revisit."

[9] @perception-cv synthesizes
```

## Final Output

### Root Cause
False positive detections from low confidence threshold (0.3) combined with no temporal persistence filter. Corrupt MJPEG frames produce detection artifacts.

### Fix
1. Raise detection confidence threshold: 0.3 → 0.6
2. Add SOI/EOI JPEG validation before detection (skip corrupt frames)
3. Add detection state machine: require 3 consecutive detections within 500ms
4. Create replay test pipeline for threshold calibration

### Simulation Artifacts
- `test/simulations/perception-cv/threshold_calibration.py` — ROC curve generator
- `test/simulations/perception-cv/false_positive_monte_carlo.py` — FP rate estimator

### Agents Involved
| Agent | Contribution |
|-------|-------------|
| @perception-cv | Detection analysis, threshold recommendation, pipeline design |
| @network-specialist | Stream quality diagnosis, frame corruption |
| @robotics-controls | Detection state machine design |
| @simulation-twin | Replay pipeline proposal |
| @mediation-gate | Safety validation of new threshold |
