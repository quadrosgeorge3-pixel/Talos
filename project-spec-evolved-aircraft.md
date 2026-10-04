# Project Spec: Evolutionary Co-Design of Powered Aircraft
**Working title:** Icarus (rename freely)

---

## 1. Vision (one-liner)

Evolve both the *shape* of a powered plane and the *neural network that flies it*, together, generation over generation — starting from planes that immediately crash, ending with planes that fly efficiently on a network as small as possible.

**Layman pitch (keep this separate from everything below, always):**
> "I made planes evolve, like Darwin's finches — except instead of millions of years, it takes a few hours on my laptop."

---

## 2. Core Idea

- Two things evolve **together**, not separately:
  1. **Morphology genome** — physical parameters of the plane (wingspan, tail size, thrust-to-weight ratio, mass placement).
  2. **Controller genome** — a NEAT-style neural network (topology *and* weights evolve) that reads flight sensors and outputs control signals.
- On top of the base evolutionary loop, a **grow-and-prune phase** periodically strips the controller network down to the smallest version that keeps performance — evolutionary growth (instead of the original gradient-based growth) combined with magnitude/impact-based pruning, in the spirit of the NeST paradigm (Dai, Yin, Jha — Princeton, 2017).
- End result is two things at once: a plane design that performs well, *and* proof of how small a brain can fly it.

---

## 3. Why This Is a Real, Open Question (not a tutorial)

Co-evolving body and controller together is a genuinely unresolved area in evolutionary robotics — the "morphology vs. controller" interaction problem (one tends to dominate/constrain the other, and nobody has a clean general answer for how to balance their evolution). Layering an explicit grow-and-prune efficiency pass on top of that — asking not just "does it fly" but "what's the smallest brain that can fly it" — is a further, less-explored combination on top of that open problem.

---

## 4. Technical Foundation

| Layer | Tool / Approach |
|---|---|
| Physics simulation | **PyFlyt** (Gymnasium-API UAV simulator, built on Bullet physics) |
| Airframe | PyFlyt's `Fixedwing` UAV — tube-and-wing design, 5 lifting-surface components (main wing, 2 ailerons, horizontal tail, vertical tail) + motor |
| Morphology configurability | PyFlyt UAVs are defined via a **URDF (geometry/mass) + YAML (parameters) file pair** — arbitrary configurations without touching library internals. Each morphology genome = one generated URDF/YAML pair. |
| Baseline controller | PyFlyt's own built-in tuned PID/cascaded controller — used as the credible, established control condition to beat (not a hand-tuned one-off) |
| Evolved controller | NEAT (topology + weights), via the `neat-python` library — don't reimplement speciation/crossover/historical-marker logic from scratch |
| Efficiency pass | Grow-and-prune, evolutionary-growth variant of NeST: periodic pass on top performers, ablate low-impact connections/neurons, keep only if fitness barely drops |
| Aerodynamics reference | Already handled inside PyFlyt's Fixedwing model (aerofoil characteristics sourced from a real UAV aerodynamics modeling paper) — no need to build lift/drag from scratch |
| Compute | CPU-only, no GPU required. Headless simulation during evolution; parallelize genome evaluation across CPU cores (`multiprocessing`) |

---

## 5. Genome Design

**Morphology genome (small parameter vector):**
- Wingspan / main wing area
- Horizontal + vertical tail size
- Thrust-to-weight ratio / motor placement
- Mass distribution

**Controller genome (NEAT network):**
- Inputs: airspeed, pitch, altitude, angle of attack (extend with PyFlyt's native observation space as needed)
- Outputs: elevator, throttle (extend to aileron/rudder once level flight is solid)
- Structure: starts minimal (near-direct input→output), grows connections/nodes via NEAT mutation, weights evolve alongside structure

---

## 6. Build Order (methodology — do in this order)

1. **Confirm the baseline.** Get PyFlyt's `Fixedwing` environment running with its own built-in PID controller. Confirm it flies stably. This is your control condition — don't skip it.
2. **Wire in NEAT** on top of the *fixed default* airframe first (controller evolution only, no morphology evolution yet). Confirms the evolutionary loop itself works before adding complexity.
3. **Add the morphology genome** — generate URDF/YAML per genome, evolve morphology params alongside the NEAT controller.
4. **Run headless, log everything** — every generation's genomes + fitness scores written to disk. No rendering during evolution.
5. **Add the grow-and-prune pass** — only once step 4 is reliably producing flying planes. Pruning something that doesn't work yet wastes time.
6. **Build the visualization/replay layer last** (see Section 8) — replay from logged data, don't render live during evolution.

---

## 7. Success Conditions (define before declaring anything "done")

1. **Survival milestone** — large majority of the population sustains controlled, level-ish flight for a fixed duration (e.g. 30s) without stalling/crashing.
2. **Efficiency milestone** — best individual's lift-to-drag / distance-per-fuel beats PyFlyt's baseline PID-controlled default airframe by a meaningful margin.
3. **Maneuverability milestone** — best individual completes a fixed waypoint course faster than the baseline.
4. **Structural efficiency milestone** — post-pruning network matches pre-pruning fitness (within a small tolerance, e.g. <5% drop) using a meaningfully smaller network (e.g. 50%+ fewer neurons/connections).

---

## 8. Visualization / Demo Plan

- **Dev-time:** simple rendering during manual test runs only (not during full evolutionary runs) to sanity-check behavior.
- **Demo-time (the actual "wow" artifact):** replay saved genome history as a time-lapse — early generations crashing immediately → later generations flying clean — shown side-by-side with a fitness-over-generations graph. Cheap to produce after the fact since it's replaying logged data, not re-simulating live.

---

## 9. Two Separate Write-Ups (do not merge these)

Lesson carried over from the Genesis thesis experience: **never let one document try to serve both audiences.**

- **Technical spec** (this document, and whatever implementation notes follow it) — as dense as it needs to be. For you and only you, or anyone who explicitly asks for depth.
- **Narrative one-pager** (written separately, afterward, once it's flying) — hook → what it does → why it's interesting → one diagram if needed. This is the only version anyone else (LinkedIn, a senior, a recruiter) ever sees first.

---

## 10. Simple Representation (pipeline overview)

```
 ┌─────────────────────┐        ┌──────────────────────┐
 │  Morphology Genome   │        │   Controller Genome    │
 │  (wingspan, tail,    │        │   (NEAT network:       │
 │   thrust, mass)      │        │    topology + weights) │
 └──────────┬───────────┘        └───────────┬───────────┘
            │                                │
            ▼                                ▼
     Generate URDF/YAML              Reads flight sensors
      (plane's body)                 → outputs controls
            │                                │
            └───────────────┬────────────────┘
                             ▼
                  ┌───────────────────────┐
                  │   PyFlyt simulation    │
                  │  (Fixedwing UAV, one   │
                  │   flight episode)      │
                  └───────────┬────────────┘
                              ▼
                   Fitness score (survival,
                   efficiency, maneuverability)
                              │
                              ▼
              ┌────────────────────────────────┐
              │  Selection + NEAT crossover /    │
              │  mutation → next generation      │
              └───────────────┬────────────────┘
                              │
              (every few generations)
                              ▼
                 ┌─────────────────────────┐
                 │  Grow-and-prune pass on   │
                 │  top performers' networks │
                 └─────────────────────────┘
                              │
                              ▼
                  Repeat until success
                  conditions (Sec. 7) are met
                              │
                              ▼
                 Replay logged history →
                 time-lapse + fitness curve
                 (the demo artifact)
```

---

## 11. Open Questions / Risks to Watch

- **Oscillation risk:** grow-and-prune could thrash (grow, prune, grow the same thing back) without ever converging — log genome size + fitness per generation from day one so this is visible early.
- **Morphology/controller imbalance:** one may dominate evolution over the other (a classic open problem in this space) — worth watching whether all improvement comes from morphology while the controller stagnates, or vice versa.
- **PyFlyt's Fixedwing is single-morphology by default** — the URDF/YAML generation-per-genome layer is custom work you're adding on top; it's the part with the least existing precedent to lean on.
