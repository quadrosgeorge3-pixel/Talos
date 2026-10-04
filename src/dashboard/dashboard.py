"""EvolutionDashboard — live 6-panel monitor for the Icarus project.

Panels (2 x 3 grid):

    [0,0] NEAT GENOME        network topology + weights
    [0,1] NETWORK STATS      nodes / connections / species / mutations
    [0,2] EXPERIMENT STATUS  generation, phase, system health
    [1,0] AIRFRAME PARAMS    morphology values + silhouette
    [1,1] BASELINE COMPARISON current best vs PyFlyt PID reference
    [1,2] FITNESS PROGRESSION best / mean over generations

The dashboard works in two modes:

- Setup mode (no experiment): shows baseline-only data, placeholder
  genome, and setup status.
- Live mode: reads the experiment SQLite DB on every refresh and
  redraws with real evolution data.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

import matplotlib
matplotlib.use("TkAgg")

import matplotlib.pyplot as plt
from matplotlib import animation
import numpy as np

from src.experiment.db import ExperimentDB
from src.experiment.metadata import load_config
from src.genome.controller import NEATController
from src.genome.morphology import MorphologyGenome, DEFAULT_MORPHOLOGY
from src.dashboard.genome_viz import GenomeVisualizer
from src.dashboard.layout import (
    draw_metric_bar,
    draw_status_row,
    draw_text_panel,
)
from src.dashboard.themes import ASCII_BANNER, COLORS


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class EvolutionDashboard:
    """Live monitoring dashboard for the Icarus project.

    Parameters
    ----------
    experiment_id : str | None
        If set, stream data from that experiment's SQLite database.
        If ``None``, run in setup mode (baseline-only).
    output_dir : str
        Root directory containing experiment outputs.
    config_path : str | None
        Optional experiment config used to bootstrap the NEAT stub.
    update_interval : float
        Seconds between UI refreshes.
    """

    def __init__(
        self,
        experiment_id: Optional[str] = None,
        output_dir: str = "output",
        config_path: Optional[str] = None,
        update_interval: float = 1.0,
    ) -> None:
        self.experiment_id = experiment_id
        self.output_dir = output_dir
        self.update_interval = update_interval
        self.is_running = False

        # Data backends
        self.db = ExperimentDB(os.path.join(output_dir, "icarus.db"))
        self._config: Optional[Dict[str, Any]] = None
        if config_path and os.path.isfile(config_path):
            self._config = load_config(config_path)

        # Baseline
        self.baseline: Optional[Dict[str, Any]] = None
        if experiment_id:
            self.baseline = self.db.get_latest_baseline(experiment_id)
        if self.baseline is None:
            self.baseline = self.db.get_baseline("B0_default_pid")

        # NEAT stub
        self.neat: Optional[NEATController] = None
        if self._config is not None:
            try:
                self.neat = NEATController(self._config)
            except Exception:
                self.neat = None

        # Current best data (updated on each refresh)
        self.current_best: Optional[Dict[str, Any]] = None
        self.latest_generation: Optional[int] = None
        self.fitness_history: list[Dict[str, Any]] = []

        # Genome visualization
        self.num_inputs = int((self._config or {}).get("controller", {}).get(
            "num_inputs", 15
        ))
        self.num_outputs = int((self._config or {}).get("controller", {}).get(
            "num_outputs", 6
        ))

        # Figure
        plt.style.use("dark_background")
        self.figure, self.axes = plt.subplots(2, 3, figsize=(18, 10))
        self.figure.patch.set_facecolor(COLORS["background"])
        self.figure.subplots_adjust(left=0.03, right=0.97, top=0.95, bottom=0.04, hspace=0.35)

        self.genome_viz = GenomeVisualizer(
            self.axes[0, 0],
            num_inputs=self.num_inputs,
            num_outputs=self.num_outputs,
        )

        self._anim: Optional[animation.FuncAnimation] = None
        self._apply_theme()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Launch the live dashboard."""
        self.is_running = True

        self._anim = animation.FuncAnimation(
            self.figure,
            self._refresh,
            interval=self.update_interval * 1000,
            blit=False,
            cache_frame_data=False,
            init_func=lambda: None,
        )

        plt.show()

    def stop(self) -> None:
        """Stop the update loop and close the window."""
        self.is_running = False
        if self._anim is not None:
            self._anim.event_source.stop()
        plt.close(self.figure)

    # ------------------------------------------------------------------
    # Data refresh
    # ------------------------------------------------------------------

    def _refresh(self, _frame: int = 0) -> None:
        """Pull latest data and redraw all panels."""
        if not self.is_running:
            return

        self._poll_latest_data()

        # Redraw everything
        self._draw_genome_panel()
        self._draw_stats_panel()
        self._draw_status_panel()
        self._draw_morphology_panel()
        self._draw_baseline_panel()
        self._draw_fitness_panel()

        # Avoid sluggish text layout stackup
        for ax in self.axes.flat:
            try:
                ax.set_axis_off()
            except Exception:
                pass

        self.figure.canvas.draw_idle()

    def _poll_latest_data(self) -> None:
        """Refresh experiment data from SQLite."""
        if self.experiment_id:
            history = self.db.get_generation_history(self.experiment_id)
            self.fitness_history = history
            if history:
                self.latest_generation = int(history[-1]["generation"])

                # Best individual of latest generation (first result)
                best_row = self._best_individual_of_latest()
                if best_row is not None:
                    self.current_best = best_row

    def _best_individual_of_latest(self) -> Optional[Dict[str, Any]]:
        if not self.experiment_id or self.latest_generation is None:
            return None
        try:
            with self.db._connect() as conn:
                row = conn.execute(
                    """
                    SELECT * FROM individuals
                    WHERE experiment_id = ? AND generation = ?
                    ORDER BY fitness DESC LIMIT 1
                    """,
                    (self.experiment_id, self.latest_generation),
                ).fetchone()
            return dict(row) if row else None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Panels
    # ------------------------------------------------------------------

    def _draw_genome_panel(self) -> None:
        """[0,0] NEAT genome topology + weights."""
        if self.current_best is not None and self.current_best.get("controller_json"):
            try:
                import json
                genome = json.loads(self.current_best["controller_json"])
                node_ids = [int(n) for n in genome.get("node_ids", [])]
                weights = {
                    str(k): float(v)
                    for k, v in genome.get("connection_weights", {}).items()
                }
                self.genome_viz.draw(
                    node_ids=node_ids,
                    connection_weights=weights,
                    fitness=self.current_best.get("fitness"),
                    title="NEAT GENOME",
                )
                return
            except Exception:
                pass

        # Placeholder: minimal input->output network
        self.genome_viz.draw(
            node_ids=[],
            connection_weights={},
            fitness=None,
            title="NEAT GENOME — SETUP MODE",
        )
        self.axes[0, 0].text(
            0.5, 0.03,
            "Awaiting evolution data — showing architecture stub",
            transform=self.axes[0, 0].transAxes,
            ha="center",
            va="bottom",
            fontsize=7,
            color=COLORS["muted"],
        )

    def _draw_stats_panel(self) -> None:
        """[0,1] NEAT network statistics."""
        if self.neat is not None and hasattr(self.neat.population, "best_genome"):
            summary = self.neat.get_genome_summary()
        else:
            summary = {}

        neat_cfg = (self._config or {}).get("neat_config", {})
        ctrl_cfg = (self._config or {}).get("controller", {})

        lines = [
            ("ARCHITECTURE", f"{self.num_inputs}->{self.num_outputs}", COLORS["text"]),
            ("GENOME ID", f"#{summary.get('id', '-')}", COLORS["text"]),
            ("GENOME FITNESS", _fmt_fitness(summary.get("fitness")), COLORS["text"]),
            ("", "", COLORS["text"]),
            ("NODES", f"{summary.get('nodes_active', 0)}/{summary.get('nodes_total', '-')}",
             _color_for_fraction(summary.get("nodes_active"), summary.get("nodes_total"))),
            ("CONNECTIONS", f"{summary.get('connections_enabled', 0)}/{summary.get('connections_total', '-')}",
             _color_for_fraction(summary.get("connections_enabled"), summary.get("connections_total"))),
            ("SPECIES", f"{self._species_count()}", COLORS["text"]),
            ("", "", COLORS["text"]),
            ("ACTIVATION", ctrl_cfg.get("activation", "tanh"), COLORS["text"]),
            ("WT MUT RATE", fmt_pct(neat_cfg.get("weight_mutate_rate", 0.8)), COLORS["text"]),
            ("BIAS MUT RATE", fmt_pct(neat_cfg.get("bias_mutate_rate", 0.7)), COLORS["text"]),
            ("NODE ADD PROB", fmt_pct(neat_cfg.get("node_add_prob", 0.3)), COLORS["warning"]),
            ("CONN ADD PROB", fmt_pct(neat_cfg.get("conn_add_prob", 0.5)), COLORS["warning"]),
        ]
        draw_text_panel(self.axes[0, 1], "NETWORK STATS", lines)

    def _draw_status_panel(self) -> None:
        """[0,2] Experiment phase + system health."""
        ax = self.axes[0, 2]
        ax.clear()
        ax.set_axis_off()
        ax.set_facecolor(COLORS["panel"])
        ax.set_title("EXPERIMENT STATUS", color=COLORS["accent"], fontsize=11, fontweight="bold", pad=8)

        # Title banner
        ax.text(
            0.5, 0.98, ASCII_BANNER,
            transform=ax.transAxes, ha="center", va="top",
            fontsize=7, fontfamily="monospace", color=COLORS["accent_dim"],
        )

        phase = "EXPERIMENT LIVE" if self.experiment_id else "SETUP — PRE-EXPERIMENT"
        phase_level = "ok" if self.experiment_id else "warn"

        draw_status_row(ax, "MODE", phase_level, 0.74, detail=f"Gen {self.latest_generation or 0}")
        draw_status_row(ax, "SIMULATION", "ok", 0.66, detail="PyFlyt wired")
        draw_status_row(ax, "DATABASE", "ok", 0.58, detail="SQLite connected")

        db_level = "ok" if self.db is not None else "off"
        draw_status_row(ax, "LOGGING", db_level, 0.50, detail="baseline stored")

        neat_level = "ok" if self.neat is not None else "warn"
        draw_status_row(ax, "NEAT BRAIN", neat_level, 0.42,
                        detail="population ready" if self.neat else "config needed")

        baseline_level = "ok" if self.baseline is not None else "warn"
        draw_status_row(ax, "BASELINE PID", baseline_level, 0.34,
                        detail=f"survival {self.baseline.get('survival_time_mean', 0):.1f}s"
                        if self.baseline else "not yet measured")

        # Next steps hint in setup mode
        if not self.experiment_id:
            ax.text(
                0.06, 0.22,
                "NEXT STEPS\n"
                "\u25b8 run baseline:  python run.py --baseline\n"
                "\u25b8 launch demo:    python run.py --dashboard\n"
                "\u25b8 experiments:    python run.py --experiment <config>",
                transform=ax.transAxes, ha="left", va="top",
                fontsize=7.5, fontfamily="monospace", color=COLORS["text"],
                linespacing=1.5,
            )

    def _draw_morphology_panel(self) -> None:
        """[1,0] Airframe parameters + silhouette."""
        ax = self.axes[1, 0]
        params = dict(DEFAULT_MORPHOLOGY)

        if self.current_best is not None and self.current_best.get("morphology_json"):
            try:
                import json
                stored = json.loads(self.current_best["morphology_json"])
                params.update(stored)
            except Exception:
                pass

        # Draw silhouette (scaled skyline)
        self._draw_aircraft_silhouette(ax, params)

        # Parameter text block
        bounds = (self._config or {}).get("morphology", {}).get("bounds", {})
        lines = [
            ("WINGSPAN", f"{params['wingspan']:.2f} m", _range_color(params['wingspan'], bounds.get('wingspan'))),
            ("WING AREA", f"{params['wing_area']:.2f} m²", _range_color(params['wing_area'], bounds.get('wing_area'))),
            ("H-TAIL", f"{params['h_tail_area']:.3f} m²", _range_color(params['h_tail_area'], bounds.get('h_tail_area'))),
            ("V-TAIL", f"{params['v_tail_area']:.3f} m²", _range_color(params['v_tail_area'], bounds.get('v_tail_area'))),
            ("T/W RATIO", f"{params['thrust_to_weight']:.2f}", _range_color(params['thrust_to_weight'], bounds.get('thrust_to_weight'))),
            ("MASS", f"{params['total_mass']:.2f} kg", _range_color(params['total_mass'], bounds.get('total_mass'))),
            ("CG OFFSET", f"{params['cg_x_offset']:+.3f} m", _range_color(params['cg_x_offset'], bounds.get('cg_x_offset'))),
        ]
        draw_text_panel(ax, "AIRFRAME PARAMS", lines, title_color=COLORS["accent"])

        ax.text(
            0.12, 0.10,
            "▸ M = model dir  |  ▸ R = regenerate  |  ▸ Q = quit",
            transform=ax.transAxes, ha="left", va="bottom",
            fontsize=7, fontfamily="monospace", color=COLORS["muted"],
        )

    def _draw_baseline_panel(self) -> None:
        """[1,1] Baseline vs current best."""
        ax = self.axes[1, 1]
        ax.clear()
        ax.set_axis_off()
        ax.set_facecolor(COLORS["panel"])
        ax.set_title("BASELINE VS CURRENT", color=COLORS["accent"], fontsize=11, fontweight="bold", pad=8)

        ref = self.baseline or {}
        best = self.current_best or {}

        # Helper to extract a metric for both sides
        def values(key: str) -> tuple[float, float]:
            baseline_val = ref.get(f"{key}_mean", 0.0) if ref else 0.0
            best_val = best.get(key, 0.0) or 0.0
            return float(baseline_val), float(best_val)

        survival_b, survival_c = values("survival_time")
        distance_b, distance_c = values("distance")
        energy_b, energy_c = values("energy")

        # Normalize: fall back to heuristic max bounds if baseline absent
        max_survival = max(survival_b, survival_c, 10.0)
        max_distance = max(distance_b, distance_c, 100.0)
        max_energy = max(energy_b, energy_c, 1e-9)

        draw_metric_bar(ax, "SURVIVAL", survival_b / max_survival, 0.80,
                        color=COLORS["accent_dim"], show_value=f"pid  {survival_b:.1f}s")
        draw_metric_bar(ax, "CURRENT", survival_c / max_survival, 0.70,
                        color=_bar_color(survival_c, survival_b),
                        show_value=f"best {survival_c:.1f}s")

        draw_metric_bar(ax, "DISTANCE", distance_b / max_distance, 0.50,
                        color=COLORS["accent_dim"], show_value=f"pid  {distance_b:.0f}m")
        draw_metric_bar(ax, "CURRENT", distance_c / max_distance, 0.40,
                        color=_bar_color(distance_c, distance_b),
                        show_value=f"best {distance_c:.0f}m")

        draw_metric_bar(ax, "ENERGY", energy_b / max_energy, 0.20,
                        color=COLORS["accent_dim"], show_value=f"pid  {energy_b:.1f}")
        draw_metric_bar(ax, "CURRENT", energy_c / max_energy, 0.10,
                        color=_bar_color(-energy_c, -energy_b),
                        show_value=f"best {energy_c:.1f}")

        ax.text(
            0.98, 0.985, "lower energy = better",
            transform=ax.transAxes, ha="right", va="top",
            fontsize=6.5, color=COLORS["muted"],
        )

        if best is None:
            ax.text(
                0.5, 0.03,
                "No evolved individual yet — baseline stored as reference",
                transform=ax.transAxes, ha="center", va="bottom",
                fontsize=7, color=COLORS["warning"],
            )

    def _draw_fitness_panel(self) -> None:
        """[1,2] Fitness progression."""
        ax = self.axes[1, 2]
        ax.clear()
        ax.set_facecolor(COLORS["panel"])
        ax.set_title("FITNESS PROGRESSION", color=COLORS["accent"], fontsize=11, fontweight="bold", pad=8)

        if self.fitness_history:
            gens = [g["generation"] for g in self.fitness_history]
            best = [g.get("best_fitness", 0.0) for g in self.fitness_history]
            mean = [g.get("mean_fitness", 0.0) for g in self.fitness_history]
            worst = [g.get("worst_fitness", 0.0) for g in self.fitness_history]

            ax.plot(gens, best, color=COLORS["healthy"], linewidth=1.8, label="best", marker="o", markersize=2.5)
            ax.plot(gens, mean, color=COLORS["positive"], linewidth=1.2, alpha=0.8, label="mean")
            ax.plot(gens, worst, color=COLORS["critical"], linewidth=0.9, alpha=0.6, label="worst")
            ax.fill_between(gens, worst, best, color=COLORS["accent_dim"], alpha=0.10)
            ax.legend(loc="upper left", fontsize=7, frameon=False, labelcolor=COLORS["text"])
        else:
            ax.text(
                0.5, 0.5,
                "No generations logged\nEvolution begins in experiment phase",
                transform=ax.transAxes, ha="center", va="center",
                fontsize=10, color=COLORS["muted"],
            )

            # Show baseline as a reference line
            if self.baseline:
                ref = self.baseline.get("survival_time_mean", 0.0)
                ax.axhline(y=ref, color=COLORS["warning"], linestyle="--", alpha=0.8)
                ax.text(
                    0.02, ref, f"  baseline survival {ref:.1f}s",
                    transform=ax.transAxes, ha="left",
                    fontsize=7, color=COLORS["warning"], va="bottom",
                )

        ax.set_xlabel("generation", fontsize=8, color=COLORS["muted"])
        ax.set_ylabel("fitness", fontsize=8, color=COLORS["muted"])
        ax.tick_params(colors=COLORS["muted"], labelsize=7)
        for spine in ax.spines.values():
            spine.set_color(COLORS["grid"])
        ax.grid(True, alpha=0.15, color=COLORS["grid"])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _apply_theme(self) -> None:
        """Style all axes uniformly."""
        for row in range(2):
            for col in range(3):
                ax = self.axes[row, col]
                ax.set_facecolor(COLORS["panel"])
                for spine in ax.spines.values():
                    spine.set_color(COLORS["grid"])
                ax.tick_params(colors=COLORS["muted"], labelsize=7)

    def _species_count(self) -> int:
        try:
            if self.neat is not None:
                return len(self.neat.population.species.species)
        except Exception:
            pass
        return 0

    def _draw_aircraft_silhouette(self, ax: Any, params: Dict[str, float]) -> None:
        """Draw a simple scaled top-down aircraft on the upper portion."""
        wingspan = params.get("wingspan", 1.0)
        wing_area = params.get("wing_area", 0.3)
        h_tail = params.get("h_tail_area", 0.05)
        v_tail = params.get("v_tail_area", 0.05)

        # Scale factors (normalized by reference)
        span_scale = wingspan / 1.0
        area_scale = wing_area / 0.3
        tail_scale_h = h_tail / 0.05
        tail_scale_v = v_tail / 0.05

        cx = 0.10  # centerline x (panel left side)
        cy = 0.62  # centerline y (upper portion of panel)

        # Fuselage (small rectangle)
        fuselage_w = 0.10 * area_scale ** 0.5
        fuselage_h = 0.16 * area_scale ** 0.5
        ax.add_patch(
            plt.Rectangle(
                (cx - fuselage_w / 2, cy - fuselage_h / 2),
                fuselage_w, fuselage_h,
                facecolor="#33404f", edgecolor=COLORS["accent_dim"],
                linewidth=1.0, zorder=1,
            )
        )

        # Main wing
        wing_span = 0.28 * span_scale
        wing_depth = 0.05 * area_scale ** 0.5
        ax.add_patch(
            plt.Rectangle(
                (cx - wing_span / 2, cy + fuselage_h / 2),
                wing_span, wing_depth,
                facecolor="#4a6b8a", edgecolor=COLORS["accent"],
                linewidth=0.8, alpha=0.85, zorder=2,
            )
        )

        # Horizontal tail
        h_span = 0.10 * tail_scale_h
        h_depth = 0.035 * tail_scale_h
        ax.add_patch(
            plt.Rectangle(
                (cx - h_span / 2, cy - fuselage_h / 2 - h_depth),
                h_span, h_depth,
                facecolor="#6a8a6a", edgecolor=COLORS["accent_dim"],
                linewidth=0.6, alpha=0.85, zorder=2,
            )
        )

        # Vertical tail stab (side view projection)
        v_h = 0.07 * tail_scale_v
        ax.add_patch(
            plt.Rectangle(
                (cx + fuselage_w / 2 - 0.01, cy + fuselage_h / 2),
                0.015, v_h,
                facecolor="#8a6a6a", edgecolor=COLORS["accent_dim"],
                linewidth=0.6, alpha=0.85, zorder=2,
            )
        )

        # Thruster indicator
        ax.text(
            cx, cy - fuselage_h / 2 - h_depth - 0.02,
            "\u25b2 THRUST",
            fontsize=6, ha="center", va="top",
            fontfamily="monospace", color=COLORS["accent_dim"],
        )


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _fmt_fitness(value: Any) -> str:
    if value is None:
        return "-"
    return f"{float(value):.3f}"


def _color_for_fraction(value: Any, total: Any) -> str:
    try:
        v, t = float(value), float(total)
        if t <= 0:
            return COLORS["text"]
        frac = v / t
    except (TypeError, ValueError):
        return COLORS["text"]
    if frac < 0.5:
        return COLORS["degraded"]
    return COLORS["text"]


def _range_color(value: float, bounds: Any) -> str:
    if not bounds:
        return COLORS["text"]
    lo, hi = bounds
    if lo <= value <= hi:
        return COLORS["healthy"]
    return COLORS["critical"]


def _bar_color(current: float, baseline: float) -> str:
    if baseline <= 0:
        return COLORS["healthy"]
    ratio = current / baseline
    if ratio >= 1.0:
        return COLORS["healthy"]
    if ratio >= 0.7:
        return COLORS["degraded"]
    return COLORS["critical"]


def fmt_pct(value: Any) -> str:
    try:
        return f"{float(value) * 100:.0f}%"
    except (TypeError, ValueError):
        return "-"