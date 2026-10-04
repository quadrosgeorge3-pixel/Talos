import os
import sys
sys.path.insert(0, ".")
import json
import sqlite3
import neat
from datetime import datetime, timezone
import numpy as np

from src.genome.morphology import MorphologyGenome
from src.genome.urdf_gen import generate_model_files
from src.simulation.generalization_benchmark import run_flight_simulation
from src.genome.controller import NEATController
from src.experiment.metadata import load_config
from scratch.quick_eval_benchmark import test_configs

def evaluate_and_store_gen_from_db(gen: int, label: str = "TALOS-P4-ULTIMA_gen382_hairpin"):
    config = load_config("configs/coevolution/p4_ultima_coevo.json")
    neat_cfg = NEATController._build_neat_config(config)

    db_path = "output/icarus.db"
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    cur.execute("SELECT fitness, nodes, connections, morphology_json, controller_json FROM individuals WHERE experiment_id = 'TALOS-P4-ULTIMA' AND generation = ?", (gen,))
    row = cur.fetchone()
    if not row:
        print(f"Error: Individual for Gen {gen} not found in DB!")
        con.close()
        return None

    fit, nodes_cnt, conns_cnt, morph_json, ctrl_json = row
    morph_dict = json.loads(morph_json)
    ctrl_data = json.loads(ctrl_json)

    print(f"Loaded Gen {gen} from DB: Fitness={fit:.2f}, Nodes={nodes_cnt}, Conns={conns_cnt}")
    print("Morphology:", morph_dict)

    # Reconstruct Genome
    genome = neat.DefaultGenome(ctrl_data["id"])
    genome.fitness = ctrl_data["fitness"]

    # 1. Instantiate all 6 output nodes (0..5) with default parameters
    for out_id in range(6):
        node_gene = genome.create_node(neat_cfg.genome_config, out_id)
        node_gene.bias = 0.0
        node_gene.activation = neat_cfg.genome_config.output_activation_default
        node_gene.aggregation = neat_cfg.genome_config.aggregation_default
        node_gene.response = 1.0
        genome.nodes[out_id] = node_gene

    # 2. Populate nodes from serialized dict (overwriting outputs if active, plus hidden nodes)
    for n in ctrl_data["nodes"]:
        nid = n["id"]
        if nid < 0:
            continue  # input node, handled by neat input_keys
        node_gene = genome.create_node(neat_cfg.genome_config, nid)
        node_gene.bias = n["bias"]
        node_gene.activation = n["activation"]
        node_gene.aggregation = n.get("aggregation", neat_cfg.genome_config.aggregation_default)
        node_gene.response = n["response"]
        genome.nodes[nid] = node_gene

    # 3. Add connections
    for idx, c in enumerate(ctrl_data["connections"]):
        cid = (c["from"], c["to"])
        conn_gene = genome.create_connection(neat_cfg.genome_config, c["from"], c["to"], innovation=idx)
        conn_gene.weight = c["weight"]
        conn_gene.enabled = c["enabled"]
        genome.connections[cid] = conn_gene

    net = neat.nn.FeedForwardNetwork.create(genome, neat_cfg)
    print("Reconstructed Neural Network successfully!")

    # Verify activation with dummy input
    test_out = net.activate([0.0]*15)
    print(f"Verification activation successful: {test_out}")

    # Build morphology
    morph = MorphologyGenome.from_dict(morph_dict)
    model_dir = f"models/benchmark_gen{gen}"
    generate_model_files(morph, model_dir)

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
        course_json = json.dumps([[float(x) for x in row_item] for row_item in wp_array]) if wp_array is not None else None
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
        "champ_id": ctrl_data["id"],
        "fitness": float(fit),
        "nodes": nodes_cnt,
        "conns": conns_cnt,
        "morphology": morph.to_dict(),
        "tests": gen_results
    }

if __name__ == "__main__":
    res = evaluate_and_store_gen_from_db(382, label="TALOS-P4-ULTIMA_gen382_hairpin")
    if res:
        with open("scratch/gen382_results.json", "w") as f:
            json.dump(res, f, indent=2, default=str)
        print("GEN382_EVAL_COMPLETE")
