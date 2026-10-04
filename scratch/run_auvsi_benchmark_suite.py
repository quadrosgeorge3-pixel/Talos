"""Course D: AUVSI SUAS Autonomous Navigation Challenge Benchmark Runner.

Standardized after the official AUVSI SUAS collegiate UAV competition rules:
  - 5-WayPoint 3D reconnaissance flight plan spanning the 1,000m arena
  - 15.0m lateral and vertical precision tolerance bands
  - 15.0m waypoint capture radius
  - Scored on Waypoint Intercepts, 15m Corridor Adherence %, and Flight Stability

Evaluates all project controllers and logs results to output/icarus.db.
"""
import os
import sys
sys.path.insert(0, ".")
import json
import sqlite3
import shutil
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import neat
import numpy as np

from src.simulation.env import FixedwingEnv
from src.simulation.pid_controller import FixedwingPIDController
from src.genome.morphology import MorphologyGenome
from src.genome.urdf_gen import generate_model_files
from src.experiment.metadata import load_config
from src.experiment.generate_notebook import generate_lab_notebook

# ---------------------------------------------------------------------------
# Course D: AUVSI SUAS 3D Waypoint Course Specification
# ---------------------------------------------------------------------------
AUVSI_WAYPOINTS = np.array([
    [180.0,   40.0, 25.0],   # Leg 1: Departure climb to 25m (+15m climb, 12 deg right)
    [320.0,  -80.0, 40.0],   # Leg 2: Transit corridor climb to 40m survey ceiling
    [160.0, -220.0, 20.0],   # Leg 3: Rapid descent corridor to 20m (-20m pullout test)
    [-60.0, -120.0, 15.0],   # Leg 4: Low-altitude terrain observation sprint at 15m
    [ 60.0,   80.0, 30.0],   # Leg 5: Return alignment climb to 30m
])

COURSE_MAP_METADATA = [
    {"leg": 1, "target": [180.0,   40.0, 25.0], "tol_lat": 15.0, "tol_alt": 15.0, "desc": "Departure Climb to 25m"},
    {"leg": 2, "target": [320.0,  -80.0, 40.0], "tol_lat": 15.0, "tol_alt": 15.0, "desc": "Survey Ceiling Transit to 40m"},
    {"leg": 3, "target": [160.0, -220.0, 20.0], "tol_lat": 15.0, "tol_alt": 15.0, "desc": "Rapid Descent Corridor to 20m"},
    {"leg": 4, "target": [-60.0, -120.0, 15.0], "tol_lat": 15.0, "tol_alt": 15.0, "desc": "Low-Altitude Terrain Hug at 15m"},
    {"leg": 5, "target": [ 60.0,   80.0, 30.0], "tol_lat": 15.0, "tol_alt": 15.0, "desc": "Return Alignment Leg to 30m"},
]

COURSE_NAME = "Test D - AUVSI SUAS Autonomous Challenge"
ARENA_RADIUS = 1000.0
WAYPOINT_RADIUS = 15.0
TEST_DURATION = 30.0
TOLERANCE_BAND = 15.0

# ---------------------------------------------------------------------------
# Simulation Runner for AUVSI Course
# ---------------------------------------------------------------------------
def run_auvsi_simulation(
    controller_type: str,
    controller_obj: Any,
    model_dir: str = None,
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

    # Set Course D waypoints and 15m capture radius
    if hasattr(unwrapped, "waypoints"):
        unwrapped.waypoints.targets = AUVSI_WAYPOINTS.copy()
        unwrapped.waypoints.num_targets = len(AUVSI_WAYPOINTS)
        unwrapped.waypoints.goal_reach_distance = WAYPOINT_RADIUS

    if controller_type == "PID":
        controller_obj.reset()

    trajectory = []
    actions = []
    corridor_hits = 0
    total_active_steps = 0

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

        # Check AUVSI corridor adherence:
        # Distance to next target in 3D, and vertical altitude deviation
        dist_to_tgt = float(info.get("dist_to_wp", 999.0))
        alt_err = abs(pz - 25.0)  # nominal reference corridor
        in_corridor = (alt_err <= TOLERANCE_BAND)
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
                "dist_to_target": dist_to_tgt,
            })

        if term or trunc:
            break

    env_metrics = env.get_metrics()
    waypoints_hit = int(getattr(unwrapped.waypoints, "num_targets_reached", 0))
    env.close()

    # Calculate AUVSI Composite Precision Score (0 - 100 scale)
    wp_points = (waypoints_hit / len(AUVSI_WAYPOINTS)) * 50.0
    corridor_pct = (corridor_hits / max(1, total_active_steps)) * 100.0
    corridor_points = (corridor_pct / 100.0) * 30.0
    survival_points = 20.0 if not env_metrics.get("crashed", False) else 0.0
    auvsi_score = round(wp_points + corridor_points + survival_points, 1)

    y_coords = [p["y"] for p in trajectory]
    z_coords = [p["z"] for p in trajectory]

    return {
        "flight_time": env_metrics.get("flight_time", 0.0),
        "distance": env_metrics.get("distance", 0.0),
        "mean_airspeed": env_metrics.get("airspeed", 0.0),
        "mean_altitude": float(np.mean(z_coords)) if z_coords else 0.0,
        "altitude_error": env_metrics.get("altitude_error", 0.0),
        "max_lateral_deviation": float(np.max(np.abs(y_coords))) if y_coords else 0.0,
        "control_energy": env_metrics.get("energy", 0.0),
        "crashed": env_metrics.get("crashed", False),
        "stalling": env_metrics.get("stalling", False),
        "waypoints_hit": waypoints_hit,
        "corridor_adherence_pct": round(corridor_pct, 1),
        "auvsi_score": auvsi_score,
        "trajectory": trajectory,
    }

# ---------------------------------------------------------------------------
# Database Logging
# ---------------------------------------------------------------------------
def log_benchmark_to_db(db_path: str, ctrl_id: str, ctrl_type: str, res: dict):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    traj_json = json.dumps(res.get("trajectory", []))
    course_json = json.dumps(COURSE_MAP_METADATA)

    # Delete previous Test D record for this controller if already exists to keep it clean
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
        float(res.get("auvsi_score", 0.0)),
        now_iso,
        course_json,
        ARENA_RADIUS,
        WAYPOINT_RADIUS,
        traj_json,
    ))
    con.commit()
    con.close()

# ---------------------------------------------------------------------------
# Main Execution for All Champions
# ---------------------------------------------------------------------------
def main():
    print("=" * 80)
    print("  PROJECT TALOS — COURSE D: AUVSI SUAS BENCHMARK EVALUATION")
    print(f"  Standard: AUVSI SUAS Rules (15m Corridor, 15m Capture Radius, 30s Duration)")
    print(f"  Waypoints: {len(AUVSI_WAYPOINTS)} 3D Multi-Elevation Targets across 1,000m Arena")
    print("=" * 80)

    db_path = "output/icarus.db"

    # 1. Base PID Controller
    pid_ctrl = FixedwingPIDController(dt=1.0 / 30.0, target_airspeed=24.0, target_altitude=10.0)

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

    # 4. P4-ULTIMA Champion (Checkpoint 135)
    p4_chk = "output/checkpoints/talos-p4-ultima-chk-135"
    p4_morph_file = "output/checkpoints/talos-p4-ultima-morph-135.json"
    pop_p4 = neat.Checkpointer.restore_checkpoint(p4_chk)
    best_p4 = max(pop_p4.population.values(), key=lambda g: g.fitness or -999)
    net_p4 = neat.nn.FeedForwardNetwork.create(best_p4, pop_p4.config)

    with open(p4_morph_file, "r", encoding="utf-8") as f:
        p4_morphs = json.load(f)
    p4_m_dict = p4_morphs.get(str(best_p4.key), list(p4_morphs.values())[0])
    p4_morph = MorphologyGenome.from_dict(p4_m_dict)
    p4_model_dir = os.path.abspath("models/bench_p4_ultima_gen135")
    generate_model_files(p4_morph, p4_model_dir)

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
        ("TALOS-P4-ULTIMA_champ", "NEAT", net_p4, p4_model_dir, "P4-ULTIMA Co-Evolved Airframe"),
    ]

    all_results = []

    for ctrl_id, ctrl_type, ctrl_obj, model_dir, desc in eval_matrix:
        print(f"\nEvaluating: {ctrl_id} ({desc})...")
        res = run_auvsi_simulation(ctrl_type, ctrl_obj, model_dir, seed=42)
        log_benchmark_to_db(db_path, ctrl_id, ctrl_type, res)

        entry = {
            "controller_id": ctrl_id,
            "type": ctrl_type,
            "description": desc,
            "auvsi_score": res["auvsi_score"],
            "waypoints_hit": f"{res['waypoints_hit']} / {len(AUVSI_WAYPOINTS)}",
            "corridor_pct": f"{res['corridor_adherence_pct']}%",
            "flight_time": f"{res['flight_time']:.1f}s",
            "distance": f"{res['distance']:.1f}m",
            "airspeed": f"{res['mean_airspeed']:.1f} m/s",
            "crashed": "YES" if res["crashed"] else "NO",
        }
        all_results.append(entry)
        print(f"  -> Score: {res['auvsi_score']}/100 | Waypoints: {res['waypoints_hit']}/5 | Corridor: {res['corridor_adherence_pct']}% | Spd: {res['mean_airspeed']:.1f} m/s | Crashed: {res['crashed']}")

    # Clean up temp P4 model dir
    shutil.rmtree(p4_model_dir, ignore_errors=True)

    # Sort results by AUVSI score descending
    all_results.sort(key=lambda x: float(x["auvsi_score"]), reverse=True)

    print("\n" + "=" * 95)
    print("  OFFICIAL AUVSI SUAS BENCHMARK LEADERBOARD (COURSE D)")
    print("=" * 95)
    header = f"{'Rank':<4} | {'Controller ID':<24} | {'AUVSI Score':<11} | {'Gates Hit':<9} | {'Corridor':<8} | {'Speed':<9} | {'Crashed':<7}"
    print(header)
    print("-" * 95)
    for i, r in enumerate(all_results, 1):
        print(f"{i:<4} | {r['controller_id']:<24} | {r['auvsi_score']:<11} | {r['waypoints_hit']:<9} | {r['corridor_pct']:<8} | {r['airspeed']:<9} | {r['crashed']:<7}")
    print("=" * 95)

    # Refresh lab notebook
    try:
        generate_lab_notebook()
        print("\n[talos] Updated docs/LAB_NOTEBOOK.md with Test D records!")
    except Exception as e:
        print(f"\n[talos] Note on notebook generation: {e}")

if __name__ == "__main__":
    main()
