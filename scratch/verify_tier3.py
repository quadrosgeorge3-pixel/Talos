import sys
sys.path.insert(0, '.')
import numpy as np
from src.experiment.metadata import load_config
from src.simulation.evaluator import compute_fitness_detailed

config = load_config('configs/coevolution/p4_ultima_coevo.json')

test_cases = [
    ('High Speed + Tight Discipline (Target Ideal)', {
        'flight_time': 20.0, 'altitude_error': 0.5, 'mean_airspeed': 55.0,
        'waypoints_hit': 4, 'crashed': False, 'stalling': False
    }),
    ('High Speed + Poor Altitude Discipline', {
        'flight_time': 20.0, 'altitude_error': 6.0, 'mean_airspeed': 65.0,
        'waypoints_hit': 2, 'crashed': False, 'stalling': False
    }),
    ('High Speed Dive / Crash', {
        'flight_time': 12.0, 'altitude_error': 4.0, 'mean_airspeed': 60.0,
        'waypoints_hit': 3, 'crashed': True, 'stalling': False
    }),
    ('Clean Sweep 4/4 Flawless Master', {
        'flight_time': 20.0, 'altitude_error': 0.2, 'mean_airspeed': 62.0,
        'waypoints_hit': 4, 'crashed': False, 'stalling': False
    }),
]

print('=== VALIDATING NEW TIER 3 CURRICULUM (GEN 330) ===')
for label, m in test_cases:
    res = compute_fitness_detailed(m, config, generation=330)
    c = res["components"]
    print(f"\nCase: {label}")
    print(f"   Fitness: {res['fitness']:.2f}")
    print(f"   Speed Reward: {c['speed_reward']:.2f}")
    print(f"   Alt Discipline: {c['alt_discipline']:.4f}")
    print(f"   Clean Sweep Bounty: {c['clean_sweep_bounty']:.2f}")
