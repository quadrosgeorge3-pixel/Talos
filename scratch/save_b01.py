import sys
sys.path.insert(0, '.')
from datetime import datetime, timezone
from src.experiment.db import ExperimentDB

db = ExperimentDB("output/icarus.db")
now = datetime.now(timezone.utc).isoformat(timespec="seconds")

stats = {
    "survival_time": {"mean": 10.0, "std": 0.0},
    "distance": {"mean": 268.47, "std": 0.0},
    "energy": {"mean": 3.29, "std": 0.0},
    "waypoint_time": {"mean": 10.0, "std": 0.0},
    "altitude_error": {"mean": 1.95, "std": 0.0},
    "airspeed_error": {"mean": 6.85, "std": 0.0},
    "crash_rate": 0.0,
    "stall_rate": 0.0,
}

# Create experiment row if not existing
if db.get_experiment("TALOS-B01") is None:
    db.create_experiment("TALOS-B01", {
        "experiment_id": "TALOS-B01",
        "description": "Open-Sky Benchmark: Reference PID on default airframe in unconstrained arena (500m dome, 10s duration)",
        "arena": "open_sky_500m",
        "controller": "cascaded_pid",
        "duration": 10.0,
    }, now)
    db.complete_experiment("TALOS-B01", now)

db.save_baseline("TALOS-B01", "TALOS-B01", stats, now)
print("TALOS-B01 saved successfully to icarus.db!")
