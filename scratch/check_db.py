import sqlite3
conn = sqlite3.connect('output/icarus.db')
c = conn.cursor()
c.execute('PRAGMA table_info(generations)')
for r in c.fetchall():
    print(r)
c.execute('SELECT * FROM generations ORDER BY generation DESC LIMIT 3')
for r in c.fetchall():
    print(r)
conn.close()
