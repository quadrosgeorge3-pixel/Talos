import sys
sys.path.insert(0, ".")

import neat
import numpy as np
import math
from src.simulation.generalization_benchmark import run_flight_simulation

chk_path = "output/checkpoints/talos-p2b-chk-100"
pop = neat.Checkpointer.restore_checkpoint(chk_path)
best_genome = max(pop.population.values(), key=lambda g: g.fitness or -999)
net = neat.nn.FeedForwardNetwork.create(best_genome, pop.config)

print("=" * 70)
print(f"EVALUATING TALOS-P2B GEN 100 CHAMPION ON STANDARDIZED TEST CASES")
print(f"Checkpoint: {chk_path}")
print(f"Training Fitness: {best_genome.fitness:.4f}")
print(f"Nodes: {len(best_genome.nodes)} | Connections: {sum(1 for c in best_genome.connections.values() if c.enabled)}")
print("=" * 70)

# Test Waypoints
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

for name, wp_arr, duration, dome in tests:
    print(f"\n--- Running {name} (Duration: {duration}s, Dome: {dome}m) ---")
    res = run_flight_simulation("NEAT", net, wp_arr, duration=duration, flight_dome_size=dome, seed=42)
    print(f"  Flight Survival Time : {res['flight_time']:.2f} s / {duration:.2f} s")
    print(f"  Airspeed Distance    : {res['distance']:.1f} m")
    print(f"  Mean Airspeed        : {res['mean_airspeed']:.1f} m/s")
    print(f"  Mean Altitude        : {res['mean_altitude']:.1f} m")
    print(f"  Max Lateral Dev      : {res['max_lateral_deviation']:.1f} m")
    print(f"  Control Energy       : {res['control_energy']:.2f}")
    print(f"  Crashed / Stalling   : {res['crashed']} / {res['stalling']}")
    print(f"  Waypoints Captured   : {res['waypoints_hit']} targets")
    
    # Check closest waypoint distance if Test B
    if wp_arr is not None and "Course" in name:
        for i, wp in enumerate(wp_arr):
            min_d = min(math.sqrt((p['x']-wp[0])**2 + (p['y']-wp[1])**2 + (p['z']-wp[2])**2) for p in res['trajectory'])
            print(f"    Target {i+1} [{wp[0]:.1f}, {wp[1]:.1f}, {wp[2]:.1f}]: Closest Approach = {min_d:.2f} m")
