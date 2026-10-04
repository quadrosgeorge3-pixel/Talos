import sqlite3, sys, json
sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect("output/icarus.db")

# ── All Experiments ──
exps = conn.execute("SELECT experiment_id, status, best_fitness, best_generation FROM experiment_metadata").fetchall()
print("=" * 100)
print("  EXPERIMENTS IN ICARUS DB")
print("=" * 100)
for e in exps:
    bf = f"{e[2]:.1f}" if e[2] is not None else "N/A"
    bg = e[3] if e[3] is not None else "N/A"
    print(f"  {e[0]:<30} status={str(e[1]):<12} best_fitness={bf}  best_gen={bg}")

# ── Morphology Champions ──
print("\n" + "=" * 100)
print("  MORPHOLOGY CHAMPIONS (Top individual per experiment)")
print("=" * 100)

exp_ids = [e[0] for e in exps]
for eid in exp_ids:
    champ = conn.execute("""
        SELECT experiment_id, generation, individual_index, fitness, survival_time, distance, 
               crashed, morphology_json
        FROM individuals WHERE experiment_id=? ORDER BY fitness DESC LIMIT 1
    """, (eid,)).fetchone()
    if champ:
        print(f"\n  >> {champ[0]} | Gen {champ[1]} | Fitness {champ[3]:.1f} | Survived {champ[4]:.1f}s | Dist {champ[5]:.1f}m | Crashed={champ[6]}")
        if champ[7]:
            m = json.loads(champ[7])
            try:
                ws = m.get('wing_span', 0)
                wc = m.get('wing_chord', 0)
                hs = m.get('htail_span', 0)
                vs = m.get('vtail_height', 0)
                fl = m.get('fuselage_length', 0)
                fr = m.get('fuselage_radius', 0)
                wing_area = float(ws) * float(wc)
                print(f"    Morphology: wing={float(ws):.3f}x{float(wc):.3f} (area={wing_area:.4f}), htail_span={float(hs):.3f}, vtail_h={float(vs):.3f}, fuse={float(fl):.3f}x{float(fr):.3f}")
            except (TypeError, ValueError):
                print(f"    Morphology: (non-standard format)")

# ── All-time Benchmark Records ──
print("\n" + "=" * 100)
print("  ALL-TIME BENCHMARK RECORDS")
print("=" * 100)

rows = conn.execute("""
    SELECT test_name, controller_id, controller_type, flight_time, distance,
           mean_airspeed, mean_altitude, altitude_error, max_lateral_dev,
           control_energy, crashed, stalling, waypoints_hit
    FROM benchmark_evaluations ORDER BY id
""").fetchall()

# Distance record
rows_sorted = sorted(rows, key=lambda x: x[4], reverse=True)
r = rows_sorted[0]
print(f"\n  [DISTANCE]    {r[4]:.1f}m by {r[1]} ({r[2]}) in {r[0]}")
# Speed record
rows_sorted = sorted(rows, key=lambda x: x[5], reverse=True)
r = rows_sorted[0]
print(f"  [SPEED]       {r[5]:.1f}m/s by {r[1]} ({r[2]}) in {r[0]}")
# Waypoints record
wp_rows = [r for r in rows if r[12] > 0]
wp_rows.sort(key=lambda x: (x[12], x[4]), reverse=True)
if wp_rows:
    r = wp_rows[0]
    print(f"  [WAYPOINTS]   {r[12]}/4 by {r[1]} ({r[2]}) in {r[0]}")
# No-crash distance
nc_rows = [r for r in rows if not r[10]]
nc_rows.sort(key=lambda x: x[4], reverse=True)
r = nc_rows[0]
print(f"  [NO-CRASH]    {r[4]:.1f}m by {r[1]} ({r[2]}) in {r[0]}")

# ── Top 3 per Test ──
tests_map = {}
for r in rows:
    tname = r[0]
    if "Test A" in tname: key = "Test A"
    elif "Test B" in tname: key = "Test B"
    elif "Test C" in tname: key = "Test C"
    else: key = tname
    if key not in tests_map: tests_map[key] = []
    tests_map[key].append(r)

for test_key in ["Test A", "Test B", "Test C"]:
    entries = tests_map.get(test_key, [])
    entries.sort(key=lambda x: x[4], reverse=True)  # by distance
    print(f"\n{'─' * 100}")
    print(f"  TOP 3: {test_key}")
    print(f"{'─' * 100}")
    for i, e in enumerate(entries[:3]):
        crash = "CRASHED" if e[10] else "survived"
        print(f"  #{i+1}  {e[1]:<28} ({e[2]})")
        print(f"      Distance: {e[4]:.1f}m | Speed: {e[5]:.1f}m/s | Alt: {e[6]:.1f}m | Time: {e[3]:.1f}s | {crash} | Gates: {e[12]}/4 | LatDev: {e[8]:.1f}m")

# ── Trajectory record holder ──
print(f"\n{'=' * 100}")
print(f"  CURRENT RECORD HOLDER TRAJECTORY")
print(f"{'=' * 100}")
record = conn.execute("""
    SELECT controller_id, controller_type, test_name, distance, mean_airspeed, 
           mean_altitude, flight_time, waypoints_hit, crashed, trajectory_json
    FROM benchmark_evaluations
    ORDER BY distance DESC LIMIT 1
""").fetchone()
print(f"\n  Controller: {record[0]} ({record[1]})")
print(f"  Test:       {record[2]}")
print(f"  Distance:   {record[3]:.1f}m")
print(f"  Speed:      {record[4]:.1f}m/s")
print(f"  Altitude:   {record[5]:.1f}m")
print(f"  Flight T:   {record[6]:.1f}s")
print(f"  Waypoints:  {record[7]}/4")
print(f"  Crashed:    {bool(record[8])}")

if record[9]:
    traj = json.loads(record[9])
    pts = traj.get('positions', [])
    if pts:
        start = pts[0]
        end = pts[-1]
        print(f"  Trajectory:  {len(pts)} points, start=({start[0]:.1f},{start[1]:.1f},{start[2]:.1f}), end=({end[0]:.1f},{end[1]:.1f},{end[2]:.1f})")
        
        # Compute range
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        zs = [p[2] for p in pts]
        print(f"  Extents:     X=[{min(xs):.1f}, {max(xs):.1f}], Y=[{min(ys):.1f}, {max(ys):.1f}], Z=[{min(zs):.1f}, {max(zs):.1f}]")

conn.close()
