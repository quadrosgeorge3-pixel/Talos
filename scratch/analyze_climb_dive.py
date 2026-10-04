import sys
sys.path.insert(0, '.')
import json, neat
import numpy as np
from src.experiment.metadata import load_config
from src.simulation.env import FixedwingEnv
from src.genome.morphology import MorphologyGenome
from src.genome.urdf_gen import generate_model_files

# Load checkpoint 110 or 113
with open('output/talos-p4-ultima_trajectory.json') as f:
    d = json.load(f)

print(f"Recorded Trajectory Gen: {d.get('generation')}")
traj = d['trajectory']

# Find where it climbed and where it dived
z_history = [p['z'] for p in traj]
t_history = [p['time'] for p in traj]
spd_history = [p['airspeed'] for p in traj]
pitch_history = [p['pitch'] for p in traj]

print(f"Max altitude reached: {max(z_history):.2f}m at t={t_history[z_history.index(max(z_history))]:.2f}s")
print(f"Initial altitude: {z_history[0]:.2f}m, Final altitude: {z_history[-1]:.2f}m")
print(f"Speed at peak altitude: {spd_history[z_history.index(max(z_history))]:.2f} m/s")
print(f"Max speed during flight: {max(spd_history):.2f} m/s")

print(f"Flight time: {d.get('flight_time'):.2f}s, Crashed: {d.get('crashed')}, Distance: {d.get('distance'):.1f}m")
print("\n--- Last 8 Trajectory Points ---")
for p in traj[-8:]:
    print(f"t={p['time']:.2f}s | pos=({p['x']:6.1f}, {p['y']:6.1f}, {p['z']:6.2f}) | spd={p['airspeed']:4.1f}m/s | pitch={p['pitch']:5.2f} | wp_hit={p['waypoints_hit']}")

