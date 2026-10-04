import sqlite3

conn = sqlite3.connect("output/icarus.db")
c = conn.cursor()

print("--- Experiment Metadata ---")
for row in c.execute("SELECT experiment_id, status, start_time, end_time FROM experiment_metadata"):
    print(row)

print("\n--- ULTIMA Generations ---")
for row in c.execute("SELECT MAX(generation), COUNT(*), MAX(best_fitness) FROM generations WHERE experiment_id='TALOS-P4-ULTIMA'"):
    print("Max Gen, Count, Best Fit:", row)

print("\n--- Recent 5 Generations for TALOS-P4-ULTIMA ---")
for row in c.execute("SELECT generation, best_fitness, mean_fitness, best_distance, best_survival_time FROM generations WHERE experiment_id='TALOS-P4-ULTIMA' ORDER BY generation DESC LIMIT 5"):
    print(row)

conn.close()
