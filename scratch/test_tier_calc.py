import os
import sys
sys.path.insert(0, ".")
import json
import neat
from src.experiment.metadata import load_config
from src.simulation.evaluator import compute_fitness_detailed

config = load_config('configs/coevolution/p4_ultima_coevo.json')
chk_path = 'output/checkpoints/talos-p4-ultima-chk-325'
pop = neat.Checkpointer.restore_checkpoint(chk_path)
best_g = max(pop.population.values(), key=lambda g: g.fitness or -999)

dummy_metrics = {
    'flight_time': 20.0,
    'energy': 10.0,
    'distance': 1000.0,
    'altitude_error': 1.0,
    'mean_airspeed': 55.0,
    'waypoints_hit': 4,
    'progress_to_wp': 100.0,
    'crashed': False,
    'stalling': False
}

for test_gen in [295, 300, 325]:
    res = compute_fitness_detailed(dummy_metrics, config, generation=test_gen)
    print("Gen", test_gen, "Fitness:", res["fitness"], "Components:", res["components"])

