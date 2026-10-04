import sys
sys.path.insert(0, '.')
from src.simulation.env import FixedwingEnv
from src.experiment.metadata import load_config

cfg = load_config('configs/controller_only/c1_controller_only.json')
env = FixedwingEnv(cfg)
obs, _ = env.reset(seed=42)
wp = env.env.unwrapped.waypoints
print('Default goal_reach_distance:', wp.goal_reach_distance)
wp.goal_reach_distance = 15.0
print('Modified goal_reach_distance:', wp.goal_reach_distance)
env.close()
