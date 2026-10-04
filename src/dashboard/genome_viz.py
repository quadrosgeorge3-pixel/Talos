"""NEAT genome rendering utilities."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import numpy as np
from matplotlib.patches import Circle, FancyArrowPatch

from .themes import COLORS


# ---------------------------------------------------------------------------
# Node layout
# ---------------------------------------------------------------------------

class GenomeLayout:
    """Computes (x, y) positions for a NEAT network.

    Nodes are placed in layers: inputs on the left, outputs on the
    right, hidden nodes between (sorted by their connection depth).
    """

    def __init__(
        self,
        num_inputs: int,
        num_outputs: int,
        hidden_nodes: Optional[Sequence[int]] = None,
        connections: Optional[Dict[Any, float]] = None,
    ) -> None:
        self.num_inputs = num_inputs
        self.num_outputs = num_outputs
        self.hidden_nodes = list(hidden_nodes or [])
        self.connections = connections or {}

        self._positions: Dict[int, np.ndarray] = {}
        self._compute()

    # ------------------------------------------------------------------

    def _compute(self) -> None:
        margin_x = 0.04
        margin_y = 0.06

        # Inputs
        for i in range(self.num_inputs):
            self._positions[-(i + 1)] = np.array(
                [margin_x, margin_y + 0.25 + i * (0.5 / max(self.num_inputs - 1, 1)) * 0.9]
            )

        # Outputs
        for j in range(self.num_outputs):
            self._positions[j + 1] = np.array(
                [1.0 - margin_x, margin_y + 0.25 + j * (0.5 / max(self.num_outputs - 1, 1)) * 0.9]
            )

        # Hidden nodes: fan out in the middle, sorted by id for stability
        n_hidden = len(self.hidden_nodes)
        if n_hidden:
            ys = np.linspace(0.08, 0.92, n_hidden)
            xs = np.linspace(0.25, 0.75, max(n_hidden, 1))
            for idx, hidden_id in enumerate(sorted(self.hidden_nodes)):
                self._positions[hidden_id] = np.array([xs[idx], ys[idx]])

    # ------------------------------------------------------------------

    def position(self, node_id: int) -> np.ndarray:
        return self._positions.get(
            node_id,
            np.array([0.5, 0.5]),
        )


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

class GenomeVisualizer:
    """Draws a NEAT genome onto a matplotlib axes.

    - Input nodes : blue circles
    - Output nodes: red circles
    - Hidden nodes: gray circles, smaller
    - Connections : lines whose thickness scales with |weight| and
      color encodes sign (positive = green, negative = red)
    """

    def __init__(self, ax: Any, num_inputs: int = 15, num_outputs: int = 6) -> None:
        self.ax = ax
        self.num_inputs = num_inputs
        self.num_outputs = num_outputs

    # ------------------------------------------------------------------

    def draw(
        self,
        node_ids: Optional[Sequence[int]] = None,
        connection_weights: Optional[Dict[str, float]] = None,
        fitness: Optional[float] = None,
        title: str = "NEAT GENOME",
    ) -> None:
        """Render the genome.

        Parameters
        ----------
        node_ids : list of int | None
            Active node ids. Inputs are ``-(i+1)``, outputs ``j+1``.
        connection_weights : dict | None
            Mapping ``"in->out"`` to weight value.
        fitness : float | None
            Current fitness of the displayed genome.
        title : str
            Panel title.
        """
        self.ax.clear()
        self.ax.set_axis_off()
        self.ax.set_title(
            title,
            color=COLORS["accent"],
            fontsize=11,
            fontweight="bold",
            pad=8,
        )

        hidden_nodes = self._extract_hidden_nodes(node_ids)

        layout = GenomeLayout(
            num_inputs=self.num_inputs,
            num_outputs=self.num_outputs,
            hidden_nodes=hidden_nodes,
            connections=connection_weights,
        )

        # Draw connections first (underneath nodes)
        if connection_weights:
            max_weight = max(
                (abs(w) for w in connection_weights.values()), default=1.0
            )
            max_weight = max(max_weight, 1e-6)

            for conn_key, weight in connection_weights.items():
                in_id, out_id = _parse_connection_key(conn_key)
                start = layout.position(in_id)
                end = layout.position(out_id)

                thickness = 0.5 + 3.0 * (abs(weight) / max_weight)
                color = (
                    COLORS["positive"] if weight >= 0 else COLORS["negative"]
                )
                alpha = min(0.25 + abs(weight) / max_weight * 0.75, 0.9)

                self.ax.plot(
                    [start[0], end[0]],
                    [start[1], end[1]],
                    color=color,
                    alpha=alpha,
                    linewidth=thickness,
                    zorder=1,
                )

        # Input nodes
        for i in range(self.num_inputs):
            node_id = -(i + 1)
            self._draw_node(
                layout.position(node_id),
                radius=0.018,
                color=COLORS["input"],
                label=f"I{i}",
                fontsize=5,
                label_on="left",
            )

        # Output nodes
        for j in range(self.num_outputs):
            node_id = j + 1
            self._draw_node(
                layout.position(node_id),
                radius=0.018,
                color=COLORS["output"],
                label=f"O{j}",
                fontsize=5,
                label_on="right",
            )

        # Hidden nodes
        for node_id in hidden_nodes:
            self._draw_node(
                layout.position(node_id),
                radius=0.012,
                color=COLORS["hidden"],
                label=str(node_id),
                fontsize=4,
                label_on="above",
            )

        # Fitness readout
        if fitness is not None:
            self.ax.text(
                0.5, 0.02,
                f"fitness = {fitness:.2f}",
                transform=self.ax.transAxes,
                ha="center",
                va="bottom",
                color=COLORS["text"],
                fontsize=8,
            )

        self.ax.set_xlim(0, 1)
        self.ax.set_ylim(0, 1)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _draw_node(
        self,
        position: np.ndarray,
        radius: float,
        color: str,
        label: str,
        fontsize: float,
        label_on: str = "above",
    ) -> None:
        circle = Circle(
            position,
            radius=radius,
            color=color,
            alpha=0.85,
            zorder=2,
        )
        self.ax.add_patch(circle)

        offset = {"above": (0.0, radius + 0.005),
                  "left": (-radius - 0.005, 0.0),
                  "right": (radius + 0.005, 0.0)}[label_on]
        ha = {"above": "center", "left": "right", "right": "left"}[label_on]

        self.ax.text(
            position[0] + offset[0],
            position[1] + offset[1],
            label,
            ha=ha,
            va="center",
            fontsize=fontsize,
            fontfamily=COLORS["text"],
            color="#9fb0c0",
            zorder=3,
        )

    @staticmethod
    def _extract_hidden_nodes(node_ids: Optional[Sequence[int]]) -> List[int]:
        """Filter active nodes down to hidden (non-input, non-output) ids."""
        if node_ids is None:
            return []

        hidden = []
        for node_id in node_ids:
            try:
                value = int(node_id)
            except (TypeError, ValueError):
                continue
            if value > 0:  # positive ids → hidden or output
                hidden.append(value)
        return hidden


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_connection_key(key: str) -> tuple[int, int]:
    """Parse ``"in->out"`` (or ``"3->1"``) keys into node id pair."""
    key = key.replace("(", "").replace(")", "").strip()
    if "->" in key:
        left, right = key.split("->", 1)
    elif "," in key:
        left, right = key.split(",", 1)
    else:
        return (-1, 1)
    return int(left.strip()), int(right.strip())