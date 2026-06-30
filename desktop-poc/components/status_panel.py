"""
components/status_panel.py -- engineering KPI cards for the Status column.
═══════════════════════════════════════════════════════════════════════════
Faithful port of frontend/src/components/KpiGrid.jsx, read directly before
writing this (not assumed) -- every card's label/value/unit/target/margin/
formula matches the real JSX source exactly, field for field.

Per direct instruction: DesignReview.jsx is deliberately NOT ported here --
this column shows only the KpiGrid card list, full (non-compact) layout,
stacked vertically since the Status column is ~260px wide (narrower than
the JSX's 220px-min grid-auto-fill, so a single column is the natural
result anyway, not a simplification).

Architecture note matching the JSX's own v1.9.9 comment ("removed all
frontend physics computation... formula strings now display backend
values rather than recomputing them"): every formula string below is
built entirely from values already in `results`/`inputs` -- no g=9.81,
no belt-clearance arithmetic, no margin computation happens in this file.
If a number isn't already in the backend response, it doesn't appear here.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea, QPushButton,
)
from PySide6.QtCore import Qt

from theme import (
    PANEL, PANEL2, BORDER, TEXT, TEXT2, TEXT3, MUTED,
    PRIMARY, SUCCESS, WARNING, DANGER, PURPLE, TEAL,
)

# Mirrors KpiGrid.jsx's STATUS object exactly.
STATUS_STYLE = {
    "ok":   {"bg": "rgba(31,184,110,.10)",  "border": "rgba(31,184,110,.3)",  "color": SUCCESS, "label": "PASS", "icon": "✓"},
    "warn": {"bg": "rgba(217,142,0,.10)",   "border": "rgba(217,142,0,.3)",   "color": WARNING, "label": "WARN", "icon": "⚠"},
    "fail": {"bg": "rgba(224,82,82,.10)",   "border": "rgba(224,82,82,.3)",   "color": DANGER,  "label": "FAIL", "icon": "✗"},
    "info": {"bg": "rgba(74,158,255,.08)",  "border": "rgba(74,158,255,.2)",  "color": PRIMARY, "label": "INFO", "icon": "·"},
}

# Mirrors KpiGrid.jsx's DISC object exactly.
DISC_STYLE = {
    "process":    {"bg": "rgba(74,158,255,.15)",  "color": PRIMARY},
    "mechanical": {"bg": "rgba(31,184,110,.15)",   "color": SUCCESS},
    "power":      {"bg": "rgba(217,142,0,.15)",    "color": WARNING},
    "structural": {"bg": "rgba(167,139,250,.15)",  "color": PURPLE},
    "discharge":  {"bg": "rgba(20,184,166,.15)",   "color": TEAL},
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
    """Port of KpiGrid.jsx's <Pill status=.../> -- icon + label, colored
    by status, in its own small pill."""

    def __init__(self, status, parent=None):
        super().__init__(parent)
        s = STATUS_STYLE.get(status, STATUS_STYLE["info"])
        self.setText(f"{s['icon']} {s['label']}")
        self.setStyleSheet(
            f"background-color: {s['bg']}; color: {s['color']}; "
            f"border: 1px solid {s['border']}; border-radius: 999px; "
            f"padding: 2px 8px; font-size: 9px; font-weight: 700; letter-spacing: .06em;"
        )


class _DiscTag(QLabel):
    """Port of KpiGrid.jsx's <Tag disc=.../> -- the category badge
    (PROCESS/MECHANICAL/POWER/STRUCTURAL/DISCHARGE)."""

    def __init__(self, disc, parent=None):
        super().__init__(parent)
        d = DISC_STYLE.get(disc, DISC_STYLE["process"])
        self.setText(disc.upper())
        self.setStyleSheet(
            f"background-color: {d['bg']}; color: {d['color']}; "
            f"border-radius: 999px; padding: 1px 7px; font-size: 9px; "
            f"font-weight: 600; letter-spacing: .05em;"
        )


class KpiCard(QFrame):
    """Port of KpiGrid.jsx's KpiCard -- category tag + status pill row,
    label, big value+unit, an optional target/margin inset row, and an
    optional collapsible formula block. Every value passed in is already
    final -- this widget formats and lays out, it doesn't compute."""

    def __init__(self, label, value, unit, status, disc, target=None, margin=None, formula=None, parent=None):
        super().__init__(parent)
        s = STATUS_STYLE.get(status, STATUS_STYLE["info"])
        self.setStyleSheet(f"background-color: {PANEL2}; border: 1px solid {BORDER}; border-radius: 10px;")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.addWidget(_DiscTag(disc))
        top_row.addStretch()
        top_row.addWidget(_StatusPill(status))
        outer.addLayout(top_row)

        label_lbl = QLabel(label.upper())
        label_lbl.setStyleSheet(f"color: {TEXT2}; font-size: 10px; font-weight: 600; letter-spacing: .04em;")
        outer.addWidget(label_lbl)

        value_row = QHBoxLayout()
        value_row.setSpacing(6)
        value_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        value_lbl = QLabel(str(value))
        value_lbl.setStyleSheet(
            f"color: {s['color']}; font-size: 23px; font-weight: 700; "
            f"font-family: 'JetBrains Mono', monospace;"
        )
        value_row.addWidget(value_lbl)
        if unit:
            unit_lbl = QLabel(unit)
            unit_lbl.setStyleSheet(f"color: {TEXT2}; font-size: 12px; font-family: 'JetBrains Mono', monospace;")
            value_row.addWidget(unit_lbl, alignment=Qt.AlignmentFlag.AlignBottom)
        outer.addLayout(value_row)

        if target or margin is not None:
            inset = QFrame()
            inset.setStyleSheet(f"background-color: rgba(255,255,255,.04); border: 1px solid {BORDER}; border-radius: 6px;")
            inset_row = QHBoxLayout(inset)
            inset_row.setContentsMargins(10, 6, 10, 6)
            if target:
                target_lbl = QLabel(f"Target: {target}")
                target_lbl.setStyleSheet(f"color: {TEXT2}; font-size: 10.5px;")
                target_lbl.setWordWrap(True)
                inset_row.addWidget(target_lbl, 1)
            if margin is not None:
                margin_color = SUCCESS if margin >= 0 else DANGER
                sign = "+" if margin >= 0 else ""
                margin_lbl = QLabel(f"{sign}{fmt(margin, 1)}%")
                margin_lbl.setStyleSheet(
                    f"color: {margin_color}; font-size: 10.5px; font-weight: 700; "
                    f"font-family: 'JetBrains Mono', monospace;"
                )
                inset_row.addWidget(margin_lbl)
            outer.addWidget(inset)

        if formula:
            self._formula_text = formula
            self._open = False
            self.toggle_btn = QPushButton("▶  SHOW FORMULA")
            self.toggle_btn.setStyleSheet(
                f"background-color: transparent; color: {TEXT3}; border: none; "
                f"text-align: left; font-size: 10px; font-weight: 600; letter-spacing: .03em; padding: 0;"
            )
            self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.toggle_btn.clicked.connect(self._toggle_formula)
            outer.addWidget(self.toggle_btn)

            self.formula_box = QLabel(formula)
            self.formula_box.setStyleSheet(
                f"background-color: {PANEL}; border: 1px solid {BORDER}; border-radius: 6px; "
                f"color: {TEXT2}; font-size: 10.5px; font-family: 'JetBrains Mono', monospace; "
                f"padding: 10px 12px;"
            )
            self.formula_box.setWordWrap(True)
            self.formula_box.hide()
            outer.addWidget(self.formula_box)

    def _toggle_formula(self):
        self._open = not self._open
        self.formula_box.setVisible(self._open)
        self.toggle_btn.setText("▼  HIDE FORMULA" if self._open else "▶  SHOW FORMULA")


class StatusPanel(QWidget):
    """Port of KpiGrid.jsx's default export. set_data(inputs, results)
    like every other component in this app; rebuilds the full card list
    each time, same pattern as InputSidebarPanel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {PANEL};")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        self.list_widget = QWidget()
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setContentsMargins(12, 12, 12, 12)
        self.list_layout.setSpacing(10)
        self.list_layout.addStretch()
        scroll.setWidget(self.list_widget)
        outer.addWidget(scroll)

    def set_data(self, inputs, results):
        inputs = inputs or {}
        results = results or {}
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            w = item.widget() if item else None
            if w:
                w.setParent(None)
                w.deleteLater()

        # Mirrors KpiGrid.jsx: `if (!results || !results.bucket) return null;`
        if not results.get("bucket"):
            empty = QLabel("Run a calculation to see KPIs.")
            empty.setStyleSheet(f"color: {TEXT2}; font-size: 11px; font-style: italic;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.list_layout.addWidget(empty)
            self.list_layout.addStretch()
            return

        r = results
        bkt = r.get("bucket") or {}
        mat = r.get("mat") or {}

        cap_ok = r.get("cap_ok", False)
        speed_ok = r.get("speed_ok", False)
        cr_ok = r.get("cr_ok", False)
        l10_ok = r.get("l10_ok", False)
        cap_margin = r.get("cap_margin_pct")
        motor_margin = r.get("motor_margin_pct")
        T_total = r.get("T_total")
        T_total_kN = T_total / 1000 if T_total is not None else None
        T_warn = T_total is not None and T_total > 50000
        T_fail = T_total is not None and T_total > 80000
        L10 = r.get("L10")

        cards = [
            dict(
                label="Design Capacity", value=fmt(r.get("Q"), 1), unit="t/h",
                disc="process", status="ok" if cap_ok else "fail",
                target=f"{inputs.get('Q_req')} t/h required", margin=cap_margin,
                formula=(
                    f"Q = (v / s) · Vb · η · ρ · 3.6\n"
                    f"v  = {fmt(r.get('v'), 3)} m/s   (belt speed)\n"
                    f"s  = {fmt(r.get('spacing'), 4)} m    (bucket spacing)\n"
                    f"Vb = {bkt.get('V')} L = {fmt((bkt.get('V') or 0) / 1000, 4)} m³\n"
                    f"η  = {fmt((inputs.get('fill_pct') or 0) / 100, 2)}   (fill factor {inputs.get('fill_pct')}%)\n"
                    f"ρ  = {r.get('rho')} kg/m³\n"
                    f"→  Q = {fmt(r.get('Q'), 2)} t/h  [CEMA 375 §4]"
                ),
            ),
            dict(
                label="Belt Speed", value=fmt(r.get("v"), 3), unit="m/s",
                disc="mechanical", status="ok" if speed_ok else "warn",
                target=f"{bkt.get('v_min')}–{bkt.get('v_max')} m/s ({bkt.get('id')})", margin=None,
                formula=(
                    f"v = π · D · n / 60\n"
                    f"D  = {inputs.get('D_mm')} mm\n"
                    f"n  = {inputs.get('n_rpm')} rpm\n"
                    f"→  v = {fmt(r.get('v'), 4)} m/s  [CEMA 375 §3]"
                ),
            ),
            dict(
                label="Total Drive Power", value=fmt(r.get("P_total"), 2), unit="kW",
                disc="power", status="info",
                target=f"Lift {fmt(r.get('P_lift'), 2)} + Dig {fmt(r.get('P_digging'), 2)} kW", margin=None,
                formula=(
                    f"P = (P_lift + P_digging) × Ceff\n"
                    f"P_lift    = {fmt(r.get('P_lift'), 3)} kW\n"
                    f"P_digging = {fmt(r.get('P_digging'), 3)} kW  (Leq={r.get('Leq')})\n"
                    f"Ceff      = {r.get('Ceff')}\n"
                    f"→  P_total = {fmt(r.get('P_total'), 3)} kW  [CEMA 375 §4 LEQ]"
                ),
            ),
            dict(
                label="Motor Selected", value=fmt(r.get("motor_kw"), 0) if r.get("motor_kw") is not None else "—",
                unit="kW", disc="power", status="ok",
                target=f"SF {inputs.get('sf')} · design {fmt((r.get('P_total') or 0) * (inputs.get('sf') or 0), 2)} kW",
                margin=motor_margin,
                formula=(
                    f"Motor = next std size ≥ P_total × SF\n"
                    f"P_total  = {fmt(r.get('P_total'), 3)} kW\n"
                    f"SF       = {inputs.get('sf')}\n"
                    f"Design   = {fmt((r.get('P_total') or 0) * (inputs.get('sf') or 0), 3)} kW\n"
                    f"Selected : {r.get('motor_kw')} kW  [IEC/NEMA std sizes]"
                ),
            ),
            dict(
                label="Headshaft Load",
                value=fmt(T_total_kN, 2) if T_total_kN is not None else "—", unit="kN",
                disc="structural", status="fail" if T_fail else ("warn" if T_warn else "ok"),
                target="T1+T2+T3  ≤ 80 kN", margin=None,
                formula=(
                    f"R = T1 + T2 + T3\n"
                    f"T1 = {fmt((r.get('T1') or 0) / 1000, 2)} kN  (material weight)\n"
                    f"T2 = {fmt((r.get('T2') or 0) / 1000, 2)} kN  (belt+bucket self-weight)\n"
                    f"T3 = {fmt((r.get('T3') or 0) / 1000, 2)} kN  (slack side, K={inputs.get('K_takeup')})\n"
                    f"→  R = {fmt(T_total_kN, 2) if T_total_kN is not None else '—'} kN  [CEMA 375 §4.07–4.09]"
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
                    f"T_shaft      = {fmt((r.get('T_Nm') or 0) / 1000, 3)} kNm  [CEMA 375 §4]"
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
                target="Optimal: 1.0 – 1.8", margin=None,
                formula=(
                    f"CR = v² / (r · g)\n"
                    f"v  = {fmt(r.get('v'), 4)} m/s\n"
                    f"r  = head pulley radius\n"
                    f"g  = gravitational acceleration\n"
                    f"→  CR = {fmt(r.get('cr'), 4)}\n"
                    f"Release angle θ = {fmt(r.get('theta_rel'), 1)}° from vertical  [CEMA 375 §3]"
                ),
            ),
            dict(
                label="Bearing L10 Life",
                value=(f"{(L10 / 1000):.0f}k" if L10 is not None and L10 > 9999 else fmt(L10, 0)),
                unit="h", disc="mechanical",
                status="ok" if l10_ok else ("warn" if (L10 or 0) >= 20000 else "fail"),
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
                target=f"{bkt.get('V')}L  ·  {bkt.get('W')}×{bkt.get('H')}mm", margin=None,
                formula=(
                    f"Active volume = V × η\n"
                    f"V   = {bkt.get('V')} L  (struck capacity)\n"
                    f"η   = {fmt((inputs.get('fill_pct') or 0) / 100, 2)}  (fill factor)\n"
                    f"Spacing  = {fmt((r.get('spacing') or 0) * 1000, 0)} mm  [CEMA 375 §4]"
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
                label="Fill Factor", value=str(inputs.get("fill_pct", "—")), unit="%",
                disc="process", status="warn" if (inputs.get("fill_pct") or 0) >= 80 else "ok",
                target="CEMA advisory ≤ 80%", margin=None,
                formula=(
                    f"η = fill_pct / 100 = {fmt((inputs.get('fill_pct') or 0) / 100, 2)}\n"
                    f"CEMA 375 §4: fill > 80% increases spillage risk at boot"
                ),
            ),
        ]

        for c in cards:
            self.list_layout.addWidget(KpiCard(**c))
        self.list_layout.addStretch()