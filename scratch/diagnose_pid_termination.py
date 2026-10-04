import sys
sys.path.insert(0, '.')
from src.experiment.metadata import load_config
from src.simulation.env import FixedwingEnv
from src.simulation.pid_controller import FixedwingPIDController

config = load_config("configs/baselines/b0_default_pid.json")
env = FixedwingEnv(config=config)
pid = FixedwingPIDController(dt=1.0 / env.control_hz)

obs, _ = env.reset(seed=42)
pid.reset()

step = 0
while True:
    action = pid.predict(obs)
    obs, reward, terminated, truncated, info = env.step(action)
    step += 1
    unwrapped = env.env.unwrapped
    if terminated or truncated:
        print(f"\nSTOPPED at step {step} ({step/env.control_hz:.3f}s)")
        print(f"terminated={terminated}, truncated={truncated}")
        print(f"unwrapped.termination={unwrapped.termination}, unwrapped.truncation={unwrapped.truncation}")
        print(f"info={info}")
        if hasattr(unwrapped, 'info'):
            print(f"unwrapped.info={unwrapped.info}")
        break

metrics = env.get_metrics()
print("\nFinal metrics:", metrics)
env.env.close()
