import sys
sys.path.insert(0, '.')
import sqlite3, json, neat
import numpy as np
from src.experiment.metadata import load_config
from src.simulation.env import FixedwingEnv

con = sqlite3.connect('output/icarus.db')
cur = con.cursor()
cur.execute('SELECT max(generation) FROM generations')
max_g = cur.fetchone()[0]
cur.execute('SELECT controller_json FROM individuals WHERE generation=? ORDER BY fitness DESC LIMIT 1', (max_g,))
ctrl_json = cur.fetchone()[0]
con.close()

config = load_config("configs/controller_only/c1_controller_only.json")
env = FixedwingEnv(config=config)

# Recreate genome from json
data = json.loads(ctrl_json)
from src.genome.controller import NEATController
controller = NEATController(config)
neat_cfg = controller.config

# Build network from weights
genome = neat.DefaultGenome(0)
genome.nodes = {}
genome.connections = {}
# reconstruct connections
for conn in data["connections"]:
    key = (conn["from"], conn["to"])
    cg = neat.genes.DefaultConnectionGene(key)
    cg.weight = conn["weight"]
    cg.enabled = conn["enabled"]
    genome.connections[key] = cg
for n in data.get("nodes", []):
    ng = neat.genes.DefaultNodeGene(n["id"])
    ng.bias = n.get("bias", 0.0)
    ng.response = n.get("response", 1.0)
    ng.activation = n.get("activation", "tanh")
    ng.aggregation = n.get("aggregation", "sum")
    genome.nodes[n["id"]] = ng

net = neat.nn.FeedForwardNetwork.create(genome, neat_cfg)

obs, _ = env.reset(seed=42)
step = 0
coords = []
while step < env.max_steps:
    action = net.activate(obs)
    obs, reward, term, trunc, info = env.step(action)
    step += 1
    if step % 30 == 0 or term or trunc:
        pos = env.env.unwrapped.env.drones[0].state[3]
        dist_from_origin = np.linalg.norm(pos)
        print(f"Step {step} ({step/30:.1f}s): pos=({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f}), dist_origin={dist_from_origin:.1f}m, term={term}, trunc={trunc}")
    if term or trunc:
        break

metrics = env.get_metrics()
print("\nMetrics:", metrics)
env.env.close()
