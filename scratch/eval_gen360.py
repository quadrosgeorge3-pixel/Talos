import os
import sys
sys.path.insert(0, '.')
import json
from scratch.quick_eval_benchmark import evaluate_and_store_gen

res = evaluate_and_store_gen(360, label='TALOS-P4-ULTIMA_gen360_pre_hairpin')
with open('scratch/gen360_baseline_results.json', 'w') as f:
    json.dump(res, f, indent=2, default=str)
print('GEN360_EVAL_COMPLETE')
