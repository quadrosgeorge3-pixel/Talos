"""Immutable experiment metadata and config snapshots."""
from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# ExperimentMetadata
# ---------------------------------------------------------------------------

class ExperimentMetadata:
    """Immutable snapshot of an experiment's config and identity.

    Parameters
    ----------
    config : dict
        Full experiment configuration (must contain ``experiment_id``).
    output_dir : str
        Root output directory for experiments.
    """

    def __init__(self, config: Dict[str, Any], output_dir: str) -> None:
        if "experiment_id" not in config:
            raise ValueError(
                "Config must include an 'experiment_id' field."
            )

        self.config = deepcopy(config)
        self.output_dir = output_dir

        self.experiment_id = config["experiment_id"]
        self.timestamp = _now_iso()

        # Immutable config hash for provenance
        canonical = json.dumps(self.config, sort_keys=True, indent=2)
        self.config_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

        # Store config hash back into the snapshot
        self.config["config_hash"] = self.config_hash

        self.run_dir = os.path.join(output_dir, self.experiment_id)

    # ------------------------------------------------------------------
    # Filesystem helpers
    # ------------------------------------------------------------------

    def ensure_directories(self) -> None:
        """Create the per-experiment output directory tree."""
        for sub in ("elites", "plots", "export"):
            os.makedirs(os.path.join(self.run_dir, sub), exist_ok=True)

    def write_config(self) -> str:
        """Persist the immutable config JSON."""
        path = os.path.join(self.run_dir, "config.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.config, fh, indent=2)
        return path

    def write_metadata(self) -> str:
        """Persist the metadata JSON (immutable snapshot)."""
        path = os.path.join(self.run_dir, "metadata.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.metadata_dict(), fh, indent=2)
        return path

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def metadata_dict(self) -> Dict[str, Any]:
        """Return the JSON-serializable metadata snapshot."""
        return {
            "experiment_id": self.experiment_id,
            "timestamp": self.timestamp,
            "config_hash": self.config_hash,
            "run_dir": self.run_dir,
            "config": self.config,
        }

    def __repr__(self) -> str:
        return (
            f"ExperimentMetadata("
            f"id={self.experiment_id!r}, hash={self.config_hash[:8]})"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_config(path: str) -> Dict[str, Any]:
    """Load and validate an experiment config JSON file."""
    with open(path, "r", encoding="utf-8") as fh:
        config = json.load(fh)
    return config