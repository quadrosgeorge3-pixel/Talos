import os
import json
import neat

for gen in [300, 305, 310, 315, 320, 325]:
    chk = f'output/checkpoints/talos-p4-ultima-chk-{gen}'
    if os.path.isfile(chk):
        pop = neat.Checkpointer.restore_checkpoint(chk)
        best_g = max(pop.population.values(), key=lambda g: g.fitness or -999)
        print(f'Gen {gen}: best_id={best_g.key}, fitness={best_g.fitness:.4f}')
