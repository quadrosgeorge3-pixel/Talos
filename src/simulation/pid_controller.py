"""Baseline PID controller for PyFlyt Fixedwing.

Provides a tuned cascaded flight controller for fixedwing waypoint following
and stable cruising, serving as the benchmark condition that evolved
controllers are evaluated against.
"""
from __future__ import annotations

from typing import Sequence
import numpy as np


class FixedwingPIDController:
    """Cascaded attitude & trajectory controller for PyFlyt Fixedwing UAVs.

    Converts the 15-element flight observation [attitude (12), waypoint_offset (3)]
    into the 6-element control surface actions:
        [left_aileron, right_aileron, elevator, rudder, flap, thrust]
    """

    def __init__(
        self,
        dt: float = 1.0 / 120.0,
        target_airspeed: float = 22.0,
        target_altitude: float = 10.0,
        dome_radius: Optional[float] = None,
    ) -> None:
        self.dt = float(dt)
        self.target_airspeed = float(target_airspeed)
        self.target_altitude = float(target_altitude)
        self.dome_radius = float(dome_radius) if dome_radius is not None else None

    def reset(self) -> None:
        """Reset internal controller state."""
        pass

    def predict(self, obs: Sequence[float]) -> np.ndarray:
        """Compute control surface deflections from flight observation.

        Parameters
        ----------
        obs : sequence of 15 floats
            obs[0:3]   ang_vel [p, q, r]
            obs[3:6]   ang_pos [roll, pitch, yaw]
            obs[6:9]   lin_vel [vx, vy, vz]
            obs[9:12]  lin_pos [x, y, z]
            obs[12:15] waypoint_offset [dx, dy, dz] (body frame)

        Returns
        -------
        action : np.ndarray, shape (6,)
            [left_aileron, right_aileron, elevator, rudder, flap, thrust]
        """
        obs_arr = np.asarray(obs, dtype=np.float64)

        p = float(obs_arr[0]) if len(obs_arr) > 0 else 0.0
        q = float(obs_arr[1]) if len(obs_arr) > 1 else 0.0
        r = float(obs_arr[2]) if len(obs_arr) > 2 else 0.0

        roll = float(obs_arr[3]) if len(obs_arr) > 3 else 0.0
        pitch = float(obs_arr[4]) if len(obs_arr) > 4 else 0.0
        yaw = float(obs_arr[5]) if len(obs_arr) > 5 else 0.0

        vx = float(obs_arr[6]) if len(obs_arr) > 6 else 20.0
        vy = float(obs_arr[7]) if len(obs_arr) > 7 else 0.0
        vz = float(obs_arr[8]) if len(obs_arr) > 8 else 0.0

        x = float(obs_arr[9]) if len(obs_arr) > 9 else 0.0
        y = float(obs_arr[10]) if len(obs_arr) > 10 else 0.0
        z = float(obs_arr[11]) if len(obs_arr) > 11 else 10.0

        dx = float(obs_arr[12]) if len(obs_arr) > 12 else 10.0
        dy = float(obs_arr[13]) if len(obs_arr) > 13 else 0.0
        dz = float(obs_arr[14]) if len(obs_arr) > 14 else 0.0

        spd = float(np.linalg.norm([vx, vy, vz]))

        # --- DOME-AWARE BOUNDED MODE (100m Geofence Loiter) ---
        if self.dome_radius is not None and self.dome_radius <= 150.0:
            r_target = 40.0
            dist_from_origin = float(np.sqrt(x**2 + y**2))
            angle_from_origin = np.arctan2(y, x)

            tangent_heading = angle_from_origin + np.pi / 2.0  # CCW orbit
            radial_error = dist_from_origin - r_target

            if dist_from_origin < 15.0:
                desired_heading = 0.0
            else:
                inward_correction = np.clip(radial_error / 12.0, -0.6, 0.7)
                desired_heading = tangent_heading - inward_correction

            heading_err = desired_heading - yaw
            heading_err = (heading_err + np.pi) % (2.0 * np.pi) - np.pi

            target_roll = np.clip(1.2 * heading_err, -0.65, 0.65)
            roll_err = target_roll - roll
            roll_cmd = np.clip(1.5 * roll_err - 0.20 * p, -0.8, 0.8)

            target_alt = 20.0
            alt_err = target_alt - z
            bank_comp = 0.05 * (1.0 - np.cos(roll))
            elev = np.clip(-0.05 - 0.08 * alt_err - 0.15 * q - bank_comp, -0.35, 0.35)

            target_spd = 16.5
            throttle_err = target_spd - spd
            throttle = np.clip(0.35 + 0.08 * throttle_err, 0.1, 0.8)
            rudder = np.clip(0.15 * target_roll - 0.10 * r, -0.25, 0.25)

        # --- OPEN-SKY MODE (Straight-Line & Waypoint Cruise) ---
        else:
            heading_err = float(np.arctan2(dy, max(dx, 1.0)))
            target_roll = float(np.clip(0.6 * heading_err, -0.25, 0.25))
            roll_cmd = float(np.clip(0.8 * (target_roll - roll) - 0.15 * p, -0.3, 0.3))

            alt_error = self.target_altitude - z
            elev = float(np.clip(-0.035 - 0.04 * alt_error - 0.15 * q, -0.15, 0.15))

            throttle = float(np.clip(0.8 + 0.05 * (self.target_airspeed - spd), 0.5, 1.0))
            rudder = 0.0

        # 6 control surface deflections
        action = np.zeros(6, dtype=np.float32)
        action[0] = roll_cmd       # left_aileron
        action[1] = -roll_cmd      # right_aileron
        action[2] = elev           # elevator
        action[3] = rudder         # rudder
        action[4] = 0.0            # flap
        action[5] = throttle       # thrust

        return action
