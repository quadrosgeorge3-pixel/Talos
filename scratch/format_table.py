import sqlite3

con = sqlite3.connect('output/icarus.db')
cur = con.cursor()

# Get baseline
cur.execute('SELECT * FROM baseline_metrics WHERE baseline_id="B0_default_pid"')
base = cur.fetchone()
base_cols = [d[0] for d in cur.description]
b_dict = dict(zip(base_cols, base))

# Get current gen
cur.execute('SELECT max(generation) FROM generations')
max_g = cur.fetchone()[0]

cur.execute('''
    SELECT * FROM individuals 
    WHERE generation=? 
    ORDER BY fitness DESC LIMIT 1
''', (max_g,))
curr_ind = cur.fetchone()
curr_cols = [d[0] for d in cur.description]
c_dict = dict(zip(curr_cols, curr_ind))

# Get all-time best distance in C1 with 10s flight time
cur.execute('''
    SELECT * FROM individuals 
    WHERE experiment_id="C1" AND survival_time >= 9.9
    ORDER BY distance DESC LIMIT 1
''')
dist_ind = cur.fetchone()
d_dict = dict(zip(curr_cols, dist_ind))

print(f"=== Baseline B0 ===")
for k, v in b_dict.items():
    print(f"  {k}: {v}")

print(f"\n=== Current Gen {max_g} Best (Individual #{c_dict['id']}) ===")
for k in ['generation', 'fitness', 'distance', 'survival_time', 'altitude_error', 'airspeed_error', 'energy', 'crashed', 'stalling', 'nodes', 'connections']:
    print(f"  {k}: {c_dict[k]}")

print(f"\n=== All-Time Furthest 10s Flight (Gen {d_dict['generation']}, Individual #{d_dict['id']}) ===")
for k in ['generation', 'fitness', 'distance', 'survival_time', 'altitude_error', 'airspeed_error', 'energy', 'crashed', 'stalling', 'nodes', 'connections']:
    print(f"  {k}: {d_dict[k]}")

con.close()
