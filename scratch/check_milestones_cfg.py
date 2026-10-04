import json
with open('configs/coevolution/p4_ultima_coevo.json') as f:
    cfg = json.load(f)
print('curriculum_milestones in config:', cfg.get('fitness', {}).get('curriculum_milestones'))
