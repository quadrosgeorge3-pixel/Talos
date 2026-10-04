import os
import json
import neat

chk_path = 'output/checkpoints/talos-p4-ultima-chk-350'
pop = neat.Checkpointer.restore_checkpoint(chk_path)
best_g = max(pop.population.values(), key=lambda g: g.fitness or -999)
print(f'Best genome ID: {best_g.key}, fitness: {best_g.fitness}')
