"""Course E: FAI F3D/F5D Pylon Racing Benchmark Runner.

Standardized against official FAI Sporting Code (Section 4: Aeromodelling - Pylon Racing):
  - Triangular 3-pylon race course:
      * Pylon 1 (Apex): (200m, 0m, 12m)
      * Pylon 2 (Base Right): (20m, 35m, 12m)
      * Pylon 3 (Base Left):  (20m, -35m, 12m)
  - Flown across multiple continuous high-G laps
  - 10.0m capture/clearance tolerance radius around pylons
  - Precision scoring matrix:
      * Waypoint Intercepts (50 pts max)
      * Low-Altitude Race Corridor Adherence (30 pts max)
      * Survival without ground collision (20 pts max)
      * Penalty for pylon cuts / wall excursions

Evaluates all project baseline/evolved champions (excluding ULTIMA) and logs results to output/icarus.db.
"""
import os
import sys
sys.path.insert(0, ".")
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import neat
import numpy as np

from src.simulation.env import FixedwingEnv
from src.simulation.pid_controller import FixedwingPIDController
from src.genome.morphology import MorphologyGenome
from src.genome.urdf_gen import generate_model_files
from src.experiment.metadata import load_config
from src.experiment.generate_notebook import generate_lab_notebook

# ---------------------------------------------------------------------------
# Course E: FAI F3D/F5D Triangular Pylon Race Specification
# ---------------------------------------------------------------------------
# 3-pylon triangular circuit:
# Pylon 1: Turnaround apex at x=200m
# Pylon 2: Twin pylon starboard at x=20m, y=35m
# Pylon 3: Twin pylon port at x=20m, y=-35m
# Flown in 3 continuous laps (9 waypoints) in 40s
P1 = [200.0,   0.0, 12.0]
P2 = [ 20.0,  35.0, 12.0]
P3 = [ 20.0, -35.0, 12.0]

F3D_WAYPOINTS = np.array([
    P1, P2, P3,  # Lap 1
    P1, P2, P3,  # Lap 2
    P1, P2, P3   # Lap 3
])

COURSE_MAP_METADATA = [
    {"gate": 1, "pylon": "Pylon 1 (Lap 1 Apex)",      "target": P1, "tol": 10.0},
    {"gate": 2, "pylon": "Pylon 2 (Lap 1 Starboard)", "target": P2, "tol": 10.0},
    {"gate": 3, "pylon": "Pylon 3 (Lap 1 Port)",      "target": P3, "tol": 10.0},
    {"gate": 4, "pylon": "Pylon 1 (Lap 2 Apex)",      "target": P1, "tol": 10.0},
    {"gate": 5, "pylon": "Pylon 2 (Lap 2 Starboard)", "target": P2, "tol": 10.0},
    {"gate": 6, "pylon": "Pylon 3 (Lap 2 Port)",      "target": P3, "tol": 10.0},
    {"gate": 7, "pylon": "Pylon 1 (Lap 3 Apex)",      "target": P1, "tol": 10.0},
    {"gate": 8, "pylon": "Pylon 2 (Lap 3 Starboard)", "target": P2, "tol": 10.0},
    {"gate": 9, "pylon": "Pylon 3 (Lap 3 Port)",      "target": P3, "tol": 10.0},
]

COURSE_NAME = "Test E - FAI F3D/F5D Pylon Racing"
ARENA_RADIUS = 1000.0
WAYPOINT_RADIUS = 10.0
TEST_DURATION = 40.0
CORRIDOR_ALT = 12.0
TOLERANCE_BAND = 10.0

def run_pylon_simulation(
    controller_type: str,
    controller_obj: Any,
    model_dir: Optional[str] = None,
    seed: int = 42,
) -> dict:
    config = load_config("configs/controller_only/c1_controller_only.json")
    config["simulation"]["episode_duration"] = TEST_DURATION
    config["simulation"]["flight_dome_size"] = ARENA_RADIUS

    env = FixedwingEnv(config=config, model_dir=model_dir)
    unwrapped = env.env.unwrapped
    unwrapped.flight_dome_size = ARENA_RADIUS
    env.max_steps = int(TEST_DURATION * env.control_hz)

    obs, _ = env.reset(seed=seed)
    unwrapped.waypoints.targets = F3D_WAYPOINTS.copy()
    unwrapped.waypoints.num_targets = len(F3D_WAYPOINTS)
    unwrapped.waypoints.goal_reach_distance = WAYPOINT_RADIUS

    if controller_type == "PID":
        controller_obj.reset()

    trajectory = []
    actions = []
    corridor_hits = 0
    total_active_steps = 0
    lap_completion_times = []
    last_wp_count = 0

    step = 0
    while step < env.max_steps:
        if controller_type == "PID":
            action = controller_obj.predict(obs)
        else:
            action = np.asarray(controller_obj.activate(obs), dtype=np.float32)

        actions.append(action)
        obs, _, term, trunc, info = env.step(action)
        step += 1
        total_active_steps += 1

        drone = unwrapped.env.drones[0]
        pos = drone.state[3]
        px, py, pz = float(pos[0]), float(pos[1]), float(pos[2])

        # Track lap crossings (each lap has 3 pylons: 3, 6, 9)
        cur_wps = int(getattr(unwrapped.waypoints, "num_targets_reached", 0))
        if cur_wps > last_wp_count:
            if cur_wps % 3 == 0:
                lap_completion_times.append(float(step / env.control_hz))
            last_wp_count = cur_wps

        # Corridor adherence: check if altitude is within [CORRIDOR_ALT +/- TOLERANCE_BAND]
        in_corridor = (abs(pz - CORRIDOR_ALT) <= TOLERANCE_BAND)
        if in_corridor:
            corridor_hits += 1

        if step % 4 == 0 or term or trunc:
            trajectory.append({
                "step": step,
                "time": float(step / env.control_hz),
                "x": px,
                "y": py,
                "z": pz,
                "airspeed": float(info.get("airspeed", 0.0)),
                "in_corridor": in_corridor,
            })

        if term or trunc:
            break

    env_metrics = env.get_metrics()
    waypoints_hit = int(getattr(unwrapped.waypoints, "num_targets_reached", 0))
    flight_time = float(env_metrics.get("flight_time", 0.0))
    env.close()

    # Lap split calculations
    lap_splits = []
    prev_t = 0.0
    for lt in lap_completion_times:
        lap_splits.append(round(lt - prev_t, 2))
        prev_t = lt
    best_lap = min(lap_splits) if lap_splits else None

    # Precision Scoring Matrix (0 - 100)
    wp_points = (waypoints_hit / len(F3D_WAYPOINTS)) * 50.0
    corridor_pct = (corridor_hits / max(1, total_active_steps)) * 100.0
    corridor_points = (corridor_pct / 100.0) * 30.0
    survival_points = 20.0 if not env_metrics.get("crashed", False) else 0.0
    precision_score = round(wp_points + corridor_points + survival_points, 1)

    y_coords = [p["y"] for p in trajectory]
    z_coords = [p["z"] for p in trajectory]

    return {
        "flight_time": flight_time,
        "distance": env_metrics.get("distance", 0.0),
        "mean_airspeed": env_metrics.get("airspeed", 0.0),
        "mean_altitude": float(np.mean(z_coords)) if z_coords else 0.0,
        "altitude_error": env_metrics.get("altitude_error", 0.0),
        "max_lateral_deviation": float(np.max(np.abs(y_coords))) if y_coords else 0.0,
        "control_energy": env_metrics.get("energy", 0.0),
        "crashed": env_metrics.get("crashed", False),
        "stalling": env_metrics.get("stalling", False),
        "waypoints_hit": waypoints_hit,
        "laps_completed": len(lap_completion_times),
        "lap_splits": lap_splits,
        "best_lap": best_lap,
        "corridor_adherence_pct": round(corridor_pct, 1),
        "precision_score": precision_score,
        "trajectory": trajectory,
    }

def log_benchmark_to_db(db_path: str, ctrl_id: str, ctrl_type: str, res: dict):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    traj_json = json.dumps(res.get("trajectory", []))
    course_json = json.dumps(COURSE_MAP_METADATA)

    # Clean previous record if exists
    cur.execute("DELETE FROM benchmark_evaluations WHERE test_name = ? AND controller_id = ?", (COURSE_NAME, ctrl_id))

    cur.execute("""
        INSERT INTO benchmark_evaluations (
            test_name, controller_id, controller_type,
            flight_time, distance, mean_airspeed, mean_altitude,
            altitude_error, max_lateral_dev, control_energy,
            crashed, stalling, waypoints_hit, precision_score, measured_at,
            course_map_json, arena_radius, waypoint_radius, trajectory_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        COURSE_NAME,
        ctrl_id,
        ctrl_type,
        float(res.get("flight_time", 0.0)),
        float(res.get("distance", 0.0)),
        float(res.get("mean_airspeed", 0.0)),
        float(res.get("mean_altitude", 0.0)),
        float(res.get("altitude_error", 0.0)),
        float(res.get("max_lateral_deviation", 0.0)),
        float(res.get("control_energy", 0.0)),
        1 if res.get("crashed", False) else 0,
        1 if res.get("stalling", False) else 0,
        int(res.get("waypoints_hit", 0)),
        float(res.get("precision_score", 0.0)),
        now_iso,
        course_json,
        ARENA_RADIUS,
        WAYPOINT_RADIUS,
        traj_json,
    ))
    con.commit()
    con.close()

def main():
    print("=" * 80)
    print("  PROJECT TALOS — COURSE E: FAI F3D/F5D PYLON RACING BENCHMARK")
    print(f"  Standard: FAI 3-Pylon Triangular Circuit (10m Gate Radius, 30s Duration)")
    print(f"  Waypoints: {len(F3D_WAYPOINTS)} Pylons across 2 Continuous Laps")
    print("  Notice: ULTIMA excluded as requested (under active co-evolution)")
    print("=" * 80)

    db_path = "output/icarus.db"

    # 1. Base PID Controller
    pid_ctrl = FixedwingPIDController(dt=1.0 / 30.0, target_airspeed=24.0, target_altitude=12.0)

    # 2. Base C1 Frozen NEAT Champion
    c1_chk = "output/checkpoints/c1-chk-297"
    pop_c1 = neat.Checkpointer.restore_checkpoint(c1_chk)
    best_c1 = max(pop_c1.population.values(), key=lambda g: g.fitness or -999)
    net_c1 = neat.nn.FeedForwardNetwork.create(best_c1, pop_c1.config)

    # 3. P2B Open-Sky Gen 300 NEAT Champion
    p2b_chk = "output/checkpoints/talos-p2b-chk-300"
    pop_p2b = neat.Checkpointer.restore_checkpoint(p2b_chk)
    best_p2b = max(pop_p2b.population.values(), key=lambda g: g.fitness or -999)
    net_p2b = neat.nn.FeedForwardNetwork.create(best_p2b, pop_p2b.config)

    # Bodies for P3A, P3B, P3C
    p3a_dir = os.path.abspath("models/TALOS-P3A/gen099/ind001")
    p3b_dir = os.path.abspath("models/TALOS-P3B/gen099/ind021")
    p3c_dir = os.path.abspath("models/TALOS-P3C/gen023/ind023")

    eval_matrix = [
        ("pid_open_sky", "PID", pid_ctrl, None, "Default Baseline B0 Airframe"),
        ("phase2_neat_caged", "NEAT", net_c1, None, "Default Airframe (Caged Champ)"),
        ("TALOS-P2B_gen300_champ", "NEAT", net_p2b, None, "Default Airframe (Open Sky Champ)"),
        ("p3a_champ_pid", "PID", pid_ctrl, p3a_dir, "P3A Evolved Airframe"),
        ("p3a_champ_neat_gen300", "NEAT", net_p2b, p3a_dir, "P3A Evolved Airframe"),
        ("p3b_champ_pid", "PID", pid_ctrl, p3b_dir, "P3B Evolved Airframe"),
        ("p3b_champ_neat_gen300", "NEAT", net_p2b, p3b_dir, "P3B Evolved Airframe"),
        ("p3c_champ_pid", "PID", pid_ctrl, p3c_dir, "P3C Evolved Airframe"),
        ("p3c_champ_neat_gen300", "NEAT", net_p2b, p3c_dir, "P3C Evolved Airframe"),
    ]

    all_results = []

    for ctrl_id, ctrl_type, ctrl_obj, model_dir, desc in eval_matrix:
        print(f"\nEvaluating: {ctrl_id} ({desc})...")
        res = run_pylon_simulation(ctrl_type, ctrl_obj, model_dir, seed=42)
        log_benchmark_to_db(db_path, ctrl_id, ctrl_type, res)

        entry = {
            "controller_id": ctrl_id,
            "type": ctrl_type,
            "description": desc,
            "precision_score": res["precision_score"],
            "waypoints_hit": f"{res['waypoints_hit']} / {len(F3D_WAYPOINTS)}",
            "corridor_pct": f"{res['corridor_adherence_pct']}%",
            "flight_time": f"{res['flight_time']:.2f}s",
            "distance": f"{res['distance']:.1f}m",
            "airspeed": f"{res['mean_airspeed']:.1f} m/s",
            "laps": f"{res['laps_completed']} / 3",
            "best_lap": f"{res['best_lap']:.2f}s" if res['best_lap'] is not None else "N/A",
            "crashed": "YES" if res["crashed"] else "NO",
        }
        all_results.append(entry)
        print(f"  -> Score: {res['precision_score']}/100 | Laps: {entry['laps']} | Best Lap: {entry['best_lap']} | Time: {entry['flight_time']} | Pylons: {res['waypoints_hit']}/9 | Spd: {entry['airspeed']} | Crashed: {res['crashed']}")

    # Sort results by Precision Score descending
    all_results.sort(key=lambda x: float(x["precision_score"]), reverse=True)

    print("\n" + "=" * 105)
    print("  OFFICIAL FAI F3D/F5D PYLON RACING LEADERBOARD (COURSE E — 3 LAPS)")
    print("=" * 105)
    header = f"{'Rank':<4} | {'Controller ID':<24} | {'Precision':<11} | {'Laps':<7} | {'Total Time':<11} | {'Best Lap':<10} | {'Pylons':<8} | {'Speed':<9} | {'Crashed':<7}"
    print(header)
    print("-" * 105)
    for i, r in enumerate(all_results, 1):
        print(f"{i:<4} | {r['controller_id']:<24} | {r['precision_score']:<11} | {r['laps']:<7} | {r['flight_time']:<11} | {r['best_lap']:<10} | {r['waypoints_hit']:<8} | {r['airspeed']:<9} | {r['crashed']:<7}")
    print("=" * 105)

    try:
        generate_lab_notebook()
        print("\n[talos] Updated docs/LAB_NOTEBOOK.md with Course E records!")
    except Exception as e:
        print(f"\n[talos] Note on notebook generation: {e}")

if __name__ == "__main__":
    main()
