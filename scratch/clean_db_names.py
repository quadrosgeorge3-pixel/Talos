import sqlite3

conn = sqlite3.connect('output/icarus.db')
c = conn.cursor()
c.execute("SELECT id, test_name FROM benchmark_evaluations")
rows = c.fetchall()
for row_id, name in rows:
    # normalize any non-ascii characters
    clean_name = name.encode('ascii', errors='ignore').decode('ascii').replace('  ', ' - ').strip()
    if clean_name != name:
        c.execute("UPDATE benchmark_evaluations SET test_name = ? WHERE id = ?", (clean_name, row_id))

conn.commit()

c.execute("SELECT id, test_name, controller_id, controller_type, flight_time, distance, waypoints_hit FROM benchmark_evaluations")
for r in c.fetchall():
    print(r)

conn.close()
