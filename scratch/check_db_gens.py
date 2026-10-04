import os
import json
import neat

# Let us check icarus.db to see what fitnesses were logged in recent generations
import sqlite3
con = sqlite3.connect('output/icarus.db')
cur = con.cursor()
rows = cur.execute("SELECT generation, best_fitness, mean_fitness FROM generations WHERE experiment_id = 'TALOS-P4-ULTIMA' ORDER BY generation DESC LIMIT 10").fetchall()
print('Recent generations in DB:')
for r in rows:
 print(r)
