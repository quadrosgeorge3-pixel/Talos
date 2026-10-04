import sys
sys.path.insert(0, ".")

import json
from src.evolution.morphology_runner import run_morphology_evolution

# Create a mini config for smoke test
smoke_cfg = {
    "experiment_id": "SMOKE-P3",
    "experiment_type": "morphology_only",
    "simulation": {
        "env_id": "PyFlyt/Fixedwing-Waypoints-v3",
        "episode_duration": 1.0,  # 1 second
        "control_hz": 30,
        "physics_hz": 240,
        "flight_dome_size": 100.0,
    },
    "pilot": {
        "type": "fixed_pid",
        "target_airspeed": 22.0,
        "target_altitude": 10.0,
    },
    "morphology_evolution": {
        "pop_size": 2,
        "num_generations": 1,
        "elitism": 1,
        "crossover_rate": 0.5,
        "mutation_rate": 0.3,
        "tournament_size": 2,
    },
    "fitness": {
        "weights": {"survival": 0.4, "efficiency": 0.3, "maneuverability": 0.3},
        "penalties": {"crash": -100.0, "stall": -5.0},
    },
}

with open("scratch/smoke_p3_config.json", "w", encoding="utf-8") as f:
    json.dump(smoke_cfg, f, indent=2)

print("Running mini morphology smoke test...")
champ = run_morphology_evolution("scratch/smoke_p3_config.json")
print("Smoke test completed successfully! Champion:", champ)
