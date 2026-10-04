"""Quick Evaluation Benchmark Script.
Evaluates TALOS-P4-ULTIMA Generation 45 (and Generation 35) on the 3 standardized generalization tests:
  - Test A: Open-Sky Straight Flight (20s, 1000m arena)
  - Test B: Open-Sky Waypoint Course (25s, 1000m arena, 4 gates)
  - Test C: Aggressive Aero Slalom (25s, 1000m arena, 4 gates)
Pulls P3C Gen 300 records from output/icarus.db for comparison without writing new records to the database.
"""
import os
import sys
sys.path.insert(0, ".")
import json
import sqlite3
from datetime import datetime, timezone
import neat
import numpy as np

from src.genome.morphology import MorphologyGenome
from src.genome.urdf_gen import generate_model_files
from src.simulation.generalization_benchmark import run_flight_simulation

wp_course_b = np.array([
    [150.0, 0.0, 10.0],
    [236.6, 50.0, 15.0],
    [151.7, -34.8, 10.0],
    [300.0, -34.8, 12.0],
])

wp_course_c = np.array([
    [80.0, 45.0, 22.0],
    [150.0, -45.0, 8.0],
    [220.0, 45.0, 25.0],
    [280.0, -45.0, 6.0],
])

wp_course_d = np.array([
    [180.0,   40.0, 25.0],
    [320.0,  -80.0, 40.0],
    [160.0, -220.0, 20.0],
    [-60.0, -120.0, 15.0],
    [ 60.0,   80.0, 30.0],
])

# Test E (FAI F3D/F5D 3-Pylon Race Course, 3 continuous laps)
P1 = [200.0,   0.0, 12.0]
P2 = [ 20.0,  35.0, 12.0]
P3 = [ 20.0, -35.0, 12.0]
wp_course_e = np.array([
    P1, P2, P3,  # Lap 1
    P1, P2, P3,  # Lap 2
    P1, P2, P3   # Lap 3
])

test_configs = [
    ("Test A - Open-Sky Straight Flight", None, 20.0, 1000.0, 2.0),
    ("Test B - Open-Sky Waypoint Course", wp_course_b, 25.0, 1000.0, 2.0),
    ("Test C - Aggressive Aero Slalom", wp_course_c, 25.0, 1000.0, 2.0),
    ("Test D - AUVSI SUAS Autonomous Challenge", wp_course_d, 30.0, 1000.0, 15.0),
    ("Test E - FAI F3D/F5D Pylon Racing", wp_course_e, 40.0, 1000.0, 10.0),
]

def evaluate_and_store_gen(gen: int, label: str = "TALOS-P4-ULTIMA_tier2"):
    chk_path = f"output/checkpoints/talos-p4-ultima-chk-{gen}"
    morph_path = f"output/checkpoints/talos-p4-ultima-morph-{gen}.json"
    
    if not os.path.isfile(chk_path) or not os.path.isfile(morph_path):
        print(f"Error: Checkpoint or morph file not found for Gen {gen}")
        return None
        
    pop = neat.Checkpointer.restore_checkpoint(chk_path)
    best_genome = max(pop.population.values(), key=lambda g: g.fitness or -999)
    net = neat.nn.FeedForwardNetwork.create(best_genome, pop.config)
    
    with open(morph_path, "r", encoding="utf-8") as f:
        morph_dict = json.load(f)
    best_gid = str(best_genome.key)
    m_params = morph_dict.get(best_gid, list(morph_dict.values())[0])
        
    morph = MorphologyGenome.from_dict(m_params)
    model_dir = f"models/benchmark_gen{gen}"
    generate_model_files(morph, model_dir)
    
    db_path = "output/icarus.db"
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    now_str = datetime.now(timezone.utc).isoformat()
    
    gen_results = {}
    for test_name, wp_array, duration, dome, wp_rad in test_configs:
        print(f"--> Running {test_name} for Gen {gen} (duration={duration}s)...")
        res = run_flight_simulation(
            controller_type="NEAT",
            controller_obj=net,
            custom_waypoints=wp_array,
            duration=duration,
            flight_dome_size=dome,
            seed=42,
            model_dir=model_dir
        )
        gen_results[test_name] = res
        
        # Compute precision score (0-100)
        num_wp = len(wp_array) if wp_array is not None else 0
        wp_hit = res["waypoints_hit"]
        crashed = res["crashed"]
        
        if num_wp > 0:
            wp_pts = (wp_hit / float(num_wp)) * 50.0
        else:
            wp_pts = min(res["distance"] / 500.0, 1.0) * 50.0
            
        alt_err = res["altitude_error"] if res["altitude_error"] is not None else 10.0
        corridor_pts = max(0.0, 1.0 - (alt_err / 15.0)) * 30.0
        surv_pts = 20.0 if not crashed else 0.0
        prec_score = round(wp_pts + corridor_pts + surv_pts, 1)
        res["precision_score"] = prec_score

        # Persist to icarus.db
        course_json = json.dumps([[float(x) for x in row] for row in wp_array]) if wp_array is not None else None
        traj_json = json.dumps(res.get("trajectory", []))

        cur.execute("DELETE FROM benchmark_evaluations WHERE test_name = ? AND controller_id = ?", (test_name, label))
        cur.execute("""
            INSERT INTO benchmark_evaluations (
                test_name, controller_id, controller_type, flight_time, distance,
                mean_airspeed, mean_altitude, altitude_error, max_lateral_dev,
                control_energy, crashed, stalling, waypoints_hit, precision_score, measured_at,
                course_map_json, arena_radius, waypoint_radius, trajectory_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            test_name, label, "NEAT", res["flight_time"], res["distance"],
            res["mean_airspeed"], res["mean_altitude"], res["altitude_error"], res["max_lateral_deviation"],
            res["control_energy"], 1 if crashed else 0, 1 if res["stalling"] else 0, wp_hit,
            prec_score, now_str, course_json, dome, wp_rad, traj_json,
        ))
        con.commit()
        print(f"    Done: Time={res['flight_time']:.2f}s | Dist={res['distance']:.1f}m | Spd={res['mean_airspeed']:.1f}m/s | WP={wp_hit}/{num_wp} | Score={prec_score} | Crashed={crashed}")
        
    con.close()
    return {
        "gen": gen,
        "champ_id": best_genome.key,
        "fitness": float(best_genome.fitness),
        "nodes": len(best_genome.nodes),
        "conns": sum(1 for c in best_genome.connections.values() if c.enabled),
        "morphology": morph.to_dict(),
        "tests": gen_results
    }

if __name__ == "__main__":
    target_gen = 295
    print(f"--- Running & Storing Pre-Tier-3 Final Evaluation for Gen {target_gen} (TALOS-P4-ULTIMA_tier2) ---")
    res = evaluate_and_store_gen(target_gen, label="TALOS-P4-ULTIMA_tier2")
    
    with open("scratch/tier2_final_eval_results.json", "w") as f:
        json.dump(res, f, indent=2, default=str)
        
    print("TIER2_BENCHMARK_AND_STORAGE_COMPLETE")

