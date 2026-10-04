import sys
sys.path.insert(0, ".")
from src.simulation.env import FixedwingEnv
from src.experiment.metadata import load_config
import inspect

cfg = load_config('configs/controller_only/c1_controller_only.json')
cfg['simulation']['episode_duration'] = 1.0
env = FixedwingEnv(cfg)
obs, info = env.reset(seed=42)
wp = env.env.unwrapped.waypoints
print("Waypoint class:", type(wp))
print("Waypoint dir:", [m for m in dir(wp) if not m.startswith('__')])
print("Waypoint source code:")
try:
    print(inspect.getsource(type(wp)))
except Exception as e:
    print("Could not get source:", e)

env.env.close()
