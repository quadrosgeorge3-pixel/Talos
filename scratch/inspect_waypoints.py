import sys
sys.path.insert(0, ".")
import inspect
import gymnasium as gym
import PyFlyt.gym_envs

env = gym.make("PyFlyt/Fixedwing-Waypoints-v3")
wp = env.unwrapped.waypoints
print("Waypoint class:", wp.__class__)
print(inspect.getsource(wp.__class__))
