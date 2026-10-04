"""Casually evaluate P4-ULTIMA Gen 170 champion against the benchmark suite.
DOES NOT save to icarus.db.
"""
import sys
sys.path.insert(0, ".")
import os
import json
import shutil
import neat
import numpy as np

from src.simulation.env import FixedwingEnv
from src.genome.morphology import MorphologyGenome
from src.genome.urdf_gen import generate_model_files
from src.experiment.metadata import load_config

AUVSI_WAYPOINTS = np.array([
    [180.0,   40.0, 25.0],
    [320.0,  -80.0, 40.0],
    [160.0, -220.0, 20.0],
    [-60.0, -120.0, 15.0],
    [ 60.0,   80.0, 30.0],
])

TEST_B_WAYPOINTS = np.array([
    [150.0,   0.0, 10.0],
    [236.6,  50.0, 15.0],
    [151.7, -34.8, 10.0],
    [300.0, -34.8, 12.0],
])

def evaluate_flight(net, model_dir, test_type="AUVSI", duration=30.0, arena=1000.0):
    config = load_config("configs/controller_only/c1_controller_only.json")
    config["simulation"]["episode_duration"] = duration
    config["simulation"]["flight_dome_size"] = arena

    env = FixedwingEnv(config=config, model_dir=model_dir)
    unwrapped = env.env.unwrapped
    unwrapped.flight_dome_size = arena
    env.max_steps = int(duration * env.control_hz)

    obs, _ = env.reset(seed=42)

    if test_type == "AUVSI" and hasattr(unwrapped, "waypoints"):
        unwrapped.waypoints.targets = AUVSI_WAYPOINTS.copy()
        unwrapped.waypoints.num_targets = len(AUVSI_WAYPOINTS)
        unwrapped.waypoints.goal_reach_distance = 15.0
    elif test_type == "TEST_B" and hasattr(unwrapped, "waypoints"):
        unwrapped.waypoints.targets = TEST_B_WAYPOINTS.copy()
        unwrapped.waypoints.num_targets = len(TEST_B_WAYPOINTS)
        unwrapped.waypoints.goal_reach_distance = 2.0
    elif test_type == "STRAIGHT":
        pass

    corridor_hits = 0
    total_steps = 0
    step = 0

    while step < env.max_steps:
        action = np.asarray(net.activate(obs), dtype=np.float32)
        obs, _, term, trunc, info = env.step(action)
        step += 1
        total_steps += 1

        drone = unwrapped.env.drones[0]
        pos = drone.state[3]
        pz = float(pos[2])
        if abs(pz - 25.0) <= 15.0:
            corridor_hits += 1

        if term or trunc:
            break

    metrics = env.get_metrics()
    wps_hit = int(getattr(unwrapped.waypoints, "num_targets_reached", 0)) if hasattr(unwrapped, "waypoints") else 0
    env.close()

    corridor_pct = (corridor_hits / max(1, total_steps)) * 100.0

    return {
        "flight_time": metrics.get("flight_time", 0.0),
        "distance": metrics.get("distance", 0.0),
        "mean_airspeed": metrics.get("airspeed", 0.0),
        "waypoints_hit": wps_hit,
        "corridor_pct": corridor_pct,
        "crashed": metrics.get("crashed", False),
    }

def main():
    chk_path = "output/checkpoints/talos-p4-ultima-chk-170"
    morph_path = "output/checkpoints/talos-p4-ultima-morph-170.json"

    pop = neat.Checkpointer.restore_checkpoint(chk_path)
    best = max(pop.population.values(), key=lambda g: g.fitness or -999)
    net = neat.nn.FeedForwardNetwork.create(best, pop.config)

    with open(morph_path, "r", encoding="utf-8") as f:
        morphs = json.load(f)
    m_dict = morphs.get(str(best.key), list(morphs.values())[0])
    morph = MorphologyGenome.from_dict(m_dict)

    temp_dir = os.path.abspath("models/temp_eval_gen170")
    generate_model_files(morph, temp_dir)

    print("Evaluating Test A (Straight Sprint)...")
    res_a = evaluate_flight(net, temp_dir, test_type="STRAIGHT", duration=20.0)

    print("Evaluating Test B (4-Gate Waypoint Course)...")
    res_b = evaluate_flight(net, temp_dir, test_type="TEST_B", duration=25.0)

    print("Evaluating Test D (AUVSI SUAS Challenge)...")
    res_d = evaluate_flight(net, temp_dir, test_type="AUVSI", duration=30.0)

    shutil.rmtree(temp_dir, ignore_errors=True)

    print("\n--- RESULTS FOR P4-ULTIMA GEN 170 ---")
    print("Test A:", res_a)
    print("Test B:", res_b)
    print("Test D:", res_d)

if __name__ == "__main__":
    main()
