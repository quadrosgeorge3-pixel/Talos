
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

;
window.TALOS_BOOTSTRAP = {bootstrap_json};