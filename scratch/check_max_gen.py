import sqlite3
con = sqlite3.connect("output/icarus.db")
cur = con.cursor()
cur.execute("SELECT MAX(generation) FROM individuals WHERE experiment_id = 'TALOS-P4-ULTIMA'")
print("Max gen in individuals:", cur.fetchone()[0])
cur.execute("SELECT MAX(generation) FROM generations WHERE experiment_id = 'TALOS-P4-ULTIMA'")
print("Max gen in generations:", cur.fetchone()[0])
