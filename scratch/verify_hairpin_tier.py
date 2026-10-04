import sys
sys.path.insert(0, '.')
import json
from src.genome.morphology import MorphologyGenome
from src.experiment.metadata import load_config
from src.simulation.evaluator import compute_fitness_detailed

cfg = load_config('configs/coevolution/p4_ultima_coevo.json')
bounds = cfg['morphology']['bounds']
print('Active bounds:', bounds)

with open('output/checkpoints/talos-p4-ultima-morph-360.json', 'r') as f:
    saved = json.load(f)

# Test restoring with bounds
first_gid = list(saved.keys())[0]
raw_morph = saved[first_gid]
print('Raw saved v_tail_area:', raw_morph.get('v_tail_area'))
clamped_morph = MorphologyGenome.from_dict(raw_morph, bounds=bounds)
print('Clamped v_tail_area:', clamped_morph.to_dict().get('v_tail_area'))
print('Clamped wingspan:', clamped_morph.to_dict().get('wingspan'))

# Test compute_fitness_detailed for Gen 360
test_metrics = {
    'flight_time': 20.0,
    'energy': 20.0,
    'distance': 1200.0,
    'altitude_error': 1.2,
    'mean_airspeed': 58.0,
    'waypoints_hit': 3,
    'progress_to_wp': 85.0,
    'min_waypoint_dist': 12.0,
    'crashed': False,
    'stalling': False,
}
res = compute_fitness_detailed(test_metrics, cfg, generation=360)
print('Gen 360 Fitness:', res['fitness'])
print('Fitness Components:', json.dumps(res['components'], indent=2))
