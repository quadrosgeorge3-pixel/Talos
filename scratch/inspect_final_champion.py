import sqlite3

con = sqlite3.connect('output/icarus.db')
cur = con.cursor()

cur.execute("SELECT max(generation) FROM generations WHERE experiment_id='C1'")
max_g = cur.fetchone()[0]
print(f"Max Generation in DB: {max_g}")

cur.execute("SELECT best_fitness, best_generation FROM experiment_metadata WHERE experiment_id='C1'")
meta = cur.fetchone()
print(f"Experiment Metadata Best: Fitness={meta[0]}, Generation={meta[1]}")

cur.execute("""
    SELECT id, generation, fitness, survival_time, distance, mean_airspeed, altitude_error, control_energy, crashed
    FROM (
        SELECT id, generation, fitness, survival_time, distance, airspeed_error as mean_airspeed, altitude_error, energy as control_energy, crashed
        FROM individuals 
        WHERE experiment_id='C1' 
        ORDER BY fitness DESC LIMIT 1
    )
""")
print(f"All-Time Highest Fitness Champion: {cur.fetchone()}")

cur.execute("""
    SELECT id, generation, fitness, survival_time, distance, altitude_error, energy, crashed, nodes, connections
    FROM individuals 
    WHERE experiment_id='C1' AND generation = ?
    ORDER BY fitness DESC LIMIT 1
""", (max_g,))
desc = [d[0] for d in cur.description]
final_ind = cur.fetchone()
print("\nFinal Generation Champion:")
for k, v in zip(desc, final_ind):
    print(f"  {k}: {v}")

con.close()
