import os
import json

morph_path = 'models/TALOS-P3C/gen099/ind002/morphology.json'
with open(morph_path, 'r') as f:
    p3c_m = json.load(f)
print('P3C Gen 100 Morphology:', json.dumps(p3c_m, indent=2))

chk_morph = 'output/checkpoints/talos-p4-ultima-morph-315.json'
with open(chk_morph, 'r') as f:
    u_m = json.load(f)

# Find champion genome in chk 315
import neat
chk_path = 'output/checkpoints/talos-p4-ultima-chk-315'
pop = neat.Checkpointer.restore_checkpoint(chk_path)
best_g = max(pop.population.values(), key=lambda g: g.fitness or -999)
print(f'Best genome ID in Gen 315: {best_g.key}, fitness: {best_g.fitness}')

best_morph = u_m.get(str(best_g.key), list(u_m.values())[0])
print('ULTIMA Gen 315 Morphology:', json.dumps(best_morph, indent=2))
