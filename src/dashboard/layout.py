"""Panel rendering helpers shared across dashboard views."""
from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

from .themes import COLORS


# ---------------------------------------------------------------------------
# Text panels
# ---------------------------------------------------------------------------

def draw_text_panel(
    ax: Any,
    title: str,
    lines: Sequence[Sequence],
    background: str = COLORS["panel"],
    title_color: str = COLORS["accent"],
) -> None:
    """Render a titled panel of (label, value, color) rows.

    Parameters
    ----------
    ax : matplotlib Axes
        Target axes.
    title : str
        Panel title.
    lines : sequence of tuples
        Each row is ``(label, value, color_tuple)`` where ``color_tuple``
        is ``(value_text, status_color)``.
    """
    ax.clear()
    ax.set_axis_off()
    ax.set_facecolor(background)
    ax.set_title(
        title,
        color=title_color,
        fontsize=11,
        fontweight="bold",
        pad=8,
    )

    y = 0.93
    row_height = 0.075

    for label, value, color in lines:
        ax.text(
            0.06, y, label,
            transform=ax.transAxes,
            ha="left", va="top",
            fontsize=8.5,
            fontfamily="monospace",
            color=COLORS["muted"],
        )
        ax.text(
            0.97, y, value,
            transform=ax.transAxes,
            ha="right", va="top",
            fontsize=8.5,
            fontfamily="monospace",
            color=color,
            fontweight="bold",
        )
        y -= row_height

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)


# ---------------------------------------------------------------------------
# Status indicators
# ---------------------------------------------------------------------------

def status_dot(level: str) -> str:
    """Map a status level to a colored dot glyph.

    Parameters
    ----------
    level : str
        One of ``"ok"``, ``"warn"``, ``"bad"``, ``"off"``.
    """
    glyph = "\u25cf"  # ●
    if level == "off":
        return glyph
    return glyph


def status_color(level: str) -> str:
    mapping = {
        "ok": COLORS["healthy"],
        "warn": COLORS["degraded"],
        "bad": COLORS["critical"],
        "off": COLORS["muted"],
    }
    return mapping.get(level, COLORS["muted"])


def draw_status_row(
    ax: Any,
    label: str,
    level: str,
    y: float,
    detail: str = "",
) -> None:
    """Draw one labeled status row with a colored dot."""
    ax.text(
        0.06, y, label,
        transform=ax.transAxes,
        ha="left", va="center",
        fontsize=8.5,
        fontfamily="monospace",
        color=COLORS["text"],
    )
    ax.text(
        0.58, y, status_dot(level),
        transform=ax.transAxes,
        ha="left", va="center",
        fontsize=14,
        color=status_color(level),
    )
    if detail:
        ax.text(
            0.97, y, detail,
            transform=ax.transAxes,
            ha="right", va="center",
            fontsize=8,
            fontfamily="monospace",
            color=COLORS["muted"],
        )


# ---------------------------------------------------------------------------
# Value bars
# ---------------------------------------------------------------------------

def draw_metric_bar(
    ax: Any,
    label: str,
    fraction: float,
    y: float,
    color: Optional[str] = None,
    show_value: str = "",
) -> None:
    """Draw a horizontal bar representing a normalized metric."""
    fraction = max(0.0, min(1.0, fraction))
    color = color or (
        COLORS["healthy"] if fraction >= 0.6
        else COLORS["degraded"] if fraction >= 0.3
        else COLORS["critical"]
    )

    ax.text(
        0.06, y, label,
        transform=ax.transAxes,
        ha="left", va="center",
        fontsize=8.5,
        fontfamily="monospace",
        color=COLORS["text"],
    )

    bar_y = y - 0.012
    ax.barh(
        bar_y, 1.0,
        left=0.06,
        height=0.028,
        transform=ax.transAxes,
        color="#16202c",
        edgecolor="none",
    )
    ax.barh(
        bar_y, fraction * 0.82,
        left=0.06,
        height=0.028,
        transform=ax.transAxes,
        color=color,
        alpha=0.9,
        edgecolor="none",
    )

    if show_value:
        ax.text(
            0.97, y, show_value,
            transform=ax.transAxes,
            ha="right", va="center",
            fontsize=8,
            fontfamily="monospace",
            color=COLORS["text"],
        )