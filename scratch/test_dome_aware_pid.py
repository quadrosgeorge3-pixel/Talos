import sys
sys.path.insert(0, ".")

import numpy as np
from src.experiment.metadata import load_config
from src.simulation.env import FixedwingEnv

class DomeAwarePIDController:
    "PID autopilot equipped with 100m geofence awareness and circular loitering."
    def __init__(
        self,
        dt: float = 1.0 / 30.0,
        target_altitude: float = 10.0,
        target_speed: float = 18.0,
        orbit_radius: float = 45.0,
        dome_radius: float = 100.0,
    ):
        self.dt = dt
        self.target_altitude = target_altitude
        self.target_speed = target_speed
        self.orbit_radius = orbit_radius
        self.dome_radius = dome_radius
        self.reset()

    def reset(self):
        self.prev_roll_err = 0.0
        self.roll_integral = 0.0

    def predict(self, obs: np.ndarray) -> np.ndarray:
        p, q, r = float(obs[0]), float(obs[1]), float(obs[2])
        roll, pitch, yaw = float(obs[3]), float(obs[4]), float(obs[5])
        vx, vy, vz = float(obs[6]), float(obs[7]), float(obs[8])
        x, y, z = float(obs[9]), float(obs[10]), float(obs[11])
        
        speed = float(np.sqrt(vx**2 + vy**2 + vz**2))
        dist_from_origin = float(np.sqrt(x**2 + y**2))

        # --- DOME AWARE TANGENT ORBIT GUIDANCE ---
        # The plane spawns at (0, 0) heading +x. 
        # A circle of radius R=35m centered at (0, 35) is perfectly tangent at (0, 0) heading +x!
        # Maximum excursion from origin is 2*R = 70m (safe inside 100m dome).
        # Clockwise orbit around (0, -38) with radius 38m (turns right, negative y)
        # Concentric circle around origin (0, 0) with target radius 40m
        # Every point on this orbit is exactly 40m from origin (60m margin from 100m dome wall!)
        r_target = 40.0
        
        dist_from_origin = float(np.sqrt(x**2 + y**2))
        angle_from_origin = np.arctan2(y, x)
        
        # CCW tangent heading
        tangent_heading = angle_from_origin + np.pi / 2.0
        
        # Radial steering: if inside 40m, spiral out; if outside 40m, steer in
        radial_error = dist_from_origin - r_target
        # If very close to origin (spawn), just fly forward to reach 30m before turning hard
        if dist_from_origin < 15.0:
            desired_heading = 0.0  # head along +x initially
        else:
            inward_correction = np.clip(radial_error / 12.0, -0.6, 0.7)
            desired_heading = tangent_heading - inward_correction

        heading_err = desired_heading - yaw
        heading_err = (heading_err + np.pi) % (2.0 * np.pi) - np.pi

        # Bank command
        target_roll = np.clip(1.2 * heading_err, -0.65, 0.65)
        roll_err = target_roll - roll
        roll_cmd = np.clip(1.5 * roll_err - 0.20 * p, -0.8, 0.8)

        # Altitude control: hold 20m with positive climb off spawn
        target_alt = 20.0
        alt_err = target_alt - z
        bank_comp = 0.05 * (1.0 - np.cos(roll))
        elev = np.clip(-0.05 - 0.08 * alt_err - 0.15 * q - bank_comp, -0.35, 0.35)

        # Decelerate to 16.5 m/s to reduce turning radius (R proportional to v^2)
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

def test_run():
    config = load_config("configs/controller_only/c1_controller_only.json")
    config["simulation"]["flight_dome_size"] = 100.0
    config["simulation"]["episode_duration"] = 10.0
    
    env = FixedwingEnv(config=config)
    env.env.unwrapped.flight_dome_size = 100.0
    env.max_steps = int(10.0 * env.control_hz)

    ctrl = DomeAwarePIDController(dt=1.0 / env.control_hz)
    obs, _ = env.reset(seed=42)
    ctrl.reset()

    step = 0
    terminated = False
    truncated = False
    max_dist_origin = 0.0

    print("Running Dome-Aware PID in 100m Dome...")
    while not (terminated or truncated) and step < env.max_steps:
        action = ctrl.predict(obs)
        obs, _, terminated, truncated, info = env.step(action)
        step += 1
        x, y, z = obs[9], obs[10], obs[11]
        d_orig = np.sqrt(x**2 + y**2)
        if d_orig > max_dist_origin:
            max_dist_origin = d_orig

    metrics = env.get_metrics()
    env.env.close()
    
    print("Result:")
    print(f"  Flight Time: {metrics.get('flight_time', 0.0):.2f} s / 10.00 s")
    print(f"  Total Distance Traversed: {metrics.get('distance', 0.0):.2f} m")
    print(f"  Max Distance from Center: {max_dist_origin:.2f} m (Dome is 100m)")
    print(f"  Crashed: {metrics.get('crashed', False)}")
    print(f"  Altitude Error: {metrics.get('altitude_error', 0.0):.2f} m")
    print(f"  Mean Airspeed: {metrics.get('airspeed', 0.0):.2f} m/s")

if __name__ == '__main__':
    test_run()
