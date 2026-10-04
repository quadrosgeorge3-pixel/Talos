import neat
import inspect

print("DefaultGenome.create_connection signature:")
print(inspect.signature(neat.DefaultGenome.create_connection))
print("DefaultGenome.create_node signature:")
print(inspect.signature(neat.DefaultGenome.create_node))
print("DefaultConnectionGene signature:")
print(inspect.signature(neat.genes.DefaultConnectionGene.__init__))
