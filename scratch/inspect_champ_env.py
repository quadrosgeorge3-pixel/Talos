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

# Rebuild neural net
neat_cfg_path = "configs/neat_default.cfg"
# Let's inspect how the controller runs:
data = json.loads(ctrl_json)
print("Nodes:", len(data.get("nodes", [])))
print("Connections:", len(data.get("connections", [])))

obs, _ = env.reset(seed=42)
print("Env control hz:", env.control_hz)
print("Env max steps:", env.max_steps)
print("Flight dome size:", env.env.unwrapped.flight_dome_size)
