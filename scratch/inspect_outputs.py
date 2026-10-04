import json
import sqlite3

con = sqlite3.connect('output/icarus.db')
cur = con.cursor()
cur.execute("SELECT controller_json FROM individuals WHERE experiment_id = 'TALOS-P4-ULTIMA' AND generation = 382")
data = json.loads(cur.fetchone()[0])
print("Node IDs present in data['nodes']:", [n['id'] for n in data['nodes']])
for c in data['connections']:
    if c['to'] in [0, 1, 2, 3, 4, 5]:
        print(f"Connection directly to output {c['to']}: from {c['from']}, enabled={c['enabled']}, weight={c['weight']}")
