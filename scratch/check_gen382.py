import os
import sys
sys.path.insert(0, ".")
import json
import sqlite3

con = sqlite3.connect("output/icarus.db")
cur = con.cursor()
cur.execute("SELECT generation, fitness, nodes, connections, morphology_json, controller_json FROM individuals WHERE experiment_id = 'TALOS-P4-ULTIMA' AND generation = 382")
row = cur.fetchone()

if row:
    gen, fit, nodes, conns, morph_json, ctrl_json = row
    print(f"Gen: {gen}, Fitness: {fit}, Nodes: {nodes}, Connections: {conns}")
    morph = json.loads(morph_json)
    print("Morphology:", morph)
    ctrl = json.loads(ctrl_json)
    print(f"Controller keys: {list(ctrl.keys())}")
    print(f"Controller nodes count: {len(ctrl.get('nodes', []))}, conns: {len(ctrl.get('connections', []))}")
else:
    print("Row not found for Gen 382")
