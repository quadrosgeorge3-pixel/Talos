import sys, json
sys.path.insert(0, '.')
import neat

# Inspect Gen 375 champion topology
chk = 'output/checkpoints/talos-p4-ultima-chk-375'
pop = neat.Checkpointer.restore_checkpoint(chk)
best = max(pop.population.values(), key=lambda g: g.fitness or -999)
print(f'Gen 375 Champion: ID={best.key}, Fitness={best.fitness}')
print(f'  Nodes: {len(best.nodes)}, Enabled Conns: {sum(1 for c in best.connections.values() if c.enabled)}')

# Morphology
with open('output/checkpoints/talos-p4-ultima-morph-375.json','r') as f:
    morphs = json.load(f)
m = morphs.get(str(best.key), list(morphs.values())[0])
print(f'  Morphology: {json.dumps(m, indent=2)}')
