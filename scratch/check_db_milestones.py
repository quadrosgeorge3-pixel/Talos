import sqlite3
import json
con = sqlite3.connect('output/icarus.db')
cur = con.cursor()
cur.execute('SELECT config_json FROM experiment_metadata WHERE experiment_id=" TALOS-P4-ULTIMA\')
row = cur.fetchone()
if row:
 cfg = json.loads(row[0])
 print('DB curriculum_milestones:', cfg.get('fitness', {}).get('curriculum_milestones'))
