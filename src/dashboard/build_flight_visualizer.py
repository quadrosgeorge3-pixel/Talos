"""build_flight_visualizer.py — Complete Flight Visualizer Generator for Project Talos.

Extracts all models and variations from output/icarus.db, populates dedicated manifest
and comparison matrix tables in icarus.db, and generates output/flight_visualizer.html.
"""
from __future__ import annotations

import json
import os
import sqlite3
from typing import Any, Dict, List, Optional

DB_PATH = "output/icarus.db"
OUTPUT_HTML = "output/flight_visualizer.html"

# Ground-truth morphology map for baseline & fixed-pilot phases (findings.md)
STATIC_MORPHOLOGIES: Dict[str, Dict[str, float]] = {
    "default": {
        "wingspan": 1.0,
        "wing_area": 0.30,
        "h_tail_area": 0.05,
        "v_tail_area": 0.05,
        "thrust_to_weight": 0.60,
        "total_mass": 1.20,
        "cg_x_offset": 0.00,
    },
    "p3a": {
        "wingspan": 3.0,
        "wing_area": 0.76,
        "h_tail_area": 0.07,
        "v_tail_area": 0.06,
        "thrust_to_weight": 1.50,
        "total_mass": 2.94,
        "cg_x_offset": -0.03,
    },
    "p3b_champ": {
        "wingspan": 3.0,
        "wing_area": 0.42,
        "h_tail_area": 0.09,
        "v_tail_area": 0.02,
        "thrust_to_weight": 1.50,
        "total_mass": 4.22,
        "cg_x_offset": -0.05,
    },
    "p3c_champ": {
        "wingspan": 1.8,
        "wing_area": 0.57,
        "h_tail_area": 0.22,
        "v_tail_area": 0.24,
        "thrust_to_weight": 1.49,
        "total_mass": 3.40,
        "cg_x_offset": 0.08,
    },
}

CATEGORIES = [
    {"id": "all", "label": "All Contenders"},
    {"id": "phase0", "label": "Phase 0 Baselines"},
    {"id": "phase1_2", "label": "Phases 1-2 Brain Evolution"},
    {"id": "phase3", "label": "Phase 3 Staged Body Evolution"},
    {"id": "testarossa", "label": "Phase 4 TESTAROSSA (Co-Evo)"},
    {"id": "ultima", "label": "Phase 4 ULTIMA (Apex Co-Evo)"},
]

CONTROLLER_METADATA: Dict[str, Dict[str, Any]] = {
    "pid_open_sky": {
        "name": "PID Open-Sky Baseline",
        "category": "phase0",
        "phase": "Phase 0",
        "is_best": 1,
        "is_latest": 1,
        "gen": 0,
        "pilot": "Cascaded PID",
        "body": "PyFlyt Default Fixed-Wing",
        "notes": "Hand-tuned cascaded PID baseline on default airframe. Stable cruise floor, zero autonomous gate tracking.",
    },
    "phase2_neat_caged": {
        "name": "Phase 2 Early NEAT Pilot",
        "category": "phase1_2",
        "phase": "Phase 1 (C1)",
        "is_best": 1,
        "is_latest": 1,
        "gen": 121,
        "pilot": "NEAT Gen 121",
        "body": "PyFlyt Default Fixed-Wing",
        "notes": "First neural pilot trained in 100m dome. Discovered fast dive-bomb speed exploit before terrain impact.",
    },
    "TALOS-P2B_gen300_champ": {
        "name": "TALOS-P2B Gen 300 Champion",
        "category": "phase1_2",
        "phase": "Phase 2B",
        "is_best": 1,
        "is_latest": 1,
        "gen": 300,
        "pilot": "NEAT Gen 300",
        "body": "PyFlyt Default Fixed-Wing",
        "notes": "Pure 300-gen evolved brain on default body. High navigation intelligence (3/4 gates) but fragile airframe dynamics.",
    },
    "p3a_champ_pid": {
        "name": "P3A Champion Body (PID Pilot)",
        "category": "phase3",
        "phase": "Phase 3A",
        "is_best": 0,
        "is_latest": 1,
        "gen": 100,
        "pilot": "Cascaded PID",
        "body": "P3A High-Lift Wing Airframe",
        "notes": "Max wing area (0.76 m²) glider body flown under PID control.",
    },
    "p3a_champ_neat_gen300": {
        "name": "P3A Champion Body (NEAT Gen 300)",
        "category": "phase3",
        "phase": "Phase 3A",
        "is_best": 1,
        "is_latest": 1,
        "gen": 100,
        "pilot": "NEAT Gen 300",
        "body": "P3A High-Lift Wing Airframe",
        "notes": "Evolved high-lift body paired with frozen NEAT Gen 300 brain.",
    },
    "p3b_gen054_pid": {
        "name": "P3B Mid-Run Gen 54 (PID Pilot)",
        "category": "phase3",
        "phase": "Phase 3B",
        "is_best": 0,
        "is_latest": 0,
        "gen": 54,
        "pilot": "Cascaded PID",
        "body": "P3B Gen 54 Intermediate Airframe",
        "notes": "Mid-evolution snapshot showing early acquisition of high-mass momentum.",
    },
    "p3b_gen054_neat_gen300": {
        "name": "P3B Mid-Run Gen 54 (NEAT Gen 300)",
        "category": "phase3",
        "phase": "Phase 3B",
        "is_best": 0,
        "is_latest": 0,
        "gen": 54,
        "pilot": "NEAT Gen 300",
        "body": "P3B Gen 54 Intermediate Airframe",
        "notes": "Heavy half-evolved body with aggressive neural pilot; high crash rate.",
    },
    "p3b_champ_pid": {
        "name": "P3B Champion Body (PID Pilot)",
        "category": "phase3",
        "phase": "Phase 3B",
        "is_best": 1,
        "is_latest": 1,
        "gen": 100,
        "pilot": "Cascaded PID",
        "body": "P3B Max-Wingspan Sailplane (4.2kg)",
        "notes": "Brute-force distance champion under PID (1,018m no-crash record, 47.9 m/s cruise).",
    },
    "p3b_champ_neat_gen300": {
        "name": "P3B Champion Body (NEAT Gen 300)",
        "category": "phase3",
        "phase": "Phase 3B",
        "is_best": 0,
        "is_latest": 1,
        "gen": 100,
        "pilot": "NEAT Gen 300",
        "body": "P3B Max-Wingspan Sailplane (4.2kg)",
        "notes": "Extreme inertia fights neural pilot quick corrections, leading to fast stall crashes.",
    },
    "p3c_champ_pid": {
        "name": "P3C Champion Body (PID Pilot)",
        "category": "phase3",
        "phase": "Phase 3C",
        "is_best": 0,
        "is_latest": 1,
        "gen": 100,
        "pilot": "Cascaded PID",
        "body": "P3C Massive Tail Airframe",
        "notes": "Oversized tail surfaces provide self-stabilizing flight even under simple PID.",
    },
    "p3c_champ_neat_gen300": {
        "name": "P3C Co-Design Champion (NEAT Gen 300)",
        "category": "phase3",
        "phase": "Phase 3C",
        "is_best": 1,
        "is_latest": 1,
        "gen": 100,
        "pilot": "NEAT Gen 300",
        "body": "P3C Massive Tail Airframe",
        "notes": "All-time speed & distance record holder: 1,229m at 49.2 m/s on Test B. Oversized tail surfaces damp neural erratic turns.",
    },
    "TALOS-P4-TESTAROSSA_gen352": {
        "name": "TESTAROSSA Gen 352 (Agile Sweeper)",
        "category": "testarossa",
        "phase": "Phase 4 Co-Evo",
        "is_best": 1,
        "is_latest": 0,
        "gen": 352,
        "pilot": "NEAT Co-Evolved Gen 352",
        "body": "Aft-CG High-Lift Sweeper",
        "notes": "Project standout: ONLY neural UAV to achieve clean 4/4 on Test B AND 4/4 on Test C with zero crashes (32.1 m/s, 717m).",
    },
    "TALOS-P4-TESTAROSSA_gen370": {
        "name": "TESTAROSSA Gen 370 (High-Speed Racer)",
        "category": "testarossa",
        "phase": "Phase 4 Co-Evo",
        "is_best": 0,
        "is_latest": 0,
        "gen": 370,
        "pilot": "NEAT Co-Evolved Gen 370",
        "body": "1.72m Wingspan / 1.20 T/W",
        "notes": "High sprint velocity (45.3 m/s on Test B, 3/5 on Test D) before terminal overspeed.",
    },
    "TALOS-P4-TESTAROSSA_gen398": {
        "name": "TESTAROSSA Gen 398 (Stable Sweeper)",
        "category": "testarossa",
        "phase": "Phase 4 Co-Evo",
        "is_best": 0,
        "is_latest": 0,
        "gen": 398,
        "pilot": "NEAT Co-Evolved Gen 398",
        "body": "Aft-CG High-Lift Sweeper",
        "notes": "Stable continuation retaining Gen 352's 4/4 gate capture morphology.",
    },
    "TALOS-P4-TESTAROSSA_gen424": {
        "name": "TESTAROSSA Gen 424 (Latest Dedicated)",
        "category": "testarossa",
        "phase": "Phase 4 Co-Evo",
        "is_best": 0,
        "is_latest": 1,
        "gen": 424,
        "pilot": "NEAT Co-Evolved Gen 424",
        "body": "Lightweight Glider (1.6kg / 0.5 T/W)",
        "notes": "Final dedicated checkpoint of 100-gen run. Outstanding calm cruise stability (93.5 score on Test A, 0 crashes across A-D).",
    },
    "TALOS-P4-ULTIMA_tier2": {
        "name": "ULTIMA Tier 2 Baseline (Gen 60)",
        "category": "ultima",
        "phase": "Phase 4 ULTIMA",
        "is_best": 0,
        "is_latest": 0,
        "gen": 60,
        "pilot": "NEAT Co-Evolved Gen 60",
        "body": "3.0m Max-Span Heavy Frame",
        "notes": "End of Tier 1 viability curriculum. High speed sprint (59.9 m/s, 4/4 gates) before aggressive turn crash.",
    },
    "TALOS-P4-ULTIMA_gen360_pre_hairpin": {
        "name": "ULTIMA Gen 360 (Pre-Hairpin Sprint)",
        "category": "ultima",
        "phase": "Phase 4 ULTIMA",
        "is_best": 0,
        "is_latest": 0,
        "gen": 360,
        "pilot": "NEAT Co-Evolved Gen 360",
        "body": "3.0m Max-Span Frame",
        "notes": "Extreme straightaway sprint velocity (56.8 m/s on Test B, 61.3 m/s on Test E).",
    },
    "TALOS-P4-ULTIMA_gen375_hairpin": {
        "name": "ULTIMA Gen 375 (Hairpin Master)",
        "category": "ultima",
        "phase": "Phase 4 ULTIMA",
        "is_best": 1,
        "is_latest": 0,
        "gen": 375,
        "pilot": "NEAT Co-Evolved Gen 375",
        "body": "Forward-CG Restored Fin (2.15m span)",
        "notes": "Peak overall precision champion: 91.3 score on Test B (4/4 clean), 88.5 on Test C (4/4 clean), and 7/9 on Test E pylon race.",
    },
    "TALOS-P4-ULTIMA_gen382_hairpin": {
        "name": "ULTIMA Gen 382 Snapshot",
        "category": "ultima",
        "phase": "Phase 4 ULTIMA",
        "is_best": 0,
        "is_latest": 0,
        "gen": 382,
        "pilot": "NEAT Co-Evolved Gen 382",
        "body": "1.88m Span Lightweight Frame",
        "notes": "Intermediate hairpin generation.",
    },
    "TALOS-P4-ULTIMA_gen384_hairpin": {
        "name": "ULTIMA Gen 384 Snapshot",
        "category": "ultima",
        "phase": "Phase 4 ULTIMA",
        "is_best": 0,
        "is_latest": 0,
        "gen": 384,
        "pilot": "NEAT Co-Evolved Gen 384",
        "body": "2.20m Span Frame",
        "notes": "Hairpin tier snapshot transitioning into autonomous control.",
    },
    "TALOS-P4-ULTIMA_gen385_hairpin": {
        "name": "ULTIMA Gen 385 Snapshot",
        "category": "ultima",
        "phase": "Phase 4 ULTIMA",
        "is_best": 0,
        "is_latest": 0,
        "gen": 385,
        "pilot": "NEAT Co-Evolved Gen 385",
        "body": "1.73m Span Compact Airframe",
        "notes": "Maintains 3/4 waypoints on Test B and 4/9 on Test E.",
    },
    "TALOS-P4-ULTIMA_gen388_auto": {
        "name": "ULTIMA Gen 388 Snapshot",
        "category": "ultima",
        "phase": "Phase 4 ULTIMA",
        "is_best": 0,
        "is_latest": 0,
        "gen": 388,
        "pilot": "NEAT Co-Evolved Gen 388",
        "body": "2.20m Span Frame",
        "notes": "Autonomous checkpoint benchmark.",
    },
    "TALOS-P4-ULTIMA_gen390_auto": {
        "name": "ULTIMA Gen 390 Snapshot",
        "category": "ultima",
        "phase": "Phase 4 ULTIMA",
        "is_best": 0,
        "is_latest": 0,
        "gen": 390,
        "pilot": "NEAT Co-Evolved Gen 390",
        "body": "2.18m Span Frame",
        "notes": "Autonomous checkpoint benchmark.",
    },
    "TALOS-P4-ULTIMA_gen392_auto": {
        "name": "ULTIMA Gen 392 Snapshot",
        "category": "ultima",
        "phase": "Phase 4 ULTIMA",
        "is_best": 0,
        "is_latest": 0,
        "gen": 392,
        "pilot": "NEAT Co-Evolved Gen 392",
        "body": "1.69m Span Frame",
        "notes": "Autonomous checkpoint benchmark.",
    },
    "TALOS-P4-ULTIMA_gen394_auto": {
        "name": "ULTIMA Gen 394 (High-Speed Auto)",
        "category": "ultima",
        "phase": "Phase 4 ULTIMA",
        "is_best": 0,
        "is_latest": 0,
        "gen": 394,
        "pilot": "NEAT Co-Evolved Gen 394",
        "body": "1.86m Span High-Speed Frame",
        "notes": "Clean 4/4 on Test B at 34.3 m/s and 7/9 on Test E at 35.5 m/s (1,420m total distance).",
    },
    "TALOS-P4-ULTIMA_gen411_auto": {
        "name": "ULTIMA Gen 411 (Peak Fitness)",
        "category": "ultima",
        "phase": "Phase 4 ULTIMA",
        "is_best": 1,
        "is_latest": 0,
        "gen": 411,
        "pilot": "NEAT Co-Evolved Gen 411",
        "body": "2.20m Span Frame",
        "notes": "All-time highest logged co-evolution scalar fitness (445.48) in ULTIMA database.",
    },
    "TALOS-P4-ULTIMA_gen417_auto": {
        "name": "ULTIMA Gen 417 Snapshot",
        "category": "ultima",
        "phase": "Phase 4 ULTIMA",
        "is_best": 0,
        "is_latest": 0,
        "gen": 417,
        "pilot": "NEAT Co-Evolved Gen 417",
        "body": "2.19m Span Frame",
        "notes": "Late-stage co-evolution snapshot.",
    },
    "TALOS-P4-ULTIMA_gen420_auto": {
        "name": "ULTIMA Gen 420 Snapshot",
        "category": "ultima",
        "phase": "Phase 4 ULTIMA",
        "is_best": 0,
        "is_latest": 0,
        "gen": 420,
        "pilot": "NEAT Co-Evolved Gen 420",
        "body": "1.54m Span Frame",
        "notes": "Late-stage co-evolution snapshot.",
    },
    "TALOS-P4-ULTIMA_gen425_auto": {
        "name": "ULTIMA Gen 425 Snapshot",
        "category": "ultima",
        "phase": "Phase 4 ULTIMA",
        "is_best": 0,
        "is_latest": 1,
        "gen": 425,
        "pilot": "NEAT Co-Evolved Gen 425",
        "body": "1.99m Span Frame",
        "notes": "Latest evaluated generation of the main ULTIMA lineage.",
    },
}


def populate_database_tables(con: sqlite3.Connection) -> None:
    """Create and populate visualizer manifest and comparison matrix tables."""
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS visualizer_manifest (
            controller_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            experiment_id TEXT,
            phase TEXT,
            is_best INTEGER DEFAULT 0,
            is_latest INTEGER DEFAULT 0,
            gen INTEGER,
            wingspan REAL,
            wing_area REAL,
            h_tail_area REAL,
            v_tail_area REAL,
            thrust_to_weight REAL,
            total_mass REAL,
            cg_x_offset REAL,
            morphology_json TEXT,
            controller_json TEXT,
            notes TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS visualizer_comparison_matrix (
            test_code TEXT NOT NULL,
            test_name TEXT NOT NULL,
            controller_id TEXT NOT NULL,
            display_name TEXT NOT NULL,
            category TEXT NOT NULL,
            gen INTEGER,
            is_best INTEGER DEFAULT 0,
            is_latest INTEGER DEFAULT 0,
            flight_time REAL,
            distance REAL,
            mean_airspeed REAL,
            waypoints_hit INTEGER,
            num_waypoints INTEGER,
            crashed INTEGER,
            precision_score REAL,
            PRIMARY KEY (test_code, controller_id)
        )
    """)

    cur.execute("DELETE FROM visualizer_manifest")
    cur.execute("DELETE FROM visualizer_comparison_matrix")

    # Helper to resolve morphology & controller JSON
    def resolve_morph(cid: str) -> Dict[str, float]:
        if cid in ["pid_open_sky", "phase2_neat_caged", "TALOS-P2B_gen300_champ"]:
            return STATIC_MORPHOLOGIES["default"]
        if "p3a_" in cid:
            return STATIC_MORPHOLOGIES["p3a"]
        if "p3b_champ" in cid:
            return STATIC_MORPHOLOGIES["p3b_champ"]
        if "p3b_gen054" in cid:
            cur.execute("SELECT morphology_json FROM individuals WHERE experiment_id='TALOS-P3B' AND generation=54")
            r = cur.fetchone()
            if r and r[0]: return json.loads(r[0])
            return STATIC_MORPHOLOGIES["p3b_champ"]
        if "p3c_" in cid:
            return STATIC_MORPHOLOGIES["p3c_champ"]
        if "TESTAROSSA" in cid:
            meta = CONTROLLER_METADATA.get(cid, {})
            gen = meta.get("gen", 352)
            cur.execute("SELECT morphology_json FROM individuals WHERE experiment_id='TALOS-P4-TESTAROSSA' AND generation=?", (gen,))
            r = cur.fetchone()
            if r and r[0]: return json.loads(r[0])
        if "ULTIMA" in cid:
            meta = CONTROLLER_METADATA.get(cid, {})
            gen = meta.get("gen", 375)
            cur.execute("SELECT morphology_json FROM individuals WHERE experiment_id='TALOS-P4-ULTIMA' AND generation=?", (gen,))
            r = cur.fetchone()
            if r and r[0]: return json.loads(r[0])
        return STATIC_MORPHOLOGIES["default"]

    def resolve_ctrl(cid: str) -> Optional[str]:
        if "pid" in cid.lower():
            return None
        if cid == "phase2_neat_caged":
            cur.execute("SELECT controller_json FROM individuals WHERE experiment_id='C1' AND is_elite=1 ORDER BY generation DESC LIMIT 1")
            r = cur.fetchone()
            return r[0] if r else None
        if "gen300" in cid or cid == "TALOS-P2B_gen300_champ":
            cur.execute("SELECT controller_json FROM individuals WHERE experiment_id='TALOS-P2B' AND is_elite=1 ORDER BY generation DESC LIMIT 1")
            r = cur.fetchone()
            return r[0] if r else None
        if "TESTAROSSA" in cid:
            meta = CONTROLLER_METADATA.get(cid, {})
            gen = meta.get("gen", 352)
            cur.execute("SELECT controller_json FROM individuals WHERE experiment_id='TALOS-P4-TESTAROSSA' AND generation=?", (gen,))
            r = cur.fetchone()
            return r[0] if r else None
        if "ULTIMA" in cid:
            meta = CONTROLLER_METADATA.get(cid, {})
            gen = meta.get("gen", 375)
            cur.execute("SELECT controller_json FROM individuals WHERE experiment_id='TALOS-P4-ULTIMA' AND generation=?", (gen,))
            r = cur.fetchone()
            return r[0] if r else None
        return None

    # Populate Manifest
    for cid, meta in CONTROLLER_METADATA.items():
        morph = resolve_morph(cid)
        ctrl_json = resolve_ctrl(cid)
        cur.execute("""
            INSERT OR REPLACE INTO visualizer_manifest (
                controller_id, name, category, experiment_id, phase,
                is_best, is_latest, gen, wingspan, wing_area, h_tail_area,
                v_tail_area, thrust_to_weight, total_mass, cg_x_offset,
                morphology_json, controller_json, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cid, meta["name"], meta["category"], meta.get("phase", ""), meta.get("phase", ""),
            meta["is_best"], meta["is_latest"], meta["gen"],
            float(morph.get("wingspan", 1.0)), float(morph.get("wing_area", 0.3)),
            float(morph.get("h_tail_area", 0.05)), float(morph.get("v_tail_area", 0.05)),
            float(morph.get("thrust_to_weight", 0.6)), float(morph.get("total_mass", 1.2)),
            float(morph.get("cg_x_offset", 0.0)), json.dumps(morph), ctrl_json, meta.get("notes", "")
        ))

    # Populate Comparison Matrix from benchmark_evaluations
    test_code_map = {
        "Test A - Open-Sky Straight Flight": "A",
        "Test A - Open-Sky Straight Flight (1 km)": "A",
        "Test B - Open-Sky Waypoint Course": "B",
        "Test C - Aggressive Aero Slalom": "C",
        "Test D - AUVSI SUAS Autonomous Challenge": "D",
        "Test E - FAI F3D/F5D Pylon Racing": "E",
    }
    wp_counts = {"A": 0, "B": 4, "C": 4, "D": 5, "E": 9}

    cur.execute("""
        SELECT test_name, controller_id, flight_time, distance, mean_airspeed,
               waypoints_hit, crashed, precision_score
        FROM benchmark_evaluations
        ORDER BY id DESC
    """)
    eval_rows = cur.fetchall()

    seen_pairs = set()
    for row in eval_rows:
        t_name, cid, f_time, dist, spd, wp_hit, crash, prec = row
        t_code = test_code_map.get(t_name)
        if not t_code:
            continue
        pair_key = (t_code, cid)
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)

        meta = CONTROLLER_METADATA.get(cid, {
            "name": cid, "category": "other", "gen": 0, "is_best": 0, "is_latest": 0
        })

        cur.execute("""
            INSERT OR REPLACE INTO visualizer_comparison_matrix (
                test_code, test_name, controller_id, display_name, category,
                gen, is_best, is_latest, flight_time, distance, mean_airspeed,
                waypoints_hit, num_waypoints, crashed, precision_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            t_code, t_name, cid, meta.get("name", cid), meta.get("category", "other"),
            meta.get("gen", 0), meta.get("is_best", 0), meta.get("is_latest", 0),
            round(float(f_time or 0.0), 1), round(float(dist or 0.0), 1),
            round(float(spd or 0.0), 1), int(wp_hit or 0), wp_counts.get(t_code, 0),
            int(crash or 0), float(prec) if prec is not None else None
        ))

    con.commit()
    print("[talos] Database tables visualizer_manifest and visualizer_comparison_matrix populated.")


def generate_visualizer_html(con: sqlite3.Connection) -> None:
    """Generate self-contained interactive flight visualizer HTML."""
    cur = con.cursor()

    # Load all controllers with benchmark evaluations
    cur.execute("""
        SELECT b.id, b.test_name, b.controller_id, b.controller_type, b.flight_time,
               b.distance, b.mean_airspeed, b.mean_altitude, b.max_lateral_dev,
               b.control_energy, b.crashed, b.stalling, b.waypoints_hit,
               b.precision_score, b.arena_radius, b.waypoint_radius,
               b.course_map_json, b.trajectory_json,
               m.name, m.category, m.phase, m.is_best, m.is_latest, m.gen,
               m.wingspan, m.wing_area, m.h_tail_area, m.v_tail_area,
               m.thrust_to_weight, m.total_mass, m.cg_x_offset,
               m.morphology_json, m.controller_json, m.notes
        FROM benchmark_evaluations b
        LEFT JOIN visualizer_manifest m ON b.controller_id = m.controller_id
        ORDER BY b.test_name, b.controller_id
    """)
    rows = cur.fetchall()

    test_code_map = {
        "Test A - Open-Sky Straight Flight": "A",
        "Test A - Open-Sky Straight Flight (1 km)": "A",
        "Test B - Open-Sky Waypoint Course": "B",
        "Test C - Aggressive Aero Slalom": "C",
        "Test D - AUVSI SUAS Autonomous Challenge": "D",
        "Test E - FAI F3D/F5D Pylon Racing": "E",
    }

    runs_data = []
    seen_runs = set()

    for r in rows:
        (b_id, t_name, c_id, c_type, f_time, dist, spd, alt, lat_dev, energy,
         crash, stall, wp_hit, prec, arena_r, wp_r, course_json, traj_json,
         m_name, m_cat, m_phase, is_best, is_latest, gen,
         wspan, warea, htarea, vtarea, tw, mass, cg,
         morph_json, ctrl_json, notes) = r

        t_code = test_code_map.get(t_name, "A")
        dedup_key = (t_code, c_id)
        if dedup_key in seen_runs:
            continue
        seen_runs.add(dedup_key)

        traj = json.loads(traj_json) if traj_json else []
        course = json.loads(course_json) if course_json else []
        morph = json.loads(morph_json) if morph_json else {}
        ctrl = json.loads(ctrl_json) if ctrl_json else None

        # Fallback if manifest didn't match directly
        disp_name = m_name or CONTROLLER_METADATA.get(c_id, {}).get("name", c_id)
        cat = m_cat or CONTROLLER_METADATA.get(c_id, {}).get("category", "other")
        is_b = is_best if is_best is not None else CONTROLLER_METADATA.get(c_id, {}).get("is_best", 0)
        is_l = is_latest if is_latest is not None else CONTROLLER_METADATA.get(c_id, {}).get("is_latest", 0)
        g_num = gen if gen is not None else CONTROLLER_METADATA.get(c_id, {}).get("gen", 0)

        runs_data.append({
            "id": b_id,
            "test_code": t_code,
            "test_name": t_name,
            "controller_id": c_id,
            "controller_type": c_type,
            "name": disp_name,
            "category": cat,
            "is_best": bool(is_b),
            "is_latest": bool(is_l),
            "gen": g_num,
            "flight_time": round(float(f_time or 0.0), 1),
            "distance": round(float(dist or 0.0), 1),
            "mean_airspeed": round(float(spd or 0.0), 1),
            "mean_altitude": round(float(alt or 0.0), 1),
            "max_lateral_dev": round(float(lat_dev or 0.0), 1),
            "control_energy": round(float(energy or 0.0), 1),
            "crashed": bool(crash),
            "stalling": bool(stall),
            "waypoints_hit": int(wp_hit or 0),
            "precision_score": round(float(prec), 1) if prec is not None else None,
            "arena_radius": float(arena_r or 1000.0),
            "waypoint_radius": float(wp_r or 2.0),
            "morphology": morph or STATIC_MORPHOLOGIES["default"],
            "controller": ctrl,
            "notes": notes or CONTROLLER_METADATA.get(c_id, {}).get("notes", ""),
            "course": course,
            "trajectory": traj,
        })

    # Fetch Best vs Latest Comparison Matrix Rows
    cur.execute("""
        SELECT test_code, test_name, controller_id, display_name, category,
               gen, is_best, is_latest, flight_time, distance, mean_airspeed,
               waypoints_hit, num_waypoints, crashed, precision_score
        FROM visualizer_comparison_matrix
        ORDER BY test_code, is_best DESC, precision_score DESC
    """)
    matrix_rows = []
    for mr in cur.fetchall():
        matrix_rows.append({
            "test_code": mr[0],
            "test_name": mr[1],
            "controller_id": mr[2],
            "display_name": mr[3],
            "category": mr[4],
            "gen": mr[5],
            "is_best": bool(mr[6]),
            "is_latest": bool(mr[7]),
            "flight_time": mr[8],
            "distance": mr[9],
            "mean_airspeed": mr[10],
            "waypoints_hit": mr[11],
            "num_waypoints": mr[12],
            "crashed": bool(mr[13]),
            "precision_score": mr[14],
        })

    runs_json = json.dumps(runs_data, indent=None)
    matrix_json = json.dumps(matrix_rows, indent=None)
    categories_json = json.dumps(CATEGORIES, indent=None)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Project TALOS — Universal 3D Flight & Morphology Visualizer</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
  <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
  <style>
    :root {{
      --bg-dark: #07090e;
      --panel-bg: rgba(13, 17, 26, 0.92);
      --panel-border: rgba(255, 255, 255, 0.12);
      --text-main: #f1f5f9;
      --text-dim: #94a3b8;
      --cyan: #00f0ff;
      --cyan-glow: rgba(0, 240, 255, 0.4);
      --magenta: #ff0055;
      --emerald: #10b981;
      --gold: #fbbf24;
      --purple: #c084fc;
      --amber: #f59e0b;
      --blue: #3b82f6;
    }}

    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      background-color: var(--bg-dark);
      color: var(--text-main);
      font-family: 'Inter', -apple-system, sans-serif;
      overflow: hidden;
      width: 100vw;
      height: 100vh;
      user-select: none;
    }}

    #canvas-container {{
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      z-index: 1;
    }}

    /* Top Floating Header & Filter Navigation */
    .top-nav-bar {{
      position: absolute;
      top: 14px;
      left: 20px;
      right: 20px;
      z-index: 20;
      display: flex;
      align-items: center;
      gap: 12px;
      pointer-events: none;
      flex-wrap: nowrap;
      overflow-x: auto;
      padding-bottom: 4px;
    }}
    .top-nav-bar > * {{ pointer-events: auto; flex-shrink: 0; }}
    .top-nav-bar::-webkit-scrollbar {{ height: 4px; }}
    .top-nav-bar::-webkit-scrollbar-thumb {{ background: rgba(255,255,255,0.2); border-radius: 4px; }}

    .brand-pill {{
      background: var(--panel-bg);
      backdrop-filter: blur(16px);
      border: 1px solid var(--panel-border);
      border-radius: 9999px;
      padding: 8px 18px;
      display: flex;
      align-items: center;
      gap: 10px;
      box-shadow: 0 10px 25px -5px rgba(0,0,0,0.6);
    }}
    .brand-dot {{
      width: 10px;
      height: 10px;
      background: var(--cyan);
      border-radius: 50%;
      box-shadow: 0 0 10px var(--cyan);
    }}
    .brand-title {{
      font-size: 13px;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      background: linear-gradient(90deg, #fff, var(--cyan));
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }}

    .selector-pill {{
      background: var(--panel-bg);
      backdrop-filter: blur(16px);
      border: 1px solid var(--panel-border);
      border-radius: 9999px;
      padding: 6px 14px;
      display: flex;
      align-items: center;
      gap: 8px;
      box-shadow: 0 10px 25px -5px rgba(0,0,0,0.6);
    }}
    .sel-label {{
      font-size: 10px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--cyan);
    }}
    .custom-select {{
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(255,255,255,0.15);
      color: #fff;
      font-size: 11px;
      font-weight: 600;
      padding: 4px 10px;
      border-radius: 8px;
      outline: none;
      cursor: pointer;
      font-family: inherit;
      max-width: 260px;
    }}
    .custom-select option, .custom-select optgroup {{
      background: #0d111a;
      color: #f1f5f9;
    }}

    .filter-btn-group {{
      display: flex;
      gap: 4px;
      background: var(--panel-bg);
      backdrop-filter: blur(16px);
      border: 1px solid var(--panel-border);
      border-radius: 9999px;
      padding: 4px;
      box-shadow: 0 10px 25px -5px rgba(0,0,0,0.6);
    }}
    .filter-btn {{
      background: transparent;
      border: none;
      color: var(--text-dim);
      padding: 5px 12px;
      border-radius: 9999px;
      font-size: 11px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
      white-space: nowrap;
      font-family: inherit;
    }}
    .filter-btn:hover {{
      color: #fff;
      background: rgba(255, 255, 255, 0.08);
    }}
    .filter-btn.active {{
      background: linear-gradient(135deg, rgba(0, 240, 255, 0.25), rgba(0, 240, 255, 0.08));
      color: var(--cyan);
      border: 1px solid rgba(0, 240, 255, 0.5);
      box-shadow: 0 0 12px var(--cyan-glow);
    }}
    .filter-btn.special-active {{
      background: linear-gradient(135deg, rgba(251, 191, 36, 0.3), rgba(251, 191, 36, 0.1));
      color: #fbbf24;
      border: 1px solid rgba(251, 191, 36, 0.5);
      box-shadow: 0 0 12px rgba(251, 191, 36, 0.3);
    }}

    .matrix-toggle-btn {{
      background: linear-gradient(135deg, rgba(192, 132, 252, 0.25), rgba(192, 132, 252, 0.08));
      border: 1px solid rgba(192, 132, 252, 0.4);
      color: var(--purple);
      padding: 6px 14px;
      border-radius: 9999px;
      font-size: 11px;
      font-weight: 700;
      cursor: pointer;
      transition: all 0.2s;
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .matrix-toggle-btn:hover {{
      background: rgba(192, 132, 252, 0.35);
      box-shadow: 0 0 12px rgba(192, 132, 252, 0.4);
      color: #fff;
    }}

    /* Left Drawer: Telemetry & Flight Stats */
    .telemetry-card {{
      position: absolute;
      top: 76px;
      left: 20px;
      width: 320px;
      background: var(--panel-bg);
      backdrop-filter: blur(16px);
      border: 1px solid var(--panel-border);
      border-radius: 16px;
      padding: 16px;
      z-index: 15;
      box-shadow: 0 20px 40px -10px rgba(0,0,0,0.7);
      display: flex;
      flex-direction: column;
      gap: 12px;
      pointer-events: auto;
      max-height: calc(100vh - 160px);
      overflow-y: auto;
    }}
    .telemetry-card::-webkit-scrollbar {{ width: 4px; }}
    .telemetry-card::-webkit-scrollbar-thumb {{ background: rgba(255,255,255,0.2); border-radius: 4px; }}

    .card-header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      border-bottom: 1px solid rgba(255,255,255,0.08);
      padding-bottom: 10px;
    }}
    .contender-name {{
      font-size: 14px;
      font-weight: 800;
      color: #fff;
      line-height: 1.3;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      padding: 2px 8px;
      border-radius: 9999px;
      font-size: 10px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    .badge-best {{ background: rgba(16, 185, 129, 0.2); color: var(--emerald); border: 1px solid rgba(16, 185, 129, 0.4); }}
    .badge-latest {{ background: rgba(245, 158, 11, 0.2); color: var(--amber); border: 1px solid rgba(245, 158, 11, 0.4); }}
    .badge-gen {{ background: rgba(59, 130, 246, 0.2); color: var(--blue); border: 1px solid rgba(59, 130, 246, 0.4); }}

    .stat-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
    }}
    .stat-box {{
      background: rgba(255,255,255,0.03);
      border: 1px solid rgba(255,255,255,0.06);
      border-radius: 10px;
      padding: 8px 10px;
    }}
    .stat-title {{
      font-size: 10px;
      color: var(--text-dim);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 4px;
    }}
    .stat-val {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 15px;
      font-weight: 700;
      color: #fff;
    }}
    .stat-sub {{ font-size: 10px; color: var(--text-dim); font-weight: 400; }}

    /* Live Telemetry HUD Bar */
    .hud-gauge-bar {{
      background: rgba(0,0,0,0.4);
      border-radius: 6px;
      height: 6px;
      width: 100%;
      overflow: hidden;
      margin-top: 4px;
    }}
    .hud-gauge-fill {{
      height: 100%;
      background: linear-gradient(90deg, var(--cyan), var(--emerald));
      width: 0%;
      transition: width 0.1s linear;
    }}

    /* Right Drawer: Morphology & NN Topology */
    .details-card {{
      position: absolute;
      top: 76px;
      right: 20px;
      width: 360px;
      background: var(--panel-bg);
      backdrop-filter: blur(16px);
      border: 1px solid var(--panel-border);
      border-radius: 16px;
      padding: 16px;
      z-index: 15;
      box-shadow: 0 20px 40px -10px rgba(0,0,0,0.7);
      display: flex;
      flex-direction: column;
      gap: 12px;
      pointer-events: auto;
      max-height: calc(100vh - 160px);
      overflow-y: auto;
    }}
    .details-card::-webkit-scrollbar {{ width: 4px; }}
    .details-card::-webkit-scrollbar-thumb {{ background: rgba(255,255,255,0.2); border-radius: 4px; }}

    .section-title {{
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--cyan);
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid rgba(255,255,255,0.08);
      padding-bottom: 6px;
    }}

    /* Morphology Blueprint Diagram SVG */
    #morphology-svg-container {{
      width: 100%;
      height: 130px;
      background: rgba(0, 0, 0, 0.4);
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 10px;
      position: relative;
      display: flex;
      align-items: center;
      justify-content: center;
    }}

    /* NN Interactive Topology Visualizer Canvas */
    #nn-canvas-container {{
      width: 100%;
      height: 160px;
      background: rgba(0, 0, 0, 0.4);
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 10px;
      position: relative;
      overflow: hidden;
    }}
    #nn-canvas {{
      width: 100%;
      height: 100%;
      display: block;
    }}

    /* Bottom Playback HUD Bar */
    .playback-hud {{
      position: absolute;
      bottom: 18px;
      left: 50%;
      transform: translateX(-50%);
      width: 580px;
      max-width: calc(100vw - 40px);
      background: var(--panel-bg);
      backdrop-filter: blur(16px);
      border: 1px solid var(--panel-border);
      border-radius: 9999px;
      padding: 8px 18px;
      z-index: 20;
      display: flex;
      align-items: center;
      gap: 14px;
      box-shadow: 0 15px 35px -5px rgba(0,0,0,0.7);
    }}
    .playback-btn {{
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid rgba(255, 255, 255, 0.15);
      color: #fff;
      width: 32px;
      height: 32px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      font-size: 12px;
      transition: all 0.2s;
    }}
    .playback-btn:hover {{
      background: var(--cyan);
      color: #000;
      box-shadow: 0 0 10px var(--cyan-glow);
    }}
    .hud-time {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px;
      color: var(--cyan);
      min-width: 68px;
    }}
    .time-slider {{
      flex: 1;
      height: 6px;
      -webkit-appearance: none;
      background: rgba(255, 255, 255, 0.15);
      border-radius: 3px;
      outline: none;
      cursor: pointer;
    }}
    .time-slider::-webkit-slider-thumb {{
      -webkit-appearance: none;
      width: 14px;
      height: 14px;
      border-radius: 50%;
      background: var(--cyan);
      box-shadow: 0 0 8px var(--cyan);
      cursor: pointer;
    }}

    /* Modal: Best vs Latest Comparison Matrix */
    .modal-overlay {{
      position: fixed;
      top: 0;
      left: 0;
      width: 100vw;
      height: 100vh;
      background: rgba(0, 0, 0, 0.8);
      backdrop-filter: blur(10px);
      z-index: 100;
      display: none;
      align-items: center;
      justify-content: center;
      padding: 30px;
    }}
    .modal-overlay.active {{ display: flex; }}

    .modal-box {{
      background: #0d111a;
      border: 1px solid rgba(255,255,255,0.15);
      border-radius: 20px;
      width: 90vw;
      max-width: 1100px;
      max-height: 85vh;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      box-shadow: 0 25px 50px -12px rgba(0,0,0,0.9);
    }}
    .modal-header {{
      padding: 18px 24px;
      border-bottom: 1px solid rgba(255,255,255,0.1);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .modal-title {{
      font-size: 16px;
      font-weight: 800;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .modal-close-btn {{
      background: rgba(255,255,255,0.08);
      border: 1px solid rgba(255,255,255,0.2);
      color: #fff;
      width: 32px;
      height: 32px;
      border-radius: 50%;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
    }}
    .modal-close-btn:hover {{ background: rgba(255,0,85,0.4); border-color: var(--magenta); }}

    .matrix-table-wrap {{
      overflow: auto;
      flex: 1;
      padding: 16px 24px;
    }}
    .matrix-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
      text-align: left;
    }}
    .matrix-table th {{
      padding: 10px 12px;
      background: rgba(255,255,255,0.03);
      color: var(--text-dim);
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      border-bottom: 1px solid rgba(255,255,255,0.1);
      position: sticky;
      top: 0;
    }}
    .matrix-table td {{
      padding: 10px 12px;
      border-bottom: 1px solid rgba(255,255,255,0.05);
      color: var(--text-main);
    }}
    .matrix-table tr:hover td {{
      background: rgba(0, 240, 255, 0.04);
    }}
    .matrix-row-best {{
      background: rgba(16, 185, 129, 0.05);
    }}
    .matrix-row-latest {{
      background: rgba(245, 158, 11, 0.05);
    }}
    .badge-win {{
      color: var(--emerald);
      font-weight: 700;
    }}
    .badge-crash {{
      color: var(--magenta);
      font-weight: 700;
    }}
  </style>
</head>
<body>

  <!-- 3D Three.js WebGL Arena Canvas -->
  <div id="canvas-container"></div>

  <!-- Top Floating Header & Filter Navigation -->
  <div class="top-nav-bar">
    <div class="brand-pill">
      <div class="brand-dot"></div>
      <span class="brand-title">TALOS 3D FLIGHT ARENA</span>
    </div>

    <!-- Category Filter Pills -->
    <div class="filter-btn-group" id="category-filters"></div>

    <!-- Test Course Selector -->
    <div class="selector-pill">
      <span class="sel-label">Course:</span>
      <select id="test-course-select" class="custom-select">
        <option value="A">Test A — Calm Straight Cruise</option>
        <option value="B" selected>Test B — Open-Sky Waypoint Course</option>
        <option value="C">Test C — Aggressive Aero Slalom</option>
        <option value="D">Test D — AUVSI SUAS Challenge</option>
        <option value="E">Test E — FAI Pylon Racing</option>
      </select>
    </div>

    <!-- Model / Aircraft Variation Dropdown -->
    <div class="selector-pill">
      <span class="sel-label">Aircraft:</span>
      <select id="aircraft-select" class="custom-select"></select>
    </div>

    <!-- Best vs Latest Comparison Matrix Button -->
    <button class="matrix-toggle-btn" id="open-matrix-btn">
      <span>📊</span> Best vs Latest Matrix
    </button>
  </div>

  <!-- Left Drawer: Telemetry & Flight Stats -->
  <div class="telemetry-card" id="telemetry-card">
    <div class="card-header">
      <div>
        <div class="contender-name" id="card-aircraft-name">Loading...</div>
        <div style="display:flex; gap:6px; margin-top:6px;">
          <span class="badge" id="badge-status">BEST</span>
          <span class="badge badge-gen" id="badge-gen">GEN 352</span>
          <span class="badge" id="badge-crash">SURVIVED</span>
        </div>
      </div>
    </div>

    <!-- Stat Grid -->
    <div class="stat-grid">
      <div class="stat-box">
        <div class="stat-title">Airspeed</div>
        <div class="stat-val"><span id="val-speed">0.0</span> <span class="stat-sub">m/s</span></div>
        <div class="hud-gauge-bar"><div class="hud-gauge-fill" id="bar-speed"></div></div>
      </div>
      <div class="stat-box">
        <div class="stat-title">Altitude</div>
        <div class="stat-val"><span id="val-alt">0.0</span> <span class="stat-sub">m</span></div>
        <div class="hud-gauge-bar"><div class="hud-gauge-fill" id="bar-alt" style="background:linear-gradient(90deg, #3b82f6, #c084fc);"></div></div>
      </div>
      <div class="stat-box">
        <div class="stat-title">Distance</div>
        <div class="stat-val"><span id="val-dist">0.0</span> <span class="stat-sub">m</span></div>
      </div>
      <div class="stat-box">
        <div class="stat-title">Flight Time</div>
        <div class="stat-val"><span id="val-time">0.0</span> <span class="stat-sub">s</span></div>
      </div>
      <div class="stat-box">
        <div class="stat-title">Gates Cleared</div>
        <div class="stat-val" style="color:var(--emerald)"><span id="val-gates">0 / 0</span></div>
      </div>
      <div class="stat-box">
        <div class="stat-title">Precision Score</div>
        <div class="stat-val" style="color:var(--gold)"><span id="val-score">0.0</span> <span class="stat-sub">/ 100</span></div>
      </div>
    </div>

    <div style="font-size:11px; color:var(--text-dim); line-height:1.4; border-top:1px solid rgba(255,255,255,0.08); padding-top:8px;" id="card-notes">
      No notes available.
    </div>
  </div>

  <!-- Right Drawer: Morphology Blueprint & Neural Topology -->
  <div class="details-card">
    <div class="section-title">
      <span>📐 Morphology Blueprint</span>
      <span style="font-family:'JetBrains Mono'; font-size:10px; color:var(--text-dim);" id="morph-spec-summary">Wingspan: 1.57m</span>
    </div>

    <!-- Morphology Blueprint SVG -->
    <div id="morphology-svg-container">
      <svg id="morphology-svg" width="100%" height="100%" viewBox="-100 -50 200 100"></svg>
    </div>

    <!-- Morphology Parameters Table -->
    <div class="stat-grid" style="grid-template-columns: 1fr 1fr 1fr; gap:6px;">
      <div class="stat-box" style="padding:6px 8px;">
        <div class="stat-title">Span</div>
        <div class="stat-val" style="font-size:12px;"><span id="morph-span">0.0</span>m</div>
      </div>
      <div class="stat-box" style="padding:6px 8px;">
        <div class="stat-title">Wing Area</div>
        <div class="stat-val" style="font-size:12px;"><span id="morph-area">0.0</span>m²</div>
      </div>
      <div class="stat-box" style="padding:6px 8px;">
        <div class="stat-title">Mass</div>
        <div class="stat-val" style="font-size:12px;"><span id="morph-mass">0.0</span>kg</div>
      </div>
      <div class="stat-box" style="padding:6px 8px;">
        <div class="stat-title">H-Tail</div>
        <div class="stat-val" style="font-size:12px;"><span id="morph-htail">0.0</span>m²</div>
      </div>
      <div class="stat-box" style="padding:6px 8px;">
        <div class="stat-title">V-Tail</div>
        <div class="stat-val" style="font-size:12px;"><span id="morph-vtail">0.0</span>m²</div>
      </div>
      <div class="stat-box" style="padding:6px 8px;">
        <div class="stat-title">T/W Ratio</div>
        <div class="stat-val" style="font-size:12px;"><span id="morph-tw">0.0</span></div>
      </div>
    </div>

    <!-- Neural Network Topology Visualizer -->
    <div class="section-title" style="margin-top:6px;">
      <span>🧠 Controller Topology (NEAT)</span>
      <span style="font-family:'JetBrains Mono'; font-size:10px; color:var(--cyan);" id="nn-summary">PID Controller</span>
    </div>
    <div id="nn-canvas-container">
      <canvas id="nn-canvas"></canvas>
    </div>
  </div>

  <!-- Bottom Playback HUD Bar -->
  <div class="playback-hud">
    <button class="playback-btn" id="play-pause-btn">▶</button>
    <button class="playback-btn" id="reset-btn" style="font-size:10px;">⏮</button>
    <span class="hud-time" id="playback-time-display">0.0s / 0.0s</span>
    <input type="range" class="time-slider" id="time-slider" min="0" max="100" value="0">
    <button class="playback-btn" id="speed-btn" style="font-size:11px; width:44px; border-radius:12px;">1.0x</button>
  </div>

  <!-- Modal: Best vs Latest Comparison Matrix -->
  <div class="modal-overlay" id="matrix-modal">
    <div class="modal-box">
      <div class="modal-header">
        <div class="modal-title">
          <span>📊 Full Best Generation vs Latest Generation Matrix</span>
        </div>
        <button class="modal-close-btn" id="close-matrix-btn">✕</button>
      </div>
      <div class="matrix-table-wrap">
        <table class="matrix-table">
          <thead>
            <tr>
              <th>Test</th>
              <th>Status</th>
              <th>Contender</th>
              <th>Gen</th>
              <th>Speed</th>
              <th>Distance</th>
              <th>Waypoints</th>
              <th>Crash?</th>
              <th>Precision Score</th>
            </tr>
          </thead>
          <tbody id="matrix-table-body"></tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- Visualizer JavaScript Engine -->
  <script>
    const ALL_RUNS = {runs_json};
    const MATRIX_ROWS = {matrix_json};
    const CATEGORIES = {categories_json};

    let activeCategory = "all";
    let activeTestCode = "B";
    let activeRun = null;

    // Three.js State
    let scene, camera, renderer, controls;
    let trajLine = null, planeMarker = null, waypointGroup = null, arenaGrid = null;
    let animRunning = false;
    let currentStepIdx = 0;
    let playbackSpeed = 1.0;
    let animTimer = null;

    // Initialize UI
    function initUI() {{
      const catContainer = document.getElementById("category-filters");
      catContainer.innerHTML = "";
      CATEGORIES.forEach(cat => {{
        const btn = document.createElement("button");
        btn.className = "filter-btn" + (cat.id === activeCategory ? " active" : "");
        btn.textContent = cat.label;
        btn.onclick = () => {{
          document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
          btn.classList.add("active");
          activeCategory = cat.id;
          populateAircraftDropdown();
        }};
        catContainer.appendChild(btn);
      }});

      document.getElementById("test-course-select").onchange = (e) => {{
        activeTestCode = e.target.value;
        populateAircraftDropdown();
      }};

      document.getElementById("aircraft-select").onchange = (e) => {{
        const targetId = e.target.value;
        const found = ALL_RUNS.find(r => r.test_code === activeTestCode && r.controller_id === targetId);
        if (found) loadRun(found);
      }};

      // Playback Controls
      document.getElementById("play-pause-btn").onclick = togglePlayPause;
      document.getElementById("reset-btn").onclick = resetPlayback;
      document.getElementById("speed-btn").onclick = cycleSpeed;
      document.getElementById("time-slider").oninput = (e) => {{
        if (!activeRun || !activeRun.trajectory.length) return;
        const pct = parseFloat(e.target.value) / 100.0;
        currentStepIdx = Math.floor(pct * (activeRun.trajectory.length - 1));
        updateFrame();
      }};

      // Matrix Modal
      document.getElementById("open-matrix-btn").onclick = () => {{
        renderMatrixTable();
        document.getElementById("matrix-modal").classList.add("active");
      }};
      document.getElementById("close-matrix-btn").onclick = () => {{
        document.getElementById("matrix-modal").classList.remove("active");
      }};

      populateAircraftDropdown();
    }}

    function populateAircraftDropdown() {{
      const select = document.getElementById("aircraft-select");
      select.innerHTML = "";

      let filtered = ALL_RUNS.filter(r => r.test_code === activeTestCode);
      if (activeCategory !== "all") {{
        filtered = filtered.filter(r => r.category === activeCategory);
      }}

      if (filtered.length === 0) {{
        filtered = ALL_RUNS.filter(r => r.test_code === activeTestCode);
      }}

      // Group by Best vs Latest
      const optBest = document.createElement("optgroup");
      optBest.label = "⭐ Best / Canonical Champions";
      const optLatest = document.createElement("optgroup");
      optLatest.label = "⏱ Latest / Iterative Checkpoints";

      filtered.forEach(r => {{
        const opt = document.createElement("option");
        opt.value = r.controller_id;
        opt.textContent = `${{r.name}} (${{r.is_best ? 'BEST' : 'LATEST'}})`;
        if (r.is_best) optBest.appendChild(opt);
        else optLatest.appendChild(opt);
      }});

      if (optBest.children.length > 0) select.appendChild(optBest);
      if (optLatest.children.length > 0) select.appendChild(optLatest);

      // Default pick: Gen 352 for TESTAROSSA, Gen 375 for ULTIMA, or first
      let pick = filtered.find(r => r.controller_id === "TALOS-P4-TESTAROSSA_gen352") ||
                 filtered.find(r => r.controller_id === "TALOS-P4-ULTIMA_gen375_hairpin") ||
                 filtered[0];
      if (pick) {{
        select.value = pick.controller_id;
        loadRun(pick);
      }}
    }}

    function loadRun(run) {{
      activeRun = run;
      updateTelemetryCard(run);
      renderMorphologySVG(run.morphology);
      renderNNTopology(run.controller);
      build3DTrajectory(run);
      resetPlayback();
    }}

    function updateTelemetryCard(run) {{
      document.getElementById("card-aircraft-name").textContent = run.name;

      const badgeStatus = document.getElementById("badge-status");
      badgeStatus.textContent = run.is_best ? "BEST IN LINEAGE" : "LATEST RUN";
      badgeStatus.className = "badge " + (run.is_best ? "badge-best" : "badge-latest");

      document.getElementById("badge-gen").textContent = `GEN ${{run.gen}}`;

      const badgeCrash = document.getElementById("badge-crash");
      badgeCrash.textContent = run.crashed ? "CRASHED" : "SURVIVED";
      badgeCrash.style.background = run.crashed ? "rgba(255,0,85,0.2)" : "rgba(16,185,129,0.2)";
      badgeCrash.style.color = run.crashed ? "var(--magenta)" : "var(--emerald)";
      badgeCrash.style.border = "1px solid " + (run.crashed ? "rgba(255,0,85,0.4)" : "rgba(16,185,129,0.4)");

      document.getElementById("val-speed").textContent = run.mean_airspeed.toFixed(1);
      document.getElementById("val-alt").textContent = run.mean_altitude.toFixed(1);
      document.getElementById("val-dist").textContent = run.distance.toFixed(1);
      document.getElementById("val-time").textContent = run.flight_time.toFixed(1);
      document.getElementById("val-gates").textContent = `${{run.waypoints_hit}} / ${{run.course.length || '-'}}`;
      document.getElementById("val-score").textContent = run.precision_score !== null ? run.precision_score.toFixed(1) : "N/A";

      document.getElementById("card-notes").textContent = run.notes || "Standard flight evaluation.";

      // Gauge Bars
      document.getElementById("bar-speed").style.width = Math.min((run.mean_airspeed / 60.0) * 100.0, 100.0) + "%";
      document.getElementById("bar-alt").style.width = Math.min((run.mean_altitude / 50.0) * 100.0, 100.0) + "%";
    }}

    // Morphology SVG Blueprint Drawing
    function renderMorphologySVG(m) {{
      const svg = document.getElementById("morphology-svg");
      svg.innerHTML = "";
      if (!m) return;

      const span = m.wingspan || 1.0;
      const area = m.wing_area || 0.3;
      const mass = m.total_mass || 1.2;
      const htail = m.h_tail_area || 0.05;
      const vtail = m.v_tail_area || 0.05;
      const tw = m.thrust_to_weight || 0.6;
      const cg = m.cg_x_offset || 0.0;

      document.getElementById("morph-span").textContent = span.toFixed(2);
      document.getElementById("morph-area").textContent = area.toFixed(2);
      document.getElementById("morph-mass").textContent = mass.toFixed(2);
      document.getElementById("morph-htail").textContent = htail.toFixed(2);
      document.getElementById("morph-vtail").textContent = vtail.toFixed(2);
      document.getElementById("morph-tw").textContent = tw.toFixed(2);
      document.getElementById("morph-spec-summary").textContent = `Span: ${{span.toFixed(2)}}m | Mass: ${{mass.toFixed(1)}}kg`;

      const scale = 50.0 / Math.max(span, 1.5);
      const halfSpan = (span * 0.5) * scale;
      const chord = Math.max((area / span) * scale, 6);
      const htSpan = Math.sqrt(htail) * 1.8 * scale;

      // Fuselage center line
      const fuse = document.createElementNS("http://www.w3.org/2000/svg", "line");
      fuse.setAttribute("x1", -35); fuse.setAttribute("y1", 0);
      fuse.setAttribute("x2", 35); fuse.setAttribute("y2", 0);
      fuse.setAttribute("stroke", "rgba(255,255,255,0.3)");
      fuse.setAttribute("stroke-width", "2");
      svg.appendChild(fuse);

      // Main Wing (trapezoid polygon)
      const wing = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
      wing.setAttribute("points", `0,-${{halfSpan}} ${{chord}},-${{halfSpan * 0.7}} ${{chord}},${{halfSpan * 0.7}} 0,${{halfSpan}} -${{chord * 0.4}},0`);
      wing.setAttribute("fill", "rgba(0, 240, 255, 0.25)");
      wing.setAttribute("stroke", "var(--cyan)");
      wing.setAttribute("stroke-width", "1.5");
      svg.appendChild(wing);

      // Horizontal Tail
      const tail = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
      tail.setAttribute("points", `-30,-${{htSpan}} -25,-${{htSpan * 0.7}} -25,${{htSpan * 0.7}} -30,${{htSpan}} -32,0`);
      tail.setAttribute("fill", "rgba(251, 191, 36, 0.3)");
      tail.setAttribute("stroke", "#fbbf24");
      tail.setAttribute("stroke-width", "1.5");
      svg.appendChild(tail);

      // CG Marker
      const cgX = cg * scale * 2.0;
      const cgDot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      cgDot.setAttribute("cx", cgX); cgDot.setAttribute("cy", 0);
      cgDot.setAttribute("r", 3);
      cgDot.setAttribute("fill", "var(--magenta)");
      svg.appendChild(cgDot);
    }}

    // NEAT Neural Network Topology Visualizer
    function renderNNTopology(ctrl) {{
      const canvas = document.getElementById("nn-canvas");
      const ctx = canvas.getContext("2d");
      const w = canvas.parentElement.clientWidth;
      const h = canvas.parentElement.clientHeight;
      canvas.width = w; canvas.height = h;
      ctx.clearRect(0, 0, w, h);

      if (!ctrl || !ctrl.nodes || ctrl.nodes.length === 0) {{
        document.getElementById("nn-summary").textContent = "Non-Neural (PID)";
        ctx.fillStyle = "#94a3b8";
        ctx.font = "12px Inter";
        ctx.textAlign = "center";
        ctx.fillText("Classical Cascaded PID Controller", w / 2, h / 2);
        ctx.fillText("(Deterministic Flight Control)", w / 2, h / 2 + 18);
        return;
      }}

      const nodes = ctrl.nodes;
      const conns = ctrl.connections || [];
      const enabledConns = conns.filter(c => c.enabled);
      document.getElementById("nn-summary").textContent = `${{nodes.length}} Nodes | ${{enabledConns.length}} Conns`;

      // Group nodes into layers
      const inputs = nodes.filter(n => n.type === "input");
      const outputs = nodes.filter(n => n.type === "output");
      const hiddens = nodes.filter(n => n.type === "hidden");

      const nodePos = {{}};
      const padX = 25, padY = 20;

      inputs.forEach((n, idx) => {{
        nodePos[n.id] = {{
          x: padX,
          y: padY + (idx / Math.max(inputs.length - 1, 1)) * (h - padY * 2),
          color: "#3b82f6"
        }};
      }});

      outputs.forEach((n, idx) => {{
        nodePos[n.id] = {{
          x: w - padX,
          y: padY + (idx / Math.max(outputs.length - 1, 1)) * (h - padY * 2),
          color: "#00f0ff"
        }};
      }});

      hiddens.forEach((n, idx) => {{
        const col = (idx % 2 === 0) ? (w * 0.42) : (w * 0.58);
        nodePos[n.id] = {{
          x: col,
          y: padY + ((idx + 0.5) / Math.max(hiddens.length, 1)) * (h - padY * 2),
          color: "#c084fc"
        }};
      }});

      // Draw connections
      enabledConns.forEach(c => {{
        const p1 = nodePos[c.from];
        const p2 = nodePos[c.to];
        if (p1 && p2) {{
          ctx.beginPath();
          ctx.moveTo(p1.x, p1.y);
          ctx.lineTo(p2.x, p2.y);
          const weight = Math.abs(c.weight || 1.0);
          ctx.lineWidth = Math.min(Math.max(weight * 0.8, 0.5), 2.5);
          ctx.strokeStyle = (c.weight >= 0) ? "rgba(0, 240, 255, 0.35)" : "rgba(255, 0, 85, 0.35)";
          ctx.stroke();
        }}
      }});

      // Draw nodes
      Object.keys(nodePos).forEach(id => {{
        const p = nodePos[id];
        ctx.beginPath();
        ctx.arc(p.x, p.y, 4, 0, Math.PI * 2);
        ctx.fillStyle = p.color;
        ctx.fill();
        ctx.strokeStyle = "#fff";
        ctx.lineWidth = 1;
        ctx.stroke();
      }});
    }}

    // Three.js 3D Flight Scene Builder
    function initThree() {{
      const container = document.getElementById("canvas-container");
      scene = new THREE.Scene();
      scene.fog = new THREE.FogExp2(0x07090e, 0.0004);

      camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 1, 5000);
      camera.position.set(-200, 150, -250);

      renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: false }});
      renderer.setPixelRatio(window.devicePixelRatio);
      renderer.setSize(window.innerWidth, window.innerHeight);
      renderer.setClearColor(0x07090e, 1);
      container.appendChild(renderer.domElement);

      controls = new THREE.OrbitControls(camera, renderer.domElement);
      controls.enableDamping = true;
      controls.dampingFactor = 0.05;
      controls.maxPolarAngle = Math.PI / 2 - 0.02;

      // Lights
      const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
      scene.add(ambientLight);

      const dirLight = new THREE.DirectionalLight(0x00f0ff, 0.8);
      dirLight.position.set(300, 500, 200);
      scene.add(dirLight);

      // Arena Grid & Boundary Dome
      arenaGrid = new THREE.GridHelper(2000, 80, 0x00f0ff, 0x1e293b);
      arenaGrid.position.y = 0;
      scene.add(arenaGrid);

      // Plane Marker (Low-poly delta dart)
      const markerGeom = new THREE.ConeGeometry(3, 9, 4);
      markerGeom.rotateX(Math.PI / 2);
      const markerMat = new THREE.MeshStandardMaterial({{ color: 0x00f0ff, roughness: 0.2, metalness: 0.8 }});
      planeMarker = new THREE.Mesh(markerGeom, markerMat);
      planeMarker.visible = false;
      scene.add(planeMarker);

      waypointGroup = new THREE.Group();
      scene.add(waypointGroup);

      window.addEventListener("resize", () => {{
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
      }});

      animate();
    }}

    function build3DTrajectory(run) {{
      if (trajLine) scene.remove(trajLine);
      waypointGroup.clear();

      // Waypoint Gate Toruses
      if (run.course && run.course.length > 0) {{
        run.course.forEach((wp, idx) => {{
          const torusGeom = new THREE.TorusGeometry(8, 0.7, 8, 24);
          const torusMat = new THREE.MeshStandardMaterial({{
            color: idx < run.waypoints_hit ? 0x10b981 : 0xfbbf24,
            emissive: idx < run.waypoints_hit ? 0x059669 : 0xb45309,
            emissiveIntensity: 0.6,
          }});
          const torus = new THREE.Mesh(torusGeom, torusMat);
          torus.position.set(wp[0], wp[2], wp[1]); // PyFlyt Z is up, Three.js Y is up
          torus.rotateY(Math.PI / 2);
          waypointGroup.add(torus);
        }});
      }}

      // Trajectory 3D Line
      const pts = run.trajectory.map(p => new THREE.Vector3(p.x, p.z, p.y));
      if (pts.length > 1) {{
        const geom = new THREE.BufferGeometry().setFromPoints(pts);
        const mat = new THREE.LineBasicMaterial({{
          color: run.crashed ? 0xff0055 : 0x00f0ff,
          linewidth: 2,
        }});
        trajLine = new THREE.Line(geom, mat);
        scene.add(trajLine);
        planeMarker.visible = true;

        // Auto-center camera
        const mid = pts[Math.floor(pts.length / 2)];
        controls.target.set(mid.x, mid.y, mid.z);
        camera.position.set(mid.x - 220, mid.y + 140, mid.z - 220);
      }} else {{
        planeMarker.visible = false;
      }}
    }}

    function updateFrame() {{
      if (!activeRun || !activeRun.trajectory.length) return;
      const pt = activeRun.trajectory[currentStepIdx];
      if (!pt) return;

      planeMarker.position.set(pt.x, pt.z, pt.y);

      // Orientation toward next point
      if (currentStepIdx < activeRun.trajectory.length - 1) {{
        const next = activeRun.trajectory[currentStepIdx + 1];
        planeMarker.lookAt(next.x, next.z, next.y);
      }}

      // Update Slider and Time Display
      const totalTime = activeRun.flight_time;
      const curTime = pt.time || (currentStepIdx * 0.133);
      document.getElementById("playback-time-display").textContent = `${{curTime.toFixed(1)}}s / ${{totalTime.toFixed(1)}}s`;
      document.getElementById("time-slider").value = Math.floor((currentStepIdx / (activeRun.trajectory.length - 1)) * 100);

      // Update Live Telemetry in Card
      document.getElementById("val-speed").textContent = (pt.airspeed || activeRun.mean_airspeed).toFixed(1);
      document.getElementById("val-alt").textContent = pt.z.toFixed(1);
    }}

    function animate() {{
      requestAnimationFrame(animate);
      controls.update();

      if (animRunning && activeRun && activeRun.trajectory.length > 0) {{
        currentStepIdx += Math.round(1 * playbackSpeed);
        if (currentStepIdx >= activeRun.trajectory.length) {{
          currentStepIdx = activeRun.trajectory.length - 1;
          animRunning = false;
          document.getElementById("play-pause-btn").textContent = "▶";
        }}
        updateFrame();
      }}

      renderer.render(scene, camera);
    }}

    function togglePlayPause() {{
      animRunning = !animRunning;
      document.getElementById("play-pause-btn").textContent = animRunning ? "⏸" : "▶";
    }}

    function resetPlayback() {{
      animRunning = false;
      currentStepIdx = 0;
      document.getElementById("play-pause-btn").textContent = "▶";
      updateFrame();
    }}

    function cycleSpeed() {{
      const speeds = [1.0, 2.0, 4.0, 0.5];
      const nextIdx = (speeds.indexOf(playbackSpeed) + 1) % speeds.length;
      playbackSpeed = speeds[nextIdx];
      document.getElementById("speed-btn").textContent = playbackSpeed + "x";
    }}

    // Render Matrix Modal Table
    function renderMatrixTable() {{
      const tbody = document.getElementById("matrix-table-body");
      tbody.innerHTML = "";

      MATRIX_ROWS.forEach(row => {{
        const tr = document.createElement("tr");
        if (row.is_best) tr.className = "matrix-row-best";
        else if (row.is_latest) tr.className = "matrix-row-latest";

        tr.innerHTML = `
          <td style="font-weight:700; color:var(--cyan)">Test ${{row.test_code}}</td>
          <td><span class="badge ${{row.is_best ? 'badge-best' : 'badge-latest'}}">${{row.is_best ? 'BEST' : 'LATEST'}}</span></td>
          <td style="font-weight:600;">${{row.display_name}}</td>
          <td style="font-family:'JetBrains Mono'">${{row.gen}}</td>
          <td style="font-family:'JetBrains Mono'">${{row.mean_airspeed.toFixed(1)}} m/s</td>
          <td style="font-family:'JetBrains Mono'">${{row.distance.toFixed(1)}} m</td>
          <td style="font-weight:700; color:${{row.waypoints_hit === row.num_waypoints && row.num_waypoints > 0 ? 'var(--emerald)' : 'inherit'}}">
            ${{row.waypoints_hit}} / ${{row.num_waypoints || '-'}}
          </td>
          <td><span class="${{row.crashed ? 'badge-crash' : 'badge-win'}}">${{row.crashed ? 'CRASH' : 'CLEAN'}}</span></td>
          <td style="font-weight:700; color:var(--gold)">${{row.precision_score !== null ? row.precision_score.toFixed(1) : '-'}}</td>
        `;

        tr.onclick = () => {{
          document.getElementById("matrix-modal").classList.remove("active");
          document.getElementById("test-course-select").value = row.test_code;
          activeTestCode = row.test_code;
          populateAircraftDropdown();
          const target = ALL_RUNS.find(r => r.test_code === row.test_code && r.controller_id === row.controller_id);
          if (target) loadRun(target);
        }};

        tbody.appendChild(tr);
      }});
    }}

    window.onload = () => {{
      initThree();
      initUI();
    }};
  </script>
</body>
</html>
"""

    with open(OUTPUT_HTML, "w", encoding="utf-8") as fh:
        fh.write(html_content)
    print(f"[talos] Universal 3D Flight Visualizer generated: {OUTPUT_HTML}")


if __name__ == "__main__":
    con = sqlite3.connect(DB_PATH)
    populate_database_tables(con)
    generate_visualizer_html(con)
    con.close()
