import json
import sqlite3

con = sqlite3.connect('output/icarus.db')
cur = con.cursor()
cur.execute("SELECT controller_json FROM individuals WHERE experiment_id = 'TALOS-P4-ULTIMA' AND generation = 382")
data = json.loads(cur.fetchone()[0])
print("Connections count:", len(data['connections']))
enabled_conns = [c for c in data['connections'] if c['enabled']]
print("Enabled connections count:", len(enabled_conns))
print("Outputs connected to:", set(c['to'] for c in enabled_conns))
print("Inputs connected from:", set(c['from'] for c in enabled_conns))
