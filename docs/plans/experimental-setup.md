# Experimental Setup Plan: Evolutionary Co-Design of Powered Aircraft
## Focus: Infrastructure & Visual Dashboard (Pre-Experiment Phase)

This plan covers ONLY the experimental setup phase and visual dashboard — NOT the actual evolutionary experiments. It provides the foundation for running experiments: project structure, dependencies, simulation environment, baseline confirmation, data logging, and a live visual dashboard to monitor NEAT model status and experiment progress.

---

## 1. Project Structure (Setup Phase Only)
```
C:\Users\hp\Desktop\Talos\
├── project-spec-evolved-aircraft.md   # existing spec (reference)
├── project-setup-evolved-aircraft.md  # THIS FILE (setup phase plan)
├── requirements.txt
├── run.py                             # CLI entry point (setup & experiment modes)
│
├── src/
│   ├── genome/
│   │   ├── __init__.py
│   │   ├── morphology.py              # Morphology genome encoding/decoding/mutation
│   │   ├── controller.py              # NEAT wrapper (thin, delegates to neat-python)
│   │   └── urdf_gen.py               # URDF + YAML generation from morphology params
│   │
│   ├── simulation/
│   │   ├── __init__.py
│   │   ├── env.py                     # PyFlyt Fixedwing wrapper (Gymnasium-like API)
│   │   ├── evaluator.py               # Fitness evaluation (single individual)
│   │   └── pool.py                    # Multiprocessing env pool (stub for setup)
│   │
│   ├── evolution/
│   │   ├── __init__.py
│   │   ├── loop.py                    # Main evolution loop (stub for setup)
│   │   └── pruning.py                 # Network pruning (stub)
│   │
│   ├── experiment/
│   │   ├── __init__.py
│   │   ├── runner.py                  # Orchestrates one full experiment (stub)
│   │   ├── db.py                      # SQLite schema + read/write (core for setup)
│   │   ├── metadata.py                # Immutable experiment metadata
│   │   └── export.py                  # SQLite → JSON/CSV export (stub)
│   │
│   ├── dashboard/                     # NEW: Visual dashboard module
│   │   ├── __init__.py
│   │   ├── __main__.py               # Dashboard entry point
│   │   ├── viz.py                     # Visualization components (matplotlib/pyqtgraph)
│   │   ├── genome_viz.py              # NEAT genome rendering
│   │   └── layout.py                  # Dashboard layout & components
│   │
│   └── analysis/                      # Stubs for future use
│       ├── __init__.py
│       ├── plots.py                   # Auto-generate matplotlib figures
│       └── comparison.py              # Cross-experiment comparison tables
│
├── configs/                           # Experiment configs (version-controlled)
│   ├── baselines/
│   │   └── b0_default_pid.json
│   ├── controller_only/
│   │   ├── c1_neat_fixed.json
│   │   └── c2_neat_multiseed.json
│   ├── morphology_only/
│   │   ├── m1_fixed_ctrl.json
│   │   └── m2_multiseed.json
│   ├── coevolution/
│   │   ├── e1_balanced.json
│   │   ├── e2_survival_heavy.json
│   │   ├── e3_efficiency_heavy.json
│   │   └── e4_multiseed.json
│   ├── pruning/
│   │   ├── p1_default_threshold.json
│   │   └── p2_threshold_sweep.json
│   └── ablation/
│       ├── a1_no_morph_evolution.json
│       ├── a2_no_controller_evolution.json
│       ├── a3_no_pruning.json
│       ├── a4_fitness_weight_variants.json
│       └── a5_morphology_param_sets.json
│
├── output/                            # Experiment outputs (gitignored)
│   └── <experiment_id>/               # Will be created during experiments
│       ├── metadata.json
│       ├── config.json
│       ├── experiment.db              # SQLite database
│       ├── elites/                    # Periodic elite genome snapshots
│       ├── plots/                     # Auto-generated plots
│       └── export/                    # JSON/CSV exports
│
├── models/                            # Generated URDF/YAML (gitignored, temp)
│
└── tests/                             # Unit tests (stubs for setup phase)
    ├── test_morphology.py
    ├── test_urdf_gen.py
    ├── test_simulation.py
    ├── test_evaluator.py
    └── test_experiment.py
```

> **Note**: During setup phase, only core modules (`src/simulation/`, `src/experiment/`, `src/dashboard/`) are implemented. Evolution-specific modules (`src/evolution/`, `src/genome/` beyond basics) are stubbed.

---

## 2. Dependencies & Setup Order
```
# requirements.txt (core for setup)
pyflyt>=0.29.0
neat-python>=0.92
numpy>=1.24
pyyaml>=6.0
matplotlib>=3.7
tqdm>=4.65
pyqt5>=5.15  # Optional: for enhanced dashboard (fallback to matplotlib if missing)
```

**Installation Sequence** (critical for PyBullet/PyFlyt):
1. `pip install wheel numpy`  # First: ensures PyBullet builds with numpy support
2. `pip install -r requirements.txt`
3. Verify installation: `python -c "import pyflyt; import neat; print('OK')"`

**Development Mode Flags** (for faster iteration during setup):
- `simulation.episode_duration`: 10s (vs 30s final)
- `simulation.num_episodes_per_eval`: 1 (vs 3 final)
- Dashboard refresh rate: 2 FPS (vs 10+ during experiments)

---

## 3. Simulation Environment (`src/simulation/env.py`)
**Design Goals**: Wrap PyFlyt's `Fixedwing-Waypoints-v3` with clean Gymnasium-like API, support custom URDF/YAML injection.

```python
class FixedwingEnv:
    def __init__(self, model_dir, drone_model="default", config=None):
        """
        Args:
            model_dir: Path to directory containing custom drone.urdf + drone.yaml
                      If None, uses PyFlyt's default fixedwing model
            drone_model: Basename of model files (without .urdf/.yaml)
            config: Experiment config dict (for episode duration, control Hz, etc.)
        """
        # Store config for step/reset
        self.config = config or {}
        
        # Build absolute paths to model files
        if model_dir is None:
            self.urdf_path = None  # Use PyFlyt's built-in
            self.yaml_path = None
        else:
            self.urdf_path = os.path.join(model_dir, f"{drone_model}.urdf")
            self.yaml_path = os.path.join(model_dir, f"{drone_model}.yaml")
            assert os.path.exists(self.urdf_path), f"URDF not found: {self.urdf_path}"
            assert os.path.exists(self.yaml_path), f"YAML not found: {self.yaml_path}"
        
        # Initialize PyFlyt environment (headless/DIRECT mode during setup)
        self.env = gym.make(
            "PyFlyt/Fixedwing-Waypoints-v3",
            render_mode=None,  # Headless during setup/experiments
            urdf=self.urdf_path,
            yaml=self.yaml_path,
        )
        
        # Validate observation/action spaces
        assert self.env.observation_space.shape == (12,)  # [ang_vel, ang_pos, lin_vel, lin_pos]
        assert self.env.action_space.shape == (6,)        # [aileron_L, aileron_R, h_tail, v_tail, main_wing, thrust]
        
        # Waypoint management (for navigation task)
        self.waypoint_index = 0
        self.waypoints = self._load_waypoints()  # Simple square pattern for now
        
    def reset(self, seed=None, options=None):
        """Reset environment, return initial observation (12 floats)"""
        obs, info = self.env.reset(seed=seed)
        self.waypoint_index = 0  # Reset to first waypoint
        return self._augment_observation(obs), info
    
    def step(self, action):
        """
        Args:
            action: 6 floats [aileron_L, aileron_R, h_tail, v_tail, main_wing, thrust] in [-1, 1]
        
        Returns:
            obs: augmented observation (15 floats) + waypoint offset
            reward: shaped reward signal
            terminated: bool (crashed/stalled/timeout)
            truncated: bool (time limit)
            info: dict with flight metrics
        """
        # Step PyFlyt environment
        obs, reward, terminated, truncated, info = self.env.step(action)
        
        # Augment observation with waypoint offset in body frame (3 floats)
        waypoint_offset = self._get_waypoint_offset()
        augmented_obs = np.concatenate([obs, waypoint_offset])  # 12 + 3 = 15
        
        # Extract flight metrics from info
        flight_metrics = self._extract_flight_metrics(info)
        
        return augmented_obs, reward, terminated, truncated, {**info, **flight_metrics}
    
    def get_metrics(self):
        """Return current flight metrics dict"""
        return self._extract_flight_metrics(self.env.get_attr("info")[0])
    
    # Helper methods: _load_waypoints, _get_waypoint_offset, _extract_flight_metrics
```

**Verification Criterion**: 
- Create env with `model_dir=None` (default PyFlyt model)
- Run `reset()` → `step([0,0,0,0,0,0.5])` for 10 steps
- Confirm observation shape is (15,) and info contains expected metrics

---

## 4. Baseline Confirmation (`src/simulation/evaluator.py` + `run.py --baseline`)
**Goal**: Establish reference performance using PyFlyt's built-in PID controller.

### Baseline Experiment Configuration (`configs/baselines/b0_default_pid.json`):
```json
{
    "experiment_id": "B0_baseline_pid",
    "experiment_type": "baseline",
    "description": "PyFlyt built-in PID controller on default airframe",
    "random_seed": 42,
    "num_seeds": 1,
    
    "population_size": 1,  # Not used for baseline
    "num_generations": 1,  # Single evaluation
    
    "simulation": {
        "episode_duration": 10.0,     // Dev mode: shorter for quick feedback
        "timestep": 0.005,
        "control_hz": 120,
        "physics_hz": 240,
        "render_mode": null,
        "num_episodes_per_eval": 3    // Average over 3 episodes for stability
    },
    
    "controller": {
        "mode": 0,                    // 0 = PyFlyt built-in PID (not NEAT)
        "num_inputs": 15,
        "num_outputs": 6,
        "placeholder": true           // Flag to bypass NEAT
    },
    
    "morphology": {
        "enabled": false              // Use default airframe only
    },
    
    "fitness": {
        "weights": {
            "survival": 0.4,
            "efficiency": 0.3,
            "maneuverability": 0.3
        },
        "penalties": {
            "crash": -100.0,
            "stall": -5.0,
            "altitude_exceeded": -2.0
        }
    }
}
```

### Baseline Runner (`run.py --baseline`):
```python
def run_baseline(config_path, episodes=10):
    """Run PyFlyt's default PID controller, aggregate metrics"""
    config = load_json(config_path)
    
    # Override episode count for baseline collection
    config["simulation"]["num_episodes_per_eval"] = episodes
    
    all_metrics = []
    for seed in range(config["num_seeds"]):
        config["random_seed"] = config.get("base_seed", 42) + seed
        
        # Create environment with default model (no custom URDF/YAML)
        env = FixedwingEnv(model_dir=None, config=config)
        
        # Run multiple episodes
        for ep in range(episodes):
            obs, info = env.reset(seed=config["random_seed"] + ep)
            done = False
            episode_metrics = []
            
            while not done:
                # Use PyFlyt's built-in PID controller (action from env)
                action = env.env.controller(obs[:12])  # First 12 obs are state
                obs, reward, terminated, truncated, info = env.step(action)
                done = terminated or truncated
                episode_metrics.append(info)
            
            # Aggregate episode metrics
            ep_summary = {
                "survival_time": np.mean([m["flight_time"] for m in episode_metrics]),
                "distance": np.sum([m["airspeed"] * m["dt"] for m in episode_metrics]),
                "energy": np.sum([m["throttle"]**2 * m["dt"] for m in episode_metrics]),
                "waypoint_time": np.mean([m["waypoint_distance"] for m in episode_metrics]),
                "altitude_error": np.mean([m["altitude_error"] for m in episode_metrics]),
                "airspeed_error": np.mean([m["airspeed_error"] for m in episode_metrics]),
                "crashed": any(m["crashed"] for m in episode_metrics),
                "stalling": any(m["stalling"] for m in episode_metrics)
            }
            all_metrics.append(ep_summary)
    
    # Compute baseline statistics (mean ± std across seeds/episodes)
    baseline_stats = {}
    for key in ["survival_time", "distance", "energy", "waypoint_time", 
                "altitude_error", "airspeed_error"]:
        vals = [m[key] for m in all_metrics]
        baseline_stats[key] = {
            "mean": np.mean(vals),
            "std": np.std(vals),
            "min": np.min(vals),
            "max": np.max(vals)
        }
    baseline_stats["crash_rate"] = np.mean([m["crashed"] for m in all_metrics])
    baseline_stats["stall_rate"] = np.mean([m["stalling"] for m in all_metrics])
    
    return baseline_stats
```

**Verification Criterion**:
- Run `python run.py --baseline --config configs/baselines/b0_default_pid.json --episodes 5`
- Output should show survival time > 25s (default PyFlyt model is stable)
- Store baseline metrics in SQLite for dashboard comparison

---

## 5. NEAT Configuration & Genome Inspection (`src/genome/controller.py`)
**Design**: Thin wrapper around `neat-python` with config building and genome introspection.

```python
class NEATController:
    def __init__(self, neat_config_path=None, config_dict=None):
        """
        Build NEAT config from either:
        - Path to neat-python config file, OR
        - Experiment JSON config dict (preferred for consistency)
        """
        if config_dict is not None:
            self.config = self._build_neat_config_from_dict(config_dict)
        else:
            self.config = neat.Config(
                neat.DefaultGenome, neat.DefaultReproduction,
                neat.DefaultSpeciesSet, neat.DefaultStagnation,
                neat_config_path
            )
        
        self.population = neat.Population(self.config)
        self.population.add_reporter(neat.StdOutReporter(True))
        self.stats = neat.StatisticsReporter()
        self.population.add_reporter(self.stats)
    
    def _build_neat_config_from_dict(self, exp_config):
        """Convert experiment JSON config to neat-python Config object"""
        neat_cfg = neat.Config(
            neat.DefaultGenome, neat.DefaultReproduction,
            neat.DefaultSpeciesSet, neat.DefaultStagnation,
            None,  # No config file - we'll set attributes directly
        )
        
        # Set population size
        neat_cfg.pop_size = exp_config["neat_config"]["pop_size"]
        
        # Set genome parameters
        neat_cfg.genome_config.num_inputs = exp_config["controller"]["num_inputs"]
        neat_cfg.genome_config.num_outputs = exp_config["controller"]["num_outputs"]
        
        neat_cfg.genome_config.activation_default = exp_config["controller"]["activation"]
        neat_cfg.genome_config.activation_mutate_rate = 0.0  # Fixed activation for now
        neat_cfg.genome_config.output_activation_default = exp_config["controller"]["output_activation"]
        
        neat_cfg.genome_config.weight_init_mean = 0.0
        neat_cfg.genome_config.weight_init_stdev = exp_config["neat_config"]["weight_init_std"]
        neat_cfg.genome_config.weight_max_value = exp_config["neat_config"]["weight_max"]
        neat_cfg.genome_config.weight_mutate_rate = exp_config["neat_config"]["weight_mutate_rate"]
        neat_cfg.genome_config.weight_replace_rate = exp_config["neat_config"]["weight_replace_rate"]
        
        neat_cfg.genome_config.bias_init_mean = 0.0
        neat_cfg.genome_config.bias_init_stdev = exp_config["neat_config"]["weight_init_std"]
        neat_cfg.genome_config.bias_max_value = exp_config["neat_config"]["bias_max"]
        neat_cfg.genome_config.bias_mutate_rate = exp_config["neat_config"]["bias_mutate_rate"]
        neat_cfg.genome_config.bias_replace_rate = 0.1
        
        neat_cfg.genome_config.compatibility_threshold = exp_config["neat_config"]["compatibility_threshold"]
        neat_cfg.genome_config.conn_add_prob = exp_config["neat_config"]["conn_add_prob"]
        neat_cfg.genome_config.conn_delete_prob = exp_config["neat_config"]["conn_delete_prob"]
        neat_cfg.genome_config.node_add_prob = exp_config["neat_config"]["node_add_prob"]
        neat_cfg.genome_config.node_delete_prob = exp_config["neat_config"]["node_delete_prob"]
        
        # Fitness settings
        neat_cfg.fitness_criterion = exp_config["neat_config"]["fitness_criterion"]
        neat_cfg.fitness_threshold = exp_config.get("fitness_threshold", 100.0)
        
        return neat_cfg
    
    def get_genome_summary(self, genome_id=None):
        """
        Return compact summary of a genome for dashboard display.
        If genome_id=None, returns best genome from current population.
        """
        if genome_id is None:
            genome = self.population.best_genome
        else:
            genome = self.population.population[genome_id]
        
        # Count active/enabled connections and nodes
        enabled_connections = [c for c in genome.connections.values() if c.enabled]
        active_nodes = set()
        for conn in enabled_connections:
            active_nodes.add(conn.key[0])  # input node
            active_nodes.add(conn.key[1])  # output node
        
        return {
            "id": genome.key,
            "fitness": genome.fitness,
            "nodes_total": len(genome.nodes),
            "nodes_active": len(active_nodes),
            "connections_total": len(genome.connections),
            "connections_enabled": len(enabled_connections),
            "species_id": genome.species_id if hasattr(genome, 'species_id') else -1,
            "is_extinct": genome.fitness < 0,  # Simple extinction heuristic
            "node_ids": sorted(list(active_nodes)),
            "connection_weights": {k: c.weight for k, c in genome.connections.items() if c.enabled}
        }
```

**Verification Criterion**:
- Build NEAT config from `configs/controller_only/c1_neat_fixed.json`
- Create population, call `get_genome_summary()`
- Confirm return dict has expected keys and sane values (fitness=None initially, 0 connections)

---

## 6. Data Logging Infrastructure (`src/experiment/db.py`)
**Schema for Setup Phase**: Focus on experiment metadata, baseline storage, and generation stub.

```sql
-- experiment_metadata: Immutable config + outcome
CREATE TABLE IF NOT EXISTS experiment_metadata (
    experiment_id TEXT PRIMARY KEY,
    config_json TEXT NOT NULL,          // Full experiment config
    start_time TEXT NOT NULL,
    end_time TEXT,
    status TEXT DEFAULT 'running',      // running, completed, failed
    baseline_survival REAL,             // From B0 baseline
    baseline_distance REAL,
    best_fitness REAL,                  // Updated during evolution
    best_generation INTEGER
);

-- baseline_metrics: Reference performance from PyFlyt PID
CREATE TABLE IF NOT EXISTS baseline_metrics (
    baseline_id TEXT PRIMARY KEY,       // e.g., "B0_default_pid"
    experiment_id TEXT NOT NULL,        // Which experiment this baseline belongs to
    survival_time_mean REAL,
    survival_time_std REAL,
    distance_mean REAL,
    distance_std REAL,
    energy_mean REAL,
    energy_std REAL,
    waypoint_time_mean REAL,
    waypoint_time_std REAL,
    altitude_error_mean REAL,
    altitude_error_std REAL,
    airspeed_error_mean REAL,
    airspeed_error_std REAL,
    crash_rate REAL,
    stall_rate REAL,
    measured_at TEXT NOT NULL,
    FOREIGN KEY (experiment_id) REFERENCES experiment_metadata(experiment_id)
);

-- generations: Per-generation statistics (stubbed during setup)
CREATE TABLE IF NOT EXISTS generations (
    generation INTEGER PRIMARY KEY,
    best_fitness REAL NOT NULL,
    mean_fitness REAL NOT NULL,
    median_fitness REAL NOT NULL,
    worst_fitness REAL NOT NULL,
    std_fitness REAL NOT NULL,
    best_nodes INTEGER,
    best_connections INTEGER,
    mean_nodes REAL,
    mean_connections REAL,
    species_count INTEGER,
    population_alive INTEGER,
    best_survival_time REAL,
    best_distance REAL,
    best_energy REAL,
    best_waypoint_time REAL
);

-- individuals: Individual genomes (minimal during setup)
CREATE TABLE IF NOT EXISTS individuals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generation INTEGER NOT NULL,
    individual_index INTEGER NOT NULL,
    fitness REAL NOT NULL,
    is_elite INTEGER DEFAULT 0,
    survival_time REAL,
    distance REAL,
    energy REAL,
    waypoint_time REAL,
    altitude_error REAL,
    airspeed_error REAL,
    crashed INTEGER,
    stalling INTEGER,
    nodes INTEGER,
    connections INTEGER,
    species_id INTEGER,
    morphology_json TEXT,    // JSON blob of morphology params
    controller_json TEXT,    // NEAT genome serialization
    FOREIGN KEY (generation) REFERENCES generations(generation)
);

-- Indexes for setup queries
CREATE INDEX IF NOT EXISTS idx_exp_status ON experiment_metadata(status);
CREATE INDEX IF NOT EXISTS idx_baseline_exp ON baseline_metrics(experiment_id);
CREATE INDEX IF NOT EXISTS idx_ind_gen ON individuals(generation);
```

**Key Functions**:
- `ExperimentDB.init_db()`: Create tables if not exist
- `ExperimentDB.save_experiment_metadata()`: Store config + track status
- `ExperimentDB.save_baseline()`: Store results from baseline run
- `ExperimentDB.get_latest_baseline()`: Retrieve baseline for dashboard comparison
- `ExperimentDB.log_generation_stub()`: Placeholder for future evolution logging

**Verification Criterion**:
- Initialize DB, save baseline from B0 run
- Query baseline metrics and confirm they match evaluator output
- Confirm experiment metadata tracks status correctly

---

## 7. Visual Dashboard (`src/dashboard/`)
**Design Philosophy**: Dark terminal/cockpit aesthetic with live-updating panels. Uses matplotlib for core visualization with optional PyQt5 enhancements. Updates every 0.5 seconds during setup/experiments.

### Dashboard Module Structure:
```
src/dashboard/
├── __init__.py
├── __main__.py          # Entry point: python -m src.dashboard
├── viz.py               # Core visualization utilities (matplotlib)
├── genome_viz.py        # NEAT genome rendering (nodes/connections)
├── layout.py            # Panel layout and composition
└── themes.py            # Dark color schemes, ASCII art assets
```

### Core Dashboard Class (`dashboard.py` concept):
```python
class EvolutionDashboard:
    def __init__(self, experiment_id=None, update_interval=0.5):
        """
        Args:
            experiment_id: If provided, load live data from this experiment
                          If None, show baseline-only mode (setup phase)
            update_interval: Seconds between UI refreshes
        """
        self.experiment_id = experiment_id
        self.update_interval = update_interval
        self.db = ExperimentDB()
        
        # Load baseline data (always available)
        self.baseline = self.db.get_latest_baseline(experiment_id) if experiment_id else self.db.get_baseline_by_id("B0_default_pid")
        
        # Initialize matplotlib figure with dark theme
        self.fig, self.axes = plt.subplots(2, 3, figsize=(16, 9))
        self.fig.patch.set_facecolor('#0a0a0a')  # Nearly black
        plt.style.use('dark_background')
        
        # Configure subplots (see layout below)
        self._setup_layout()
        
        # Animation object for live updates
        self.ani = None
        self.is_running = False
    
    def _setup_layout(self):
        """Define the 2x3 grid of panels"""
        # Row 0: [NEAT Genome] [NEAT Stats] [Experiment Status]
        # Row 1: [Morphology]   [Baseline Comparison] [Fitness Curve]
        
        # Panel 0,0: NEAT Genome Visualization
        self.ax_genome = self.axes[0, 0]
        self.ax_genome.set_title("NEAT GENOME", color='#00ff88', fontweight='bold')
        self.ax_genome.set_axis_off()
        
        # Panel 0,1: NEAT Statistics
        self.ax_stats = self.axes[0, 1]
        self.ax_stats.set_title("NETWORK STATS", color='#00ff88', fontweight='bold')
        self.ax_stats.set_axis_off()
        
        # Panel 0,2: Experiment Status
        self.ax_status = self.axes[0, 2]
        self.ax_status.set_title("EXPERIMENT STATUS", color='#00ff88', fontweight='bold')
        self.ax_status.set_axis_off()
        
        # Panel 1,0: Morphology Parameters
        self.ax_morph = self.axes[1, 0]
        self.ax_morph.set_title("AIRFRAME PARAMS", color='#00ff88', fontweight='bold')
        self.ax_morph.set_axis_off()
        
        # Panel 1,1: Baseline Comparison
        self.ax_baseline = self.axes[1, 1]
        self.ax_baseline.set_title("BASELINE VS CURRENT", color='#00ff88', fontweight='bold')
        self.ax_baseline.set_axis_off()
        
        # Panel 1,2: Fitness Curve (live)
        self.ax_fitness = self.axes[1, 2]
        self.ax_fitness.set_title("FITNESS PROGRESSION", color='#00ff88', fontweight='bold')
        self.ax_fitness.set_xlabel("Generation")
        self.ax_fitness.set_ylabel("Fitness")
        self.ax_fitness.grid(True, alpha=0.2)
    
    def update(self, frame):
        """Called by matplotlib animation - refresh all panels"""
        if not self.is_running:
            return
        
        # Fetch latest data (from DB if experiment running, else baseline-only)
        if self.experiment_id:
            latest_gen = self.db.get_latest_generation(self.experiment_id)
            current_best = self.db.get_best_individual(self.experiment_id, latest_gen) if latest_gen else None
        else:
            latest_gen = None
            current_best = None
        
        # Clear and redraw all panels
        for ax in self.axes.flat:
            ax.clear()
        
        self._setup_layout()  # Reset titles/axes after clear
        
        # --- PANEL 0,0: NEAT GENOME VISUALIZATION ---
        if current_best:
            genome_viz = GenomeVisualizer(self.ax_genome)
            genome_viz.draw_genome(current_best.controller_genome)
        else:
            # Show placeholder: minimal NEAT network (inputs -> outputs)
            self.ax_genome.text(0.5, 0.5, "NO GENOME DATA\n(Setup Phase)", 
                               ha='center', va='center', color='#666666', 
                               transform=self.ax_genome.transAxes, fontsize=10)
            self._draw_placeholder_genome(self.ax_genome)
        
        # --- PANEL 0,1: NEAT STATISTICS ---
        if self.experiment_id and latest_gen is not None:
            stats = self.db.get_generation_stats(self.experiment_id, latest_gen)
            self._draw_neat_stats(self.ax_stats, stats)
        else:
            self._draw_neat_stats_placeholder(self.ax_stats)
        
        # --- PANEL 0,2: EXPERIMENT STATUS ---
        if self.experiment_id:
            status = self.db.get_experiment_status(self.experiment_id)
            self._draw_experiment_status(self.ax_status, status, latest_gen)
        else:
            self._draw_setup_status(self.ax_status)
        
        # --- PANEL 1,0: MORPHOLOGY PARAMETERS ---
        if current_best and current_best.morphology_genome:
            self._draw_morphology_params(self.ax_morph, current_best.morphology_genome)
            self._draw_aircraft_silhouette(self.ax_morph, current_best.morphology_genome)
        else:
            self._draw_morphology_placeholder(self.ax_morph)
        
        # --- PANEL 1,1: BASELINE COMPARISON ---
        if self.baseline and current_best:
            self._draw_baseline_comparison(self.ax_baseline, self.baseline, current_best.metrics)
        else:
            self._draw_baseline_placeholder(self.ax_baseline)
        
        # --- PANEL 1,2: FITNESS CURVE ---
        if self.experiment_id and latest_gen is not None:
            fitness_history = self.db.get_fitness_history(self.experiment_id)
            self._draw_fitness_curve(self.ax_fitness, fitness_history)
        else:
            # Show just baseline as horizontal line
            self.ax_fitness.axhline(y=self.baseline["survival_time_mean"] if self.baseline else 0, 
                                   color='#ff6b6b', linestyle='--', alpha=0.7, label='Baseline')
            self.ax_fitness.legend(loc='upper right')
            self.ax_fitness.set_xlim(0, 10)
            self.ax_fitness.set_ylim(0, 30)
        
        plt.tight_layout()
    
    # Helper drawing methods for each panel (using matplotlib text/circles/lines)
    def _draw_placeholder_genome(self, ax):
        """Draw minimal NEAT genome: 15 inputs -> 6 outputs"""
        layer_spacing = 0.3
        input_y = np.linspace(0.2, 0.8, 15)
        output_y = np.linspace(0.2, 0.8, 6)
        
        # Draw input nodes
        for i, y in enumerate(input_y):
            circle = Circle((0.1, y), 0.03, color='#4a90e2', alpha=0.8)
            ax.add_patch(circle)
            ax.text(0.05, y, f"I{i}", ha='right', va='center', fontsize=6, color='white')
        
        # Draw output nodes
        for i, y in enumerate(output_y):
            circle = Circle((0.9, y), 0.03, color='#ff6b6b', alpha=0.8)
            ax.add_patch(circle)
            ax.text(0.95, y, f"O{i}", ha='left', va='center', fontsize=6, color='white')
        
        # Draw sparse connections (show concept only)
        for i in [0, 5, 10, 14]:  # Sample inputs
            for j in [0, 3, 5]:   # Sample outputs
                if np.random.random() > 0.7:  # 30% connection density
                    ax.plot([0.13, 0.87], [input_y[i], output_y[j]], 
                           color='#ffff00', alpha=0.4, linewidth=0.5)
        
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
    
    def _draw_neat_stats_placeholder(self, ax):
        """Show NEAT stats when no evolution running"""
        stats_text = """
        NETWORK STATISTICS
        ──────────────────
        Generation: — 
        Best Fitness: — 
        ──────────────────
        Nodes: — / — 
        Connections: — / — 
        Species: — 
        ──────────────────
        Mutation Rates:
        Weight: — 
        Bias: — 
        Add Node: — 
        Add Conn: — 
        """
        ax.text(0.05, 0.95, stats_text, transform=ax.transAxes, 
                fontsize=9, va='top', fontfamily='monospace',
                color='#cccccc', linespacing=1.2)
    
    def _draw_setup_status(self, ax):
        """Show setup phase status"""
        status_text = """
        EXPERIMENT SETUP
        ──────────────────
        Status: 🟢 READY
        Phase: Infrastructure
        ──────────────────
        Baseline: LOADED
        DB: CONNECTED
        Sim: READY
        ──────────────────
        Next Steps:
        1. Run baseline confirmation
        2. Test NEAT integration
        3. Launch dashboard
        4. Begin experiments
        """
        ax.text(0.05, 0.95, status_text, transform=ax.transAxes, 
                fontsize=9, va='top', fontfamily='monospace',
                color='#00ff88', linespacing=1.2)
    
    def _draw_morphology_placeholder(self, ax):
        """Show aircraft silhouette with default parameters"""
        # Simple tube-and-wing ASCII art
        ascii_art = """
              _____
             /     \\   ← Wing Span
            |       |
            |       |   ← Fuselage
             \\_____/  
              | | |    ← Vertical/Horizontal Tails
        """
        ax.text(0.5, 0.5, ascii_art, transform=ax.transAxes,
                ha='center', va='center', fontsize=10,
                fontfamily='monospace', color='#cccccc')
        
        # Parameter labels
        params_text = """
        Wingspan: 1.0m
        Wing Area: 0.3m²
        H-Tail Area: 0.05m²
        V-Tail Area: 0.05m²
        T/W Ratio: 0.6
        Mass: 1.2kg
        CG Offset: 0.0m
        """
        ax.text(0.05, 0.05, params_text, transform=ax.transAxes,
                ha='left', va='bottom', fontsize=8,
                fontfamily='monospace', color='#aaaaaa')
    
    def start(self):
        """Launch the live dashboard"""
        self.is_running = True
        self.ani = animation.FuncAnimation(
            self.fig, self.update, interval=self.update_interval*1000,
            blit=False, cache_frame_data=False
        )
        plt.tight_layout()
        plt.show()
    
    def stop(self):
        """Stop the dashboard"""
        self.is_running = False
        if self.ani:
            self.ani.event_source.stop()
```

**Dashboard Features**:
- **NEAT Genome Panel**: Visualizes nodes as circles (inputs blue, outputs red, hidden gray), connections as lines (weight → thickness/color: blue=positive, red=negative, thickness=|weight|)
- **NEAT Stats Panel**: Shows node/connection counts, species count, mutation rates (color-coded: green=optimal, yellow=suboptimal, red=problematic)
- **Experiment Status Panel**: Displays generation, timing, status indicators (🟢 running, 🟡 paused, 🔴 crashed), ETA estimates
- **Morphology Panel**: Lists 7 parameters with current values + ASCII aircraft silhouette that scales with parameters (wingspan → width, tail size → height)
- **Baseline Comparison**: Side-by-side bars showing current best vs baseline for survival, distance, efficiency
- **Fitness Curve**: Live-updating line chart (best/mean/worst per generation) with baseline reference line

**Verification Criterion**:
- Run `python -m src.dashboard` (baseline-only mode)
- Confirm window opens with all 6 panels populated
- Check that placeholder genome, status, and morphology panels show correct setup-phase info
- Close window cleanly with `q` or window close button

---

## 8. Build Order for Setup Phase
**Concrete Steps with Verification Criteria**

| Step | Action | Verification Criterion |
|------|--------|------------------------|
| **1** | Scaffold project structure<br>- Create directories<br>- Copy existing spec<br>- Create empty `__init__.py` files | `tree -L 2` shows expected structure<br>All packages importable: `python -c "import src.simulation.env"` |
| **2** | Install dependencies<br>- `pip install wheel numpy`<br>- `pip install -r requirements.txt`<br>- Verify PyFlyt/NEAT import | `python -c "import pyflyt, neat, numpy; print('Deps OK')"`<br>`python -c "import pyflyt; print(pyflyt.__version__)"` |
| **3** | Implement & test simulation wrapper<br>- `src/simulation/env.py`<br>- Test with default PyFlyt model | `reset()` → `step()` returns (15,) obs<br>`get_metrics()` returns dict with expected keys<br>No crashes on 100-step rollout |
| **4** | Implement & test baseline confirmation<br>- `src/simulation/evaluator.py`<br>- `run.py --baseline` command | Baseline survival time > 25s<br>Baseline metrics saved to SQLite<br>`ExperimentDB.get_latest_baseline()` returns correct data |
| **5** | Implement & test NEAT controller wrapper<br>- `src/genome/controller.py`<br>- Genome summary method | NEAT config builds from JSON<br>`get_genome_summary()` returns dict with all expected keys<br>Fitness=None initially, 0 connections |
| **6** | Implement & test data logging infrastructure<br>- `src/experiment/db.py`<br>- Schema creation + CRUD ops | Tables create without error<br>Baseline save/load round-trip accurate<br>Indexes present and usable |
| **7** | Implement visual dashboard<br>- `src/dashboard/` modules<br>- `python -m src.dashboard` entry point | Dashboard launches and shows 6 panels<br>Placeholder genome visible<br>Setup status panel shows "READY"<br>Baseline data displayed in comparison panel |
| **8** | End-to-end setup smoke test<br>- Run baseline<br>- Launch dashboard<br>- Confirm live updates (even if static) | Dashboard shows baseline metrics<br>Status panel reflects completed baseline<br>No errors in console during operation<br>Clean shutdown |

**Exit Criteria for Setup Phase**:
- Baseline metrics captured and stored
- Simulation environment works with default and custom models
- NEAT configuration loads and can generate genome summaries
- Database schema is initialized and functional
- Dashboard launches and displays all required information
- User can run `python run.py --baseline` followed by `python -m src.dashboard` to see baseline data visualized

> **Note**: Actual evolutionary experiments (Steps 9+ in the full plan) are NOT part of this setup phase plan. This plan ends when the dashboard is live and showing baseline-ready status.

---
*This plan provides the complete experimental setup infrastructure and visual monitoring capability needed to begin evolutionary co-design experiments. The dashboard gives real-time visibility into NEAT model status, morphology parameters, and experiment progress — fulfilling the requirement to "see what's up" visually during the setup and early experiment phases.*