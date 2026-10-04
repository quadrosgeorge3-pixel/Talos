import os
import sys
sys.path.insert(0, ".")
import json
import sqlite3
import shutil
import neat
import numpy as np

from src.genome.morphology import MorphologyGenome, DEFAULT_MORPHOLOGY
from src.genome.urdf_gen import generate_model_files
from src.simulation.generalization_benchmark import run_flight_simulation

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

test_configs = [
    ("Test A - Straight Flight (1 km)", None, 20.0, 1000.0),
    ("Test B - Waypoint Course", wp_course_b, 25.0, 1000.0),
    ("Test C - Aggressive Slalom", wp_course_c, 25.0, 1000.0),
]

# 1. Evaluate P4 Gen 105 Champion
chk_path = "output/checkpoints/talos-p4-ultima-chk-105"
morph_path = "output/checkpoints/talos-p4-ultima-morph-105.json"

pop = neat.Checkpointer.restore_checkpoint(chk_path)
best_genome = max(pop.population.values(), key=lambda g: g.fitness or -999)
net = neat.nn.FeedForwardNetwork.create(best_genome, pop.config)

with open(morph_path, "r", encoding="utf-8") as f:
    morph_dict = json.load(f)
best_gid = str(best_genome.key)
m_params = morph_dict.get(best_gid, list(morph_dict.values())[0])
morph_p4_105 = MorphologyGenome.from_dict(m_params)

model_dir = "models/casual_bench_p4_gen105"
generate_model_files(morph_p4_105, model_dir)

p4_results = {}
for tname, wps, dur, dome in test_configs:
    res = run_flight_simulation(
        controller_type="NEAT",
        controller_obj=net,
        custom_waypoints=wps,
        duration=dur,
        flight_dome_size=dome,
        seed=42,
        model_dir=model_dir
    )
    p4_results[tname] = res

# Cleanup model files so we don't leave clutter
shutil.rmtree(model_dir, ignore_errors=True)

# 2. Pull P3C Gen 300 and Default PID from icarus.db
conn = sqlite3.connect("output/icarus.db")
c = conn.cursor()

def get_controller_benchmarks(ctrl_id):
    rows = c.execute("""
        SELECT test_name, flight_time, distance, mean_airspeed, waypoints_hit, crashed
        FROM benchmark_evaluations
        WHERE controller_id = ?
    """, (ctrl_id,)).fetchall()
    return {r[0]: {"flight_time": r[1], "distance": r[2], "mean_airspeed": r[3], "waypoints_hit": r[4], "crashed": bool(r[5])} for r in rows}

p3c_bench = get_controller_benchmarks("p3c_champ_neat_gen300")
pid_bench = get_controller_benchmarks("pid_open_sky")

# Morphologies
p3c_morph_row = c.execute("SELECT morphology_json FROM individuals WHERE experiment_id='TALOS-P3C' ORDER BY generation DESC, fitness DESC LIMIT 1").fetchone()
p3c_morph = json.loads(p3c_morph_row[0]) if p3c_morph_row else {}

conn.close()

def clean_res(d):
    return {k: {
        "flight_time": round(v.get("flight_time", 0.0), 2),
        "distance": round(v.get("distance", 0.0), 1),
        "mean_airspeed": round(v.get("mean_airspeed", 0.0), 1),
        "waypoints_hit": v.get("waypoints_hit", 0),
        "crashed": bool(v.get("crashed", False)),
    } for k, v in d.items()}

print("\n--- BENCHMARK FLIGHT METRICS ---")
bench_table = {
    "P4-ULTIMA (Gen 105)": clean_res(p4_results),
    "P3C Champ (Gen 300)": clean_res(p3c_bench),
    "Default Baseline (PID)": clean_res(pid_bench),
}
print(json.dumps(bench_table, indent=2))

print("\n--- AIRFRAME MORPHOLOGY COMPARISON ---")
morph_table = {
    "Default Baseline (B0)": {k: round(v, 4) for k, v in DEFAULT_MORPHOLOGY.items()},
    "P3C Champ (Gen 300)": {k: round(v, 4) for k, v in p3c_morph.items()},
    "P4-ULTIMA (Gen 105)": {k: round(v, 4) for k, v in morph_p4_105.to_dict().items()},
}
print(json.dumps(morph_table, indent=2))
