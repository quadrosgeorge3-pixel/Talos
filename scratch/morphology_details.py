import sqlite3, sys, json
sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect("output/icarus.db")

# Check which experiment_ids have morphology data 
print("Experiments with morphology_json:")
rows = conn.execute("""
    SELECT experiment_id, COUNT(*), 
           SUM(CASE WHEN morphology_json IS NOT NULL AND morphology_json != '' THEN 1 ELSE 0 END) as has_morph
    FROM individuals GROUP BY experiment_id
""").fetchall()
for r in rows:
    print(f"  {r[0]}: {r[1]} individuals, {r[2]} with morphology")

# Get the P3C morphology champion
print("\n--- P3C (TALOS-P3C) champion morphology ---")
p3c = conn.execute("""
    SELECT generation, individual_index, fitness, morphology_json
    FROM individuals WHERE experiment_id='TALOS-P3C'
    ORDER BY fitness DESC LIMIT 1
""").fetchone()
if p3c:
    print(f"Gen {p3c[0]}, idx {p3c[1]}, fitness {p3c[2]:.4f}")
    if p3c[3]:
        m = json.loads(p3c[3])
        print(json.dumps(m, indent=2))

# Get the P3B champion morphology  
print("\n--- P3B (TALOS-P3B) champion morphology ---")
p3b = conn.execute("""
    SELECT generation, individual_index, fitness, morphology_json
    FROM individuals WHERE experiment_id='TALOS-P3B'
    ORDER BY fitness DESC LIMIT 1
""").fetchone()
if p3b:
    print(f"Gen {p3b[0]}, idx {p3b[1]}, fitness {p3b[2]:.4f}")
    if p3b[3]:
        m = json.loads(p3b[3])
        print(json.dumps(m, indent=2))

# Get the P3A champion morphology
print("\n--- P3A (TALOS-P3A) champion morphology ---")
p3a = conn.execute("""
    SELECT generation, individual_index, fitness, morphology_json
    FROM individuals WHERE experiment_id='TALOS-P3A'
    ORDER BY fitness DESC LIMIT 1
""").fetchone()
if p3a:
    print(f"Gen {p3a[0]}, idx {p3a[1]}, fitness {p3a[2]:.4f}")
    if p3a[3]:
        m = json.loads(p3a[3])
        print(json.dumps(m, indent=2))

# Get default morphology from code
sys.path.insert(0, ".")
from src.genome.morphology import DEFAULT_MORPHOLOGY
print("\n--- DEFAULT MORPHOLOGY (Baseline) ---")
print(json.dumps(DEFAULT_MORPHOLOGY, indent=2))

conn.close()
