import gymnasium as gym
import PyFlyt.gym_envs
import numpy as np

env = gym.make('PyFlyt/Fixedwing-Waypoints-v3')
obs, _ = env.reset(seed=42)

pylon_wp = np.array([
    [100.0, 0.0, 15.0],
    [150.0, 50.0, 15.0],
    [100.0, 100.0, 15.0],
    [0.0, 50.0, 15.0],
])

env.unwrapped.waypoints.targets = pylon_wp.copy()
env.unwrapped.waypoints.num_targets = len(pylon_wp)

print('Targets assigned successfully:', env.unwrapped.waypoints.targets.shape)
