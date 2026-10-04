import sqlite3
import os
import shutil

DB_PATH = "output/icarus.db"
EID = "TALOS-P4-ULTIMA"
CHECKPOINT_GEN = 105

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

print("=== BEFORE RESUMPTION CLEANUP ===")
c.execute("SELECT generation, best_fitness, best_distance FROM generations WHERE experiment_id = ? AND generation >= ? ORDER BY generation", (EID, CHECKPOINT_GEN))
print("Generations >= 105 to prune:", c.fetchall())

c.execute("SELECT generation, individual_index, fitness FROM individuals WHERE experiment_id = ? AND generation >= ? ORDER BY generation", (EID, CHECKPOINT_GEN))
print("Individuals >= 105 to prune:", c.fetchall())

# Delete generations and individuals >= CHECKPOINT_GEN
c.execute("DELETE FROM generations WHERE experiment_id = ? AND generation >= ?", (EID, CHECKPOINT_GEN))
gens_deleted = c.rowcount

c.execute("DELETE FROM individuals WHERE experiment_id = ? AND generation >= ?", (EID, CHECKPOINT_GEN))
inds_deleted = c.rowcount

# Set status to running
c.execute("UPDATE experiment_metadata SET status = 'running' WHERE experiment_id = ?", (EID,))

conn.commit()
print(f"Deleted {gens_deleted} generation records and {inds_deleted} individual records.")

c.execute("SELECT MAX(generation), COUNT(*) FROM generations WHERE experiment_id = ?", (EID,))
print("Post-cleanup Generations state:", c.fetchone())

conn.close()

# Remove partial gen108 model files if present
partial_dir = os.path.join("models", EID, "gen108")
if os.path.exists(partial_dir):
    shutil.rmtree(partial_dir, ignore_errors=True)
    print(f"Removed partial run directory: {partial_dir}")
else:
    print("No partial directory found.")

print("Resumption preparation complete! Ready to resume at Gen 105.")
