"""Quick verification: run to check imports and basic construction."""
from __future__ import annotations

import sys
import traceback

def main() -> None:
    errors = []

    modules = [
        "src.simulation.env",
        "src.simulation.evaluator",
        "src.genome.controller",
        "src.genome.morphology",
        "src.genome.urdf_gen",
        "src.experiment.db",
        "src.experiment.metadata",
        "src.dashboard.genome_viz",
        "src.dashboard.layout",
        "src.dashboard.themes",
        "src.dashboard.dashboard",
    ]

    print("Verifying imports...\n")
    for mod in modules:
        try:
            __import__(mod)
            print(f"  OK  {mod}")
        except Exception as exc:
            print(f"  FAIL  {mod}: {exc}")
            errors.append((mod, exc))

    print("\nVerifying core construction...\n")

    # NEATController config building
    try:
        from src.genome.controller import NEATController
        config = {
            "controller": {"num_inputs": 15, "num_outputs": 6,
                           "activation": "tanh", "output_activation": "sigmoid"},
            "neat_config": {"pop_size": 10, "fitness_criterion": "max",
                            "compatibility_threshold": 3.0, "conn_add_prob": 0.5,
                            "conn_delete_prob": 0.2, "node_add_prob": 0.3,
                            "node_delete_prob": 0.1, "weight_mutate_rate": 0.8,
                            "weight_replace_rate": 0.1, "weight_max": 3.0,
                            "weight_init_std": 1.0, "bias_mutate_rate": 0.7,
                            "bias_max": 3.0},
        }
        ctrl = NEATController(config)
        s = ctrl.get_genome_summary()
        print(f"  OK  NEATController: {len(ctrl.population.population)} genomes, "
              f"summary={s['nodes_total']} nodes / {s['connections_total']} conns")
    except Exception as exc:
        print(f"  FAIL  NEATController: {exc}")
        traceback.print_exc()

    # MorphologyGenome
    try:
        from src.genome.morphology import MorphologyGenome
        mg = MorphologyGenome()
        print(f"  OK  MorphologyGenome: {mg.to_dict()}")
    except Exception as exc:
        print(f"  FAIL  MorphologyGenome: {exc}")

    # ExperimentDB
    try:
        import tempfile, os
        from src.experiment.db import ExperimentDB
        with tempfile.TemporaryDirectory() as td:
            db = ExperimentDB(os.path.join(td, "test.db"))
            db.create_experiment("test", {}, "2025-01-01T00:00:00Z")
            row = db.get_experiment("test")
            print(f"  OK  ExperimentDB: experiment_id={row['experiment_id']}, status={row['status']}")
    except Exception as exc:
        print(f"  FAIL  ExperimentDB: {exc}")

    # Fitness computation
    try:
        from src.simulation.evaluator import compute_fitness
        cfg = {"simulation": {"episode_duration": 10.0},
               "fitness": {"weights": {"survival": 0.4, "efficiency": 0.3,
                                         "maneuverability": 0.3},
                           "penalties": {"crash": -100.0, "stall": -5.0}}}
        metrics = {"flight_time": 10.0, "distance": 200.0, "energy": 10.0,
                   "crashed": False, "stalling": False}
        score = compute_fitness(metrics, cfg)
        print(f"  OK  Fitness score: {score:.3f}")
    except Exception as exc:
        print(f"  FAIL  Fitness: {exc}")

    if errors:
        print(f"\n{len(errors)} import(s) failed")
        sys.exit(1)
    else:
        print("\nAll core modules verified.")


if __name__ == "__main__":
    main()