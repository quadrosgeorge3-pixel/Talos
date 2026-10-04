import sqlite3
import json
import numpy as np

conn = sqlite3.connect('output/icarus.db')
c = conn.cursor()

gens_to_check = [48, 49, 50, 51, 52, 53, 59, 60, 61, 62]
print(f"{'Gen':<4} | {'Index':<5} | {'Fitness':<8} | {'Dist':<7} | {'Surv':<5} | {'Span':<5} | {'Area':<5} | {'Mass':<5} | {'T/W':<5} | {'CG_x':<6} | {'V_tail':<6} | {'H_tail':<6}")
print("-" * 95)

for g in gens_to_check:
    row = c.execute("""
        SELECT generation, individual_index, fitness, distance, survival_time, morphology_json
        FROM individuals
        WHERE experiment_id = 'TALOS-P3C' AND generation = ? AND is_elite = 1
        ORDER BY fitness DESC LIMIT 1
    """, (g,)).fetchone()
    if row:
        gen, idx, fit, dist, surv, m_json = row
        m = json.loads(m_json)
        print(f"{gen:<4} | {idx:<5} | {fit:<8.3f} | {dist:<7.1f} | {surv:<5.1f} | {m['wingspan']:<5.2f} | {m['wing_area']:<5.2f} | {m['total_mass']:<5.2f} | {m['thrust_to_weight']:<5.2f} | {m['cg_x_offset']:<6.3f} | {m['v_tail_area']:<6.3f} | {m['h_tail_area']:<6.3f}")

conn.close()
