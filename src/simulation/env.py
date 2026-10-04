"""Fixedwing environment wrapper for PyFlyt.

Wraps PyFlyt's ``Fixedwing-Waypoints-v3`` with a clean Gymnasium-like API.

- Observation space: 15 floats (12 native state + 3 waypoint offset)
- Action space: 6 floats [left_aileron, right_aileron, elevator,
  rudder, main_wing_flap, thrust]
"""
from __future__ import annotations

import os
import shutil
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

try:
    import gymnasium as gym
    import PyFlyt.gym_envs  # noqa: F401 - registers PyFlyt gymnasium environments
    from PyFlyt.gym_envs.fixedwing_envs.fixedwing_base_env import FixedwingBaseEnv

    # Ensure FixedwingBaseEnv forwards options['drone_options'] to Aviary
    _orig_begin_reset = FixedwingBaseEnv.begin_reset

    def _patched_begin_reset(self, seed=None, options=None, drone_options=None):
        if options is not None and "drone_options" in options:
            if drone_options is None:
                drone_options = {}
            drone_options.update(options["drone_options"])
        return _orig_begin_reset(self, seed=seed, options=options, drone_options=drone_options)

    FixedwingBaseEnv.begin_reset = _patched_begin_reset
except ImportError:
    gym = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_NATIVE_OBS_SIZE = 12
_NUM_CONTROL_AXES = 6
_WAYPOINT_OFFSET_SIZE = 3

INPUT_NAMES = [
    "ang_vel_p",
    "ang_vel_q",
    "ang_vel_r",
    "roll",
    "pitch",
    "yaw",
    "lin_vel_u",
    "lin_vel_v",
    "lin_vel_w",
    "pos_x",
    "pos_y",
    "pos_z",
    "waypoint_dx",
    "waypoint_dy",
    "waypoint_dz",
]

ACTION_NAMES = [
    "left_aileron",
    "right_aileron",
    "elevator",
    "rudder",
    "main_wing_flap",
    "thrust",
]


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

class FixedwingEnv:
    """Gymnasium-style wrapper around PyFlyt Fixedwing-Waypoints-v3.

    Parameters
    ----------
    config : dict
        Experiment configuration containing the ``simulation`` block.
    model_dir : str | None
        Directory containing ``drone_model``.urdf and ``.yaml`` files.
        If ``None``, PyFlyt's built-in default fixedwing model is used.
    drone_model : str
        Base name of the model files (without extension).
    """

    def __init__(
        self,
        config: Dict[str, Any],
        model_dir: Optional[str] = None,
        drone_model: str = "fixedwing",
    ) -> None:
        if gym is None:
            raise ImportError(
                "gymnasium and PyFlyt are required. Install with: pip install pyflyt gymnasium"
            )

        self.config = config
        sim_cfg = config.get("simulation", {})

        self.episode_duration = float(sim_cfg.get("episode_duration", 10.0))
        self.control_hz = int(sim_cfg.get("control_hz", 30))
        self.physics_hz = int(sim_cfg.get("physics_hz", 240))
        self.max_steps = int(self.episode_duration * self.control_hz)

        self.render_mode = sim_cfg.get("render_mode", None)

        # Model paths
        self._model_dir = model_dir
        self._drone_model = drone_model
        self._urdf_path: Optional[str] = None
        self._yaml_path: Optional[str] = None
        self._aviary_model_dir: Optional[str] = None
        self._aviary_drone_model: Optional[str] = None

        if model_dir is not None:
            # PyFlyt expects: os.path.join(model_dir, f"{drone_model}/{drone_model}.urdf")
            if os.path.isfile(os.path.join(model_dir, drone_model, f"{drone_model}.urdf")):
                self._aviary_model_dir = os.path.abspath(model_dir)
                self._aviary_drone_model = drone_model
                self._urdf_path = os.path.join(model_dir, drone_model, f"{drone_model}.urdf")
                self._yaml_path = os.path.join(model_dir, drone_model, f"{drone_model}.yaml")
            elif os.path.basename(os.path.abspath(model_dir)) == drone_model and os.path.isfile(os.path.join(model_dir, f"{drone_model}.urdf")):
                self._aviary_model_dir = os.path.dirname(os.path.abspath(model_dir))
                self._aviary_drone_model = drone_model
                self._urdf_path = os.path.join(model_dir, f"{drone_model}.urdf")
                self._yaml_path = os.path.join(model_dir, f"{drone_model}.yaml")
            elif os.path.isfile(os.path.join(model_dir, f"{drone_model}.urdf")):
                # Wrap inside drone_model subfolder so PyFlyt's hardcoded path finds it
                sub_dir = os.path.join(model_dir, drone_model)
                os.makedirs(sub_dir, exist_ok=True)
                shutil.copy2(os.path.join(model_dir, f"{drone_model}.urdf"), os.path.join(sub_dir, f"{drone_model}.urdf"))
                if os.path.isfile(os.path.join(model_dir, f"{drone_model}.yaml")):
                    shutil.copy2(os.path.join(model_dir, f"{drone_model}.yaml"), os.path.join(sub_dir, f"{drone_model}.yaml"))
                self._aviary_model_dir = os.path.abspath(model_dir)
                self._aviary_drone_model = drone_model
                self._urdf_path = os.path.join(sub_dir, f"{drone_model}.urdf")
                self._yaml_path = os.path.join(sub_dir, f"{drone_model}.yaml")
            else:
                raise FileNotFoundError(f"URDF not found in {model_dir}: expected {drone_model}.urdf")

            if not os.path.isfile(self._yaml_path):
                raise FileNotFoundError(f"YAML not found: {self._yaml_path}")

        # PyFlyt environment
        env_id = _resolve_env_id(sim_cfg)
        kwargs: Dict[str, Any] = {
            "render_mode": self.render_mode,
            "agent_hz": self.control_hz,
            "max_duration_seconds": self.episode_duration,
            "angle_representation": "euler",
        }
        if "flight_dome_size" in sim_cfg:
            kwargs["flight_dome_size"] = float(sim_cfg["flight_dome_size"])

        self.env = gym.make(env_id, **kwargs)

        # Step metrics buffer
        self._step_metrics: List[Dict[str, float]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reset(
        self, seed: Optional[int] = None
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Reset the environment and return the augmented observation.

        Returns
        -------
        obs : np.ndarray, shape (15,)
            Native state (12) + waypoint offset (3).
        info : dict
            Environment info dict.
        """
        options: Dict[str, Any] = {}
        if self._model_dir is not None:
            options["drone_options"] = {
                "model_dir": self._aviary_model_dir if self._aviary_model_dir is not None else self._model_dir,
                "drone_model": self._aviary_drone_model if self._aviary_drone_model is not None else self._drone_model,
            }

        obs, info = self.env.reset(seed=seed, options=options)

        # Configure drone for 6-axis surface control mode (-1)
        try:
            self.env.unwrapped.env.set_mode(-1)
        except Exception:
            pass

        self._step_metrics = []
        self._step_count = 0
        self.env.unwrapped.step_count = 0
        return self._build_observation(obs), info

    def step(
        self, action: Sequence[float]
    ) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        """Advance the simulation by one control step.

        Parameters
        ----------
        action : sequence of 6 floats
            [left_aileron, right_aileron, elevator, rudder, flap, thrust]

        Returns
        -------
        obs, reward, terminated, truncated, info
            Standard Gymnasium 5-tuple. ``info`` is augmented with
            flight metrics.
        """
        action = np.asarray(action, dtype=np.float64)
        if action.shape != (_NUM_CONTROL_AXES,):
            raise ValueError(
                f"Expected action of shape ({_NUM_CONTROL_AXES},), "
                f"got {action.shape}"
            )

        act = action.copy()
        act[:5] = np.clip(act[:5], -1.0, 1.0)
        act[5] = np.clip(act[5], 0.0, 1.0)  # thrust in [0, 1]

        unwrapped = self.env.unwrapped
        # Direct surface actuation in mode -1
        unwrapped.env.set_setpoint(0, act)
        for _ in range(unwrapped.env_step_ratio):
            unwrapped.env.step()
        unwrapped.compute_state()
        unwrapped.compute_term_trunc_reward()

        self._step_count += 1
        unwrapped.step_count = self._step_count
        is_truncated = bool(unwrapped.truncation) or (self._step_count >= self.max_steps)

        flight_metrics = _extract_flight_metrics(
            self.env,
            dt=1.0 / self.control_hz,
            current_thrust=float(act[5]),
        )
        self._step_metrics.append(flight_metrics)

        augmented_obs = self._build_observation(unwrapped.state)
        augmented_info = {**unwrapped.info, **flight_metrics}

        return (
            augmented_obs,
            float(unwrapped.reward),
            bool(unwrapped.termination),
            is_truncated,
            augmented_info,
        )

    def get_metrics(self) -> Dict[str, float]:
        """Aggregate flight metrics over the current episode."""
        if not self._step_metrics:
            return {}
        return _aggregate_metrics(self._step_metrics)

    def close(self) -> None:
        """Disconnect PyBullet and release environment resources."""
        if hasattr(self, "env") and self.env is not None:
            try:
                self.env.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_observation(self, state: Any) -> np.ndarray:
        """Construct a 15-float array: 12 attitude + 3 waypoint delta."""
        if isinstance(state, dict):
            att = np.asarray(state.get("attitude", np.zeros(12)), dtype=np.float32)[:12]
            deltas = state.get("target_deltas")
            if deltas is not None and len(deltas) > 0:
                offset = np.asarray(deltas[0][:3], dtype=np.float32)
            else:
                offset = np.zeros(3, dtype=np.float32)
            return np.concatenate([att, offset]).astype(np.float32)
        elif isinstance(state, np.ndarray) and state.size >= 15:
            return state[:15].astype(np.float32)
        return np.zeros(15, dtype=np.float32)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _resolve_env_id(sim_cfg: Dict[str, Any]) -> str:
    """Pick the PyFlyt environment id from config, defaulting to v3 waypoints."""
    return sim_cfg.get("env_id", "PyFlyt/Fixedwing-Waypoints-v3")


def _extract_flight_metrics(
    env: Any, dt: float, current_thrust: float = 0.0
) -> Dict[str, float]:
    """Extract a snapshot of flight metrics from the PyFlyt environment."""
    try:
        drone = env.unwrapped.env.drones[0]
        ang_vel = drone.state[0]
        ang_pos = drone.state[1]
        lin_vel = drone.state[2]
        pos = drone.state[3]

        airspeed = float(np.linalg.norm(lin_vel))
        altitude = float(pos[2])
        crashed = bool(env.unwrapped.info.get("collision", False)) or altitude <= 0.2
        stalling = bool(airspeed < 8.0)

        # Extract waypoint telemetry if present
        unwrapped = env.unwrapped
        waypoints_hit = 0
        dist_to_wp = 999.0
        progress_to_wp = 0.0
        if hasattr(unwrapped, "waypoints"):
            wp = unwrapped.waypoints
            waypoints_hit = int(getattr(wp, "num_targets_reached", 0))
            raw_dist = getattr(wp, "distance_to_next_target", 999.0)
            dist_to_wp = 999.0 if np.isinf(raw_dist) or np.isnan(raw_dist) else float(raw_dist)
            raw_prog = getattr(wp, "progress_to_next_target", 0.0)
            progress_to_wp = 0.0 if np.isinf(raw_prog) or np.isnan(raw_prog) else float(raw_prog)

        return {
            "flight_time": dt,
            "survival_time": dt,
            "airspeed": airspeed,
            "altitude": altitude,
            "throttle": float(current_thrust),
            "crashed": crashed,
            "stalling": stalling,
            "altitude_error": abs(altitude - 10.0),
            "airspeed_error": abs(airspeed - 20.0),
            "roll": float(ang_pos[0]),
            "pitch": float(ang_pos[1]),
            "yaw": float(ang_pos[2]),
            "waypoints_hit": waypoints_hit,
            "dist_to_wp": dist_to_wp,
            "progress_to_wp": progress_to_wp,
        }
    except Exception:
        return {
            "flight_time": dt,
            "survival_time": dt,
            "airspeed": 0.0,
            "altitude": 0.0,
            "throttle": current_thrust,
            "crashed": False,
            "stalling": False,
            "altitude_error": 0.0,
            "airspeed_error": 0.0,
            "roll": 0.0,
            "pitch": 0.0,
            "yaw": 0.0,
            "waypoints_hit": 0,
            "dist_to_wp": 999.0,
            "progress_to_wp": 0.0,
        }


def _aggregate_metrics(
    step_metrics: List[Dict[str, float]]
) -> Dict[str, float]:
    """Aggregate per-step metrics into per-episode summary."""
    if not step_metrics:
        return {}

    summary: Dict[str, float] = {}
    scalar_keys = [k for k in step_metrics[0] if k not in ("crashed", "stalling")]

    for key in scalar_keys:
        summary[key] = float(np.mean([m[key] for m in step_metrics]))

    total_flight_time = float(sum(m["flight_time"] for m in step_metrics))
    summary["flight_time"] = total_flight_time
    summary["survival_time"] = total_flight_time
    summary["crashed"] = bool(any(m["crashed"] for m in step_metrics))
    summary["stalling"] = bool(any(m["stalling"] for m in step_metrics))
    summary["distance"] = float(np.sum([m["airspeed"] * m["flight_time"] for m in step_metrics]))
    summary["energy"] = float(np.sum([(m["throttle"] ** 2) * m["flight_time"] for m in step_metrics]))
    summary["waypoint_time"] = total_flight_time

    # Waypoint and airspeed specifics
    summary["waypoints_hit"] = int(max(m.get("waypoints_hit", 0) for m in step_metrics))
    summary["min_waypoint_dist"] = float(min(m.get("dist_to_wp", 999.0) for m in step_metrics))
    summary["progress_to_wp"] = float(sum(max(0.0, m.get("progress_to_wp", 0.0)) for m in step_metrics))
    summary["mean_airspeed"] = float(np.mean([m.get("airspeed", 0.0) for m in step_metrics]))
    summary["max_airspeed"] = float(np.max([m.get("airspeed", 0.0) for m in step_metrics]))

    return summary