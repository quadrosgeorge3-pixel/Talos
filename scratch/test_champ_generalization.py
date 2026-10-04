import sys
sys.path.insert(0, '.')
import neat
import numpy as np
from src.experiment.metadata import load_config
from src.simulation.env import FixedwingEnv

# Load latest checkpoint
pop = neat.Checkpointer.restore_checkpoint('output/checkpoints/c1-chk-212')
best_g = max(pop.population.values(), key=lambda g: g.fitness or -999)
net = neat.nn.FeedForwardNetwork.create(best_g, pop.config)

# Inspect input connections of champion
input_names = [
    "p (roll rate)", "q (pitch rate)", "r (yaw rate)",
    "roll", "pitch", "yaw",
    "u (fwd vel)", "v (lat vel)", "w (vert vel)",
    "x (pos)", "y (pos)", "z (pos)",
    "dx (waypoint)", "dy (waypoint)", "dz (waypoint)"
]
output_names = ["left_aileron", "right_aileron", "elevator", "rudder", "flap", "thrust"]

print("=== Champion Active Connections ===")
for conn_key, cg in best_g.connections.items():
    if cg.enabled:
        src, dst = conn_key
        src_name = input_names[-src - 1] if src < 0 else f"Node {src}"
        dst_name = output_names[dst] if dst < len(output_names) else f"Node {dst}"
        if "waypoint" in src_name:
            print(f"  * WAYPOINT SENSITIVITY: {src_name} -> {dst_name}: weight={cg.weight:.3f}")

# Now test the champion in an OPEN FIELD (500m dome)
config = load_config("configs/controller_only/c1_controller_only.json")
config["simulation"]["episode_duration"] = 20.0  # Let it fly for 20 seconds!
env = FixedwingEnv(config=config)
env.env.unwrapped.flight_dome_size = 1000.0  # 1km open field!
env.max_steps = int(20.0 * env.control_hz)

obs, _ = env.reset(seed=42)
step = 0
positions = []
while step < env.max_steps:
    action = net.activate(obs)
    obs, reward, term, trunc, info = env.step(action)
    step += 1
    pos = env.env.unwrapped.env.drones[0].state[3]
    positions.append(pos)
    if step % 60 == 0 or term or trunc:
        print(f"Step {step:3d} ({step/30:.1f}s): pos=({pos[0]:6.1f}, {pos[1]:6.1f}, {pos[2]:6.1f}) | speed={np.linalg.norm(env.env.unwrapped.env.drones[0].state[2]):.1f}m/s | crashed={info.get('crashed', False)}")
    if term or trunc:
        break

metrics = env.get_metrics()
print("\nOpen Field 20s Flight Metrics:", metrics)
env.env.close()
