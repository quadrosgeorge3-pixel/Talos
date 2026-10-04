import json
import sqlite3

con = sqlite3.connect('output/icarus.db')
cur = con.cursor()
cur.execute("SELECT controller_json FROM individuals WHERE experiment_id = 'TALOS-P4-ULTIMA' AND generation = 382")
data = json.loads(cur.fetchone()[0])
print("Node IDs in data['nodes']:", [n['id'] for n in data['nodes']])
print("Node types:", {n['id']: n.get('type') for n in data['nodes']})
print("Sample node dict:", data['nodes'][0])
