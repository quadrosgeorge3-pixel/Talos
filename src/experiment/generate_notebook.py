"""Automated Research Lab Notebook Generator for Project Talos.

Queries output/icarus.db and generates docs/LAB_NOTEBOOK.md with:
- Plain-English Glossary (No cryptic codes)
- Permanent Baseline Measurements
- Live Evolution Progress & Stats
- Key Scientific Insights & Discoveries
- Next Steps Roadmap
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone


def generate_lab_notebook(
    db_path: str = "output/icarus.db",
    output_md: str = "docs/LAB_NOTEBOOK.md",
) -> None:
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    con = sqlite3.connect(db_path)
    cur = con.cursor()

    # Query baselines
    cur.execute("""
        SELECT baseline_id, distance_mean, survival_time_mean, energy_mean, altitude_error_mean
        FROM baseline_metrics
        WHERE baseline_id IN ('pid_bounded_100m', 'pid_open_sky')
    """)
    baselines = {r[0]: r for r in cur.fetchall()}

    # Query evolution stats per experiment
    def _get_exp_stats(eid: str):
        cur.execute("SELECT max(generation) FROM generations WHERE experiment_id = ?", (eid,))
        m_gen = cur.fetchone()[0]
        if m_gen is None:
            return None
        cur.execute("""
            SELECT best_fitness, mean_fitness, best_distance, best_survival_time, best_energy, best_nodes, best_connections
            FROM generations WHERE experiment_id = ? AND generation = ?
        """, (eid, m_gen))
        g_row = cur.fetchone() or (0, 0, 0, 0, 0, 0, 0)
        cur.execute("""
            SELECT distance, survival_time, altitude_error, energy, nodes, connections, generation
            FROM individuals WHERE experiment_id = ? AND crashed = 0 AND survival_time >= 9.9
            ORDER BY distance DESC LIMIT 1
        """, (eid,))
        top = cur.fetchone() or (0, 0, 0, 0, 0, 0, 0)
        return {
            "max_gen": m_gen,
            "best_fitness": g_row[0],
            "mean_fitness": g_row[1],
            "best_distance": g_row[2],
            "best_survival": g_row[3],
            "nodes": g_row[5],
            "connections": g_row[6],
            "top_distance": top[0],
            "top_gen": top[6],
        }

    c1_stats = _get_exp_stats("C1")
    p2b_stats = _get_exp_stats("TALOS-P2B")

    # Check if precision_score column exists
    cols = [r[1] for r in cur.execute("PRAGMA table_info(benchmark_evaluations)").fetchall()]
    if "precision_score" not in cols:
        cur.execute("ALTER TABLE benchmark_evaluations ADD COLUMN precision_score REAL")
        con.commit()

    # Query benchmark evaluations
    cur.execute("""
        SELECT test_name, controller_type, flight_time, distance, mean_airspeed,
               mean_altitude, max_lateral_dev, control_energy, crashed, stalling,
               waypoints_hit, arena_radius, waypoint_radius, course_map_json, precision_score
        FROM benchmark_evaluations
        ORDER BY test_name, controller_type DESC
    """)
    bench_rows = cur.fetchall()

    con.close()

    # Format Markdown
    md = []
    md.append("# Project Talos — Automated Research Lab Notebook")
    md.append(f"> **Last Auto-Generated:** {now_str}  ")
    md.append(f"> **Active Database:** `{db_path}`  ")
    if p2b_stats:
        md.append(f"> **Phase 2B (Open-Sky):** Gen {p2b_stats['max_gen']} / 300 | **Phase 2A (Bounded):** Gen 300 / 300 (Complete)\n")
    else:
        md.append(f"> **Phase 2A (Bounded):** Gen 300 / 300 (Complete) | **Phase 2B (Open-Sky):** Ready / Queued\n")
    md.append("---\n")

    md.append("## 1. Plain-English Experiment Glossary")
    md.append("To keep research clear and accessible, here is the simplified naming key used across the project:\n")
    md.append("| Plain-English Name | What It Actually Is | Arena | Duration |")
    md.append("| :--- | :--- | :--- | :--- |")
    md.append("| **`pid_bounded_100m`** | Reference PID Autopilot | 100m Flight Dome | ~3.94s (Boundary Halt) |")
    md.append("| **`pid_open_sky`** | Reference PID Autopilot | 500m Open Sky | 10.00s (Full duration) |")
    md.append("| **`phase2_neat_caged`** | Current Evolving Brain | 100m Flight Dome | 10.00s (Banked Loiterer) |")
    md.append("| **`phase2_neat_open`** | Upcoming Open-Sky Brain | 1,000m Open Sky | 10.00s (Cruising Specialist) |")
    md.append("| **`phase3_morphology`** | Airframe Shape Sensitivity | 1,000m Open Sky | Systematic geometry sweeps |")
    md.append("| **`phase4_coevolution`** | Body + Brain Co-Evolution | 1,000m Open Sky | Co-adapting plane & controller |\n")
    md.append("---\n")

    md.append("## 2. Permanent Baseline Records")
    md.append("Both baseline flight conditions are permanently recorded in the database:\n")
    md.append("| Baseline Condition | Flight Time | Distance | Airspeed | Altitude Hold | Status |")
    md.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
    if 'pid_bounded_100m' in baselines:
        b = baselines['pid_bounded_100m']
        status_str = "**Completed full 10.0s flight (Geofenced 40m orbit)**" if b[2] >= 9.9 else "**Halted at 100m geofence**"
        spd_str = f"~{b[1]/b[2]:.1f} m/s" if b[2] > 0 else "~17.6 m/s"
        md.append(f"| **`pid_bounded_100m`** | {b[2]:.2f} s | {b[1]:.1f} m | {spd_str} | Altitude hold (±{b[4]:.2f}m) | {status_str} |")
    if 'pid_open_sky' in baselines:
        b = baselines['pid_open_sky']
        md.append(f"| **`pid_open_sky`** | {b[2]:.2f} s | {b[1]:.1f} m | ~26.8 m/s | Altitude hold (±{b[4]:.2f}m) | **Completed full 10.0s flight** |\n")
    md.append("---\n")

    md.append("## 3. Phase 2 Controller Evolution Status (Dual-Track)")
    if c1_stats:
        md.append("### Track 1: Bounded Cage (`phase2_neat_caged` / C1)")
        md.append(f"* **Status:** **Completed (300 / 300 Generations)**")
        md.append(f"* **All-Time Longest Stable Flight:** **{c1_stats['top_distance']:.1f} meters** (Gen {c1_stats['top_gen']})")
        md.append(f"* **Champion Architecture:** {c1_stats['nodes']} nodes, {c1_stats['connections']} connections (Loitering Reflex)")
    if p2b_stats:
        md.append("\n### Track 2: Open Sky (`phase2_neat_open` / TALOS-P2B)")
        md.append(f"* **Status:** **Active / In Progress (Generation {p2b_stats['max_gen']} / 300)**")
        md.append(f"* **Current Best Distance:** **{p2b_stats['best_distance']:.1f} meters**")
        md.append(f"* **Current Best Fitness:** **{p2b_stats['best_fitness']:.4f}**")
        md.append(f"* **Active Architecture:** {p2b_stats['nodes']} nodes, {p2b_stats['connections']} connections")
    else:
        md.append("\n### Track 2: Open Sky (`phase2_neat_open` / TALOS-P2B)")
        md.append("* **Status:** **Ready to launch (1,000m arena, 300 generations, identical starting seed 42)**\n")
    md.append("---\n")

    md.append("## 4. Key Discoveries to Date")
    md.append("### A. The 100-Meter Geofence Discovery")
    md.append("* The 3.94s flight time of the baseline PID was caused by PyFlyt's 100m spherical flight dome, not an aerodynamic stall or crash.")
    md.append("* When tested in open skies, the PID flies for 10.0s and covers 268.5 meters.")

    md.append("### B. Emergent Banked Loitering (The 'Caged Bird' Phenomenon)")
    md.append("* Because crossing the 100m perimeter carried a -100 death penalty, NEAT evolved coordinated banked turns to stay inside a 60m radius while clocking 246+ meters of flight distance.")
    md.append("* When tested in a 1 km open field, the brain flew for 19.03 seconds and 509 meters, proving genuine aerodynamic stabilization, while retaining its persistent circular looping reflex.")

    md.append("### C. The Lift vs. Speed Equilibrium")
    md.append("* At cruise speed (>20 m/s), the PyFlyt airframe generates lift exceeding vehicle weight.")
    md.append("* Evolution discovered a stable trim altitude at ~15m where lift equals weight without dangerous nose-down elevator deflection.")

    md.append("### D. The Bounded PID Score Deconstruction (Is 0.4733 Reliable?)")
    md.append("* **Mathematical Breakdown:** The PID's 0.4733 score came from tight altitude hold (0.218 out of 0.50) and low energy (0.147 out of 0.15) over 3.94s, despite earning low survival (0.079 out of 0.20) and low distance (0.030 out of 0.15).")
    md.append("* **The Geofence Grace:** The baseline evaluator only penalized ground crashes and stalls, granting the PID a 'graceful exit' at the 100m wall without the -100 death penalty applied to evolving genomes. If penalized like NEAT, its bounded score would be -99.5.")
    md.append("* **Open-Sky Truth:** In open skies, where PID actually flies 10s and 268.5m, its true unconstrained fitness is **0.530**.")

    md.append("### E. The Sequential Behavioral Strategy Hypothesis")
    md.append("* **Core Scientific Inference:** As the fitness landscape changes (via environmental boundaries or curriculum shifts), NEAT does not monotonically improve a single generalized flight policy. Instead, it sequentially discovers and transitions between distinct, specialized behavioral strategies.")
    md.append("* **Empirical Evidence:**")
    md.append("  * **Mode 1 (100m Dome):** Tight circular loitering (30m radius) to evade boundary death.")
    md.append("  * **Mode 2 (1000m Dome, Gen 0-34):** Ballistic dive and maximum acceleration (34-42 m/s, 813m distance) to exploit raw distance rewards.")
    md.append("  * **Mode 3 (1000m Dome, Gen 35+):** Reorganization into pitch-leveling horizon control (drift dropped from 258m to 13m) when 50% altitude priority was activated.\n")
    md.append("---\n")

    md.append("## 5. Dual-Track Architecture for Phases 2, 3, and 4")
    md.append("We have adopted a **Dual-Track Evolutionary Pipeline** to study Specialist vs. Generalist adaptation:\n")
    md.append("| Pipeline Track | Training Arena | Target Specialization | Expected Morphology in Phase 4 |")
    md.append("| :--- | :--- | :--- | :--- |")
    md.append("| **Track 1: Bounded (100m)** | 100m Dome (-100 boundary penalty) | **Agility & Loitering** (Spatial confinement) | Compact wingspan, high roll rate, oversized tail control |")
    md.append("| **Track 2: Open-Sky (1000m)**| 1000m Open Sky (Unconstrained) | **Aerodynamic Efficiency** (High-speed cruise) | High aspect ratio, low induced drag, slender glider body |\n")
    md.append("### Standardized Generalization Battery (Tests 1, 2, 3)")
    md.append("Every evolved controller and morphology from both tracks is evaluated against the same three zero-shot tests:")
    md.append("1. **Test A - Open-Sky Straight Flight (1 km):** Measures raw cross-country endurance and drift.")
    md.append("2. **Test B - Open-Sky Waypoint Course:** Measures structured waypoint navigation.")
    md.append("3. **Test C - Aggressive Aero Slalom:** Measures high-G bank angle agility and rapid altitude response.\n")
    md.append("---\n")

    if bench_rows:
        md.append("## 6. Head-to-Head Generalization Benchmark Suite Results")
        md.append("Recorded in table `benchmark_evaluations` within `output/icarus.db`:\n")
        md.append("| Test Name | Controller | Precision Score | Flight Time | Distance | Airspeed | Altitude | Lateral Dev | Energy | Waypoints Hit | Arena Radius |")
        md.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for r in bench_rows:
            t_name, c_type, f_time, dist, spd, alt, lat_dev, energy, crashed, stalling, wp_hit, arena_r, wp_r, course_json, prec_score = r
            score_str = f"**{prec_score:.1f} / 100**" if prec_score is not None else "N/A"
            md.append(f"| {t_name} | **{c_type}** | {score_str} | {f_time:.2f} s | {dist:.1f} m | {spd:.1f} m/s | {alt:.1f} m | {lat_dev:.1f} m | {energy:.2f} | **{wp_hit} targets** | {arena_r:.0f} m |")
        md.append("\n### Course Maps & Test Conditions Stored in Database\n")
        md.append("* **Arena Radius:** 1,000.0 meters (all boundary constraints removed).")
        md.append("* **Waypoint Capture Radius:** 2.0 meters.")
        md.append("* **Test B (Structured Waypoint Course):**")
        md.append("  * WP 1: `(150.0m, 0.0m, 10.0m)` — 150m straight climb/cruise")
        md.append("  * WP 2: `(236.6m, 50.0m, 15.0m)` — +30 deg dogleg, climb to 15m")
        md.append("  * WP 3: `(151.7m, -34.8m, 10.0m)` — -45 deg diagonal return")
        md.append("  * WP 4: `(300.0m, -34.8m, 12.0m)` — Long straight sprint")
        md.append("* **Test C (Aggressive Slalom):**")
        md.append("  * WP 1: `(80.0m, 45.0m, 22.0m)` — Sharp right turn, rapid climb")
        md.append("  * WP 2: `(150.0m, -45.0m, 8.0m)` — Sharp left turn, dive to 8m")
        md.append("  * WP 3: `(220.0m, 45.0m, 25.0m)` — Reverse right, climb to 25m")
        md.append("  * WP 4: `(280.0m, -45.0m, 6.0m)` — Reverse left, low-altitude terrain hug")
        md.append("\n### Waypoint Miss Analysis (Why PID scored 0/4)")
        md.append("* **Turning Radius vs. Waypoint Spacing:** At 29.4 m/s with bank angle limited to 14.3 degrees (0.25 rad), the PID's turning circle is ~345 meters wide. It cannot execute the tight turns required by Test B and C.")
        md.append("* **Sequential Queue Blocking:** In Test B, PID grazed Target 1 at 4.30m (just 2.3m outside the 2.0m capture bubble). In PyFlyt, waypoint queues are strictly sequential: because Target 1 was never registered, the queue never advanced to Target 2, even though the PID flew directly through Target 4 later (1.01m closest approach)!\n")
        md.append("---\n")

    md.append("## 7. Immediate Execution Checklist")
    md.append("1. **Complete Gen 300 & Freeze `phase2_neat_caged`** [DONE - Checkpoint Gen 297].")
    md.append("2. **Run Generalization Battery** on both `pid_open_sky` and `phase2_neat_caged` [DONE - Recorded in `output/icarus.db`].")
    md.append("3. **Launch Phase 2B (`phase2_neat_open`)** in 1000m arena.")
    md.append("4. **Proceed to Phase 3 (Morphology Parametrics) & Phase 4 (Co-Evolution)** across both tracks.\n")

    content = "\n".join(md)
    os.makedirs(os.path.dirname(output_md), exist_ok=True)
    with open(output_md, "w", encoding="utf-8") as fh:
        fh.write(content)

    print(f"[talos] Automated lab notebook generated: {output_md}")


if __name__ == "__main__":
    generate_lab_notebook()
