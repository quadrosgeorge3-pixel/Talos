import sqlite3
con = sqlite3.connect('output/icarus.db')
cur = con.cursor()
cur.execute('SELECT config_json FROM experiment_metadata WHERE experiment_id=" TALOS-P4-ULTIMA\')
print(cur.fetchone()[0][:200])
