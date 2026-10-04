import os
import json
import neat

chk_morph = 'output/checkpoints/talos-p4-ultima-morph-325.json'
with open(chk_morph, 'r') as f:
    u_m = json.load(f)

chk_path = 'output/checkpoints/talos-p4-ultima-chk-325'
pop = neat.Checkpointer.restore_checkpoint(chk_path)
best_g = max(pop.population.values(), key=lambda g: g.fitness or -999)
print(f'Best genome ID in Gen 325: {best_g.key}, fitness: {best_g.fitness}')

best_morph = u_m.get(str(best_g.key), list(u_m.values())[0])
print('ULTIMA Gen 325 Morphology:', json.dumps(best_morph, indent=2))
