import os
import sys
sys.path.insert(0, ".")
import json
from scratch.quick_eval_benchmark import evaluate_and_store_gen

gen = 385
print(f"--- Running standard benchmark evaluation for Gen {gen} ---")
res = evaluate_and_store_gen(gen, label=f"TALOS-P4-ULTIMA_gen{gen}_hairpin")

if res:
    with open(f"scratch/gen{gen}_results.json", "w") as f:
        json.dump(res, f, indent=2, default=str)
    print(f"GEN{gen}_BENCHMARK_COMPLETE")
else:
    print(f"Failed to evaluate Gen {gen}")
