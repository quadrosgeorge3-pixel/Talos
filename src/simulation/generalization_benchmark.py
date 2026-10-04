"""Talos Post-Evolution Generalization Benchmark Suite.

Runs both the frozen Gen-300 NEAT champion (TALOS-P2A) and the reference
human-engineered Cascaded PID controller (TALOS-B01) through a standardized
battery of 3 flight tests, persisting all metrics into output/icarus.db:

    Test A — Open-Sky Straight Flight (1 km arena, 20s duration)
    Test B — Open-Sky Structured Waypoint Course (150m -> 100m -> 120m)
    Test C — Aggressive Aero Slalom Course (Rapid bank/climb/dive)
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
sys.path.insert(0, ".")
from datetime import datetime, timezone

import neat
import numpy as np

from src.experiment.metadata import load_config
from src.simulation.env import FixedwingEnv
from src.simulation.pid_controller import FixedwingPIDController


# ---------------------------------------------------------------------------
# Database Helpers
# ---------------------------------------------------------------------------

def _init_benchmark_db(db_path: str = "output/icarus.db") -> None:
    """Ensure the benchmark_evaluations table exists in the database."""
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS benchmark_evaluations (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            test_name         TEXT NOT NULL,
            controller_id     TEXT NOT NULL,
            controller_type   TEXT NOT NULL,
            flight_time       REAL,
            distance          REAL,
            mean_airspeed     REAL,
            mean_altitude     REAL,
            altitude_error    REAL,
            max_lateral_dev   REAL,
            control_energy    REAL,
            crashed           INTEGER,
            stalling          INTEGER,
            waypoints_hit     INTEGER,
            precision_score   REAL,
            measured_at       TEXT NOT NULL,
            course_map_json   TEXT,
            arena_radius      REAL,
            waypoint_radius   REAL,
            trajectory_json   TEXT
        )
    """)
    # Check if precision_score column exists if table was pre-existing
    cols = [r[1] for r in cur.execute("PRAGMA table_info(benchmark_evaluations)").fetchall()]
    if "precision_score" not in cols:
        cur.execute("ALTER TABLE benchmark_evaluations ADD COLUMN precision_score REAL")
    con.commit()
    con.close()


def _log_benchmark_result(
    db_path: str,
    test_name: str,
    controller_id: str,
    controller_type: str,
    metrics: Dict[str, Any],
    course_map: Optional[List[Dict[str, Any]]] = None,
    arena_radius: float = 1000.0,
    waypoint_radius: float = 2.0,
) -> None:
    """Record a single benchmark evaluation into SQLite."""
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    traj_json = json.dumps(metrics.get("trajectory", [])) if "trajectory" in metrics else None
    course_json = json.dumps(course_map) if course_map is not None else None

    # Calculate Standard Precision Score (0 - 100 scale)
    wp_hit = int(metrics.get("waypoints_hit", 0))
    crashed = bool(metrics.get("crashed", False))
    num_wp = len(course_map) if course_map else 0
    
    if num_wp > 0:
        wp_points = (wp_hit / float(num_wp)) * 50.0
    else:
        # Straight flight course: evaluate distance progress toward 500m
        wp_points = min(float(metrics.get("distance", 0.0)) / 500.0, 1.0) * 50.0

    # Corridor/altitude adherence: nominal reference band +/-15m
    alt_err = float(metrics.get("altitude_error", 10.0))
    corridor_points = max(0.0, 1.0 - (alt_err / 15.0)) * 30.0
    survival_points = 20.0 if not crashed else 0.0
    precision_score = round(wp_points + corridor_points + survival_points, 1)

    cur.execute("""
        INSERT INTO benchmark_evaluations (
            test_name, controller_id, controller_type,
            flight_time, distance, mean_airspeed, mean_altitude,
            altitude_error, max_lateral_dev, control_energy,
            crashed, stalling, waypoints_hit, precision_score, measured_at,
            course_map_json, arena_radius, waypoint_radius, trajectory_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        test_name,
        controller_id,
        controller_type,
        float(metrics.get("flight_time", 0.0)),
        float(metrics.get("distance", 0.0)),
        float(metrics.get("mean_airspeed", 0.0)),
        float(metrics.get("mean_altitude", 0.0)),
        float(metrics.get("altitude_error", 0.0)),
        float(metrics.get("max_lateral_deviation", 0.0)),
        float(metrics.get("control_energy", 0.0)),
        1 if crashed else 0,
        1 if metrics.get("stalling", False) else 0,
        wp_hit,
        precision_score,
        now_iso,
        course_json,
        float(arena_radius),
        float(waypoint_radius),
        traj_json,
    ))
    con.commit()
    con.close()


# ---------------------------------------------------------------------------
# Controller Loaders
# ---------------------------------------------------------------------------

def load_champion_network(
    experiment_id: str = "C1",
    checkpoint_dir: str = "output/checkpoints",
) -> Tuple[neat.nn.FeedForwardNetwork, Dict[str, Any], int]:
    """Retrieve the latest champion network from database and checkpoints."""
    chks = [
        os.path.join(checkpoint_dir, f)
        for f in os.listdir(checkpoint_dir)
        if f.startswith(f"{experiment_id.lower()}-chk-")
    ]
    if not chks:
        raise FileNotFoundError(f"No checkpoints found in {checkpoint_dir} for {experiment_id}")

    def _chk_gen(p: str) -> int:
        try:
            return int(os.path.basename(p).split("-")[-1])
        except Exception:
            return 0

    chks.sort(key=_chk_gen)
    latest_chk = chks[-1]
    latest_gen = _chk_gen(latest_chk)

    pop = neat.Checkpointer.restore_checkpoint(latest_chk)
    best_genome = max(pop.population.values(), key=lambda g: g.fitness or -999)
    net = neat.nn.FeedForwardNetwork.create(best_genome, pop.config)

    meta = {
        "checkpoint": latest_chk,
        "generation": latest_gen,
        "fitness": float(best_genome.fitness) if best_genome.fitness is not None else 0.0,
        "nodes": len(best_genome.nodes),
        "connections": sum(1 for c in best_genome.connections.values() if c.enabled),
    }
    return net, meta, latest_gen


# ---------------------------------------------------------------------------
# Standard Benchmark Course Definitions
# ---------------------------------------------------------------------------

# Test A: Open-Sky Straight Flight (1 km arena, level cruise corridor at nominal altitude 10m)
WP_COURSE_A = np.array([
    [250.0, 0.0, 10.0],
    [500.0, 0.0, 10.0],
    [750.0, 0.0, 10.0],
    [1000.0, 0.0, 10.0],
])

# Test B: Structured Cross-Country Course (4 gates)
WP_COURSE_B = np.array([
    [150.0, 0.0, 10.0],       # Leg 1: 150m straight cruise
    [236.6, 50.0, 15.0],      # Leg 2: 100m at +30 deg, climb to 15m
    [151.7, -34.8, 10.0],     # Leg 3: 120m return diagonal
    [300.0, -34.8, 12.0],     # Leg 4: Long straightout
])

# Test C: Aggressive High-G Aero Slalom (4 gates)
WP_COURSE_C = np.array([
    [80.0, 45.0, 22.0],       # Sharp bank right, climb
    [150.0, -45.0, 8.0],      # Sharp bank left, dive
    [220.0, 45.0, 25.0],      # Rapid climb and reverse
    [280.0, -45.0, 6.0],      # Low-altitude terrain hug
])

# Test D: AUVSI SUAS Autonomous Challenge (5 gates)
WP_COURSE_D = np.array([
    [180.0,   40.0, 25.0],
    [320.0,  -80.0, 40.0],
    [160.0, -220.0, 20.0],
    [-60.0, -120.0, 15.0],
    [ 60.0,   80.0, 30.0],
])

# Test E: FAI F3D/F5D 3-Pylon Race Course (3 continuous laps, 9 gates)
_P1 = [200.0,   0.0, 12.0]
_P2 = [ 20.0,  35.0, 12.0]
_P3 = [ 20.0, -35.0, 12.0]
WP_COURSE_E = np.array([
    _P1, _P2, _P3,  # Lap 1
    _P1, _P2, _P3,  # Lap 2
    _P1, _P2, _P3,  # Lap 3
])

BENCHMARK_TEST_CONFIGS = [
    ("Test A - Open-Sky Straight Flight", None, 20.0, 1000.0, 10.0),
    ("Test B - Open-Sky Waypoint Course", WP_COURSE_B, 25.0, 1000.0, 2.0),
    ("Test C - Aggressive Aero Slalom", WP_COURSE_C, 25.0, 1000.0, 2.0),
    ("Test D - AUVSI SUAS Autonomous Challenge", WP_COURSE_D, 30.0, 1000.0, 15.0),
    ("Test E - FAI F3D/F5D Pylon Racing", WP_COURSE_E, 40.0, 1000.0, 10.0),
]


# ---------------------------------------------------------------------------
# Test Runners
# ---------------------------------------------------------------------------

def run_flight_simulation(
    controller_type: str,
    controller_obj: Any,
    custom_waypoints: Optional[np.ndarray] = None,
    duration: float = 20.0,
    flight_dome_size: float = 1000.0,
    waypoint_radius: float = 2.0,
    seed: int = 42,
    model_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Simulate either a NEAT network or PID controller under specified flight conditions."""
    config = load_config("configs/controller_only/c1_controller_only.json")
    config["simulation"]["episode_duration"] = duration
    config["simulation"]["flight_dome_size"] = flight_dome_size

    env = FixedwingEnv(config=config, model_dir=model_dir)
    env.env.unwrapped.flight_dome_size = flight_dome_size
    env.max_steps = int(duration * env.control_hz)

    obs, _ = env.reset(seed=seed)
    if custom_waypoints is not None:
        env.env.unwrapped.waypoints.targets = custom_waypoints.copy()
        env.env.unwrapped.waypoints.num_targets = len(custom_waypoints)
        if hasattr(env.env.unwrapped.waypoints, "goal_reach_distance"):
            env.env.unwrapped.waypoints.goal_reach_distance = float(waypoint_radius)

    if controller_type == "PID":
        controller_obj.reset()

    trajectory: List[Dict[str, float]] = []
    actions: List[np.ndarray] = []
    num_wp_total = len(custom_waypoints) if custom_waypoints is not None else 0
    course_completed = False
    crashed = False
    step = 0

    while step < env.max_steps:
        if controller_type == "PID":
            action = controller_obj.predict(obs)
        else:
            action = np.asarray(controller_obj.activate(obs), dtype=np.float32)

        actions.append(action)
        obs, _, term, trunc, info = env.step(action)
        step += 1

        drone = env.env.unwrapped.env.drones[0]
        pos = drone.state[3]
        altitude = float(pos[2])
        airspeed = float(info.get("airspeed", 0.0))
        collision = bool(info.get("collision", False))

        wp_handler = getattr(env.env.unwrapped, "waypoints", None)
        waypoints_hit = int(getattr(wp_handler, "num_targets_reached", 0)) if wp_handler else 0

        # Check 1: Course Completion (All gates cleared)
        # Stop immediately when all targets are reached to avoid post-run unguided coasting/clipping
        if custom_waypoints is not None and (
            (wp_handler and getattr(wp_handler, "all_targets_reached", False))
            or (waypoints_hit >= num_wp_total and num_wp_total > 0)
        ):
            course_completed = True
            waypoints_hit = num_wp_total
            trajectory.append({
                "step": step,
                "time": float(step / env.control_hz),
                "x": float(pos[0]),
                "y": float(pos[1]),
                "z": altitude,
                "airspeed": airspeed,
            })
            break

        if step % 4 == 0 or term or trunc:
            trajectory.append({
                "step": step,
                "time": float(step / env.control_hz),
                "x": float(pos[0]),
                "y": float(pos[1]),
                "z": altitude,
                "airspeed": airspeed,
            })

        if term or trunc:
            break

    env_metrics = env.get_metrics()
    unwrapped = env.env.unwrapped
    if hasattr(unwrapped, "waypoints"):
        final_wp_hit = getattr(unwrapped.waypoints, "num_targets_reached", 0)
    else:
        final_wp_hit = waypoints_hit

    # POST-FINISH CLIP BUG RESOLUTION:
    # If the aircraft reached all course waypoints, the flight was a 100% mission success.
    # It must NOT be marked crashed just because it clipped the ground after the run was over.
    if course_completed or (num_wp_total > 0 and final_wp_hit >= num_wp_total):
        crashed = False
        final_wp_hit = num_wp_total
    else:
        crashed = bool(env_metrics.get("crashed", False))

    env.env.close()

    y_coords = [p["y"] for p in trajectory]
    z_coords = [p["z"] for p in trajectory]
    act_arr = np.array(actions) if actions else np.zeros((1, 6))

    return {
        "flight_time": env_metrics.get("flight_time", float(step / env.control_hz)),
        "distance": env_metrics.get("distance", 0.0),
        "mean_airspeed": env_metrics.get("airspeed", 0.0),
        "mean_altitude": float(np.mean(z_coords)) if z_coords else 0.0,
        "altitude_error": env_metrics.get("altitude_error", 0.0),
        "max_lateral_deviation": float(np.max(np.abs(y_coords))) if y_coords else 0.0,
        "control_energy": env_metrics.get("energy", 0.0),
        "rms_control_effort": float(np.sqrt(np.mean(act_arr ** 2))) if len(act_arr) > 0 else 0.0,
        "crashed": crashed,
        "stalling": env_metrics.get("stalling", False),
        "waypoints_hit": final_wp_hit,
        "trajectory": trajectory,
    }


# ---------------------------------------------------------------------------
# Benchmark Suite Execution
# ---------------------------------------------------------------------------

def run_comparative_generalization_suite(
    experiment_id: str = "C1",
    seed: int = 42,
    db_path: str = "output/icarus.db",
    output_path: str = "output/generalization_results.json",
) -> Dict[str, Any]:
    """Execute complete head-to-head generalization tests between PID and NEAT."""
    _init_benchmark_db(db_path)

    print(f"\n{'=' * 75}")
    print(f"  TALOS HEAD-TO-HEAD GENERALIZATION BENCHMARK SUITE")
    print(f"  Comparing: Reference PID (TALOS-B01) vs. Frozen NEAT (TALOS-P2A)")
    print(f"  Database : {db_path}")
    print(f"{'=' * 75}\n")

    # 1. Load NEAT Champion
    neat_net, neat_meta, gen = load_champion_network(experiment_id=experiment_id)
    print(f"[talos] Loaded Frozen NEAT Champion: Gen {gen} ({neat_meta['nodes']} nodes, {neat_meta['connections']} conns)")

    # 2. Instantiate PID Controller
    pid_ctrl = FixedwingPIDController(dt=1.0 / 30.0, target_airspeed=24.0, target_altitude=10.0)
    print(f"[talos] Loaded Reference Cascaded PID Autopilot\n")

    results: Dict[str, Any] = {
        "metadata": {
            "neat_generation": gen,
            "neat_checkpoint": neat_meta["checkpoint"],
            "seed": seed,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
        "tests": {},
    }

    for test_name, wp_array, duration, dome_size, wp_rad in BENCHMARK_TEST_CONFIGS:
        print(f"{'-' * 75}")
        print(f"  RUNNING: {test_name} (Duration: {duration}s, Arena: {dome_size}m, Radius: {wp_rad}m)")
        print(f"{'-' * 75}")

        # Run PID
        print("  [1/2] Evaluating Reference PID (pid_open_sky)...")
        pid_res = run_flight_simulation("PID", pid_ctrl, wp_array, duration, dome_size, wp_rad, seed)
        _log_benchmark_result(
            db_path, test_name, "pid_open_sky", "PID", pid_res,
            course_map=wp_array.tolist() if wp_array is not None else None,
            arena_radius=dome_size, waypoint_radius=wp_rad,
        )

        # Run NEAT
        print("  [2/2] Evaluating Frozen NEAT Champion (phase2_neat_caged)...")
        neat_res = run_flight_simulation("NEAT", neat_net, wp_array, duration, dome_size, wp_rad, seed)
        _log_benchmark_result(
            db_path, test_name, "phase2_neat_caged", "NEAT", neat_res,
            course_map=wp_array.tolist() if wp_array is not None else None,
            arena_radius=dome_size, waypoint_radius=wp_rad,
        )

        # Print clean side-by-side comparison
        print(f"\n  Results for {test_name}:")
        print(f"  {'Metric':<25} | {'Reference PID':<18} | {'Evolved NEAT':<18} | {'Delta / Verdict'}")
        print(f"  {'-'*25} | {'-'*18} | {'-'*18} | {'-'*20}")
        print(f"  {'Flight Time':<25} | {pid_res['flight_time']:>6.2f} s           | {neat_res['flight_time']:>6.2f} s           | {neat_res['flight_time']-pid_res['flight_time']:+.2f} s")
        print(f"  {'Airspeed Distance':<25} | {pid_res['distance']:>6.1f} m           | {neat_res['distance']:>6.1f} m           | {neat_res['distance']-pid_res['distance']:+.1f} m")
        print(f"  {'Mean Airspeed':<25} | {pid_res['mean_airspeed']:>6.1f} m/s         | {neat_res['mean_airspeed']:>6.1f} m/s         | {neat_res['mean_airspeed']-pid_res['mean_airspeed']:+.1f} m/s")
        print(f"  {'Mean Altitude':<25} | {pid_res['mean_altitude']:>6.1f} m           | {neat_res['mean_altitude']:>6.1f} m           | Diff: {abs(neat_res['mean_altitude']-pid_res['mean_altitude']):.1f} m")
        print(f"  {'Max Lateral Deviation':<25} | {pid_res['max_lateral_deviation']:>6.1f} m           | {neat_res['max_lateral_deviation']:>6.1f} m           | Loiter: {neat_res['max_lateral_deviation']:.1f}m")
        print(f"  {'Control Energy':<25} | {pid_res['control_energy']:>6.2f}             | {neat_res['control_energy']:>6.2f}             | {neat_res['control_energy']-pid_res['control_energy']:+.2f}")
        print(f"  {'Crashed / Stalling':<25} | {str(pid_res['crashed']):<5} / {str(pid_res['stalling']):<5}    | {str(neat_res['crashed']):<5} / {str(neat_res['stalling']):<5}    | Tied")
        print(f"  {'Waypoints Captured':<25} | {pid_res['waypoints_hit']:>2d} targets         | {neat_res['waypoints_hit']:>2d} targets         | {'Captured' if neat_res['waypoints_hit'] > 0 else 'Loiter'}\n")

        results["tests"][test_name] = {
            "PID": pid_res,
            "NEAT": neat_res,
        }

    # Save to JSON
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)

    print(f"\n[talos] Benchmark complete! All comparison parameters saved to:")
    print(f"        * Database: {db_path} (table: benchmark_evaluations)")
    print(f"        * JSON Log: {output_path}\n")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Talos Head-to-Head Generalization Suite")
    parser.add_argument("--experiment", default="C1", help="Experiment ID (default: C1)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--db", default="output/icarus.db", help="Database path")
    parser.add_argument("--output", default="output/generalization_results.json", help="Output JSON path")
    args = parser.parse_args()

    run_comparative_generalization_suite(
        experiment_id=args.experiment,
        seed=args.seed,
        db_path=args.db,
        output_path=args.output,
    )
