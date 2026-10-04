import sys
import os
sys.path.insert(0, os.path.abspath("."))
import sqlite3
import json
from src.genome.morphology import MorphologyGenome
from src.genome.urdf_gen import generate_model_files

conn = sqlite3.connect("output/icarus.db")
c = conn.cursor()

c.execute("""
    SELECT experiment_id, generation, individual_index, fitness, morphology_json
    FROM individuals
    WHERE experiment_id IN ('TALOS-P3A', 'TALOS-P3B') AND is_elite = 1
    ORDER BY fitness DESC
    LIMIT 3
""")

rows = c.fetchall()
print(f"Fetched {len(rows)} top elite individuals from DB:")
for r in rows:
    exp_id, gen, ind_idx, fit, morph_json = r
    print(f"\n--- {exp_id} Gen {gen} Ind {ind_idx} (Fitness: {fit:.2f}) ---")
    data = json.loads(morph_json)
    print("Stored JSON:", json.dumps(data, indent=2))
    
    # Can we reconstruct a MorphologyGenome directly from this dict?
    genome = MorphologyGenome.from_dict(data)
    print("Reconstructed Genome params:", genome.to_dict())
    
    # Can we generate model files (URDF & PyFlyt XML) independently?
    test_dir = f"scratch/test_reconstruct_{exp_id}_g{gen}_i{ind_idx}"
    files = generate_model_files(genome, test_dir)
    print(f"Generated model files in {test_dir}:", files)

conn.close()
