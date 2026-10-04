"""Morphology genome encoding, mutation, and crossover.

Encodes 7 continuous aircraft parameters as a numpy vector:
    [wingspan, wing_area, h_tail_area, v_tail_area,
     thrust_to_weight, total_mass, cg_x_offset]
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from .controller import morphology_param_names


# ---------------------------------------------------------------------------
# Reference morphology (PyFlyt default fixedwing)
# ---------------------------------------------------------------------------

DEFAULT_MORPHOLOGY: Dict[str, float] = {
    "wingspan": 1.0,
    "wing_area": 0.3,
    "h_tail_area": 0.05,
    "v_tail_area": 0.05,
    "thrust_to_weight": 0.6,
    "total_mass": 1.2,
    "cg_x_offset": 0.0,
}


# ---------------------------------------------------------------------------
# Morphology Genome
# ---------------------------------------------------------------------------

class MorphologyGenome:
    """Continuous-vector morphology genome with PyFlyt-compatible bounds.

    Parameters
    ----------
    params : np.ndarray, optional
        7-float vector of [wingspan, wing_area, h_tail_area, v_tail_area,
        thrust_to_weight, total_mass, cg_x_offset].
        Defaults to ``DEFAULT_MORPHOLOGY``.
    bounds : dict, optional
        Override ``bounds`` block from experiment config.
    """

    def __init__(
        self,
        params: Optional[np.ndarray] = None,
        bounds: Optional[Dict[str, List[float]]] = None,
    ) -> None:
        self.names = morphology_param_names()
        self.bounds = self._default_bounds()
        if bounds is not None:
            self.bounds.update(bounds)

        if params is None:
            params = np.asarray(
                [DEFAULT_MORPHOLOGY[name] for name in self.names],
                dtype=np.float32,
            )
        self.params = self._clamp(np.asarray(params, dtype=np.float32))

    # ------------------------------------------------------------------
    # Encoding / decoding
    # ------------------------------------------------------------------

    @classmethod
    def from_dict(
        cls, values: Dict[str, float], bounds: Optional[Dict[str, List[float]]] = None
    ) -> "MorphologyGenome":
        names = morphology_param_names()
        params = [values.get(name, DEFAULT_MORPHOLOGY[name]) for name in names]
        return cls(params=np.asarray(params, dtype=np.float32), bounds=bounds)

    def to_dict(self) -> Dict[str, float]:
        return {name: float(v) for name, v in zip(self.names, self.params)}

    # ------------------------------------------------------------------
    # Genetic operators
    # ------------------------------------------------------------------

    @property
    def ranges(self) -> np.ndarray:
        return np.asarray(
            [self.bounds[name][1] - self.bounds[name][0] for name in self.names],
            dtype=np.float32,
        )

    def mutate(self, rng: np.random.Generator, rate: float = 0.3) -> "MorphologyGenome":
        """Gaussian mutation scaled by each parameter's range."""
        scale = self.ranges * 0.1
        noise = rng.normal(0.0, 1.0, size=len(self.params)).astype(np.float32) * scale
        mask = rng.random(len(self.params)) < rate
        mutated = self.params + noise * mask
        return MorphologyGenome(params=mutated, bounds=self.bounds)

    def crossover(
        self, other: "MorphologyGenome", alpha: float = 0.5, rng: Optional[np.random.Generator] = None
    ) -> "MorphologyGenome":
        """BLX-alpha blend crossover."""
        rng = rng or np.random.default_rng()
        gamma = (1.0 + 2.0 * alpha) * rng.random(len(self.params))
        gamma = gamma.astype(np.float32)
        child = self.params + gamma * (other.params - self.params)
        return MorphologyGenome(params=child, bounds=self.bounds)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _clamp(self, params: np.ndarray) -> np.ndarray:
        clipped = np.empty_like(params, dtype=np.float32)
        for i, name in enumerate(self.names):
            lo, hi = self.bounds[name]
            clipped[i] = np.clip(params[i], lo, hi)
        return clipped

    @staticmethod
    def _default_bounds() -> Dict[str, List[float]]:
        return {
            "wingspan": [0.8, 3.0],
            "wing_area": [0.15, 1.5],
            "h_tail_area": [0.02, 0.4],
            "v_tail_area": [0.02, 0.3],
            "thrust_to_weight": [0.4, 1.5],
            "total_mass": [0.8, 5.0],
            "cg_x_offset": [-0.05, 0.15],
        }

    def __repr__(self) -> str:
        return f"MorphologyGenome({self.to_dict()})"


def bounds_from_config(config: Dict[str, Any]) -> Dict[str, List[float]]:
    """Pull morphology bounds from experiment config."""
    return config.get("morphology", {}).get("bounds", {})