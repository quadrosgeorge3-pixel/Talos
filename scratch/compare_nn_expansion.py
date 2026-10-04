import sqlite3

conn = sqlite3.connect('output/icarus.db')
c = conn.cursor()

print("=== C1 (100m Bounded) Generations 0 to 15 ===")
c.execute("""
    SELECT generation, best_nodes, best_connections, mean_nodes, mean_connections, best_fitness, best_distance 
    FROM generations WHERE experiment_id='C1' AND generation <= 15 ORDER BY generation
""")
for r in c.fetchall():
    print(f"Gen {r[0]:2d} | Nodes: {r[1]} (mean {r[3]:.1f}) | Conns: {r[2]} (mean {r[4]:.1f}) | Fit: {r[5]:.4f} | Dist: {r[6]:.1f}m")

print("\n=== TALOS-P2B (1000m Open Sky) All Recorded Generations ===")
c.execute("""
    SELECT generation, best_nodes, best_connections, mean_nodes, mean_connections, best_fitness, best_distance 
    FROM generations WHERE experiment_id='TALOS-P2B' ORDER BY generation
""")
for r in c.fetchall():
    print(f"Gen {r[0]:2d} | Nodes: {r[1]} (mean {r[3]:.1f}) | Conns: {r[2]} (mean {r[4]:.1f}) | Fit: {r[5]:.4f} | Dist: {r[6]:.1f}m")

conn.close()
