import sqlite3

con = sqlite3.connect('output/icarus.db')
cur = con.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print("Tables in DB:", tables)

for table in tables:
    cur.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cur.fetchall()]
    print(f"\nTable {table}: {cols}")

cur.execute('SELECT max(generation) FROM generations')
max_gen = cur.fetchone()[0]
print(f"\n--- Latest Generation in DB: {max_gen} ---")

cur.execute('SELECT * FROM generations WHERE generation=?', (max_gen,))
print("Gen row:", cur.fetchone())

cur.execute('SELECT * FROM individuals WHERE generation=? ORDER BY fitness DESC LIMIT 1', (max_gen,))
ind_desc = [d[0] for d in cur.description]
ind_row = cur.fetchone()
print("Top Ind row of latest gen:")
for col, val in zip(ind_desc, ind_row):
    if col not in ('controller_json', 'morphology_json'):
        print(f"  {col}: {val}")

# Also check all-time best individual
cur.execute('SELECT * FROM individuals ORDER BY fitness DESC LIMIT 1')
best_ind_desc = [d[0] for d in cur.description]
best_ind_row = cur.fetchone()
print("\n--- All-Time Best Individual across all generations ---")
for col, val in zip(best_ind_desc, best_ind_row):
    if col not in ('controller_json', 'morphology_json'):
        print(f"  {col}: {val}")

# If there's an evaluations or baselines table, print it
for t in ['baselines', 'experiments', 'benchmark', 'reference']:
    if t in tables:
        cur.execute(f"SELECT * FROM {t}")
        print(f"\nTable {t} rows:", cur.fetchall())

con.close()
