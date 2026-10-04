import sqlite3
con = sqlite3.connect('output/icarus.db')
cur = con.cursor()
cur.execute('SELECT name FROM sqlite_master WHERE type=\'table\'')
print(cur.fetchall())
