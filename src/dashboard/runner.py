"""Flight execution and replay runner for the Talos dashboard.

Executes a single visual or headless flight demonstration for a requested
experiment (baseline PID, best evolved individual, or specific generation)
and extracts the 3D trajectory and telemetry for the web dashboard.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

import numpy as np

from src.experiment.db import ExperimentDB
from src.experiment.metadata import load_config
from src.simulation.env import FixedwingEnv
from src.simulation.pid_controller import FixedwingPIDController


def run_best_model(
    experiment_id: str,
    db_path: str = os.path.join("output", "icarus.db"),
    render: bool = False,
    episodes: int = 1,
    generation: Optional[int] = None,
) -> Dict[str, Any]:
    """Execute a flight run for the best/final model of an experiment.

    Parameters
    ----------
    experiment_id : str
        ID of the experiment to run (e.g. 'B0_baseline_pid').
    db_path : str
        Path to the SQLite database.
    render : bool
        If True, opens the PyBullet 3D visualization window ('human').
    episodes : int
        Number of episodes to execute (default: 1).

    Returns
    -------
    dict
        Flight summary containing metrics, trajectory coordinates, and status.
    """
    render_mode = "human" if render else None
    eid_lower = experiment_id.lower()

    # ------------------------------------------------------------------
    # Baseline PID Flight
    # ------------------------------------------------------------------
    if "baseline" in eid_lower or eid_lower.startswith("b0"):
        config_path = os.path.join("configs", "baselines", "b0_default_pid.json")
        if not os.path.isfile(config_path):
            config_path = os.path.join("configs", "baselines", "b0_default_pid.json")
        config = load_config(config_path) if os.path.isfile(config_path) else {
            "simulation": {"episode_duration": 10.0, "control_hz": 120}
        }
        if render_mode:
            config["simulation"]["render_mode"] = render_mode

        env = FixedwingEnv(config=config, model_dir=None)
        pid = FixedwingPIDController(dt=1.0 / env.control_hz)

        obs, _ = env.reset(seed=42)
        pid.reset()

        trajectory: List[Dict[str, float]] = []
        terminated = False
        truncated = False
        step = 0

        while not (terminated or truncated) and step < env.max_steps:
            action = pid.predict(obs)
            obs, _, terminated, truncated, info = env.step(action)
            step += 1

            # Sample trajectory every 4 steps to keep payload compact
            if step % 4 == 0:
                trajectory.append({
                    "step": step,
                    "x": float(obs[9]),
                    "y": float(obs[10]),
                    "z": float(obs[11]),
                    "roll": float(obs[3]),
                    "pitch": float(obs[4]),
                    "yaw": float(obs[5]),
                    "airspeed": float(info.get("airspeed", 20.0)),
                    "thrust": float(info.get("throttle", 0.8)),
                })

        metrics = env.get_metrics()
        try:
            env.env.close()
        except Exception:
            pass

        return {
            "status": "success",
            "experiment_id": experiment_id,
            "type": "baseline_pid",
            "rendered": render,
            "flight_time": metrics.get("flight_time", 0.0),
            "distance": metrics.get("distance", 0.0),
            "crashed": metrics.get("crashed", False),
            "stalling": metrics.get("stalling", False),
            "altitude_error": metrics.get("altitude_error", 0.0),
            "airspeed_error": metrics.get("airspeed_error", 0.0),
            "trajectory": trajectory,
            "message": "Baseline PID flight executed successfully.",
        }

    # ------------------------------------------------------------------
    # Evolutionary Individual Flight
    # ------------------------------------------------------------------
    db = ExperimentDB(db_path)
    lookup_id = experiment_id

    if eid_lower in ("c1", "controller_only"):
        lookup_id = "C1"
    elif eid_lower in ("co1", "coevolution"):
        lookup_id = "TALOS-P4-ULTIMA"

    if generation is not None:
        inds = db.get_individuals(lookup_id, generation=generation)
        best_ind = max(inds, key=lambda x: x.get("fitness", -999)) if inds else None
    else:
        best_ind = db.get_best_individual(lookup_id)

    if best_ind is None:
        return {
            "status": "no_data",
            "experiment_id": experiment_id,
            "type": "evolutionary",
            "message": f"No evaluated individuals found for '{experiment_id}' yet. Run evolution first.",
            "trajectory": [],
        }

    ctrl_json = best_ind.get("controller_json")
    if not ctrl_json:
        return {
            "status": "no_controller",
            "experiment_id": experiment_id,
            "type": "evolutionary",
            "message": "Individual metadata did not contain controller network structure.",
            "trajectory": [],
        }

    # Reconstruct controller and simulate flight
    try:
        import neat
        from src.genome.controller import NEATController
        ctrl_data = json.loads(ctrl_json)

        cfg_path = os.path.join("configs", "coevolution", "p4_ultima_coevo.json")
        if not os.path.isfile(cfg_path):
            cfg_path = os.path.join("configs", "controller_only", "c1_controller_only.json")
        config = load_config(cfg_path) if os.path.isfile(cfg_path) else {
            "simulation": {"episode_duration": 20.0, "control_hz": 30},
            "controller": {"num_inputs": 15, "num_outputs": 6, "activation": "tanh", "output_activation": "sigmoid"},
            "neat_config": {"pop_size": 50},
        }
        if render_mode:
            config["simulation"]["render_mode"] = render_mode

        ctrl = NEATController(config)
        neat_cfg = ctrl.config

        genome = neat.DefaultGenome(ctrl_data.get("id", 0))
        genome.fitness = best_ind["fitness"]

        for nd in ctrl_data.get("nodes", []):
            nid = nd["id"]
            if nid >= 0:
                node_gene = neat_cfg.genome_config.node_gene_type(nid)
                node_gene.bias = nd["bias"]
                node_gene.activation = nd.get("activation", "tanh")
                node_gene.aggregation = "sum"
                node_gene.response = nd.get("response", 1.0)
                genome.nodes[nid] = node_gene

        for idx, cn in enumerate(ctrl_data.get("connections", [])):
            key = (cn["from"], cn["to"])
            conn_gene = neat_cfg.genome_config.connection_gene_type(key, innovation=idx)
            conn_gene.weight = cn["weight"]
            conn_gene.enabled = cn.get("enabled", True)
            genome.connections[key] = conn_gene

        net = neat.nn.FeedForwardNetwork.create(genome, neat_cfg)

        model_dir = None
        morph_json = best_ind.get("morphology_json")
        if morph_json:
            try:
                from src.genome.morphology import MorphologyGenome
                from src.genome.urdf_gen import generate_model_files
                m_dict = json.loads(morph_json)
                if m_dict and isinstance(m_dict, dict) and "wingspan" in m_dict:
                    m_genome = MorphologyGenome.from_dict(m_dict)
                    model_dir = os.path.abspath(os.path.join("models", "_dashboard_temp"))
                    os.makedirs(model_dir, exist_ok=True)
                    generate_model_files(m_genome, model_dir)
            except Exception:
                model_dir = None

        env = FixedwingEnv(config=config, model_dir=model_dir)
        obs, _ = env.reset(seed=42)

        trajectory: List[Dict[str, float]] = []
        terminated = False
        truncated = False
        step = 0

        while not (terminated or truncated) and step < env.max_steps:
            act = np.asarray(net.activate(obs), dtype=np.float32)
            obs, _, terminated, truncated, info = env.step(act)
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
                    "thrust": float(act[5] if len(act) > 5 else 0.0),
                })

        metrics = env.get_metrics()
        try:
            env.env.close()
        except Exception:
            pass

        return {
            "status": "success",
            "experiment_id": experiment_id,
            "type": "evolutionary",
            "individual_id": best_ind.get("id"),
            "generation": best_ind.get("generation"),
            "fitness": best_ind.get("fitness"),
            "flight_time": metrics.get("flight_time", best_ind.get("survival_time", 0.0)),
            "distance": metrics.get("distance", best_ind.get("distance", 0.0)),
            "crashed": metrics.get("crashed", False),
            "stalling": metrics.get("stalling", False),
            "altitude_error": metrics.get("altitude_error", 0.0),
            "airspeed_error": metrics.get("airspeed_error", 0.0),
            "trajectory": trajectory,
            "message": f"Flight simulation completed for Gen {best_ind.get('generation')} champion (Fitness: {best_ind.get('fitness'):.2f}).",
        }

    except Exception as exc:
        return {
            "status": "success",
            "experiment_id": experiment_id,
            "type": "evolutionary",
            "individual_id": best_ind.get("id"),
            "generation": best_ind.get("generation"),
            "fitness": best_ind.get("fitness"),
            "survival_time": best_ind.get("survival_time", 0.0),
            "flight_time": best_ind.get("survival_time", 0.0),
            "distance": best_ind.get("distance", 0.0),
            "crashed": bool(best_ind.get("crashed", False)),
            "stalling": bool(best_ind.get("stalling", False)),
            "altitude_error": float(best_ind.get("altitude_error", 0.0)),
            "airspeed_error": float(best_ind.get("airspeed_error", 0.0)),
            "trajectory": [],
            "message": f"Loaded Gen {best_ind.get('generation')} champion record (fallback: {exc}).",
        }
