"""Fitness evaluation for individual aircraft + controller genomes."""
from __future__ import annotations

from typing import Any, Dict, List

import numpy as np

from .env import FixedwingEnv
from src.genome.controller import NEATController


# ---------------------------------------------------------------------------
# Fitness decomposition
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Fitness decomposition & 3-Tier Evolutionary Curriculum
# ---------------------------------------------------------------------------

BENCHMARK_TARGET_SPEED = 49.2  # m/s (P3C Gen 300 Test 2 Record)

def compute_fitness_detailed(
    metrics: Dict[str, Any],
    config: Dict[str, Any],
    generation: int = 0,
) -> Dict[str, Any]:
    """Compute decomposed and scalar fitness across the 3-tier curriculum.

    Tier 1 (Gen 0 - 59 in 600-gen run):
        Baseline viability & airworthiness: survival, basic lift, anti-stall.
    Tier 2 (Gen 60 - 499 in 600-gen run):
        Post-Gen 60 guided navigation: altitude tracking, moderate waypoint
        incentives, and progressive speedup toward cruise regime.
    Tier 3 (Gen 500+ in 600-gen run):
        Endgame Beast Mode: heavily rewarded 4/4 waypoint gate capture and
        speed benchmarked directly against the P3C Test 2 record (49.2 m/s).
    """
    episode_duration = float(config.get("simulation", {}).get("episode_duration", 20.0))
    fitness_cfg = config.get("fitness", {})
    weights = fitness_cfg.get("weights", {})
    penalties = fitness_cfg.get("penalties", {})

    flight_time = float(metrics.get("flight_time", 0.0))
    survival_score = min(flight_time / max(1.0, episode_duration), 1.0)

    energy = float(metrics.get("energy", 0.0))
    efficiency_score = 1.0 - min(energy / 100.0, 1.0)

    distance = float(metrics.get("distance", 0.0))
    maneuver_score = min(distance / 500.0, 1.0)

    alt_err = float(metrics.get("altitude_error", 2.0))
    altitude_score = float(np.exp(-0.8 * alt_err))

    airspeed = float(metrics.get("mean_airspeed", metrics.get("airspeed", 0.0)))
    wp_hits = int(metrics.get("waypoints_hit", 0))
    progress_to_wp = float(metrics.get("progress_to_wp", 0.0))
    crashed = bool(metrics.get("crashed", False))
    stalling = bool(metrics.get("stalling", False))

    components: Dict[str, float] = {
        "survival": survival_score,
        "efficiency": efficiency_score,
        "maneuverability": maneuver_score,
        "altitude": altitude_score,
        "airspeed": airspeed,
        "waypoints_hit": float(wp_hits),
    }

    milestones = fitness_cfg.get("curriculum_milestones", {})
    tier2_threshold = int(milestones.get("tier2_generation", 60))
    tier_hairpin_threshold = int(milestones.get("tier_hairpin_generation", milestones.get("tier3_generation", 350)))
    tier4_threshold = int(milestones.get("tier4_generation", 550))

    if generation >= tier4_threshold:
        # ------------------------------------------------------------------
        # Tier 4 (Gen 550+ in 600-gen run): APEX MASTERY & PRECISION AEROBATICS
        # ------------------------------------------------------------------
        # Full Tier 3 high-speed sprint + 4-gate capture + glide energy polish
        gate_rewards = [0.0, 25.0, 60.0, 120.0, 260.0]
        wp_score_heavy = gate_rewards[min(wp_hits, 4)]
        components["waypoint_reward"] = wp_score_heavy

        # Unconstrained speed benchmarked to 49.2 m/s
        if airspeed <= BENCHMARK_TARGET_SPEED:
            speed_raw = 35.0 * float((airspeed / BENCHMARK_TARGET_SPEED) ** 2)
        else:
            delta_v = airspeed - BENCHMARK_TARGET_SPEED
            speed_raw = 35.0 + 18.0 * float(delta_v ** 1.15)

        if crashed:
            speed_beast = 0.0
        else:
            compliance = 0.30 + 0.70 * (min(wp_hits, 4) / 4.0)
            speed_beast = speed_raw * compliance
        components["speed_reward"] = speed_beast

        # Cherry on top: Precision altitude tracking + glide efficiency
        precision_alt = 25.0 * float(np.exp(-1.2 * alt_err))
        efficiency_term = 20.0 * efficiency_score
        surv_term = 15.0 * survival_score
        components["altitude_term"] = precision_alt
        components["efficiency_term"] = efficiency_term
        components["survival_term"] = surv_term

        # Grand Slam 4/4 Clean Sweep Bounty
        grand_slam = 50.0 if (wp_hits >= 4 and not crashed) else 0.0
        components["grand_slam_bounty"] = grand_slam

        raw = wp_score_heavy + speed_beast + precision_alt + efficiency_term + surv_term + grand_slam

        if crashed:
            raw += penalties.get("crash", -100.0)
        if stalling:
            raw += penalties.get("stall", -5.0)

        final_fitness = float(np.clip(raw, -200.0, 550.0))

    elif generation >= tier_hairpin_threshold:
        # ------------------------------------------------------------------
        # Tier 3 (Gen 350+): SPEED-SCALED WAYPOINT CAPTURE & ZERO-TOLERANCE CRASH
        # Fast gate conquest: Waypoint reward scales directly with crossing airspeed!
        # Crashing, stalling, or clipping instantly zeros out all positive points.
        # ------------------------------------------------------------------
        # 1. Base Gate Capture Milestones (supports up to 12 gates for Grand Prix)
        # Scaled progressively: each sequential gate passed provides substantial points
        gate_rewards = [0.0, 35.0, 75.0, 120.0, 170.0, 225.0, 285.0, 350.0, 420.0, 500.0, 590.0, 690.0, 800.0]
        base_wp_reward = gate_rewards[min(wp_hits, len(gate_rewards) - 1)]

        # 2. Speed Scaling Multiplier for Waypoints:
        # If you hit waypoints, you get the speed you were at as a direct bonus!
        # Crossing at high speed scales up the waypoint reward:
        speed_factor = float(np.clip(airspeed / BENCHMARK_TARGET_SPEED, 0.20, 1.80))
        wp_score_heavy = base_wp_reward * (0.25 + 0.75 * speed_factor)
        components["waypoint_reward"] = wp_score_heavy

        # 3. Direct Speed Sprint Reward
        if airspeed <= BENCHMARK_TARGET_SPEED:
            speed_raw = 50.0 * float((airspeed / BENCHMARK_TARGET_SPEED) ** 1.5)
        else:
            delta_v = airspeed - BENCHMARK_TARGET_SPEED
            speed_raw = 50.0 + 25.0 * float(delta_v ** 1.1)

        # 4. Altitude Discipline Factor: exp(-1.2 * alt_err)
        alt_discipline = float(np.exp(-1.2 * max(0.0, alt_err)))
        components["alt_discipline"] = alt_discipline
        speed_coupled = speed_raw * alt_discipline
        components["speed_reward"] = speed_coupled

        # 5. Maneuverability & Waypoint Tracking Closure
        wp_progress_norm = min(progress_to_wp / 100.0, 1.0)
        min_wp_dist = float(metrics.get("min_waypoint_dist", 999.0))
        proximity_score = float(np.exp(-0.04 * min(min_wp_dist, 100.0)))
        maneuver_term = 15.0 * wp_progress_norm + 15.0 * proximity_score
        components["maneuver_term"] = maneuver_term

        # 6. Altitude Tracking & Survival
        alt_term = 25.0 * alt_discipline
        surv_term = 20.0 * survival_score
        components["altitude_term"] = alt_term
        components["survival_term"] = surv_term

        # 7. Grand Clean Sweep Completion Bounty (150 pts for full course completion)
        clean_sweep_bounty = 150.0 if (wp_hits >= 11 and not crashed) else (50.0 if (wp_hits >= 4 and not crashed) else 0.0)
        components["clean_sweep_bounty"] = clean_sweep_bounty

        # 8. INSTANT ZERO FOR CRASH, STALL, OR GROUND CLIPS:
        # If the aircraft crashes or stalls, all accumulated positive reward is wiped out!
        if crashed or stalling:
            raw = penalties.get("crash", -200.0) if crashed else penalties.get("stall", -50.0)
        else:
            raw = wp_score_heavy + speed_coupled + maneuver_term + alt_term + surv_term + clean_sweep_bounty

        final_fitness = float(np.clip(raw, -250.0, 1200.0))

    elif generation >= tier2_threshold:
        # ------------------------------------------------------------------
        # Tier 2 (Gen 60 - 499 in 600-gen run): INTERMEDIATE GUIDED NAVIGATION
        # ------------------------------------------------------------------
        # Moderate waypoint reward: progressive closing + gate bonuses
        wp_progress_norm = min(progress_to_wp / 100.0, 1.0)
        wp_mod_score = 0.20 * wp_progress_norm + 0.80 * (min(wp_hits, 4) / 4.0)
        components["waypoint_reward"] = wp_mod_score

        # Progressive speed ramp-up towards 35 m/s
        speed_base = min(airspeed / 35.0, 1.0)
        components["speed_reward"] = speed_base

        raw = (
            0.20 * survival_score
            + 0.25 * altitude_score
            + 0.15 * speed_base
            + 0.25 * wp_mod_score
            + 0.15 * efficiency_score
        )

        # Penalties
        if crashed:
            raw += penalties.get("crash", -100.0)
        if stalling:
            raw += penalties.get("stall", -5.0)

        final_fitness = float(np.clip(raw, -200.0, 150.0))

    else:
        # ------------------------------------------------------------------
        # Tier 1 (Gen 0 - 34): EARLY AIRWORTHINESS FOUNDATION
        # ------------------------------------------------------------------
        raw = (
            weights.get("survival", 0.4) * survival_score
            + weights.get("efficiency", 0.3) * efficiency_score
            + weights.get("maneuverability", 0.3) * maneuver_score
        )

        # Penalties
        if crashed:
            raw += penalties.get("crash", -100.0)
        if stalling:
            raw += penalties.get("stall", -5.0)

        final_fitness = float(np.clip(raw, -200.0, 100.0))

    return {
        "fitness": final_fitness,
        "components": components,
        "generation": generation,
    }


def compute_fitness(
    metrics: Dict[str, Any],
    config: Dict[str, Any],
    generation: int = 0,
) -> float:
    """Combine raw flight metrics into a scalar fitness score across curriculum tiers."""
    detailed = compute_fitness_detailed(metrics, config, generation=generation)
    return float(detailed["fitness"])


# ---------------------------------------------------------------------------
# Individual evaluation
# ---------------------------------------------------------------------------

def evaluate_individual(
    controller: NEATController,
    genome_key: int,
    config: Dict[str, Any],
    model_dir: str | None = None,
    num_episodes: int | None = None,
    seed: int | None = None,
    generation: int = 0,
) -> Dict[str, Any]:
    """Evaluate a single NEAT genome over one or more episodes.

    Parameters
    ----------
    controller : NEATController
        Wrapper exposing ``activate(genome_key, obs)``.
    genome_key : int
        Key of the genome inside the NEAT population.
    config : dict
        Experiment configuration.
    model_dir : str | None
        Morphology model directory, if any.
    num_episodes : int | None
        Override for number of episodes (default from config).
    seed : int | None
        Base random seed.

    Returns
    -------
    dict
        Aggregated metrics, fitness, and fitness components.
    """
    num_episodes = num_episodes or int(
        config["simulation"].get("num_episodes_per_eval", 3)
    )

    all_metrics: List[Dict[str, Any]] = []

    for episode in range(num_episodes):
        env = FixedwingEnv(
            config=config,
            model_dir=model_dir,
        )

        episode_seed = None if seed is None else seed + episode
        obs, _ = env.reset(seed=episode_seed)

        terminated = False
        truncated = False
        step_metrics: List[Dict[str, Any]] = []

        while not (terminated or truncated):
            action = controller.activate(genome_key, obs)
            obs, _, terminated, truncated, info = env.step(action)
            step_metrics.append(info)

        env_metrics = env.get_metrics()
        all_metrics.append(env_metrics)

        # Close environment to free physics resources
        try:
            env.env.close()
        except Exception:
            pass

    # Aggregate across episodes
    aggregated = _aggregate_episodes(all_metrics)

    detailed = compute_fitness_detailed(aggregated, config, generation=generation)
    aggregated["fitness"] = detailed["fitness"]
    aggregated["fitness_components"] = detailed["components"]

    return aggregated


# ---------------------------------------------------------------------------
# Batch evaluation (placeholder for pool-based parallelism)
# ---------------------------------------------------------------------------

def evaluate_population(
    controller: NEATController,
    config: Dict[str, Any],
    model_dir: str | None = None,
    seeds: List[int] | None = None,
) -> Dict[int, Dict[str, Any]]:
    """Evaluate all genomes in the population sequentially (setup fallback)."""
    results: Dict[int, Dict[str, Any]] = {}

    for genome_key in controller.population.population:
        individual_seed = None
        if seeds is not None:
            individual_seed = seeds[genome_key % len(seeds)]

        results[genome_key] = evaluate_individual(
            controller=controller,
            genome_key=genome_key,
            config=config,
            model_dir=model_dir,
            num_episodes=1,  # Dev mode: single episode
            seed=individual_seed,
        )

    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _aggregate_episodes(
    episodes: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Average numeric metrics across episodes; keep flags as 'any'."""
    if not episodes:
        return {}

    numeric: Dict[str, List[float]] = {}
    flags: Dict[str, List[bool]] = {}

    for ep in episodes:
        for key, value in ep.items():
            if isinstance(value, bool):
                flags.setdefault(key, []).append(value)
            elif isinstance(value, (int, float)) and key != "fitness":
                numeric.setdefault(key, []).append(float(value))

    aggregated: Dict[str, Any] = {}
    for key, values in numeric.items():
        aggregated[key] = float(np.mean(values))

    for key, values in flags.items():
        aggregated[key] = bool(any(values))

    return aggregated