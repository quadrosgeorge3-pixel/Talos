# -*- coding: utf-8 -*-
"""run_testarossa_comparison.py - Automated 5-Test Benchmark Suite & Comparison for TALOS-P4-TESTAROSSA."""
import sys
import os
import json
import sqlite3
from datetime import datetime, timezone
import numpy as np

sys.path.insert(0, ".")

import neat
from src.genome.morphology import MorphologyGenome
from src.genome.urdf_gen import generate_model_files
from src.simulation.generalization_benchmark import run_flight_simulation, BENCHMARK_TEST_CONFIGS
from src.genome.controller import NEATController
from src.experiment.metadata import load_config

def get_latest_testarossa_gen():
    con = sqlite3.connect("output/icarus.db")
    cur = con.cursor()
    cur.execute("SELECT MAX(generation) FROM individuals WHERE experiment_id = 'TALOS-P4-TESTAROSSA'")
    res = cur.fetchone()
    con.close()
    return res[0] if res else None

def evaluate_testarossa(gen: int):
    config = load_config("configs/coevolution/p4_testarossa.json")
    neat_cfg = NEATController._build_neat_config(config)

    db_path = "output/icarus.db"
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    cur.execute(
        "SELECT fitness, nodes, connections, morphology_json, controller_json FROM individuals WHERE experiment_id = 'TALOS-P4-TESTAROSSA' AND generation = ?",
        (gen,)
    )
    row = cur.fetchone()
    if not row:
        print(f"Error: Individual for Gen {gen} not found in DB!")
        con.close()
        return None

    fit, nodes_cnt, conns_cnt, morph_json, ctrl_json = row
    morph_dict = json.loads(morph_json)
    ctrl_data = json.loads(ctrl_json)

    genome = neat.DefaultGenome(ctrl_data["id"])
    genome.fitness = ctrl_data["fitness"]

    for out_id in range(6):
        node_gene = genome.create_node(neat_cfg.genome_config, out_id)
        node_gene.bias = 0.0
        node_gene.activation = neat_cfg.genome_config.output_activation_default
        node_gene.aggregation = neat_cfg.genome_config.aggregation_default
        node_gene.response = 1.0
        genome.nodes[out_id] = node_gene

    for n in ctrl_data["nodes"]:
        nid = n["id"]
        if nid < 0:
            continue
        node_gene = genome.create_node(neat_cfg.genome_config, nid)
        node_gene.bias = n["bias"]
        node_gene.activation = n["activation"]
        node_gene.aggregation = n.get("aggregation", neat_cfg.genome_config.aggregation_default)
        node_gene.response = n["response"]
        genome.nodes[nid] = node_gene

    for idx, c in enumerate(ctrl_data["connections"]):
        cid = (c["from"], c["to"])
        conn_gene = genome.create_connection(neat_cfg.genome_config, c["from"], c["to"], innovation=idx)
        conn_gene.weight = c["weight"]
        conn_gene.enabled = c["enabled"]
        genome.connections[cid] = conn_gene

    net = neat.nn.FeedForwardNetwork.create(genome, neat_cfg)

    morph = MorphologyGenome.from_dict(morph_dict)
    model_dir = f"models/testarossa_eval_gen{gen}"
    generate_model_files(morph, model_dir)

    now_str = datetime.now(timezone.utc).isoformat()
    test_results = {}

    print(f"\n=======================================================")
    print(f"  RUNNING 5-TEST SUITE FOR TALOS-P4-TESTAROSSA GEN {gen}")
    print(f"=======================================================")

    for test_name, wp_array, duration, dome, wp_rad in BENCHMARK_TEST_CONFIGS:
        res = run_flight_simulation(
            controller_type="NEAT",
            controller_obj=net,
            custom_waypoints=wp_array,
            duration=duration,
            flight_dome_size=dome,
            waypoint_radius=wp_rad,
            seed=42,
            model_dir=model_dir
        )
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

        label = f"TALOS-P4-TESTAROSSA_gen{gen}"
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

        test_code = test_name.split(" - ")[0].replace("Test ", "")
        print(f"  [{test_code}] {res['mean_airspeed']:4.1f} m/s | WP: {wp_hit}/{num_wp if num_wp else '-'} | Crash: {str(crashed):5s} | Score: {prec_score:4.1f}")

        test_results[test_name] = {
            "speed": res["mean_airspeed"],
            "flight_time": res["flight_time"],
            "distance": res["distance"],
            "wp_hit": wp_hit,
            "num_wp": num_wp,
            "crashed": crashed,
            "score": prec_score
        }

    con.close()
    return {
        "gen": gen,
        "fitness": fit,
        "nodes": nodes_cnt,
        "conns": conns_cnt,
        "morphology": morph.to_dict(),
        "tests": test_results
    }

if __name__ == "__main__":
    target = int(sys.argv[1]) if len(sys.argv) > 1 else get_latest_testarossa_gen()
    results = evaluate_testarossa(target)
    with open("output/testarossa_benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("\nBenchmark completed and saved to output/testarossa_benchmark_results.json")
