import sqlite3

conn = sqlite3.connect('output/icarus.db')
c = conn.cursor()

print("=== Population Health & Diversity from Gen 35 to Gen 104 ===")
c.execute("""
    SELECT generation, best_fitness, mean_fitness, median_fitness, species_count, best_distance, best_survival_time
    FROM generations WHERE experiment_id='TALOS-P2B' AND generation >= 35 AND generation % 10 = 0
    ORDER BY generation
""")
for r in c.fetchall():
    print(f"Gen {r[0]:3d} | Best Fit: {r[1]:.4f} | Mean Fit: {r[2]:7.2f} | Med Fit: {r[3]:7.2f} | Species: {r[4]} | Best Dist: {r[5]:5.1f}m | Time: {r[6]:5.2f}s")

# Let's inspect individuals in Gen 100
print("\n=== Top 5 Individuals in Gen 100 ===")
c.execute("""
    SELECT individual_index, fitness, is_elite, survival_time, distance, altitude_error, airspeed_error, crashed, stalling, nodes, connections
    FROM individuals WHERE experiment_id='TALOS-P2B' AND generation = 100
    ORDER BY fitness DESC LIMIT 5
""")
for ind in c.fetchall():
    print(f"Ind {ind[0]:2d} | Fit: {ind[1]:.4f} | Elite: {bool(ind[2])} | Time: {ind[3]:5.2f}s | Dist: {ind[4]:5.1f}m | AltErr: {ind[5]:5.2f}m | SpdErr: {ind[6]:5.2f}m/s | Crash: {bool(ind[7])} | Stall: {bool(ind[8])}")

conn.close()
