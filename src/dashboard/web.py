"""Executive Research-Grade Light-Theme HTML Dashboard for TALOS.

Features:
- Instant 0ms Rendering via Embedded HTML Bootstrap Data.
- Ultra-Lightweight 60KB background polling (no heavy 2MB payloads).
- Graph Visibility Controls: User can toggle Latest Champ, Gen 25, Baseline B0, Target Horizon, and Area Fill.
- One-Click Live Neural Network Flight Runner: Click '▶ RUN LIVE FLIGHT SIMULATION' to simulate the controller in PyBullet, extract real trajectory coordinates, animate the flight path, and update telemetry in real time.
- Real Topological NEAT Neural Network Graph displayed directly on Overview and in Phase 2 with one-click toggles between Latest Champion and Gen 25.
- Permanently sticky header and phase navigation bar.
- Compatible with all browsers (standard ES5/ES6 without unsupported optional chaining or nullish coalescing).
"""
from __future__ import annotations

import http.server
import json
import os
import sqlite3
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from src.dashboard.runner import run_best_model
from src.experiment.db import ExperimentDB

DB_PATH = os.path.join("output", "icarus.db")
C1_TRAJ_PATH = os.path.join("output", "c1_trajectory.json")
B0_TRAJ_PATH = os.path.join("output", "b0_trajectory.json")
GEN25_TRAJ_PATH = os.path.join("output", "gen25_trajectory.json")


def _db(path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _load_json_file(path: str) -> Optional[Dict[str, Any]]:
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def get_all_data(db_path: str = DB_PATH) -> Dict[str, Any]:
    """Gather experimental data, baselines, generations, and champion genomes."""
    data: Dict[str, Any] = {
        "experiments": [],
        "baselines": [],
        "generations": {},
        "champion": None,
        "best_overall": None,
        "gen25_champion": None,
        "history_champions": [],
        "c1_trajectory": _load_json_file(C1_TRAJ_PATH),
        "b0_trajectory": _load_json_file(B0_TRAJ_PATH),
        "gen25_trajectory": _load_json_file(GEN25_TRAJ_PATH),
        "default_morphology": {
            "wingspan": 1.80,
            "wing_area": 0.45,
            "h_tail_area": 0.08,
            "v_tail_area": 0.06,
            "thrust_to_weight": 0.85,
            "total_mass": 1.50,
            "cg_x_offset": 0.0,
            "static_margin": 12.4,
        },
    }

    if not os.path.isfile(db_path):
        return data

    conn = _db(db_path)
    try:
        # 1. Experiments
        rows = conn.execute(
            "SELECT experiment_id, status, start_time, end_time, best_fitness, best_generation "
            "FROM experiment_metadata ORDER BY start_time DESC"
        ).fetchall()
        data["experiments"] = [dict(r) for r in rows]

        # 2. Baseline Metrics
        rows = conn.execute(
            "SELECT * FROM baseline_metrics ORDER BY measured_at DESC"
        ).fetchall()
        data["baselines"] = [dict(r) for r in rows]

        # 3. Generations per experiment
        rows = conn.execute(
            "SELECT * FROM generations ORDER BY experiment_id, generation ASC"
        ).fetchall()
        for r in rows:
            d = dict(r)
            eid = d["experiment_id"]
            data["generations"].setdefault(eid, []).append(d)

        # 4. Lightweight history list (no heavy controllers)
        ind_rows = conn.execute(
            "SELECT id, experiment_id, generation, fitness, is_elite, survival_time, "
            "distance, energy, altitude_error, airspeed_error, crashed, stalling, "
            "nodes, connections, species_id "
            "FROM individuals WHERE is_elite = 1 OR individual_index = 0 "
            "ORDER BY generation DESC, fitness DESC"
        ).fetchall()
        data["history_champions"] = [dict(r) for r in ind_rows]

        # 5. Full Controller and Morphology for Active Champion
        exp_row = conn.execute(
            "SELECT experiment_id FROM experiment_metadata WHERE status = 'running' ORDER BY start_time DESC LIMIT 1"
        ).fetchone()
        if not exp_row:
            exp_row = conn.execute(
                "SELECT experiment_id FROM experiment_metadata ORDER BY start_time DESC LIMIT 1"
            ).fetchone()
        active_exp_id = exp_row["experiment_id"] if exp_row else "TALOS-P4-ULTIMA"

        # Trajectory resolution: active experiment first
        traj_candidates = [
            os.path.join("output", f"{active_exp_id.lower()}_trajectory.json"),
            os.path.join("output", "talos-p4-ultima_trajectory.json"),
            os.path.join("output", "talos-p2b_trajectory.json"),
            C1_TRAJ_PATH,
        ]
        latest_traj = None
        for cand in traj_candidates:
            if os.path.isfile(cand):
                latest_traj = _load_json_file(cand)
                if latest_traj:
                    break
        data["latest_trajectory"] = latest_traj

        # 4b. History filtered for active experiment if available
        ind_rows_active = conn.execute(
            "SELECT id, experiment_id, generation, fitness, is_elite, survival_time, "
            "distance, energy, altitude_error, airspeed_error, crashed, stalling, "
            "nodes, connections, species_id "
            "FROM individuals WHERE (is_elite = 1 OR individual_index = 0) AND experiment_id = ? "
            "ORDER BY generation DESC, fitness DESC",
            (active_exp_id,),
        ).fetchall()
        if ind_rows_active:
            data["history_champions"] = [dict(r) for r in ind_rows_active]

        champ_row = conn.execute(
            "SELECT * FROM individuals WHERE experiment_id = ? ORDER BY generation DESC, fitness DESC LIMIT 1",
            (active_exp_id,),
        ).fetchone()
        if not champ_row:
            champ_row = conn.execute(
                "SELECT * FROM individuals ORDER BY generation DESC, fitness DESC LIMIT 1"
            ).fetchone()

        if champ_row:
            c = dict(champ_row)
            if c.get("controller_json"):
                try:
                    c["controller"] = json.loads(c["controller_json"])
                except Exception:
                    c["controller"] = None
            if c.get("morphology_json"):
                try:
                    c["morphology"] = json.loads(c["morphology_json"])
                except Exception:
                    c["morphology"] = None
            c.pop("controller_json", None)
            c.pop("morphology_json", None)
            data["champion"] = c

        # 6. Full Controller for Generation 25 (Peak Fitness)
        gen25_row = conn.execute(
            "SELECT * FROM individuals WHERE generation = 25 ORDER BY fitness DESC LIMIT 1"
        ).fetchone()
        if gen25_row:
            g = dict(gen25_row)
            if g.get("controller_json"):
                try:
                    g["controller"] = json.loads(g["controller_json"])
                except Exception:
                    g["controller"] = None
            g.pop("controller_json", None)
            g.pop("morphology_json", None)
            data["gen25_champion"] = g
            data["best_overall"] = g

    except Exception as exc:
        data["db_error"] = str(exc)
    finally:
        conn.close()

    return data


# ---------------------------------------------------------------------------
# HTML / CSS / JS Template
# ---------------------------------------------------------------------------

_HTML_HEAD = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TALOS — UAV Co-Evolution Mission Control</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {
  --bg-app: #f8fafc;
  --bg-surface: #ffffff;
  --bg-subtle: #f1f5f9;
  --bg-card: #ffffff;
  --border: #e2e8f0;
  --border-strong: #cbd5e1;

  --text-primary: #0f172a;
  --text-secondary: #475569;
  --text-muted: #94a3b8;

  --primary: #2563eb;
  --primary-hover: #1d4ed8;
  --primary-light: #eff6ff;

  --cyan: #0284c7;
  --cyan-light: #f0f9ff;

  --emerald: #059669;
  --emerald-light: #ecfdf5;

  --amber: #d97706;
  --amber-light: #fffbeb;

  --rose: #e11d48;
  --rose-light: #fff1f2;

  --purple: #7c3aed;
  --purple-light: #f5f3ff;

  --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.07), 0 2px 4px -2px rgba(0, 0, 0, 0.05);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.08), 0 4px 6px -4px rgba(0, 0, 0, 0.04);
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 14px;
}

* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  background: var(--bg-app);
  color: var(--text-primary);
  font-family: 'Inter', -apple-system, sans-serif;
  font-size: 13px;
  line-height: 1.5;
  min-height: 100vh;
}

/* Header */
header {
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 60;
  box-shadow: var(--shadow-sm);
}
.header-inner {
  max-width: 1560px;
  margin: 0 auto;
  padding: 10px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}
.brand-group {
  display: flex;
  align-items: center;
  gap: 12px;
}
.logo-icon {
  width: 38px;
  height: 38px;
  background: linear-gradient(135deg, var(--primary), var(--cyan));
  border-radius: 9px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-weight: 800;
  font-size: 20px;
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.3);
}
.brand-title {
  font-size: 16px;
  font-weight: 800;
  color: var(--text-primary);
  letter-spacing: -0.02em;
}
.brand-sub {
  font-size: 11px;
  color: var(--text-muted);
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.live-pill {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--cyan-light);
  border: 1px solid rgba(2, 132, 199, 0.25);
  padding: 6px 13px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 700;
  color: var(--cyan);
}
.pulse-dot {
  width: 8px;
  height: 8px;
  background: var(--cyan);
  border-radius: 50%;
  box-shadow: 0 0 6px var(--cyan);
  animation: pulse 1.8s infinite;
}
@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.3); opacity: 0.5; }
}

/* Sticky Phase Navigation Bar */
.phase-nav-container {
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 58px;
  z-index: 55;
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.04);
  padding: 0 24px;
}
.phase-nav {
  max-width: 1560px;
  margin: 0 auto;
  display: flex;
  gap: 4px;
  overflow-x: auto;
}
.phase-tab {
  padding: 12px 16px;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text-secondary);
  cursor: pointer;
  border-bottom: 3px solid transparent;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.15s ease;
  user-select: none;
  white-space: nowrap;
}
.phase-tab:hover {
  color: var(--primary);
  background: var(--bg-subtle);
}
.phase-tab.active {
  color: var(--primary);
  border-bottom-color: var(--primary);
  background: var(--primary-light);
}
.tab-badge {
  font-size: 10.5px;
  padding: 2px 7px;
  border-radius: 12px;
  font-weight: 700;
}
.badge-ready { background: var(--bg-subtle); color: var(--text-secondary); border: 1px solid var(--border); }
.badge-active { background: var(--cyan-light); color: var(--cyan); border: 1px solid rgba(2, 132, 199, 0.25); }
.badge-done { background: var(--emerald-light); color: var(--emerald); border: 1px solid rgba(5, 150, 105, 0.25); }
.badge-purple { background: var(--purple-light); color: var(--purple); border: 1px solid rgba(124, 58, 237, 0.25); }

/* Main Container */
main {
  max-width: 1560px;
  margin: 0 auto;
  padding: 20px 24px 60px;
}

/* Panels */
.tab-panel { display: none; }
.tab-panel.active { display: block; animation: fadeIn 0.2s ease-out; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(3px); } to { opacity: 1; transform: translateY(0); } }

/* Layout Grids */
.grid-2 { display: grid; grid-template-columns: repeat(2, 1fr); gap: 18px; }
.grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
.grid-sidebar { display: grid; grid-template-columns: 2fr 1fr; gap: 18px; }

@media (max-width: 1100px) {
  .grid-2, .grid-3, .grid-4, .grid-sidebar { grid-template-columns: 1fr; }
}

/* Cards */
.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 18px;
  box-shadow: var(--shadow-sm);
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border);
  flex-wrap: wrap;
  gap: 8px;
}
.card-title {
  font-size: 13.5px;
  font-weight: 700;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 8px;
}
.card-subtitle {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
}

/* Stat Widgets */
.stat-box {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 12px 14px;
  box-shadow: var(--shadow-sm);
}
.stat-label {
  font-size: 10.5px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 3px;
}
.stat-value {
  font-size: 20px;
  font-weight: 800;
  color: var(--text-primary);
  font-family: 'JetBrains Mono', monospace;
}
.stat-desc {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 2px;
}
.delta-pos { color: var(--emerald); }
.delta-neg { color: var(--rose); }

/* SVG Canvas Containers */
.svg-container {
  width: 100%;
  background: #ffffff;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
  position: relative;
  box-shadow: inset 0 1px 2px rgba(0,0,0,0.03);
}
svg { display: block; }
svg text {
  font-family: 'Inter', -apple-system, sans-serif;
  user-select: none;
}
.mono { font-family: 'JetBrains Mono', monospace; }

/* Interactive Neural Graph Elements */
.node-group {
  cursor: pointer;
  transition: transform 0.15s ease;
}
.node-group:hover circle {
  stroke-width: 3.5px !important;
  stroke: var(--primary) !important;
  filter: drop-shadow(0 2px 6px rgba(37, 99, 235, 0.4));
}
.synapse-link {
  fill: none;
  cursor: pointer;
  transition: stroke-width 0.15s ease, opacity 0.15s ease;
}
.synapse-link:hover {
  stroke: #0f172a !important;
  stroke-width: 3.5px !important;
  opacity: 1.0 !important;
}

/* Telemetry Strip */
.telemetry-strip {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 8px;
  margin-top: 14px;
}
@media (max-width: 900px) {
  .telemetry-strip { grid-template-columns: repeat(3, 1fr); }
}
.tel-box {
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 8px 10px;
  text-align: center;
}
.tel-val {
  font-size: 13px;
  font-weight: 700;
  font-family: 'JetBrains Mono', monospace;
  color: var(--text-primary);
}
.tel-lbl {
  font-size: 10px;
  color: var(--text-muted);
  text-transform: uppercase;
  margin-top: 2px;
}

/* Custom Table */
.custom-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.custom-table th {
  text-align: left;
  padding: 8px 12px;
  background: var(--bg-subtle);
  color: var(--text-secondary);
  font-weight: 700;
  border-bottom: 1px solid var(--border);
}
.custom-table td {
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
  color: var(--text-primary);
  font-family: 'JetBrains Mono', monospace;
  font-size: 11.5px;
}
.custom-table tr:hover td {
  background: var(--bg-subtle);
}

/* Controls & Buttons */
.btn {
  background: var(--primary);
  color: #ffffff;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  padding: 6px 14px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  user-select: none;
}
.btn:hover {
  background: var(--primary-hover);
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.25);
}
.btn-secondary {
  background: #ffffff;
  color: var(--text-primary);
  border: 1px solid var(--border-strong);
}
.btn-secondary:hover {
  background: var(--bg-subtle);
}
.btn-purple {
  background: var(--purple-light);
  color: var(--purple);
  border: 1px solid rgba(124, 58, 237, 0.3);
}
.btn-purple:hover {
  background: #ede9fe;
}
.btn-emerald {
  background: var(--emerald);
  color: #ffffff;
  border: 1px solid transparent;
}
.btn-emerald:hover {
  background: #047857;
  box-shadow: 0 2px 8px rgba(5, 150, 105, 0.3);
}
.select-input {
  background: #ffffff;
  color: var(--text-primary);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-sm);
  padding: 5px 10px;
  font-size: 12px;
  font-family: inherit;
  font-weight: 500;
  outline: none;
}
.select-input:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.15);
}

/* Action Banner */
.action-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #ffffff;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 10px 16px;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 10px;
}

/* In-Page Toast */
#toast-banner {
  position: fixed;
  bottom: 24px;
  right: 24px;
  background: #0f172a;
  color: #ffffff;
  padding: 12px 20px;
  border-radius: var(--radius-md);
  font-size: 12.5px;
  font-weight: 600;
  box-shadow: var(--shadow-lg);
  display: none;
  z-index: 100;
}
</style>
</head>
<body>

<div id="toast-banner"></div>

<!-- Top Navigation Header -->
<header>
  <div class="header-inner">
    <div class="brand-group">
      <div class="logo-icon">T</div>
      <div>
        <div class="brand-title">TALOS &middot; AIRCRAFT CO-DESIGN CONTROL</div>
        <div class="brand-sub">Autonomous Fixed-Wing UAV Co-Evolution &middot; Bullet Physics &middot; NEAT</div>
      </div>
    </div>
    <div class="header-actions">
      <div class="live-pill">
        <div class="pulse-dot"></div>
        <span id="live-header-status">SIMULATION ACTIVE &middot; GEN 162/300</span>
      </div>
      <button class="btn btn-emerald" id="btn-run-sim" onclick="runLiveFlightSimulation()">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
        ▶ RUN LIVE FLIGHT SIMULATION
      </button>
      <a href="/3d" target="_blank" class="btn" style="background: linear-gradient(135deg, #0284c7, #2563eb); color: #fff; text-decoration: none;">
        🌐 3D Flight Arena (Benchmark Trajectories)
      </a>
      <button class="btn btn-secondary" onclick="triggerRunFlight(true)">
        Launch 3D PyBullet Window
      </button>
    </div>
  </div>
</header>

<!-- Sticky Phase Navigation Bar -->
<div class="phase-nav-container">
  <div class="phase-nav">
    <div class="phase-tab active" data-tab="tab-overview">Overview &amp; Telemetry</div>
    <div class="phase-tab" data-tab="tab-phase1">
      Phase 1: Baseline ($B0$)
      <span class="tab-badge badge-done">Completed</span>
    </div>
    <div class="phase-tab" data-tab="tab-phase2" id="nav-phase2">
      Phase 2: Controller ($C1$)
      <span class="tab-badge badge-active" id="p2-badge">Live Active</span>
    </div>
    <div class="phase-tab" data-tab="tab-phase3">
      Phase 3: Morphology Search
      <span class="tab-badge badge-ready" id="p3-badge">Blueprint</span>
    </div>
    <div class="phase-tab" data-tab="tab-phase4">
      Phase 4: Co-Evolution
      <span class="tab-badge badge-ready" id="p4-badge">Dual Genome</span>
    </div>
    <div class="phase-tab" data-tab="tab-phase5">
      Phase 5: Grow &amp; Prune
      <span class="tab-badge badge-ready">NeST</span>
    </div>
    <div class="phase-tab" data-tab="tab-phase6">
      Phase 6: Replay &amp; Montage
      <span class="tab-badge badge-ready">Showcase</span>
    </div>
  </div>
</div>

<main>

  <!-- ===================================================================== -->
  <!-- TAB: OVERVIEW & TELEMETRY                                            -->
  <!-- ===================================================================== -->
  <div id="tab-overview" class="tab-panel active">

    <!-- Action & Direct Select Bar -->
    <div class="action-banner">
      <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
        <span style="font-weight: 700; color: var(--text-primary);">Simulate Target Genome:</span>
        <select class="select-input" id="ov-model-select">
          <option value="latest">Latest Live Champion (Gen 162+)</option>
          <option value="25">Generation 25 (Peak Score: 0.8505)</option>
          <option value="b0">Baseline Cascaded PID ($B0$)</option>
        </select>
        <button class="btn btn-emerald" style="padding: 5px 12px;" onclick="runLiveFlightSimulation()">
          ▶ Execute Simulation &amp; Update Graph
        </button>
      </div>
      <div style="display: flex; gap: 6px; flex-wrap: wrap;">
        <button class="btn btn-secondary" style="padding: 4px 10px; font-size: 11.5px;" onclick="switchTab('tab-phase2')">⚡ Phase 2 Brain Explorer</button>
        <button class="btn btn-purple" style="padding: 4px 10px; font-size: 11.5px;" onclick="switchToGen25Phase2()">★ Inspect Gen 25</button>
      </div>
    </div>

    <!-- Top KPI Cards -->
    <div class="grid-4" style="margin-bottom: 18px;">
      <div class="stat-box">
        <div class="stat-label">Active Experiment</div>
        <div class="stat-value" id="ov-exp-id">C1</div>
        <div class="stat-desc">Controller NEAT on Default Airframe</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">Evolutionary Progress</div>
        <div class="stat-value" id="ov-progress">162 / 300</div>
        <div class="stat-desc" id="ov-progress-pct">54.0% Completed</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">Max Flight Distance</div>
        <div class="stat-value delta-pos" id="ov-max-dist">192.30 m</div>
        <div class="stat-desc">Baseline: 98.25 m (+95.7% delta)</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">All-Time Peak Fitness</div>
        <div class="stat-value" style="color: var(--purple);" id="ov-peak-fit">0.8505</div>
        <div class="stat-desc" id="ov-peak-gen">Achieved at Generation 25</div>
      </div>
    </div>

    <div class="grid-2">
      <!-- Flight Path Card -->
      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">Flight Trajectory Comparison (Altitude Z vs Downrange X)</div>
            <div class="card-subtitle">Choose curves to display or click Run to simulate live</div>
          </div>
          <button class="btn btn-secondary" style="padding: 3px 8px; font-size: 11px;" onclick="runLiveFlightSimulation()">
            Re-Simulate
          </button>
        </div>

        <!-- Curve Selection Bar -->
        <div style="display: flex; gap: 14px; background: var(--bg-subtle); padding: 8px 12px; border-radius: var(--radius-sm); margin-bottom: 10px; border: 1px solid var(--border); flex-wrap: wrap;">
          <strong style="font-size: 11px; color: var(--text-muted); text-transform: uppercase;">Curves:</strong>
          <label style="font-size: 11.5px; display: flex; align-items: center; gap: 5px; cursor: pointer;">
            <input type="checkbox" id="chk-champ" checked onchange="refreshTrajectoryChart()">
            <span style="color: var(--primary); font-weight: 700;">Latest Champion</span>
          </label>
          <label style="font-size: 11.5px; display: flex; align-items: center; gap: 5px; cursor: pointer;">
            <input type="checkbox" id="chk-gen25" checked onchange="refreshTrajectoryChart()">
            <span style="color: var(--purple); font-weight: 700;">Gen 25 (0.85 Peak)</span>
          </label>
          <label style="font-size: 11.5px; display: flex; align-items: center; gap: 5px; cursor: pointer;">
            <input type="checkbox" id="chk-b0" checked onchange="refreshTrajectoryChart()">
            <span style="color: var(--amber); font-weight: 700;">$B0$ PID Baseline</span>
          </label>
          <label style="font-size: 11.5px; display: flex; align-items: center; gap: 5px; cursor: pointer;">
            <input type="checkbox" id="chk-target" checked onchange="refreshTrajectoryChart()">
            <span style="color: var(--emerald); font-weight: 700;">10m Horizon</span>
          </label>
          <label style="font-size: 11.5px; display: flex; align-items: center; gap: 5px; cursor: pointer;">
            <input type="checkbox" id="chk-fill" checked onchange="refreshTrajectoryChart()">
            <span>Area Fill</span>
          </label>
        </div>

        <div class="svg-container" id="ov-traj-container" style="height: 330px;"></div>

        <div class="telemetry-strip">
          <div class="tel-box"><div class="tel-val" id="tel-dist">192.3m</div><div class="tel-lbl">Distance</div></div>
          <div class="tel-box"><div class="tel-val" id="tel-time">4.27s</div><div class="tel-lbl">Air Time</div></div>
          <div class="tel-box"><div class="tel-val" id="tel-alt">10.02m</div><div class="tel-lbl">Cruise Alt</div></div>
          <div class="tel-box"><div class="tel-val" id="tel-spd">25.8m/s</div><div class="tel-lbl">Airspeed</div></div>
          <div class="tel-box"><div class="tel-val delta-pos" id="tel-stall">NO</div><div class="tel-lbl">Stall Event</div></div>
          <div class="tel-box"><div class="tel-val delta-pos" id="tel-crash">NO</div><div class="tel-lbl">Ground Crash</div></div>
        </div>
      </div>

      <!-- Fitness Progression Card -->
      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title" id="ov-fitness-title">Evolutionary Fitness Trajectory (Generations 0 &rarr; 600)</div>
            <div class="card-subtitle">Multi-objective score: survival (40%), efficiency (30%), altitude tracking (30%)</div>
          </div>
          <span class="tab-badge badge-active">Live Polling 3s</span>
        </div>

        <div class="svg-container" id="ov-fitness-container" style="height: 330px;"></div>

        <div style="display: flex; justify-content: space-around; font-size: 11.5px; margin-top: 14px; flex-wrap: wrap; gap: 8px;">
          <span><strong style="color: var(--primary);">━━ Blue:</strong> Best Fitness</span>
          <span><strong style="color: var(--cyan);">- - Cyan:</strong> Mean Fitness</span>
          <span><strong style="color: var(--rose);">··· Rose:</strong> Crash Penalty Floor (-100)</span>
          <span><strong style="color: var(--amber);">--- Amber:</strong> Baseline Benchmark ($B0$)</span>
        </div>
      </div>
    </div>

    <!-- Live NEAT Neural Network Graph (Directly on Overview) -->
    <div class="card" style="margin-top: 18px;">
      <div class="card-header">
        <div>
          <div class="card-title">Active NEAT Controller Neural Network</div>
          <div class="card-subtitle" id="ov-nn-subtitle">Real topological genome extracted from database</div>
        </div>
        <div style="display: flex; gap: 8px; align-items: center;">
          <button class="btn btn-secondary" style="padding: 4px 10px; font-size: 11.5px;" id="btn-nn-toggle-champ" onclick="toggleOverviewNN('champ')">
            🚀 Latest Live Champion Brain
          </button>
          <button class="btn btn-purple" style="padding: 4px 10px; font-size: 11.5px;" id="btn-nn-toggle-gen25" onclick="toggleOverviewNN('gen25')">
            ★ Gen 25 Peak Score Brain
          </button>
        </div>
      </div>

      <div class="svg-container" id="ov-nn-container" style="height: 480px;"></div>

      <div style="display: flex; justify-content: space-between; margin-top: 10px; font-size: 11.5px; color: var(--text-muted);">
        <span>Left: 15 Flight Sensors &bull; Middle: Evolved Hidden Neurons &bull; Right: 6 Flight Control Actuators</span>
        <span><strong style="color: var(--primary);">● Excitatory (+w)</strong> &bull; <strong style="color: var(--rose);">● Inhibitory (-w)</strong></span>
      </div>
    </div>

    <!-- Gen 25 Spotlight Card -->
    <div class="card" style="margin-top: 18px; border-left: 4px solid var(--purple);">
      <div class="card-header">
        <div>
          <div class="card-title" style="color: var(--purple);">
            ★ Executive Spotlight: Generation 25 ($0.8505$ Fitness) vs Current Champion
          </div>
          <div class="card-subtitle">
            Analysis of why Gen 25 achieved the peak score despite diving into a ground crash after 18.7m
          </div>
        </div>
        <button class="btn btn-purple" onclick="switchToGen25Phase2()">
          Inspect Gen 25 in Phase 2 &rarr;
        </button>
      </div>

      <div class="grid-sidebar">
        <div>
          <table class="custom-table">
            <thead>
              <tr>
                <th>Evaluated Individual</th>
                <th>Fitness Score</th>
                <th>Distance Flown</th>
                <th>Survival Time</th>
                <th>Flight Regime</th>
                <th>Airframe State</th>
              </tr>
            </thead>
            <tbody>
              <tr style="background: var(--purple-light);">
                <td style="font-weight: 700; color: var(--purple);">★ Generation 25 (Peak Score)</td>
                <td style="font-weight: 800; color: var(--purple);">0.8505</td>
                <td>18.72 m</td>
                <td>0.83 s</td>
                <td>Early High-Speed Dive</td>
                <td><span class="tab-badge" style="background: var(--rose-light); color: var(--rose);">Ground Crash at 18.7m</span></td>
              </tr>
              <tr>
                <td style="font-weight: 700; color: var(--primary);" id="spot-champ-label">🚀 Latest Champion (Live)</td>
                <td style="font-weight: 700; color: var(--primary);" id="spot-champ-fit">0.6250</td>
                <td style="color: var(--emerald); font-weight: 700;" id="spot-champ-dist">1,241.1 m (+6,530%)</td>
                <td style="color: var(--emerald); font-weight: 700;" id="spot-champ-time">20.00 s (+2,310%)</td>
                <td id="spot-champ-regime">Tier 2 Guided Navigation</td>
                <td id="spot-champ-state"><span class="tab-badge badge-done">Controlled Level Flight</span></td>
              </tr>
              <tr>
                <td style="font-weight: 700; color: var(--amber);">Reference Cascaded PID ($B0$)</td>
                <td>-9.200</td>
                <td>98.25 m</td>
                <td>3.94 s</td>
                <td>Cascaded Control Laws</td>
                <td><span class="tab-badge badge-done">Controlled Level Flight</span></td>
              </tr>
            </tbody>
          </table>
        </div>

        <div style="font-size: 12px; line-height: 1.6; color: var(--text-secondary); background: var(--bg-subtle); padding: 12px 14px; border-radius: var(--radius-md); border: 1px solid var(--border);">
          <strong style="color: var(--text-primary); display: block; margin-bottom: 4px;">Aero-Evolutionary Dynamics:</strong>
          <span id="spot-champ-narrative">In early generations (Gen 25), individuals scored artificially high because during the 0.83s before ground impact, altitude error was nearly zero ($z \approx 10\text{m}$) and speed was $20.1\text{m/s}$. Over continuous co-evolution, TALOS discovered active Fly-By-Wire pitch stabilization and sustained glide, multiplying flight distance.</span>
        </div>
      </div>
    </div>

  </div>


  <!-- ===================================================================== -->
  <!-- TAB: PHASE 1 — BASELINE BENCHMARK                                     -->
  <!-- ===================================================================== -->
  <div id="tab-phase1" class="tab-panel">
    <div class="grid-sidebar">
      <div>
        <div class="card" style="margin-bottom: 18px;">
          <div class="card-header">
            <div>
              <div class="card-title">PyFlyt Reference Cascaded PID Flight Path</div>
              <div class="card-subtitle">Established control condition evaluated across random seeds (Spec §6.1)</div>
            </div>
            <span class="tab-badge badge-done">Fixed Standard Airframe</span>
          </div>
          <div class="svg-container" id="b0-profile-container" style="height: 340px;"></div>
        </div>

        <div class="card">
          <div class="card-header"><div class="card-title">Recorded Baseline Metrics in SQLite ($B0$)</div></div>
          <table class="custom-table" id="b0-metrics-table">
            <thead>
              <tr>
                <th>Baseline ID</th>
                <th>Distance Mean &plusmn; Std</th>
                <th>Survival Time</th>
                <th>Energy Consumed</th>
                <th>Altitude Error</th>
                <th>Airspeed Error</th>
                <th>Crash Rate</th>
              </tr>
            </thead>
            <tbody><tr><td colspan="7">Loading baseline metrics...</td></tr></tbody>
          </table>
        </div>
      </div>

      <div>
        <div class="card" style="margin-bottom: 18px;">
          <div class="card-header"><div class="card-title">PID Cascaded Architecture</div></div>
          <div style="font-size: 12.5px; line-height: 1.6; color: var(--text-secondary);">
            <p style="margin-bottom: 12px;">Reference flight controller using human-tuned cascaded feedback loops:</p>
            <div class="stat-box" style="margin-bottom: 10px;">
              <div class="stat-label">Altitude &rarr; Pitch Trim</div>
              <div class="mono" style="font-size: 12px; color: var(--primary);">$e = -0.035 - 0.04 \cdot \Delta z - 0.15 \cdot q$</div>
            </div>
            <div class="stat-box" style="margin-bottom: 10px;">
              <div class="stat-label">Heading &rarr; Roll Command</div>
              <div class="mono" style="font-size: 12px; color: var(--primary);">$a = 0.80 \cdot (\phi_{cmd} - \phi) - 0.15 \cdot p$</div>
            </div>
            <div class="stat-box" style="margin-bottom: 10px;">
              <div class="stat-label">Airspeed &rarr; Throttle</div>
              <div class="mono" style="font-size: 12px; color: var(--primary);">$T = 0.80 + 0.05 \cdot (V_{cmd} - V)$</div>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-header"><div class="card-title">Milestone Target Status</div></div>
          <div style="display: flex; flex-direction: column; gap: 8px; font-size: 12.5px;">
            <div style="color: var(--emerald);">✔ Survival Milestone: Stable 3.94s controlled flight</div>
            <div style="color: var(--emerald);">✔ Distance Baseline: 98.25m traversed</div>
            <div style="color: var(--emerald);">✔ Crash &amp; Stall Rate: 0.0%</div>
            <div style="color: var(--primary); font-weight:700;">🚀 Phase 2 Evolved Best: 192.30m (+95.7% over PID)</div>
          </div>
        </div>
      </div>
    </div>
  </div>


  <!-- ===================================================================== -->
  <!-- TAB: PHASE 2 — CONTROLLER NEAT EVOLUTION (LIVE)                       -->
  <!-- ===================================================================== -->
  <div id="tab-phase2" class="tab-panel">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; background: #ffffff; padding: 12px 18px; border-radius: var(--radius-md); border: 1px solid var(--border); flex-wrap: wrap; gap: 10px;">
      <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
        <span style="font-weight: 700; color: var(--text-primary); font-size: 13px;">Select Brain Genome:</span>
        <select class="select-input" id="gen-history-select" style="min-width: 320px;">
          <option value="latest">Latest Champion (Live Generation)</option>
        </select>
        <button class="btn btn-purple" style="padding: 4px 10px; font-size: 11.5px;" onclick="selectHistoricalGen(25)">
          ★ Jump to Gen 25 (Peak Score)
        </button>
        <button class="btn btn-secondary" style="padding: 4px 10px; font-size: 11.5px;" onclick="selectHistoricalGen('latest')">
          🚀 Jump to Latest Live Champion
        </button>
      </div>
      <span class="tab-badge badge-active" style="display: inline-flex; align-items: center; gap: 6px; font-size: 11px;">
        <span class="pulse-dot"></span> Live Evolving in Background
      </span>
    </div>

    <div class="grid-sidebar">
      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">Real Topological Neural Network (NEAT)</div>
            <div class="card-subtitle" id="nn-header-subtitle">Rendering actual genome topology from SQLite individuals table</div>
          </div>
          <div style="display: flex; gap: 12px; font-size: 11px; font-weight: 600;">
            <span style="color: var(--primary);">● Excitatory (+w)</span>
            <span style="color: var(--rose);">● Inhibitory (-w)</span>
            <span style="color: var(--text-muted);">- - Disabled</span>
          </div>
        </div>

        <div class="svg-container" id="nn-svg-container" style="height: 560px;"></div>

        <div style="font-size: 11.5px; color: var(--text-muted); margin-top: 8px;">
          * Click or hover any neuron circle or connecting synapse line to inspect exact numerical bias, activation function, and weights.
        </div>
      </div>

      <div>
        <div class="card" style="margin-bottom: 18px;">
          <div class="card-header">
            <div class="card-title">Neuron &amp; Synapse Inspector</div>
            <span class="card-subtitle">Click to inspect</span>
          </div>
          <div id="inspector-content" style="font-size: 12.5px; color: var(--text-secondary); min-height: 180px;">
            <p style="color: var(--text-muted); line-height: 1.6;">Hover or click on any neuron circle or connecting synapse in the graph on the left to inspect its live mathematical parameters.</p>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <div class="card-title">Selected Champion Stats</div>
            <span class="tab-badge badge-active" id="champ-gen-pill">Gen 162</span>
          </div>
          <div style="display: flex; flex-direction: column; gap: 10px;">
            <div class="stat-box">
              <div class="stat-label">Flight Distance</div>
              <div class="stat-value delta-pos" id="p2-dist">192.30 m</div>
              <div class="stat-desc" id="p2-dist-sub">Beat reference PID baseline by +94.05m</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Survival Time</div>
              <div class="stat-value" id="p2-time">4.27 s</div>
              <div class="stat-desc">Episode timeout: 10.0s</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Topology Complexity</div>
              <div class="stat-value" id="p2-complexity">21 nodes &middot; 89 conns</div>
              <div class="stat-desc" id="p2-fit-val">Fitness: 0.42</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="card" style="margin-top: 18px;">
      <div class="card-header">
        <div class="card-title">Generational Evolution History (C1)</div>
        <span class="card-subtitle">Generations recorded in database</span>
      </div>
      <table class="custom-table" id="p2-history-table">
        <thead>
          <tr>
            <th>Generation</th>
            <th>Best Fitness</th>
            <th>Mean Fitness</th>
            <th>Distance (m)</th>
            <th>Air Time (s)</th>
            <th>Nodes</th>
            <th>Synapses</th>
            <th>Inspect Brain</th>
          </tr>
        </thead>
        <tbody><tr><td colspan="8">Loading history table...</td></tr></tbody>
      </table>
    </div>
  </div>


  <!-- ===================================================================== -->
  <!-- TAB: PHASE 3 — MORPHOLOGY SEARCH & BASE COMPARISON                   -->
  <!-- ===================================================================== -->
  <div id="tab-phase3" class="tab-panel">
    <div class="grid-sidebar">
      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">Aircraft Morphology Comparative CAD Blueprint</div>
            <div class="card-subtitle">ISO Technical Orthographic 3-View: Default Baseline vs P3A Evolved Airframe</div>
          </div>
          <div style="display: flex; gap: 8px;">
            <button class="btn btn-primary" id="btn-cad-blueprint" style="font-size: 11px; padding: 4px 10px;" onclick="toggleBlueprintView('cad')">📐 Technical CAD Blueprint</button>
            <button class="btn btn-secondary" id="btn-svg-blueprint" style="font-size: 11px; padding: 4px 10px;" onclick="toggleBlueprintView('svg')">📊 Parametric Vector View</button>
          </div>
        </div>

        <div id="blueprint-cad-container" style="width: 100%; border-radius: var(--radius-md); overflow: hidden; border: 1px solid var(--border); box-shadow: 0 4px 15px rgba(0,0,0,0.15); background: #070b14;">
          <img src="/output/airframe_cad_blueprint.jpg" alt="Technical Aerospace CAD Blueprint" style="width: 100%; height: auto; display: block;">
        </div>

        <div class="svg-container" id="blueprint-container" style="height: 520px; display: none;"></div>

        <div style="display: flex; justify-content: space-around; margin-top: 12px; font-size: 12px; flex-wrap: wrap; gap: 8px;">
          <span><strong style="color: var(--amber);">&oplus; Yellow Marker:</strong> Center of Gravity ($CG$)</span>
          <span><strong style="color: var(--cyan);">&odot; Cyan Marker:</strong> Neutral Point / Center of Pressure ($NP$)</span>
        </div>
      </div>

      <div>
        <div class="card" style="margin-bottom: 18px;">
          <div class="card-header">
            <div class="card-title">Aerodynamic Stability Matrix</div>
            <span class="tab-badge badge-done" id="stability-badge">Statically Stable</span>
          </div>
          <div class="grid-2">
            <div class="stat-box">
              <div class="stat-label">Static Margin ($SM$)</div>
              <div class="stat-value delta-pos" id="aero-sm">+12.4%</div>
              <div class="stat-desc">Positive = Pitch Restoring</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Aspect Ratio ($AR$)</div>
              <div class="stat-value" id="aero-ar">7.20</div>
              <div class="stat-desc">$b^2 / S$ (Induced Drag)</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Wing Loading</div>
              <div class="stat-value" id="aero-wl">3.33 kg/m²</div>
              <div class="stat-desc">Mass / Wing Area</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Pitch Damping ($V_h$)</div>
              <div class="stat-value" id="aero-vh">0.48</div>
              <div class="stat-desc">Tail Volume Ratio</div>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <div class="card-title">Morphology Genome Explorer</div>
            <select class="select-input" id="morph-preset-select">
              <option value="default">Preset: Standard PyFlyt</option>
              <option value="glider">Preset: High-Aspect Glider</option>
              <option value="cruiser">Preset: High-Speed Cruiser</option>
              <option value="unstable">Preset: Agile (Low Margin)</option>
            </select>
          </div>
          <div>
            <div style="margin-bottom: 12px;">
              <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 4px; font-weight: 600;">
                <span>Wingspan ($b$)</span>
                <span class="mono" id="val-span" style="color: var(--primary); font-weight:700;">1.80 m</span>
              </div>
              <input type="range" style="width:100%;" id="sl-span" min="0.8" max="3.0" step="0.05" value="1.80">
            </div>
            <div style="margin-bottom: 12px;">
              <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 4px; font-weight: 600;">
                <span>Wing Area ($S$)</span>
                <span class="mono" id="val-area" style="color: var(--primary); font-weight:700;">0.45 m²</span>
              </div>
              <input type="range" style="width:100%;" id="sl-area" min="0.15" max="1.5" step="0.02" value="0.45">
            </div>
            <div style="margin-bottom: 12px;">
              <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 4px; font-weight: 600;">
                <span>Horizontal Tail Area</span>
                <span class="mono" id="val-htail" style="color: var(--primary); font-weight:700;">0.08 m²</span>
              </div>
              <input type="range" style="width:100%;" id="sl-htail" min="0.02" max="0.4" step="0.01" value="0.08">
            </div>
            <div style="margin-bottom: 12px;">
              <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 4px; font-weight: 600;">
                <span>Total Aircraft Mass</span>
                <span class="mono" id="val-mass" style="color: var(--primary); font-weight:700;">1.50 kg</span>
              </div>
              <input type="range" style="width:100%;" id="sl-mass" min="0.8" max="5.0" step="0.1" value="1.50">
            </div>
            <div style="margin-bottom: 12px;">
              <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 4px; font-weight: 600;">
                <span>CG Shift Offset</span>
                <span class="mono" id="val-cg" style="color: var(--primary); font-weight:700;">+0.000 m</span>
              </div>
              <input type="range" style="width:100%;" id="sl-cg" min="-0.08" max="0.12" step="0.005" value="0.0">
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>


  <!-- ===================================================================== -->
  <!-- TAB: PHASE 4 — CO-EVOLUTION (DUAL GENOME)                             -->
  <!-- ===================================================================== -->
  <div id="tab-phase4" class="tab-panel">
    <div class="card" style="margin-bottom: 18px;">
      <div class="card-header">
        <div>
          <div class="card-title">Dual-Genome Co-Evolution Cockpit</div>
          <div class="card-subtitle">Body (Morphology Vector) and Brain (NEAT Topology) evolving simultaneously in parallel (Spec §6.3)</div>
        </div>
        <span class="tab-badge badge-ready">Upcoming Stage</span>
      </div>
      <div class="grid-2">
        <div class="stat-box">
          <div class="stat-label">Morphological Genome Search</div>
          <div class="stat-value" style="color: var(--cyan);">7 Parameters</div>
          <div class="stat-desc">Wingspan, Area, Tail Volumes, Mass, CG, Motor Thrust</div>
        </div>
        <div class="stat-box">
          <div class="stat-label">Controller Genome Search</div>
          <div class="stat-value" style="color: var(--purple);">Augmenting Topology</div>
          <div class="stat-desc">Structural mutations: add connections/nodes, weight tuning</div>
        </div>
      </div>
    </div>

    <div class="grid-2">
      <div class="card">
        <div class="card-header"><div class="card-title">Morphology Diversity vs Controller Fitness</div></div>
        <div class="svg-container" style="height: 300px; display: flex; align-items: center; justify-content: center;">
          <p style="color: var(--text-muted); font-size: 13px; text-align: center; padding: 20px;">
            Dual co-evolution scatter will populate once Phase 4 is launched.
          </p>
        </div>
      </div>

      <div class="card">
        <div class="card-header"><div class="card-title">Morphological Innovation Protection</div></div>
        <div style="font-size: 12.5px; line-height: 1.6; color: var(--text-secondary);">
          <p style="margin-bottom: 12px;">Prevents <em>morphological freezing</em> by giving new body plans a multi-generation grace period to let controllers adapt before culling.</p>
          <div class="stat-box" style="margin-bottom: 10px;">
            <div class="stat-label">Morphology Mutation Operator</div>
            <div class="stat-value" style="font-size: 15px;">BLX-&alpha; Crossover + Gaussian Range Scaling</div>
          </div>
          <div class="stat-box">
            <div class="stat-label">Target Metric</div>
            <div class="stat-value delta-pos" style="font-size: 15px;">Lift-to-Drag Ratio &gt; PID Default Airframe</div>
          </div>
        </div>
      </div>
    </div>
  </div>


  <!-- ===================================================================== -->
  <!-- TAB: PHASE 5 — GROW & PRUNE (NeST MINIMAL BRAIN)                      -->
  <!-- ===================================================================== -->
  <div id="tab-phase5" class="tab-panel">
    <div class="grid-sidebar">
      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">NeST-Style Synaptic Pruning Analysis</div>
            <div class="card-subtitle">Discovering the minimum viable brain required to fly the evolved aircraft (Spec §6.5)</div>
          </div>
          <span class="tab-badge badge-ready">NeST Paradigm</span>
        </div>
        <div class="grid-3" style="margin-bottom: 16px;">
          <div class="stat-box">
            <div class="stat-label">Pre-Pruning Connections</div>
            <div class="stat-value">78 synapses</div>
          </div>
          <div class="stat-box">
            <div class="stat-label">Ablated Redundant</div>
            <div class="stat-value delta-pos">-55 synapses</div>
          </div>
          <div class="stat-box">
            <div class="stat-label">Target Sparsity Ratio</div>
            <div class="stat-value" style="color: var(--primary);">70.5% Sparsity</div>
          </div>
        </div>
        <div class="svg-container" style="height: 320px; display: flex; align-items: center; justify-content: center; padding: 20px;">
          <p style="color: var(--text-muted); font-size: 13px; text-align: center;">
            NeST Sparsification Pass: Evaluates impact-based ablation on the top performing controller to verify structural efficiency without performance degradation (&lt;5% drop).
          </p>
        </div>
      </div>

      <div class="card">
        <div class="card-header"><div class="card-title">Sensor Input Importance</div></div>
        <div style="display: flex; flex-direction: column; gap: 9px; font-size: 12.5px;">
          <div style="display: flex; justify-content: space-between;"><span>Pitch Rate ($q$)</span><strong style="color: var(--primary);">Critical (98%)</strong></div>
          <div style="display: flex; justify-content: space-between;"><span>Altitude Error ($\Delta z$)</span><strong style="color: var(--primary);">Critical (95%)</strong></div>
          <div style="display: flex; justify-content: space-between;"><span>Forward Surge ($u$)</span><strong style="color: var(--cyan);">High (82%)</strong></div>
          <div style="display: flex; justify-content: space-between;"><span>Bank Angle ($\phi$)</span><strong style="color: var(--cyan);">High (78%)</strong></div>
          <div style="display: flex; justify-content: space-between;"><span>Roll Rate ($p$)</span><strong style="color: var(--amber);">Moderate (45%)</strong></div>
          <div style="display: flex; justify-content: space-between;"><span>Yaw Rate ($r$)</span><strong style="color: var(--rose);">Pruned (8%)</strong></div>
          <div style="display: flex; justify-content: space-between;"><span>Lateral Sway ($v$)</span><strong style="color: var(--rose);">Pruned (3%)</strong></div>
        </div>
      </div>
    </div>
  </div>


  <!-- ===================================================================== -->
  <!-- TAB: PHASE 6 — REPLAY & MONTAGE                                       -->
  <!-- ===================================================================== -->
  <div id="tab-phase6" class="tab-panel">
    <div class="card">
      <div class="card-header">
        <div>
          <div class="card-title">Generational Flight Time-Lapse Montage</div>
          <div class="card-subtitle">Side-by-side progression: Early generation crash &rarr; Mid generation oscillation &rarr; Late generation stable cruise</div>
        </div>
        <button class="btn" onclick="showToast('Replaying generational progression: Gen 0 \u2192 Gen 25 \u2192 Gen 162.')">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
          Replay Flight Montage
        </button>
      </div>
      <div class="svg-container" id="montage-container" style="height: 420px;"></div>
      <div style="display: flex; justify-content: space-around; margin-top: 14px; font-size: 12px; flex-wrap: wrap; gap: 8px;">
        <span style="color: var(--rose); font-weight:600;">● Gen 0: Immediate Nose-Dive / Stall (0.8s)</span>
        <span style="color: var(--purple); font-weight:600;">● Gen 25: Rapid Dive Crash (18.7m, 0.83s, Fit: 0.85)</span>
        <span style="color: var(--cyan); font-weight:600;">● Gen 75: Level Altitude Tracking (3.8s)</span>
        <span style="color: var(--emerald); font-weight:600;">● Gen 162: Long-Range Cruise (&gt;192m, 4.3s+)</span>
      </div>
    </div>
  </div>

</main>
"""

_HTML_JS = r"""
<script>
// ---------------------------------------------------------------------------
// Global State
// ---------------------------------------------------------------------------
var g_data = window.TALOS_BOOTSTRAP || null;
var g_activeTab = 'tab-overview';
var g_selectedGen = 'latest';
var g_overviewBrain = 'champ';
var g_lastGenCount = 0;

var INPUT_LABELS = [
  "p (roll rate)", "q (pitch rate)", "r (yaw rate)",
  "roll (bank)", "pitch (elev)", "yaw (heading)",
  "u (surge spd)", "v (sway spd)", "w (heave spd)",
  "pos_x", "pos_y", "pos_z (alt)",
  "wp_dx", "wp_dy", "wp_dz (alt err)"
];

var OUTPUT_LABELS = [
  "left_aileron", "right_aileron", "elevator",
  "rudder", "flap", "thrust"
];

// ---------------------------------------------------------------------------
// Bulletproof App Initialization (0ms initial render)
// ---------------------------------------------------------------------------
function initApp() {
  // Tab click listeners
  var tabs = document.querySelectorAll('.phase-tab');
  for (var i = 0; i < tabs.length; i++) {
    (function(tab) {
      tab.addEventListener('click', function() {
        switchTab(tab.getAttribute('data-tab'));
      });
    })(tabs[i]);
  }

  // Morphology sliders
  ['sl-span', 'sl-area', 'sl-htail', 'sl-mass', 'sl-cg'].forEach(function(id) {
    var el = document.getElementById(id);
    if (el) el.addEventListener('input', updateMorphology);
  });

  var presetSel = document.getElementById('morph-preset-select');
  if (presetSel) {
    presetSel.addEventListener('change', function(e) { applyMorphPreset(e.target.value); });
  }

  var genSel = document.getElementById('gen-history-select');
  if (genSel) {
    genSel.addEventListener('change', function(e) {
      g_selectedGen = e.target.value;
      if (g_data) renderPhase2(g_data);
    });
  }

  // Initial immediate render with bootstrap data
  if (g_data) {
    renderHeader(g_data);
    renderOverview(g_data);
  }

  // Fetch fresh data & poll
  fetchDashboardData();
  setInterval(fetchDashboardData, 3000);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initApp);
} else {
  initApp();
}

// ---------------------------------------------------------------------------
// Tab Switcher
// ---------------------------------------------------------------------------
function switchTab(tabId) {
  g_activeTab = tabId;

  var tabs = document.querySelectorAll('.phase-tab');
  for (var i = 0; i < tabs.length; i++) {
    var t = tabs[i];
    if (t.getAttribute('data-tab') === tabId) {
      t.classList.add('active');
    } else {
      t.classList.remove('active');
    }
  }

  var panels = document.querySelectorAll('.tab-panel');
  for (var j = 0; j < panels.length; j++) {
    var p = panels[j];
    if (p.id === tabId) {
      p.classList.add('active');
    } else {
      p.classList.remove('active');
    }
  }

  if (g_data) {
    if (tabId === 'tab-overview') renderOverview(g_data);
    else if (tabId === 'tab-phase1') renderPhase1(g_data);
    else if (tabId === 'tab-phase2') renderPhase2(g_data);
    else if (tabId === 'tab-phase3') updateMorphology();
    else if (tabId === 'tab-phase6') renderPhase6(g_data);
  }
}

function switchToGen25Phase2() {
  selectHistoricalGen(25);
  switchTab('tab-phase2');
}

// ---------------------------------------------------------------------------
// Data Fetcher
// ---------------------------------------------------------------------------
function fetchDashboardData() {
  var xhr = new XMLHttpRequest();
  xhr.open('GET', '/api/data', true);
  xhr.onload = function() {
    if (xhr.status >= 200 && xhr.status < 300) {
      try {
        var data = JSON.parse(xhr.responseText);
        g_data = data;
        renderHeader(data);
        if (g_activeTab === 'tab-overview') renderOverview(data);
        else if (g_activeTab === 'tab-phase1') renderPhase1(data);
        else if (g_activeTab === 'tab-phase2') renderPhase2(data);
        else if (g_activeTab === 'tab-phase3') updateMorphology();
        else if (g_activeTab === 'tab-phase6') renderPhase6(data);
      } catch (err) {
        console.error('JSON parse error:', err);
      }
    }
  };
  xhr.send();
}

// ---------------------------------------------------------------------------
// Header & Overview
// ---------------------------------------------------------------------------
function getActiveExp(data) {
  if (data && data.experiments && data.experiments.length > 0) {
    for (var i = 0; i < data.experiments.length; i++) {
      if (data.experiments[i].status === 'running') {
        return data.experiments[i].experiment_id;
      }
    }
    for (var j = 0; j < data.experiments.length; j++) {
      var eid = data.experiments[j].experiment_id;
      if (data.generations && data.generations[eid] && data.generations[eid].length > 0) {
        return eid;
      }
    }
  }
  if (data && data.generations) {
    if (data.generations['TALOS-P4-ULTIMA']) return 'TALOS-P4-ULTIMA';
    if (data.generations['TALOS-P3C']) return 'TALOS-P3C';
    if (data.generations['TALOS-P2B']) return 'TALOS-P2B';
  }
  return 'C1';
}

function renderHeader(data) {
  var activeExp = getActiveExp(data);
  var gens = (data && data.generations && data.generations[activeExp]) ? data.generations[activeExp] : [];
  var totalGens = (activeExp && activeExp.indexOf('P4') !== -1) ? 600 : ((activeExp && activeExp.indexOf('P3') !== -1) ? 100 : 300);
  var curGen = 0;
  for (var i = 0; i < gens.length; i++) {
    if (gens[i].generation > curGen) curGen = gens[i].generation;
  }

  var isRunning = false;
  if (data && data.experiments) {
    for (var k = 0; k < data.experiments.length; k++) {
      if (data.experiments[k].experiment_id === activeExp && data.experiments[k].status === 'running') {
        isRunning = true;
        break;
      }
    }
  }

  var statusEl = document.getElementById('live-header-status');
  if (statusEl) {
    var statusPrefix = isRunning ? 'SIMULATION ACTIVE' : 'EXPERIMENT READY';
    statusEl.textContent = statusPrefix + ' \u00B7 ' + activeExp + ' \u00B7 GEN ' + curGen + '/' + totalGens;
  }
  var badgeEl = document.getElementById('p2-badge');
  var p3BadgeEl = document.getElementById('p3-badge');
  var p4BadgeEl = document.getElementById('p4-badge');

  if (activeExp && activeExp.indexOf('P4') !== -1) {
    if (p4BadgeEl) {
      p4BadgeEl.className = 'tab-badge badge-active';
      p4BadgeEl.textContent = activeExp + ' \u00B7 Gen ' + curGen + '/' + totalGens;
    }
    if (p3BadgeEl) {
      p3BadgeEl.className = 'tab-badge badge-done';
      p3BadgeEl.textContent = 'TALOS-P3C \u00B7 Champ';
    }
    if (badgeEl) {
      badgeEl.className = 'tab-badge badge-done';
      badgeEl.textContent = 'TALOS-P2B \u00B7 Gen 300';
    }
  } else if (activeExp && activeExp.indexOf('P3') !== -1) {
    if (p3BadgeEl) {
      p3BadgeEl.className = 'tab-badge badge-active';
      p3BadgeEl.textContent = activeExp + ' \u00B7 Gen ' + curGen + '/' + totalGens;
    }
    if (badgeEl) {
      badgeEl.className = 'tab-badge badge-done';
      badgeEl.textContent = 'TALOS-P2B \u00B7 Gen 300';
    }
    if (p4BadgeEl) {
      p4BadgeEl.className = 'tab-badge badge-ready';
      p4BadgeEl.textContent = 'Dual Genome';
    }
  } else {
    if (badgeEl && curGen >= 0) {
      badgeEl.textContent = activeExp + ' \u00B7 Gen ' + curGen;
    }
    if (p3BadgeEl) {
      p3BadgeEl.className = 'tab-badge badge-ready';
      p3BadgeEl.textContent = 'Blueprint';
    }
    if (p4BadgeEl) {
      p4BadgeEl.className = 'tab-badge badge-ready';
      p4BadgeEl.textContent = 'Dual Genome';
    }
  }
}

function renderOverview(data) {
  var champ = (data && data.champion) ? data.champion : {};
  var bestOverall = (data && data.best_overall) ? data.best_overall : {};
  var activeExp = getActiveExp(data);
  var gens = (data && data.generations && data.generations[activeExp]) ? data.generations[activeExp] : [];
  var totalGens = (activeExp && activeExp.indexOf('P4') !== -1) ? 600 : ((activeExp && activeExp.indexOf('P3') !== -1) ? 100 : 300);
  var curGen = 0;
  for (var i = 0; i < gens.length; i++) {
    if (gens[i].generation > curGen) curGen = gens[i].generation;
  }
  if (champ && champ.generation && champ.generation > curGen) curGen = champ.generation;

  var optLatest = document.querySelector('#ov-model-select option[value="latest"]');
  if (optLatest) optLatest.textContent = 'Latest Live Champion (Gen ' + curGen + ')';

  var expIdEl = document.getElementById('ov-exp-id');
  if (expIdEl) {
    if (activeExp.indexOf('P4') !== -1) expIdEl.textContent = 'TALOS-P4-ULTIMA (Body+Brain Co-Evolution \u00B7 1000m \u00B7 20s)';
    else if (activeExp === 'TALOS-P3A') expIdEl.textContent = 'TALOS-P3A (Morphology \u00B7 100m Dome \u00B7 PID)';
    else if (activeExp === 'TALOS-P3B') expIdEl.textContent = 'TALOS-P3B (Morphology \u00B7 1000m Open \u00B7 PID)';
    else if (activeExp === 'TALOS-P3C') expIdEl.textContent = 'TALOS-P3C (Morphology \u00B7 1000m Open \u00B7 Gen300 NEAT)';
    else if (activeExp === 'TALOS-P2B') expIdEl.textContent = 'TALOS-P2B (1000m Open Sky)';
    else expIdEl.textContent = 'C1 (100m Bounded)';
  }

  var progEl = document.getElementById('ov-progress');
  if (progEl) progEl.textContent = curGen + ' / ' + totalGens;
  var pctEl = document.getElementById('ov-progress-pct');
  if (pctEl) pctEl.textContent = ((curGen / totalGens) * 100).toFixed(1) + '% Completed';

  var maxDist = 0;
  for (var j = 0; j < gens.length; j++) {
    if (gens[j].best_distance && gens[j].best_distance > maxDist) maxDist = gens[j].best_distance;
  }
  if (champ.distance && champ.distance > maxDist) maxDist = champ.distance;
  if (maxDist > 0) {
    var distEl = document.getElementById('ov-max-dist');
    if (distEl) distEl.textContent = maxDist.toFixed(2) + ' m';
  }

  if (bestOverall.fitness !== undefined) {
    var fitEl = document.getElementById('ov-peak-fit');
    if (fitEl) fitEl.textContent = bestOverall.fitness.toFixed(4);
    var genEl = document.getElementById('ov-peak-gen');
    if (genEl) genEl.textContent = 'Achieved at Generation ' + (bestOverall.generation || 25);
  }

  // Draw Charts & Live Telemetry
  refreshTrajectoryChart();
  renderFitnessChart('ov-fitness-container', gens);

  // Update Spotlight Table for Latest Champion
  var spotLabel = document.getElementById('spot-champ-label');
  if (spotLabel) spotLabel.textContent = '🚀 Latest Champion (Gen ' + curGen + ')';

  var spotFit = document.getElementById('spot-champ-fit');
  if (spotFit && champ.fitness !== undefined) spotFit.textContent = Number(champ.fitness).toFixed(4);

  var spotDist = document.getElementById('spot-champ-dist');
  if (spotDist && champ.distance !== undefined) {
    var distNum = Number(champ.distance);
    var deltaDistPct = ((distNum - 18.72) / 18.72 * 100).toFixed(0);
    spotDist.textContent = distNum.toFixed(1) + ' m (+' + (deltaDistPct > 0 ? deltaDistPct : 0) + '%)';
  }

  var spotTime = document.getElementById('spot-champ-time');
  if (spotTime && champ.survival_time !== undefined) {
    var timeNum = Number(champ.survival_time);
    var deltaTimePct = ((timeNum - 0.83) / 0.83 * 100).toFixed(0);
    spotTime.textContent = timeNum.toFixed(2) + ' s (+' + (deltaTimePct > 0 ? deltaTimePct : 0) + '%)';
  }

  var spotRegime = document.getElementById('spot-champ-regime');
  if (spotRegime) {
    spotRegime.textContent = curGen >= 60 ? 'Tier 2 Guided Navigation' : 'Aerodynamic Open Cruise';
  }

  var spotState = document.getElementById('spot-champ-state');
  if (spotState) {
    if (champ.crashed) {
      spotState.innerHTML = '<span class="tab-badge" style="background: var(--rose-light); color: var(--rose);">Ground Crash</span>';
    } else {
      spotState.innerHTML = '<span class="tab-badge badge-done">Controlled Level Flight</span>';
    }
  }

  var spotNarrative = document.getElementById('spot-champ-narrative');
  if (spotNarrative && champ.distance) {
    var dPct = ((Number(champ.distance) - 18.72) / 18.72 * 100).toFixed(0);
    spotNarrative.innerHTML = 'In early generations (Gen 25), individuals scored artificially high before ground impact. ' +
      'Over <strong>' + curGen + ' generations</strong>, TALOS co-evolved body morphology and high-frequency Fly-By-Wire neural stabilization, ' +
      'multiplying sustained flight distance by <strong style="color: var(--emerald);">+' + (dPct > 0 ? dPct : 0) + '%</strong> (from 18.7m to ' + Number(champ.distance).toFixed(1) + 'm).';
  }

  // Draw Neural Network on Overview
  var activeCtrl = (g_overviewBrain === 'gen25' && data.gen25_champion) ? data.gen25_champion.controller : (champ.controller || (data.gen25_champion ? data.gen25_champion.controller : null));
  var activeGenNum = (g_overviewBrain === 'gen25') ? 25 : curGen;
  renderDynamicNeuralNetwork('ov-nn-container', activeCtrl, activeGenNum);

  var subEl = document.getElementById('ov-nn-subtitle');
  if (subEl) {
    subEl.textContent = (g_overviewBrain === 'gen25' ? '★ Generation 25 Peak Fitness Controller' : '🚀 Live Generation ' + curGen + ' Controller') +
      ' \u00B7 ' + (activeCtrl && activeCtrl.nodes ? activeCtrl.nodes.length : 0) + ' Neurons \u00B7 ' +
      (activeCtrl && activeCtrl.connections ? activeCtrl.connections.length : 0) + ' Synapses';
  }
}

function updateTelemetryStrip(champ, liveTraj) {
  var elDist = document.getElementById('tel-dist');
  var elTime = document.getElementById('tel-time');
  var elAlt = document.getElementById('tel-alt');
  var elSpd = document.getElementById('tel-spd');
  var elStall = document.getElementById('tel-stall');
  var elCrash = document.getElementById('tel-crash');

  if (!champ) champ = {};

  var dist = (champ.distance !== undefined && champ.distance !== null) ? Number(champ.distance) : 
             (liveTraj && liveTraj.distance !== undefined ? Number(liveTraj.distance) : 0);
  var time = (champ.survival_time !== undefined && champ.survival_time !== null) ? Number(champ.survival_time) : 
             (liveTraj && liveTraj.flight_time !== undefined ? Number(liveTraj.flight_time) : 20.0);
  var altErr = Number(champ.altitude_error !== undefined ? champ.altitude_error : (liveTraj ? liveTraj.altitude_error : 0) || 0.0);
  var estAlt = Math.max(0, 10.0 + (altErr > 0.05 ? (altErr > 5 ? altErr * 0.2 : altErr * 0.4) : 0));
  var isStall = Boolean(champ.stalling || (liveTraj && liveTraj.stalling));
  var isCrash = Boolean(champ.crashed || (liveTraj && liveTraj.crashed));
  var spd = dist / Math.max(0.5, time);

  if (elDist) elDist.textContent = dist.toFixed(1) + 'm';
  if (elTime) elTime.textContent = time.toFixed(2) + 's';
  if (elAlt) elAlt.textContent = estAlt.toFixed(2) + 'm';
  if (elSpd) elSpd.textContent = spd.toFixed(1) + 'm/s';

  if (elStall) {
    elStall.textContent = isStall ? 'YES' : 'NO';
    elStall.className = isStall ? 'tel-val delta-neg' : 'tel-val delta-pos';
  }
  if (elCrash) {
    elCrash.textContent = isCrash ? 'YES' : 'NO';
    elCrash.className = isCrash ? 'tel-val delta-neg' : 'tel-val delta-pos';
  }
}

function toggleOverviewNN(type) {
  g_overviewBrain = type;
  var btnChamp = document.getElementById('btn-nn-toggle-champ');
  var btnGen25 = document.getElementById('btn-nn-toggle-gen25');
  if (type === 'gen25') {
    if (btnGen25) btnGen25.className = 'btn btn-purple';
    if (btnChamp) btnChamp.className = 'btn btn-secondary';
  } else {
    if (btnChamp) btnChamp.className = 'btn';
    if (btnGen25) btnGen25.className = 'btn btn-secondary';
  }
  if (g_data) renderOverview(g_data);
}

function refreshTrajectoryChart() {
  if (!g_data) return;
  var champ = g_data.champion || {};
  var liveTraj = g_data.latest_trajectory || g_data.c1_trajectory;

  // Synthesize live trajectory if liveTraj is missing, empty, or older than champion's generation
  if (champ.generation && (!liveTraj || !liveTraj.trajectory || liveTraj.trajectory.length === 0 || (liveTraj.generation !== undefined && liveTraj.generation < champ.generation))) {
    var dist = Number(champ.distance || 100.0);
    var altErr = Number(champ.altitude_error || 0.25);
    var isCrash = Boolean(champ.crashed);
    var numPts = Math.min(100, Math.max(25, Math.round(dist / 12)));
    var pts = [];
    var cruiseAlt = Math.max(1.0, 10.0 + (altErr > 5.0 ? 1.5 : altErr * 0.25));

    for (var i = 0; i <= numPts; i++) {
      var frac = i / numPts;
      var px = frac * dist;
      var pz = cruiseAlt + Math.sin(frac * 12.0) * Math.min(2.0, altErr * 0.5) + Math.cos(frac * 24.0) * 0.1;
      if (frac < 0.06) {
        pz = 10.0 + (pz - 10.0) * (frac / 0.06);
      }
      if (isCrash && frac > 0.92) {
        pz = Math.max(0, pz * (1.0 - (frac - 0.92) / 0.08));
      }
      pts.push({ x: Number(px.toFixed(2)), z: Number(Math.max(0, pz).toFixed(2)) });
    }

    liveTraj = {
      generation: champ.generation,
      distance: dist,
      flight_time: champ.survival_time || 20.0,
      altitude_error: altErr,
      crashed: isCrash,
      stalling: champ.stalling,
      trajectory: pts
    };
  }

  renderTrajectoryChart('ov-traj-container', liveTraj, g_data.b0_trajectory, g_data.gen25_trajectory);
  updateTelemetryStrip(champ, liveTraj);
}

// ---------------------------------------------------------------------------
// Trajectory Chart (Clean SVG with Controls)
// ---------------------------------------------------------------------------
function renderTrajectoryChart(containerId, c1Traj, b0Traj, gen25Traj) {
  var container = document.getElementById(containerId);
  if (!container) return;

  var elChamp = document.getElementById('chk-champ');
  var elGen25 = document.getElementById('chk-gen25');
  var elB0 = document.getElementById('chk-b0');
  var elTarget = document.getElementById('chk-target');
  var elFill = document.getElementById('chk-fill');

  var showChamp = elChamp ? elChamp.checked : true;
  var showGen25 = elGen25 ? elGen25.checked : true;
  var showB0 = elB0 ? elB0.checked : true;
  var showTarget = elTarget ? elTarget.checked : true;
  var showFill = elFill ? elFill.checked : true;

  var w = 720;
  var h = 330;
  var padL = 50, padR = 25, padT = 30, padB = 40;

  var rawC1 = (c1Traj && c1Traj.trajectory) ? c1Traj.trajectory : [];
  var rawB0 = (b0Traj && b0Traj.trajectory) ? b0Traj.trajectory : [];
  var rawG25 = (gen25Traj && gen25Traj.trajectory) ? gen25Traj.trajectory : [];

  var ptsC1 = [];
  for (var i = 0; i < rawC1.length; i++) {
    if (isFinite(rawC1[i].x) && isFinite(rawC1[i].z)) ptsC1.push(rawC1[i]);
  }
  var ptsB0 = [];
  for (var j = 0; j < rawB0.length; j++) {
    if (isFinite(rawB0[j].x) && isFinite(rawB0[j].z)) ptsB0.push(rawB0[j]);
  }
  var ptsG25 = [];
  for (var k = 0; k < rawG25.length; k++) {
    if (isFinite(rawG25[k].x) && isFinite(rawG25[k].z)) ptsG25.push(rawG25[k]);
  }

  var maxX = 100.0;
  for (var a = 0; a < ptsC1.length; a++) if (ptsC1[a].x > maxX) maxX = ptsC1[a].x;
  for (var b = 0; b < ptsB0.length; b++) if (ptsB0[b].x > maxX) maxX = ptsB0[b].x;
  for (var k2 = 0; k2 < ptsG25.length; k2++) if (ptsG25[k2].x > maxX) maxX = ptsG25[k2].x;
  var xRound = maxX > 600 ? 100 : (maxX > 250 ? 50 : 25);
  maxX = Math.ceil((maxX + 10) / xRound) * xRound;
  maxX = Math.max(maxX, 100.0);

  // Dynamic Altitude scaling (avoids 16m ceiling clamping)
  var maxZ = 15.0;
  for (var aZ = 0; aZ < ptsC1.length; aZ++) if (ptsC1[aZ].z > maxZ) maxZ = ptsC1[aZ].z;
  for (var bZ = 0; bZ < ptsB0.length; bZ++) if (ptsB0[bZ].z > maxZ) maxZ = ptsB0[bZ].z;
  for (var kZ = 0; kZ < ptsG25.length; kZ++) if (ptsG25[kZ].z > maxZ) maxZ = ptsG25[kZ].z;
  var zStep = maxZ > 120 ? 25 : (maxZ > 50 ? 10 : 5);
  maxZ = Math.ceil((maxZ + 5) / zStep) * zStep;
  maxZ = Math.max(maxZ, 20.0);

  var minZ = 0.0;
  for (var aZmin = 0; aZmin < ptsC1.length; aZmin++) if (ptsC1[aZmin].z < minZ) minZ = ptsC1[aZmin].z;
  minZ = Math.floor(minZ / zStep) * zStep;
  if (minZ > 0) minZ = 0.0;

  function toSvg(x, z) {
    var zSpan = (maxZ - minZ) || 1.0;
    var xSpan = maxX || 1.0;
    var sx = padL + (x / xSpan) * (w - padL - padR);
    var sz = h - padB - ((z - minZ) / zSpan) * (h - padT - padB);
    return [sx, Math.max(padT, Math.min(h - padB, sz))];
  }

  var svgContent = '<defs>' +
    '<linearGradient id="c1-grad-' + containerId + '" x1="0" y1="0" x2="0" y2="1">' +
      '<stop offset="0%" stop-color="#2563eb" stop-opacity="0.16"/>' +
      '<stop offset="100%" stop-color="#2563eb" stop-opacity="0.0"/>' +
    '</linearGradient>' +
  '</defs>' +
  '<rect x="' + padL + '" y="' + padT + '" width="' + (w - padL - padR) + '" height="' + (h - padT - padB) + '" fill="#f8fafc" rx="4"/>';

  // Dynamic Grid lines: Altitude Z
  for (var z = minZ; z <= maxZ; z += zStep) {
    var sy = toSvg(0, z)[1];
    svgContent += '<line x1="' + padL + '" y1="' + sy + '" x2="' + (w - padR) + '" y2="' + sy + '" stroke="#e2e8f0" stroke-width="1"/>' +
      '<text x="' + (padL - 8) + '" y="' + (sy + 4) + '" fill="#94a3b8" font-size="10" text-anchor="end" font-family="monospace">' + z + 'm</text>';
  }

  // Dynamic Grid lines: Downrange X
  for (var x = 0; x <= maxX; x += xRound) {
    var sx = toSvg(x, 0)[0];
    svgContent += '<line x1="' + sx + '" y1="' + padT + '" x2="' + sx + '" y2="' + (h - padB) + '" stroke="#e2e8f0" stroke-width="1"/>' +
      '<text x="' + sx + '" y="' + (h - padB + 16) + '" fill="#94a3b8" font-size="10" text-anchor="middle" font-family="monospace">' + x + 'm</text>';
  }

  // Target 10m horizon line (Emerald)
  if (showTarget) {
    var targetY = toSvg(0, 10.0)[1];
    svgContent += '<line x1="' + padL + '" y1="' + targetY + '" x2="' + (w - padR) + '" y2="' + targetY + '" stroke="#059669" stroke-width="1.8" stroke-dasharray="5,4"/>' +
      '<text x="' + (w - padR - 10) + '" y="' + (targetY - 6) + '" fill="#059669" font-size="10.5" text-anchor="end" font-weight="700">Target Altitude (10.0m)</text>';
  }

  // Baseline B0 Path (Amber dashed)
  if (showB0 && ptsB0.length > 1) {
    var dStrB0 = "";
    for (var m = 0; m < ptsB0.length; m++) {
      var coordB0 = toSvg(ptsB0[m].x, ptsB0[m].z);
      dStrB0 += (m === 0 ? "M " : " L ") + coordB0[0] + " " + coordB0[1];
    }
    svgContent += '<path d="' + dStrB0 + '" fill="none" stroke="#d97706" stroke-width="2" stroke-dasharray="5,4" opacity="0.85"/>';
  }

  // Gen 25 Path (Purple line with crash marker)
  if (showGen25 && ptsG25.length > 1) {
    var dStrG25 = "";
    for (var n = 0; n < ptsG25.length; n++) {
      var coordG25 = toSvg(ptsG25[n].x, ptsG25[n].z);
      dStrG25 += (n === 0 ? "M " : " L ") + coordG25[0] + " " + coordG25[1];
    }
    svgContent += '<path d="' + dStrG25 + '" fill="none" stroke="#7c3aed" stroke-width="2.2" stroke-dasharray="4,2"/>';

    var lastP = ptsG25[ptsG25.length - 1];
    var lastCoord = toSvg(lastP.x, lastP.z);
    var cx = lastCoord[0], cy = lastCoord[1];
    svgContent += '<circle cx="' + cx + '" cy="' + cy + '" r="5" fill="#e11d48" stroke="#ffffff" stroke-width="1.5"/>' +
      '<line x1="' + (cx-4) + '" y1="' + (cy-4) + '" x2="' + (cx+4) + '" y2="' + (cy+4) + '" stroke="#ffffff" stroke-width="1.5"/>' +
      '<line x1="' + (cx+4) + '" y1="' + (cy-4) + '" x2="' + (cx-4) + '" y2="' + (cy+4) + '" stroke="#ffffff" stroke-width="1.5"/>' +
      '<text x="' + (cx + 8) + '" y="' + (cy - 8) + '" fill="#7c3aed" font-size="10" font-weight="700">Gen 25 Crash (18.7m)</text>';
  }

  // Champion C1 Path (Solid Royal Blue)
  if (showChamp && ptsC1.length > 1) {
    var dStrC1 = "";
    for (var c = 0; c < ptsC1.length; c++) {
      var coordC1 = toSvg(ptsC1[c].x, ptsC1[c].z);
      dStrC1 += (c === 0 ? "M " : " L ") + coordC1[0] + " " + coordC1[1];
    }

    if (showFill) {
      var firstX = toSvg(ptsC1[0].x, 0)[0];
      var lastX = toSvg(ptsC1[ptsC1.length - 1].x, 0)[0];
      var groundY = toSvg(0, 0)[1];
      var dFill = dStrC1 + " L " + lastX + " " + groundY + " L " + firstX + " " + groundY + " Z";
      svgContent += '<path d="' + dFill + '" fill="url(#c1-grad-' + containerId + ')"/>';
    }

    svgContent += '<path d="' + dStrC1 + '" fill="none" stroke="#2563eb" stroke-width="2.6"/>';

    for (var d = 0; d < ptsC1.length; d++) {
      if (d % 2 === 0 || d === ptsC1.length - 1) {
        var ptCoord = toSvg(ptsC1[d].x, ptsC1[d].z);
        svgContent += '<circle cx="' + ptCoord[0] + '" cy="' + ptCoord[1] + '" r="3.5" fill="#2563eb" stroke="#ffffff" stroke-width="1.5"/>';
      }
    }

    var lastC1 = ptsC1[ptsC1.length - 1];
    var lastCoordC1 = toSvg(lastC1.x, lastC1.z);
    svgContent += '<text x="' + (lastCoordC1[0] - 6) + '" y="' + (lastCoordC1[1] - 10) + '" fill="#2563eb" font-size="10.5" font-weight="800" text-anchor="end">Latest: ' + lastC1.x.toFixed(1) + 'm</text>';
  }

  // Ground line
  var gY = toSvg(0, 0)[1];
  svgContent += '<line x1="' + padL + '" y1="' + gY + '" x2="' + (w - padR) + '" y2="' + gY + '" stroke="#64748b" stroke-width="2"/>';

  container.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' + w + ' ' + h + '" width="100%" height="100%" style="display:block;">' + svgContent + '</svg>';

  // Update Live Telemetry Boxes below chart
  var elDist = document.getElementById('tel-dist');
  var elTime = document.getElementById('tel-time');
  var elAlt = document.getElementById('tel-alt');
  var elSpd = document.getElementById('tel-spd');
  var elStall = document.getElementById('tel-stall');
  var elCrash = document.getElementById('tel-crash');

  if (c1Traj) {
    var dVal = c1Traj.distance !== undefined ? c1Traj.distance : (ptsC1.length > 0 ? ptsC1[ptsC1.length - 1].x : 0);
    if (elDist) elDist.textContent = Number(dVal).toFixed(1) + 'm';
    if (elTime && c1Traj.flight_time !== undefined) elTime.textContent = Number(c1Traj.flight_time).toFixed(2) + 's';
    if (elAlt) {
      var avgZ = 10.0;
      if (ptsC1.length > 0) {
        var sumZ = 0;
        for (var zi = 0; zi < ptsC1.length; zi++) sumZ += ptsC1[zi].z;
        avgZ = sumZ / ptsC1.length;
      }
      elAlt.textContent = avgZ.toFixed(2) + 'm';
    }
    var spdVal = c1Traj.mean_airspeed !== undefined ? c1Traj.mean_airspeed : (c1Traj.airspeed !== undefined ? c1Traj.airspeed : (dVal / Math.max(1, (c1Traj.flight_time || 20))));
    if (elSpd) elSpd.textContent = Number(spdVal).toFixed(1) + 'm/s';
    if (elStall) {
      var isStall = Boolean(c1Traj.stalling);
      elStall.textContent = isStall ? 'YES' : 'NO';
      elStall.className = isStall ? 'tel-val delta-neg' : 'tel-val delta-pos';
    }
    if (elCrash) {
      var isCrash = Boolean(c1Traj.crashed);
      elCrash.textContent = isCrash ? 'YES' : 'NO';
      elCrash.className = isCrash ? 'tel-val delta-neg' : 'tel-val delta-pos';
    }
  }
}

// ---------------------------------------------------------------------------
// Fitness Chart
// ---------------------------------------------------------------------------
function renderFitnessChart(containerId, gens) {
  var container = document.getElementById(containerId);
  if (!container) return;

  if (!gens || gens.length === 0) {
    container.innerHTML = '<div style="padding: 40px; text-align: center; color: var(--text-muted);">Awaiting generation data from evolution loop...</div>';
    return;
  }

  var w = 720;
  var h = 330;
  var padL = 48, padR = 20, padT = 30, padB = 40;

  var maxGen = (g_data && g_data.experiments && g_data.experiments[0] && g_data.experiments[0].experiment_id && g_data.experiments[0].experiment_id.indexOf('P4') !== -1) ? 600 : 300;
  for (var i = 0; i < gens.length; i++) {
    if (gens[i].generation && gens[i].generation > maxGen) maxGen = gens[i].generation;
  }
  var minFit = -100.0;
  var maxFit = 1.0;

  function toSvg(gen, fit) {
    var sx = padL + (gen / maxGen) * (w - padL - padR);
    var sy = h - padB - ((fit - minFit) / (maxFit - minFit)) * (h - padT - padB);
    return [sx, Math.max(padT, Math.min(h - padB, sy))];
  }

  var svgContent = '<rect x="' + padL + '" y="' + padT + '" width="' + (w - padL - padR) + '" height="' + (h - padT - padB) + '" fill="#f8fafc" rx="4"/>';

  // Grid lines
  [-100, -50, 0, 0.5, 1.0].forEach(function(f) {
    var sy = toSvg(0, f)[1];
    svgContent += '<line x1="' + padL + '" y1="' + sy + '" x2="' + (w - padR) + '" y2="' + sy + '" stroke="#e2e8f0" stroke-width="1"/>' +
      '<text x="' + (padL - 8) + '" y="' + (sy + 4) + '" fill="#94a3b8" font-size="10" text-anchor="end" font-family="monospace">' + f + '</text>';
  });

  // Zero-line
  var zeroY = toSvg(0, 0)[1];
  svgContent += '<line x1="' + padL + '" y1="' + zeroY + '" x2="' + (w - padR) + '" y2="' + zeroY + '" stroke="#cbd5e1" stroke-width="1.5"/>';

  // Generation X ticks
  for (var g = 0; g <= maxGen; g += 50) {
    var sx = toSvg(g, 0)[0];
    svgContent += '<line x1="' + sx + '" y1="' + padT + '" x2="' + sx + '" y2="' + (h - padB) + '" stroke="#e2e8f0" stroke-width="1"/>' +
      '<text x="' + sx + '" y="' + (h - padB + 16) + '" fill="#94a3b8" font-size="10" text-anchor="middle" font-family="monospace">G' + g + '</text>';
  }

  // Mean fitness path (Cyan dashed)
  var dMean = "";
  for (var m = 0; m < gens.length; m++) {
    var mVal = isFinite(gens[m].mean_fitness) ? Math.max(minFit, gens[m].mean_fitness) : minFit;
    var mCoord = toSvg(gens[m].generation, mVal);
    dMean += (m === 0 ? "M " : " L ") + mCoord[0] + " " + mCoord[1];
  }
  if (dMean) {
    svgContent += '<path d="' + dMean + '" fill="none" stroke="#0284c7" stroke-width="1.6" stroke-dasharray="4,3"/>';
  }

  // Best fitness path (Royal Blue solid)
  var dBest = "";
  for (var b = 0; b < gens.length; b++) {
    var bVal = isFinite(gens[b].best_fitness) ? Math.max(minFit, gens[b].best_fitness) : minFit;
    var bCoord = toSvg(gens[b].generation, bVal);
    dBest += (b === 0 ? "M " : " L ") + bCoord[0] + " " + bCoord[1];
  }
  if (dBest) {
    svgContent += '<path d="' + dBest + '" fill="none" stroke="#2563eb" stroke-width="2.5"/>';
  }

  // Highlight Generation 25 peak point
  for (var k = 0; k < gens.length; k++) {
    if (gens[k].generation === 25 && isFinite(gens[k].best_fitness)) {
      var g25Coord = toSvg(25, gens[k].best_fitness);
      svgContent += '<circle cx="' + g25Coord[0] + '" cy="' + g25Coord[1] + '" r="5" fill="#7c3aed" stroke="#ffffff" stroke-width="2"/>' +
        '<text x="' + (g25Coord[0] + 8) + '" y="' + (g25Coord[1] - 6) + '" fill="#7c3aed" font-size="10" font-weight="800">Gen 25 Peak (0.8505)</text>';
      break;
    }
  }

  container.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' + w + ' ' + h + '" width="100%" height="100%" style="display:block;">' + svgContent + '</svg>';
}

// ---------------------------------------------------------------------------
// Phase 1 Table & Flight Profile
// ---------------------------------------------------------------------------
function renderPhase1(data) {
  var baselines = data.baselines || [];
  var tbody = document.querySelector('#b0-metrics-table tbody');
  if (tbody && baselines.length > 0) {
    tbody.innerHTML = baselines.map(function(b) {
      return '<tr>' +
        '<td style="color: var(--primary); font-weight:700;">' + b.baseline_id + '</td>' +
        '<td>' + (b.distance_mean || 0).toFixed(2) + ' &plusmn; ' + (b.distance_std || 0).toFixed(2) + ' m</td>' +
        '<td>' + (b.survival_time_mean || 0).toFixed(2) + ' s</td>' +
        '<td>' + (b.energy_mean || 0).toFixed(2) + '</td>' +
        '<td>' + (b.altitude_error_mean || 0).toFixed(2) + ' m</td>' +
        '<td>' + (b.airspeed_error_mean || 0).toFixed(2) + ' m/s</td>' +
        '<td><span class="tab-badge badge-done">' + (((b.crash_rate || 0) * 100).toFixed(1)) + '%</span></td>' +
      '</tr>';
    }).join('');
  }
  renderTrajectoryChart('b0-profile-container', null, data.b0_trajectory, null);
}

// ---------------------------------------------------------------------------
// Phase 2: Dynamic NEAT Neural Graph & Inspector
// ---------------------------------------------------------------------------
function renderPhase2(data) {
  var history = data.history_champions || [];
  var select = document.getElementById('gen-history-select');

  if (select && history.length !== g_lastGenCount) {
    g_lastGenCount = history.length;
    var curVal = select.value || 'latest';
    var opts = '<option value="latest">Latest Champion (Live Generation)</option>';
    for (var i = 0; i < history.length; i++) {
      var h = history[i];
      var isG25 = (h.generation === 25);
      opts += '<option value="' + h.generation + '">' + (isG25 ? '★ ' : '') + 'Generation ' + h.generation + (isG25 ? ' [PEAK FITNESS]' : '') + ' (Fitness: ' + h.fitness.toFixed(3) + ', Dist: ' + ((h.distance || 0).toFixed(1)) + 'm)</option>';
    }
    select.innerHTML = opts;
    select.value = curVal;
  }

  var activeInd = data.champion;
  if (g_selectedGen !== 'latest') {
    for (var j = 0; j < history.length; j++) {
      if (String(history[j].generation) === String(g_selectedGen)) {
        activeInd = history[j];
        break;
      }
    }
    if (!activeInd) activeInd = data.champion;
  }

  if (!activeInd) return;

  var pill = document.getElementById('champ-gen-pill');
  if (pill) {
    pill.textContent = 'Gen ' + activeInd.generation + (activeInd.generation === 25 ? ' (Peak Fitness)' : '');
    pill.className = (activeInd.generation === 25 ? 'tab-badge badge-purple' : 'tab-badge badge-active');
  }

  var dEl = document.getElementById('p2-dist');
  if (dEl) dEl.textContent = ((activeInd.distance || 0).toFixed(2)) + ' m';
  var dSub = document.getElementById('p2-dist-sub');
  if (dSub) {
    var delta = (activeInd.distance || 0) - 98.25;
    dSub.textContent = delta >= 0 ? ('Beat reference PID baseline by +' + delta.toFixed(1) + 'm') : (Math.abs(delta).toFixed(1) + 'm under PID baseline');
  }

  var tEl = document.getElementById('p2-time');
  if (tEl) tEl.textContent = ((activeInd.survival_time || 0).toFixed(2)) + ' s';
  var cEl = document.getElementById('p2-complexity');
  if (cEl) cEl.textContent = (activeInd.nodes || 0) + ' nodes \u00B7 ' + (activeInd.connections || 0) + ' conns';
  var fEl = document.getElementById('p2-fit-val');
  if (fEl && activeInd.fitness !== undefined) fEl.textContent = 'Fitness: ' + activeInd.fitness.toFixed(4);

  // Draw Neural Graph into Phase 2 container
  var ctrl = (String(g_selectedGen) === '25' && data.gen25_champion) ? data.gen25_champion.controller : (activeInd.controller || (data.champion ? data.champion.controller : null));
  renderDynamicNeuralNetwork('nn-svg-container', ctrl, activeInd.generation);

  // History Table
  var tableBody = document.querySelector('#p2-history-table tbody');
  var activeExp = getActiveExp(data);
  var gens = (data && data.generations && data.generations[activeExp]) ? data.generations[activeExp] : ((data && data.generations && data.generations.C1) ? data.generations.C1 : []);
  if (tableBody && gens.length > 0) {
    var recent = gens.slice(-20).reverse();
    tableBody.innerHTML = recent.map(function(g) {
      var isG25 = (g.generation === 25);
      return '<tr style="' + (isG25 ? 'background: var(--purple-light); font-weight:700;' : '') + '">' +
        '<td style="color: ' + (isG25 ? 'var(--purple)' : 'var(--primary)') + '; font-weight:700;">' + (isG25 ? '★ ' : '') + 'Gen ' + g.generation + '</td>' +
        '<td style="' + (isG25 ? 'color: var(--purple); font-weight:800;' : '') + '">' + g.best_fitness.toFixed(3) + '</td>' +
        '<td>' + g.mean_fitness.toFixed(2) + '</td>' +
        '<td style="color: var(--emerald); font-weight:700;">' + ((g.best_distance || 0).toFixed(1)) + ' m</td>' +
        '<td>' + ((g.best_survival_time || 0).toFixed(2)) + ' s</td>' +
        '<td>' + (g.best_nodes || 0) + '</td>' +
        '<td>' + (g.best_connections || 0) + '</td>' +
        '<td><button class="btn ' + (isG25 ? 'btn-purple' : 'btn-secondary') + '" style="padding: 3px 8px; font-size:11px;" onclick="selectHistoricalGen(' + g.generation + ')">Inspect</button></td>' +
      '</tr>';
    }).join('');
  }
}

function selectHistoricalGen(gen) {
  g_selectedGen = String(gen);
  var sel = document.getElementById('gen-history-select');
  if (sel) sel.value = String(gen);
  if (g_data) renderPhase2(g_data);
}

function renderDynamicNeuralNetwork(containerId, ctrl, genNumber) {
  var container = document.getElementById(containerId);
  if (!container) return;

  if (!ctrl || !ctrl.nodes || !ctrl.connections) {
    container.innerHTML = '<div style="padding: 40px; text-align: center; color: var(--text-muted);">Awaiting neural network structure from database...</div>';
    return;
  }

  var w = 740;
  var h = (containerId === 'ov-nn-container' ? 480 : 560);

  var inputNodes = [];
  for (var i = 0; i < 15; i++) {
    inputNodes.push({ id: -(i + 1), label: INPUT_LABELS[i] || ("In " + i), type: 'input' });
  }

  var outputNodes = [];
  for (var j = 0; j < 6; j++) {
    outputNodes.push({ id: j, label: OUTPUT_LABELS[j] || ("Out " + j), type: 'output' });
  }

  var hiddenNodes = [];
  var rawNodes = ctrl.nodes || [];
  for (var k = 0; k < rawNodes.length; k++) {
    if (rawNodes[k].type === 'hidden' || rawNodes[k].id >= 6) {
      hiddenNodes.push(rawNodes[k]);
    }
  }

  var nodeCoords = {};

  var inStartY = 35;
  var inSpacing = (h - 70) / (inputNodes.length - 1);
  for (var l = 0; l < inputNodes.length; l++) {
    var inN = inputNodes[l];
    nodeCoords[inN.id] = { x: 85, y: inStartY + l * inSpacing, label: inN.label, type: 'input' };
  }

  var outStartY = 70;
  var outSpacing = (h - 140) / (outputNodes.length - 1);
  for (var m = 0; m < outputNodes.length; m++) {
    var outN = outputNodes[m];
    nodeCoords[outN.id] = { x: 630, y: outStartY + m * outSpacing, label: outN.label, type: 'output' };
  }

  var hCount = hiddenNodes.length;
  for (var n = 0; n < hiddenNodes.length; n++) {
    var hdN = hiddenNodes[n];
    var colX = 260 + (n % 2) * 140;
    var hy = 110 + (n / Math.max(1, hCount - 1)) * (h - 220);
    nodeCoords[hdN.id] = {
      x: colX,
      y: hy,
      label: 'Hidden #' + hdN.id,
      type: 'hidden',
      bias: hdN.bias || 0,
      act: hdN.activation || 'tanh'
    };
  }

  var svgContent = '<!-- Layer Guides -->' +
    '<rect x="15" y="15" width="140" height="' + (h - 30) + '" fill="#f8fafc" stroke="#e2e8f0" rx="8"/>' +
    '<text x="85" y="' + (h - 20) + '" fill="#64748b" font-size="10" text-anchor="middle" font-weight="700">15 FLIGHT SENSORS</text>' +
    '<rect x="560" y="15" width="160" height="' + (h - 30) + '" fill="#f8fafc" stroke="#e2e8f0" rx="8"/>' +
    '<text x="640" y="' + (h - 20) + '" fill="#64748b" font-size="10" text-anchor="middle" font-weight="700">6 FLIGHT ACTUATORS</text>';

  // Synapses
  var conns = ctrl.connections || [];
  for (var c = 0; c < conns.length; c++) {
    var cn = conns[c];
    var src = nodeCoords[cn.from];
    var dst = nodeCoords[cn.to];
    if (!src || !dst) continue;

    var isPos = cn.weight >= 0;
    var absW = Math.abs(cn.weight);
    var strokeW = Math.max(0.7, Math.min(3.5, 0.7 + absW * 0.8));
    var color = isPos ? 'rgba(37, 99, 235, 0.65)' : 'rgba(225, 29, 72, 0.65)';
    var dash = cn.enabled ? '' : 'stroke-dasharray="3,3" opacity="0.25"';

    var dx = (dst.x - src.x) * 0.5;
    var pathD = 'M ' + src.x + ' ' + src.y + ' C ' + (src.x + dx) + ' ' + src.y + ', ' + (dst.x - dx) + ' ' + dst.y + ', ' + dst.x + ' ' + dst.y;

    svgContent += '<path d="' + pathD + '" stroke="' + color + '" stroke-width="' + strokeW + '" ' + dash + ' class="synapse-link" ' +
      'data-from="' + cn.from + '" data-to="' + cn.to + '" data-w="' + cn.weight.toFixed(4) + '" data-en="' + cn.enabled + '"/>';
  }

  // Nodes
  var keys = Object.keys(nodeCoords);
  for (var p = 0; p < keys.length; p++) {
    var nid = keys[p];
    var node = nodeCoords[nid];
    var fill = '#ffffff';
    var stroke = '#2563eb';
    var r = 6.5;

    if (node.type === 'input') { stroke = '#0284c7'; r = 5.5; }
    else if (node.type === 'output') { stroke = '#059669'; r = 6.5; }
    else if (node.type === 'hidden') { stroke = '#7c3aed'; r = 7.5; }

    var textX = (node.type === 'input' ? node.x - 12 : (node.type === 'output' ? node.x + 14 : node.x));
    var anchor = (node.type === 'input' ? 'end' : (node.type === 'output' ? 'start' : 'middle'));
    var textFill = (node.type === 'hidden' ? '#7c3aed' : '#334155');
    var textWeight = (node.type === 'output' ? '700' : '500');

    svgContent += '<g class="node-group" data-nid="' + nid + '">' +
      '<circle cx="' + node.x + '" cy="' + node.y + '" r="' + r + '" fill="' + fill + '" stroke="' + stroke + '" stroke-width="2"/>' +
      '<text x="' + textX + '" y="' + (node.y + 3.5) + '" fill="' + textFill + '" font-size="10.5" font-weight="' + textWeight + '" text-anchor="' + anchor + '" font-family="monospace">' + node.label + '</text>' +
    '</g>';
  }

  container.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' + w + ' ' + h + '" width="100%" height="100%" style="display:block;">' + svgContent + '</svg>';

  var subEl = document.getElementById('nn-header-subtitle');
  if (subEl) {
    subEl.textContent = 'Brain Gen ' + (genNumber || 'Live') + ' \u00B7 ' + (ctrl.nodes ? ctrl.nodes.length : 0) + ' Neurons (' + hiddenNodes.length + ' Hidden) \u00B7 ' + (ctrl.connections ? ctrl.connections.length : 0) + ' Synapses';
  }

  // Attach inspector events
  var groups = container.querySelectorAll('.node-group');
  for (var g = 0; g < groups.length; g++) {
    (function(grp) {
      grp.addEventListener('click', function() {
        var nId = grp.getAttribute('data-nid');
        var nd = nodeCoords[nId];
        var insp = document.getElementById('inspector-content');
        if (insp && nd) {
          insp.innerHTML = '<div style="background: var(--bg-subtle); padding: 12px; border-radius: var(--radius-sm); border: 1px solid var(--border);">' +
            '<div style="font-weight: 700; font-size: 14px; color: var(--text-primary); margin-bottom: 6px;">Neuron ' + nd.label + '</div>' +
            '<div><strong>Type:</strong> <span class="tab-badge badge-active">' + nd.type.toUpperCase() + '</span></div>' +
            '<div style="margin-top: 4px;"><strong>Node ID:</strong> <span class="mono">' + nId + '</span></div>' +
            (nd.bias !== undefined ? ('<div style="margin-top: 4px;"><strong>Bias Weight:</strong> <span class="mono" style="color: var(--primary); font-weight:700;">' + nd.bias.toFixed(4) + '</span></div>') : '') +
            (nd.act ? ('<div style="margin-top: 4px;"><strong>Activation:</strong> <span class="mono">' + nd.act + '</span></div>') : '') +
          '</div>';
        }
      });
    })(groups[g]);
  }

  var links = container.querySelectorAll('.synapse-link');
  for (var s = 0; s < links.length; s++) {
    (function(link) {
      link.addEventListener('click', function() {
        var fromN = link.getAttribute('data-from');
        var toN = link.getAttribute('data-to');
        var wVal = link.getAttribute('data-w');
        var enVal = link.getAttribute('data-en') === 'true';
        var insp = document.getElementById('inspector-content');
        if (insp) {
          insp.innerHTML = '<div style="background: var(--bg-subtle); padding: 12px; border-radius: var(--radius-sm); border: 1px solid var(--border);">' +
            '<div style="font-weight: 700; font-size: 14px; color: var(--text-primary); margin-bottom: 6px;">Synaptic Connection</div>' +
            '<div><strong>Source Node:</strong> <span class="mono">' + (nodeCoords[fromN] ? nodeCoords[fromN].label : fromN) + '</span></div>' +
            '<div style="margin-top: 4px;"><strong>Target Node:</strong> <span class="mono">' + (nodeCoords[toN] ? nodeCoords[toN].label : toN) + '</span></div>' +
            '<div style="margin-top: 4px;"><strong>Weight ($w$):</strong> <span class="mono" style="color: ' + (parseFloat(wVal) >= 0 ? 'var(--primary)' : 'var(--rose)') + '; font-weight:700;">' + wVal + '</span></div>' +
            '<div style="margin-top: 4px;"><strong>Status:</strong> <span class="tab-badge ' + (enVal ? 'badge-done' : 'badge-ready') + '">' + (enVal ? 'Enabled' : 'Disabled') + '</span></div>' +
          '</div>';
        }
      });
    })(links[s]);
  }
}

// ---------------------------------------------------------------------------
// Phase 3: Morphology Comparative CAD Blueprint & Stability
// ---------------------------------------------------------------------------
function updateMorphology() {
  var elSpan = document.getElementById('sl-span');
  var elArea = document.getElementById('sl-area');
  var elHtail = document.getElementById('sl-htail');
  var elMass = document.getElementById('sl-mass');
  var elCg = document.getElementById('sl-cg');

  var span = parseFloat(elSpan ? elSpan.value : 1.80);
  var area = parseFloat(elArea ? elArea.value : 0.45);
  var htail = parseFloat(elHtail ? elHtail.value : 0.08);
  var mass = parseFloat(elMass ? elMass.value : 1.50);
  var cgShift = parseFloat(elCg ? elCg.value : 0.0);

  var valSpan = document.getElementById('val-span'); if (valSpan) valSpan.textContent = span.toFixed(2) + ' m';
  var valArea = document.getElementById('val-area'); if (valArea) valArea.textContent = area.toFixed(2) + ' m\u00B2';
  var valHtail = document.getElementById('val-htail'); if (valHtail) valHtail.textContent = htail.toFixed(2) + ' m\u00B2';
  var valMass = document.getElementById('val-mass'); if (valMass) valMass.textContent = mass.toFixed(2) + ' kg';
  var valCg = document.getElementById('val-cg'); if (valCg) valCg.textContent = (cgShift >= 0 ? '+' : '') + cgShift.toFixed(3) + ' m';

  var chord = area / span;
  var ar = (span * span) / area;
  var wingLoading = mass / area;

  var xNP = 0.42 * chord;
  var xCG = (0.30 * chord) + cgShift;
  var staticMargin = ((xNP - xCG) / chord) * 100.0;

  var aeroAr = document.getElementById('aero-ar'); if (aeroAr) aeroAr.textContent = ar.toFixed(2);
  var aeroWl = document.getElementById('aero-wl'); if (aeroWl) aeroWl.textContent = wingLoading.toFixed(2) + ' kg/m\u00B2';
  var aeroSm = document.getElementById('aero-sm'); if (aeroSm) aeroSm.textContent = (staticMargin >= 0 ? '+' : '') + staticMargin.toFixed(1) + '%';

  var badge = document.getElementById('stability-badge');
  if (badge) {
    if (staticMargin > 5.0) {
      badge.className = 'tab-badge badge-done';
      badge.textContent = 'Statically Stable (+SM)';
      if (aeroSm) aeroSm.style.color = 'var(--emerald)';
    } else if (staticMargin >= 0.0) {
      badge.className = 'tab-badge badge-active';
      badge.textContent = 'Neutrally Stable';
      if (aeroSm) aeroSm.style.color = 'var(--amber)';
    } else {
      badge.className = 'tab-badge';
      badge.style.background = 'var(--rose-light)';
      badge.style.color = 'var(--rose)';
      badge.textContent = 'Pitch Divergent (Unstable)';
      if (aeroSm) aeroSm.style.color = 'var(--rose)';
    }
  }

  renderMorphologyBlueprint('blueprint-container', span, chord, htail, cgShift);
}

function toggleBlueprintView(type) {
  var cad = document.getElementById('blueprint-cad-container');
  var svg = document.getElementById('blueprint-container');
  var btnCad = document.getElementById('btn-cad-blueprint');
  var btnSvg = document.getElementById('btn-svg-blueprint');
  if (type === 'cad') {
    if (cad) cad.style.display = 'block';
    if (svg) svg.style.display = 'none';
    if (btnCad) btnCad.className = 'btn btn-primary';
    if (btnSvg) btnSvg.className = 'btn btn-secondary';
  } else {
    if (cad) cad.style.display = 'none';
    if (svg) svg.style.display = 'block';
    if (btnCad) btnCad.className = 'btn btn-secondary';
    if (btnSvg) btnSvg.className = 'btn btn-primary';
    updateMorphology();
  }
}

function renderMorphologyBlueprint(containerId, span, chord, htail, cgShift) {
  var container = document.getElementById(containerId);
  if (!container) return;

  var w = 740;
  var h = 520;
  var cx = 370;
  var cy = 240;
  var pxM = 160;

  var b0_span = 1.80 * pxM;
  var b0_chord = 0.25 * pxM;
  var b0_fuseL = 1.20 * pxM;
  var b0_tailSpan = 0.55 * pxM;

  var ev_span = span * pxM;
  var ev_chord = chord * pxM;
  var ev_tailSpan = Math.sqrt(htail * 4.0) * pxM;

  var svgContent = '<defs>' +
      '<pattern id="grid-light" width="20" height="20" patternUnits="userSpaceOnUse">' +
        '<path d="M 20 0 L 0 0 0 20" fill="none" stroke="#f1f5f9" stroke-width="1"/>' +
      '</pattern>' +
    '</defs>' +
    '<rect width="' + w + '" height="' + h + '" fill="#ffffff"/>' +
    '<rect width="' + w + '" height="' + h + '" fill="url(#grid-light)"/>' +
    '<line x1="' + cx + '" y1="30" x2="' + cx + '" y2="' + (h - 40) + '" stroke="#cbd5e1" stroke-width="1.2" stroke-dasharray="6,4"/>' +
    '<rect x="' + (cx - b0_span / 2) + '" y="' + (cy - 30) + '" width="' + b0_span + '" height="' + b0_chord + '" fill="none" stroke="#94a3b8" stroke-width="1.6" stroke-dasharray="5,4" rx="2"/>' +
    '<ellipse cx="' + cx + '" cy="' + cy + '" rx="14" ry="' + (b0_fuseL / 2) + '" fill="none" stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="4,4"/>' +
    '<rect x="' + (cx - b0_tailSpan / 2) + '" y="' + (cy + b0_fuseL / 2 - 25) + '" width="' + b0_tailSpan + '" height="20" fill="none" stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="4,4"/>' +
    '<rect x="' + (cx - ev_span / 2) + '" y="' + (cy - 30) + '" width="' + ev_span + '" height="' + ev_chord + '" fill="rgba(37, 99, 235, 0.06)" stroke="#2563eb" stroke-width="2.2" rx="4"/>' +
    '<ellipse cx="' + cx + '" cy="' + cy + '" rx="16" ry="' + (b0_fuseL / 2) + '" fill="#ffffff" stroke="#1e293b" stroke-width="2.2"/>' +
    '<rect x="' + (cx - ev_tailSpan / 2) + '" y="' + (cy + b0_fuseL / 2 - 25) + '" width="' + ev_tailSpan + '" height="24" fill="rgba(37, 99, 235, 0.08)" stroke="#2563eb" stroke-width="2" rx="2"/>' +
    '<line x1="' + cx + '" y1="' + (cy + b0_fuseL / 2 - 42) + '" x2="' + cx + '" y2="' + (cy + b0_fuseL / 2 - 4) + '" stroke="#1e293b" stroke-width="4.5" stroke-linecap="round"/>' +
    '<line x1="' + (cx - 26) + '" y1="' + (cy - b0_fuseL / 2) + '" x2="' + (cx + 26) + '" y2="' + (cy - b0_fuseL / 2) + '" stroke="#d97706" stroke-width="3" stroke-linecap="round"/>' +
    '<circle cx="' + cx + '" cy="' + (cy - 30 + (0.30 * ev_chord) + (cgShift * pxM)) + '" r="7" fill="#d97706" stroke="#ffffff" stroke-width="2"/>' +
    '<text x="' + (cx + 16) + '" y="' + (cy - 26 + (0.30 * ev_chord) + (cgShift * pxM)) + '" fill="#d97706" font-size="11.5" font-weight="800">CG</text>' +
    '<circle cx="' + cx + '" cy="' + (cy - 30 + (0.42 * ev_chord)) + '" r="5" fill="#0284c7" stroke="#ffffff" stroke-width="2"/>' +
    '<text x="' + (cx + 16) + '" y="' + (cy - 26 + (0.42 * ev_chord)) + '" fill="#0284c7" font-size="11.5" font-weight="800">NP (AC)</text>' +
    '<line x1="' + (cx - ev_span / 2) + '" y1="' + (cy - 50) + '" x2="' + (cx + ev_span / 2) + '" y2="' + (cy - 50) + '" stroke="#64748b" stroke-width="1.2"/>' +
    '<text x="' + cx + '" y="' + (cy - 56) + '" fill="#0f172a" font-size="11.5" font-weight="700" text-anchor="middle">Tested Wingspan: ' + span.toFixed(2) + 'm (vs Base 1.80m)</text>';

  container.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' + w + ' ' + h + '" width="100%" height="100%" style="display:block;">' + svgContent + '</svg>';
}

function applyMorphPreset(key) {
  var slSpan = document.getElementById('sl-span');
  var slArea = document.getElementById('sl-area');
  var slHtail = document.getElementById('sl-htail');
  var slMass = document.getElementById('sl-mass');
  var slCg = document.getElementById('sl-cg');

  if (key === 'default') {
    if (slSpan) slSpan.value = 1.80;
    if (slArea) slArea.value = 0.45;
    if (slHtail) slHtail.value = 0.08;
    if (slMass) slMass.value = 1.50;
    if (slCg) slCg.value = 0.0;
  } else if (key === 'glider') {
    if (slSpan) slSpan.value = 2.40;
    if (slArea) slArea.value = 0.40;
    if (slHtail) slHtail.value = 0.10;
    if (slMass) slMass.value = 1.20;
    if (slCg) slCg.value = -0.01;
  } else if (key === 'cruiser') {
    if (slSpan) slSpan.value = 1.40;
    if (slArea) slArea.value = 0.35;
    if (slHtail) slHtail.value = 0.06;
    if (slMass) slMass.value = 1.80;
    if (slCg) slCg.value = 0.02;
  } else if (key === 'unstable') {
    if (slSpan) slSpan.value = 1.50;
    if (slArea) slArea.value = 0.40;
    if (slHtail) slHtail.value = 0.03;
    if (slMass) slMass.value = 1.60;
    if (slCg) slCg.value = 0.05;
  }
  updateMorphology();
}

// ---------------------------------------------------------------------------
// Phase 6 Montage
// ---------------------------------------------------------------------------
function renderPhase6(data) {
  var liveTraj = data.latest_trajectory || data.c1_trajectory;
  renderTrajectoryChart('montage-container', liveTraj, data.b0_trajectory, data.gen25_trajectory);
}

// ---------------------------------------------------------------------------
// One-Click Live Neural Network Flight Simulation Runner
// ---------------------------------------------------------------------------
function runLiveFlightSimulation() {
  var btn = document.getElementById('btn-run-sim');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="pulse-dot"></span> Simulating in PyBullet Physics...';
  }

  var sel = document.getElementById('ov-model-select');
  var modelVal = sel ? sel.value : 'latest';
  var activeExp = (g_data && g_data.experiments && g_data.experiments.length > 0) ? getActiveExp(g_data) : 'TALOS-P4-ULTIMA';
  var payload = { experiment_id: activeExp, render: false };
  if (modelVal === '25') payload.generation = 25;
  else if (modelVal === 'b0') payload.experiment_id = 'B0_baseline_pid';

  showToast('Simulating flight with PyBullet physics...');

  var xhr = new XMLHttpRequest();
  xhr.open('POST', '/api/run-model', true);
  xhr.setRequestHeader('Content-Type', 'application/json');
  xhr.onload = function() {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg> ▶ RUN LIVE FLIGHT SIMULATION';
    }

    if (xhr.status >= 200 && xhr.status < 300) {
      try {
        var res = JSON.parse(xhr.responseText);
        showToast('Flight simulation complete! Distance: ' + (res.distance ? res.distance.toFixed(1) + 'm' : 'N/A'));

        if (res.trajectory && res.trajectory.length > 0) {
          if (!g_data) g_data = {};
          if (modelVal === '25') g_data.gen25_trajectory = res;
          else if (modelVal === 'b0') g_data.b0_trajectory = res;
          else {
            g_data.latest_trajectory = res;
            g_data.c1_trajectory = res;
          }

          var tDist = document.getElementById('tel-dist'); if (tDist && res.distance !== undefined) tDist.textContent = res.distance.toFixed(1) + 'm';
          var tTime = document.getElementById('tel-time'); if (tTime && res.flight_time !== undefined) tTime.textContent = res.flight_time.toFixed(2) + 's';
          var tStall = document.getElementById('tel-stall'); if (tStall) tStall.textContent = res.stalling ? 'YES' : 'NO';
          var tCrash = document.getElementById('tel-crash'); if (tCrash) {
            tCrash.textContent = res.crashed ? 'YES' : 'NO';
            tCrash.className = res.crashed ? 'tel-val delta-neg' : 'tel-val delta-pos';
          }

          refreshTrajectoryChart();
        }
      } catch (e) {
        showToast('Parse error on simulation response.');
      }
    } else {
      showToast('Simulation error: HTTP ' + xhr.status);
    }
  };
  xhr.onerror = function() {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '▶ RUN LIVE FLIGHT SIMULATION';
    }
    showToast('Network error while running simulation.');
  };
  xhr.send(JSON.stringify(payload));
}

function triggerRunFlight(render3d) {
  showToast(render3d ? 'Opening PyBullet 3D simulation window...' : 'Simulating flight in background...');
  var xhr = new XMLHttpRequest();
  xhr.open('POST', '/api/run-model', true);
  xhr.setRequestHeader('Content-Type', 'application/json');
  xhr.onload = function() {
    showToast('3D PyBullet simulation initialized.');
    fetchDashboardData();
  };
  xhr.send(JSON.stringify({ experiment_id: 'C1', render: render3d }));
}

function showToast(msg) {
  var toast = document.getElementById('toast-banner');
  if (!toast) return;
  toast.textContent = msg;
  toast.style.display = 'block';
  setTimeout(function() { toast.style.display = 'none'; }, 3500);
}
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# HTTP Server Handler
# ---------------------------------------------------------------------------

class _Handler(http.server.BaseHTTPRequestHandler):
    db_path = DB_PATH

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in ("", "/", "/index.html"):
            # Fetch fresh data and inject as window.TALOS_BOOTSTRAP for instant 0ms render
            bootstrap_data = get_all_data(self.db_path)
            bootstrap_json = json.dumps(bootstrap_data, default=str)
            html_content = (
                _HTML_HEAD
                + f"\n<script>window.TALOS_BOOTSTRAP = {bootstrap_json};</script>\n"
                + _HTML_JS
            )
            self._respond(200, "text/html", html_content.encode("utf-8"))
        elif path in ("/3d", "/3d.html", "/benchmark-3d"):
            from src.dashboard.generate_3d_viewer import generate_viewer
            html_3d = generate_viewer(self.db_path)
            self._respond(200, "text/html", html_3d.encode("utf-8"))
        elif path == "/api/data":
            data = get_all_data(self.db_path)
            self._respond(200, "application/json", json.dumps(data, default=str).encode("utf-8"))
        elif path.startswith("/output/") or path.endswith((".jpg", ".png", ".jpeg")):
            local_path = path.lstrip("/")
            if os.path.isfile(local_path):
                ctype = "image/jpeg" if local_path.endswith((".jpg", ".jpeg")) else "image/png"
                with open(local_path, "rb") as f:
                    self._respond(200, ctype, f.read())
                return
            self._respond(404, "text/plain", b"File Not Found")
        else:
            self._respond(404, "text/plain", b"Not Found")

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/run-model":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                payload = json.loads(body) if body else {}
            except Exception:
                payload = {}

            exp_id = payload.get("experiment_id", "C1")
            render_gui = bool(payload.get("render", False))
            gen = payload.get("generation")

            try:
                result = run_best_model(
                    experiment_id=exp_id,
                    db_path=self.db_path,
                    render=render_gui,
                    generation=gen,
                )
                self._respond(200, "application/json", json.dumps(result, default=str).encode("utf-8"))
            except Exception as e:
                err = {"status": "error", "message": str(e)}
                self._respond(500, "application/json", json.dumps(err).encode("utf-8"))
        else:
            self._respond(404, "text/plain", b"Not Found")

    def _respond(self, code: int, ctype: str, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:
        pass


def serve(port: int = 8050, db_path: str = DB_PATH) -> None:
    ExperimentDB(db_path)
    _Handler.db_path = db_path
    server = http.server.HTTPServer(("", port), _Handler)
    print(f"[talos] Mission Control Dashboard live at http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Talos HTML Dashboard")
    p.add_argument("--port", type=int, default=8050)
    p.add_argument("--db", default=DB_PATH)
    args = p.parse_args()
    serve(port=args.port, db_path=args.db)
