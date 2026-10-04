import sys
sys.path.insert(0, '.')
import neat
import numpy as np
from src.experiment.metadata import load_config
from src.simulation.env import FixedwingEnv

pop = neat.Checkpointer.restore_checkpoint('output/checkpoints/c1-chk-212')
best_g = max(pop.population.values(), key=lambda g: g.fitness or -999)
net = neat.nn.FeedForwardNetwork.create(best_g, pop.config)

config = load_config("configs/controller_only/c1_controller_only.json")
env = FixedwingEnv(config=config)

obs, _ = env.reset(seed=42)
step = 0
while step < env.max_steps:
    action = net.activate(obs)
    obs, reward, term, trunc, info = env.step(action)
    step += 1
    drone = env.env.unwrapped.env.drones[0]
    pos = drone.state[3]
    dist_origin = np.linalg.norm(pos)
    if step % 30 == 0 or term or trunc:
        print(f"Step {step:3d} ({step/30:.1f}s): pos=({pos[0]:6.1f}, {pos[1]:6.1f}, {pos[2]:6.1f}) | dist_origin={dist_origin:6.1f}m | term={term} | trunc={trunc}")
    if term or trunc:
        break

metrics = env.get_metrics()
print("\nMetrics:", metrics)
env.env.close()
