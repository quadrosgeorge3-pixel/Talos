import os
import json
import sqlite3

con = sqlite3.connect('output/icarus.db')
cur = con.cursor()
row = cur.execute("SELECT config_json FROM experiments WHERE id = 'TALOS-P4-ULTIMA'").fetchone()
if row and row[0]:
 cfg = json.loads(row[0])
 print('DB curriculum_milestones:', cfg.get('fitness', {}).get('curriculum_milestones'))
