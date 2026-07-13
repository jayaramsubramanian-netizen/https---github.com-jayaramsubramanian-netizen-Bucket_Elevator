"""
theme.py -- shared design tokens for every component in this app.
═══════════════════════════════════════════════════════════════════════════
CANONICAL SOURCE: frontend/src/index.css  (VECTRIX Design Tokens v2.0).

WHY THIS FILE CHANGED
─────────────────────
The previous version of this file was ported from the *inline fallback*
values inside the JSX -- e.g. InputSidebar.jsx's `T` object reads
`var(--panel, #0d1c2e)`, and #0d1c2e was lifted from there. But that
fallback only applies if the CSS variable is undefined. At runtime the web
app always resolves --panel from index.css, which is v2.0 and says
#162032. So the desktop app was faithfully reproducing a palette the web
app hasn't used since v1 -- every JSX fallback literal in this codebase
is a fossil, not a source of truth.

Three consequences, all now fixed:

  1. Wrong palette. v1 was near-black + #4a9eff blue + #e05252 red;
     v2 is steel-blue depth + #3b82f6 blue + #ef4444 red.

  2. Wrong BORDERS -- this is the box-in-box bug's second root cause.
     index.css v2 states its own intent explicitly: "Borders: 60%
     reduction -- use bg-contrast + spacing instead", and sets
     --border to rgba(255,255,255,.07). The desktop app was running
     v1's solid #1c3050, a hard structural line, on every single frame.

  3. Split-brain. The DRAWING dict below was ALREADY v2 (sampled from
     ElevatorSchematic.jsx's own C object, which uses literals not
     vars). So the CAD/schematic views rendered v2 while all the UI
     chrome rendered v1 -- the app was literally two-toned.

Every constant name from the old file is preserved, so no import
anywhere breaks. Only values changed, plus new tokens + helpers added.

THE OTHER ROOT CAUSE -- READ BEFORE ADDING ANY setStyleSheet
────────────────────────────────────────────────────────────
A stylesheet with NO selector is treated by Qt as `* { ... }` -- it
applies to the widget AND EVERY DESCENDANT. So:

    frame.setStyleSheet("background: X; border: 1px solid Y;")   # BAD

gives a border to the frame *and* to every QLabel, QSpinBox and QComboBox
inside it. That is the box-in-box bug. Verified directly, not assumed: a
QFrame with 4 child QLabels rendered 1732 interior border pixels in 8
horizontal runs (= 4 children x top+bottom edge) with a bare declaration,
and 0 with a scoped one.

Rule from here on: any stylesheet that sets a `border` MUST be scoped.
Use the helpers at the bottom of this file rather than hand-writing it.

    frame.setStyleSheet(card_qss(frame))          # scoped, correct
    frame, layout = card_frame()                  # even better
"""
from typing import Optional

# ══════════════════════════════════════════════════════════════════════════
# Backgrounds -- real depth, not near-black  (index.css v2)
# ══════════════════════════════════════════════════════════════════════════
BG       = "#0f172a"   # --bg      page background
PANEL    = "#162032"   # --panel   primary panels, sidebar
PANEL2   = "#1e293b"   # --panel2  secondary panels, section bg
SURFACE  = "#243247"   # --surface cards, inputs, elevated surfaces
SURFACE2 = "#2d3f57"   # --surface2 hovered surfaces, active states
OVERLAY  = "#0a1220"   # --overlay deepest layer, nav underlay

# ══════════════════════════════════════════════════════════════════════════
# Text hierarchy
# ══════════════════════════════════════════════════════════════════════════
TEXT   = "#f1f5f9"   # --text   headings, values
TEXT2  = "#cbd5e1"   # --text2  labels, descriptions
TEXT3  = "#94a3b8"   # --text3  placeholders, hints
MUTED  = "#64748b"   # --muted  disabled, faint labels
FAINT  = "#3d536b"   # --faint  decorative separators

# NOTE: in the OLD theme.py, TEXT3 and MUTED were the SAME literal
# (#5a7a9a) -- dialog_helpers.py documents the legibility complaint that
# caused. In v2 they are genuinely distinct (#94a3b8 vs #64748b), so the
# distinction between "hint" and "disabled/meta" is now real and the
# contrast problem largely resolves itself.

# ══════════════════════════════════════════════════════════════════════════
# Borders -- subtle, not structural. THE 60% REDUCTION.
# ══════════════════════════════════════════════════════════════════════════
BORDER  = "rgba(255,255,255,.07)"   # --border   default
BORDER2 = "rgba(255,255,255,.12)"   # --border2  stronger / focus rings
BORDER3 = "rgba(255,255,255,.18)"   # --border3  emphasis

# ══════════════════════════════════════════════════════════════════════════
# Primary action -- BLUE
# ══════════════════════════════════════════════════════════════════════════
PRIMARY       = "#3b82f6"
PRIMARY_HOVER = "#2563eb"
PRIMARY_DIM   = "rgba(59,130,246,.15)"
PRIMARY_RING  = "rgba(59,130,246,.35)"

# ══════════════════════════════════════════════════════════════════════════
# Semantic colors -- with their dim/border variants.
#
# These *_DIM / *_BORDER tokens are new. They already existed in the app,
# just hardcoded as rgba() literals in ~15 separate places (main.py's
# fail_warn_badges, ToggleButton, toggle_pair, n_way_selector, every
# advisory card...). Every one of those literals was a v1 color. They now
# live here, once.
# ══════════════════════════════════════════════════════════════════════════
SUCCESS        = "#10b981"
SUCCESS_DIM    = "rgba(16,185,129,.12)"
SUCCESS_BORDER = "rgba(16,185,129,.3)"

WARNING        = "#f59e0b"
WARNING_DIM    = "rgba(245,158,11,.12)"
WARNING_BORDER = "rgba(245,158,11,.3)"

DANGER         = "#ef4444"
DANGER_DIM     = "rgba(239,68,68,.12)"
DANGER_BORDER  = "rgba(239,68,68,.3)"

INFO           = "#38bdf8"
INFO_DIM       = "rgba(56,189,248,.12)"
INFO_BORDER    = "rgba(56,189,248,.3)"

NONE_C = MUTED

STATUS_COLOR = {"ok": SUCCESS, "warn": WARNING, "fail": DANGER, "none": NONE_C}
STATUS_DIM   = {"ok": SUCCESS_DIM, "warn": WARNING_DIM, "fail": DANGER_DIM,
                "info": INFO_DIM, "none": "rgba(100,116,139,.12)"}

# ══════════════════════════════════════════════════════════════════════════
# Brand accent -- logo + critical states only, NOT general UI
# ══════════════════════════════════════════════════════════════════════════
# OPEN DECISION (Jay): index.css v2 declares --brand: #c8192e. The old
# theme.py had #b5362f, sampled from a screenshot of the title bar. A
# screenshot is a rendering (subject to compression, color profile, and
# whatever alpha was composited over it) -- it is NOT a source of truth
# about the intended value, so I've taken index.css as canonical here.
# Say the word and I'll flip it back; this is the one value I've changed
# on judgment rather than on evidence.
BRAND     = "#c8192e"
BRAND2    = "#a01122"
BRAND_DIM = "rgba(200,25,46,.15)"
BRAND_RED = BRAND          # legacy alias -- main.py imports this name

# ══════════════════════════════════════════════════════════════════════════
# Data-viz series + semantic aliases
# ══════════════════════════════════════════════════════════════════════════
CHART1, CHART2, CHART3 = "#3b82f6", "#10b981", "#f59e0b"
CHART4, CHART5         = "#a78bfa", "#38bdf8"

GREEN  = "#10b981"
AMBER  = "#f59e0b"
RED    = "#ef4444"
BLUE   = "#3b82f6"
TEAL   = "#14b8a6"
PURPLE = "#a78bfa"
SKY    = "#38bdf8"

# ══════════════════════════════════════════════════════════════════════════
# Typography / spacing / radius  (index.css v2)
# ══════════════════════════════════════════════════════════════════════════
FF_UI   = '"Inter", "Segoe UI", system-ui, sans-serif'
FF_MONO = '"JetBrains Mono", "Consolas", monospace'

TEXT_XS, TEXT_SM, TEXT_BASE = 11, 12, 13
TEXT_MD, TEXT_LG, TEXT_XL   = 14, 16, 18
TEXT_2XL                    = 22

SP_1, SP_2, SP_3, SP_4, SP_5, SP_6 = 4, 8, 12, 16, 20, 24

R_SM, R_MD, R_LG, R_XL = 6, 8, 12, 16
R_PILL = 999

# ══════════════════════════════════════════════════════════════════════════
# QSS HELPERS -- the single place a border is allowed to be declared
# ══════════════════════════════════════════════════════════════════════════
_CARD_SEQ = [0]


def scoped(widget, decls, selector=None, extra=""):
    """Return a SCOPED stylesheet string for `widget` and apply nothing --
    the caller passes the result to setStyleSheet().

    This is the antidote to the bare-declaration cascade. It gives the
    widget a unique objectName (if it hasn't got one) and wraps `decls`
    in a `Class#name { ... }` selector, so the rules bind to THIS widget
    only and never reach its children.

        frame.setStyleSheet(scoped(frame,
            f"background-color: {PANEL2}; border: 1px solid {BORDER};"))

    `extra` is appended for rules you genuinely DO want (a :hover state, a
    sub-control, a named child class). Write `{sel}` where the widget's own
    selector should go -- it is substituted in:

        btn.setStyleSheet(scoped(btn,
            f"background: {SURFACE}; border: 1px solid {BORDER};",
            extra="{sel}:hover { background: %s; }" % BORDER2))

    Why the placeholder rather than just calling widget.objectName() in the
    caller: scoped() is what ASSIGNS the objectName. At the moment the caller
    builds its `extra` string, objectName() is still empty, so an f-string
    referencing it produces the selector "QPushButton#" -- syntactically
    invalid, silently dropped by Qt's parser, and every hover state quietly
    stops working. Found this while writing main.py's nav buttons.
    """
    name = widget.objectName()
    if not name:
        _CARD_SEQ[0] += 1
        name = f"w{_CARD_SEQ[0]}"
        widget.setObjectName(name)
    cls = widget.metaObject().className()
    sel = f"{cls}#{name}"
    if extra:
        extra = extra.replace("{sel}", sel)
    return f"{sel} {{ {decls} }}\n{extra}"


def card_qss(widget, bg=PANEL2, border=BORDER, radius=R_SM, extra=""):
    """Scoped QSS for a standard card/panel frame. Use this instead of
    hand-writing `background: X; border: 1px solid Y;`."""
    return scoped(
        widget,
        f"background-color: {bg}; border: 1px solid {border}; "
        f"border-radius: {radius}px;",
        extra=extra,
    )


def card_frame(bg=PANEL2, border=BORDER, radius=R_SM,
               margins=(10, 8, 10, 8), spacing=4):
    """Create a correctly-scoped card QFrame + its QVBoxLayout.

    Returns (frame, layout). This is the preferred way to build any
    bordered container -- stat_box, quadrant, advisory card, KPI card,
    wrap-angle box, and so on. Because the border is declared exactly
    once, in one scoped rule, no child can inherit it.
    """
    from PySide6.QtWidgets import QFrame, QVBoxLayout
    frame = QFrame()
    frame.setStyleSheet(card_qss(frame, bg=bg, border=border, radius=radius))
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    return frame, layout


def plain_bg(widget, color):
    """Set ONLY a background color, scoped -- no border, nothing to
    inherit. For containers that just need to match the panel color
    (the exact thing charts_panel's _content needed)."""
    return scoped(widget, f"background-color: {color};")


_STATUS_BORDER = {
    "ok": SUCCESS_BORDER,
    "warn": WARNING_BORDER,
    "fail": DANGER_BORDER,
    "info": INFO_BORDER,
}


def status_card_qss(widget, status: Optional[str] = None, bg=PANEL2, radius=R_SM):
    """Card whose border carries a status tint. Still scoped, still ONE
    border. status: 'ok' | 'warn' | 'fail' | 'info' | None.

    Membership test rather than dict.get(status, BORDER): `status` is
    Optional[str] and dict.get()'s key parameter is str, so passing a
    possibly-None key is a real type error (Pylance reportArgumentType /
    reportCallIssue), not a false positive -- `.get(None, ...)` would
    silently work at runtime but the signature genuinely doesn't accept
    it. This form is both type-correct and clearer about intent: an
    unknown or absent status means the neutral border.
    """
    border = _STATUS_BORDER[status] if status in _STATUS_BORDER else BORDER
    return card_qss(widget, bg=bg, border=border, radius=radius)


# ══════════════════════════════════════════════════════════════════════════
# Drawing-specific colors -- lifted from ElevatorSchematic.jsx's own C
# object. These were already v2 and are UNCHANGED; they now agree with the
# UI palette above instead of clashing with it.
# ══════════════════════════════════════════════════════════════════════════
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