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

# Connect to database and find the latest completed generation champion
db_path = "output/icarus.db"
con = sqlite3.connect(db_path)
cur = con.cursor()
cur.execute("SELECT max(generation) FROM generations WHERE experiment_id = 'TALOS-P3B'")
max_gen = cur.fetchone()[0]
cur.execute(
    "SELECT individual_index, generation, fitness, morphology_json, distance "
    "FROM individuals WHERE experiment_id = 'TALOS-P3B' AND generation = ? "
    "ORDER BY fitness DESC LIMIT 1",
    (max_gen,)
)
row = cur.fetchone()
ind_idx, gen_num, fit_score, morph_str, train_dist = row

p3b_model_dir = os.path.abspath(f"models/TALOS-P3B/gen{gen_num:03d}/ind{ind_idx:03d}")
if not os.path.isdir(p3b_model_dir):
    raise FileNotFoundError(f"Model dir not found at {p3b_model_dir}")

print("=" * 75)
print(f"[benchmark] BENCHMARKING LATEST TALOS-P3B GENERATION: Gen {gen_num} (Individual {ind_idx})")
print(f"[benchmark] Training Fitness: {fit_score:.4f} | Training Distance: {train_dist:.1f}m")
print(f"[benchmark] Model Directory: {p3b_model_dir}")
print(f"[benchmark] Morphology: {morph_str}")
print("=" * 75)

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

eval_configs = [
    (f"p3b_gen{gen_num:03d}_pid", "PID", pid_ctrl),
    (f"p3b_gen{gen_num:03d}_neat_gen300", "NEAT", neat_net),
]

all_results = {}

for ctrl_id, ctrl_type, ctrl_obj in eval_configs:
    all_results[ctrl_id] = {}
    print(f"\n--- EVALUATING: {ctrl_id} ({ctrl_type}) on P3B Gen {gen_num} Body ---")

    for test_name, wp_arr, duration, dome in tests:
        res = run_flight_simulation(
            controller_type=ctrl_type,
            controller_obj=ctrl_obj,
            custom_waypoints=wp_arr,
            duration=duration,
            flight_dome_size=dome,
            seed=42,
            model_dir=p3b_model_dir,
        )
        all_results[ctrl_id][test_name] = res

        t = res["flight_time"]
        d = res["distance"]
        spd = res["mean_airspeed"]
        alt = res["mean_altitude"]
        lat = res["max_lateral_deviation"]
        cr = res["crashed"]
        wp_hit = res["waypoints_hit"]
        print(f"  {test_name:<36} | Time: {t:4.1f}s | Dist: {d:6.1f}m | Spd: {spd:4.1f}m/s | Alt: {alt:4.1f}m | LatDev: {lat:5.1f}m | Crash: {str(cr):<5} | Gates: {wp_hit}/4")

        course_json = json.dumps([[float(x) for x in row] for row in wp_arr]) if wp_arr is not None else None
        traj_json = json.dumps(res.get("trajectory", []))
        now_str = datetime.now(timezone.utc).isoformat()

        cur.execute("""
            INSERT INTO benchmark_evaluations (
                test_name, controller_id, controller_type, flight_time, distance,
                mean_airspeed, mean_altitude, altitude_error, max_lateral_dev,
                control_energy, crashed, stalling, waypoints_hit, measured_at,
                course_map_json, arena_radius, waypoint_radius, trajectory_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            test_name,
            ctrl_id,
            ctrl_type,
            res["flight_time"],
            res["distance"],
            res["mean_airspeed"],
            res["mean_altitude"],
            abs(res["mean_altitude"] - 10.0),
            res["max_lateral_deviation"],
            res["control_energy"],
            1 if res["crashed"] else 0,
            1 if res["stalling"] else 0,
            res["waypoints_hit"],
            now_str,
            course_json,
            1000.0,
            2.0,
            traj_json,
        ))
        con.commit()

con.close()
print("\n[benchmark] All 6 evaluations committed to output/icarus.db successfully!")

# Regenerate 3D viewer
try:
    from src.dashboard.generate_3d_viewer import generate_viewer
    generate_viewer()
except Exception as e:
    print(f"[benchmark] 3D viewer regeneration error: {e}")

# Regenerate Lab Notebook
try:
    generate_lab_notebook()
except Exception as e:
    print(f"[benchmark] Lab notebook regeneration error: {e}")
