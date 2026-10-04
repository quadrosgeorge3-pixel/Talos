import sqlite3
con = sqlite3.connect('output/icarus.db')
cur = con.cursor()
row = cur.execute('SELECT MAX(generation) FROM generations WHERE experiment_id = " TALOS-P4-ULTIMA\').fetchone()
print('Current co-evolution generation in DB:', row[0])
