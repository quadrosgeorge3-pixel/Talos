import sys
sys.path.insert(0, '.')
import json, sqlite3
import numpy as np
from src.experiment.metadata import load_config
from src.simulation.env import FixedwingEnv
from src.genome.morphology import MorphologyGenome
from src.genome.urdf_gen import generate_model_files

config = load_config('configs/coevolution/p4_ultima_coevo.json')
conn = sqlite3.connect('output/icarus.db')
c = conn.cursor()
row = c.execute('SELECT morphology_json, controller_json FROM individuals WHERE experiment_id="TALOS-P4-ULTIMA" AND generation=114 ORDER BY fitness DESC LIMIT 1').fetchone()
conn.close()

if row:
    morph_data = json.loads(row[0])
    morph = MorphologyGenome.from_dict(morph_data)
    model_dir = 'models/test_crash_inspect'
    generate_model_files(morph, model_dir)
    
    # Check champion evaluation seed: in coevolution_runner.py, champ_flight uses:
    # champ_flight = _record_coevo_champion_flight(env=champ_env, net=champ_net, seed=rnd_seed, ...) where rnd_seed=42!
    print("--- 1. CHAMPION FLIGHT RECORDING SEED (rnd_seed = 42) ---")
    env = FixedwingEnv(config=config, model_dir=model_dir)
    obs, _ = env.reset(seed=42)
    wp_handler = env.env.unwrapped.waypoints
    print(f"Goal reach distance: {wp_handler.goal_reach_distance}m, min_height: {wp_handler.min_height}m")
    for idx, target in enumerate(wp_handler.targets):
        print(f"  Target {idx+1}: ({target[0]:.1f}, {target[1]:.1f}, {target[2]:.1f})")
    env.close()

    print("\n--- 2. TRAINING POPULATION EVAL SEED (seed = 42 + 114*1000 + gid) ---")
    env = FixedwingEnv(config=config, model_dir=model_dir)
    obs, _ = env.reset(seed=42 + 114*1000)
    wp_handler = env.env.unwrapped.waypoints
    for idx, target in enumerate(wp_handler.targets):
        print(f"  Target {idx+1}: ({target[0]:.1f}, {target[1]:.1f}, {target[2]:.1f})")
    env.close()
