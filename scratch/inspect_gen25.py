import sqlite3
import json

conn = sqlite3.connect('output/icarus.db')
c = conn.cursor()

print("=== TALOS-P2B Generation 25 Stats from 'generations' table ===")
c.execute("""
    SELECT generation, best_fitness, mean_fitness, best_distance, best_survival_time, best_energy, best_nodes, best_connections, species_count
    FROM generations WHERE experiment_id='TALOS-P2B' AND generation = 25
""")
row = c.fetchone()
if row:
    print(f"Generation: {row[0]}")
    print(f"Best Fitness: {row[1]:.4f}")
    print(f"Mean Fitness: {row[2]:.4f}")
    print(f"Best Distance: {row[3]:.1f} meters")
    print(f"Best Survival Time: {row[4]:.2f} seconds")
    print(f"Best Control Energy: {row[5]:.2f}")
    print(f"Champion Architecture: {row[6]} nodes, {row[7]} connections")
    print(f"Active Species: {row[8]}")

print("\n=== TALOS-P2B Generation 25 Best Individual(s) from 'individuals' table ===")
c.execute("""
    SELECT individual_index, fitness, is_elite, survival_time, distance, energy, altitude_error, airspeed_error, crashed, stalling, nodes, connections
    FROM individuals WHERE experiment_id='TALOS-P2B' AND generation = 25
    ORDER BY fitness DESC LIMIT 3
""")
for ind in c.fetchall():
    print(f"Ind {ind[0]} | Fit: {ind[1]:.4f} | Elite: {bool(ind[2])} | Time: {ind[3]:.2f}s | Dist: {ind[4]:.1f}m | AltErr: {ind[6]:.2f}m | SpdErr: {ind[7]:.2f}m/s | Crash: {bool(ind[8])} | Stall: {bool(ind[9])} | Topology: {ind[10]} nodes, {ind[11]} conns")

conn.close()
