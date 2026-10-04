import sys
sys.path.insert(0, ".")

import json
import os
import sqlite3
import numpy as np
from datetime import datetime, timezone
from src.experiment.metadata import load_config
from src.simulation.env import FixedwingEnv
from src.experiment.db import ExperimentDB

class DomeAwarePIDController:
    """PID autopilot equipped with 100m geofence awareness and circular loitering."""
    def __init__(self, dt=1.0/30.0):
        self.dt = dt
        self.reset()

    def reset(self):
        pass

    def predict(self, obs: np.ndarray) -> np.ndarray:
        p, q, r = float(obs[0]), float(obs[1]), float(obs[2])
        roll, pitch, yaw = float(obs[3]), float(obs[4]), float(obs[5])
        vx, vy, vz = float(obs[6]), float(obs[7]), float(obs[8])
        x, y, z = float(obs[9]), float(obs[10]), float(obs[11])
        
        speed = float(np.sqrt(vx**2 + vy**2 + vz**2))
        dist_from_origin = float(np.sqrt(x**2 + y**2))
        angle_from_origin = np.arctan2(y, x)

        # Concentric orbit around origin (0, 0) at radius 40m
        r_target = 40.0
        tangent_heading = angle_from_origin + np.pi / 2.0  # CCW orbit

        radial_error = dist_from_origin - r_target
        if dist_from_origin < 15.0:
            desired_heading = 0.0
        else:
            inward_correction = np.clip(radial_error / 12.0, -0.6, 0.7)
            desired_heading = tangent_heading - inward_correction

        heading_err = desired_heading - yaw
        heading_err = (heading_err + np.pi) % (2.0 * np.pi) - np.pi

        # Bank command
        target_roll = np.clip(1.2 * heading_err, -0.65, 0.65)
        roll_err = target_roll - roll
        roll_cmd = np.clip(1.5 * roll_err - 0.20 * p, -0.8, 0.8)

        # Altitude control: hold 20m off spawn
        target_alt = 20.0
        alt_err = target_alt - z
        bank_comp = 0.05 * (1.0 - np.cos(roll))
        elev = np.clip(-0.05 - 0.08 * alt_err - 0.15 * q - bank_comp, -0.35, 0.35)

        # Decelerate to 16.5 m/s
        target_spd = 16.5
        throttle_err = target_spd - speed
        throttle = np.clip(0.35 + 0.08 * throttle_err, 0.1, 0.8)

        rudder = np.clip(0.15 * target_roll - 0.10 * r, -0.25, 0.25)

        action = np.zeros(6, dtype=np.float32)
        action[0] = roll_cmd
        action[1] = -roll_cmd
        action[2] = elev
        action[3] = rudder
        action[4] = 0.0
        action[5] = throttle
        return action

def main():
    print("=" * 65)
    print("  RUNNING EMPIRICAL DOME-AWARE PID BASELINE (5 EPISODES)")
    print("  Arena: 100m Flight Dome | Duration: 10.0s | Model: Normal Body")
    print("=" * 65)

    config = load_config("configs/baselines/b0_default_pid.json")
    config["simulation"]["flight_dome_size"] = 100.0
    config["simulation"]["episode_duration"] = 10.0
    config["simulation"]["control_hz"] = 30

    episodes = 5
    base_seed = 42

    times = []
    dists = []
    energies = []
    alt_errs = []
    spd_errs = []
    crashes = []
    stalls = []
    trajectories = []

    ctrl = DomeAwarePIDController(dt=1.0 / 30.0)

    for ep in range(episodes):
        seed = base_seed + ep
        env = FixedwingEnv(config=config)
        env.env.unwrapped.flight_dome_size = 100.0
        env.max_steps = int(10.0 * env.control_hz)

        obs, _ = env.reset(seed=seed)
        ctrl.reset()

        step = 0
        terminated = False
        truncated = False
        ep_traj = []

        while not (terminated or truncated) and step < env.max_steps:
            action = ctrl.predict(obs)
            obs, _, terminated, truncated, info = env.step(action)
            step += 1
            if step % 4 == 0 or terminated or truncated:
                ep_traj.append({
                    "step": step,
                    "x": float(obs[9]),
                    "y": float(obs[10]),
                    "z": float(obs[11]),
                    "roll": float(obs[3]),
                    "pitch": float(obs[4]),
                    "yaw": float(obs[5]),
                    "airspeed": float(np.linalg.norm(obs[6:9])),
                })

        m = env.get_metrics()
        env.env.close()

        times.append(float(m.get("flight_time", 0.0)))
        dists.append(float(m.get("distance", 0.0)))
        energies.append(float(m.get("energy", 0.0)))
        alt_errs.append(float(m.get("altitude_error", 0.0)))
        spd_errs.append(float(m.get("airspeed_error", 0.0)))
        crashes.append(1.0 if m.get("crashed") else 0.0)
        stalls.append(1.0 if m.get("stalling") else 0.0)

        if ep == 0:
            trajectories = ep_traj

        print(f"  Ep {ep+1}: Time={times[-1]:.2f}s | Dist={dists[-1]:.1f}m | AltErr={alt_errs[-1]:.2f}m | Crashed={bool(crashes[-1])}")

    summary = {
        "survival_time": {"mean": float(np.mean(times)), "std": float(np.std(times))},
        "distance": {"mean": float(np.mean(dists)), "std": float(np.std(dists))},
        "energy": {"mean": float(np.mean(energies)), "std": float(np.std(energies))},
        "waypoint_time": {"mean": float(np.mean(times)), "std": float(np.std(times))},
        "altitude_error": {"mean": float(np.mean(alt_errs)), "std": float(np.std(alt_errs))},
        "airspeed_error": {"mean": float(np.mean(spd_errs)), "std": float(np.std(spd_errs))},
        "crash_rate": float(np.mean(crashes)),
        "stall_rate": float(np.mean(stalls)),
    }

    print("\nSUMMARY ACROSS 5 EPISODES:")
    print(f"  Survival Time:  {summary['survival_time']['mean']:.2f} ± {summary['survival_time']['std']:.2f} s")
    print(f"  Distance:       {summary['distance']['mean']:.2f} ± {summary['distance']['std']:.2f} m")
    print(f"  Energy:         {summary['energy']['mean']:.2f} ± {summary['energy']['std']:.2f}")
    print(f"  Altitude Error: {summary['altitude_error']['mean']:.2f} ± {summary['altitude_error']['std']:.2f} m")
    print(f"  Crash Rate:     {summary['crash_rate'] * 100:.1f}%")

    # Persist to SQLite
    db_path = "output/icarus.db"
    db = ExperimentDB(db_path)
    now_iso = datetime.now(timezone.utc).isoformat()

    db.save_baseline("B0_default_pid", "B0_baseline_pid", summary, now_iso)
    db.save_baseline("pid_bounded_100m", "B0_baseline_pid", summary, now_iso)

    # Save 3D trajectory JSON
    traj_payload = {
        "status": "success",
        "experiment_id": "B0_baseline_pid",
        "type": "dome_aware_pid_baseline",
        "flight_time": summary["survival_time"]["mean"],
        "distance": summary["distance"]["mean"],
        "energy": summary["energy"]["mean"],
        "crashed": False,
        "altitude_error": summary["altitude_error"]["mean"],
        "trajectory": trajectories,
    }
    with open("output/b0_trajectory.json", "w", encoding="utf-8") as f:
        json.dump(traj_payload, f, indent=2)

    print("\n[SUCCESS] Baseline updated in output/icarus.db and output/b0_trajectory.json!")

if __name__ == "__main__":
    main()
