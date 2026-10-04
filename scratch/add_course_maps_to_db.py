import sqlite3
import json

db_path = "output/icarus.db"
con = sqlite3.connect(db_path)
cur = con.cursor()

# Check existing columns in benchmark_evaluations
cur.execute("PRAGMA table_info(benchmark_evaluations)")
existing_cols = [r[1] for r in cur.fetchall()]
print("Existing columns:", existing_cols)

# Add new columns if not present
new_cols = {
    "course_map_json": "TEXT",
    "arena_radius": "REAL DEFAULT 1000.0",
    "waypoint_radius": "REAL DEFAULT 2.0",
    "trajectory_json": "TEXT"
}

for col, col_type in new_cols.items():
    if col not in existing_cols:
        cur.execute(f"ALTER TABLE benchmark_evaluations ADD COLUMN {col} {col_type}")
        print(f"Added column: {col}")

# Define course maps
wp_course_b = [
    {"target": 1, "x": 150.0, "y": 0.0, "z": 10.0, "desc": "Straight leg"},
    {"target": 2, "x": 236.6, "y": 50.0, "z": 15.0, "desc": "+30 deg right, climb 15m"},
    {"target": 3, "x": 151.7, "y": -34.8, "z": 10.0, "desc": "-45 deg return diagonal"},
    {"target": 4, "x": 300.0, "y": -34.8, "z": 12.0, "desc": "Long straight finish"}
]

wp_course_c = [
    {"target": 1, "x": 80.0, "y": 45.0, "z": 22.0, "desc": "Sharp right bank, climb 22m"},
    {"target": 2, "x": 150.0, "y": -45.0, "z": 8.0, "desc": "Sharp left bank, dive 8m"},
    {"target": 3, "x": 220.0, "y": 45.0, "z": 25.0, "desc": "Rapid climb, reverse right"},
    {"target": 4, "x": 280.0, "y": -45.0, "z": 6.0, "desc": "Low terrain hug, reverse left"}
]

# Update row 1 (Test 2)
cur.execute("""
    UPDATE benchmark_evaluations 
    SET course_map_json = ?, arena_radius = 1000.0, waypoint_radius = 2.0
    WHERE id = 1
""", (json.dumps(wp_course_b),))

# Update row 2 (Test 3)
cur.execute("""
    UPDATE benchmark_evaluations 
    SET course_map_json = ?, arena_radius = 1000.0, waypoint_radius = 2.0
    WHERE id = 2
""", (json.dumps(wp_course_c),))

con.commit()

# Verify updated rows
cur.execute("SELECT id, test_name, arena_radius, waypoint_radius, course_map_json FROM benchmark_evaluations")
for r in cur.fetchall():
    print(f"\nRow {r[0]}: {r[1]}")
    print(f"  Arena: {r[2]}m | Waypoint Radius: {r[3]}m")
    print(f"  Course Map: {r[4]}")

con.close()
