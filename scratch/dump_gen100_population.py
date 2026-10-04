import sys
sys.path.insert(0, ".")

import neat
import csv
import json
import numpy as np

chk_path = "output/checkpoints/talos-p2b-chk-100"
pop = neat.Checkpointer.restore_checkpoint(chk_path)

genomes_list = []
for gid, g in pop.population.items():
    fit = float(g.fitness) if g.fitness is not None else -100.0
    nodes_cnt = len(g.nodes)
    conns_cnt = sum(1 for c in g.connections.values() if c.enabled)
    total_conns = len(g.connections)
    genomes_list.append({
        "genome_id": gid,
        "fitness": fit,
        "nodes": nodes_cnt,
        "enabled_connections": conns_cnt,
        "total_connections": total_conns,
        "species_id": getattr(g, "species_id", 1),
    })

# Sort by fitness descending
genomes_list.sort(key=lambda x: x["fitness"], reverse=True)

# Save CSV
csv_path = "output/gen100_population_50_genomes.csv"
with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Rank", "Genome_ID", "Fitness", "Nodes", "Enabled_Conns", "Total_Conns", "Species_ID"])
    for rank, g in enumerate(genomes_list, 1):
        writer.writerow([rank, g["genome_id"], f"{g['fitness']:.4f}", g["nodes"], g["enabled_connections"], g["total_connections"], g["species_id"]])

# Save JSON
json_path = "output/gen100_population_50_genomes.json"
with open(json_path, "w", encoding="utf-8") as f:
    json.dump({
        "generation": 100,
        "checkpoint": chk_path,
        "population_size": len(genomes_list),
        "genomes": genomes_list,
    }, f, indent=2)

print(f"Successfully exported {len(genomes_list)} genomes to {csv_path} and {json_path}")
