"""Dashboard entry point: ``python -m src.dashboard``."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="icarus-dashboard",
        description="Live dashboard for the Icarus evolution project.",
    )
    parser.add_argument(
        "--experiment",
        default=None,
        help="Experiment ID to stream (default: setup/baseline mode)",
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Root output directory (default: output)",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to an experiment config (used to bootstrap NEAT display)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Refresh interval in seconds (default: 1.0)",
    )
    args = parser.parse_args()

    from src.dashboard import EvolutionDashboard

    dashboard = EvolutionDashboard(
        experiment_id=args.experiment,
        output_dir=args.output_dir,
        config_path=args.config,
        update_interval=args.interval,
    )
    dashboard.start()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())