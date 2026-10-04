# Body-Brain Co-Evolution in Fixed-Wing Aircraft
## Prior Art, Academic Foundations, and Experimental Hypotheses
**Project:** Icarus / Talos  
**Status:** Working Reference Document  

---

## 1. Executive Summary

This document compiles the academic literature, historical precedents, and theoretical failure modes relevant to the **Icarus** co-design pipeline. It outlines what previous researchers have discovered when simultaneously evolving physical morphology and neural control, and defines the exact inferences and behavioral milestones we will test as the experiment advances through its 6 phases.

---

## 2. Academic Lineage & Prior Art

### 2.1 Classical Body-Brain Co-Evolution (Evolutionary Robotics)
* **Foundations:** The field originates with Karl Sims (*Evolving Virtual Creatures*, 1994) and was extended significantly by Lipson & Pollack (2000), Bongard (2013), and Cheney et al. (2013, 2018).
* **Historical Focus:** The overwhelming majority of literature focuses on **terrestrial modular robots, soft voxel creatures, and multi-legged animats**. In these systems, locomotion is governed by ground friction, contact collision dynamics, and periodic actuator cycles (oscillators/CPGs).
* **Key Finding:** The morphology and controller co-adapt in a fragile dance. When the body plan shifts, the existing controller policy is often rendered completely obsolete.

### 2.2 Aerospace Co-Design (Concurrent Engineering)
* **Traditional Approach:** Aerospace researchers frequently conduct concurrent aerostructural and control optimization (MDO — Multidisciplinary Design Optimization).
* **The Classical Constraint:** In aerospace literature (AIAA, NASA, TU Delft), morphology optimization (aspect ratio, wing sweep, camber, tail volume) is virtually always paired with **classical linear control laws** (e.g., gain-scheduled PID, LQR, or H-infinity controllers).
* **The Gap:** True **topological neuroevolution** (evolving neural network wiring, activation topologies, and weights from scratch) paired with parametric continuous 3D airframe geometry in a 6-DOF rigid-body physics engine is rarely explored in aerospace due to the unpredictability of unconstrained neural controllers.

### 2.3 Neuroevolution (NEAT) in Flight Control
* **Autonomous Soaring & UAV Flight:** Studies in MDPI, IEEE, and AIAA have applied NEAT (Stanley & Miikkulainen, 2002) to unmanned aerial vehicles:
  * Autonomous soaring using thermal updrafts (exploiting meteorological gradients).
  * Quadcopter high-agility maneuvers and attitude stabilization.
  * Glider flare-and-landing under actuator failures.
* **Key Advantage:** NEAT produces remarkably compact, interpretable networks that can run at high frequencies (120+ Hz) on embedded flight hardware without requiring large deep learning models.
* **The Limitation of Past Studies:** The airframe in these experiments is **100% static**. The neural network is forced to master a human-engineered, fixed vehicle.

### 2.4 Structural Parsimony & Grow-and-Prune (NeST / Lottery Tickets)
* **The NeST Paradigm:** Dai, Yin, and Jha (Princeton, 2017) demonstrated that neural architectures benefit from alternating growth and pruning phases.
* **Lottery Ticket Hypothesis:** Frankle & Carbin (2018) showed that dense networks contain sparse sub-networks ("winning tickets") that can match the performance of the full network when trained in isolation.
* **Application to Flight:** In reflex control, over-parameterization is only needed during initial exploratory learning. Once coordination pathways are established, low-magnitude synapses and uninformative sensor inputs can be aggressively ablated.

---

## 3. Core Theoretical Hypotheses & Expected Inferences

When co-evolution begins in earnest (Phase 4) followed by pruning (Phase 5), literature predicts several specific phenomena that we will monitor:

### Hypothesis 1: The Morphology-Controller Asymmetry (The "Freezing" Trap)
* **Theoretical Problem:** A mutation in neural weights causes a minor shift in control response. However, a mutation in aircraft morphology (e.g., moving the Center of Gravity aft by 5% MAC or reducing vertical fin area) can instantly shift an aircraft from dynamically stable to statically unstable (divergent pitch/yaw).
* **Expected Failure Mode:** Existing controllers cannot immediately fly a radically mutated body. As a result, the evolutionary search tends to suffer from **morphological freezing** — it converges on a conservative, "easy-to-fly" airframe (large wings, oversized tail, forward CG) and discards potentially superior high-efficiency morphologies because they crash on generation 1.
* **Mitigation to Test in Phase 4:** If freezing occurs, we must introduce **Morphological Innovation Protection** (giving new morphologies a grace period or multi-generation controller fine-tuning before tournament selection).

### Hypothesis 2: Morphological Computation ("Embodied Intelligence")
* **Theoretical Principle:** A well-designed airframe performs computation for free through physics. An aircraft with positive static margin and high dihedral automatically self-rights against roll/pitch perturbations.
* **Expected Inference:** As morphology evolves toward aerodynamically stable designs, the **controller complexity (number of nodes and connections) will decrease rather than increase**. The neural network only needs to provide light trim guidance rather than continuous high-gain damping.

### Hypothesis 3: Input Sparsity & Redundancy in Flight Sensors
* **Input Analysis:** The 15 flight inputs provided to NEAT are:
  `[p, q, r, roll, pitch, yaw, u, v, w, x, y, z, dx, dy, dz]`
* **Expected Inference:** When Phase 5 pruning is applied:
  * Primary drivers: Pitch rate (`q`), surge velocity (`u`), altitude error (`Δz`), and vertical speed (`w`) will retain strong synapse weights.
  * Redundant/Ablated: Yaw rate (`r`), lateral drift (`v`), and absolute ground positions (`x, y`) will show minimal or zero connection density for simple level cruising.

### Hypothesis 4: Simulation Deception (Superficial Survival Exploits)
* **The Simulation Artifact:** In early generations, evolutionary algorithms routinely discover physics exploits. Common examples in flight simulators:
  * High-alpha deep stall glides (surviving 10 seconds without crashing by floating slowly, without ever achieving controlled cruising).
  * High-speed downward diving that reaches distance before ground impact.
* **Empirical Validation:** This directly validates why our multi-objective fitness function shifts at Generation 35+ to heavily penalize altitude error (`exp(-0.8 · |Δz|)`), forcing true level horizon tracking.

---

## 4. Phase-by-Phase Roadmap & Evaluation Protocol

| Phase | Description | Key Research Question to Answer |
|---|---|---|
| **Phase 1: Baseline** | PyFlyt Default PID on Default Airframe | *What is the baseline performance to beat?* (Recorded: 3.94s survival, 98.2m dist, 1.71 energy). |
| **Phase 2: Controller Evolution** | NEAT on Default Airframe (300 gens) | *Can topological evolution discover a reflex controller that matches or exceeds the PID benchmark on a fixed body?* |
| **Phase 3: Morphology Parametrics** | Parameter Sensitivity Search | *How sensitive is flight stability to independent variations in wingspan, tail volume, and CG placement?* |
| **Phase 4: Co-Evolution** | Morphology + Controller Dual Genome | *Does co-evolution produce non-intuitive airframe shapes, or does morphology freeze?* |
| **Phase 5: Grow-and-Prune** | NeST Sparsification Pass | *What is the minimum number of neurons and synapses required to maintain flight stability?* |
| **Phase 6: Analysis & Demo** | Generational Time-Lapse & Flight Replay | *Synthesis and public demonstration artifact.* |

---

## 5. Empirical Findings from Phase 2 (Controller Evolution)

### 5.1 The Lift vs. Speed Dilemma (Aerodynamic Trim Dynamics)
* **Observed Phenomenon:** Mid-to-late generation champions (Gen 120–190+) consistently initialize flight, climb smoothly from release altitude up to ~15m, and establish a level, high-speed cruise equilibrium at that altitude for the remainder of the episode.
* **Aerodynamic Mechanism:** The PyFlyt default airframe features positive wing camber and positive wing incidence relative to the fuselage waterline. At cruise airspeeds (V > 20 m/s), the wings generate dynamic lift in excess of total vehicle weight (Lift > Weight).
* **The Negative Pitch Trim Hazard:** To force the aircraft down to exactly 10.0m at full throttle, a flight controller must continuously hold negative elevator deflection (nose-down pitch trim). However, holding negative pitch trim at high speed is aerodynamically precarious: during mutation cycles, slight synaptic perturbations on an active nose-down command cause steep, unrecoverable dives into the terrain.
* **The Asymmetric Risk Attractor:** Because ground collision triggers an immediate catastrophic crash penalty (-100.0), the evolutionary landscape features an asymmetric risk gradient. Flying 5m higher than target altitude incurs a soft altitude penalty (0.50 · exp(-0.8 · 5) ≈ 0.01), but guarantees zero ground collision risk. Evolution consequently converges on an equilibrium altitude of ~15m, where aerodynamic lift balances gravity without risky downward trim.

### 5.2 Comparative Analysis: Bounded-Dome Survival vs. Open-Sky Flight

To ensure complete academic rigor, the comparison between the baseline PID controller and the evolved NEAT controller must be separated into its two distinct operational contexts:

#### Context A: Bounded Geofence Task (100-Meter Flight Dome)
*In this task, the environment penalizes leaving a 100m spherical arena (-100 penalty, instant termination). Both controllers are evaluated with geofence boundary awareness:*

| Metric | Reference PID ($B_0$, Dome-Aware) | Evolved NEAT (Gen 202 / 295) | Performance Verdict |
| :--- | :--- | :--- | :--- |
| **Survival / Air Time** | **10.00 ± 0.00 s** *(Full duration)* | **10.00 s** *(Full duration)* | **Tied** (Both achieve 100% survival) |
| **Accumulated Path Length**| 175.57 ± 0.00 m | **246.68 m** (up to 277.2m) | **NEAT sustains faster circling (+40%)** |
| **Maximum Distance from Origin**| 87.31 m *(Held inside dome)* | **60.2 m** *(Held inside dome)* | **NEAT discovers tighter 30m orbit** |
| **Flight Trajectory** | 40m-radius concentric orbit | 30m-radius banked loitering | Both master spatial containment |
| **Average Airspeed** | 17.56 m/s | 24.67 m/s | PID throttles down; NEAT banks at speed |
| **Crash & Stall Rates** | 0.0% | 0.0% | Both 100% crash/stall-free |

---

### 5.3 Provenance and Scientific Interpretation

#### 1. Provenance of the PID Controller:
* PyFlyt's core fixed-wing implementation does **not** provide a built-in autonomous waypoint autopilot (it only provides manual surface modes and an attitude-rate assist mode).
* The cascaded PID controller in `src/simulation/pid_controller.py` was specifically engineered for this project.
* When evaluated in the 100m bounded dome, the PID is equipped with **Geofence Awareness**, executing a concentric circular orbit ($R = 40\text{ m}$) centered at $(0, 0)$. This provides an authentic, fair human-engineered baseline that achieves 10.0s full-duration flight and 175.57m path distance without boundary collision.

#### 2. What the Evolutionary Result Actually Demonstrates:
* The evolved neural network did **not** merely learn "how to fly." It discovered how to solve a **constrained-space loitering task**.
* Confronted with the -100 crash/boundary penalty, NEAT discovered that flying straight meant elimination, while executing coordinated banked turns permitted continuous high-speed flight (24.7 m/s) within a 60m radius of the spawn point.
* The evolved brain achieved 6-DOF reflex stabilization, dynamic stall avoidance, and turn coordination using only 6 output nodes and 90 synapses without human flight equations.

#### 3. Implications for Phase 3 (Morphology) & Phase 4 (Co-Evolution):
* This does **not** invalidate the co-evolution pipeline; rather, it provides a crucial experimental safeguard:
  - When evaluating **pure aerodynamic morphology metrics** (e.g., L/D ratio, glide efficiency, wing loading in Phase 4), simulations should run in an **unconstrained / wide flight arena** so that physical aerodynamics, not artificial boundary geofencing, dictates the flight ceiling.
  - When evaluating **maneuverability and agile reflex control**, the bounded dome can be retained as an explicit turning-radius benchmark.

---

## 6. Standardized Experimental Taxonomy & Roadmap

To maintain clean scientific attribution across the project, experiments in Talos are formally organized into two distinct benchmark families:

### 6.1 Benchmark Families

#### Family A — Control Learning in Bounded Arenas
* **Operational Environment:** Bounded Flight Dome (100 m radius, -100 boundary penalty).
* **Research Question:** Can topological neuroevolution discover spatial containment, energy-efficient loitering, and stable 6-DOF reflex flight under strict environmental boundaries?
* **Core Metrics:** Arena survival time, boundary breach rate, path length accumulated inside geofence, orbit radius, synaptic complexity.

#### Family B — Aircraft Aerodynamic Performance & Co-Evolution
* **Operational Environment:** Effectively Unbounded / Open Airspace (1,000 m+ radius).
* **Research Question:** Does morphological evolution and body-brain co-evolution discover aircraft geometries with superior aerodynamic efficiency (L/D, glide endurance, minimum drag) compared to human-engineered baselines?
* **Core Metrics:** Downrange distance, open-sky endurance, control energy, lift-to-drag ratio (L/D), trim altitude adherence, airspeed stability.

### 6.2 Experiment Registry

| Experiment ID | Family | Airframe | Controller | Arena | Target Objective / Key Finding |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **TALOS-B01** | B (Open-Sky) | Fixed (PyFlyt Default) | Cascaded PID | 500 m | **Open-Sky PID Baseline:** 268.47 m dist, 10.0 s survival, 11.9 m alt, 3.29 energy. |
| **TALOS-E01** | A (Bounded) | Fixed (PyFlyt Default) | NEAT (300 gens) | 100 m | **Bounded Controller Evolution:** 246.68 m path length, 10.0 s survival within 60 m orbit. |
| **TALOS-E02** | B (Open-Sky) | Fixed (PyFlyt Default) | NEAT (Open Sky) | 1,000 m | **Open-Sky NEAT Flight:** Evaluates unconstrained cross-country cruise of evolved network. |
| **TALOS-M01** | B (Open-Sky) | Parametric (7-DOF) | Benchmark PID | 1,000 m | **Morphology Sensitivity:** Independent sweeps of wingspan, tail volume, and CG offset. |
| **TALOS-C01** | B (Open-Sky) | Parametric (7-DOF) | Co-Evolved NEAT | 1,000 m | **Body-Brain Co-Evolution:** Simultaneous co-adaptation of aircraft shape and neural wiring. |

### 6.3 The Core Phase 4 Co-Evolution Hypothesis
With **TALOS-B01 (PID Open Sky: 268.47 m)** and **TALOS-E01 (NEAT Open Sky: 246.70 m)** established as rigorous baselines:

> **Primary Experimental Question:**  
> When aircraft morphology (wingspan, wing area, tail volume, dihedral, CG location) and neural reflex control are permitted to co-adapt simultaneously in unconstrained airspace (**TALOS-C01**), does the co-evolved body-brain system outperform both the human-engineered baseline (268.5 m) and the fixed-airframe neural controller (246.7 m)?

---

## 7. Post-Evolution Generalization Battery & TALOS-P2B Protocol

### 7.1 Preservation Policy for Current Gen 300 Champion
The champion brain produced by the current 300-generation run (**TALOS-P2A**) is a **frozen, permanent scientific artifact**. It will **not** be retrained, fine-tuned, or modified. It represents the authentic answer to:
> *"What 6-DOF reflex policy does topological neuroevolution discover when flight endurance and distance are rewarded inside a strictly bounded 100m arena?"*

### 7.2 Zero-Shot Generalization Test Battery (Side-by-Side: PID vs. Frozen NEAT)
Immediately upon completion of Generation 300, **both controllers** — the human-engineered reference PID (`TALOS-B01`) and the frozen NEAT champion (`TALOS-P2A`) — will be evaluated across three standardized flight challenges under identical physics seeds.

All parameters (survival, distance, airspeed, altitude tracking, lateral deviation, control effort, waypoints reached) will be permanently logged to the `benchmark_evaluations` table in `output/icarus.db` as the final ground-truth comparative baseline.

#### Test A — Open-Sky Straight Flight (1,000m Arena)
* **Conditions:** 1 km arena, no geofence boundary pressure, 20.0s flight window.
* **Measured Metrics:** Total downrange distance, lateral deviation from waterline, altitude stability, cruise airspeed, survival duration, RMS control effort.
* **Objective:** Quantify the persistent "cage reflex" (tendency to bank and loop) versus raw open-air cruise capability.

#### Test B — Open-Sky Waypoint Course
* **Course Geometry:**
  - `START` $\rightarrow$ `WP1`: 150 m straight leg
  - `WP1` $\rightarrow$ `WP2`: 100 m diagonal offset (30° right)
  - `WP2` $\rightarrow$ `WP3`: 120 m diagonal return (45° left)
  - `WP3` $\rightarrow$ `FINISH`
* **Objective:** Test how the emergent waypoint sensitivity (`dx, dy, dz` synapses) handles structured navigation when waypoints extend beyond the 100m training horizon.

#### Test C — Aggressive Aero Slalom Course
* **Course Geometry:** Alternating high-deflection left/right waypoints, dynamic altitude step commands (10m $\rightarrow$ 25m $\rightarrow$ 5m), and heading reversals.
* **Objective:** Test whether the brain's specialized high-speed banking maneuvers give it superior agility over human PID on rapid turning tasks.

---

### 7.3 Comparative Evolution: TALOS-P2B (Open-Sky Controller Evolution)
To isolate environmental conditioning from evolutionary learning, a parallel evolutionary run (**TALOS-P2B**) will be executed under identical parameters:
* **Airframe:** Default PyFlyt fixed-wing (identical).
* **Sensors & Actuators:** 15 inputs, 6 outputs (identical).
* **Population & NEAT Config:** 50 genomes, 300 generations, same mutation rates (identical).
* **Independent Variable:** `flight_dome_size = 1000.0 m` (Unconstrained open sky).

#### Head-to-Head Comparative Study
Once TALOS-P2B completes, both specialized brains:
* **TALOS-P2A ("Caged Specialist"):** Optimized for spatial confinement, tight banked loitering, and boundary evasion.
* **TALOS-P2B ("Open Specialist"):** Optimized for long-range cross-country flight and low-drag cruising.

will be deployed on the **exact same tricky waypoint course**. This will empirically prove how the distribution of training environments dictates emergent flight phenotypes in neuroevolution.

---

## 8. Empirical Findings & The Sequential Behavioral Strategy Hypothesis

### 8.1 The Sequential Behavioral Strategy Hypothesis
> **Core Inference:**  
> As the fitness landscape changes (via environmental constraints or curriculum phase shifts), neuroevolution (NEAT) does **not** monotonically improve a single generalized flight policy. Instead, it sequentially discovers and transitions between distinct, specialized behavioral attractors.

### 8.2 Empirical Evidence from Project Talos

This phenomenon was empirically demonstrated across Phases 2A and 2B:

1. **Behavioral Mode 1: The Bounded Loitering Specialist (TALOS-P2A / Gen 0–300):**
   * **Environmental Pressure:** 100m dome with a -100 crash/boundary penalty.
   * **Emergent Strategy:** Tight circular banked turns inside a 30m radius.
   * **Non-Monotonic Generalization:** When deployed in a 1,000m arena, this strategy persisted rather than generalizing into straight cruise. The brain had converged on a localized topological attractor tailored specifically to spatial confinement.

2. **Behavioral Mode 2: The Ballistic Dive & High-Speed Cruise (TALOS-P2B / Gen 0–34):**
   * **Environmental Pressure:** 1,000m dome with raw distance (30%), survival (40%), and efficiency (30%).
   * **Emergent Strategy:** Steep throttle application, pitch-down attitude, and extreme acceleration to 34.5–42.7 m/s (124–154 km/h), accumulating 813.1m of distance (surpassing the Reference PID).
   * **Trade-Off:** Massive lateral drift (258.9m) and altitude deviation (-16m to +30m).

3. **Behavioral Mode 3: The Pitch-Leveling Horizon Lock (TALOS-P2B / Gen 35–65+):**
   * **Curriculum Shift:** At Gen 35, an exponential altitude penalty was introduced, dedicating 50% of fitness to maintaining 10m altitude.
   * **Evolutionary Reorganization:** Instead of incrementally tweaking the high-speed dive, the population underwent a profound structural reorganization. Lateral drift plummeted from 258.9m to 13.9m, altitude error collapsed to near 10m, and airspeed temporarily decelerated to ~18 m/s as the brain learned to pull pitch up.

### 8.3 Implications for Phase 4 Co-Evolution
This inference demonstrates that multi-objective evolutionary robotics proceeds via **punctuated equilibria and modular behavioral phase transitions**. In Phase 4 (body-brain co-evolution), we must expect physical morphology changes to trigger sudden leaps between distinct aerodynamic flight modes rather than smooth gradient descent.

---

*Document updated with formal Sequential Behavioral Strategy Hypothesis and Phase 2 empirical evidence.*

