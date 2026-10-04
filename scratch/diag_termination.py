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

def main():
    chk_path = 'output/checkpoints/talos-p4-ultima-chk-170'
    morph_path = 'output/checkpoints/talos-p4-ultima-morph-170.json'

    pop = neat.Checkpointer.restore_checkpoint(chk_path)
    best = max(pop.population.values(), key=lambda g: g.fitness or -999)
    net = neat.nn.FeedForwardNetwork.create(best, pop.config)

    with open(morph_path, "r", encoding="utf-8") as f:
        morphs = json.load(f)
    m_dict = morphs[str(best.key)]
    morph = MorphologyGenome.from_dict(m_dict)

    temp_dir = os.path.abspath("models/temp_diag_170")
    generate_model_files(morph, temp_dir)

    cfg = load_config("configs/controller_only/c1_controller_only.json")
    cfg["simulation"]["episode_duration"] = 30.0
    cfg["simulation"]["flight_dome_size"] = 1000.0

    # 1. Test D
    print("=" * 60)
    print("RUNNING TEST D DIAGNOSTIC...")
    env = FixedwingEnv(config=cfg, model_dir=temp_dir)
    unwrapped = env.env.unwrapped
    unwrapped.flight_dome_size = 1000.0
    unwrapped.waypoints.targets = np.array([
        [180.0,   40.0, 25.0],
        [320.0,  -80.0, 40.0],
        [160.0, -220.0, 20.0],
        [-60.0, -120.0, 15.0],
        [ 60.0,   80.0, 30.0],
    ])
    unwrapped.waypoints.num_targets = 5
    unwrapped.waypoints.goal_reach_distance = 15.0
    env.max_steps = int(30.0 * env.control_hz)

    obs, _ = env.reset(seed=42)
    term_reason = "MAX_STEPS"
    for step in range(env.max_steps):
        act = np.asarray(net.activate(obs), dtype=np.float32)
        obs, _, term, trunc, info = env.step(act)
        drone = unwrapped.env.drones[0]
        pos = drone.state[3]
        if term or trunc:
            term_reason = f"Term: {term}, Trunc: {trunc}, Crashed: {info.get('crashed')}, Stalling: {info.get('stalling')}"
            print(f"Test D ended at Step {step} ({step/30.0:.2f}s)")
            print(f"Final Pos: x={pos[0]:.1f}, y={pos[1]:.1f}, z={pos[2]:.2f}")
            print(f"Final Airspeed: {info.get('airspeed', 0.0):.1f} m/s")
            print(f"Waypoints reached: {unwrapped.waypoints.num_targets_reached} / 5")
            print(f"Termination Reason: {term_reason}")
            print(f"Ground impact flag (collision): {unwrapped.env.contact_array[0] if hasattr(unwrapped.env, 'contact_array') else 'N/A'}")
            break
    metrics_d = env.get_metrics()
    print("Metrics D:", {k: v for k, v in metrics_d.items() if k in ['flight_time', 'distance', 'airspeed', 'crashed', 'stalling']})
    env.close()

    # 2. Test B
    print("\n" + "=" * 60)
    print("RUNNING TEST B DIAGNOSTIC...")
    cfg["simulation"]["episode_duration"] = 25.0
    env2 = FixedwingEnv(config=cfg, model_dir=temp_dir)
    unwrapped2 = env2.env.unwrapped
    unwrapped2.flight_dome_size = 1000.0
    unwrapped2.waypoints.targets = np.array([
        [150.0,   0.0, 10.0],
        [236.6,  50.0, 15.0],
        [151.7, -34.8, 10.0],
        [300.0, -34.8, 12.0],
    ])
    unwrapped2.waypoints.num_targets = 4
    unwrapped2.waypoints.goal_reach_distance = 2.0
    env2.max_steps = int(25.0 * env2.control_hz)

    obs, _ = env2.reset(seed=42)
    for step in range(env2.max_steps):
        act = np.asarray(net.activate(obs), dtype=np.float32)
        obs, _, term, trunc, info = env2.step(act)
        drone = unwrapped2.env.drones[0]
        pos = drone.state[3]
        if term or trunc:
            term_reason = f"Term: {term}, Trunc: {trunc}, Crashed: {info.get('crashed')}, Stalling: {info.get('stalling')}"
            print(f"Test B ended at Step {step} ({step/30.0:.2f}s)")
            print(f"Final Pos: x={pos[0]:.1f}, y={pos[1]:.1f}, z={pos[2]:.2f}")
            print(f"Final Airspeed: {info.get('airspeed', 0.0):.1f} m/s")
            print(f"Waypoints reached: {unwrapped2.waypoints.num_targets_reached} / 4")
            print(f"Termination Reason: {term_reason}")
            break
    metrics_b = env2.get_metrics()
    print("Metrics B:", {k: v for k, v in metrics_b.items() if k in ['flight_time', 'distance', 'airspeed', 'crashed', 'stalling']})
    env2.close()

    shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    main()
