import json
with open('output/talos-p4-ultima_trajectory.json', 'r') as f:
    t = json.load(f)
print('Generation:', t.get('generation'))
print('Waypoints hit:', t.get('waypoints_hit'))
print('Mean airspeed:', t.get('mean_airspeed'))
print('Distance:', t.get('distance'))
print('Crashed:', t.get('crashed'))
print('Morphology:', json.dumps(t.get('morphology'), indent=2))
