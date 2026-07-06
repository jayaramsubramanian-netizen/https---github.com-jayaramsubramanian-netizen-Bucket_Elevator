"""
theme.py -- shared color palette for every component in this app.
═══════════════════════════════════════════════════════════════════════════
Mirrors the role of the CSS custom properties (--bg, --panel, --text, etc.)
in the real frontend, and ElevatorSchematic.jsx's own `C` object for the
drawing-specific colors. Every PySide6 component should import from here
rather than keep its own copy -- the three earlier PoC files each had a
slightly different version of this palette, which is exactly the kind of
drift that makes a theme change require touching N files instead of one.
"""

# ── App-wide UI colors (sidebar, panels, text, status) ──────────────────────
BG       = "#0a1628"
PANEL    = "#0d1c2e"
PANEL2   = "#0f2138"
BORDER   = "#1c3050"
TEXT     = "#e8f0fa"
TEXT2    = "#b0c4d8"
TEXT3    = "#5a7a9a"
MUTED    = "#5a7a9a"
PRIMARY  = "#4a9eff"
SUCCESS  = "#1fb86e"
WARNING  = "#d98e00"
DANGER   = "#e05252"
NONE_C   = "#5a7a9a"
# Discipline-tag colors for KpiGrid-style cards (Structural/Discharge) --
# sampled directly from KpiGrid.jsx's own DISC object, not guessed.
PURPLE   = "#a78bfa"
TEAL     = "#14b8a6"
# Sampled directly from the VECTRIX platform title bar image, not guessed.
BRAND_RED = "#b5362f"

STATUS_COLOR = {"ok": SUCCESS, "warn": WARNING, "fail": DANGER, "none": NONE_C}

# ── Drawing-specific colors -- lifted directly from ElevatorSchematic.jsx's
#    own `C` object, not a different scheme, so every ported view (Elevation,
#    Plan, Side, Trajectory, Bucket Detail) stays visually consistent with
#    the others and with the original ──────────────────────────────────────
DRAWING = {
    "bg": "#0f172a", "casing": "#243247", "casFill": "#162032",
    "belt": "#14b8a6", "beltRtn": "#0d9488", "bucket": "#3b82f6",
    "pulley": "#3b82f6", "lagging": "#f59e0b", "hub": "#0f172a",
    "motor": "#10b981", "gearbox": "#059669", "coupling": "#6b7280",
    "dim": "#3d536b", "dimTxt": "#64748b", "label": "#475569", "labelBr": "#94a3b8",
    "feed": "#f59e0b", "chute": "#f59e0b", "text": "#f1f5f9", "text3": "#64748b",
    "traj": "#ef4444", "border": "#243247", "panel": "#162032",
    "success": "#10b981", "warning": "#f59e0b", "danger": "#ef4444",
    "primary": "#3b82f6", "grid": "rgba(59,130,246,.04)", "leg": "#1e3a5a",
}