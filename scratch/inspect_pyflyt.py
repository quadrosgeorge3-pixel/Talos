import sys
sys.path.insert(0, ".")
import inspect
from PyFlyt.gym_envs.fixedwing_envs.fixedwing_waypoints_env import FixedwingWaypointsEnv

print("--- FixedwingWaypointsEnv.compute_term_trunc_reward ---")
print(inspect.getsource(FixedwingWaypointsEnv.compute_term_trunc_reward))
