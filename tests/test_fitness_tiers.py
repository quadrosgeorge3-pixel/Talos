"""Unit tests for the 3-Tier Evolutionary Curriculum and Waypoint/Speed Incentive System."""
import unittest
import numpy as np
from src.simulation.evaluator import compute_fitness_detailed, compute_fitness, BENCHMARK_TARGET_SPEED

class TestFitnessTiers(unittest.TestCase):
    def setUp(self):
        self.config = {
            "simulation": {"episode_duration": 20.0},
            "fitness": {
                "weights": {
                    "survival": 0.4,
                    "efficiency": 0.3,
                    "maneuverability": 0.3,
                },
                "penalties": {
                    "crash": -100.0,
                    "stall": -5.0,
                },
                "curriculum_milestones": {
                    "tier2_generation": 60,
                    "tier3_generation": 500,
                },
            },
        }

    def test_tier1_early_evolution(self):
        """Gen < 60 focuses on survival, efficiency, and distance without waypoint pressure."""
        metrics = {
            "flight_time": 20.0,
            "energy": 20.0,
            "distance": 400.0,
            "altitude_error": 5.0,
            "airspeed": 20.0,
            "waypoints_hit": 0,
            "crashed": False,
            "stalling": False,
        }
        res = compute_fitness_detailed(metrics, self.config, generation=10)
        fit = res["fitness"]
        self.assertAlmostEqual(fit, 0.88, places=2)

        # Verify crash penalty
        metrics_crash = dict(metrics, crashed=True, flight_time=2.0)
        fit_crash = compute_fitness(metrics_crash, self.config, generation=10)
        self.assertLess(fit_crash, -50.0)

    def test_tier2_intermediate_curriculum(self):
        """60 <= Gen < 500 introduces altitude tracking, moderate waypoint rewards, and speedup."""
        metrics_bad_alt = {
            "flight_time": 20.0,
            "energy": 20.0,
            "distance": 500.0,
            "altitude_error": 4.0,
            "airspeed": 25.0,
            "waypoints_hit": 1,
            "progress_to_wp": 50.0,
            "crashed": False,
            "stalling": False,
        }
        res_bad = compute_fitness_detailed(metrics_bad_alt, self.config, generation=80)

        metrics_good_alt = dict(metrics_bad_alt, altitude_error=0.1, waypoints_hit=2)
        res_good = compute_fitness_detailed(metrics_good_alt, self.config, generation=80)

        # Good altitude and more waypoints must score strictly higher
        self.assertGreater(res_good["fitness"], res_bad["fitness"])
        self.assertGreater(res_good["components"]["waypoint_reward"], res_bad["components"]["waypoint_reward"])
        self.assertGreater(res_good["components"]["altitude"], res_bad["components"]["altitude"])

    def test_tier3_beast_mode_waypoint_scaling(self):
        """Gen >= 500 heavily rewards hitting waypoints, with massive bonus for beating P3C (4 gates)."""
        base_metrics = {
            "flight_time": 20.0,
            "energy": 30.0,
            "distance": 900.0,
            "altitude_error": 0.5,
            "mean_airspeed": 49.2,
            "crashed": False,
            "stalling": False,
        }

        # Compare gate hit progression
        res_0 = compute_fitness_detailed(dict(base_metrics, waypoints_hit=0), self.config, generation=505)
        res_1 = compute_fitness_detailed(dict(base_metrics, waypoints_hit=1), self.config, generation=505)
        res_2 = compute_fitness_detailed(dict(base_metrics, waypoints_hit=2), self.config, generation=505)
        res_3 = compute_fitness_detailed(dict(base_metrics, waypoints_hit=3), self.config, generation=505)
        res_4 = compute_fitness_detailed(dict(base_metrics, waypoints_hit=4), self.config, generation=505)

        # Waypoint rewards must strictly increase and reward 4 gates massively
        self.assertEqual(res_0["components"]["waypoint_reward"], 0.0)
        self.assertEqual(res_1["components"]["waypoint_reward"], 20.0)
        self.assertEqual(res_2["components"]["waypoint_reward"], 50.0)
        self.assertEqual(res_3["components"]["waypoint_reward"], 95.0)   # Matches P3C
        self.assertEqual(res_4["components"]["waypoint_reward"], 220.0)  # Beats P3C (all 4)

        self.assertGreater(res_4["fitness"], res_3["fitness"] + 100.0)

    def test_tier3_speed_benchmark_and_surge(self):
        """Gen >= 500 benchmarks speed against 49.2 m/s and rewards super-benchmark speeds."""
        metrics_sub = {
            "flight_time": 20.0,
            "energy": 30.0,
            "distance": 600.0,
            "altitude_error": 0.5,
            "mean_airspeed": 35.0,
            "waypoints_hit": 4,
            "crashed": False,
            "stalling": False,
        }
        res_sub = compute_fitness_detailed(metrics_sub, self.config, generation=505)

        metrics_bench = dict(metrics_sub, mean_airspeed=BENCHMARK_TARGET_SPEED)
        res_bench = compute_fitness_detailed(metrics_bench, self.config, generation=505)

        metrics_beast = dict(metrics_sub, mean_airspeed=53.0)  # Exceeds P3C record
        res_beast = compute_fitness_detailed(metrics_beast, self.config, generation=505)

        # Benchmark speed (49.2 m/s) gets exactly 30 pts speed reward with 4 waypoints
        self.assertAlmostEqual(res_bench["components"]["speed_reward"], 30.0, places=1)

        # Sub-benchmark gets less than 30 pts
        self.assertLess(res_sub["components"]["speed_reward"], res_bench["components"]["speed_reward"])

        # Super-benchmark gets beast surge (> 30 pts)
        self.assertGreater(res_beast["components"]["speed_reward"], 30.0)
        self.assertGreater(res_beast["fitness"], res_bench["fitness"])

    def test_tier3_anti_exploit_dive_gating(self):
        """Crashed individuals receive 0 speed reward and full crash penalty."""
        metrics_dive = {
            "flight_time": 5.0,
            "energy": 50.0,
            "distance": 300.0,
            "altitude_error": 15.0,
            "mean_airspeed": 60.0,  # Fast dive
            "waypoints_hit": 0,
            "crashed": True,
            "stalling": False,
        }
        res_dive = compute_fitness_detailed(metrics_dive, self.config, generation=505)
        self.assertEqual(res_dive["components"]["speed_reward"], 0.0)
        self.assertLessEqual(res_dive["fitness"], -50.0)

if __name__ == "__main__":
    unittest.main()
