"""3D Benchmark Trajectory Visualizer Generator for Project Talos.

Extracts all benchmark flight trajectories and course waypoint maps from
output/icarus.db and generates a futuristic, high-performance 3D WebGL viewer
(Three.js) saved to output/benchmark_3d_viewer.html. Clean, unobstructed 3D arena
with top header dropdown flight selector, zero card overlay clutter, camera autofocus,
and course isolation.
"""
from __future__ import annotations

import json
import os
import sqlite3
from typing import Any, Dict, List


def fetch_benchmark_data(db_path: str = "output/icarus.db") -> List[Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
        SELECT id, test_name, controller_id, controller_type, flight_time, distance,
               mean_airspeed, mean_altitude, max_lateral_dev, control_energy,
               crashed, stalling, waypoints_hit, arena_radius, waypoint_radius,
               course_map_json, trajectory_json
        FROM benchmark_evaluations
        ORDER BY id
    """)
    rows = c.fetchall()
    conn.close()

    runs = []
    for r in rows:
        t_id, t_name, c_id, c_type, f_time, dist, spd, alt, lat_dev, energy, crash, stall, wp_hit, arena_r, wp_r, course_json, traj_json = r
        traj = json.loads(traj_json) if traj_json else []
        course = json.loads(course_json) if course_json else []
        runs.append({
            "id": t_id,
            "test_name": t_name,
            "controller_id": c_id,
            "controller_type": c_type,
            "flight_time": float(f_time or 0.0),
            "distance": float(dist or 0.0),
            "mean_airspeed": float(spd or 0.0),
            "mean_altitude": float(alt or 0.0),
            "max_lateral_dev": float(lat_dev or 0.0),
            "control_energy": float(energy or 0.0),
            "crashed": bool(crash),
            "stalling": bool(stall),
            "waypoints_hit": int(wp_hit or 0),
            "arena_radius": float(arena_r or 1000.0),
            "waypoint_radius": float(wp_r or 2.0),
            "course": course,
            "trajectory": traj,
        })
    return runs


def build_3d_html(runs: List[Dict[str, Any]]) -> str:
    runs_json = json.dumps(runs, indent=None)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Talos 3D Flight Arena — Benchmark Flight Trajectories</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
  <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
  <style>
    :root {{
      --bg-dark: #07090e;
      --panel-bg: rgba(13, 17, 26, 0.88);
      --panel-border: rgba(255, 255, 255, 0.12);
      --text-main: #f1f5f9;
      --text-dim: #94a3b8;
      --cyan: #00f0ff;
      --cyan-glow: rgba(0, 240, 255, 0.4);
      --magenta: #ff0055;
      --magenta-glow: rgba(255, 0, 85, 0.4);
      --gold: #fbbf24;
      --emerald: #10b981;
      --purple: #c084fc;
      --amber: #f59e0b;
    }}

    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      background-color: var(--bg-dark);
      color: var(--text-main);
      font-family: 'Inter', -apple-system, sans-serif;
      overflow: hidden;
      width: 100vw;
      height: 100vh;
      user-select: none;
    }}

    #canvas-container {{
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      z-index: 1;
    }}

    /* Top Floating Header Bar (Single Clean Row, No Overlap) */
    .header-bar {{
      position: absolute;
      top: 14px;
      left: 20px;
      right: 20px;
      z-index: 10;
      display: flex;
      align-items: center;
      gap: 12px;
      pointer-events: none;
      flex-wrap: nowrap;
      overflow-x: auto;
      padding-bottom: 4px;
    }}
    .header-bar > * {{ pointer-events: auto; flex-shrink: 0; }}
    .header-bar::-webkit-scrollbar {{ height: 4px; }}
    .header-bar::-webkit-scrollbar-thumb {{ background: rgba(255,255,255,0.2); border-radius: 4px; }}

    .brand-pill {{
      background: var(--panel-bg);
      backdrop-filter: blur(12px);
      border: 1px solid var(--panel-border);
      border-radius: 9999px;
      padding: 8px 16px;
      display: flex;
      align-items: center;
      gap: 10px;
      box-shadow: 0 10px 25px -5px rgba(0,0,0,0.5);
    }}
    .brand-dot {{
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: var(--cyan);
      box-shadow: 0 0 12px var(--cyan);
      animation: pulse 2s infinite;
    }}
    @keyframes pulse {{
      0%, 100% {{ transform: scale(1); opacity: 1; }}
      50% {{ transform: scale(1.3); opacity: 0.6; }}
    }}
    .brand-title {{
      font-weight: 700;
      letter-spacing: 0.06em;
      font-size: 12px;
      text-transform: uppercase;
      color: #fff;
    }}

    /* Clean Flight Selector Dropdown in Header */
    .flight-selector-pill {{
      display: flex;
      align-items: center;
      gap: 6px;
      background: var(--panel-bg);
      backdrop-filter: blur(12px);
      border: 1px solid var(--panel-border);
      border-radius: 9999px;
      padding: 4px 8px;
      box-shadow: 0 10px 25px -5px rgba(0,0,0,0.5);
    }}
    .selector-label {{
      font-size: 10px;
      font-weight: 700;
      color: var(--cyan);
      letter-spacing: 0.05em;
      text-transform: uppercase;
      padding-left: 6px;
    }}
    .flight-dropdown {{
      background: rgba(18, 24, 38, 0.95);
      border: 1px solid rgba(255, 255, 255, 0.2);
      color: #fff;
      padding: 6px 12px;
      border-radius: 9999px;
      font-size: 11.5px;
      font-family: 'JetBrains Mono', monospace;
      outline: none;
      cursor: pointer;
      max-width: 360px;
      transition: all 0.2s;
    }}
    .flight-dropdown:focus {{
      border-color: var(--cyan);
      box-shadow: 0 0 10px var(--cyan-glow);
    }}
    .flight-dropdown option, .flight-dropdown optgroup {{
      background: #0d111a;
      color: #f1f5f9;
    }}
    .nav-arrow-btn {{
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid var(--panel-border);
      color: #fff;
      padding: 5px 9px;
      border-radius: 9999px;
      font-size: 10px;
      font-weight: 700;
      cursor: pointer;
      transition: all 0.2s;
    }}
    .nav-arrow-btn:hover {{
      background: rgba(0, 240, 255, 0.2);
      color: var(--cyan);
      border-color: rgba(0, 240, 255, 0.4);
    }}

    /* View Filter Pills */
    .view-filters {{
      display: flex;
      gap: 4px;
      background: var(--panel-bg);
      backdrop-filter: blur(12px);
      border: 1px solid var(--panel-border);
      border-radius: 9999px;
      padding: 4px;
      box-shadow: 0 10px 25px -5px rgba(0,0,0,0.5);
    }}
    .pill-btn {{
      background: transparent;
      border: none;
      color: var(--text-dim);
      padding: 5px 11px;
      border-radius: 9999px;
      font-size: 11px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s ease;
      font-family: 'Inter', sans-serif;
      white-space: nowrap;
    }}
    .pill-btn:hover {{
      color: #fff;
      background: rgba(255, 255, 255, 0.08);
    }}
    .pill-btn.active {{
      background: linear-gradient(135deg, rgba(0, 240, 255, 0.2), rgba(0, 240, 255, 0.05));
      color: var(--cyan);
      border: 1px solid rgba(0, 240, 255, 0.4);
      box-shadow: 0 0 12px rgba(0, 240, 255, 0.2);
    }}
    .pill-btn.pill-isolate.active {{
      background: linear-gradient(135deg, rgba(245, 158, 11, 0.25), rgba(245, 158, 11, 0.08));
      color: #fbbf24;
      border: 1px solid rgba(245, 158, 11, 0.5);
      box-shadow: 0 0 12px rgba(245, 158, 11, 0.25);
    }}

    /* Legend Box */
    .legend-box {{
      display: flex;
      gap: 8px;
      font-size: 10px;
      font-family: 'JetBrains Mono', monospace;
      align-items: center;
      flex-wrap: nowrap;
    }}
    .legend-item {{
      display: flex;
      align-items: center;
      gap: 4px;
    }}
    .legend-color {{
      width: 9px;
      height: 4px;
      border-radius: 2px;
    }}

    /* Bottom Control Cockpit */
    .bottom-cockpit {{
      position: absolute;
      bottom: 16px;
      left: 20px;
      right: 20px;
      z-index: 10;
      background: var(--panel-bg);
      backdrop-filter: blur(16px);
      border: 1px solid var(--panel-border);
      border-radius: 14px;
      padding: 10px 18px;
      display: flex;
      align-items: center;
      gap: 14px;
      box-shadow: 0 15px 35px -5px rgba(0,0,0,0.6);
      flex-wrap: wrap;
    }}

    .cockpit-btn {{
      background: rgba(255, 255, 255, 0.07);
      border: 1px solid var(--panel-border);
      color: #fff;
      padding: 7px 14px;
      border-radius: 8px;
      font-size: 11.5px;
      font-weight: 600;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 6px;
      transition: all 0.2s;
      white-space: nowrap;
    }}
    .cockpit-btn:hover {{
      background: rgba(255, 255, 255, 0.15);
      border-color: rgba(255, 255, 255, 0.3);
    }}
    .cockpit-btn.play-btn {{
      background: var(--cyan);
      color: #07090e;
      border: none;
      box-shadow: 0 0 15px var(--cyan-glow);
    }}
    .cockpit-btn.play-btn:hover {{
      background: #38f4ff;
    }}

    .scrubber-container {{
      flex: 1;
      min-width: 180px;
      display: flex;
      flex-direction: column;
      gap: 3px;
    }}
    .scrubber-label {{
      display: flex;
      justify-content: space-between;
      font-size: 10.5px;
      font-family: 'JetBrains Mono', monospace;
      color: var(--text-dim);
    }}
    .scrubber-slider {{
      -webkit-appearance: none;
      width: 100%;
      height: 6px;
      border-radius: 3px;
      background: rgba(255, 255, 255, 0.15);
      outline: none;
      cursor: pointer;
    }}
    .scrubber-slider::-webkit-slider-thumb {{
      -webkit-appearance: none;
      appearance: none;
      width: 14px;
      height: 14px;
      border-radius: 50%;
      background: var(--cyan);
      box-shadow: 0 0 10px var(--cyan);
      cursor: pointer;
    }}

    /* Right Telemetry HUD Panel */
    .hud-panel {{
      position: absolute;
      top: 72px;
      right: 20px;
      width: 290px;
      z-index: 10;
      background: var(--panel-bg);
      backdrop-filter: blur(14px);
      border: 1px solid var(--panel-border);
      border-radius: 14px;
      padding: 14px;
      display: flex;
      flex-direction: column;
      gap: 9px;
      pointer-events: none;
    }}
    .hud-title {{
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--text-dim);
      border-bottom: 1px solid rgba(255,255,255,0.08);
      padding-bottom: 6px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .hud-row {{
      display: flex;
      justify-content: space-between;
      font-size: 11.5px;
    }}
    .hud-label {{ color: var(--text-dim); }}
    .hud-val {{
      font-family: 'JetBrains Mono', monospace;
      font-weight: 600;
      color: #fff;
    }}

    /* Camera preset buttons */
    .cam-btns {{
      display: flex;
      gap: 4px;
      pointer-events: auto;
    }}
    .cam-btn {{
      background: rgba(255,255,255,0.06);
      border: 1px solid var(--panel-border);
      color: var(--text-dim);
      padding: 3px 7px;
      border-radius: 5px;
      font-size: 9.5px;
      font-weight: 600;
      cursor: pointer;
    }}
    .cam-btn:hover {{ color: #fff; background: rgba(255,255,255,0.12); }}

    .selection-notice {{
      background: rgba(0, 240, 255, 0.08);
      border: 1px solid rgba(0, 240, 255, 0.25);
      border-radius: 6px;
      padding: 5px 8px;
      font-size: 10px;
      color: var(--cyan);
      display: flex;
      justify-content: space-between;
      align-items: center;
      pointer-events: auto;
    }}
  </style>
</head>
<body>

  <div id="canvas-container"></div>

  <!-- Top Floating Header (Unobstructed, Non-Colliding) -->
  <div class="header-bar">
    <div class="brand-pill">
      <div class="brand-dot"></div>
      <div class="brand-title">TALOS 3D FLIGHT ARENA</div>
    </div>

    <!-- Integrated Flight Selector Dropdown -->
    <div class="flight-selector-pill">
      <span class="selector-label">TRACK:</span>
      <select id="flight-select" class="flight-dropdown" onchange="onFlightSelectChange(this.value)">
        <!-- Dynamically populated -->
      </select>
      <button class="nav-arrow-btn" onclick="stepFlight(-1)" title="Previous Flight">◀ PREV</button>
      <button class="nav-arrow-btn" onclick="stepFlight(1)" title="Next Flight">NEXT ▶</button>
    </div>

    <!-- View Filter Pills -->
    <div class="view-filters">
      <button class="pill-btn active" onclick="setTestFilter('all')">All Tests</button>
      <button class="pill-btn" onclick="setTestFilter('Test A')">Test A</button>
      <button class="pill-btn" onclick="setTestFilter('Test B')">Test B</button>
      <button class="pill-btn" onclick="setTestFilter('Test C')">Test C</button>
      <span style="border-left: 1px solid rgba(255,255,255,0.15); margin: 2px 0;"></span>
      <button class="pill-btn" onclick="setAirframeFilter('all')">All Bodies</button>
      <button class="pill-btn" onclick="setAirframeFilter('P3C')">P3C Body</button>
      <button class="pill-btn" onclick="setAirframeFilter('P3B')">P3B Body</button>
      <button class="pill-btn" onclick="setAirframeFilter('P3A')">P3A Body</button>
      <button class="pill-btn" onclick="setAirframeFilter('STD')">Std Body</button>
      <span style="border-left: 1px solid rgba(255,255,255,0.15); margin: 2px 0;"></span>
      <button class="pill-btn pill-isolate" id="btn-isolate-mode" onclick="toggleIsolateMode()">⚡ Solo</button>
    </div>

    <!-- Legend -->
    <div class="legend-box brand-pill">
      <div class="legend-item">
        <div class="legend-color" style="background: var(--cyan); box-shadow: 0 0 6px var(--cyan);"></div>
        <span>Std PID</span>
      </div>
      <div class="legend-item">
        <div class="legend-color" style="background: var(--emerald); box-shadow: 0 0 6px var(--emerald);"></div>
        <span>Std Gen300</span>
      </div>
      <div class="legend-item">
        <div class="legend-color" style="background: var(--purple); box-shadow: 0 0 6px var(--purple);"></div>
        <span>P3A PID</span>
      </div>
      <div class="legend-item">
        <div class="legend-color" style="background: var(--amber); box-shadow: 0 0 6px var(--amber);"></div>
        <span>P3A Gen300</span>
      </div>
      <div class="legend-item">
        <div class="legend-color" style="background: #ff5722; box-shadow: 0 0 6px #ff5722;"></div>
        <span>P3B PID (48m/s)</span>
      </div>
      <div class="legend-item">
        <div class="legend-color" style="background: #f43f5e; box-shadow: 0 0 6px #f43f5e;"></div>
        <span>P3B Gen300</span>
      </div>
      <div class="legend-item">
        <div class="legend-color" style="background: #38bdf8; box-shadow: 0 0 6px #38bdf8;"></div>
        <span>P3C PID</span>
      </div>
      <div class="legend-item">
        <div class="legend-color" style="background: #a3e635; box-shadow: 0 0 6px #a3e635;"></div>
        <span>P3C Gen300 (1229m)</span>
      </div>
      <div class="legend-item">
        <div class="legend-color" style="background: var(--gold); border-radius: 50%; width: 6px; height: 6px;"></div>
        <span>Gates</span>
      </div>
    </div>
  </div>

  <!-- Right Telemetry HUD -->
  <div class="hud-panel" id="hud-panel">
    <div class="hud-title">
      <span>TELEMETRY FEED</span>
      <div class="cam-btns">
        <button class="cam-btn" onclick="setCameraView('iso')">ISO</button>
        <button class="cam-btn" onclick="setCameraView('top')">TOP</button>
        <button class="cam-btn" onclick="setCameraView('side')">SIDE</button>
        <button class="cam-btn" onclick="focusSelectedFlight()">FOCUS</button>
      </div>
    </div>

    <div class="selection-notice" id="selection-banner">
      <span id="selection-status-text">Comparing All Visible Flights</span>
      <button class="cam-btn" onclick="deselectFlight()">ALL</button>
    </div>

    <div class="hud-row">
      <span class="hud-label">Active Track</span>
      <span class="hud-val" id="hud-track" style="color: var(--cyan);">—</span>
    </div>
    <div class="hud-row">
      <span class="hud-label">Controller</span>
      <span class="hud-val" id="hud-ctrl">—</span>
    </div>
    <div class="hud-row">
      <span class="hud-label">Airframe</span>
      <span class="hud-val" id="hud-airframe">—</span>
    </div>
    <div class="hud-row">
      <span class="hud-label">Status</span>
      <span class="hud-val" id="hud-status">—</span>
    </div>
    <div style="border-top: 1px solid rgba(255,255,255,0.06); margin: 2px 0;"></div>
    <div class="hud-row">
      <span class="hud-label">Mission Time</span>
      <span class="hud-val" id="hud-time">0.00 s</span>
    </div>
    <div class="hud-row">
      <span class="hud-label">Distance Flown</span>
      <span class="hud-val" id="hud-dist">0.0 m</span>
    </div>
    <div class="hud-row">
      <span class="hud-label">Airspeed</span>
      <span class="hud-val" id="hud-speed">0.0 m/s</span>
    </div>
    <div class="hud-row">
      <span class="hud-label">Altitude (AGL)</span>
      <span class="hud-val" id="hud-alt">0.0 m</span>
    </div>
    <div class="hud-row">
      <span class="hud-label">Coordinates (X,Y,Z)</span>
      <span class="hud-val" id="hud-coords">(0, 0, 0)</span>
    </div>
    <div style="border-top: 1px solid rgba(255,255,255,0.06); margin: 2px 0;"></div>
    <div class="hud-row">
      <span class="hud-label">Waypoints Hit</span>
      <span class="hud-val" id="hud-wp" style="color: var(--gold);">— / 4</span>
    </div>
    <div class="hud-row">
      <span class="hud-label">Max Lateral Dev</span>
      <span class="hud-val" id="hud-latdev">—</span>
    </div>
    <div class="hud-row">
      <span class="hud-label">Control Energy</span>
      <span class="hud-val" id="hud-energy">—</span>
    </div>
  </div>

  <!-- Bottom Cockpit Scrubber -->
  <div class="bottom-cockpit">
    <button class="cockpit-btn play-btn" id="play-btn" onclick="togglePlay()">
      <span id="play-icon">▶</span> PLAY
    </button>
    <button class="cockpit-btn" onclick="resetPlayback()">⏮ RESET</button>
    <button class="cockpit-btn" onclick="cycleSpeed()">SPEED: <span id="speed-val">1x</span></button>

    <div class="scrubber-container">
      <div class="scrubber-label">
        <span>SIMULATION SCRUBBER</span>
        <span id="scrub-time">0.00 s / 25.00 s</span>
      </div>
      <input type="range" class="scrubber-slider" id="scrubber" min="0" max="25" step="0.05" value="0" oninput="onScrub(this.value)">
    </div>

    <button class="cockpit-btn" onclick="toggleDome()"><span id="dome-btn-text">🌐 DOMES</span></button>
    <button class="cockpit-btn" onclick="toggleTrails()">✨ TRAILS</button>
    <button class="cockpit-btn" onclick="deselectFlight()">↺ SHOW ALL</button>
  </div>

  <script>
    // --- Injected Benchmark Data ---
    const BENCHMARK_RUNS = {runs_json};

    let scene, camera, renderer, controls;
    let flightObjects = [];
    let waypointObjects = [];
    let dome100Mesh = null;
    let dome1000Mesh = null;
    let showDome = true;
    let showFullTrails = true;

    let isPlaying = true;
    let currentTime = 0.0;
    let playbackSpeed = 1.0;
    let maxFlightDuration = 25.0;

    let activeTestFilter = 'all';      // 'all', 'Test A', 'Test B', 'Test C'
    let activeAirframeFilter = 'all';  // 'all', 'P3A', 'STD'
    let isolateMode = false;           // If true, non-selected flights are completely hidden
    let selectedRunId = null;

    const SPEED_STEPS = [0.5, 1.0, 2.0, 4.0];
    let speedIdx = 1;

    function simTo3D(x, y, z) {{
      return new THREE.Vector3(y, z, -x);
    }}

    function getRunMetadata(run) {{
      const cid = (run.controller_id || '').toLowerCase();
      const ctype = (run.controller_type || '').toUpperCase();

      if (cid.includes('p3c') && ctype === 'PID') {{
        return {{
          category: 'p3c-pid',
          airframeType: 'P3C',
          color: 0x38bdf8,
          cssColor: '#38bdf8',
          glow: 'rgba(56, 189, 248, 0.45)',
          tagLabel: 'P3C BODY · PID',
          airframeLabel: 'P3C Fin-Stabilized Missile Airframe',
          controllerLabel: 'Fixed PID Pilot',
        }};
      }}
      if (cid.includes('p3c') && ctype === 'NEAT') {{
        return {{
          category: 'p3c-neat',
          airframeType: 'P3C',
          color: 0xa3e635,
          cssColor: '#a3e635',
          glow: 'rgba(163, 230, 53, 0.45)',
          tagLabel: 'P3C BODY · GEN 300 (1229m)',
          airframeLabel: 'P3C Fin-Stabilized Missile Airframe',
          controllerLabel: 'Open NEAT Gen 300 Champ (1.2km Record)',
        }};
      }}

      if (cid.includes('p3b') && ctype === 'PID') {{
        return {{
          category: 'p3b-pid',
          airframeType: 'P3B',
          color: 0xff5722,
          cssColor: '#ff5722',
          glow: 'rgba(255, 87, 34, 0.45)',
          tagLabel: 'P3B BODY · PID (RECORD)',
          airframeLabel: 'P3B High-Aspect Sailplane',
          controllerLabel: 'Fixed PID Pilot (48 m/s Record)',
        }};
      }}
      if (cid.includes('p3b') && ctype === 'NEAT') {{
        return {{
          category: 'p3b-neat',
          airframeType: 'P3B',
          color: 0xf43f5e,
          cssColor: '#f43f5e',
          glow: 'rgba(244, 63, 94, 0.45)',
          tagLabel: 'P3B BODY · GEN 300',
          airframeLabel: 'P3B High-Aspect Sailplane',
          controllerLabel: 'Open NEAT Gen 300 Champ',
        }};
      }}
      if (cid === 'p3a_champ_pid' || (cid.includes('p3a') && ctype === 'PID')) {{
        return {{
          category: 'p3a-pid',
          airframeType: 'P3A',
          color: 0xc084fc,
          cssColor: '#c084fc',
          glow: 'rgba(192, 132, 252, 0.45)',
          tagLabel: 'P3A BODY · PID',
          airframeLabel: 'P3A Evolved Airframe',
          controllerLabel: 'Fixed PID Pilot',
        }};
      }}
      if (cid === 'p3a_champ_neat_gen300' || (cid.includes('p3a') && ctype === 'NEAT')) {{
        return {{
          category: 'p3a-neat',
          airframeType: 'P3A',
          color: 0xf59e0b,
          cssColor: '#f59e0b',
          glow: 'rgba(245, 158, 11, 0.45)',
          tagLabel: 'P3A BODY · GEN 300',
          airframeLabel: 'P3A Evolved Airframe',
          controllerLabel: 'Open NEAT Gen 300 Champ',
        }};
      }}
      if (cid.includes('gen300') || cid.includes('p2b')) {{
        return {{
          category: 'gen300-std',
          airframeType: 'STD',
          color: 0x10b981,
          cssColor: '#10b981',
          glow: 'rgba(16, 185, 129, 0.45)',
          tagLabel: 'STD BODY · GEN 300',
          airframeLabel: 'Standard PyFlyt Airframe',
          controllerLabel: 'Open NEAT Gen 300 Champ',
        }};
      }}
      if (ctype === 'PID' || cid.includes('pid')) {{
        return {{
          category: 'pid-std',
          airframeType: 'STD',
          color: 0x00f0ff,
          cssColor: '#00f0ff',
          glow: 'rgba(0, 240, 255, 0.4)',
          tagLabel: 'STD BODY · PID',
          airframeLabel: 'Standard PyFlyt Airframe',
          controllerLabel: 'Reference PID Pilot',
        }};
      }}
      return {{
        category: 'neat-caged',
        airframeType: 'STD',
        color: 0xff0055,
        cssColor: '#ff0055',
        glow: 'rgba(255, 0, 85, 0.4)',
        tagLabel: 'STD BODY · CAGED NEAT',
        airframeLabel: 'Standard PyFlyt Airframe',
        controllerLabel: 'Caged NEAT Pilot',
      }};
    }}

    function initScene() {{
      const container = document.getElementById('canvas-container');
      scene = new THREE.Scene();
      scene.background = new THREE.Color(0x07090e);
      scene.fog = new THREE.FogExp2(0x07090e, 0.0008);

      camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 1, 4000);
      camera.position.set(150, 110, 180);

      renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: false }});
      renderer.setPixelRatio(window.devicePixelRatio);
      renderer.setSize(window.innerWidth, window.innerHeight);
      renderer.shadowMap.enabled = true;
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      container.appendChild(renderer.domElement);

      controls = new THREE.OrbitControls(camera, renderer.domElement);
      controls.enableDamping = true;
      controls.dampingFactor = 0.05;
      controls.maxDistance = 2500;
      controls.target.set(0, 15, -250);

      // Lights
      const ambientLight = new THREE.AmbientLight(0xffffff, 0.55);
      scene.add(ambientLight);

      const dirLight = new THREE.DirectionalLight(0xffffff, 0.85);
      dirLight.position.set(150, 250, 80);
      scene.add(dirLight);

      // Grid Ground
      const grid = new THREE.GridHelper(1800, 90, 0x00f0ff, 0x1e293b);
      grid.position.y = 0;
      scene.add(grid);

      // Ground plane
      const planeGeo = new THREE.PlaneGeometry(2200, 2200);
      const planeMat = new THREE.MeshBasicMaterial({{ color: 0x07090e, depthWrite: false }});
      const groundMesh = new THREE.Mesh(planeGeo, planeMat);
      groundMesh.rotation.x = -Math.PI / 2;
      groundMesh.position.y = -0.1;
      scene.add(groundMesh);

      // 100m Dome wireframe visualization (The Bounded Cage)
      const dome100Geo = new THREE.SphereGeometry(100, 32, 16, 0, Math.PI * 2, 0, Math.PI / 2);
      const dome100Mat = new THREE.MeshBasicMaterial({{
        color: 0xff0055,
        wireframe: true,
        transparent: true,
        opacity: 0.18,
      }});
      dome100Mesh = new THREE.Mesh(dome100Geo, dome100Mat);
      dome100Mesh.position.set(0, 0, 0);
      scene.add(dome100Mesh);

      // 1000m Open Arena wireframe visualization
      const dome1000Geo = new THREE.SphereGeometry(1000, 48, 24, 0, Math.PI * 2, 0, Math.PI / 2);
      const dome1000Mat = new THREE.MeshBasicMaterial({{
        color: 0x00f0ff,
        wireframe: true,
        transparent: true,
        opacity: 0.06,
      }});
      dome1000Mesh = new THREE.Mesh(dome1000Geo, dome1000Mat);
      dome1000Mesh.position.set(0, 0, 0);
      scene.add(dome1000Mesh);

      // Build 3D models for all flights & courses
      buildTrajectories();
      buildWaypoints();
      populateFlightDropdown();

      window.addEventListener('resize', onWindowResize);
      animate();
    }}

    function buildTrajectories() {{
      flightObjects.forEach(fo => {{
        scene.remove(fo.line);
        scene.remove(fo.droneMesh);
      }});
      flightObjects = [];

      BENCHMARK_RUNS.forEach((run) => {{
        const meta = getRunMetadata(run);

        const points = run.trajectory.map(pt => simTo3D(pt.x, pt.y, pt.z));
        if (points.length < 2) return;

        const curve = new THREE.CatmullRomCurve3(points);
        const tubeGeo = new THREE.TubeGeometry(curve, points.length * 2, 0.45, 8, false);
        const tubeMat = new THREE.MeshBasicMaterial({{
          color: meta.color,
          transparent: true,
          opacity: 0.75,
        }});
        const tubeMesh = new THREE.Mesh(tubeGeo, tubeMat);
        scene.add(tubeMesh);

        // Drone marker
        const droneGroup = new THREE.Group();
        const bodyGeo = new THREE.ConeGeometry(1.2, 3.2, 5);
        bodyGeo.rotateX(Math.PI / 2);
        const bodyMat = new THREE.MeshStandardMaterial({{
          color: meta.color,
          emissive: meta.color,
          emissiveIntensity: 0.6,
          metalness: 0.8,
          roughness: 0.2,
        }});
        const bodyMesh = new THREE.Mesh(bodyGeo, bodyMat);
        droneGroup.add(bodyMesh);

        // Wings
        const wingGeo = new THREE.BoxGeometry(4.2, 0.1, 0.9);
        const wingMesh = new THREE.Mesh(wingGeo, bodyMat);
        droneGroup.add(wingMesh);

        // Ground shadow / altitude leader
        const leaderGeo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0,0,0), new THREE.Vector3(0, -10, 0)]);
        const leaderMat = new THREE.LineDashedMaterial({{ color: meta.color, dashSize: 1, gapSize: 1, opacity: 0.4, transparent: true }});
        const leaderLine = new THREE.Line(leaderGeo, leaderMat);
        leaderLine.computeLineDistances();
        droneGroup.add(leaderLine);

        scene.add(droneGroup);

        flightObjects.push({{
          run: run,
          meta: meta,
          points: points,
          trajectory: run.trajectory,
          line: tubeMesh,
          tubeMat: tubeMat,
          droneMesh: droneGroup,
          color: meta.color,
        }});
      }});
    }}

    function buildWaypoints() {{
      waypointObjects.forEach(w => scene.remove(w.mesh));
      waypointObjects = [];

      const courses = [];
      BENCHMARK_RUNS.forEach(r => {{
        if (r.course && r.course.length > 0 && !courses.find(c => c.test === r.test_name)) {{
          courses.push({{ test: r.test_name, course: r.course }});
        }}
      }});

      courses.forEach(c => {{
        c.course.forEach((wp, wIdx) => {{
          const wx = Array.isArray(wp) ? wp[0] : wp.x;
          const wy = Array.isArray(wp) ? wp[1] : wp.y;
          const wz = Array.isArray(wp) ? wp[2] : wp.z;
          const pos3d = simTo3D(wx, wy, wz);

          // Glowing holographic sphere for 2m gate radius
          const sphereGeo = new THREE.SphereGeometry(2.0, 16, 16);
          const sphereMat = new THREE.MeshBasicMaterial({{
            color: 0xfbbf24,
            wireframe: true,
            transparent: true,
            opacity: 0.45,
          }});
          const sphereMesh = new THREE.Mesh(sphereGeo, sphereMat);
          sphereMesh.position.copy(pos3d);
          scene.add(sphereMesh);

          // Central pulsing beacon
          const beaconGeo = new THREE.SphereGeometry(0.5, 8, 8);
          const beaconMat = new THREE.MeshBasicMaterial({{ color: 0xffffff }});
          const beacon = new THREE.Mesh(beaconGeo, beaconMat);
          sphereMesh.add(beacon);

          // Altitude pole to ground
          const poleGeo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, -pos3d.y, 0)]);
          const poleMat = new THREE.LineBasicMaterial({{ color: 0xfbbf24, transparent: true, opacity: 0.25 }});
          const pole = new THREE.Line(poleGeo, poleMat);
          sphereMesh.add(pole);

          waypointObjects.push({{
            test: c.test,
            wpIndex: wIdx + 1,
            mesh: sphereMesh,
            pos: pos3d,
          }});
        }});
      }});
    }}

    function populateFlightDropdown() {{
      const sel = document.getElementById('flight-select');
      if (!sel) return;
      sel.innerHTML = '';

      const optAll = document.createElement('option');
      optAll.value = 'all';
      optAll.textContent = '✈ ALL FLIGHTS (Comparison Fleet)';
      sel.appendChild(optAll);

      const p3cGroup = document.createElement('optgroup');
      p3cGroup.label = '🎯 P3C CO-ADAPTED BODY (1229m NEAT RECORD)';
      const p3bGroup = document.createElement('optgroup');
      p3bGroup.label = '🚀 P3B 1000m OPEN SKY CHAMPION (RECORD SPEED)';
      const p3aGroup = document.createElement('optgroup');
      p3aGroup.label = '⚡ P3A 100m BOUNDED DOME CHAMPION';
      const stdGroup = document.createElement('optgroup');
      stdGroup.label = '✈ STANDARD PYFLYT AIRFRAME';

      BENCHMARK_RUNS.forEach(run => {{
        const meta = getRunMetadata(run);
        const opt = document.createElement('option');
        opt.value = run.id;
        const testShort = run.test_name.split(' - ')[0];
        opt.textContent = `${{testShort}} · ${{meta.tagLabel}} (${{run.distance.toFixed(0)}}m, ${{run.mean_airspeed.toFixed(1)}}m/s)`;
        if (meta.airframeType === 'P3C') {{
          p3cGroup.appendChild(opt);
        }} else if (meta.airframeType === 'P3B') {{
          p3bGroup.appendChild(opt);
        }} else if (meta.airframeType === 'P3A') {{
          p3aGroup.appendChild(opt);
        }} else {{
          stdGroup.appendChild(opt);
        }}
      }});

      sel.appendChild(p3cGroup);
      sel.appendChild(p3bGroup);
      sel.appendChild(p3aGroup);
      sel.appendChild(stdGroup);

      // Default: select P3C NEAT Record flight (1229m @ 49.2m/s) if present
      const p3cRecordRun = BENCHMARK_RUNS.find(r => r.controller_id === 'p3c_champ_neat_gen300' && r.test_name.includes('Test B')) ||
                           BENCHMARK_RUNS.find(r => r.controller_id === 'p3b_champ_pid' && r.test_name.includes('Test B')) ||
                           BENCHMARK_RUNS[0];
      if (p3cRecordRun) {{
        sel.value = p3cRecordRun.id;
        selectFlight(p3cRecordRun.id);
      }}
    }}

    function onFlightSelectChange(val) {{
      if (val === 'all') {{
        deselectFlight();
      }} else {{
        selectFlight(parseInt(val, 10));
      }}
    }}

    function stepFlight(delta) {{
      const visibleRuns = BENCHMARK_RUNS.filter(r => {{
        const fo = flightObjects.find(f => f.run.id === r.id);
        return fo && doesFlightMatchFilters(fo);
      }});
      if (visibleRuns.length === 0) return;

      let currIdx = visibleRuns.findIndex(r => r.id === selectedRunId);
      if (currIdx === -1) {{
        currIdx = (delta > 0) ? 0 : visibleRuns.length - 1;
      }} else {{
        currIdx = (currIdx + delta + visibleRuns.length) % visibleRuns.length;
      }}
      const nextRun = visibleRuns[currIdx];
      const sel = document.getElementById('flight-select');
      if (sel) sel.value = nextRun.id;
      selectFlight(nextRun.id);
    }}

    function doesFlightMatchFilters(fo) {{
      const matchTest = (activeTestFilter === 'all') || fo.run.test_name.includes(activeTestFilter);
      const matchAirframe = (activeAirframeFilter === 'all') || (fo.meta.airframeType === activeAirframeFilter);
      return matchTest && matchAirframe;
    }}

    function applyVisualStates() {{
      flightObjects.forEach(fo => {{
        const passesFilter = doesFlightMatchFilters(fo);
        const isSelected = (fo.run.id === selectedRunId);

        if (!passesFilter) {{
          fo.line.visible = false;
          fo.droneMesh.visible = false;
          return;
        }}

        if (selectedRunId !== null) {{
          if (isSelected) {{
            fo.line.visible = showFullTrails;
            fo.line.material.opacity = 1.0;
            fo.line.material.depthWrite = true;
            fo.droneMesh.visible = true;
            fo.droneMesh.scale.set(1.5, 1.5, 1.5);
          }} else {{
            if (isolateMode) {{
              fo.line.visible = false;
              fo.droneMesh.visible = false;
            }} else {{
              fo.line.visible = showFullTrails;
              fo.line.material.opacity = 0.08;
              fo.line.material.depthWrite = false;
              fo.droneMesh.visible = false;
              fo.droneMesh.scale.set(0.7, 0.7, 0.7);
            }}
          }}
        }} else {{
          fo.line.visible = showFullTrails;
          fo.line.material.opacity = 0.75;
          fo.line.material.depthWrite = true;
          fo.droneMesh.visible = true;
          fo.droneMesh.scale.set(1.0, 1.0, 1.0);
        }}
      }});

      // Waypoint gate filtering
      waypointObjects.forEach(wo => {{
        if (selectedRunId !== null) {{
          const selFo = flightObjects.find(f => f.run.id === selectedRunId);
          if (selFo) {{
            const testPrefix = selFo.run.test_name.split(' - ')[0];
            wo.mesh.visible = wo.test.includes(testPrefix);
            return;
          }}
        }}
        const matchTest = (activeTestFilter === 'all') || wo.test.includes(activeTestFilter);
        wo.mesh.visible = matchTest;
      }});
    }}

    function selectFlight(runId) {{
      selectedRunId = runId;
      const sel = document.getElementById('flight-select');
      if (sel && sel.value != runId) {{
        sel.value = runId;
      }}

      // Update HUD
      const fo = flightObjects.find(f => f.run.id === runId);
      if (fo) {{
        const run = fo.run;
        const meta = fo.meta;
        const banner = document.getElementById('selection-banner');
        banner.style.borderColor = meta.cssColor;
        banner.style.background = meta.glow;
        document.getElementById('selection-status-text').innerHTML = `Active: <b>${{run.test_name.split(' - ')[0]}} (${{meta.tagLabel}})</b>`;

        document.getElementById('hud-track').textContent = `${{run.test_name.split(' - ')[0]}}`;
        document.getElementById('hud-track').style.color = meta.cssColor;
        document.getElementById('hud-ctrl').textContent = meta.controllerLabel;
        document.getElementById('hud-airframe').textContent = meta.airframeLabel;
        document.getElementById('hud-wp').textContent = `${{run.waypoints_hit}} / 4`;
        document.getElementById('hud-wp').style.color = run.waypoints_hit > 0 ? '#fbbf24' : 'var(--text-dim)';

        // Status badge
        const statusEl = document.getElementById('hud-status');
        if (run.crashed) {{
          statusEl.textContent = 'CRASHED';
          statusEl.style.color = '#ef4444';
        }} else if (run.stalling) {{
          statusEl.textContent = 'STALLED';
          statusEl.style.color = '#f59e0b';
        }} else {{
          statusEl.textContent = `SURVIVED (${{run.flight_time.toFixed(1)}}s)`;
          statusEl.style.color = '#10b981';
        }}

        // Lateral deviation & energy
        document.getElementById('hud-latdev').textContent = `${{run.max_lateral_dev.toFixed(1)}} m`;
        document.getElementById('hud-energy').textContent = `${{run.control_energy.toFixed(2)}}`;

        // Distance (total)
        document.getElementById('hud-dist').textContent = `${{run.distance.toFixed(1)}} m`;

        focusFlightTrajectory(fo);
      }}

      applyVisualStates();
    }}

    function deselectFlight() {{
      selectedRunId = null;
      const sel = document.getElementById('flight-select');
      if (sel) sel.value = 'all';

      const banner = document.getElementById('selection-banner');
      banner.style.borderColor = 'rgba(0, 240, 255, 0.25)';
      banner.style.background = 'rgba(0, 240, 255, 0.08)';
      document.getElementById('selection-status-text').textContent = 'Comparing All Visible Flights';
      document.getElementById('hud-track').textContent = 'Multi-Flight Fleet';
      document.getElementById('hud-track').style.color = 'var(--cyan)';
      document.getElementById('hud-ctrl').textContent = 'PID / NEAT (Mixed)';
      document.getElementById('hud-airframe').textContent = 'P3A / P3B / P3C / Standard';
      document.getElementById('hud-status').textContent = `${{BENCHMARK_RUNS.length}} flights loaded`;
      document.getElementById('hud-status').style.color = 'var(--text-dim)';
      document.getElementById('hud-wp').textContent = '— / 4';
      document.getElementById('hud-wp').style.color = 'var(--text-dim)';
      document.getElementById('hud-latdev').textContent = '—';
      document.getElementById('hud-energy').textContent = '—';

      applyVisualStates();
    }}

    function focusFlightTrajectory(fo) {{
      if (!fo || !fo.points || fo.points.length === 0) return;

      let sumX = 0, sumY = 0, sumZ = 0;
      fo.points.forEach(p => {{
        sumX += p.x;
        sumY += p.y;
        sumZ += p.z;
      }});
      const midX = sumX / fo.points.length;
      const midY = sumY / fo.points.length;
      const midZ = sumZ / fo.points.length;

      controls.target.set(midX, Math.max(8, midY), midZ);
      controls.update();
    }}

    function focusSelectedFlight() {{
      if (selectedRunId !== null) {{
        const fo = flightObjects.find(f => f.run.id === selectedRunId);
        if (fo) focusFlightTrajectory(fo);
      }} else {{
        controls.target.set(0, 15, -250);
        controls.update();
      }}
    }}

    function setTestFilter(mode) {{
      activeTestFilter = mode;
      document.querySelectorAll('.view-filters .pill-btn').forEach(b => {{
        if (['all', 'Test A', 'Test B', 'Test C'].includes(b.textContent.trim()) || b.textContent.includes(mode)) {{
          b.classList.toggle('active', b.textContent.includes(mode) || (mode === 'all' && b.textContent === 'All Tests'));
        }}
      }});
      applyVisualStates();
    }}

    function setAirframeFilter(af) {{
      activeAirframeFilter = af;
      document.querySelectorAll('.view-filters .pill-btn').forEach(b => {{
        if (af === 'all' && b.textContent.includes('All Bodies')) b.classList.add('active');
        else if (af === 'P3C' && b.textContent.includes('P3C Body')) b.classList.add('active');
        else if (af === 'P3B' && b.textContent.includes('P3B Body')) b.classList.add('active');
        else if (af === 'P3A' && b.textContent.includes('P3A Body')) b.classList.add('active');
        else if (af === 'STD' && b.textContent.includes('Std Body')) b.classList.add('active');
        else if (b.textContent.includes('Body') || b.textContent.includes('Bodies')) b.classList.remove('active');
      }});
      applyVisualStates();
    }}

    function toggleIsolateMode() {{
      isolateMode = !isolateMode;
      const btn = document.getElementById('btn-isolate-mode');
      btn.classList.toggle('active', isolateMode);
      btn.textContent = isolateMode ? '⚡ Solo Active' : '⚡ Solo';
      applyVisualStates();
    }}

    function setCameraView(preset) {{
      if (preset === 'top') {{
        camera.position.set(0, 450, -250);
        controls.target.set(0, 0, -250);
      }} else if (preset === 'side') {{
        camera.position.set(400, 30, -250);
        controls.target.set(0, 15, -250);
      }} else if (preset === 'iso') {{
        camera.position.set(150, 110, 180);
        controls.target.set(0, 15, -250);
      }}
      controls.update();
    }}

    function togglePlay() {{
      isPlaying = !isPlaying;
      document.getElementById('play-btn').innerHTML = isPlaying ? '<span>⏸</span> PAUSE' : '<span>▶</span> PLAY';
    }}

    function resetPlayback() {{
      currentTime = 0.0;
      document.getElementById('scrubber').value = 0;
      updateSimulationTime(0);
    }}

    function cycleSpeed() {{
      speedIdx = (speedIdx + 1) % SPEED_STEPS.length;
      playbackSpeed = SPEED_STEPS[speedIdx];
      document.getElementById('speed-val').textContent = playbackSpeed + 'x';
    }}

    function onScrub(val) {{
      currentTime = parseFloat(val);
      updateSimulationTime(currentTime);
    }}

    function toggleDome() {{
      showDome = !showDome;
      if (dome100Mesh) dome100Mesh.visible = showDome;
      if (dome1000Mesh) dome1000Mesh.visible = showDome;
      document.getElementById('dome-btn-text').textContent = showDome ? '🌐 HIDE DOMES' : '🌐 SHOW DOMES';
    }}

    function toggleTrails() {{
      showFullTrails = !showFullTrails;
      applyVisualStates();
    }}

    function updateSimulationTime(time) {{
      document.getElementById('scrub-time').textContent = `${{time.toFixed(2)}} s / ${{maxFlightDuration.toFixed(2)}} s`;

      flightObjects.forEach(fo => {{
        const traj = fo.trajectory;
        if (!traj || traj.length === 0) return;

        let prev = traj[0];
        let next = traj[traj.length - 1];
        let found = false;

        for (let i = 0; i < traj.length - 1; i++) {{
          if (time >= traj[i].time && time <= traj[i + 1].time) {{
            prev = traj[i];
            next = traj[i + 1];
            found = true;
            break;
          }}
        }}

        if (!found && time >= traj[traj.length - 1].time) {{
          prev = traj[traj.length - 1];
          next = traj[traj.length - 1];
        }}

        const span = (next.time - prev.time) || 0.001;
        const alpha = Math.min(1.0, Math.max(0.0, (time - prev.time) / span));

        const curX = prev.x + (next.x - prev.x) * alpha;
        const curY = prev.y + (next.y - prev.y) * alpha;
        const curZ = prev.z + (next.z - prev.z) * alpha;
        const curSpd = prev.airspeed + (next.airspeed - prev.airspeed) * alpha;

        const pos3d = simTo3D(curX, curY, curZ);
        fo.droneMesh.position.copy(pos3d);

        const nextPos3d = simTo3D(next.x, next.y, next.z);
        if (pos3d.distanceTo(nextPos3d) > 0.1) {{
          fo.droneMesh.lookAt(nextPos3d);
        }}

        const isFocus = (selectedRunId !== null && fo.run.id === selectedRunId) ||
                        (selectedRunId === null && fo.line.visible && fo === flightObjects[0]);

        if (isFocus) {{
          document.getElementById('hud-time').textContent = `${{Math.min(time, fo.run.flight_time).toFixed(2)}} s`;
          document.getElementById('hud-dist').textContent = `${{(curX > 0 ? curX : 0).toFixed(1)}} m`;
          document.getElementById('hud-speed').textContent = `${{curSpd.toFixed(1)}} m/s (${{(curSpd * 3.6).toFixed(0)}} km/h)`;
          document.getElementById('hud-alt').textContent = `${{curZ.toFixed(1)}} m AGL`;
          document.getElementById('hud-coords').textContent = `(${{curX.toFixed(1)}}, ${{curY.toFixed(1)}}, ${{curZ.toFixed(1)}})`;
        }}

        if (time > fo.run.flight_time) {{
          fo.droneMesh.visible = false;
        }} else if (fo.line.visible) {{
          if (selectedRunId !== null && fo.run.id !== selectedRunId && isolateMode) {{
            fo.droneMesh.visible = false;
          }} else {{
            fo.droneMesh.visible = true;
          }}
        }}
      }});
    }}

    let lastClock = performance.now();
    function animate() {{
      requestAnimationFrame(animate);

      const now = performance.now();
      const dt = (now - lastClock) / 1000.0;
      lastClock = now;

      if (isPlaying) {{
        currentTime += dt * playbackSpeed;
        if (currentTime > maxFlightDuration) {{
          currentTime = 0.0;
        }}
        document.getElementById('scrubber').value = currentTime;
        updateSimulationTime(currentTime);
      }}

      waypointObjects.forEach(w => {{
        w.mesh.rotation.y += 0.012;
      }});

      controls.update();
      renderer.render(scene, camera);
    }}

    function onWindowResize() {{
      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
    }}

    window.onload = initScene;
  </script>
</body>
</html>
"""
    return html


def generate_viewer(
    db_path: str = "output/icarus.db",
    output_html: str = "output/benchmark_3d_viewer.html",
) -> str:
    runs = fetch_benchmark_data(db_path)
    content = build_3d_html(runs)
    os.makedirs(os.path.dirname(output_html), exist_ok=True)
    with open(output_html, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[talos] 3D Benchmark Arena Viewer generated ({len(runs)} flights) at: {output_html}")
    return content


if __name__ == "__main__":
    generate_viewer()
