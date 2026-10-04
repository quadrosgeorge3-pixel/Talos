"""Evolutionary experiment runner for ICARUS / Talos.

Coordinates NEAT topological evolution on PyFlyt fixedwing aircraft,
logging generation statistics, champion individuals, and flight trajectories
directly to SQLite (`output/icarus.db`).
"""
from __future__ import annotations

import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import neat
import numpy as np
from tqdm import tqdm

from src.experiment.db import ExperimentDB
from src.experiment.metadata import load_config
from src.genome.controller import NEATController, serialize_genome, serialize_genome_dict
from src.simulation.env import FixedwingEnv
from src.simulation.evaluator import compute_fitness


# ---------------------------------------------------------------------------
# Trajectory recording
# ---------------------------------------------------------------------------

def _record_champion_flight(
    env: FixedwingEnv,
    net: neat.nn.FeedForwardNetwork,
    seed: int,
    experiment_id: str,
) -> Dict[str, Any]:
    """Run one evaluation of the champion and record its 3D flight trajectory."""
    obs, _ = env.reset(seed=seed)
    trajectory: List[Dict[str, Any]] = []

    terminated = False
    truncated = False
    step = 0

    while not (terminated or truncated) and step < env.max_steps:
        action = np.asarray(net.activate(obs), dtype=np.float32)
        obs, _, terminated, truncated, info = env.step(action)
        step += 1

        # Sample every 4 steps to keep JSON compact while retaining fidelity
        if step % 4 == 0 or terminated or truncated:
            trajectory.append({
                "step": step,
                "x": float(info.get("pos_x", obs[9])),
                "y": float(info.get("pos_y", obs[10])),
                "z": float(info.get("pos_z", obs[11])),
                "roll": float(info.get("roll", obs[3])),
                "pitch": float(info.get("pitch", obs[4])),
                "yaw": float(info.get("yaw", obs[5])),
                "airspeed": float(info.get("airspeed", obs[6])),
                "thrust": float(action[5] if len(action) > 5 else 0.0),
            })

    metrics = env.get_metrics()
    return {
        "status": "success",
        "experiment_id": experiment_id,
        "type": "evolutionary_champion",
        "flight_time": float(metrics.get("flight_time", 0.0)),
        "distance": float(metrics.get("distance", 0.0)),
        "energy": float(metrics.get("energy", 0.0)),
        "crashed": bool(metrics.get("crashed", False)),
        "stalling": bool(metrics.get("stalling", False)),
        "altitude_error": float(metrics.get("altitude_error", 0.0)),
        "airspeed_error": float(metrics.get("airspeed_error", 0.0)),
        "trajectory": trajectory,
    }


# ---------------------------------------------------------------------------
# Database reporter hook for NEAT
# ---------------------------------------------------------------------------

class DatabaseReporter(neat.reporting.BaseReporter):
    """Custom NEAT reporter that logs per-generation stats and champion to SQLite."""

    def __init__(
        self,
        experiment_id: str,
        db: ExperimentDB,
        config: Dict[str, Any],
        neat_config: neat.Config,
        env: FixedwingEnv,
        base_seed: int = 42,
    ) -> None:
        self.experiment_id = experiment_id
        self.db = db
        self.config = config
        self.neat_config = neat_config
        self.env = env
        self.base_seed = base_seed
        self.generation = 0
        self.best_overall_fitness = -float("inf")
        self.start_time = time.time()

    def start_generation(self, generation: int) -> None:
        self.generation = generation

    def post_evaluate(
        self,
        config: neat.Config,
        population: Dict[int, neat.DefaultGenome],
        species: neat.DefaultSpeciesSet,
        best_genome: neat.DefaultGenome,
    ) -> None:
        fitnesses = [g.fitness for g in population.values() if g.fitness is not None]
        if not fitnesses:
            return

        best_fit = float(np.max(fitnesses))
        mean_fit = float(np.mean(fitnesses))
        med_fit = float(np.median(fitnesses))
        worst_fit = float(np.min(fitnesses))
        std_fit = float(np.std(fitnesses))

        # Node and connection complexity of the population & champion
        best_enabled_conns = sum(1 for c in best_genome.connections.values() if c.enabled)
        best_nodes = len(best_genome.nodes)
        mean_nodes = float(np.mean([len(g.nodes) for g in population.values()]))
        mean_conns = float(
            np.mean([sum(1 for c in g.connections.values() if c.enabled) for g in population.values()])
        )
        species_count = len(species.species)
        population_alive = len(fitnesses)

        # Run trajectory recording on the champion
        champ_net = neat.nn.FeedForwardNetwork.create(best_genome, config)
        flight_data = _record_champion_flight(
            self.env, champ_net, seed=self.base_seed, experiment_id=self.experiment_id
        )

        # Store generation stats
        stats = {
            "best_fitness": best_fit,
            "mean_fitness": mean_fit,
            "median_fitness": med_fit,
            "worst_fitness": worst_fit,
            "std_fitness": std_fit,
            "best_nodes": best_nodes,
            "best_connections": best_enabled_conns,
            "mean_nodes": mean_nodes,
            "mean_connections": mean_conns,
            "species_count": species_count,
            "population_alive": population_alive,
            "best_survival_time": flight_data["flight_time"],
            "best_distance": flight_data["distance"],
            "best_energy": flight_data["energy"],
            "best_waypoint_time": 0.0,
        }
        self.db.log_generation(self.experiment_id, self.generation, stats)

        # Serialize champion genome for visual dashboard
        ctrl_json = serialize_genome(best_genome, config)
        ind_data = {
            "fitness": best_fit,
            "is_elite": True,
            "survival_time": flight_data["flight_time"],
            "distance": flight_data["distance"],
            "energy": flight_data["energy"],
            "waypoint_time": 0.0,
            "altitude_error": flight_data["altitude_error"],
            "airspeed_error": flight_data["airspeed_error"],
            "crashed": flight_data["crashed"],
            "stalling": flight_data["stalling"],
            "nodes": best_nodes,
            "connections": best_enabled_conns,
            "species_id": getattr(best_genome, "species_id", 0),
            "morphology_json": json.dumps(self.config.get("morphology", {})),
            "controller_json": ctrl_json,
        }
        self.db.log_individual(
            self.experiment_id,
            self.generation,
            index=0,
            data=ind_data,
        )

        # Update best overall
        if best_fit > self.best_overall_fitness:
            self.best_overall_fitness = best_fit
            self.db.update_best(self.experiment_id, best_fit, self.generation)

            # Export latest trajectory to both specific c1 and global b0 for dashboard
            os.makedirs("output", exist_ok=True)
            for path in [
                os.path.join("output", f"{self.experiment_id.lower()}_trajectory.json"),
                os.path.join("output", "b0_trajectory.json"),
            ]:
                try:
                    with open(path, "w", encoding="utf-8") as fh:
                        json.dump(flight_data, fh, indent=2)
                except Exception:
                    pass

        elapsed = time.time() - self.start_time
        print(
            f"[{self.experiment_id}] Gen {self.generation:3d} | "
            f"Best: {best_fit:6.2f} | Mean: {mean_fit:6.2f} | "
            f"Dist: {flight_data['distance']:5.1f}m | "
            f"Species: {species_count:2d} | "
            f"Time: {elapsed:5.1f}s"
        )
        sys.stdout.flush()


# ---------------------------------------------------------------------------
# Main Evolution Entry Point
# ---------------------------------------------------------------------------

def run_evolution(
    config_path: str = os.path.join("configs", "controller_only", "c1_controller_only.json"),
    experiment_id: Optional[str] = None,
    generations: Optional[int] = None,
    seed: Optional[int] = None,
    db_path: str = os.path.join("output", "icarus.db"),
) -> neat.DefaultGenome:
    """Run NEAT controller evolution pipeline for Phase 2.

    Parameters
    ----------
    config_path : str
        Path to JSON experiment config.
    experiment_id : str, optional
        Override experiment ID (default: from config or 'C1').
    generations : int, optional
        Number of generations to evolve (default: from config or 300).
    seed : int, optional
        Random seed (default: 42).
    db_path : str
        SQLite database path.
    """
    config = load_config(config_path)

    eid = experiment_id or config.get("experiment_id", "C1")
    rnd_seed = seed if seed is not None else int(config.get("random_seed", 42))
    num_gens = generations if generations is not None else int(
        config.get("neat_config", {}).get("num_generations", 300)
    )

    # Set random seeds
    random.seed(rnd_seed)
    np.random.seed(rnd_seed)

    print(f"\n{'=' * 60}")
    print(f"  ICARUS / TALOS — PHASE 2 CONTROLLER EVOLUTION")
    print(f"  Experiment ID : {eid}")
    print(f"  Generations   : {num_gens}")
    print(f"  Random Seed   : {rnd_seed}")
    print(f"  Database      : {db_path}")
    print(f"{'=' * 60}\n")

    # Connect to SQLite DB
    db = ExperimentDB(db_path)
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # Register experiment
    existing = db.get_experiment(eid)
    if existing is None:
        db.create_experiment(eid, config, now_iso)
    else:
        # Re-activate status if rerunning
        conn = db._conn()
        try:
            conn.execute(
                "UPDATE experiment_metadata SET status = 'running', start_time = ? WHERE experiment_id = ?",
                (now_iso, eid),
            )
            conn.commit()
        finally:
            conn.close()

    # Look for latest checkpoint to resume if available
    chk_dir = os.path.join("output", "checkpoints")
    os.makedirs(chk_dir, exist_ok=True)
    latest_chk = None
    if os.path.isdir(chk_dir):
        chks = [
            os.path.join(chk_dir, f)
            for f in os.listdir(chk_dir)
            if f.startswith(f"{eid.lower()}-chk-")
        ]
        if chks:
            def _chk_gen(p: str) -> int:
                try:
                    return int(os.path.basename(p).split("-")[-1])
                except Exception:
                    return 0
            chks.sort(key=_chk_gen)
            latest_chk = chks[-1]

    if latest_chk and os.path.isfile(latest_chk):
        print(f"[icarus] Resuming evolution from checkpoint: {latest_chk}")
        pop = neat.Checkpointer.restore_checkpoint(latest_chk)
        pop.config.reset_on_extinction = True
        if hasattr(pop.reproduction, 'stagnation'):
            pop.reproduction.stagnation.species_elitism = 2
            pop.reproduction.stagnation.max_stagnation = 50
        neat_cfg = pop.config
    else:
        controller = NEATController(config)
        pop = controller.population
        neat_cfg = controller.config

    # Persistent simulation environment
    env = FixedwingEnv(config=config)

    # Attach custom database reporter
    db_reporter = DatabaseReporter(
        experiment_id=eid,
        db=db,
        config=config,
        neat_config=neat_cfg,
        env=env,
        base_seed=rnd_seed,
    )
    pop.add_reporter(db_reporter)

    # Define evaluation function
    def eval_genomes(
        genomes: List[Tuple[int, neat.DefaultGenome]],
        neat_config: neat.Config,
    ) -> None:
        cur_gen = db_reporter.generation
        for genome_id, genome in genomes:
            net = neat.nn.FeedForwardNetwork.create(genome, neat_config)
            obs, _ = env.reset(seed=rnd_seed + (genome_id % 1000))

            terminated = False
            truncated = False
            step = 0

            while not (terminated or truncated) and step < env.max_steps:
                action = np.asarray(net.activate(obs), dtype=np.float32)
                obs, _, terminated, truncated, _ = env.step(action)
                step += 1

            metrics = env.get_metrics()
            fitness = compute_fitness(metrics, config, generation=cur_gen)
            genome.fitness = float(fitness)

    # Checkpoint every 5 generations
    pop.add_reporter(neat.Checkpointer(5, filename_prefix=os.path.join("output", "checkpoints", f"{eid.lower()}-chk-")))

    remaining_gens = max(1, num_gens - pop.generation)
    try:
        winner = pop.run(eval_genomes, remaining_gens)
    except KeyboardInterrupt:
        print(f"\n[icarus] Evolution interrupted by user. Finalizing records...")
        winner = pop.best_genome
    finally:
        end_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
        db.complete_experiment(eid, end_iso)
        try:
            env.env.close()
        except Exception:
            pass

    print(f"\n{'=' * 60}")
    print(f"  PHASE 2 COMPLETED: {eid}")
    print(f"  Champion Fitness : {winner.fitness if winner else 'N/A'}")
    print(f"  Recorded into    : {db_path}")
    print(f"{'=' * 60}\n")

    return winner
