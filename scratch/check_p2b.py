import sqlite3

conn = sqlite3.connect('output/icarus.db')
c = conn.cursor()
c.execute("SELECT max(generation) FROM generations WHERE experiment_id='TALOS-P2B'")
max_g = c.fetchone()[0]
if max_g is not None:
    c.execute("""
        SELECT generation, best_fitness, mean_fitness, best_distance, best_survival_time, best_nodes, best_connections, species_count 
        FROM generations WHERE experiment_id='TALOS-P2B' AND generation = ?
    """, (max_g,))
    r = c.fetchone()
    pct = (r[0] + 1) / 300.0 * 100.0
    print(f"Current Gen: {r[0]} / 300 ({pct:.1f}%)")
    print(f"Neural Network: {r[5]} nodes, {r[6]} active connections ({r[7]} species)")
    print(f"Best Fitness: {r[1]:.4f} (Mean: {r[2]:.4f})")
    print(f"Best Distance: {r[3]:.1f} meters (Survival: {r[4]:.2f}s)")
else:
    print("TALOS-P2B initializing Gen 0...")
conn.close()
