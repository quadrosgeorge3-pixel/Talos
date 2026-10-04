import sqlite3
con = sqlite3.connect("output/icarus.db")
cur = con.cursor()
cur.execute("SELECT MAX(generation), COUNT(*) FROM generations WHERE experiment_id = 'TALOS-P4-ULTIMA'")
row = cur.fetchone()
print(f"Max generation in DB: {row[0]}, Total generations logged: {row[1]}")

cur.execute("SELECT generation, best_fitness, best_distance, timestamp FROM generations WHERE experiment_id = 'TALOS-P4-ULTIMA' ORDER BY generation DESC LIMIT 5")
for r in cur.fetchall():
    print(f"Gen {r[0]}: BestFit={r[1]:.2f}, Dist={r[2]:.1f}m, Time={r[3]}")
