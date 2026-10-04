import sqlite3

con = sqlite3.connect('output/icarus.db')
cur = con.cursor()

# Check existing baselines
cur.execute("SELECT * FROM baseline_metrics")
rows = cur.fetchall()
cols = [d[0] for d in cur.description]

# Add plain-English aliases:
# 1. B0_default_pid -> pid_bounded_100m
# 2. TALOS-B01 -> pid_open_sky

for row in rows:
    r_dict = dict(zip(cols, row))
    b_id = r_dict['baseline_id']
    
    if b_id == 'B0_default_pid':
        new_id = 'pid_bounded_100m'
    elif b_id == 'TALOS-B01':
        new_id = 'pid_open_sky'
    else:
        continue
    
    cur.execute("SELECT 1 FROM baseline_metrics WHERE baseline_id = ?", (new_id,))
    if not cur.fetchone():
        r_dict['baseline_id'] = new_id
        r_dict['experiment_id'] = new_id
        keys = list(r_dict.keys())
        vals = list(r_dict.values())
        placeholders = ', '.join(['?'] * len(keys))
        cur.execute(f"INSERT INTO baseline_metrics ({', '.join(keys)}) VALUES ({placeholders})", vals)
        print(f"Added friendly alias: {new_id}")

con.commit()

# Print current baselines
cur.execute("SELECT baseline_id, distance_mean, survival_time_mean, energy_mean, altitude_error_mean FROM baseline_metrics")
print("\nAll Available Baselines in DB:")
for r in cur.fetchall():
    print(f"  * {r[0]:<20} | Dist: {r[1]:6.1f}m | AirTime: {r[2]:5.2f}s | Energy: {r[3]:4.2f} | AltErr: {r[4]:4.2f}m")

con.close()
