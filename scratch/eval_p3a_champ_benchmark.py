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

# 1. Paths
p3a_model_dir = os.path.abspath("models/TALOS-P3A/gen099/ind001")
if not os.path.isdir(p3a_model_dir):
    raise FileNotFoundError(f"P3A champion model directory not found at {p3a_model_dir}")

print(f"[benchmark] Target Airframe: TALOS-P3A Gen 99/100 Champion at {p3a_model_dir}")
with open(os.path.join(p3a_model_dir, "morphology.json"), "r") as f:
    morph_data = json.load(f)
print(f"[benchmark] Morphology parameters: {morph_data}")

# 2. Controllers
# Controller A: Reference PID
pid_ctrl = FixedwingPIDController(dt=1.0 / 30.0, target_airspeed=24.0, target_altitude=10.0)

# Controller B: Frozen Gen 300 NEAT Champion
chk_path = "output/checkpoints/talos-p2b-chk-300"
pop = neat.Checkpointer.restore_checkpoint(chk_path)
best_genome = max(pop.population.values(), key=lambda g: g.fitness or -999)
neat_net = neat.nn.FeedForwardNetwork.create(best_genome, pop.config)
print(f"[benchmark] Loaded NEAT Gen 300 Champion ({len(best_genome.nodes)} nodes, {sum(1 for c in best_genome.connections.values() if c.enabled)} connections)")

# 3. Test Course Definitions
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
    ("p3a_champ_pid", "PID", pid_ctrl),
    ("p3a_champ_neat_gen300", "NEAT", neat_net),
]

all_results = {}
db_path = "output/icarus.db"
con = sqlite3.connect(db_path)
cur = con.cursor()

for ctrl_id, ctrl_type, ctrl_obj in eval_configs:
    all_results[ctrl_id] = {}
    print(f"\n{'=' * 75}")
    print(f"  BENCHMARKING: {ctrl_id} ({ctrl_type}) on P3A Evolved Airframe")
    print(f"{'=' * 75}")

    for test_name, wp_arr, duration, dome in tests:
        print(f"\n--> Running {test_name} (duration={duration}s)...")
        res = run_flight_simulation(
            controller_type=ctrl_type,
            controller_obj=ctrl_obj,
            custom_waypoints=wp_arr,
            duration=duration,
            flight_dome_size=dome,
            seed=42,
            model_dir=p3a_model_dir,
        )
        all_results[ctrl_id][test_name] = res

        t = res["flight_time"]
        d = res["distance"]
        spd = res["mean_airspeed"]
        alt = res["mean_altitude"]
        lat = res["max_lateral_deviation"]
        cr = res["crashed"]
        wp_hit = res["waypoints_hit"]
        print(f"    Time: {t:.2f}s / {duration}s | Dist: {d:.1f}m | Speed: {spd:.1f}m/s | Alt: {alt:.1f}m | LatDev: {lat:.1f}m | Crashed: {cr} | WP Hit: {wp_hit}")

        # Persist to database
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
            test_name, ctrl_id, ctrl_type, res["flight_time"], res["distance"],
            res["mean_airspeed"], res["mean_altitude"], abs(res["mean_altitude"] - 10.0), res["max_lateral_deviation"],
            res["control_energy"], 1 if res["crashed"] else 0, 1 if res["stalling"] else 0, res["waypoints_hit"],
            now_str, course_json, 1000.0, 2.0, traj_json,
        ))
        con.commit()

con.close()
print("\n[benchmark] All evaluations successfully saved to benchmark_evaluations in output/icarus.db")

# Save summary json
summary_out = {}
for cid in all_results:
    summary_out[cid] = {}
    for tname, res in all_results[cid].items():
        summary_out[cid][tname] = {
            m: res[m] for m in [
                "flight_time", "distance", "mean_airspeed", "mean_altitude",
                "max_lateral_deviation", "control_energy", "crashed", "stalling", "waypoints_hit"
            ]
        }

with open("scratch/p3a_benchmark_results.json", "w", encoding="utf-8") as f:
    json.dump(summary_out, f, indent=2)

try:
    generate_lab_notebook()
    print("[benchmark] Updated docs/LAB_NOTEBOOK.md")
except Exception as e:
    print("[benchmark] Notebook update skipped:", e)
