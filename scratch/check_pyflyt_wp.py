import gymnasium as gym
import PyFlyt.gym_envs
env = gym.make('PyFlyt/Fixedwing-Waypoints-v3')
obs, _ = env.reset(seed=42)
print('Env waypoints targets:')
print(env.unwrapped.waypoints.targets)
