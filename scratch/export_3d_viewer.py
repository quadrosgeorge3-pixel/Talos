"""Export all benchmark tests (Test A, B, C, D) to output/benchmark_3d_viewer.html.

Excludes Ultima data as requested, and packages all 9 historical controllers across
all 4 tests into a self-contained 3D interactive viewer.
"""
import json
import sqlite3
import re
import os

def main():
    db_path = "output/icarus.db"
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    # Query all benchmark evaluations excluding ULTIMA
    rows = cur.execute("""
        SELECT id, test_name, controller_id, controller_type,
               flight_time, distance, mean_airspeed, mean_altitude,
               altitude_error, max_lateral_dev, control_energy,
               crashed, stalling, waypoints_hit, arena_radius,
               waypoint_radius, course_map_json, trajectory_json
        FROM benchmark_evaluations
        WHERE controller_id NOT LIKE '%ULTIMA%'
        ORDER BY test_name, controller_id
    """).fetchall()
    con.close()

    print(f"Loaded {len(rows)} benchmark records from database.")

    runs = []
    for r in rows:
        (run_id, test_name, ctrl_id, ctrl_type, flight_time, distance,
         mean_airspeed, mean_altitude, alt_err, max_lat_dev, energy,
         crashed, stalling, waypoints_hit, arena_radius, wp_radius,
         course_json, traj_json) = r

        course = []
        if course_json:
            try:
                course = json.loads(course_json)
            except Exception:
                pass

        traj = []
        if traj_json:
            try:
                traj = json.loads(traj_json)
            except Exception:
                pass

        runs.append({
            "id": run_id,
            "test_name": test_name,
            "controller_id": ctrl_id,
            "controller_type": ctrl_type,
            "flight_time": float(flight_time or 0.0),
            "distance": float(distance or 0.0),
            "mean_airspeed": float(mean_airspeed or 0.0),
            "mean_altitude": float(mean_altitude or 0.0),
            "altitude_error": float(alt_err or 0.0),
            "max_lateral_dev": float(max_lat_dev or 0.0),
            "control_energy": float(energy or 0.0),
            "crashed": bool(crashed),
            "stalling": bool(stalling),
            "waypoints_hit": int(waypoints_hit or 0),
            "arena_radius": float(arena_radius or 1000.0),
            "waypoint_radius": float(wp_radius or 2.0),
            "course": course,
            "trajectory": traj,
        })

    runs_json = json.dumps(runs)

    # Read existing template
    viewer_path = "output/benchmark_3d_viewer.html"
    with open(viewer_path, "r", encoding="utf-8") as f:
        html = f.read()

    # 1. Update Test Filters in Header
    old_filters = '''<button class="pill-btn active" onclick="setTestFilter('all')">All Tests</button>
      <button class="pill-btn" onclick="setTestFilter('Test A')">Test A (Straight)</button>
      <button class="pill-btn" onclick="setTestFilter('Test B')">Test B (Waypoints)</button>
      <button class="pill-btn" onclick="setTestFilter('Test C')">Test C (Slalom)</button>'''
    
    new_filters = '''<button class="pill-btn active" onclick="setTestFilter('all')">All Tests</button>
      <button class="pill-btn" onclick="setTestFilter('Test A')">Test A (Straight)</button>
      <button class="pill-btn" onclick="setTestFilter('Test B')">Test B (Waypoints)</button>
      <button class="pill-btn" onclick="setTestFilter('Test C')">Test C (Slalom)</button>
      <button class="pill-btn" onclick="setTestFilter('Test D')">Test D (AUVSI SUAS)</button>'''
    
    if old_filters in html:
        html = html.replace(old_filters, new_filters)

    # 2. Update scrubber max to 30.0s
    html = re.sub(r'max="25"', 'max="30"', html)
    html = re.sub(r'0\.00 s / 25\.00 s', '0.00 s / 30.00 s', html)
    html = re.sub(r'let maxFlightDuration = 25\.0;', 'let maxFlightDuration = 30.0;', html)

    # 3. Update waypoint builder to support 15m radius Course D gates and dict format
    old_build_wp = '''    function buildWaypoints() {
      waypointObjects.forEach(w => scene.remove(w.mesh));
      waypointObjects = [];

      const courses = [];
      BENCHMARK_RUNS.forEach(r => {
        if (r.course && r.course.length > 0 && !courses.find(c => c.test === r.test_name)) {
          courses.push({ test: r.test_name, course: r.course });
        }
      });

      courses.forEach(c => {
        c.course.forEach((wp, wIdx) => {
          const wx = Array.isArray(wp) ? wp[0] : wp.x;
          const wy = Array.isArray(wp) ? wp[1] : wp.y;
          const wz = Array.isArray(wp) ? wp[2] : wp.z;
          const pos3d = simTo3D(wx, wy, wz);

          // Glowing holographic sphere for 2m gate radius
          const sphereGeo = new THREE.SphereGeometry(2.0, 16, 16);'''

    new_build_wp = '''    function buildWaypoints() {
      waypointObjects.forEach(w => scene.remove(w.mesh));
      waypointObjects = [];

      const courses = [];
      BENCHMARK_RUNS.forEach(r => {
        if (r.course && r.course.length > 0 && !courses.find(c => c.test === r.test_name)) {
          courses.push({ test: r.test_name, course: r.course, wpRadius: r.waypoint_radius || 2.0 });
        }
      });

      courses.forEach(c => {
        const isAuvsi = c.test.includes('Test D');
        const gateRadius = isAuvsi ? 15.0 : 2.0;

        c.course.forEach((wp, wIdx) => {
          let wx, wy, wz;
          if (Array.isArray(wp)) {
            wx = wp[0]; wy = wp[1]; wz = wp[2];
          } else if (wp.target) {
            wx = wp.target[0]; wy = wp.target[1]; wz = wp.target[2];
          } else {
            wx = wp.x; wy = wp.y; wz = wp.z;
          }
          const pos3d = simTo3D(wx, wy, wz);

          // Glowing holographic sphere for gate radius
          const sphereGeo = new THREE.SphereGeometry(gateRadius, isAuvsi ? 24 : 16, isAuvsi ? 24 : 16);'''

    if old_build_wp in html:
        html = html.replace(old_build_wp, new_build_wp)

    # 4. Update setTestFilter function to check Test D
    old_test_filter_fn = '''    function setTestFilter(mode) {
      activeTestFilter = mode;
      document.querySelectorAll('.view-filters .pill-btn').forEach(b => {
        if (['all', 'Test A', 'Test B', 'Test C'].includes(b.textContent.trim()) || b.textContent.includes(mode)) {
          b.classList.toggle('active', b.textContent.includes(mode) || (mode === 'all' && b.textContent === 'All Tests'));
        }
      });
      applyVisualStates();
    }'''

    new_test_filter_fn = '''    function setTestFilter(mode) {
      activeTestFilter = mode;
      document.querySelectorAll('.view-filters .pill-btn').forEach(b => {
        if (['all', 'Test A', 'Test B', 'Test C', 'Test D'].some(t => b.textContent.includes(t))) {
          b.classList.toggle('active', b.textContent.includes(mode) || (mode === 'all' && b.textContent === 'All Tests'));
        }
      });
      applyVisualStates();
    }'''

    if old_test_filter_fn in html:
        html = html.replace(old_test_filter_fn, new_test_filter_fn)

    # 5. Inject the new BENCHMARK_RUNS
    # Replace from const BENCHMARK_RUNS = ... to ;\n\n    let scene
    pattern = r'const BENCHMARK_RUNS = .*?;\s*let scene, camera'
    replacement = f'const BENCHMARK_RUNS = {runs_json};\n\n    let scene, camera'
    html = re.sub(pattern, replacement, html, flags=re.DOTALL)

    with open(viewer_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Successfully updated {viewer_path} with {len(runs)} benchmark runs!")

if __name__ == "__main__":
    main()
