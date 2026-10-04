import os
import sys
sys.path.insert(0, '.')
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

P1 = [200.0,   0.0, 12.0]
P2 = [ 20.0,  35.0, 12.0]
P3 = [ 20.0, -35.0, 12.0]
wp_course_e = np.array([
    P1, P2, P3,
    P1, P2, P3,
    P1, P2, P3
])

test_configs = [
    ("Test A - Open-Sky Straight Flight", None, 20.0, 1000.0, 2.0),
    ("Test B - Open-Sky Waypoint Course", wp_course_b, 25.0, 1000.0, 2.0),
    ("Test C - Aggressive Aero Slalom", wp_course_c, 25.0, 1000.0, 2.0),
    ("Test D - AUVSI SUAS Autonomous Challenge", wp_course_d, 30.0, 1000.0, 15.0),
    ("Test E - FAI F3D/F5D Pylon Racing", wp_course_e, 40.0, 1000.0, 10.0),
]

gen = 325
chk_path = f'output/checkpoints/talos-p4-ultima-chk-{gen}'
morph_path = f'output/checkpoints/talos-p4-ultima-morph-{gen}.json'

pop = neat.Checkpointer.restore_checkpoint(chk_path)
best_genome = max(pop.population.values(), key=lambda g: g.fitness or -999)
net = neat.nn.FeedForwardNetwork.create(best_genome, pop.config)

with open(morph_path, 'r', encoding='utf-8') as f:
    morph_dict = json.load(f)
best_gid = str(best_genome.key)
m_params = morph_dict.get(best_gid, list(morph_dict.values())[0])

morph = MorphologyGenome.from_dict(m_params)
model_dir = f'models/benchmark_gen{gen}'
generate_model_files(morph, model_dir)

results = {}
for test_name, wp_array, duration, dome, wp_rad in test_configs:
    print(f'Running {test_name} for Gen {gen}...')
    res = run_flight_simulation(
        controller_type='NEAT',
        controller_obj=net,
        custom_waypoints=wp_array,
        duration=duration,
        flight_dome_size=dome,
        seed=42,
        model_dir=model_dir
    )
    
    num_wp = len(wp_array) if wp_array is not None else 0
    wp_hit = res['waypoints_hit']
    crashed = res['crashed']
    
    if num_wp > 0:
        wp_pts = (wp_hit / float(num_wp)) * 50.0
    else:
        wp_pts = min(res['distance'] / 500.0, 1.0) * 50.0
        
    alt_err = res['altitude_error'] if res['altitude_error'] is not None else 10.0
    corridor_pts = max(0.0, 1.0 - (alt_err / 15.0)) * 30.0
    surv_pts = 20.0 if not crashed else 0.0
    prec_score = round(wp_pts + corridor_pts + surv_pts, 1)
    
    res_clean = {
        'flight_time': round(res['flight_time'], 2),
        'distance': round(res['distance'], 1),
        'mean_airspeed': round(res['mean_airspeed'], 1),
        'waypoints_hit': wp_hit,
        'num_waypoints': num_wp,
        'crashed': crashed,
        'precision_score': prec_score
    }
    results[test_name] = res_clean
    print(f'   Result: {res_clean}')

with open('scratch/gen325_results.json', 'w') as f:
    json.dump(results, f, indent=2)

print('EVAL_COMPLETE')
