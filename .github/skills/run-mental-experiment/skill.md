---
name: run-mental-experiment
description: Execute an agent mental experiment — formalize a thought experiment as a runnable simulation, produce auditable results, and create regression tests from findings.
---

# Run Mental Experiment

## When to Use
When any agent needs to validate a hypothesis, test an invariant, or explore a failure mode before committing to a design decision or implementation. This is the universal skill for converting thought experiments into executable, reproducible evidence.

## Inputs Required
- **Agent domain**: Which agent is running the experiment (determines tool selection).
- **Hypothesis**: The specific question being tested (e.g., "Does the control loop remain stable under 150ms input jitter?").
- **Scope**: What is being simulated (one subsystem, two interacting subsystems, full system).
- **Fidelity level**: How detailed the simulation needs to be (event-level DES, physics co-sim, formal verification).

## Steps

### 1. Formalize the Question
- State the hypothesis as a falsifiable claim.
- Define the variables: what is being varied (independent), what is being measured (dependent), what is held constant (controlled).
- Define the acceptance criterion: what result would confirm or reject the hypothesis?

### 2. Select the Simulation Tool

Choose based on the agent domain and fidelity needed:

| Domain | Tool | Fidelity | When to use |
|--------|------|----------|-------------|
| Timing / RTOS | `UPPAAL` | Formal | Deadline verification, priority inversion |
| State machines | `Supremica`, `libFAUDES` | Formal | Supervisory control, reachability |
| Concurrency | `PIPE`, `WoPeD` | Formal | Deadlock detection, Petri net analysis |
| Event flows | `SimPy` | DES | Event-driven state machines, queuing, timing |
| Physics / robotics | `PyBullet`, `MuJoCo` | Co-sim | Joint dynamics, stability, collision |
| Full robot | `ROS2 + Gazebo` | Co-sim | Multi-sensor, multi-actuator scenarios |
| Network | `ns-3`, `OMNeT++` | DES | Topology, congestion, loss modeling |
| Perception | `pomdp_py`, Monte Carlo | Probabilistic | Belief updates, noise propagation |
| Energy | `SimPy` + cost model | DES | Duty cycling, sensing policies |
| Human behavior | User sim agent, LLM sandbox | Behavioral | Decision latency, error patterns |
| VR experience | Godot XR headless | Engine | Frame timing, visual regression |
| Integration | `SimPy` multi-agent, `Ray` | Co-sim | Emergent behavior, hidden coupling |
| Statistical | Python + pandas + MC | Analytical | Power analysis, metric validation |

### 3. Build the Simulation

Create in `test/simulations/<agent-domain>/<experiment-name>/`:

```
<experiment-name>/
├── README.md              # hypothesis, parameters, methodology, results
├── sim_<name>.py          # executable simulation script
├── config.json            # simulation parameters (separable from code)
├── requirements.txt       # Python dependencies (if any)
└── results/               # output directory for data, plots, logs
    ├── <name>_results.csv
    └── <name>_plot.png
```

Requirements for the simulation script:
- Must be runnable with a single command: `python sim_<name>.py`
- Must read parameters from `config.json` (not hardcoded)
- Must produce deterministic output given the same config and random seed
- Must write results to `results/` directory
- Must print a summary verdict to stdout

### 4. Execute and Record

- Run the simulation with the specified parameters.
- Record: runtime, memory usage, random seed, tool version.
- Save all outputs (data files, plots, logs) in the `results/` directory.
- Document any deviations from the plan.

### 5. Analyze Results

Apply the scientific reporting protocol:

**Observation**: What the simulation produced (raw data summary, key metrics).
**Methodology**: What was simulated, at what fidelity, with what parameters.
**Result**: Does the hypothesis hold? Confidence level: certain / likely / speculative.
           Include effect sizes, distributions, and boundary conditions — not just pass/fail.
**Next Steps**: What should change based on these findings? What follow-up experiments are needed?

### 6. Create Regression Tests

**This step is mandatory when the experiment reveals a failure mode or boundary condition.**

For each discovered issue:
1. Identify the minimal reproduction case from the simulation.
2. Create a test in the appropriate test directory:
   - Host-side unit test → `test/host/`
   - Simulation regression → `test/simulations/<domain>/`
   - On-device smoke test → `test/device/`
3. The test must:
   - Fail under the conditions that triggered the issue.
   - Pass when the issue is properly handled.
   - Be deterministic and CI-compatible (for host-side tests).
4. Document the link between the simulation finding and the test.

### 7. Update Experiment Log

Maintain `test/simulations/EXPERIMENT_LOG.md`:
```markdown
| Date | Agent | Experiment | Hypothesis | Verdict | Test Created | Link |
|------|-------|------------|------------|---------|-------------|------|
| YYYY-MM-DD | @agent-name | experiment-name | "..." | confirmed/rejected/inconclusive | yes/no | path |
```

## Acceptance Criteria
- Hypothesis is stated as a falsifiable claim.
- Simulation is executable with a single command.
- Parameters are externalized in config files.
- Results are deterministic given the same seed and config.
- Scientific report follows Observation → Methodology → Result → Next Steps.
- Failure modes discovered are converted to regression tests.
- Experiment is logged in `EXPERIMENT_LOG.md`.

## Anti-Patterns
- Do not write a "simulation" that is just a prose paragraph describing what might happen.
- Do not hardcode parameters — use config files so experiments can be re-run with variations.
- Do not discard simulation results — they are research data.
- Do not run an experiment and skip the test creation step when a failure is found.
- Do not claim "the simulation proves X" without stating assumptions and confidence level.
