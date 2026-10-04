import sys
sys.path.insert(0, '.')
from src.simulation.env import FixedwingEnv
from src.experiment.metadata import load_config
import numpy as np

cfg = load_config('configs/coevolution/p4_ultima_coevo.json')
env = FixedwingEnv(config=cfg)
obs, _ = env.reset(seed=42)
print('Default initial obs delta:', obs[12:15])
print('Default targets shape:', env.env.unwrapped.waypoints.targets.shape)

wp = np.array([[80.0, 45.0, 20.0], [150.0, -45.0, 10.0], [220.0, 45.0, 22.0], [290.0, -45.0, 8.0]])
env.env.unwrapped.waypoints.targets = wp.copy()
env.env.unwrapped.waypoints.num_targets = len(wp)
env.env.unwrapped.compute_state()
new_obs = env._build_observation(env.env.unwrapped.state)
print('New obs delta after compute_state:', new_obs[12:15])
env.close()
