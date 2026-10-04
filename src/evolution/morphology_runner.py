"""Standalone morphology evolutionary runner for ICARUS / TALOS.

Evolves the 7-parameter aircraft morphology genome while the flight controller
remains fixed (PID autopilot or frozen NEAT champion). Logs generation statistics,
champion airframes, and 3D flight trajectories directly to SQLite ('output/icarus.db').
"""
from __future__ import annotations

import json
import os
import shutil
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np

import neat
from src.experiment.db import ExperimentDB
from src.experiment.metadata import load_config
from src.genome.controller import morphology_param_names
from src.genome.morphology import MorphologyGenome
from src.genome.urdf_gen import generate_model_files
from src.simulation.env import FixedwingEnv
from src.simulation.evaluator import compute_fitness
from src.simulation.pid_controller import FixedwingPIDController


def _record_champion_trajectory(
    env: FixedwingEnv,
    controller: Any,
    pilot_type: str,
    seed: int,
    experiment_id: str,
    generation: int,
    morph_dict: Dict[str, float],
) -> Dict[str, Any]:
    """Run one evaluation of the champion and record its 3D flight trajectory."""
    obs, _ = env.reset(seed=seed)
    if hasattr(controller, "reset"):
        controller.reset()
    trajectory: List[Dict[str, Any]] = []

    step = 0
    terminated = False
    truncated = False

    while not (terminated or truncated) and step < env.max_steps:
        if pilot_type == "fixed_pid":
            action = controller.predict(obs)
        else:
            action = np.asarray(controller.activate(obs), dtype=np.float32)
        obs, _, terminated, truncated, info = env.step(action)
        step += 1

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
        "generation": generation,
        "type": "morphology_champion",
        "morphology": morph_dict,
        "flight_time": float(metrics.get("flight_time", 0.0)),
        "distance": float(metrics.get("distance", 0.0)),
        "energy": float(metrics.get("energy", 0.0)),
        "crashed": bool(metrics.get("crashed", False)),
        "stalling": bool(metrics.get("stalling", False)),
        "altitude_error": float(metrics.get("altitude_error", 0.0)),
        "airspeed_error": float(metrics.get("airspeed_error", 0.0)),
        "trajectory": trajectory,
    }


def run_morphology_evolution(
    config_path: str,
    db_path: str = "output/icarus.db",
    output_dir: str = "output",
    checkpoint_every: int = 25,
) -> MorphologyGenome:
    """Execute the continuous morphology evolutionary loop."""
    config = load_config(config_path)
    experiment_id = config.get("experiment_id", "TALOS-P3A")
    sim_cfg = config.get("simulation", {})
    pilot_cfg = config.get("pilot", {})
    morph_cfg = config.get("morphology_evolution", {})

    pop_size = int(morph_cfg.get("pop_size", 50))
    num_generations = int(morph_cfg.get("num_generations", 100))
    elitism = int(morph_cfg.get("elitism", 2))
    crossover_rate = float(morph_cfg.get("crossover_rate", 0.7))
    mutation_rate = float(morph_cfg.get("mutation_rate", 0.3))
    tournament_size = int(morph_cfg.get("tournament_size", 3))
    bounds = morph_cfg.get("bounds", None)
    base_seed = int(config.get("random_seed", 42))

    dome_radius = float(sim_cfg.get("flight_dome_size", 100.0))
    target_airspeed = float(pilot_cfg.get("target_airspeed", 22.0))
    target_altitude = float(pilot_cfg.get("target_altitude", 10.0))

    os.makedirs(output_dir, exist_ok=True)
    base_models_dir = os.path.join("models", experiment_id)
    os.makedirs(base_models_dir, exist_ok=True)

    db = ExperimentDB(db_path)
    start_time = datetime.now(timezone.utc).isoformat()
    db.create_experiment(experiment_id, config, start_time)

    rng = np.random.default_rng(base_seed)
    param_names = morphology_param_names()

    # Initial population
    population: List[MorphologyGenome] = []
    # Ind 0: Default PyFlyt reference morphology
    population.append(MorphologyGenome(bounds=bounds))

    # Ind 1..pop_size-1: Sampled uniformly within bounds
    for _ in range(pop_size - 1):
        rand_vec = []
        for name in param_names:
            b_lo, b_hi = bounds[name] if bounds and name in bounds else (0.8, 3.0)
            rand_vec.append(rng.uniform(b_lo, b_hi))
        population.append(MorphologyGenome(params=np.array(rand_vec, dtype=np.float32), bounds=bounds))

    pilot_type = str(pilot_cfg.get("type", "fixed_pid")).lower()
    is_neat_pilot = "neat" in pilot_type

    frozen_net: Optional[neat.nn.FeedForwardNetwork] = None
    if is_neat_pilot:
        chk_path = pilot_cfg.get("checkpoint", "output/checkpoints/talos-p2b-chk-300")
        if not os.path.isfile(chk_path):
            raise FileNotFoundError(f"NEAT checkpoint not found at: {chk_path}")
        pop = neat.Checkpointer.restore_checkpoint(chk_path)
        best_genome = max(pop.population.values(), key=lambda g: g.fitness or -999)
        frozen_net = neat.nn.FeedForwardNetwork.create(best_genome, pop.config)
        pilot_desc = f"FROZEN NEAT GEN 300 CHAMPION ({len(best_genome.nodes)} nodes, {sum(1 for c in best_genome.connections.values() if c.enabled)} conn)"
    else:
        pilot_desc = f"FIXED PID AUTOPILOT (Speed={target_airspeed}m/s, Alt={target_altitude}m)"

    print(f"\n{'='*75}")
    print(f"[talos] STARTING MORPHOLOGY EVOLUTION: {experiment_id}")
    print(f"[talos] Generations: {num_generations} | Population: {pop_size} | Dome: {dome_radius}m")
    print(f"[talos] Fixed Pilot: {pilot_desc}")
    print(f"[talos] Database: {db_path} | Models: {base_models_dir}")
    print(f"{'='*75}\n")

    all_time_best_fitness = -float("inf")
    all_time_champion: Optional[MorphologyGenome] = None

    for gen in range(num_generations):
        gen_evals: List[Dict[str, Any]] = []

        # Evaluate each individual in the population
        for ind_idx, ind in enumerate(population):
            model_dir = os.path.join(base_models_dir, f"gen{gen:03d}", f"ind{ind_idx:03d}")
            generate_model_files(ind, model_dir)

            env = FixedwingEnv(config=config, model_dir=model_dir)
            obs, _ = env.reset(seed=base_seed + gen)
            step = 0

            if is_neat_pilot:
                while step < env.max_steps:
                    action = np.asarray(frozen_net.activate(obs), dtype=np.float32)
                    obs, _, term, trunc, _ = env.step(action)
                    step += 1
                    if term or trunc:
                        break
            else:
                pid = FixedwingPIDController(
                    dt=1.0 / env.control_hz,
                    target_airspeed=target_airspeed,
                    target_altitude=target_altitude,
                    dome_radius=dome_radius,
                )
                pid.reset()
                while step < env.max_steps:
                    action = pid.predict(obs)
                    obs, _, term, trunc, _ = env.step(action)
                    step += 1
                    if term or trunc:
                        break

            metrics = env.get_metrics()
            fitness = compute_fitness(metrics, config, generation=gen)
            env.close()

            gen_evals.append({
                "individual": ind,
                "index": ind_idx,
                "fitness": fitness,
                "metrics": metrics,
                "model_dir": model_dir,
            })

        # Sort by fitness descending
        gen_evals.sort(key=lambda x: x["fitness"], reverse=True)
        champ_eval = gen_evals[0]
        champ_ind = champ_eval["individual"]
        champ_fit = champ_eval["fitness"]
        champ_metrics = champ_eval["metrics"]
        champ_p = champ_ind.to_dict()

        if champ_fit > all_time_best_fitness:
            all_time_best_fitness = champ_fit
            all_time_champion = champ_ind

        # Record full 3D trajectory for champion
        champ_env = FixedwingEnv(config=config, model_dir=champ_eval["model_dir"])
        if is_neat_pilot:
            traj_data = _record_champion_trajectory(
                champ_env, frozen_net, "neat", base_seed + gen, experiment_id, gen, champ_p
            )
        else:
            champ_pid = FixedwingPIDController(
                dt=1.0 / champ_env.control_hz,
                target_airspeed=target_airspeed,
                target_altitude=target_altitude,
                dome_radius=dome_radius,
            )
            traj_data = _record_champion_trajectory(
                champ_env, champ_pid, "fixed_pid", base_seed + gen, experiment_id, gen, champ_p
            )
        champ_env.close()

        # Save trajectory to output files for dashboard
        traj_path_p3c = os.path.join(output_dir, "p3c_trajectory.json")
        with open(traj_path_p3c, "w", encoding="utf-8") as f:
            json.dump(traj_data, f, indent=2)

        traj_path_p3b = os.path.join(output_dir, "p3b_trajectory.json")
        with open(traj_path_p3b, "w", encoding="utf-8") as f:
            json.dump(traj_data, f, indent=2)

        traj_path_p3a = os.path.join(output_dir, "p3a_trajectory.json")
        with open(traj_path_p3a, "w", encoding="utf-8") as f:
            json.dump(traj_data, f, indent=2)

        traj_path_c1 = os.path.join(output_dir, "c1_trajectory.json")
        with open(traj_path_c1, "w", encoding="utf-8") as f:
            json.dump(traj_data, f, indent=2)

        # Compute generation stats
        all_fits = [x["fitness"] for x in gen_evals]
        gen_stats = {
            "best_fitness": float(champ_fit),
            "mean_fitness": float(np.mean(all_fits)),
            "median_fitness": float(np.median(all_fits)),
            "worst_fitness": float(np.min(all_fits)),
            "std_fitness": float(np.std(all_fits)),
            "best_nodes": 7,
            "best_connections": 0,
            "mean_nodes": 7.0,
            "mean_connections": 0.0,
            "species_count": 1,
            "population_alive": sum(1 for x in gen_evals if not x["metrics"].get("crashed", False)),
            "best_survival_time": float(champ_metrics.get("survival_time", 0.0)),
            "best_distance": float(champ_metrics.get("distance", 0.0)),
            "best_energy": float(champ_metrics.get("energy", 0.0)),
            "best_waypoint_time": float(champ_metrics.get("waypoint_time", 0.0)),
        }

        # Log generation to SQLite
        db.log_generation(experiment_id, gen, gen_stats)

        # Log all individuals
        for rank, item in enumerate(gen_evals):
            is_elite = 1 if rank < elitism else 0
            m_dict = item["individual"].to_dict()
            ind_metrics = item["metrics"]
            db.log_individual(
                experiment_id=experiment_id,
                generation=gen,
                index=item["index"],
                data={
                    "fitness": item["fitness"],
                    "is_elite": is_elite,
                    "survival_time": ind_metrics.get("survival_time"),
                    "distance": ind_metrics.get("distance"),
                    "energy": ind_metrics.get("energy"),
                    "waypoint_time": ind_metrics.get("waypoint_time"),
                    "altitude_error": ind_metrics.get("altitude_error"),
                    "airspeed_error": ind_metrics.get("airspeed_error"),
                    "crashed": ind_metrics.get("crashed", False),
                    "stalling": ind_metrics.get("stalling", False),
                    "nodes": 7,
                    "connections": 0,
                    "species_id": 1,
                    "morphology_json": json.dumps(m_dict),
                    "controller_json": None,
                }
            )

        db.update_best(experiment_id, all_time_best_fitness, gen)

        # Clean up non-champion directories to save disk space
        for rank, item in enumerate(gen_evals):
            if rank > 0:
                try:
                    shutil.rmtree(item["model_dir"])
                except Exception:
                    pass

        # Print clean progress line
        surv = champ_metrics.get("survival_time", 0.0)
        dist = champ_metrics.get("distance", 0.0)
        print(
            f"[{experiment_id}] Gen {gen:3d}/{num_generations} | "
            f"Fit: {champ_fit:6.2f} (mean {np.mean(all_fits):5.2f}) | "
            f"Surv: {surv:4.1f}s | "
            f"Dist: {dist:5.1f}m | "
            f"Span: {champ_p['wingspan']:.2f}m | Area: {champ_p['wing_area']:.2f}m2 | "
            f"Mass: {champ_p['total_mass']:.2f}kg | T/W: {champ_p['thrust_to_weight']:.2f}"
        )

        # Reproduction for next generation
        if gen < num_generations - 1:
            next_pop: List[MorphologyGenome] = []

            # 1. Elitism: Preserve top individuals verbatim
            for e in range(min(elitism, len(gen_evals))):
                next_pop.append(gen_evals[e]["individual"])

            # 2. Tournament Selection, BLX Crossover, and Gaussian Mutation
            while len(next_pop) < pop_size:
                tourn1 = rng.choice(gen_evals, size=min(tournament_size, len(gen_evals)), replace=False)
                parent1 = max(tourn1, key=lambda x: x["fitness"])["individual"]

                if rng.random() < crossover_rate:
                    tourn2 = rng.choice(gen_evals, size=min(tournament_size, len(gen_evals)), replace=False)
                    parent2 = max(tourn2, key=lambda x: x["fitness"])["individual"]
                    child = parent1.crossover(parent2, alpha=0.5, rng=rng)
                else:
                    child = MorphologyGenome(params=parent1.params.copy(), bounds=bounds)

                if rng.random() < mutation_rate:
                    child = child.mutate(rng=rng, rate=mutation_rate)

                next_pop.append(child)

            population = next_pop

    end_time = datetime.now(timezone.utc).isoformat()
    db.complete_experiment(experiment_id, end_time)

    print(f"\n{'='*75}")
    print(f"[talos] MORPHOLOGY EVOLUTION COMPLETE: {experiment_id}")
    print(f"[talos] All-time Best Fitness: {all_time_best_fitness:.2f}")
    print(f"{'='*75}\n")

    return all_time_champion or population[0]
