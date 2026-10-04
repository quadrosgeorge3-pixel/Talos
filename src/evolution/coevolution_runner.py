"""Simultaneous Body-Brain Co-Evolutionary Runner for Project TALOS (Phase 4).

Coordinates simultaneous evolution of:
1. Controller Genome: NEAT topological neural network (pyflyt observations -> 6 control surfaces)
2. Morphology Genome: Continuous 7-parameter airframe vector (URDF/YAML generation per individual)

Both evolve together from a shared fresh baseline (Gen 0), logging generation stats,
champion genomes (both brain and body), and 3D flight trajectories to SQLite (output/icarus.db).
Features a 3-tier curriculum with endgame beast mode benchmarked against P3C Test 2 (49.2 m/s).
"""
from __future__ import annotations

import json
import os
import random
import shutil
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import neat
import numpy as np

from src.experiment.db import ExperimentDB
from src.experiment.metadata import load_config
from src.genome.controller import NEATController, serialize_genome, morphology_param_names
from src.genome.morphology import MorphologyGenome, DEFAULT_MORPHOLOGY
from src.genome.urdf_gen import generate_model_files
from src.simulation.env import FixedwingEnv
from src.simulation.evaluator import compute_fitness_detailed, BENCHMARK_TARGET_SPEED


# ---------------------------------------------------------------------------
# Hairpin Mastery Tier Curriculum Courses (Gen 350+)
# ---------------------------------------------------------------------------

HAIRPIN_COURSES = [
    # Course 0: Pylon Hairpin Reversal Course (Test E style, 180° hairpin turn)
    np.array([
        [160.0, 0.0, 12.0],
        [25.0, 35.0, 12.0],
        [25.0, -35.0, 12.0],
        [160.0, 0.0, 12.0],
    ], dtype=np.float32),
    # Course 1: High-G Aero Slalom Course (Test C style, rapid banking reversals)
    np.array([
        [80.0, 45.0, 18.0],
        [150.0, -45.0, 10.0],
        [220.0, 45.0, 20.0],
        [280.0, -45.0, 8.0],
    ], dtype=np.float32),
    # Course 2: Sharp 90-120° Hairpin Chicane
    np.array([
        [110.0, 0.0, 12.0],
        [150.0, 65.0, 14.0],
        [80.0, 100.0, 14.0],
        [20.0, 40.0, 12.0],
    ], dtype=np.float32),
    # Course 3: High-Speed Sprint Waypoints (Test B style, maintaining high cruise)
    np.array([
        [150.0, 0.0, 10.0],
        [236.6, 50.0, 15.0],
        [151.7, -34.8, 10.0],
        [300.0, -34.8, 12.0],
    ], dtype=np.float32),
]


# ---------------------------------------------------------------------------
# Testarossa Grand Prix Unified Course:
# 500m Straight Sprint -> Broad Turn -> Dynamic Slalom -> 180° Pylon Hairpin -> 500m Final Return Straight
# ---------------------------------------------------------------------------

TESTAROSSA_GRAND_PRIX_COURSE = np.array([
    # Sector 1: 500m Initial High-Speed Sprint
    [250.0, 0.0, 12.0],
    [500.0, 0.0, 12.0],
    # Sector 2: Broad High-Speed Sweeping Turn
    [650.0, 100.0, 14.0],
    [600.0, 250.0, 14.0],
    # Sector 3: Dynamic Slalom Transition
    [450.0, 300.0, 12.0],
    [300.0, 200.0, 10.0],
    [150.0, 300.0, 12.0],
    # Sector 4: 180° Pylon Hairpin Reversal
    [0.0, 150.0, 12.0],
    [-40.0, 50.0, 12.0],
    [0.0, -50.0, 12.0],
    # Sector 5: 500m Final Return Straightaway
    [250.0, -50.0, 12.0],
    [500.0, -50.0, 12.0],
], dtype=np.float32)


def _get_hairpin_tier_course(gid: int, gen: int, eid: str = "") -> np.ndarray:
    """Select track for evaluation: dedicated unified Grand Prix for TESTAROSSA, rotating for others."""
    if "TESTAROSSA" in eid.upper():
        return TESTAROSSA_GRAND_PRIX_COURSE
    idx = (gid + gen) % len(HAIRPIN_COURSES)
    return HAIRPIN_COURSES[idx]


# ---------------------------------------------------------------------------
# Trajectory Recording for Co-Evolved Champion
# ---------------------------------------------------------------------------

def _record_coevo_champion_flight(
    env: FixedwingEnv,
    net: neat.nn.FeedForwardNetwork,
    seed: int,
    experiment_id: str,
    generation: int,
    morph_dict: Dict[str, float],
    custom_waypoints: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """Run one evaluation of the co-evolved champion and record its 3D flight trajectory."""
    obs, _ = env.reset(seed=seed)
    if custom_waypoints is not None:
        env.env.unwrapped.waypoints.targets = custom_waypoints.copy()
        env.env.unwrapped.waypoints.num_targets = len(custom_waypoints)
        env.env.unwrapped.compute_state()
        obs = env._build_observation(env.env.unwrapped.state)
    trajectory: List[Dict[str, Any]] = []

    terminated = False
    truncated = False
    step = 0

    while not (terminated or truncated) and step < env.max_steps:
        action = np.asarray(net.activate(obs), dtype=np.float32)
        obs, _, terminated, truncated, info = env.step(action)
        step += 1

        if step % 4 == 0 or terminated or truncated:
            trajectory.append({
                "step": step,
                "time": float(step / env.control_hz),
                "x": float(info.get("pos_x", obs[9])),
                "y": float(info.get("pos_y", obs[10])),
                "z": float(info.get("pos_z", obs[11])),
                "roll": float(info.get("roll", obs[3])),
                "pitch": float(info.get("pitch", obs[4])),
                "yaw": float(info.get("yaw", obs[5])),
                "airspeed": float(info.get("airspeed", obs[6])),
                "thrust": float(action[5] if len(action) > 5 else 0.0),
                "waypoints_hit": int(info.get("waypoints_hit", 0)),
            })

    metrics = env.get_metrics()
    return {
        "status": "success",
        "experiment_id": experiment_id,
        "generation": generation,
        "type": "coevolution_champion",
        "morphology": morph_dict,
        "flight_time": float(metrics.get("flight_time", 0.0)),
        "distance": float(metrics.get("distance", 0.0)),
        "energy": float(metrics.get("energy", 0.0)),
        "crashed": bool(metrics.get("crashed", False)),
        "stalling": bool(metrics.get("stalling", False)),
        "altitude_error": float(metrics.get("altitude_error", 0.0)),
        "airspeed_error": float(metrics.get("airspeed_error", 0.0)),
        "mean_airspeed": float(metrics.get("mean_airspeed", 0.0)),
        "max_airspeed": float(metrics.get("max_airspeed", 0.0)),
        "waypoints_hit": int(metrics.get("waypoints_hit", 0)),
        "trajectory": trajectory,
    }


# ---------------------------------------------------------------------------
# Co-Evolution Main Loop
# ---------------------------------------------------------------------------

def run_coevolution(
    config_path: str = os.path.join("configs", "coevolution", "p4_ultima_coevo.json"),
    experiment_id: Optional[str] = None,
    generations: Optional[int] = None,
    seed: Optional[int] = None,
    db_path: str = os.path.join("output", "icarus.db"),
    base_models_dir: Optional[str] = None,
) -> Tuple[neat.DefaultGenome, MorphologyGenome]:
    """Execute simultaneous body and brain co-evolution.

    Parameters
    ----------
    config_path : str
        Path to co-evolution configuration JSON.
    experiment_id : str, optional
        Override experiment identifier (default: TALOS-P4-ULTIMA).
    generations : int, optional
        Number of co-evolutionary generations.
    seed : int, optional
        Base pseudo-random seed.
    db_path : str
        Path to SQLite experiment database.
    base_models_dir : str, optional
        Base directory to store generated URDF/YAML airframe models.
    """
    config = load_config(config_path)

    eid = experiment_id or config.get("experiment_id", "TALOS-P4-ULTIMA")
    rnd_seed = seed if seed is not None else int(config.get("random_seed", 42))
    num_gens = generations if generations is not None else int(
        config.get("neat_config", {}).get("num_generations", 600)
    )

    random.seed(rnd_seed)
    np.random.seed(rnd_seed)
    rng = np.random.default_rng(rnd_seed)

    sim_cfg = config.get("simulation", {})
    morph_cfg = config.get("morphology", {})
    bounds = morph_cfg.get("bounds", None)
    morph_mutate_rate = float(morph_cfg.get("mutation_rate", 0.3))

    models_dir = base_models_dir or os.path.join("models", eid)
    os.makedirs(models_dir, exist_ok=True)
    os.makedirs(os.path.join("output", "checkpoints"), exist_ok=True)

    print(f"\n{'=' * 75}")
    print(f"  TALOS — SIMULTANEOUS BODY + BRAIN CO-EVOLUTION")
    print(f"  Experiment ID : {eid}")
    print(f"  Generations   : {num_gens}")
    print(f"  Episode Length: {sim_cfg.get('episode_duration', 20.0)}s")
    print(f"  Dome Size     : {sim_cfg.get('flight_dome_size', 1000.0)}m")
    print(f"  Target Speed  : {BENCHMARK_TARGET_SPEED} m/s (P3C Test 2 Record)")
    print(f"  Random Seed   : {rnd_seed}")
    print(f"  Database      : {db_path}")
    print(f"{'=' * 75}\n")

    # Connect to SQLite DB
    db = ExperimentDB(db_path)
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")

    existing = db.get_experiment(eid)
    if existing is None:
        db.create_experiment(eid, config, now_iso)
    else:
        conn = db._conn()
        try:
            conn.execute(
                "UPDATE experiment_metadata SET status = 'running', start_time = ? WHERE experiment_id = ?",
                (now_iso, eid),
            )
            conn.commit()
        finally:
            conn.close()

    # Check for checkpoint resume
    chk_dir = os.path.join("output", "checkpoints")
    latest_chk = None
    latest_morph_chk = None
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
            gen_num = _chk_gen(latest_chk)
            morph_chk = os.path.join(chk_dir, f"{eid.lower()}-morph-{gen_num}.json")
            if os.path.isfile(morph_chk):
                latest_morph_chk = morph_chk

    # Initialize NEAT population and morphology dictionary
    morph_population: Dict[int, MorphologyGenome] = {}

    if latest_chk and os.path.isfile(latest_chk):
        print(f"[talos] Resuming co-evolution from NEAT checkpoint: {latest_chk}")
        pop = neat.Checkpointer.restore_checkpoint(latest_chk)
        pop.config.reset_on_extinction = True
        neat_cfg = pop.config
        if latest_morph_chk:
            print(f"[talos] Restoring morphology population from: {latest_morph_chk}")
            with open(latest_morph_chk, "r", encoding="utf-8") as f:
                saved_morphs = json.load(f)
                for gid_str, p_dict in saved_morphs.items():
                    morph_population[int(gid_str)] = MorphologyGenome.from_dict(p_dict, bounds=bounds)
    else:
        controller = NEATController(config)
        pop = controller.population
        neat_cfg = controller.config

    # Ensure all current genomes have a morphology
    for gid in pop.population.keys():
        if gid not in morph_population:
            if gid == 0:
                morph_population[gid] = MorphologyGenome(bounds=bounds)
            else:
                # Slight variation around default baseline for initial diversity
                morph_population[gid] = MorphologyGenome(bounds=bounds).mutate(rng, rate=0.4)

    start_time = time.time()
    all_time_best_fitness = (
        float(existing["best_fitness"])
        if existing and existing.get("best_fitness") is not None
        else -float("inf")
    )
    all_time_best_genome: Optional[neat.DefaultGenome] = None
    all_time_best_morph: Optional[MorphologyGenome] = None

    start_gen = pop.generation
    total_target_gens = start_gen + (num_gens - start_gen)

    try:
        while pop.generation < num_gens:
            cur_gen = pop.generation
            gen_start_time = time.time()

            # Dynamically reload config to catch live milestone/weight changes
            try:
                config = load_config(config_path)
                morph_cfg = config.get("morphology", {})
                bounds = morph_cfg.get("bounds", bounds)
                morph_mutate_rate = float(morph_cfg.get("mutation_rate", morph_mutate_rate))
            except Exception:
                pass

            # --------------------------------------------------------------
            # 1. Evaluate Every Co-Evolved Pair (Brain + Body)
            # --------------------------------------------------------------
            eval_results: Dict[int, Dict[str, Any]] = {}

            for gid, genome in pop.population.items():
                morph = morph_population.get(gid)
                if morph is None:
                    morph = MorphologyGenome(bounds=bounds)
                    morph_population[gid] = morph

                # Build physical airframe files
                ind_model_dir = os.path.join(models_dir, f"gen{cur_gen:03d}", f"ind{gid:03d}")
                generate_model_files(morph, ind_model_dir)

                # Initialize physics environment with multi-seed varying waypoint track
                env = FixedwingEnv(config=config, model_dir=ind_model_dir)
                ep_seed = rnd_seed + (cur_gen * 1000) + (gid % 1000)
                obs, _ = env.reset(seed=ep_seed)

                # Inject Hairpin & Slalom tracks starting from Hairpin Tier (Gen 350+)
                milestones = config.get("fitness", {}).get("curriculum_milestones", {})
                t_hairpin_milestone = int(milestones.get("tier_hairpin_generation", milestones.get("tier3_generation", 350)))
                if cur_gen >= t_hairpin_milestone or "TESTAROSSA" in eid.upper():
                    course_wp = _get_hairpin_tier_course(gid, cur_gen, eid=eid)
                    env.env.unwrapped.waypoints.targets = course_wp.copy()
                    env.env.unwrapped.waypoints.num_targets = len(course_wp)
                    env.env.unwrapped.compute_state()
                    obs = env._build_observation(env.env.unwrapped.state)

                net = neat.nn.FeedForwardNetwork.create(genome, neat_cfg)

                step = 0
                terminated = False
                truncated = False

                while not (terminated or truncated) and step < env.max_steps:
                    action = np.asarray(net.activate(obs), dtype=np.float32)
                    obs, _, terminated, truncated, _ = env.step(action)
                    step += 1

                metrics = env.get_metrics()
                env.close()

                # Clean up individual model directory to conserve disk space (champion is preserved)
                try:
                    shutil.rmtree(ind_model_dir, ignore_errors=True)
                except Exception:
                    pass

                # Compute fitness via 3-tier curriculum
                fit_details = compute_fitness_detailed(metrics, config, generation=cur_gen)
                fit_val = float(fit_details["fitness"])
                genome.fitness = fit_val

                eval_results[gid] = {
                    "fitness": fit_val,
                    "metrics": metrics,
                    "components": fit_details["components"],
                }

            # --------------------------------------------------------------
            # 2. Extract Generation Stats & Champion
            # --------------------------------------------------------------
            fitnesses = [g.fitness for g in pop.population.values() if g.fitness is not None]
            best_gid, best_genome = max(pop.population.items(), key=lambda item: item[1].fitness or -999.0)
            best_morph = morph_population[best_gid]
            best_eval = eval_results[best_gid]
            best_metrics = best_eval["metrics"]

            best_fit = float(np.max(fitnesses))
            mean_fit = float(np.mean(fitnesses))
            med_fit = float(np.median(fitnesses))
            worst_fit = float(np.min(fitnesses))
            std_fit = float(np.std(fitnesses))

            best_enabled_conns = sum(1 for c in best_genome.connections.values() if c.enabled)
            best_nodes = len(best_genome.nodes)
            mean_nodes = float(np.mean([len(g.nodes) for g in pop.population.values()]))
            mean_conns = float(
                np.mean([sum(1 for c in g.connections.values() if c.enabled) for g in pop.population.values()])
            )
            species_count = len(pop.species.species)
            population_alive = len(fitnesses)

            # Persist champion model files
            champ_model_dir = os.path.join(models_dir, f"gen{cur_gen:03d}", "champion")
            generate_model_files(best_morph, champ_model_dir)

            # Record champion flight trajectory
            champ_env = FixedwingEnv(config=config, model_dir=champ_model_dir)
            champ_net = neat.nn.FeedForwardNetwork.create(best_genome, neat_cfg)
            champ_course = _get_hairpin_tier_course(0, cur_gen, eid=eid) if (cur_gen >= t_hairpin_milestone or "TESTAROSSA" in eid.upper()) else None
            champ_flight = _record_coevo_champion_flight(
                env=champ_env,
                net=champ_net,
                seed=rnd_seed,
                experiment_id=eid,
                generation=cur_gen,
                morph_dict=best_morph.to_dict(),
                custom_waypoints=champ_course,
            )
            champ_env.close()

            # --------------------------------------------------------------
            # 3. Log to SQLite (icarus.db)
            # --------------------------------------------------------------
            gen_stats = {
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
                "best_survival_time": champ_flight["flight_time"],
                "best_distance": champ_flight["distance"],
                "best_energy": champ_flight["energy"],
                "best_waypoint_time": champ_flight["flight_time"],
            }
            db.log_generation(eid, cur_gen, gen_stats)

            ctrl_json = serialize_genome(best_genome, neat_cfg)
            ind_data = {
                "fitness": best_fit,
                "is_elite": True,
                "survival_time": champ_flight["flight_time"],
                "distance": champ_flight["distance"],
                "energy": champ_flight["energy"],
                "waypoint_time": champ_flight["flight_time"],
                "altitude_error": champ_flight["altitude_error"],
                "airspeed_error": champ_flight["airspeed_error"],
                "crashed": champ_flight["crashed"],
                "stalling": champ_flight["stalling"],
                "nodes": best_nodes,
                "connections": best_enabled_conns,
                "species_id": getattr(best_genome, "species_id", 0),
                "morphology_json": json.dumps(best_morph.to_dict()),
                "controller_json": ctrl_json,
            }
            db.log_individual(eid, cur_gen, index=0, data=ind_data)

            # Export live trajectory for dashboard
            os.makedirs("output", exist_ok=True)
            try:
                with open(os.path.join("output", f"{eid.lower()}_trajectory.json"), "w", encoding="utf-8") as fh:
                    json.dump(champ_flight, fh, indent=2)
            except Exception:
                pass

            # Update all-time best
            if best_fit > all_time_best_fitness:
                all_time_best_fitness = best_fit
                all_time_best_genome = best_genome
                all_time_best_morph = best_morph
                db.update_best(eid, best_fit, cur_gen)

                try:
                    with open(os.path.join("output", "b0_trajectory.json"), "w", encoding="utf-8") as fh:
                        json.dump(champ_flight, fh, indent=2)
                except Exception:
                    pass

            # Console reporting
            milestones = config.get("fitness", {}).get("curriculum_milestones", {})
            t2_milestone = int(milestones.get("tier2_generation", 60))
            t_hairpin_milestone = int(milestones.get("tier_hairpin_generation", milestones.get("tier3_generation", 350)))
            t4_milestone = int(milestones.get("tier4_generation", 550))
            if cur_gen >= t4_milestone:
                tier_name = "T4 APEX"
            elif cur_gen >= t_hairpin_milestone:
                tier_name = "T3 HAIRPIN"
            elif cur_gen >= t2_milestone:
                tier_name = "T2 GUIDED"
            else:
                tier_name = "T1 BASE"
            elapsed = time.time() - gen_start_time
            total_gates = 12 if "TESTAROSSA" in eid.upper() else 4
            print(
                f"[{eid}] Gen {cur_gen:3d} ({tier_name}) | "
                f"BestFit: {best_fit:6.2f} | MeanFit: {mean_fit:6.2f} | "
                f"Gates: {champ_flight['waypoints_hit']}/{total_gates} | "
                f"Spd: {champ_flight['mean_airspeed']:4.1f}m/s | "
                f"Dist: {champ_flight['distance']:5.1f}m | "
                f"Crash: {str(champ_flight['crashed']):<5} | "
                f"Time: {elapsed:4.1f}s"
            )
            sys.stdout.flush()

            # Checkpoint every 5 generations
            if cur_gen % 5 == 0 or cur_gen == num_gens - 1:
                chk_prefix = os.path.join("output", "checkpoints", f"{eid.lower()}-chk-{cur_gen}")
                pop.reporters.start_generation(cur_gen)
                neat.Checkpointer(1, filename_prefix=os.path.join("output", "checkpoints", f"{eid.lower()}-chk-")).save_checkpoint(
                    neat_cfg, pop.population, pop.species, cur_gen
                )
                # Save morphology population checkpoint
                morph_chk_path = os.path.join("output", "checkpoints", f"{eid.lower()}-morph-{cur_gen}.json")
                with open(morph_chk_path, "w", encoding="utf-8") as fh:
                    json.dump({str(k): v.to_dict() for k, v in morph_population.items()}, fh, indent=2)

            # --------------------------------------------------------------
            # 4. Reproduce Next Generation with Symbiotic Co-Inheritance
            # --------------------------------------------------------------
            # Let NEAT advance controller population
            pop.species.speciate(neat_cfg, pop.population, pop.generation)
            new_controllers = pop.reproduction.reproduce(
                neat_cfg, pop.species, neat_cfg.pop_size, pop.generation
            )

            # Build synchronized offspring morphology population using ancestor tracking
            new_morph_pop: Dict[int, MorphologyGenome] = {}
            for new_gid, new_genome in new_controllers.items():
                if new_gid in morph_population:
                    # Retained elite survives unchanged (clamped to active bounds)
                    m_existing = morph_population[new_gid]
                    new_morph_pop[new_gid] = MorphologyGenome(params=m_existing.params, bounds=bounds)
                elif hasattr(pop.reproduction, "ancestors") and new_gid in pop.reproduction.ancestors:
                    # Sexual or asexual offspring: crossover and mutate parents' morphologies
                    p1_id, p2_id = pop.reproduction.ancestors[new_gid]
                    m1 = morph_population.get(p1_id, best_morph)
                    m2 = morph_population.get(p2_id, m1)
                    child_morph = m1.crossover(m2, rng=rng).mutate(rng, rate=morph_mutate_rate)
                    new_morph_pop[new_gid] = MorphologyGenome(params=child_morph.params, bounds=bounds)
                else:
                    # Fresh innovation fallback
                    mutated = best_morph.mutate(rng, rate=morph_mutate_rate)
                    new_morph_pop[new_gid] = MorphologyGenome(params=mutated.params, bounds=bounds)

            morph_population = new_morph_pop
            pop.population = new_controllers
            pop.generation += 1

    except KeyboardInterrupt:
        print(f"\n[talos] Co-evolution interrupted by user. Finalizing records...")
    finally:
        end_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
        db.complete_experiment(eid, end_iso)

    print(f"\n{'=' * 75}")
    print(f"  CO-EVOLUTION COMPLETED / FINALIZED: {eid}")
    print(f"  All-Time Best Fitness: {all_time_best_fitness:6.2f}")
    print(f"  Total Duration       : {time.time() - start_time:6.1f}s")
    print(f"  Database Path        : {db_path}")
    print(f"{'=' * 75}\n")

    return all_time_best_genome, all_time_best_morph
