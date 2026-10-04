import sqlite3

conn = sqlite3.connect('output/icarus.db')
c = conn.cursor()

print("--- GENERATIONS 110 to LATEST ---")
rows = c.execute('''
    SELECT g.generation, g.best_fitness, g.best_distance, g.best_survival_time,
           i.crashed, i.stalling, i.altitude_error, i.airspeed_error, i.morphology_json
    FROM generations g
    JOIN individuals i ON g.experiment_id = i.experiment_id AND g.generation = i.generation
    WHERE g.experiment_id='TALOS-P4-ULTIMA' AND g.generation >= 110
    ORDER BY g.generation ASC
''').fetchall()

import json

for r in rows:
    gen, fit, dist, time, crash, stall, alt_err, spd_err, morph_json = r
    spd = dist / max(0.1, time)
    m = json.loads(morph_json) if morph_json else {}
    print(f"Gen {gen:3d} | Spd: {spd:5.1f}m/s | Crash: {crash} | Fit: {fit:.4f} | AltErr: {alt_err:5.1f}m | T/W: {m.get('thrust_to_weight', 0):.2f} | Span: {m.get('wingspan', 0):.2f}m | Mass: {m.get('total_mass', 0):.2f}kg")

conn.close()
