import sys
sys.path.insert(0, '.')
from src.experiment.metadata import load_config
from src.simulation.env import FixedwingEnv
from src.simulation.pid_controller import FixedwingPIDController

config = load_config("configs/baselines/b0_default_pid.json")
# Let's temporarily test what PID does if flight_dome_size is 500m
config["simulation"]["flight_dome_size"] = 500.0

env = FixedwingEnv(config=config)
env.env.unwrapped.flight_dome_size = 500.0
print("Gym env flight dome size set to:", env.env.unwrapped.flight_dome_size)

pid = FixedwingPIDController(dt=1.0 / env.control_hz)
obs, _ = env.reset(seed=42)
pid.reset()

step = 0
while True:
    action = pid.predict(obs)
    obs, reward, term, trunc, info = env.step(action)
    step += 1
    if step % 120 == 0 or term or trunc:
        pos = env.env.unwrapped.env.drones[0].state[3]
        print(f"PID Step {step:4d} ({step/120:.2f}s): pos=({pos[0]:6.1f}, {pos[1]:6.1f}, {pos[2]:6.1f}), term={term}, trunc={trunc}")
    if term or trunc:
        break

metrics = env.get_metrics()
print("\nPID Metrics with dome:", metrics)
env.env.close()
