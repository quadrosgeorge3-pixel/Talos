import sqlite3
import json

conn = sqlite3.connect('output/icarus.db')
c = conn.cursor()

c.execute("SELECT id, experiment_id, generation, fitness, nodes, connections, controller_json FROM individuals WHERE experiment_id='TALOS-P2B' AND generation = 25 ORDER BY fitness DESC LIMIT 1")
row = c.fetchone()
conn.close()

ind_id, exp_id, gen, fit, nodes, conns, ctrl_json = row
data = json.loads(ctrl_json)

print("=" * 70)
print("AUDIT: NEURAL NETWORK INTEGRITY & PROVENANCE REPORT")
print("=" * 70)
print(f"Individual ID     : {ind_id}")
print(f"Experiment ID     : {exp_id}")
print(f"Generation        : {gen}")
print(f"Fitness Score     : {fit:.4f}")
print(f"Total Nodes       : {nodes}")
print(f"Total Connections : {conns}")
print("-" * 70)
print("Gene Sample (Innovation IDs, Synaptic Weights, Node Connections):")
for i, conn_gene in enumerate(data.get("connections", [])[:12]):
    print(f"  Gene {i+1:2d} : {conn_gene}")

print("-" * 70)
print(f"Evolved Hidden Nodes:")
for node_gene in data.get("nodes", []):
    print(f"  Node : {node_gene}")
print("=" * 70)
