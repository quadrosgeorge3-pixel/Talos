import os
import json
import neat
chk = 'output/checkpoints/talos-p4-ultima-chk-325'
pop = neat.Checkpointer.restore_checkpoint(chk)
fits = sorted([g.fitness for g in pop.population.values() if g.fitness is not None], reverse=True)
print('Top 10 fitness values in Gen 325 checkpoint:', fits[:10])
