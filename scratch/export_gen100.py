import sqlite3
import csv
import json

conn = sqlite3.connect('output/icarus.db')
c = conn.cursor()

# 1. Summary stats
c.execute("""
    SELECT experiment_id, generation, best_fitness, mean_fitness, median_fitness, worst_fitness, std_fitness,
           best_nodes, best_connections, species_count, best_distance, best_survival_time, best_energy
    FROM generations WHERE experiment_id='TALOS-P2B' AND generation = 100
""")
sum_row = c.fetchone()

# 2. All 50 individuals
c.execute("""
    SELECT individual_index, fitness, is_elite, survival_time, distance, altitude_error, airspeed_error, energy,
           crashed, stalling, nodes, connections, species_id
    FROM individuals WHERE experiment_id='TALOS-P2B' AND generation = 100
    ORDER BY fitness DESC, individual_index ASC
""")
inds = c.fetchall()
conn.close()

# Export CSV
csv_path = "output/gen100_population_data.csv"
with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Individual_ID", "Fitness", "Is_Elite", "Survival_Time_s", "Distance_m", "Altitude_Error_m", "Airspeed_Error_ms", "Energy", "Crashed", "Stalling", "Nodes", "Connections", "Species_ID"])
    for ind in inds:
        writer.writerow([ind[0], f"{ind[1]:.4f}", bool(ind[2]), f"{ind[3]:.2f}", f"{ind[4]:.2f}", f"{ind[5]:.2f}", f"{ind[6]:.2f}", f"{ind[7]:.2f}", bool(ind[8]), bool(ind[9]), ind[10], ind[11], ind[12]])

# Export JSON
json_path = "output/gen100_population_data.json"
json_data = {
    "experiment_id": sum_row[0],
    "generation": sum_row[1],
    "summary": {
        "best_fitness": sum_row[2],
        "mean_fitness": sum_row[3],
        "median_fitness": sum_row[4],
        "worst_fitness": sum_row[5],
        "std_fitness": sum_row[6],
        "best_nodes": sum_row[7],
        "best_connections": sum_row[8],
        "species_count": sum_row[9],
        "best_distance": sum_row[10],
        "best_survival_time": sum_row[11],
        "best_energy": sum_row[12],
    },
    "population": [
        {
            "id": ind[0],
            "fitness": ind[1],
            "is_elite": bool(ind[2]),
            "survival_time": ind[3],
            "distance": ind[4],
            "altitude_error": ind[5],
            "airspeed_error": ind[6],
            "energy": ind[7],
            "crashed": bool(ind[8]),
            "stalling": bool(ind[9]),
            "nodes": ind[10],
            "connections": ind[11],
            "species_id": ind[12],
        }
        for ind in inds
    ]
}
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(json_data, f, indent=2)

print(f"Exported {len(inds)} individuals to {csv_path} and {json_path}")
