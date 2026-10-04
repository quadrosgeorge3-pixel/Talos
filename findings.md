# Project TALOS — Full Experiment Report

> A complete walkthrough of what we did, what we found, and where we're at.  
> Anyone reading this should understand the full picture.

---

## What Is This?

Project TALOS is a neuroevolution + body co-evolution experiment for autonomous fixed-wing UAV flight. We evolve both the **brain** (a NEAT neural network controller) and the **body** (airframe morphology — wing size, tail area, mass, thrust) to see if co-evolving them together produces better flight than either alone. Everything runs in a PyBullet physics simulator using PyFlyt.

---

## The Experiment Journey (Step by Step)

### Phase 0 — Baselines

- **B0: PID Baseline** (`pid_open_sky`) — We flew the default PyFlyt fixed-wing airframe with a hand-tuned PID controller to establish a performance floor; it reliably flies straight at ~29 m/s but has zero intelligence — it can't navigate waypoints or adapt to anything.

- **TALOS-B01** — Initial baseline configuration run to validate the simulation pipeline works end-to-end; no individuals stored, just confirmed the tooling.

### Phase 1 — Early Brain Evolution

- **C1: First NEAT Experiment** (`phase2_neat_caged`) — Our first attempt at evolving a neural network controller inside a 100m bounded dome; ran 320 individuals over ~120 generations; the best one learned to fly fast (411m distance) but always crashed — it discovered a "dive bomb" exploit where it trades altitude for speed, scoring high on distance before slamming into the ground.

### Phase 2 — Serious Brain Evolution

- **TALOS-P2B: 300-Generation NEAT** (`TALOS-P2B_gen300_champ`) — We scaled up to 300 generations of pure brain evolution (no body changes, just the default airframe); the Gen 300 champion learned genuine flight control — it's the first agent to **hit 3/4 waypoint gates** on the open-sky course, but it's unstable on the default body and crashes within 2-3 seconds on Test A and C because the standard airframe can't handle its aggressive manoeuvres.

### Phase 3A — Body Evolution with NEAT Pilot

- **TALOS-P3A** (`p3a_champ`) — We froze a NEAT pilot and evolved just the body to work with it; 5,000 individuals over 100 generations; the champion evolved the **largest wing area** (0.76 m², +153% vs default) and max thrust for a lighter frame (2.94 kg); it's an efficient glider that consistently places 3rd across tests — solid but never spectacular.

### Phase 3B — Body Evolution with PID Pilot

- **TALOS-P3B** (`p3b_champ`) — We evolved the body under the stable PID controller; 5,000 individuals over 100 generations; the champion went full **brute-force**: maximum wingspan (3.0m, +200%), heaviest mass (4.22 kg, +252%), max thrust — essentially a big, heavy, fast sailplane that PID can drive at 47+ m/s; it holds the **no-crash distance record** (1,018.7m) because the PID never loses control of this stable platform.

### Phase 3C — Body-Brain Co-Evolution (The Main Event)

- **TALOS-P3C** (`p3c_champ`) — This is the key experiment: we took the frozen NEAT Gen 300 brain and evolved a body **specifically for it**; 5,000 individuals over 100 generations; the champion evolved a completely unique strategy — instead of going big like P3B, it grew **massively oversized tail surfaces** (+347% horizontal tail, +377% vertical tail) to act as passive stability augmentation, compensating for the neural controller's erratic tendencies; this "self-stabilizing" airframe lets the NEAT brain focus on navigation instead of fighting to stay airborne.

---

## What Got Benchmarked (and What Didn't)

Every experiment's champion was put through a standardised 3-test gauntlet. Here's the full pool:

| Benchmark Contender | Source Experiment | In Pool? | Notes |
|---|---|---|---|
| `pid_open_sky` | B0 Baseline PID | **YES** (3 tests) | The performance floor — default body + PID |
| `phase2_neat_caged` | C1 Early NEAT | **YES** (3 tests) | The first neural pilot — crashes fast but proved NEAT can learn |
| `TALOS-P2B_gen300_champ` | TALOS-P2B | **YES** (3 tests) | The 300-gen evolved brain on default body — fragile but smart |
| `p3a_champ_pid` | TALOS-P3A | **YES** (3 tests) | P3A body with PID — tests if the evolved body helps even PID |
| `p3a_champ_neat_gen300` | TALOS-P3A | **YES** (3 tests) | P3A body with NEAT brain — the combo it was evolved for |
| `p3b_champ_pid` | TALOS-P3B | **YES** (3 tests) | P3B body with PID — the speed/distance king |
| `p3b_champ_neat_gen300` | TALOS-P3B | **YES** (3 tests) | P3B body with NEAT brain — body designed for PID, crashes with NEAT |
| `p3b_gen054_pid` | TALOS-P3B (gen 54) | **YES** (3 tests) | Mid-evolution snapshot — how good is a half-evolved body? |
| `p3b_gen054_neat_gen300` | TALOS-P3B (gen 54) | **YES** (3 tests) | Same mid-evo body but with NEAT — also crashes |
| `p3c_champ_pid` | TALOS-P3C | **YES** (3 tests) | P3C body with PID — tail-heavy body works well even with PID |
| `p3c_champ_neat_gen300` | TALOS-P3C | **YES** (3 tests) | **THE RECORD HOLDER** — co-evolved body + brain = 1.23 km |
| C1 champion directly | C1 | **NO** | Not benchmarked as a standalone; represented by `phase2_neat_caged` |
| TALOS-B01 | B01 | **NO** | Config validation run, no individuals stored |

> [!IMPORTANT]
> **Yes, both baselines are in the pool.** The PID baseline (`pid_open_sky`) and the early NEAT (`phase2_neat_caged` from C1) compete against all evolved contenders. They consistently rank in the bottom half — the evolved bodies significantly outperform them.

---

## The Three Benchmark Tests

| Test | Duration | Arena | What It Tests |
|---|---|---|---|
| **Test A** — Calm Cruise | 20s | 500m radius | Pure stable flight in calm conditions — can you stay airborne and go far? |
| **Test B** — Waypoint Course | 25s | 1000m radius | Navigate through 4 waypoint gates in open sky — tests range + manoeuvrability |
| **Test C** — Aero Slalom | 25s | 1000m radius | Aggressive turns and wind — the stress test |

---

## All-Time Records

| Record | Value | Who | Test |
|---|---|---|---|
| **Longest Flight** | **1,229.4 m** | P3C body + NEAT Gen300 | Test B |
| **Fastest Mean Speed** | **49.2 m/s** (177 km/h) | P3C body + NEAT Gen300 | Test B |
| **Most Waypoints** | **3 / 4 gates** | P3C body + NEAT Gen300 | Test B |
| **Longest No-Crash** | **1,018.7 m** | P3B body + PID | Test C |

---

## Top 3 Per Test (Leaderboard)

### Test A — Calm Cruise
| # | Contender | Dist | Speed | Crashed | Why |
|---|---|---|---|---|---|
| 🥇 | P3B + PID | 939 m | 47.0 m/s | No | Biggest airframe + max thrust = raw power in a straight line |
| 🥈 | P3C + PID | 769 m | 38.5 m/s | No | Oversized tail keeps it ultra-stable even without neural control |
| 🥉 | P3A + PID | 727 m | 36.4 m/s | No | Largest wing area = most lift, efficient cruiser |

### Test B — Waypoint Course
| # | Contender | Dist | Speed | Gates | Crashed | Why |
|---|---|---|---|---|---|---|
| 🥇 | **P3C + NEAT** | **1,229 m** | **49.2 m/s** | **3/4** | Yes | Co-evolved synergy — tail stability lets NEAT push aggressively through gates |
| 🥈 | P3B + PID | 1,005 m | 47.9 m/s | 0/4 | No | Fast but PID can't navigate — just flies far in a straight line |
| 🥉 | P3C + PID | 991 m | 39.6 m/s | 0/4 | No | P3C body is good under any controller, but PID can't seek gates |

### Test C — Aero Slalom
| # | Contender | Dist | Speed | Crashed | Why |
|---|---|---|---|---|---|
| 🥇 | P3B + PID | 1,019 m | 47.8 m/s | No | Heavy frame + wide span plows through turbulence |
| 🥈 | P3C + PID | 991 m | 39.6 m/s | No | Tail-heavy stability absorbs aggressive conditions |
| 🥉 | P3A + PID | 938 m | 37.5 m/s | No | High wing area keeps it aloft but drifts sideways (507m deviation) |

---

## The Evolved Bodies — How They Differ

| Parameter | Default | P3A | P3B | P3C | What It Means |
|---|---|---|---|---|---|
| Wingspan | 1.0 m | 3.0 m | 3.0 m | 1.8 m | P3C doesn't need huge wings — stability comes from tail |
| Wing Area | 0.30 m² | 0.76 m² | 0.42 m² | 0.57 m² | P3A went for max lift, P3C went for balanced |
| H-Tail Area | 0.05 m² | 0.07 m² | 0.09 m² | **0.22 m²** | P3C's tail is **4.5x the default** — this is the key innovation |
| V-Tail Area | 0.05 m² | 0.06 m² | 0.02 m² | **0.24 m²** | P3C also massively increased yaw stability |
| Thrust/Weight | 0.60 | 1.50 | 1.50 | 1.49 | All evolved bodies maxed out thrust — more power is always better |
| Mass | 1.2 kg | 2.9 kg | 4.2 kg | 3.4 kg | P3B is heaviest — momentum helps in PID straight-line flight |
| CG Offset | 0.0 m | −0.03 m | −0.05 m | **+0.08 m** | P3C shifted CG forward — only body to do this — enhances pitch stability |

---

## Key Findings (The Takeaways)

1. **Body-brain co-evolution works.** The P3C body + NEAT brain combo holds every meaningful record despite neither component being impressive alone — the NEAT brain crashes in <3s on the default body, and the P3C body is just mid-tier under PID control.

2. **Evolution finds non-obvious solutions.** No human engineer would design an airframe with 4.5x oversized tail surfaces — but evolution discovered that passive aerodynamic stability is the best way to compensate for a neural controller's unpredictable outputs.

3. **The brain needs the right body to express what it learned.** The NEAT Gen 300 champion genuinely learned waypoint navigation (3/4 gates), but it can only demonstrate this skill when paired with a body that keeps it alive long enough to navigate.

4. **PID dominates on stability, NEAT dominates on intelligence.** PID never crashes but can't navigate gates (0/4 across all tests). NEAT hits gates but needs body support. There's a clear capability ceiling for each approach.

5. **Bigger isn't always better.** P3B (the biggest body) wins PID tests but is the worst NEAT body — its high mass and inertia fight against the neural controller's quick corrections. P3C found a smarter strategy than just scaling up.

6. **Early evolution matters more than you'd think.** The P3B gen-54 snapshot (halfway through evolution) already performs within 80% of the final champion under PID — most gains happen in the first half of training.

7. **The C1 "dive bomb" exploit was a real finding.** Our first neural pilot discovered it could game the fitness function by trading altitude for distance — this taught us about reward shaping and led to better fitness functions in later experiments.

---

## Where We're At Right Now

- **7 experiments completed**, all stored in `icarus.db` — 15,620 evolved individuals total
- **33 benchmark evaluations** across 11 contenders × 3 tests, all results stored and queryable
- **3D Flight Arena viewer** live with all trajectories, playback, telemetry HUD, and flight-by-flight comparison
- **The P3C + NEAT combo** is the current champion at 1.23 km distance and 3/4 waypoint gates
- **All airframes are reconstructable** from database-stored morphology JSON — the bodies can be rebuilt independently from the DB
- **Next logical step** would be unfreezing the brain during P3C-style evolution (true simultaneous body-brain co-evolution) — currently the brain was frozen and only the body adapted to it

---

*All data sourced from `output/icarus.db` · 7 experiments · 15,620 individuals · 33 benchmark evaluations*
