import sqlite3
conn = sqlite3.connect('output/icarus.db')
c = conn.cursor()
c.execute('SELECT max(generation) FROM generations')
print('Max Gen:', c.fetchone()[0])
c.execute('SELECT generation, best_fitness, mean_fitness, best_survival_time, best_distance FROM generations ORDER BY generation DESC LIMIT 6')
for r in c.fetchall():
    print(r)
conn.close()
