import os
import sys
sys.path.insert(0, '.')
from src.experiment.metadata import load_config
from src.simulation.evaluator import compute_fitness_detailed

cfg = load_config('configs/coevolution/p4_ultima_coevo.json')
dummy_metrics = {
    'flight_time': 20.0, 'altitude_error': 0.5, 'mean_airspeed': 55.0,
    'waypoints_hit': 4, 'crashed': False, 'stalling': False
}

for g in [299, 300, 332]:
    res = compute_fitness_detailed(dummy_metrics, cfg, generation=g)
    fit = res["fitness"]
    spd = res["components"].get("speed_reward", 0.0)
    print(f"Gen {g}: Fitness={fit:.2f}, SpeedReward={spd:.2f}")
