# Project Talos — Automated Research Lab Notebook
> **Last Auto-Generated:** 2026-09-19 13:44:13 UTC  
> **Active Database:** `output/icarus.db`  
> **Phase 2B (Open-Sky):** Gen 299 / 300 | **Phase 2A (Bounded):** Gen 300 / 300 (Complete)

---

## 1. Plain-English Experiment Glossary
To keep research clear and accessible, here is the simplified naming key used across the project:

| Plain-English Name | What It Actually Is | Arena | Duration |
| :--- | :--- | :--- | :--- |
| **`pid_bounded_100m`** | Reference PID Autopilot | 100m Flight Dome | ~3.94s (Boundary Halt) |
| **`pid_open_sky`** | Reference PID Autopilot | 500m Open Sky | 10.00s (Full duration) |
| **`phase2_neat_caged`** | Current Evolving Brain | 100m Flight Dome | 10.00s (Banked Loiterer) |
| **`phase2_neat_open`** | Upcoming Open-Sky Brain | 1,000m Open Sky | 10.00s (Cruising Specialist) |
| **`phase3_morphology`** | Airframe Shape Sensitivity | 1,000m Open Sky | Systematic geometry sweeps |
| **`phase4_coevolution`** | Body + Brain Co-Evolution | 1,000m Open Sky | Co-adapting plane & controller |

---

## 2. Permanent Baseline Records
Both baseline flight conditions are permanently recorded in the database:

| Baseline Condition | Flight Time | Distance | Airspeed | Altitude Hold | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`pid_bounded_100m`** | 10.00 s | 175.6 m | ~17.6 m/s | Altitude hold (±3.69m) | **Completed full 10.0s flight (Geofenced 40m orbit)** |
| **`pid_open_sky`** | 10.00 s | 268.5 m | ~26.8 m/s | Altitude hold (±1.95m) | **Completed full 10.0s flight** |

---

## 3. Phase 2 Controller Evolution Status (Dual-Track)
### Track 1: Bounded Cage (`phase2_neat_caged` / C1)
* **Status:** **Completed (300 / 300 Generations)**
* **All-Time Longest Stable Flight:** **317.9 meters** (Gen 216)
* **Champion Architecture:** 8 nodes, 57 connections (Loitering Reflex)

### Track 2: Open Sky (`phase2_neat_open` / TALOS-P2B)
* **Status:** **Active / In Progress (Generation 299 / 300)**
* **Current Best Distance:** **159.7 meters**
* **Current Best Fitness:** **0.6251**
* **Active Architecture:** 11 nodes, 9 connections
---

## 4. Key Discoveries to Date
### A. The 100-Meter Geofence Discovery
* The 3.94s flight time of the baseline PID was caused by PyFlyt's 100m spherical flight dome, not an aerodynamic stall or crash.
* When tested in open skies, the PID flies for 10.0s and covers 268.5 meters.
### B. Emergent Banked Loitering (The 'Caged Bird' Phenomenon)
* Because crossing the 100m perimeter carried a -100 death penalty, NEAT evolved coordinated banked turns to stay inside a 60m radius while clocking 246+ meters of flight distance.
* When tested in a 1 km open field, the brain flew for 19.03 seconds and 509 meters, proving genuine aerodynamic stabilization, while retaining its persistent circular looping reflex.
### C. The Lift vs. Speed Equilibrium
* At cruise speed (>20 m/s), the PyFlyt airframe generates lift exceeding vehicle weight.
* Evolution discovered a stable trim altitude at ~15m where lift equals weight without dangerous nose-down elevator deflection.
### D. The Bounded PID Score Deconstruction (Is 0.4733 Reliable?)
* **Mathematical Breakdown:** The PID's 0.4733 score came from tight altitude hold (0.218 out of 0.50) and low energy (0.147 out of 0.15) over 3.94s, despite earning low survival (0.079 out of 0.20) and low distance (0.030 out of 0.15).
* **The Geofence Grace:** The baseline evaluator only penalized ground crashes and stalls, granting the PID a 'graceful exit' at the 100m wall without the -100 death penalty applied to evolving genomes. If penalized like NEAT, its bounded score would be -99.5.
* **Open-Sky Truth:** In open skies, where PID actually flies 10s and 268.5m, its true unconstrained fitness is **0.530**.
### E. The Sequential Behavioral Strategy Hypothesis
* **Core Scientific Inference:** As the fitness landscape changes (via environmental boundaries or curriculum shifts), NEAT does not monotonically improve a single generalized flight policy. Instead, it sequentially discovers and transitions between distinct, specialized behavioral strategies.
* **Empirical Evidence:**
  * **Mode 1 (100m Dome):** Tight circular loitering (30m radius) to evade boundary death.
  * **Mode 2 (1000m Dome, Gen 0-34):** Ballistic dive and maximum acceleration (34-42 m/s, 813m distance) to exploit raw distance rewards.
  * **Mode 3 (1000m Dome, Gen 35+):** Reorganization into pitch-leveling horizon control (drift dropped from 258m to 13m) when 50% altitude priority was activated.

---

## 5. Dual-Track Architecture for Phases 2, 3, and 4
We have adopted a **Dual-Track Evolutionary Pipeline** to study Specialist vs. Generalist adaptation:

| Pipeline Track | Training Arena | Target Specialization | Expected Morphology in Phase 4 |
| :--- | :--- | :--- | :--- |
| **Track 1: Bounded (100m)** | 100m Dome (-100 boundary penalty) | **Agility & Loitering** (Spatial confinement) | Compact wingspan, high roll rate, oversized tail control |
| **Track 2: Open-Sky (1000m)**| 1000m Open Sky (Unconstrained) | **Aerodynamic Efficiency** (High-speed cruise) | High aspect ratio, low induced drag, slender glider body |

### Standardized Generalization Battery (Tests 1, 2, 3)
Every evolved controller and morphology from both tracks is evaluated against the same three zero-shot tests:
1. **Test A - Open-Sky Straight Flight (1 km):** Measures raw cross-country endurance and drift.
2. **Test B - Open-Sky Waypoint Course:** Measures structured waypoint navigation.
3. **Test C - Aggressive Aero Slalom:** Measures high-G bank angle agility and rapid altitude response.

---

## 6. Head-to-Head Generalization Benchmark Suite Results
Recorded in table `benchmark_evaluations` within `output/icarus.db`:

| Test Name | Controller | Precision Score | Flight Time | Distance | Airspeed | Altitude | Lateral Dev | Energy | Waypoints Hit | Arena Radius |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Test A - Open-Sky Straight Flight | **PID** | N/A | 20.00 s | 727.3 m | 36.4 m/s | 16.8 m | 322.9 m | 5.40 | **0 targets** | 1000 m |
| Test A - Open-Sky Straight Flight | **PID** | N/A | 20.00 s | 578.8 m | 28.9 m/s | 12.1 m | 284.1 m | 6.37 | **0 targets** | 1000 m |
| Test A - Open-Sky Straight Flight | **PID** | N/A | 20.00 s | 939.0 m | 47.0 m/s | 21.6 m | 377.1 m | 5.32 | **0 targets** | 1000 m |
| Test A - Open-Sky Straight Flight | **PID** | N/A | 20.00 s | 769.2 m | 38.5 m/s | 14.2 m | 329.3 m | 5.35 | **0 targets** | 1000 m |
| Test A - Open-Sky Straight Flight | **PID** | N/A | 20.00 s | 727.3 m | 36.4 m/s | 16.8 m | 322.9 m | 5.40 | **0 targets** | 1000 m |
| Test A - Open-Sky Straight Flight | **NEAT** | N/A | 20.00 s | 318.9 m | 15.9 m/s | 15.2 m | 218.0 m | 4.02 | **0 targets** | 1000 m |
| Test A - Open-Sky Straight Flight | **NEAT** | N/A | 20.00 s | 397.6 m | 19.9 m/s | 36.0 m | 205.5 m | 4.51 | **0 targets** | 1000 m |
| Test A - Open-Sky Straight Flight | **NEAT** | N/A | 2.03 s | 46.2 m | 22.7 m/s | 6.4 m | 12.9 m | 1.12 | **0 targets** | 1000 m |
| Test A - Open-Sky Straight Flight | **NEAT** | N/A | 2.27 s | 56.5 m | 24.9 m/s | 6.4 m | 10.5 m | 0.96 | **0 targets** | 1000 m |
| Test A - Open-Sky Straight Flight | **NEAT** | N/A | 2.53 s | 69.4 m | 27.4 m/s | 6.4 m | 36.1 m | 1.54 | **0 targets** | 1000 m |
| Test A - Open-Sky Straight Flight | **NEAT** | N/A | 20.00 s | 397.6 m | 19.9 m/s | 36.0 m | 205.5 m | 4.51 | **0 targets** | 1000 m |
| Test A - Open-Sky Straight Flight | **NEAT** | **70.0 / 100** | 20.00 s | 1094.1 m | 54.7 m/s | 211.5 m | 266.6 m | 19.50 | **3 targets** | 1000 m |
| Test A - Open-Sky Straight Flight (1 km) | **PID** | N/A | 20.00 s | 583.1 m | 29.2 m/s | 12.7 m | 285.1 m | 6.25 | **0 targets** | 1000 m |
| Test A - Open-Sky Straight Flight (1 km) | **NEAT** | N/A | 5.73 s | 152.3 m | 26.6 m/s | 25.9 m | 30.0 m | 5.73 | **0 targets** | 1000 m |
| Test B - Open-Sky Waypoint Course | **PID** | N/A | 25.00 s | 734.1 m | 29.4 m/s | 12.9 m | 132.6 m | 7.56 | **0 targets** | 1000 m |
| Test B - Open-Sky Waypoint Course | **PID** | N/A | 25.00 s | 935.0 m | 37.4 m/s | 17.7 m | 138.2 m | 6.65 | **0 targets** | 1000 m |
| Test B - Open-Sky Waypoint Course | **PID** | N/A | 25.00 s | 728.0 m | 29.1 m/s | 12.4 m | 54.1 m | 7.75 | **0 targets** | 1000 m |
| Test B - Open-Sky Waypoint Course | **PID** | N/A | 20.97 s | 1005.3 m | 47.9 m/s | 20.2 m | 88.6 m | 5.56 | **0 targets** | 1000 m |
| Test B - Open-Sky Waypoint Course | **PID** | N/A | 25.00 s | 990.8 m | 39.6 m/s | 15.2 m | 223.6 m | 6.60 | **0 targets** | 1000 m |
| Test B - Open-Sky Waypoint Course | **PID** | N/A | 25.00 s | 935.0 m | 37.4 m/s | 17.7 m | 138.2 m | 6.65 | **0 targets** | 1000 m |
| Test B - Open-Sky Waypoint Course | **NEAT** | N/A | 1.33 s | 27.2 m | 20.4 m/s | 5.7 m | 8.4 m | 0.03 | **0 targets** | 1000 m |
| Test B - Open-Sky Waypoint Course | **NEAT** | N/A | 25.00 s | 626.4 m | 25.1 m/s | 9.3 m | 119.1 m | 9.31 | **3 targets** | 1000 m |
| Test B - Open-Sky Waypoint Course | **NEAT** | N/A | 25.00 s | 852.2 m | 34.1 m/s | 25.9 m | 42.0 m | 12.30 | **0 targets** | 1000 m |
| Test B - Open-Sky Waypoint Course | **NEAT** | N/A | 2.07 s | 48.2 m | 23.3 m/s | 5.9 m | 3.2 m | 1.10 | **0 targets** | 1000 m |
| Test B - Open-Sky Waypoint Course | **NEAT** | N/A | 2.37 s | 62.8 m | 26.6 m/s | 5.4 m | 1.6 m | 1.03 | **0 targets** | 1000 m |
| Test B - Open-Sky Waypoint Course | **NEAT** | N/A | 25.00 s | 1229.4 m | 49.2 m/s | -5.6 m | 128.8 m | 16.30 | **3 targets** | 1000 m |
| Test B - Open-Sky Waypoint Course | **NEAT** | N/A | 25.00 s | 852.2 m | 34.1 m/s | 25.9 m | 42.0 m | 12.30 | **0 targets** | 1000 m |
| Test B - Open-Sky Waypoint Course | **NEAT** | **62.4 / 100** | 13.10 s | 785.4 m | 60.0 m/s | 15.3 m | 131.7 m | 12.79 | **4 targets** | 1000 m |
| Test C - Aggressive Aero Slalom | **PID** | N/A | 25.00 s | 733.8 m | 29.4 m/s | 12.7 m | 437.8 m | 7.51 | **0 targets** | 1000 m |
| Test C - Aggressive Aero Slalom | **PID** | N/A | 25.00 s | 937.9 m | 37.5 m/s | 16.5 m | 507.0 m | 6.65 | **0 targets** | 1000 m |
| Test C - Aggressive Aero Slalom | **PID** | N/A | 25.00 s | 727.0 m | 29.1 m/s | 12.3 m | 418.5 m | 7.72 | **0 targets** | 1000 m |
| Test C - Aggressive Aero Slalom | **PID** | N/A | 21.30 s | 1018.7 m | 47.8 m/s | 22.8 m | 494.4 m | 5.64 | **0 targets** | 1000 m |
| Test C - Aggressive Aero Slalom | **PID** | N/A | 25.00 s | 991.1 m | 39.6 m/s | 14.9 m | 574.9 m | 6.60 | **0 targets** | 1000 m |
| Test C - Aggressive Aero Slalom | **PID** | N/A | 25.00 s | 937.9 m | 37.5 m/s | 16.5 m | 507.0 m | 6.65 | **0 targets** | 1000 m |
| Test C - Aggressive Aero Slalom | **NEAT** | N/A | 1.13 s | 22.7 m | 20.0 m/s | 5.9 m | 0.5 m | 0.23 | **0 targets** | 1000 m |
| Test C - Aggressive Aero Slalom | **NEAT** | N/A | 1.60 s | 36.6 m | 22.9 m/s | 6.4 m | 14.0 m | 0.99 | **0 targets** | 1000 m |
| Test C - Aggressive Aero Slalom | **NEAT** | N/A | 1.53 s | 36.9 m | 24.1 m/s | 7.0 m | 8.0 m | 0.80 | **0 targets** | 1000 m |
| Test C - Aggressive Aero Slalom | **NEAT** | N/A | 1.53 s | 33.6 m | 21.9 m/s | 6.7 m | 5.5 m | 0.97 | **0 targets** | 1000 m |
| Test C - Aggressive Aero Slalom | **NEAT** | N/A | 1.50 s | 36.5 m | 24.4 m/s | 6.0 m | 6.5 m | 0.75 | **0 targets** | 1000 m |
| Test C - Aggressive Aero Slalom | **NEAT** | N/A | 1.67 s | 44.2 m | 26.5 m/s | 5.8 m | 13.2 m | 0.93 | **0 targets** | 1000 m |
| Test C - Aggressive Aero Slalom | **NEAT** | N/A | 1.53 s | 36.9 m | 24.1 m/s | 7.0 m | 8.0 m | 0.80 | **0 targets** | 1000 m |
| Test C - Aggressive Aero Slalom | **NEAT** | **50.0 / 100** | 13.00 s | 750.6 m | 57.7 m/s | 15.2 m | 94.5 m | 12.69 | **4 targets** | 1000 m |
| Test D - AUVSI SUAS Autonomous Challenge | **PID** | **48.5 / 100** | 30.00 s | 885.1 m | 29.5 m/s | 12.8 m | 627.8 m | 8.82 | **0 targets** | 1000 m |
| Test D - AUVSI SUAS Autonomous Challenge | **PID** | **49.0 / 100** | 27.40 s | 1035.4 m | 37.8 m/s | 17.4 m | 635.6 m | 7.25 | **0 targets** | 1000 m |
| Test D - AUVSI SUAS Autonomous Challenge | **PID** | **50.0 / 100** | 30.00 s | 636.9 m | 21.2 m/s | 10.8 m | 509.4 m | 26.43 | **0 targets** | 1000 m |
| Test D - AUVSI SUAS Autonomous Challenge | **PID** | **42.9 / 100** | 26.03 s | 1037.2 m | 39.8 m/s | 15.3 m | 676.4 m | 6.86 | **0 targets** | 1000 m |
| Test D - AUVSI SUAS Autonomous Challenge | **NEAT** | **0.0 / 100** | 1.10 s | 22.0 m | 20.0 m/s | 5.8 m | 1.3 m | 0.03 | **0 targets** | 1000 m |
| Test D - AUVSI SUAS Autonomous Challenge | **NEAT** | **65.2 / 100** | 30.00 s | 556.1 m | 18.5 m/s | 20.6 m | 237.8 m | 7.44 | **2 targets** | 1000 m |
| Test D - AUVSI SUAS Autonomous Challenge | **NEAT** | **6.7 / 100** | 1.93 s | 47.4 m | 24.5 m/s | 6.3 m | 8.4 m | 0.93 | **0 targets** | 1000 m |
| Test D - AUVSI SUAS Autonomous Challenge | **NEAT** | **9.3 / 100** | 2.03 s | 37.8 m | 18.6 m/s | 6.5 m | 8.6 m | 1.09 | **0 targets** | 1000 m |
| Test D - AUVSI SUAS Autonomous Challenge | **NEAT** | **52.0 / 100** | 24.23 s | 1083.3 m | 44.7 m/s | 4.4 m | 258.0 m | 13.67 | **4 targets** | 1000 m |
| Test D - AUVSI SUAS Autonomous Challenge | **NEAT** | **66.6 / 100** | 16.00 s | 923.5 m | 57.7 m/s | 17.4 m | 223.7 m | 13.40 | **4 targets** | 1000 m |
| Test D - AUVSI SUAS Autonomous Challenge | **NEAT** | **54.2 / 100** | 15.57 s | 989.0 m | 63.5 m/s | 14.8 m | 235.3 m | 15.19 | **4 targets** | 1000 m |
| Test E - FAI F3D/F5D Pylon Racing | **PID** | **55.6 / 100** | 33.97 s | 1008.3 m | 29.7 m/s | 15.2 m | 197.1 m | 10.06 | **1 targets** | 1000 m |
| Test E - FAI F3D/F5D Pylon Racing | **PID** | **39.6 / 100** | 27.00 s | 1007.2 m | 37.3 m/s | 22.9 m | 183.8 m | 7.20 | **1 targets** | 1000 m |
| Test E - FAI F3D/F5D Pylon Racing | **PID** | **55.6 / 100** | 40.00 s | 848.2 m | 21.2 m/s | 13.0 m | 107.4 m | 35.35 | **1 targets** | 1000 m |
| Test E - FAI F3D/F5D Pylon Racing | **PID** | **43.2 / 100** | 25.63 s | 1015.2 m | 39.6 m/s | 17.1 m | 360.0 m | 6.77 | **0 targets** | 1000 m |
| Test E - FAI F3D/F5D Pylon Racing | **NEAT** | **25.5 / 100** | 1.33 s | 27.2 m | 20.4 m/s | 5.7 m | 8.4 m | 0.03 | **0 targets** | 1000 m |
| Test E - FAI F3D/F5D Pylon Racing | **NEAT** | **36.7 / 100** | 24.97 s | 580.2 m | 23.2 m/s | 13.8 m | 86.3 m | 9.09 | **2 targets** | 1000 m |
| Test E - FAI F3D/F5D Pylon Racing | **NEAT** | **18.1 / 100** | 11.77 s | 497.0 m | 42.2 m/s | -13.4 m | 54.0 m | 8.04 | **1 targets** | 1000 m |
| Test E - FAI F3D/F5D Pylon Racing | **NEAT** | **21.6 / 100** | 2.87 s | 52.4 m | 18.3 m/s | 5.1 m | 10.5 m | 1.58 | **0 targets** | 1000 m |
| Test E - FAI F3D/F5D Pylon Racing | **NEAT** | **20.7 / 100** | 15.53 s | 542.8 m | 34.9 m/s | 15.8 m | 97.5 m | 7.64 | **1 targets** | 1000 m |
| Test E - FAI F3D/F5D Pylon Racing | **NEAT** | **11.1 / 100** | 13.70 s | 810.9 m | 59.2 m/s | 32.5 m | 47.8 m | 13.37 | **2 targets** | 1000 m |

### Course Maps & Test Conditions Stored in Database

* **Arena Radius:** 1,000.0 meters (all boundary constraints removed).
* **Waypoint Capture Radius:** 2.0 meters.
* **Test B (Structured Waypoint Course):**
  * WP 1: `(150.0m, 0.0m, 10.0m)` — 150m straight climb/cruise
  * WP 2: `(236.6m, 50.0m, 15.0m)` — +30 deg dogleg, climb to 15m
  * WP 3: `(151.7m, -34.8m, 10.0m)` — -45 deg diagonal return
  * WP 4: `(300.0m, -34.8m, 12.0m)` — Long straight sprint
* **Test C (Aggressive Slalom):**
  * WP 1: `(80.0m, 45.0m, 22.0m)` — Sharp right turn, rapid climb
  * WP 2: `(150.0m, -45.0m, 8.0m)` — Sharp left turn, dive to 8m
  * WP 3: `(220.0m, 45.0m, 25.0m)` — Reverse right, climb to 25m
  * WP 4: `(280.0m, -45.0m, 6.0m)` — Reverse left, low-altitude terrain hug

### Waypoint Miss Analysis (Why PID scored 0/4)
* **Turning Radius vs. Waypoint Spacing:** At 29.4 m/s with bank angle limited to 14.3 degrees (0.25 rad), the PID's turning circle is ~345 meters wide. It cannot execute the tight turns required by Test B and C.
* **Sequential Queue Blocking:** In Test B, PID grazed Target 1 at 4.30m (just 2.3m outside the 2.0m capture bubble). In PyFlyt, waypoint queues are strictly sequential: because Target 1 was never registered, the queue never advanced to Target 2, even though the PID flew directly through Target 4 later (1.01m closest approach)!

---

## 7. Immediate Execution Checklist
1. **Complete Gen 300 & Freeze `phase2_neat_caged`** [DONE - Checkpoint Gen 297].
2. **Run Generalization Battery** on both `pid_open_sky` and `phase2_neat_caged` [DONE - Recorded in `output/icarus.db`].
3. **Launch Phase 2B (`phase2_neat_open`)** in 1000m arena.
4. **Proceed to Phase 3 (Morphology Parametrics) & Phase 4 (Co-Evolution)** across both tracks.
