"""Smoke tests for the Icarus experimental setup phase.

Run:  python -m pytest tests/ -v
"""
from __future__ import annotations

import json
import os
import tempfile

import pytest

# ---------------------------------------------------------------------------
# Import checks
# ---------------------------------------------------------------------------

def test_imports():
    from src.simulation.env import FixedwingEnv
    from src.simulation.evaluator import compute_fitness, evaluate_individual
    from src.genome.controller import NEATController
    from src.genome.morphology import MorphologyGenome, DEFAULT_MORPHOLOGY
    from src.genome.urdf_gen import generate_model_files, model_dir_for
    from src.experiment.db import ExperimentDB
    from src.experiment.metadata import ExperimentMetadata, load_config
    assert True


# ---------------------------------------------------------------------------
# Morphology genome
# ---------------------------------------------------------------------------

class TestMorphologyGenome:
    def test_default(self):
        from src.genome.morphology import MorphologyGenome, DEFAULT_MORPHOLOGY
        mg = MorphologyGenome()
        d = mg.to_dict()
        for key, val in DEFAULT_MORPHOLOGY.items():
            assert d[key] == pytest.approx(val, abs=1e-6)

    def test_bounds(self):
        from src.genome.morphology import DEFAULT_MORPHOLOGY, MorphologyGenome
        mg = MorphologyGenome()
        lo, hi = mg.bounds["wingspan"]
        assert lo < DEFAULT_MORPHOLOGY["wingspan"] < hi

    def test_clamp(self):
        from src.genome.morphology import MorphologyGenome
        mg = MorphologyGenome(
            params=[10.0, 0.01, 0.01, 0.01, 0.5, 1.0, 0.0]
        )
        d = mg.to_dict()
        assert d["wingspan"] <= mg.bounds["wingspan"][1]

    def test_from_dict(self):
        from src.genome.morphology import MorphologyGenome
        mg = MorphologyGenome.from_dict({"wingspan": 2.0, "wing_area": 0.8})
        assert mg.to_dict()["wingspan"] == pytest.approx(2.0)
        assert mg.to_dict()["wing_area"] == pytest.approx(0.8)

    def test_mutation(self):
        import numpy as np
        from src.genome.morphology import MorphologyGenome
        rng = np.random.default_rng(seed=42)
        mg = MorphologyGenome()
        mg2 = mg.mutate(rng, rate=1.0)
        d1, d2 = mg.to_dict(), mg2.to_dict()
        # With rate=1.0, all params should be perturbed (not always guaranteed
        # but overwhelmingly likely given Gaussian noise)
        diffs = [abs(d1[k] - d2[k]) for k in d1]
        assert sum(diffs) > 0


# ---------------------------------------------------------------------------
# Experiment DB
# ---------------------------------------------------------------------------

class TestExperimentDB:
    def test_init(self, tmp_path):
        from src.experiment.db import ExperimentDB
        db_path = str(tmp_path / "test.db")
        db = ExperimentDB(db_path)
        assert os.path.exists(db_path)

    def test_experiment_lifecycle(self, tmp_path):
        from src.experiment.db import ExperimentDB
        db = ExperimentDB(str(tmp_path / "test.db"))
        db.create_experiment("test_01", {"foo": "bar"}, "2025-01-01T00:00:00Z")
        row = db.get_experiment("test_01")
        assert row is not None
        assert row["experiment_id"] == "test_01"
        assert row["status"] == "running"

        db.complete_experiment("test_01", "2025-01-01T01:00:00Z")
        row = db.get_experiment("test_01")
        assert row["status"] == "completed"

    def test_baseline_round_trip(self, tmp_path):
        from src.experiment.db import ExperimentDB
        db = ExperimentDB(str(tmp_path / "test.db"))
        db.create_experiment("test_01", {}, "2025-01-01T00:00:00Z")

        stats = {
            "survival_time": {"mean": 25.0, "std": 1.5},
            "distance": {"mean": 300.0, "std": 20.0},
            "energy": {"mean": 15.0, "std": 2.0},
        }
        db.save_baseline("B0_test", "test_01", stats, "2025-01-01T01:00:00Z")

        loaded = db.get_baseline("B0_test")
        assert loaded is not None
        assert loaded["survival_time_mean"] == pytest.approx(25.0)
        assert loaded["survival_time_std"] == pytest.approx(1.5)


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

class TestMetadata:
    def test_hash_determinism(self, tmp_path):
        from src.experiment.metadata import ExperimentMetadata
        config = {"experiment_id": "meta_test", "neat_config": {"pop_size": 50}}
        m1 = ExperimentMetadata(config, str(tmp_path))
        m2 = ExperimentMetadata(config, str(tmp_path))
        assert m1.config_hash == m2.config_hash

    def test_write_and_load(self, tmp_path):
        from src.experiment.metadata import ExperimentMetadata
        config = {"experiment_id": "meta_test"}
        meta = ExperimentMetadata(config, str(tmp_path))
        meta.ensure_directories()
        path = meta.write_metadata()
        assert os.path.isfile(path)


# ---------------------------------------------------------------------------
# NEAT controller (light — just config building)
# ---------------------------------------------------------------------------

class TestNEATController:
    def test_config_builds(self):
        config = {
            "controller": {
                "num_inputs": 15,
                "num_outputs": 6,
                "activation": "tanh",
                "output_activation": "sigmoid",
            },
            "neat_config": {
                "pop_size": 20,
                "fitness_criterion": "max",
                "compatibility_threshold": 3.0,
                "conn_add_prob": 0.5,
                "conn_delete_prob": 0.2,
                "node_add_prob": 0.3,
                "node_delete_prob": 0.1,
                "weight_mutate_rate": 0.8,
                "weight_replace_rate": 0.1,
                "weight_max": 3.0,
                "weight_init_std": 1.0,
                "bias_mutate_rate": 0.7,
                "bias_max": 3.0,
            },
        }
        from src.genome.controller import NEATController
        ctrl = NEATController(config)
        assert ctrl.config.pop_size == 20
        assert ctrl.config.genome_config.num_inputs == 15
        assert ctrl.config.genome_config.num_outputs == 6

    def test_genome_summary(self):
        config = {
            "controller": {"num_inputs": 15, "num_outputs": 6,
                           "activation": "tanh", "output_activation": "sigmoid"},
            "neat_config": {"pop_size": 10, "fitness_criterion": "max",
                            "compatibility_threshold": 3.0, "conn_add_prob": 0.5,
                            "conn_delete_prob": 0.2, "node_add_prob": 0.3,
                            "node_delete_prob": 0.1, "weight_mutate_rate": 0.8,
                            "weight_replace_rate": 0.1, "weight_max": 3.0,
                            "weight_init_std": 1.0, "bias_mutate_rate": 0.7,
                            "bias_max": 3.0},
        }
        from src.genome.controller import NEATController
        ctrl = NEATController(config)
        summary = ctrl.get_genome_summary()
        # full_direct initial_connection: 15 inputs x 6 outputs = 90 connections
        assert summary["connections_total"] == 90


# ---------------------------------------------------------------------------
# Fitness scoring
# ---------------------------------------------------------------------------

class TestFitness:
    def test_baseline_score(self):
        config = {
            "simulation": {"episode_duration": 10.0},
            "fitness": {
                "weights": {"survival": 0.4, "efficiency": 0.3, "maneuverability": 0.3},
                "penalties": {"crash": -100.0, "stall": -5.0, "altitude_exceeded": -2.0},
            },
        }
        from src.simulation.evaluator import compute_fitness
        metrics = {
            "flight_time": 10.0,
            "distance": 200.0,
            "energy": 10.0,
            "crashed": False,
            "stalling": False,
        }
        score = compute_fitness(metrics, config)
        assert score > 0.0
        assert score < 100.0