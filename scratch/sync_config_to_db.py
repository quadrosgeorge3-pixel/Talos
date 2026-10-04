import sqlite3
import json

DB_PATH = "output/icarus.db"
CONFIG_PATH = "configs/coevolution/p4_ultima_coevo.json"
EID = "TALOS-P4-ULTIMA"

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config_dict = json.load(f)

config_json_str = json.dumps(config_dict, indent=2)

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

c.execute("UPDATE experiment_metadata SET config_json = ? WHERE experiment_id = ?", (config_json_str, EID))
conn.commit()

# Verify
c.execute("SELECT experiment_id, config_json FROM experiment_metadata WHERE experiment_id = ?", (EID,))
row = c.fetchone()
if row:
    saved = json.loads(row[1])
    milestones = saved.get("fitness", {}).get("curriculum_milestones", {})
    print(f"Successfully synced config to icarus.db for {EID}!")
    print("Database curriculum milestones:", milestones)
else:
    print(f"Error: {EID} not found in experiment_metadata")

conn.close()
