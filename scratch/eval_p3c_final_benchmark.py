import sys
sys.path.insert(0, ".")

import os
import json
import sqlite3
from datetime import datetime, timezone
import neat
import numpy as np

from src.simulation.generalization_benchmark import run_flight_simulation
from src.simulation.pid_controller import FixedwingPIDController
from src.experiment.generate_notebook import generate_lab_notebook

# Paths to models
p3c_champ_dir = os.path.abspath("models/TALOS-P3C/gen023/ind023")

with open(os.path.join(p3c_champ_dir, "morphology.json"), "r") as f:
    champ_morph = json.load(f)

print("=" * 80)
print(f"[benchmark] EVALUATING TALOS-P3C ALL-TIME CHAMPION (Gen 23, Ind 23)")
print(f"[benchmark] Model Path: {p3c_champ_dir}")
print(f"[benchmark] Morphology: {champ_morph}")
print("=" * 80)

# Controllers
pid_ctrl = FixedwingPIDController(dt=1.0 / 30.0, target_airspeed=24.0, target_altitude=10.0)

chk_path = "output/checkpoints/talos-p2b-chk-300"
pop = neat.Checkpointer.restore_checkpoint(chk_path)
best_genome = max(pop.population.values(), key=lambda g: g.fitness or -999)
neat_net = neat.nn.FeedForwardNetwork.create(best_genome, pop.config)

# Test Courses
wp_course_b = np.array([
    [150.0, 0.0, 10.0],
    [236.6, 50.0, 15.0],
    [151.7, -34.8, 10.0],
    [300.0, -34.8, 12.0],
])

wp_course_c = np.array([
    [80.0, 45.0, 22.0],
    [150.0, -45.0, 8.0],
    [220.0, 45.0, 25.0],
    [280.0, -45.0, 6.0],
])

tests = [
    ("Test A - Open-Sky Straight Flight", None, 20.0, 1000.0),
    ("Test B - Open-Sky Waypoint Course", wp_course_b, 25.0, 1000.0),
    ("Test C - Aggressive Aero Slalom", wp_course_c, 25.0, 1000.0),
]

eval_runs = [
    ("p3c_champ_pid", "PID", pid_ctrl, p3c_champ_dir),
    ("p3c_champ_neat_gen300", "NEAT", neat_net, p3c_champ_dir),
]

db_path = "output/icarus.db"
con = sqlite3.connect(db_path)
cur = con.cursor()

results = []

for ctrl_id, ctrl_type, ctrl_obj, model_dir in eval_runs:
    print(f"\n---> Evaluating {ctrl_id} ({ctrl_type}) on P3C Body")
    for test_name, wp_arr, duration, dome in tests:
        res = run_flight_simulation(
            controller_type=ctrl_type,
            controller_obj=ctrl_obj,
            custom_waypoints=wp_arr,
            duration=duration,
            flight_dome_size=dome,
            seed=42,
            model_dir=model_dir,
        )

        t = res["flight_time"]
        d = res["distance"]
        spd = res["mean_airspeed"]
        alt = res["mean_altitude"]
        lat = res["max_lateral_deviation"]
        cr = res["crashed"]
        wp_hit = res["waypoints_hit"]
        energy = res.get("control_energy", 0.0)

        print(f"  {test_name:<36} | Time: {t:4.1f}s | Dist: {d:6.1f}m | Spd: {spd:4.1f}m/s | Alt: {alt:4.1f}m | LatDev: {lat:5.1f}m | Crash: {str(cr):<5} | Gates: {wp_hit}/4")

        course_json = json.dumps([[float(x) for x in row] for row in wp_arr]) if wp_arr is not None else None
        traj_json = json.dumps(res.get("trajectory", []))
        now_str = datetime.now(timezone.utc).isoformat()

        cur.execute("""
            INSERT INTO benchmark_evaluations (
                test_name, controller_id, controller_type, flight_time, distance,
                mean_airspeed, mean_altitude, altitude_error, max_lateral_dev,
                control_energy, crashed, stalling, waypoints_hit, measured_at,
                arena_radius, waypoint_radius, course_map_json, trajectory_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            test_name, ctrl_id, ctrl_type, t, d,
            spd, alt, res.get("altitude_error", 0.0), lat,
            energy, int(cr), int(res.get("stalling", False)), wp_hit, now_str,
            dome, 2.0, course_json, traj_json
        ))
        con.commit()

        results.append({
            "test": test_name,
            "controller_id": ctrl_id,
            "controller_type": ctrl_type,
            "time": t,
            "dist": d,
            "speed": spd,
            "altitude": alt,
            "lat_dev": lat,
            "crashed": cr,
            "waypoints": wp_hit,
        })

con.close()

print("\n" + "=" * 80)
print("BENCHMARK EVALUATIONS COMMITTED TO ICARUS.DB")
print("=" * 80)

# Generate lab notebook
generate_lab_notebook()
print("[benchmark] Updated docs/LAB_NOTEBOOK.md with new benchmark runs.")
