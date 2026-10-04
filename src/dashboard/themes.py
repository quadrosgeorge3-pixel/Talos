"""Color schemes, typography, and ASCII art for the dashboard."""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Dark cockpit palette
# ---------------------------------------------------------------------------

COLORS = {
    "background": "#0a0e14",
    "panel": "#0f151d",
    "grid": "#1c2735",
    "text": "#c8d3e0",
    "muted": "#5a6b7d",
    "accent": "#00ff9f",       # neon green
    "accent_dim": "#00996a",
    "input": "#4a9eff",        # blue
    "output": "#ff6b6b",       # red
    "hidden": "#8a92a3",       # gray
    "positive": "#00e676",
    "negative": "#ff5252",
    "warning": "#ffd740",
    "critical": "#ff1744",
    "healthy": "#00e676",
    "degraded": "#ffd740",
}

FONT_MONO = "DejaVu Sans Mono"
FONT_SANS = "DejaVu Sans"

# ---------------------------------------------------------------------------
# ASCII art assets
# ---------------------------------------------------------------------------

# Top-down / side view tube-and-wing silhouette, parameterized later
AIRCRAFT_ART = r"""
              ___________________
             /                   \
            /                     \
           |        FUSELAGE       |
      _____|_______________________|_____
     /     |                       |     \
    |      |                       |      |
    |______|_______________________|______|
           |                       |
            \_/                 \_/
             |                    |
        (h-tail)             (v-tail)
"""

# Side silhouette used in terminal mode
AIRCRAFT_SIDE = r"""
        _____
       /     \      <- wing span
      |       |
      |       |     <- fuselage
      |       |
       \     /
        | | |       <- tails
"""

AIRCRAFT_SIDE_BY_LINES = [
    "        ____        ",
    "       /    \\      <- wing span",
    "      |      |",
    "      |      |      <- fuselage",
    "      |      |",
    "       \\    /",
    "        | | |       <- tail",
]

# Status glyphs
GLYPH = {
    "ok": "\u25cf",        # ●
    "warn": "\u25d2",      # ◒
    "bad": "\u25cf",       # ● (colored red)
    "arrow": "\u25b8",     # ▸
    "bar_full": "\u2588",  # █
    "bar_empty": "\u2591", # ░
}

ASCII_BANNER = r"""
   _   _   ___    __   ___   ____  _   _    ___  ____  ____  _____
  (_)_| | |__  )  / | |__  )|  _ \| | | |  / __||  _ \|  __||    /
  | | | |  /_  | | | | /_  || |_) | |_| | | |__ | |_) | \_  | ]_ \
  | | | | | |) | | | | | >  ||   __|  _  |  \__ \|  __/| | | | __/
  |_|_|_| |___/| |_| | |_|)||_|    |_| |_|  |___/|_|   |___|    /
"""