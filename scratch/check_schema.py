import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect("output/icarus.db")
rows = conn.execute("SELECT sql FROM sqlite_master WHERE type='table'").fetchall()
for r in rows:
    print(r[0])
    print()
conn.close()
