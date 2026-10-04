# Talos

Autonomous co-evolution of fixed-wing UAV morphology and neural flight controllers in PyBullet.

---

## Overview

Most UAV neuroevolution experiments fix the aircraft geometry and train a neural network to fly it. Talos explores what happens when you evolve both together:

1. **Morphology genome**: Physical airframe parameters (wingspan, wing area, horizontal and vertical tail sizing, thrust-to-weight ratio, mass, and center-of-gravity offset) converted dynamically into URDF and configuration files.
2. **Controller genome**: A NEAT (`neat-python`) topological neural network that takes real-time flight telemetry (airspeed, pitch, climb rate, attitude errors, waypoint vectors) and outputs primary flight control commands (elevator, aileron, rudder, throttle).



---

## Core Findings

Across iterative experiments (PID baseline, pure neural evolution, body evolution with PID, and joint body-brain co-evolution), the main takeaway was clear:

- **Neural controllers on default airframes struggle with stability.** A 300-generation NEAT controller on the stock airframe achieved aggressive waypoint navigation (clearing 3/4 course gates) but crashed within seconds in turbulence due to control-induced oscillation.
- **Body evolution with PID produces brute-force sailplanes.** When optimizing morphology for a standard PID controller (P3B), evolution maxed out wingspan (3.0 m) and mass (4.2 kg), setting straight-line endurance records (1,018 m) but offering zero navigation agility.
- **Co-evolution discovers passive aerodynamic damping.** When the body evolved specifically for the neural pilot (P3C), it did not simply build larger wings. Instead, it grew oversized horizontal and vertical tail surfaces (+347% and +377% over default area) and shifted the center of gravity forward (+0.08 m). The airframe itself passively dampened high-frequency neural jitter, allowing the pilot to push 49.2 m/s through aggressive waypoint courses to set the all-time flight distance record of 1,229.4 m.

### Morphology Comparison

| Metric | Stock Airframe | P3A (Glider) | P3B (Heavy Cruise) | P3C (Co-Evolved) |
|---|---|---|---|---|
| Wingspan | 1.00 m | 3.00 m | 3.00 m | 1.80 m |
| Main Wing Area | 0.30 m² | 0.76 m² | 0.42 m² | 0.57 m² |
| Horizontal Tail | 0.05 m² | 0.07 m² | 0.09 m² | **0.22 m²** (4.4x) |
| Vertical Tail | 0.05 m² | 0.06 m² | 0.02 m² | **0.24 m²** (4.8x) |
| Mass | 1.20 kg | 2.94 kg | 4.22 kg | 3.41 kg |
| Thrust / Weight | 0.60 | 1.50 | 1.50 | 1.49 |
| CG Shift | 0.00 m | -0.03 m | -0.05 m | **+0.08 m (Forward)** |

---

## Project Structure

```
Talos/
├── configs/             # Experiment configs (baselines, NEAT, co-evolution)
│   ├── baselines/       # Standard PID benchmarks
│   ├── coevolution/     # Joint morphology + controller runs
│   ├── controller_only/ # Fixed-body NEAT evolution
│   └── morphology_only/ # Fixed-controller airframe evolution
├── src/
│   ├── simulation/      # PyFlyt environment wrappers & waypoint courses
│   ├── genome/          # URDF generation and NEAT network interfaces
│   ├── evolution/       # Evaluator pools, population routines, fitness metrics
│   ├── experiment/      # Telemetry logging and SQLite tracking
│   └── dashboard/       # Interactive Dash/Plotly visualization server
├── docs/                # Lab notebook, specs, literature review, diagrams
├── tests/               # Smoke tests and fitness tier validation
├── run.py               # Main CLI entry point
├── compare_latest.py    # Head-to-head evaluation script
└── requirements.txt     # Python dependencies
```

---

## Getting Started

### 1. Requirements

- Python 3.10+
- PyBullet / PyFlyt dependencies

```bash
git clone https://github.com/quadrosgeorge3-pixel/Talos.git
cd Talos
pip install -r requirements.txt
```

### 2. Verify Simulation Setup

Run the smoke test suite to verify physics environment initialization:

```bash
python verify_setup.py
```

### 3. Run Baselines

Evaluate PyFlyt's built-in PID controller on the default airframe across multiple seeds:

```bash
python run.py baseline
```

### 4. Run Evolution

Start or resume an evolutionary run using an experiment configuration:

```bash
python run.py evolve --config configs/coevolution/p3c_coevolution.json --generations 100
```

### 5. Inspect Results

Start the local web dashboard to inspect flight trajectories, morphology mutations, and fitness curves:

```bash
python run.py web --port 8050
```

Or compare historical benchmark champions directly:

```bash
python compare_latest.py
```

---

## License

This project is licensed under the Apache 2.0 License. See [LICENSE](LICENSE) for details.
