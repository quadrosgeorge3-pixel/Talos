import sqlite3
con = sqlite3.connect('output/icarus.db')
cur = con.cursor()
for cid in ['pid_open_sky', 'p3c_champ_neat_gen300', 'p3c_champ_pid']:
    rows = cur.execute('SELECT test_name, flight_time, distance, mean_airspeed, waypoints_hit, precision_score, crashed FROM benchmark_evaluations WHERE controller_id = ? ORDER BY test_name', (cid,)).fetchall()
    print(f'=== {cid} ===')
    for r in rows:
        print(r)
