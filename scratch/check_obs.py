import sys
sys.path.insert(0, ".")
from src.simulation.env import FixedwingEnv
from src.experiment.metadata import load_config
import numpy as np

cfg = load_config('configs/controller_only/c1_controller_only.json')
cfg['simulation']['episode_duration'] = 2.0
env = FixedwingEnv(cfg)
obs, info = env.reset(seed=42)
print("obs shape:", obs.shape)
print("obs values:", np.round(obs, 3))
print("unwrapped state type:", type(env.env.unwrapped.state))
if isinstance(env.env.unwrapped.state, dict):
    for k, v in env.env.unwrapped.state.items():
        print(f"  {k}: {v}")
elif isinstance(env.env.unwrapped.state, np.ndarray):
    print("state array:", env.env.unwrapped.state)

# Let's inspect drone object
drone = env.env.unwrapped.env.drones[0]
print("drone state shapes:")
for i, s in enumerate(drone.state):
    print(f"  drone.state[{i}]: {s}")

# Let's inspect waypoints object
wp_obj = env.env.unwrapped.waypoints
print("waypoints targets:", wp_obj.targets)
print("waypoints num_targets:", wp_obj.num_targets)
print("waypoints target_index:", getattr(wp_obj, "target_index", None))
print("waypoints distance_to_target:", getattr(wp_obj, "distance_to_target", None))

env.env.close()
