import os
import sys
sys.path.insert(0, '.')
import json
from scratch.quick_eval_benchmark import evaluate_and_store_gen

res = evaluate_and_store_gen(375, label='TALOS-P4-ULTIMA_gen375_hairpin')
with open('scratch/gen375_results.json', 'w') as f:
    json.dump(res, f, indent=2, default=str)
print('GEN375_EVAL_COMPLETE')
