import sys
import json
sys.path.insert(0, '.')
from src.simulation.evaluator import compute_fitness_detailed
with open('configs/coevolution/p4_ultima_coevo.json') as f:
    cfg = json.load(f)
metrics = {'flight_time': 20.0, 'distance': 1000.0, 'energy': 10.0, 'altitude_error': 0.5, 'mean_airspeed': 60.0, 'waypoints_hit': 3, 'crashed': False, 'stalling': False}
res = compute_fitness_detailed(metrics, cfg, generation=350)
print('Fitness at gen 350 with current evaluator:', res['fitness'])
