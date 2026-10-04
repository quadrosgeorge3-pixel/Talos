import sqlite3
conn = sqlite3.connect('output/icarus.db')
c = conn.cursor()
c.execute('SELECT max(generation) FROM generations')
max_gen = c.fetchone()[0]
c.execute('SELECT generation, best_fitness, best_survival_time FROM generations ORDER BY generation DESC LIMIT 5')
rows = c.fetchall()
print('Current Gen:', max_gen)
for r in rows:
    print(r)
conn.close()
