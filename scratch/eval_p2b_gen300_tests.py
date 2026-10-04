import sys
sys.path.insert(0, '.')
import os, json, sqlite3, datetime, math
import neat
import numpy as np
from src.simulation.generalization_benchmark import run_flight_simulation

chk_path = 'output/checkpoints/talos-p2b-chk-300'
pop = neat.Checkpointer.restore_checkpoint(chk_path)
best_genome = max(pop.population.values(), key=lambda g: g.fitness or -999)
net = neat.nn.FeedForwardNetwork.create(best_genome, pop.config)

print(f"Restored Gen 300 Champion: Fitness={best_genome.fitness:.4f}, Nodes={len(best_genome.nodes)}, Conns={sum(1 for c in best_genome.connections.values() if c.enabled)}")

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

con = sqlite3.connect('output/icarus.db')
cur = con.cursor()

results = {}

for name, wp_arr, duration, dome in tests:
    print(f"\nRunning {name}...")
    res = run_flight_simulation("NEAT", net, wp_arr, duration=duration, flight_dome_size=dome, seed=42)
    results[name] = res
    t = res["flight_time"]
    d = res["distance"]
    spd = res["mean_airspeed"]
    alt = res["mean_altitude"]
    lat = res["max_lateral_deviation"]
    cr = res["crashed"]
    wp_hit = res["waypoints_hit"]
    print(f"  Time: {t:.2f}s / {duration}s | Dist: {d:.1f}m | Speed: {spd:.1f}m/s | Alt: {alt:.1f}m | LatDev: {lat:.1f}m | Crashed: {cr} | WP Hit: {wp_hit}")
    
    # Store to DB
    course_json = json.dumps([[float(x) for x in row] for row in wp_arr]) if wp_arr is not None else None
    traj_json = json.dumps(res['trajectory'])
    now_str = datetime.datetime.utcnow().isoformat()
    
    cur.execute('''
        INSERT INTO benchmark_evaluations (
            test_name, controller_id, controller_type, flight_time, distance,
            mean_airspeed, mean_altitude, altitude_error, max_lateral_dev,
            control_energy, crashed, stalling, waypoints_hit, measured_at,
            course_map_json, arena_radius, waypoint_radius, trajectory_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        name, 'TALOS-P2B_gen300_champ', 'NEAT', res['flight_time'], res['distance'],
        res['mean_airspeed'], res['mean_altitude'], abs(res['mean_altitude'] - 10.0), res['max_lateral_deviation'],
        res['control_energy'], 1 if res['crashed'] else 0, 1 if res['stalling'] else 0, res['waypoints_hit'],
        now_str, course_json, 1000.0, 2.0, traj_json
    ))

con.commit()
con.close()
print("\nSuccessfully logged all 3 tests to benchmark_evaluations in output/icarus.db")

with open('scratch/gen300_benchmark_results.json', 'w') as f:
    json.dump({k: {m: res[m] for m in ['flight_time', 'distance', 'mean_airspeed', 'mean_altitude', 'max_lateral_deviation', 'control_energy', 'crashed', 'stalling', 'waypoints_hit']} for k, res in results.items()}, f, indent=2)
print("Saved summary to scratch/gen300_benchmark_results.json")
