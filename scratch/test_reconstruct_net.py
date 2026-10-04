import os
import sys
sys.path.insert(0, ".")
import json
import sqlite3
import neat

from src.genome.controller import NEATController
from src.experiment.metadata import load_config

# Load experiment config
config = load_config("configs/coevolution/p4_ultima_coevo.json")
neat_cfg = NEATController._build_neat_config(config)

con = sqlite3.connect("output/icarus.db")
cur = con.cursor()
cur.execute("SELECT controller_json FROM individuals WHERE experiment_id = 'TALOS-P4-ULTIMA' AND generation = 382")
row = cur.fetchone()

if not row:
    print("Gen 382 not found")
    sys.exit(1)

ctrl_data = json.loads(row[0])
print(f"Gen 382 controller loaded, keys: {list(ctrl_data.keys())}")

# Reconstruct DefaultGenome
genome = neat.DefaultGenome(ctrl_data["id"])
genome.fitness = ctrl_data["fitness"]

# Add nodes
for n in ctrl_data["nodes"]:
    nid = n["id"]
    node_gene = genome.create_node(neat_cfg.genome_config, nid)
    node_gene.bias = n["bias"]
    node_gene.activation = n["activation"]
    node_gene.response = n["response"]
    genome.nodes[nid] = node_gene

# Add connections
for c in ctrl_data["connections"]:
    cid = (c["from"], c["to"])
    conn_gene = genome.create_connection(neat_cfg.genome_config, c["from"], c["to"])
    conn_gene.weight = c["weight"]
    conn_gene.enabled = c["enabled"]
    genome.connections[cid] = conn_gene

print(f"Reconstructed genome: {len(genome.nodes)} nodes, {len(genome.connections)} conns")

# Test FeedForwardNetwork creation
net = neat.nn.FeedForwardNetwork.create(genome, neat_cfg)
print("FeedForwardNetwork created successfully!")
out = net.activate([0.0]*15)
print(f"Test activation output: {out}")
