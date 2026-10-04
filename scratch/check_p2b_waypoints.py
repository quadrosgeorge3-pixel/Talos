import sys
sys.path.insert(0, ".")

import neat
import numpy as np
import math
from src.simulation.generalization_benchmark import run_flight_simulation

chk_path = "output/checkpoints/talos-p2b-chk-25"
pop = neat.Checkpointer.restore_checkpoint(chk_path)
best_genome = max(pop.population.values(), key=lambda g: g.fitness or -999)
net = neat.nn.FeedForwardNetwork.create(best_genome, pop.config)

# Test B Waypoints
wp_course_b = np.array([
    [150.0, 0.0, 10.0],
    [236.6, 50.0, 15.0],
    [151.7, -34.8, 10.0],
    [300.0, -34.8, 12.0],
])

print("=== Running Test B Waypoint Proximity Analysis on Gen 25 ===")
res_b = run_flight_simulation("NEAT", net, wp_course_b, duration=25.0, flight_dome_size=1000.0, seed=42)
traj = res_b["trajectory"]

print(f"Total Trajectory Steps logged: {len(traj)}")
print(f"Flight Time: {res_b['flight_time']:.2f}s | Distance: {res_b['distance']:.1f}m | Waypoints Hit: {res_b['waypoints_hit']}")

for i, wp in enumerate(wp_course_b):
    wx, wy, wz = wp
    min_dist = 999999.0
    closest_pt = None
    for pt in traj:
        d = math.sqrt((pt['x'] - wx)**2 + (pt['y'] - wy)**2 + (pt['z'] - wz)**2)
        if d < min_dist:
            min_dist = d
            closest_pt = pt
    print(f"  Target {i+1} at ({wx:.1f}, {wy:.1f}, {wz:.1f}):")
    print(f"    Closest distance = {min_dist:.2f} meters (Threshold: 2.0m)")
    print(f"    Craft position at closest: ({closest_pt['x']:.1f}, {closest_pt['y']:.1f}, {closest_pt['z']:.1f}) at t={closest_pt['time']:.2f}s, speed={closest_pt['airspeed']:.1f} m/s")

# Let's inspect control surface outputs / actions
print("\n=== Inspecting Network Steering Behavior ===")
# Let's see what aileron/rudder commands it outputs when given waypoint offset
# Test zero offset vs lateral offset
sample_obs_straight = np.zeros(15, dtype=np.float32)
sample_obs_straight[6] = 25.0 # vx
sample_obs_straight[11] = 10.0 # z
sample_obs_straight[12] = 50.0 # dx forward
sample_obs_straight[13] = 0.0 # dy
act_straight = net.activate(sample_obs_straight)

sample_obs_right = sample_obs_straight.copy()
sample_obs_right[13] = 30.0 # waypoint is 30m to the right
act_right = net.activate(sample_obs_right)

sample_obs_left = sample_obs_straight.copy()
sample_obs_left[13] = -30.0 # waypoint is 30m to the left
act_left = net.activate(sample_obs_left)

print("Action: [left_aileron, right_aileron, elevator, rudder, flap, thrust]")
print("When waypoint is STRAIGHT AHEAD :", np.round(act_straight, 3))
print("When waypoint is 30m RIGHT      :", np.round(act_right, 3))
print("When waypoint is 30m LEFT       :", np.round(act_left, 3))
