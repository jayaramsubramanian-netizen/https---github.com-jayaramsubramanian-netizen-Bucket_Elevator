"""
components/status_panel.py -- Status column KPI grid (port of KpiGrid.jsx).
═══════════════════════════════════════════════════════════════════════════
Category tag + status pill, label, big value+unit, optional target/margin
inset, optional collapsible formula block. Every value passed in is already
final -- this widget formats and lays out, it does not compute.

BOX-IN-BOX BORDER SWEEP (this round)
────────────────────────────────────
KpiCard was a bare declaration:

    self.setStyleSheet(f"background-color: {PANEL2}; "
                       f"border: 1px solid {BORDER}; border-radius: 10px;")

No selector -> Qt reads it as `* { ... }` -> it applies to the card AND
EVERY DESCENDANT. A KpiCard contains the discipline tag, the status pill,
the label, the value, the unit, the target/margin inset and the formula
box, so all of them inherited `border: 1px solid` and each drew its own
box. With ~12 cards in the column, that's the whole Status panel rendering
as boxes inside boxes.

The `inset` frame did it again to its own target and margin labels.

Verified directly, not assumed: a QFrame with N child QLabels renders 2N
horizontal border runs inside itself under a bare declaration, and 0 under
a scoped one.

Note also (learned from status_design_leaves.py, and it applies here):
writing `QFrame { border: ... }` is NOT a safe alternative -- a QSS class
selector matches all SUBCLASSES, and QLabel IS a QFrame subclass
(QLabel -> QFrame -> QWidget). Only an objectName selector binds to one
widget. theme.scoped() generates exactly that.

COLORS -- HALF THIS FILE WAS STALE, WHICH IS WHY IT LOOKED WRONG
────────────────────────────────────────────────────────────────
STATUS_STYLE and DISC_STYLE were each half-v1, half-v2 IN THE SAME DICT:

    "ok": {"bg": "rgba(31,184,110,.10)",   <- v1 success (#1fb86e)
           "color": SUCCESS}                <- v2 success (#10b981), imported

So every PASS pill drew v2 green text on a v1 green tint inside a v1 green
border -- three different greens in one 60px pill. Same for warn (v1
#d98e00 vs v2 #f59e0b), fail (v1 #e05252 vs v2 #ef4444) and info (v1
#4a9eff vs v2 #3b82f6). All tints now come from the *_DIM / *_BORDER
tokens, so the pill's fill, border and text are guaranteed to be the same
hue.

The two that were already correct and are UNCHANGED: structural's
rgba(167,139,250,..) matches theme.PURPLE, and discharge's
rgba(20,184,166,..) matches theme.TEAL -- both were sampled from
KpiGrid.jsx's own DISC object, which uses literals rather than CSS vars.
Those are now expressed via the same _tint() helper for consistency, at
identical values.

ARCHITECTURE VIOLATION -- FLAGGED, NOT SILENTLY CHANGED
───────────────────────────────────────────────────────
    T_warn = T_total is not None and T_total > 50000
    T_fail = T_total is not None and T_total > 80000

These 50 kN / 80 kN headshaft-load thresholds are ENGINEERING CONSTANTS
living in the frontend. The project rule is that the frontend is pure I/O
-- no physics, no engineering constants -- precisely so a threshold here
can't silently drift from the backend's. Every other status on this panel
already reads a pre-computed boolean (cap_ok, speed_ok, cr_ok, l10_ok);
this one does not, and there is no `headshaft_ok` in results to read.

I have NOT invented a backend field or changed the numbers -- they are
preserved exactly. But this wants a `headshaft_load_ok` (and ideally a
`headshaft_load_limit_N`) computed in calculations.py and consumed here,
the same way cap_ok is. Same for "≥ 40,000 h continuous" in the L10 card's
target text and "Optimal: 1.0 – 1.8" in the CR card -- both are hardcoded
limits the backend already knows. Marked with THRESHOLD-IN-FRONTEND below.

ALSO
────
  * set_data()'s clear loop was not recursive -> shared clear_layout().
  * Hardcoded "'JetBrains Mono', monospace" -> theme.FF_MONO.
  * Three flush-left indentation breaks restored (hard SyntaxErrors as
    pasted: `cards = [`, `dict(`, `for c in cards:`).
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea, QPushButton,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from theme import (
    PANEL, PANEL2, SURFACE, BORDER, TEXT, TEXT2, TEXT3, MUTED,
    PRIMARY, PRIMARY_DIM, PRIMARY_RING,
    SUCCESS, SUCCESS_DIM, SUCCESS_BORDER,
    WARNING, WARNING_DIM, WARNING_BORDER,
    DANGER, DANGER_DIM, DANGER_BORDER,
    INFO_DIM, INFO_BORDER, PURPLE, TEAL,
    R_SM, R_MD, R_LG, R_PILL, FF_MONO,
    scoped, plain_bg,
)
from .dialog_helpers import clear_layout


def _tint(color_hex, alpha):
    """rgba() tint derived from a theme color -- so a pill's fill, border
    and text are always the same hue. Mixing a hardcoded tint with an
    imported text color is exactly what made every pill three-toned."""
    c = QColor(color_hex)
    return f"rgba({c.red()},{c.green()},{c.blue()},{alpha})"


# Mirrors KpiGrid.jsx's STATUS object -- now with all three parts of each
# entry (bg / border / color) derived from ONE theme token.
STATUS_STYLE = {
    "ok":   {"bg": SUCCESS_DIM, "border": SUCCESS_BORDER, "color": SUCCESS,
             "label": "PASS", "icon": "✓"},
    "warn": {"bg": WARNING_DIM, "border": WARNING_BORDER, "color": WARNING,
             "label": "WARN", "icon": "⚠"},
    "fail": {"bg": DANGER_DIM,  "border": DANGER_BORDER,  "color": DANGER,
             "label": "FAIL", "icon": "✗"},
    "info": {"bg": INFO_DIM,    "border": INFO_BORDER,    "color": PRIMARY,
             "label": "INFO", "icon": "·"},
}

# Mirrors KpiGrid.jsx's DISC object. purple/teal values are unchanged --
# they were sampled from the JSX's own literals and already match theme.
DISC_STYLE = {
    "process":    {"bg": _tint(PRIMARY, ".15"), "color": PRIMARY},
    "mechanical": {"bg": _tint(SUCCESS, ".15"), "color": SUCCESS},
    "power":      {"bg": _tint(WARNING, ".15"), "color": WARNING},
    "structural": {"bg": _tint(PURPLE,  ".15"), "color": PURPLE},
    "discharge":  {"bg": _tint(TEAL,    ".15"), "color": TEAL},
}


def fmt(v, digits=2):
    """Mirrors KpiGrid.jsx's fmt() exactly: dash for None/NaN, else
    fixed-point. Never invents a value the backend didn't provide."""
    if v is None:
        return "—"
    try:
        return f"{float(v):.{digits}f}"
    except (TypeError, ValueError):
        return "—"


class _StatusPill(QLabel):
    """Port of KpiGrid.jsx's <Pill status=.../>."""

    def __init__(self, status, parent=None):
        super().__init__(parent)
        s = STATUS_STYLE.get(status, STATUS_STYLE["info"])
        self.setText(f"{s['icon']} {s['label']}")
        self.setStyleSheet(scoped(
            self,
            f"background-color: {s['bg']}; color: {s['color']}; "
            f"border: 1px solid {s['border']}; border-radius: {R_PILL}px; "
            f"padding: 2px 8px; font-size: 12px; font-weight: 700; "
            f"letter-spacing: .06em;"
        ))


class _DiscTag(QLabel):
    """Port of KpiGrid.jsx's <Tag disc=.../>."""

    def __init__(self, disc, parent=None):
        super().__init__(parent)
        d = DISC_STYLE.get(disc, DISC_STYLE["process"])
        self.setText(disc.upper())
        self.setStyleSheet(scoped(
            self,
            f"background-color: {d['bg']}; color: {d['color']}; border: none; "
            f"border-radius: {R_PILL}px; padding: 1px 7px; font-size: 12px; "
            f"font-weight: 600; letter-spacing: .05em;"
        ))


class KpiCard(QFrame):
    """Port of KpiGrid.jsx's KpiCard.

    SCOPED: the bare declaration was cascading `border: 1px solid` onto the
    discipline tag, status pill, label, value, unit, inset and formula box
    -- seven phantom boxes per card, across a column of twelve cards.
    """

    def __init__(self, label, value, unit, status, disc, target=None,
                 margin=None, formula=None, parent=None):
        super().__init__(parent)
        s = STATUS_STYLE.get(status, STATUS_STYLE["info"])
        self.setStyleSheet(scoped(
            self,
            f"background-color: {PANEL2}; border: 1px solid {BORDER}; "
            f"border-radius: {R_LG}px;"
        ))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.addWidget(_DiscTag(disc))
        top_row.addStretch()
        top_row.addWidget(_StatusPill(status))
        outer.addLayout(top_row)

        label_lbl = QLabel(label.upper())
        label_lbl.setStyleSheet(
            f"color: {TEXT2}; font-size: 13px; font-weight: 600; "
            f"letter-spacing: .04em;")
        outer.addWidget(label_lbl)

        value_row = QHBoxLayout()
        value_row.setSpacing(6)
        value_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        value_lbl = QLabel(str(value))
        value_lbl.setStyleSheet(
            f"color: {s['color']}; font-size: 24px; font-weight: 700; "
            f"font-family: {FF_MONO};"
        )
        value_row.addWidget(value_lbl)
        if unit:
            unit_lbl = QLabel(unit)
            unit_lbl.setStyleSheet(
                f"color: {TEXT2}; font-size: 14px; font-family: {FF_MONO};")
            value_row.addWidget(unit_lbl, alignment=Qt.AlignmentFlag.AlignBottom)
        outer.addLayout(value_row)

        if target or margin is not None:
            # SCOPED: bare border here boxed the target and margin labels.
            inset = QFrame()
            inset.setStyleSheet(scoped(
                inset,
                f"background-color: rgba(255,255,255,.04); "
                f"border: 1px solid {BORDER}; border-radius: {R_SM}px;"
            ))
            inset_row = QHBoxLayout(inset)
            inset_row.setContentsMargins(10, 6, 10, 6)
            if target:
                target_lbl = QLabel(f"Target: {target}")
                target_lbl.setStyleSheet(f"color: {TEXT2}; font-size: 13px;")
                target_lbl.setWordWrap(True)
                inset_row.addWidget(target_lbl, 1)
            if margin is not None:
                margin_color = SUCCESS if margin >= 0 else DANGER
                sign = "+" if margin >= 0 else ""
                margin_lbl = QLabel(f"{sign}{fmt(margin, 1)}%")
                margin_lbl.setStyleSheet(
                    f"color: {margin_color}; font-size: 13px; font-weight: 700; "
                    f"font-family: {FF_MONO};"
                )
                inset_row.addWidget(margin_lbl)
            outer.addWidget(inset)

        if formula:
            self._formula_text = formula
            self._open = False
            self.toggle_btn = QPushButton("▶  SHOW FORMULA")
            self.toggle_btn.setStyleSheet(scoped(
                self.toggle_btn,
                f"background-color: transparent; color: {TEXT3}; border: none; "
                f"text-align: left; font-size: 13px; font-weight: 600; "
                f"letter-spacing: .03em; padding: 0;",
                extra="{sel}:hover { color: %s; }" % TEXT2,
            ))
            self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.toggle_btn.clicked.connect(self._toggle_formula)
            outer.addWidget(self.toggle_btn)

            self.formula_box = QLabel(formula)
            self.formula_box.setStyleSheet(scoped(
                self.formula_box,
                f"background-color: {PANEL}; border: 1px solid {BORDER}; "
                f"border-radius: {R_SM}px; color: {TEXT2}; font-size: 13px; "
                f"font-family: {FF_MONO}; padding: 10px 12px;"
            ))
            self.formula_box.setWordWrap(True)
            self.formula_box.hide()
            outer.addWidget(self.formula_box)

    def _toggle_formula(self):
        self._open = not self._open
        self.formula_box.setVisible(self._open)
        self.toggle_btn.setText(
            "▼  HIDE FORMULA" if self._open else "▶  SHOW FORMULA")


class StatusPanel(QWidget):
    """Port of KpiGrid.jsx's default export. set_data(inputs, results) like
    every other component; rebuilds the full card list each time."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(plain_bg(self, PANEL))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(scoped(scroll, "border: none; background: transparent;"))
        self.list_widget = QWidget()
        self.list_widget.setStyleSheet(plain_bg(self.list_widget, PANEL))
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setContentsMargins(12, 12, 12, 12)
        self.list_layout.setSpacing(10)
        self.list_layout.addStretch()
        scroll.setWidget(self.list_widget)
        outer.addWidget(scroll)

    def set_data(self, inputs, results):
        inputs = inputs or {}
        results = results or {}
        clear_layout(self.list_layout)

        # Mirrors KpiGrid.jsx: `if (!results || !results.bucket) return null;`
        if not results.get("bucket"):
            empty = QLabel("Run a calculation to see KPIs.")
            empty.setStyleSheet(
                f"color: {TEXT2}; font-size: 13px; font-style: italic;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.list_layout.addWidget(empty)
            self.list_layout.addStretch()
            return

        r = results
        bkt = r.get("bucket") or {}
        mat = r.get("mat") or {}

        # Pre-computed booleans from the backend -- the frontend does not
        # re-derive any of these. This is the correct pattern.
        cap_ok = r.get("cap_ok", False)
        speed_ok = r.get("speed_ok", False)
        cr_ok = r.get("cr_ok", False)
        l10_ok = r.get("l10_ok", False)
        cap_margin = r.get("cap_margin_pct")
        motor_margin = r.get("motor_margin_pct")

        T_total = r.get("T_total")
        T_total_kN = T_total / 1000 if T_total is not None else None
        L10 = r.get("L10")

        # THRESHOLD-IN-FRONTEND (see module docstring). These 50/80 kN limits
        # are engineering constants that belong in calculations.py, exposed as
        # a `headshaft_load_ok` boolean like cap_ok/speed_ok/cr_ok/l10_ok. Every
        # other card on this panel reads a backend verdict; this one computes
        # its own, which is exactly how a frontend limit silently drifts from
        # the backend's. Values preserved unchanged -- flagged, not "fixed" by
        # inventing a field that doesn't exist yet.
        T_warn = T_total is not None and T_total > 50000
        T_fail = T_total is not None and T_total > 80000

        cards = [
            dict(
                label="Design Capacity", value=fmt(r.get("Q"), 1), unit="t/h",
                disc="process", status="ok" if cap_ok else "fail",
                target=f"{inputs.get('Q_req')} t/h required", margin=cap_margin,
                formula=(
                    f"Q = (v / s) · Vb · η · ρ · 3.6\n"
                    f"v  = {fmt(r.get('v'), 3)} m/s   (belt speed)\n"
                    f"s  = {fmt(r.get('spacing'), 4)} m    (bucket spacing)\n"
                    f"Vb = {bkt.get('V')} L = "
                    f"{fmt((bkt.get('V') or 0) / 1000, 4)} m³\n"
                    f"η  = {fmt((inputs.get('fill_pct') or 0) / 100, 2)}   "
                    f"(fill factor {inputs.get('fill_pct')}%)\n"
                    f"ρ  = {r.get('rho')} kg/m³\n"
                    f"→  Q = {fmt(r.get('Q'), 2)} t/h  [CEMA 375 §4]"
                ),
            ),
            dict(
                label="Belt Speed", value=fmt(r.get("v"), 3), unit="m/s",
                disc="mechanical", status="ok" if speed_ok else "warn",
                target=f"{bkt.get('v_min')}–{bkt.get('v_max')} m/s "
                       f"({bkt.get('id')})",
                margin=None,
                formula=(
                    f"v = π · D · n / 60\n"
                    f"D  = {inputs.get('D_mm')} mm\n"
                    f"n  = {inputs.get('n_rpm')} rpm\n"
                    f"→  v = {fmt(r.get('v'), 4)} m/s  [CEMA 375 §3]"
                ),
            ),
            dict(
                label="Total Drive Power", value=fmt(r.get("P_total"), 2),
                unit="kW", disc="power", status="info",
                target=f"Lift {fmt(r.get('P_lift'), 2)} + "
                       f"Dig {fmt(r.get('P_digging'), 2)} kW",
                margin=None,
                formula=(
                    f"P = (P_lift + P_digging) × Ceff\n"
                    f"P_lift    = {fmt(r.get('P_lift'), 3)} kW\n"
                    f"P_digging = {fmt(r.get('P_digging'), 3)} kW  "
                    f"(Leq={r.get('Leq')})\n"
                    f"Ceff      = {r.get('Ceff')}\n"
                    f"→  P_total = {fmt(r.get('P_total'), 3)} kW  "
                    f"[CEMA 375 §4 LEQ]"
                ),
            ),
            dict(
                label="Motor Selected",
                value=fmt(r.get("motor_kw"), 0)
                      if r.get("motor_kw") is not None else "—",
                unit="kW", disc="power", status="ok",
                target=f"SF {inputs.get('sf')} · design "
                       f"{fmt((r.get('P_total') or 0) * (inputs.get('sf') or 0), 2)} kW",
                margin=motor_margin,
                formula=(
                    f"Motor = next std size ≥ P_total × SF\n"
                    f"P_total  = {fmt(r.get('P_total'), 3)} kW\n"
                    f"SF       = {inputs.get('sf')}\n"
                    f"Design   = "
                    f"{fmt((r.get('P_total') or 0) * (inputs.get('sf') or 0), 3)} kW\n"
                    f"Selected : {r.get('motor_kw')} kW  [IEC/NEMA std sizes]"
                ),
            ),
            dict(
                label="Headshaft Load",
                value=fmt(T_total_kN, 2) if T_total_kN is not None else "—",
                unit="kN", disc="structural",
                # THRESHOLD-IN-FRONTEND -- see above.
                status="fail" if T_fail else ("warn" if T_warn else "ok"),
                target="T1+T2+T3  ≤ 80 kN", margin=None,
                formula=(
                    f"R = T1 + T2 + T3\n"
                    f"T1 = {fmt((r.get('T1') or 0) / 1000, 2)} kN  "
                    f"(material weight)\n"
                    f"T2 = {fmt((r.get('T2') or 0) / 1000, 2)} kN  "
                    f"(belt+bucket self-weight)\n"
                    f"T3 = {fmt((r.get('T3') or 0) / 1000, 2)} kN  "
                    f"(slack side, K={inputs.get('K_takeup')})\n"
                    f"→  R = "
                    f"{fmt(T_total_kN, 2) if T_total_kN is not None else '—'} kN  "
                    f"[CEMA 375 §4.07–4.09]"
                ),
            ),
            dict(
                label="Head Shaft Dia.", value=fmt(r.get("d_mm"), 0), unit="mm",
                disc="structural", status="info",
                target=f"Governed by {r.get('governed_by', 'stress')}", margin=None,
                formula=(
                    f"Stress check (ASME DE-Goodman):\n"
                    f"  d_stress   = {fmt(r.get('d_stress_mm'), 1)} mm\n"
                    f"Deflection check (CEMA 0.0015 in/in):\n"
                    f"  d_deflect  = {fmt(r.get('d_deflect_mm'), 1)} mm\n"
                    f"Governing    = {fmt(r.get('d_mm'), 1)} mm\n"
                    f"T_shaft      = {fmt((r.get('T_Nm') or 0) / 1000, 3)} kNm  "
                    f"[CEMA 375 §4]"
                ),
            ),
            dict(
                label="Belt Width", value=str(r.get("belt_w", "—")), unit="mm",
                disc="mechanical", status="info",
                target=f"Bucket {bkt.get('W')}mm + clearance", margin=None,
                formula=(
                    f"Belt width = next std ≥ bucket_W + clearance\n"
                    f"Bucket W  = {bkt.get('W')} mm\n"
                    f"Selected  = {r.get('belt_w')} mm  [CEMA std widths]"
                ),
            ),
            dict(
                label="Centrifugal Ratio", value=fmt(r.get("cr"), 3), unit="—",
                disc="discharge", status="ok" if cr_ok else "warn",
                # THRESHOLD-IN-FRONTEND: the 1.0-1.8 band is display text only
                # (cr_ok is the real verdict, from the backend) -- but the band
                # is still a hardcoded copy of a backend constant.
                target="Optimal: 1.0 – 1.8", margin=None,
                formula=(
                    f"CR = v² / (r · g)\n"
                    f"v  = {fmt(r.get('v'), 4)} m/s\n"
                    f"r  = head pulley radius\n"
                    f"g  = gravitational acceleration\n"
                    f"→  CR = {fmt(r.get('cr'), 4)}\n"
                    f"Release angle θ = {fmt(r.get('theta_rel'), 1)}° from "
                    f"vertical  [CEMA 375 §3]"
                ),
            ),
            dict(
                label="Bearing L10 Life",
                value=(f"{(L10 / 1000):.0f}k"
                       if L10 is not None and L10 > 9999 else fmt(L10, 0)),
                unit="h", disc="mechanical",
                status="ok" if l10_ok else ("warn" if (L10 or 0) >= 20000 else "fail"),
                # THRESHOLD-IN-FRONTEND: 40,000h display text + the 20,000h
                # floor in the status expression above. The 20,000h floor is a
                # real optimizer constraint in the backend -- it should be read
                # from there, not restated here.
                target="≥ 40,000 h continuous", margin=None,
                formula=(
                    f"L10 = (C / P)³ × 10⁶ / (60 × n)\n"
                    f"C   = rated dynamic capacity (from bearing selection)\n"
                    f"P   = {fmt(r.get('R_headshaft'), 0)} N  (radial load)\n"
                    f"n   = {inputs.get('n_rpm')} rpm\n"
                    f"→  L10 = {fmt(L10, 0)} h  [ISO 281]"
                ),
            ),
            dict(
                label="Bucket Series", value=str(bkt.get("id", "—")), unit="",
                disc="process", status="info",
                target=f"{bkt.get('V')}L  ·  {bkt.get('W')}×{bkt.get('H')}mm",
                margin=None,
                formula=(
                    f"Active volume = V × η\n"
                    f"V   = {bkt.get('V')} L  (struck capacity)\n"
                    f"η   = {fmt((inputs.get('fill_pct') or 0) / 100, 2)}  "
                    f"(fill factor)\n"
                    f"Spacing  = {fmt((r.get('spacing') or 0) * 1000, 0)} mm  "
                    f"[CEMA 375 §4]"
                ),
            ),
            dict(
                label="Material", value=str(r.get("rho", "—")), unit="kg/m³",
                disc="process", status="info",
                target=mat.get("name", ""), margin=None,
                formula=(
                    f"CEMA 550 code : {mat.get('cema_code', '—')}\n"
                    f"ρ_loose      = {mat.get('rho_loose')} kg/m³\n"
                    f"ρ_vibrated   = {mat.get('rho_vib')} kg/m³\n"
                    f"Abrasive     = {mat.get('abr_code')}/7\n"
                    f"Flowability  = {mat.get('flowability')}/4\n"
                    f"Km factor    = {mat.get('Km')}  [ANSI/CEMA 550-2020]"
                ),
            ),
            dict(
                label="Fill Factor", value=str(inputs.get("fill_pct", "—")),
                unit="%", disc="process",
                # THRESHOLD-IN-FRONTEND: the 80% advisory limit again.
                status="warn" if (inputs.get("fill_pct") or 0) >= 80 else "ok",
                target="CEMA advisory ≤ 80%", margin=None,
                formula=(
                    f"η = fill_pct / 100 = "
                    f"{fmt((inputs.get('fill_pct') or 0) / 100, 2)}\n"
                    f"CEMA 375 §4: fill > 80% increases spillage risk at boot"
                ),
            ),
        ]

        for c in cards:
            self.list_layout.addWidget(KpiCard(**c))
        self.list_layout.addStretch()