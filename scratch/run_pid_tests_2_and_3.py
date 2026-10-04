import sys
sys.path.insert(0, ".")

import json
import sqlite3
import numpy as np
from datetime import datetime, timezone
from src.experiment.metadata import load_config
from src.simulation.env import FixedwingEnv
from src.simulation.pid_controller import FixedwingPIDController
from src.experiment.generate_notebook import generate_lab_notebook

db_path = "output/icarus.db"

# Ensure benchmark_evaluations table exists
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
        measured_at       TEXT NOT NULL
    )
""")
con.commit()
con.close()


def run_pid_on_course(test_name: str, course_waypoints: np.ndarray, duration: float = 25.0, seed: int = 42):
    print(f"\n{'=' * 65}")
    print(f"  RUNNING PID BENCHMARK: {test_name}")
    print(f"  Duration: {duration}s | Arena: 1000m | Seed: {seed}")
    print(f"{'=' * 65}")

    config = load_config("configs/controller_only/c1_controller_only.json")
    config["simulation"]["episode_duration"] = duration
    config["simulation"]["flight_dome_size"] = 1000.0

    env = FixedwingEnv(config=config)
    env.env.unwrapped.flight_dome_size = 1000.0
    env.max_steps = int(duration * env.control_hz)

    obs, _ = env.reset(seed=seed)
    env.env.unwrapped.waypoints.targets = course_waypoints.copy()
    env.env.unwrapped.waypoints.num_targets = len(course_waypoints)

    pid_ctrl = FixedwingPIDController(dt=1.0 / env.control_hz, target_airspeed=24.0, target_altitude=10.0)
    pid_ctrl.reset()

    trajectory = []
    actions = []
    step = 0

    while step < env.max_steps:
        action = pid_ctrl.predict(obs)
        actions.append(action)
        obs, _, term, trunc, info = env.step(action)
        step += 1

        drone = env.env.unwrapped.env.drones[0]
        pos = drone.state[3]
        if step % 10 == 0 or term or trunc:
            trajectory.append({
                "step": step,
                "time": float(step / env.control_hz),
                "x": float(pos[0]),
                "y": float(pos[1]),
                "z": float(pos[2]),
                "airspeed": float(info.get("airspeed", 0.0)),
            })
            if step % 60 == 0:
                print(f"  Step {step:4d} ({step/env.control_hz:5.1f}s): pos=({pos[0]:6.1f}, {pos[1]:6.1f}, {pos[2]:6.1f}) | speed={info.get('airspeed', 0.0):4.1f}m/s")
        if term or trunc:
            break

    env_metrics = env.get_metrics()
    unwrapped = env.env.unwrapped
    waypoints_hit = getattr(unwrapped.waypoints, "num_targets_reached", 0) if hasattr(unwrapped, "waypoints") else 0
    env.env.close()

    y_coords = [p["y"] for p in trajectory]
    z_coords = [p["z"] for p in trajectory]
    act_arr = np.array(actions) if actions else np.zeros((1, 6))

    result = {
        "flight_time": env_metrics.get("flight_time", 0.0),
        "distance": env_metrics.get("distance", 0.0),
        "mean_airspeed": env_metrics.get("airspeed", 0.0),
        "mean_altitude": float(np.mean(z_coords)) if z_coords else 0.0,
        "altitude_error": env_metrics.get("altitude_error", 0.0),
        "max_lateral_deviation": float(np.max(np.abs(y_coords))) if y_coords else 0.0,
        "control_energy": env_metrics.get("energy", 0.0),
        "rms_control_effort": float(np.sqrt(np.mean(act_arr ** 2))) if len(act_arr) > 0 else 0.0,
        "crashed": env_metrics.get("crashed", False),
        "stalling": env_metrics.get("stalling", False),
        "waypoints_hit": waypoints_hit,
    }

    # Save to SQLite
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cur.execute("""
        INSERT INTO benchmark_evaluations (
            test_name, controller_id, controller_type,
            flight_time, distance, mean_airspeed, mean_altitude,
            altitude_error, max_lateral_dev, control_energy,
            crashed, stalling, waypoints_hit, measured_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        test_name,
        "pid_open_sky",
        "PID",
        result["flight_time"],
        result["distance"],
        result["mean_airspeed"],
        result["mean_altitude"],
        result["altitude_error"],
        result["max_lateral_deviation"],
        result["control_energy"],
        1 if result["crashed"] else 0,
        1 if result["stalling"] else 0,
        int(result["waypoints_hit"]),
        now_iso,
    ))
    con.commit()
    con.close()

    print(f"\n  Summary for {test_name}:")
    print(f"    * Flight Time    : {result['flight_time']:.2f} s")
    print(f"    * Path Distance  : {result['distance']:.1f} m")
    print(f"    * Airspeed       : {result['mean_airspeed']:.1f} m/s")
    print(f"    * Mean Altitude  : {result['mean_altitude']:.1f} m (Error: {result['altitude_error']:.2f}m)")
    print(f"    * Max Lateral Dev: {result['max_lateral_deviation']:.1f} m")
    print(f"    * Control Energy : {result['control_energy']:.2f}")
    print(f"    * Waypoints Hit  : {result['waypoints_hit']} / {len(course_waypoints)}")
    print(f"    * Crashed        : {result['crashed']}")
    return result


# Define Test 2 Course: Multi-Leg Cross-Country
wp_course_b = np.array([
    [150.0, 0.0, 10.0],
    [236.6, 50.0, 15.0],
    [151.7, -34.8, 10.0],
    [300.0, -34.8, 12.0],
])

# Define Test 3 Course: Aggressive Aero Slalom
wp_course_c = np.array([
    [80.0, 45.0, 22.0],
    [150.0, -45.0, 8.0],
    [220.0, 45.0, 25.0],
    [280.0, -45.0, 6.0],
])

print("\nStarting PID Pre-Benchmark Runs for Test 2 and Test 3...")
res_b = run_pid_on_course("Test 2 — Open-Sky Waypoint Course", wp_course_b, duration=25.0)
res_c = run_pid_on_course("Test 3 — Aggressive Aero Slalom", wp_course_c, duration=25.0)

generate_lab_notebook()
print("\n[talos] Both PID tests successfully executed and saved to output/icarus.db!")
