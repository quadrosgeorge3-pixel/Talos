import neat
import json
import numpy as np

def main():
    pop170 = neat.Checkpointer.restore_checkpoint('output/checkpoints/talos-p4-ultima-chk-170')
    morph170 = json.load(open('output/checkpoints/talos-p4-ultima-morph-170.json'))

    wingspans = [m['wingspan'] for m in morph170.values()]
    masses = [m['total_mass'] for m in morph170.values()]
    tws = [m['thrust_to_weight'] for m in morph170.values()]
    h_tails = [m['h_tail_area'] for m in morph170.values()]
    v_tails = [m['v_tail_area'] for m in morph170.values()]
    cg_offsets = [m['cg_x_offset'] for m in morph170.values()]

    print(f"--- POPULATION MORPHOLOGY AT GEN 170 (N = {len(morph170)}) ---")
    print(f"Wingspan: mean={np.mean(wingspans):.2f}m, std={np.std(wingspans):.3f} (min={np.min(wingspans):.2f}, max={np.max(wingspans):.2f})")
    print(f"Mass: mean={np.mean(masses):.2f}kg, std={np.std(masses):.3f} (min={np.min(masses):.2f}, max={np.max(masses):.2f})")
    print(f"Thrust-to-Weight: mean={np.mean(tws):.2f}, std={np.std(tws):.3f}")
    print(f"H-Tail: mean={np.mean(h_tails):.3f}m2, std={np.std(h_tails):.3f}")
    print(f"V-Tail: mean={np.mean(v_tails):.3f}m2, std={np.std(v_tails):.3f}")
    print(f"CG Offset: mean={np.mean(cg_offsets):.3f}, std={np.std(cg_offsets):.3f}")

    # Check Neural Network Complexity
    conn_counts = [len(g.connections) for g in pop170.population.values()]
    node_counts = [len(g.nodes) for g in pop170.population.values()]
    print(f"\n--- NEURAL NETWORK TOPOLOGY AT GEN 170 ---")
    print(f"Nodes: mean={np.mean(node_counts):.1f}, max={np.max(node_counts)}, min={np.min(node_counts)}")
    print(f"Connections: mean={np.mean(conn_counts):.1f}, max={np.max(conn_counts)}, min={np.min(conn_counts)}")
    best = max(pop170.population.values(), key=lambda g: g.fitness or -999)
    print(f"Best Gen 170 Genome {best.key}: {len(best.nodes)} nodes, {len(best.connections)} connections, Fitness: {best.fitness:.4f}")

    # Let's inspect Gen 170, 200, 210, 220, 230, 240
    for gen in [170, 200, 210, 220, 230, 240]:
        try:
            m_data = json.load(open(f'output/checkpoints/talos-p4-ultima-morph-{gen}.json'))
            p_data = neat.Checkpointer.restore_checkpoint(f'output/checkpoints/talos-p4-ultima-chk-{gen}')
            b = max(p_data.population.values(), key=lambda g: g.fitness or -999)
            bm = m_data[str(b.key)]
            print(f"\n[GEN {gen} CHAMP (ID {b.key})]")
            print(f"  Wingspan: {bm['wingspan']:.2f}m | Area: {bm['wing_area']:.3f}m2 | Mass: {bm['total_mass']:.2f}kg | T/W: {bm['thrust_to_weight']:.2f}")
            print(f"  H-Tail: {bm['h_tail_area']:.3f}m2 | V-Tail: {bm['v_tail_area']:.3f}m2 | CG Offset: {bm['cg_x_offset']:.3f}")
            print(f"  NN Nodes: {len(b.nodes)} | Conns: {len(b.connections)} | Fitness: {b.fitness:.4f}")
            
            # Pop stats
            masses = [m['total_mass'] for m in m_data.values()]
            spans = [m['wingspan'] for m in m_data.values()]
            cgs = [m['cg_x_offset'] for m in m_data.values()]
            print(f"  POP AVG -> Mass: {np.mean(masses):.2f}kg | Span: {np.mean(spans):.2f}m | CG: {np.mean(cgs):.3f}")
        except Exception as e:
            print(f"Gen {gen} check error: {e}")

if __name__ == "__main__":
    main()

