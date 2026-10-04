import os
import json

path = 'configs/coevolution/p4_ultima_coevo.json'
with open(path, 'r') as f:
    cfg = json.load(f)

print('curriculum_milestones in config:', cfg.get('fitness', {}).get('curriculum_milestones', {}))
