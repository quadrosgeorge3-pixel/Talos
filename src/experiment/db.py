"""SQLite storage for experiment metadata, baselines, and generation stats.

Schema mirrors the plan in
``docs/plans/1789391271544-evolved-aircraft-experimental-setup.md``.
"""
from __future__ import annotations

import json
import os
import sqlite3
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS experiment_metadata (
    experiment_id     TEXT PRIMARY KEY,
    config_json       TEXT NOT NULL,
    start_time        TEXT NOT NULL,
    end_time          TEXT,
    status            TEXT DEFAULT 'running',
    baseline_survival REAL,
    best_fitness      REAL,
    best_generation   INTEGER
);

CREATE TABLE IF NOT EXISTS baseline_metrics (
    baseline_id               TEXT PRIMARY KEY,
    experiment_id             TEXT NOT NULL,
    survival_time_mean        REAL,
    survival_time_std         REAL,
    distance_mean             REAL,
    distance_std              REAL,
    energy_mean               REAL,
    energy_std                REAL,
    waypoint_time_mean        REAL,
    waypoint_time_std         REAL,
    altitude_error_mean       REAL,
    altitude_error_std        REAL,
    airspeed_error_mean       REAL,
    airspeed_error_std        REAL,
    crash_rate                REAL,
    stall_rate                REAL,
    measured_at               TEXT NOT NULL,
    FOREIGN KEY (experiment_id) REFERENCES experiment_metadata(experiment_id)
);

CREATE TABLE IF NOT EXISTS generations (
    experiment_id     TEXT NOT NULL,
    generation        INTEGER NOT NULL,
    best_fitness      REAL NOT NULL,
    mean_fitness      REAL NOT NULL,
    median_fitness    REAL NOT NULL,
    worst_fitness     REAL NOT NULL,
    std_fitness       REAL NOT NULL,
    best_nodes        INTEGER,
    best_connections  INTEGER,
    mean_nodes        REAL,
    mean_connections  REAL,
    species_count     INTEGER,
    population_alive  INTEGER,
    best_survival_time REAL,
    best_distance     REAL,
    best_energy       REAL,
    best_waypoint_time REAL,
    PRIMARY KEY (experiment_id, generation),
    FOREIGN KEY (experiment_id) REFERENCES experiment_metadata(experiment_id)
);

CREATE TABLE IF NOT EXISTS individuals (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id     TEXT NOT NULL,
    generation        INTEGER NOT NULL,
    individual_index  INTEGER NOT NULL,
    fitness           REAL NOT NULL,
    is_elite          INTEGER DEFAULT 0,
    survival_time     REAL,
    distance          REAL,
    energy            REAL,
    waypoint_time     REAL,
    altitude_error    REAL,
    airspeed_error    REAL,
    crashed           INTEGER,
    stalling          INTEGER,
    nodes             INTEGER,
    connections       INTEGER,
    species_id        INTEGER,
    morphology_json   TEXT,
    controller_json   TEXT,
    FOREIGN KEY (experiment_id, generation) REFERENCES generations(experiment_id, generation)
);

CREATE TABLE IF NOT EXISTS benchmark_evaluations (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    test_name         TEXT NOT NULL,
    controller_id     TEXT NOT NULL,
    controller_type   TEXT NOT NULL,
    flight_time       REAL,
    distance          REAL,
    mean_airspeed     REAL,
    mean_altitude     REAL,
    altitude_error    REAL,
    max_lateral_dev   REAL,
    control_energy    REAL,
    crashed           INTEGER,
    stalling          INTEGER,
    waypoints_hit     INTEGER,
    precision_score   REAL,
    measured_at       TEXT NOT NULL,
    course_map_json   TEXT,
    arena_radius      REAL,
    waypoint_radius   REAL,
    trajectory_json   TEXT
);

CREATE INDEX IF NOT EXISTS idx_exp_status ON experiment_metadata(status);
CREATE INDEX IF NOT EXISTS idx_baseline_exp ON baseline_metrics(experiment_id);
CREATE INDEX IF NOT EXISTS idx_ind_gen ON individuals(experiment_id, generation);
CREATE INDEX IF NOT EXISTS idx_ind_elite ON individuals(is_elite) WHERE is_elite = 1;
CREATE INDEX IF NOT EXISTS idx_gen_exp ON generations(experiment_id);
CREATE INDEX IF NOT EXISTS idx_bench_test ON benchmark_evaluations(test_name, controller_id);
"""


# ---------------------------------------------------------------------------
# Database wrapper
# ---------------------------------------------------------------------------

class ExperimentDB:
    """SQLite wrapper for experiment lifecycle + read/write operations."""

    def __init__(self, db_path: str) -> None:
        self.db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._migrate()
        self._init_schema()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _conn(self) -> sqlite3.Connection:
        """Return a raw connection; caller must close it."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _connect(self) -> sqlite3.Connection:
        """Alias for _conn (used as context manager by dashboard)."""
        return self._conn()

    def _migrate(self) -> None:
        """Drop old-schema tables if they lack experiment_id."""
        conn = self._conn()
        try:
            # Check if the generations table exists at all
            has_table = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='generations'"
            ).fetchone()
            if has_table:
                cols = [r["name"] for r in conn.execute("PRAGMA table_info(generations)").fetchall()]
                if "experiment_id" not in cols:
                    conn.executescript(
                        "DROP TABLE IF EXISTS individuals;"
                        "DROP TABLE IF EXISTS generations;"
                    )
                    conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        conn = self._conn()
        try:
            conn.executescript(_SCHEMA)
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Experiment metadata
    # ------------------------------------------------------------------

    def create_experiment(
        self,
        experiment_id: str,
        config: Dict[str, Any],
        start_time: str,
    ) -> None:
        conn = self._conn()
        try:
            conn.execute(
                """
                INSERT INTO experiment_metadata
                    (experiment_id, config_json, start_time, status)
                VALUES (?, ?, ?, 'running')
                """,
                (experiment_id, json.dumps(config, indent=2), start_time),
            )
            conn.commit()
        finally:
            conn.close()

    def complete_experiment(self, experiment_id: str, end_time: str) -> None:
        conn = self._conn()
        try:
            conn.execute(
                """
                UPDATE experiment_metadata
                SET status = 'completed', end_time = ?
                WHERE experiment_id = ?
                """,
                (end_time, experiment_id),
            )
            conn.commit()
        finally:
            conn.close()

    def fail_experiment(self, experiment_id: str, end_time: str) -> None:
        conn = self._conn()
        try:
            conn.execute(
                """
                UPDATE experiment_metadata
                SET status = 'failed', end_time = ?
                WHERE experiment_id = ?
                """,
                (end_time, experiment_id),
            )
            conn.commit()
        finally:
            conn.close()

    def update_best(
        self, experiment_id: str, fitness: float, generation: int
    ) -> None:
        conn = self._conn()
        try:
            conn.execute(
                """
                UPDATE experiment_metadata
                SET best_fitness = ?, best_generation = ?
                WHERE experiment_id = ?
                """,
                (fitness, generation, experiment_id),
            )
            conn.commit()
        finally:
            conn.close()

    def get_experiment(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM experiment_metadata WHERE experiment_id = ?",
                (experiment_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_experiments(self) -> List[Dict[str, Any]]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT experiment_id, status, start_time, end_time "
                "FROM experiment_metadata ORDER BY start_time DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Baselines
    # ------------------------------------------------------------------

    def save_baseline(self, baseline_id: str, experiment_id: str, stats: Dict[str, Any], measured_at: str) -> None:
        """Insert or replace baseline metrics."""
        conn = self._conn()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO baseline_metrics (
                    baseline_id, experiment_id,
                    survival_time_mean, survival_time_std,
                    distance_mean,      distance_std,
                    energy_mean,        energy_std,
                    waypoint_time_mean, waypoint_time_std,
                    altitude_error_mean, altitude_error_std,
                    airspeed_error_mean, airspeed_error_std,
                    crash_rate, stall_rate,
                    measured_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    baseline_id, experiment_id,
                    _mean(stats, "survival_time"),
                    _std(stats, "survival_time"),
                    _mean(stats, "distance"),
                    _std(stats, "distance"),
                    _mean(stats, "energy"),
                    _std(stats, "energy"),
                    _mean(stats, "waypoint_time"),
                    _std(stats, "waypoint_time"),
                    _mean(stats, "altitude_error"),
                    _std(stats, "altitude_error"),
                    _mean(stats, "airspeed_error"),
                    _std(stats, "airspeed_error"),
                    stats.get("crash_rate", 0.0),
                    stats.get("stall_rate", 0.0),
                    measured_at,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_baseline(self, baseline_id: str) -> Optional[Dict[str, Any]]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM baseline_metrics WHERE baseline_id = ?",
                (baseline_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_latest_baseline(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        conn = self._conn()
        try:
            row = conn.execute(
                """
                SELECT * FROM baseline_metrics
                WHERE experiment_id = ?
                ORDER BY measured_at DESC LIMIT 1
                """,
                (experiment_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Generations (used by the evolution loop in the experiment phase)
    # ------------------------------------------------------------------

    def log_generation(
        self, experiment_id: str, generation: int, stats: Dict[str, Any]
    ) -> None:
        """Insert or replace per-generation statistics."""
        conn = self._conn()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO generations (
                    experiment_id, generation,
                    best_fitness, mean_fitness, median_fitness,
                    worst_fitness, std_fitness, best_nodes, best_connections,
                    mean_nodes, mean_connections, species_count, population_alive,
                    best_survival_time, best_distance, best_energy,
                    best_waypoint_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    experiment_id,
                    generation,
                    stats.get("best_fitness", 0.0),
                    stats.get("mean_fitness", 0.0),
                    stats.get("median_fitness", 0.0),
                    stats.get("worst_fitness", 0.0),
                    stats.get("std_fitness", 0.0),
                    stats.get("best_nodes"),
                    stats.get("best_connections"),
                    stats.get("mean_nodes"),
                    stats.get("mean_connections"),
                    stats.get("species_count"),
                    stats.get("population_alive"),
                    stats.get("best_survival_time"),
                    stats.get("best_distance"),
                    stats.get("best_energy"),
                    stats.get("best_waypoint_time"),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_generation_history(
        self, experiment_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Return generation rows, optionally filtered by experiment."""
        conn = self._conn()
        try:
            if experiment_id:
                rows = conn.execute(
                    "SELECT * FROM generations WHERE experiment_id = ? ORDER BY generation",
                    (experiment_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM generations ORDER BY generation"
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Individuals
    # ------------------------------------------------------------------

    def log_individual(
        self,
        experiment_id: str,
        generation: int,
        index: int,
        data: Dict[str, Any],
    ) -> int:
        """Insert one evaluated individual; returns its row id."""
        conn = self._conn()
        try:
            cursor = conn.execute(
                """
                INSERT INTO individuals (
                    experiment_id, generation, individual_index, fitness,
                    is_elite,
                    survival_time, distance, energy, waypoint_time,
                    altitude_error, airspeed_error, crashed, stalling,
                    nodes, connections, species_id, morphology_json,
                    controller_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    experiment_id,
                    generation,
                    index,
                    data.get("fitness", 0.0),
                    int(data.get("is_elite", False)),
                    data.get("survival_time"),
                    data.get("distance"),
                    data.get("energy"),
                    data.get("waypoint_time"),
                    data.get("altitude_error"),
                    data.get("airspeed_error"),
                    int(data.get("crashed", False)),
                    int(data.get("stalling", False)),
                    data.get("nodes"),
                    data.get("connections"),
                    data.get("species_id"),
                    data.get("morphology_json"),
                    data.get("controller_json"),
                ),
            )
            conn.commit()
            row_id = int(cursor.lastrowid)
            return row_id
        finally:
            conn.close()

    def get_best_individual(
        self, experiment_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Return the individual with highest fitness (optionally for an experiment)."""
        conn = self._conn()
        try:
            if experiment_id:
                row = conn.execute(
                    """
                    SELECT * FROM individuals
                    WHERE experiment_id = ?
                    ORDER BY fitness DESC LIMIT 1
                    """,
                    (experiment_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM individuals ORDER BY fitness DESC LIMIT 1"
                ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_individuals(
        self, experiment_id: str, generation: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Return individuals for an experiment, optionally filtered by generation."""
        conn = self._conn()
        try:
            if generation is not None:
                rows = conn.execute(
                    """
                    SELECT * FROM individuals
                    WHERE experiment_id = ? AND generation = ?
                    ORDER BY individual_index
                    """,
                    (experiment_id, generation),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM individuals
                    WHERE experiment_id = ?
                    ORDER BY generation, individual_index
                    """,
                    (experiment_id,),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mean(stats: Dict[str, Any], key: str) -> Optional[float]:
    value = stats.get(key)
    if isinstance(value, dict):
        return value.get("mean")
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _std(stats: Dict[str, Any], key: str) -> Optional[float]:
    value = stats.get(key)
    if isinstance(value, dict):
        return value.get("std")
    return None