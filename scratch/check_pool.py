import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect('output/icarus.db')

print('=== BENCHMARK POOL (all controller_ids that were tested) ===')
rows = conn.execute('SELECT controller_id, controller_type, COUNT(*) FROM benchmark_evaluations GROUP BY controller_id, controller_type ORDER BY controller_id').fetchall()
for r in rows:
    print(f'  {r[0]:<32} type={r[1]:<5} benchmarks={r[2]}')

print()
print('=== EXPERIMENTS IN DB ===')
rows = conn.execute('SELECT experiment_id, status, best_fitness, best_generation FROM experiment_metadata').fetchall()
for r in rows:
    bf = f"{r[2]:.3f}" if r[2] else "N/A"
    bg = r[3] if r[3] else "N/A"
    print(f'  {r[0]:<20} status={r[1]:<12} best_fit={bf}  best_gen={bg}')

print()
print('=== C1 EXPERIMENT TOP 3 ===')
rows = conn.execute('SELECT experiment_id, generation, fitness, survival_time, distance, crashed FROM individuals WHERE experiment_id="C1" ORDER BY fitness DESC LIMIT 3').fetchall()
for x in rows:
    print(f'  gen={x[1]} fitness={x[2]:.3f} surv={x[3]:.1f}s dist={x[4]:.1f}m crash={x[5]}')

print()
print('=== TALOS-B01 & B0_baseline_pid ===')
for eid in ['TALOS-B01', 'B0_baseline_pid']:
    rows = conn.execute(f'SELECT COUNT(*) FROM individuals WHERE experiment_id="{eid}"').fetchone()
    bench = conn.execute(f'SELECT COUNT(*) FROM benchmark_evaluations WHERE controller_id LIKE "%{eid}%"').fetchone()
    print(f'  {eid}: {rows[0]} individuals, {bench[0]} benchmark entries')

print()
print('=== MAPPING: Which experiment produced which benchmark contender? ===')
print('  pid_open_sky          -> B0_baseline_pid (default body + PID baseline)')
print('  phase2_neat_caged     -> C1 (early NEAT, bounded 100m dome)')
print('  TALOS-P2B_gen300_champ -> TALOS-P2B (300-gen NEAT brain, default body)')
print('  p3a_champ_*           -> TALOS-P3A (evolved body, NEAT pilot)')
print('  p3b_champ_*           -> TALOS-P3B (evolved body, PID pilot)')
print('  p3b_gen054_*          -> TALOS-P3B gen 54 (mid-evo snapshot)')
print('  p3c_champ_*           -> TALOS-P3C (co-evolved body, frozen NEAT brain)')

conn.close()
