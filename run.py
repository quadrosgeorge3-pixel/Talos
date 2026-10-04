"""Talos CLI — experimental setup and execution commands.

Currently supported:

    python run.py baseline [--config <path>] [--episodes N]
    python run.py evolve [--generations N] [--checkpoint <path>]
    python run.py web [--port 8050]
    python run.py dashboard [--experiment <id>]
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import tqdm

from src.experiment.db import ExperimentDB
from src.experiment.metadata import load_config
from src.simulation.env import FixedwingEnv


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OUTPUT_DIR = "output"
DEFAULT_BASELINE_CONFIG = os.path.join(
    "configs", "baselines", "b0_default_pid.json"
)


# ---------------------------------------------------------------------------
# Baseline runner
# ---------------------------------------------------------------------------

def run_baseline(
    config_path: str = DEFAULT_BASELINE_CONFIG,
    episodes: int = 5,
    base_seed: int = 42,
) -> Dict[str, Any]:
    """Evaluate PyFlyt's built-in PID controller on the default airframe.

    Aggregates flight metrics across ``episodes`` independent runs and
    stores them in the experiment database as ``B0_default_pid``.
    """
    config = load_config(config_path)
    experiment_id = config.get("experiment_id", "B0_baseline_pid")

    # PyFlyt/PyBullet are required for actual simulation
    try:
        import gymnasium  # noqa: F401
    except ImportError:
        print("[talos] ERROR: gymnasium not installed.")
        print("          Install dependencies with:  pip install wheel numpy pyflyt")
        sys.exit(1)

    sim_cfg = config["simulation"]
    num_episodes = episodes

    all_metrics: List[Dict[str, Any]] = []

    print(f"[talos] Running baseline '{experiment_id}' over {num_episodes} episodes...")

    from src.simulation.pid_controller import FixedwingPIDController

    for episode in tqdm.trange(num_episodes, desc="baseline", unit="ep"):
        env = FixedwingEnv(config=config, model_dir=None)
        pid_controller = FixedwingPIDController(dt=1.0 / env.control_hz)

        seed = base_seed + episode
        obs, _ = env.reset(seed=seed)
        pid_controller.reset()

        terminated = False
        truncated = False
        step_metrics: List[Dict[str, Any]] = []

        while not (terminated or truncated):
            action = pid_controller.predict(obs)
            obs, reward, terminated, truncated, info = env.step(action)
            step_metrics.append(info)

        episode_metrics = env.get_metrics()
        all_metrics.append(episode_metrics)

        try:
            env.env.close()
        except Exception:
            pass

    # Aggregate statistics across episodes
    summary = _aggregate_baseline(all_metrics)

    # Persist to SQLite
    db = ExperimentDB(os.path.join(OUTPUT_DIR, "icarus.db"))

    # Register experiment metadata row if missing
    existing = db.get_experiment(experiment_id)
    if existing is None:
        now = _now_iso()
        db.create_experiment(experiment_id, config, now)

    measured_at = _now_iso()
    db.save_baseline("B0_default_pid", experiment_id, summary, measured_at)
    db.complete_experiment(experiment_id, measured_at)

    _print_baseline_summary(summary)

    return summary


# ---------------------------------------------------------------------------
# Dashboard launcher
# ---------------------------------------------------------------------------

def launch_dashboard(
    experiment_id: Optional[str] = None,
    config_path: Optional[str] = None,
    interval: float = 1.0,
) -> None:
    """Launch the visual dashboard in setup or live mode."""
    from src.dashboard import EvolutionDashboard

    dashboard = EvolutionDashboard(
        experiment_id=experiment_id,
        output_dir=OUTPUT_DIR,
        config_path=config_path,
        update_interval=interval,
    )
    dashboard.start()


def launch_web_dashboard(
    port: int = 8050,
    db_path: str = os.path.join(OUTPUT_DIR, "icarus.db"),
) -> None:
    """Launch the HTML dashboard in the browser."""
    from src.dashboard.web import serve
    serve(port=port, db_path=db_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="icarus",
        description=(
            "Icarus — Evolutionary Co-Design of Powered Aircraft.\n"
            "Setup phase: baseline confirmation + visual dashboard."
        ),
    )

    sub = parser.add_subparsers(dest="command")

    # Baseline
    p_base = sub.add_parser(
        "baseline",
        help="Measure PyFlyt's built-in PID controller on the default airframe.",
    )
    p_base.add_argument(
        "--config",
        default=DEFAULT_BASELINE_CONFIG,
        help=f"Baseline config path (default: {DEFAULT_BASELINE_CONFIG})",
    )
    p_base.add_argument(
        "--episodes",
        type=int,
        default=5,
        help="Number of episodes to average (default: 5)",
    )
    p_base.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Base random seed (default: 42)",
    )

    # Dashboard
    p_dash = sub.add_parser(
        "dashboard",
        help="Launch the live visual dashboard.",
    )
    p_dash.add_argument(
        "--experiment",
        default=None,
        help="Experiment ID to stream (default: setup/baseline mode)",
    )
    p_dash.add_argument(
        "--config",
        default=None,
        help="Experiment config used to bootstrap the NEAT display",
    )
    p_dash.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Refresh interval in seconds (default: 1.0)",
    )

    # Web dashboard
    p_web = sub.add_parser(
        "web",
        help="Launch the HTML dashboard in the browser.",
    )
    p_web.add_argument(
        "--port",
        type=int,
        default=8050,
        help="Port number (default: 8050)",
    )

    # Evolution
    p_evo = sub.add_parser(
        "evolve",
        help="Run evolutionary optimization (Phase 2 controller, Phase 3 morphology, etc.).",
    )
    p_evo.add_argument(
        "--config",
        default=os.path.join("configs", "controller_only", "c1_controller_only.json"),
        help="Path to experiment JSON config",
    )
    p_evo.add_argument(
        "--experiment",
        default=None,
        help="Override experiment ID (e.g. C1)",
    )
    p_evo.add_argument(
        "--generations",
        type=int,
        default=None,
        help="Override number of generations",
    )
    p_evo.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed",
    )

    # Benchmark
    p_bench = sub.add_parser(
        "benchmark",
        help="Run the head-to-head generalization benchmark suite (PID vs NEAT).",
    )
    p_bench.add_argument(
        "--experiment",
        default="C1",
        help="Experiment ID of the champion to test (default: C1)",
    )
    p_bench.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Physics evaluation seed (default: 42)",
    )

    # Morphology Evolution
    p_morph = sub.add_parser(
        "evolve-morphology",
        help="Run continuous morphology evolutionary optimization (Phase 3).",
    )
    p_morph.add_argument(
        "--config",
        default=os.path.join("configs", "morphology_only", "p3a_bounded_100m.json"),
        help="Path to morphology experiment JSON config",
    )
    p_morph.add_argument(
        "--db",
        default="output/icarus.db",
        help="Database path (default: output/icarus.db)",
    )

    # Co-Evolution (Phase 4)
    p_coevo = sub.add_parser(
        "coevolve",
        help="Run simultaneous body + brain co-evolution (Phase 4).",
    )
    p_coevo.add_argument(
        "--config",
        default=os.path.join("configs", "coevolution", "p4_ultima_coevo.json"),
        help="Path to coevolution experiment JSON config",
    )
    p_coevo.add_argument(
        "--experiment",
        default=None,
        help="Override experiment ID (e.g. TALOS-P4-ULTIMA)",
    )
    p_coevo.add_argument(
        "--generations",
        type=int,
        default=None,
        help="Override number of generations",
    )
    p_coevo.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed",
    )
    p_coevo.add_argument(
        "--db",
        default="output/icarus.db",
        help="Database path (default: output/icarus.db)",
    )

    # Notebook
    p_note = sub.add_parser(
        "notebook",
        help="Refresh the automated research lab notebook (docs/LAB_NOTEBOOK.md).",
    )

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "baseline":
        run_baseline(
            config_path=args.config,
            episodes=args.episodes,
            base_seed=args.seed,
        )
        return 0

    if args.command == "evolve":
        from src.evolution.runner import run_evolution
        run_evolution(
            config_path=args.config,
            experiment_id=args.experiment,
            generations=args.generations,
            seed=args.seed,
        )
        return 0

    if args.command == "evolve-morphology":
        from src.evolution.morphology_runner import run_morphology_evolution
        run_morphology_evolution(
            config_path=args.config,
            db_path=args.db,
        )
        return 0

    if args.command == "coevolve":
        from src.evolution.coevolution_runner import run_coevolution
        run_coevolution(
            config_path=args.config,
            experiment_id=args.experiment,
            generations=args.generations,
            seed=args.seed,
            db_path=args.db,
        )
        return 0

    if args.command == "benchmark":
        from src.simulation.generalization_benchmark import run_comparative_generalization_suite
        from src.experiment.generate_notebook import generate_lab_notebook
        run_comparative_generalization_suite(experiment_id=args.experiment, seed=args.seed)
        generate_lab_notebook()
        return 0

    if args.command == "notebook":
        from src.experiment.generate_notebook import generate_lab_notebook
        generate_lab_notebook()
        return 0

    if args.command == "dashboard":
        launch_dashboard(
            experiment_id=args.experiment,
            config_path=args.config,
            interval=args.interval,
        )
        return 0

    if args.command == "web":
        launch_web_dashboard(port=args.port)
        return 0

    # No command: show help
    parser.print_help()
    return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _aggregate_baseline(metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute mean/std per metric across episodes."""
    keys = [
        "survival_time", "distance", "energy", "waypoint_time",
        "altitude_error", "airspeed_error",
    ]

    summary: Dict[str, Any] = {}

    for key in keys:
        if key == "survival_time":
            values = np.asarray([m.get("survival_time", m.get("flight_time", 0.0)) for m in metrics], dtype=np.float64)
        else:
            values = np.asarray([m.get(key, 0.0) for m in metrics], dtype=np.float64)
        summary[key] = {
            "mean": float(np.mean(values)),
            "std": float(np.std(values)),
            "min": float(np.min(values)),
            "max": float(np.max(values)),
        }

    summary["crash_rate"] = float(np.mean([m.get("crashed", False) for m in metrics]))
    summary["stall_rate"] = float(np.mean([m.get("stalling", False) for m in metrics]))
    summary["num_episodes"] = len(metrics)

    return summary


def _print_baseline_summary(summary: Dict[str, Any]) -> None:
    print("\n" + "=" * 52)
    print("  BASELINE SUMMARY — PyFlyt default PID controller")
    print("=" * 52)
    for key in ["survival_time", "distance", "energy", "altitude_error", "airspeed_error"]:
        stat = summary[key]
        print(f"  {key:16s}  mean={stat['mean']:8.2f}  std={stat['std']:6.2f}")
    print(f"  {'crash_rate':16s}  {summary['crash_rate']:.0%}")
    print(f"  {'stall_rate':16s}  {summary['stall_rate']:.0%}")
    print("=" * 52)
    print(f"  Stored to output/icarus.db as 'B0_default_pid'\n")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    raise SystemExit(main())