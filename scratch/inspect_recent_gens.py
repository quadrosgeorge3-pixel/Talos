import sqlite3

conn = sqlite3.connect('output/icarus.db')
c = conn.cursor()

print("=== TALOS-P2B: Evolution History from Gen 30 to Gen 62 ===")
c.execute("""
    SELECT generation, best_fitness, mean_fitness, best_distance, best_survival_time, best_nodes, best_connections
    FROM generations WHERE experiment_id='TALOS-P2B' AND generation >= 30 ORDER BY generation
""")
for r in c.fetchall():
    print(f"Gen {r[0]:2d} | Fit: {r[1]:.4f} (Mean: {r[2]:.2f}) | Dist: {r[3]:5.1f}m | Time: {r[4]:5.2f}s | NN: {r[5]} nodes, {r[6]} conns")

print("\n=== Best Individuals in Gen 60 ===")
c.execute("""
    SELECT individual_index, fitness, survival_time, distance, altitude_error, airspeed_error, crashed, stalling, nodes, connections
    FROM individuals WHERE experiment_id='TALOS-P2B' AND generation = 60
    ORDER BY fitness DESC LIMIT 3
""")
for ind in c.fetchall():
    print(f"Ind {ind[0]} | Fit: {ind[1]:.4f} | Time: {ind[2]:.2f}s | Dist: {ind[3]:.1f}m | AltErr: {ind[4]:.2f}m | SpdErr: {ind[5]:.2f}m/s | Crash: {bool(ind[6])} | Stall: {bool(ind[7])}")

conn.close()
