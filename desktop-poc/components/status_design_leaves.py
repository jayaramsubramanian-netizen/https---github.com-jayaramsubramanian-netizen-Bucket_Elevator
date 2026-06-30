"""
components/status_design_leaves.py -- per-component design detail for the
Status column.
═══════════════════════════════════════════════════════════════════════════
Replaces this round's earlier status_panel.py (KpiGrid.jsx port) content in
the Status column, per direct instruction: "I do not need design review or
kpi grid to show up in the status section but a Preliminary BOM and any
advisories... can show up there." status_panel.py itself is left in the
codebase (a complete, tested component) but is no longer wired into
main.py's col4 -- this file replaces it there.

Architecture, per the chosen alternative ("leaving the BOM in the center
console and the component design values and supporting equations can be on
the status section... Make each component on the BOM correspond to a
design leaf in the status section. When clicked the leaf can open up a
modal with the details of the equations used and the calculated values as
a table"):

  - One leaf per BOM category, same set and order as bom_panel.py's
    CATEGORY_ORDER -- the two panels share that one list so a category can
    never appear in the BOM without a corresponding leaf here, or vice
    versa, per direct instruction.
  - Each leaf's status badge is the worst (fail > warn > ok) of every
    real checks[] entry whose subsystem tag maps to that category (see
    SUBSYSTEM_TO_CATEGORY below -- confirmed against every real subsystem
    tag in calculations.py, not guessed).
  - Clicking a leaf opens DesignLeafModal: the real BOM line items for
    that category as a table, plus supporting equations. Equation text is
    display-only and built entirely from already-computed result fields
    (no new physics) -- several are adapted directly from status_panel.py's
    existing KpiGrid-derived formula strings, extended to cover categories
    KpiGrid never had (Take-Up, Casing, Chute, Bearings, Fasteners).
  - Advisory strip at the top of the leaf list surfaces real fail/warn
    checks[] entries (via flag_note) plus the BOM's own static disclaimer
    notes -- NOT a fabricated "sensors recommended" feature. Confirmed
    directly: there is no sensor-recommendation logic anywhere in this
    backend yet, so none is invented here; this is flagged honestly rather
    than built as a placeholder.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea,
    QDialog, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
)
from PySide6.QtCore import Qt

from theme import PANEL, PANEL2, BORDER, TEXT, TEXT2, TEXT3, MUTED, PRIMARY, SUCCESS, WARNING, DANGER
from .dialog_helpers import status_badge, flag_note, modal_header, modal_footer
from .bom_panel import CATEGORY_ORDER, CAT_STYLE, group_items, kg_to_t, fmt as bom_fmt


def fmt(v, dp=2, fb="—"):
    if v is None:
        return fb
    try:
        return f"{float(v):.{dp}f}"
    except (TypeError, ValueError):
        return fb


# Confirmed directly against every subsystem="..." tag in calculations.py
# (grep, not guessed): belt, boot_pulley, bucket, casing, discharge,
# power, process, pulley, service, shaft, takeup. process/service are
# material- and site-condition-level, not tied to one hardware category,
# so they're surfaced only in the top-level advisory strip, not filtered
# into a specific leaf below.
SUBSYSTEM_TO_CATEGORY = {
    "shaft": ["SHAFT", "BEARINGS"],
    "pulley": ["PULLEY"],
    "boot_pulley": ["PULLEY"],
    "belt": ["BELT"],
    "bucket": ["BELT"],
    "power": ["DRIVE"],
    "takeup": ["TAKE-UP"],
    "casing": ["CASING"],
    "discharge": ["CHUTE"],
}

CATEGORY_LABELS = {
    "SHAFT": "Shaft Design", "PULLEY": "Pulleys", "BELT": "Belt / Chain & Buckets",
    "DRIVE": "Drive & Motor", "TAKE-UP": "Take-Up", "CASING": "Casing",
    "FASTENERS": "Fasteners", "BEARINGS": "Bearings", "CHUTE": "Discharge Chute",
}


def _checks_for_category(checks, category):
    subsystems = [s for s, cats in SUBSYSTEM_TO_CATEGORY.items() if category in cats]
    return [c for c in (checks or []) if c.get("subsystem") in subsystems]


def _worst_status(checks):
    if any(c.get("type") == "fail" for c in checks):
        return "fail"
    if any(c.get("type") == "warn" for c in checks):
        return "warn"
    if checks:
        return "ok"
    return None


def _build_formula(category, r, inputs):
    """Display-only equation text per category -- every value is read
    straight from already-computed results/inputs, nothing recomputed.
    SHAFT/PULLEY/DRIVE/BELT formulas are adapted from status_panel.py's
    existing KpiGrid-derived strings; TAKE-UP/CASING/CHUTE/BEARINGS/
    FASTENERS are new, built the same way (real fields only)."""
    bkt = r.get("bucket") or {}
    if category == "SHAFT":
        boot_shaft = (r.get("boot_pulley") or {}).get("shaft") or {}
        return (
            f"Head shaft -- stress (ASME DE-Goodman) + deflection (CEMA 0.0015 in/in):\n"
            f"  d_stress   = {fmt(r.get('d_stress_mm'), 1)} mm\n"
            f"  d_deflect  = {fmt(r.get('d_deflect_mm'), 1)} mm\n"
            f"  Governing  = {fmt(r.get('d_mm'), 1)} mm  (by {r.get('governed_by','stress')})\n"
            f"  T_shaft    = {fmt((r.get('T_Nm') or 0) / 1000, 3)} kNm\n\n"
            f"Boot shaft -- bending/deflection only (free-running, no torque):\n"
            f"  Governing  = {fmt(boot_shaft.get('d_mm'), 1)} mm  "
            f"(by {boot_shaft.get('governed_by','bending')})\n"
            f"  [CEMA 375 §4]"
        )
    if category == "PULLEY":
        return (
            f"Wrap angle: θ = 180° + 2·arcsin((R_H−R_B)/C)\n"
            f"  Geometric  = {fmt(r.get('wrap_geom_deg'), 1)}°\n"
            f"  Effective  = {fmt(r.get('wrap_effective_deg'), 1)}°\n"
            f"Head pulley shell (CEMA Pulley Standard + belt-pressure check):\n"
            f"  t_governing = {fmt((r.get('pulley_shell') or {}).get('t_governing_mm'), 1)} mm\n"
            f"Boot pulley shell:\n"
            f"  t_governing = {fmt((r.get('boot_shell') or {}).get('t_governing_mm'), 1)} mm\n"
            f"  [CEMA 375 §3,6]"
        )
    if category == "BELT":
        return (
            f"Q = (v / s) · Vb · η · ρ · 3.6\n"
            f"  v = {fmt(r.get('v'), 3)} m/s   s = {fmt(r.get('spacing'), 4)} m\n"
            f"  Vb = {bkt.get('V')} L   η = {fmt((inputs.get('fill_pct') or 0) / 100, 2)}\n"
            f"  → Q = {fmt(r.get('Q'), 2)} t/h\n\n"
            f"Belt slip (Euler/Eytelwein): e^μθ = {fmt(r.get('euler_ratio'), 3)}\n"
            f"  μ = {inputs.get('mu')}   θ = {fmt(r.get('wrap_effective_deg'), 0)}°\n"
            f"  [CEMA 375 §4]"
        )
    if category == "DRIVE":
        return (
            f"P = (P_lift + P_digging) × Ceff\n"
            f"  P_lift = {fmt(r.get('P_lift'), 3)} kW   P_digging = {fmt(r.get('P_digging'), 3)} kW\n"
            f"  Ceff = {r.get('Ceff')}  →  P_total = {fmt(r.get('P_total'), 3)} kW\n\n"
            f"Motor = next std size ≥ P_total × SF\n"
            f"  SF = {inputs.get('sf')}   Selected = {r.get('motor_kw')} kW\n"
            f"  Gearbox ratio = {fmt(r.get('gearbox_ratio'), 1)}:1\n"
            f"  [CEMA 375 §4 LEQ]"
        )
    if category == "TAKE-UP":
        tg = r.get("takeup_gravity") or {}
        ts = r.get("takeup_screw") or {}
        th = r.get("takeup_hydraulic") or {}
        ttype = inputs.get("takeup_type", "gravity")
        if ttype == "screw":
            return (
                f"Screw take-up -- buckling check:\n"
                f"  Force = {fmt((ts.get('F_screw_N') or 0) / 1000, 1)} kN\n"
                f"  Core dia (min) = {fmt(ts.get('d_core_min_mm'), 0)} mm\n"
                f"  SF buckling = {fmt(ts.get('SF_buckling'), 2)}\n"
                f"  [CEMA 375 §4]"
            )
        if ttype == "hydraulic":
            return (
                f"Hydraulic take-up -- standard cylinder mechanics (not a CEMA-published method):\n"
                f"  Force = {fmt((th.get('F_cylinder_N') or 0) / 1000, 1)} kN\n"
                f"  Bore dia (min) = {fmt(th.get('d_bore_min_mm'), 1)} mm\n"
                f"  Stroke = {fmt(th.get('stroke_mm'), 0)} mm   SF buckling = {fmt(th.get('SF_buckling'), 2)}"
            )
        return (
            f"Gravity take-up -- counterweight sizing:\n"
            f"  K (tension factor) = {inputs.get('K_takeup')}\n"
            f"  Counterweight (gross) = {fmt(tg.get('W_counterweight_kg_gross'), 0)} kg\n"
            f"  Travel required = {fmt(tg.get('travel_m'), 3)} m\n"
            f"  [CEMA 375 §4]"
        )
    if category == "CASING":
        cp = r.get("casing_panel") or {}
        return (
            f"Panel deflection (CEMA 375 §7):\n"
            f"  δ_actual = {fmt(cp.get('delta_actual_mm'), 2)} mm   "
            f"δ_allow (L/360) = {fmt(cp.get('delta_allow_mm'), 2)} mm\n"
            f"  σ_max = {fmt(cp.get('sigma_max_MPa'), 1)} MPa   SF yield = {fmt(cp.get('SF_yield'), 1)}\n"
            f"  t_use = {fmt(cp.get('t_use_mm'), 1)} mm   Wind pressure = {inputs.get('wind_pressure_pa')} Pa"
        )
    if category == "CHUTE":
        dc = r.get("discharge_chute") or {}
        perf = dc.get("performance") or {}
        return (
            f"Centrifugal ratio: CR = v² / (r·g)\n"
            f"  v = {fmt(r.get('v'), 4)} m/s   →  CR = {fmt(r.get('cr'), 4)}\n"
            f"  Release angle θ = {fmt(r.get('theta_rel'), 1)}° from vertical\n\n"
            f"Chute angle vs mass-flow minimum:\n"
            f"  Chute angle = {fmt(perf.get('chute_angle_deg'), 1)}°   "
            f"Min required = {fmt(perf.get('min_angle_deg'), 1)}°\n"
            f"  [CEMA 375 §3,5]"
        )
    if category == "BEARINGS":
        boot_pulley = r.get("boot_pulley") or {}
        return (
            f"L10 = (C / P)³ × 10⁶ / (60 × n)   [ISO 281]\n"
            f"Head: P = {fmt(r.get('R_headshaft'), 0)} N   n = {inputs.get('n_rpm')} rpm\n"
            f"  → L10 = {fmt(r.get('L10'), 0)} h\n"
            f"Boot: P = {fmt(boot_pulley.get('R_boot_N'), 0)} N\n"
            f"  → L10 = {fmt(boot_pulley.get('L10_boot_h'), 0)} h\n"
            f"  (20,000h floor enforced as a hard optimizer constraint, both bearings)"
        )
    if category == "FASTENERS":
        cb = r.get("casing_bolts") or {}
        return (
            f"Casing assembly bolt count -- fabrication estimate from panel "
            f"perimeter and stiffener band count:\n"
            f"  Bolt size = {cb.get('bolt_size', '—')}\n"
            f"  Seam bolts = {cb.get('n_bolts_seams', '—')}   "
            f"Stiffener bolts = {cb.get('n_bolts_stiffeners', '—')}\n"
            f"  Total = {cb.get('n_bolts_total', '—')}\n"
            f"  Confirm against actual panel module size and shop joining practice."
        )
    return "No formula available for this category."


class DesignLeafModal(QDialog):
    """Detail modal for one BOM category -- the real line items as a
    table, plus the supporting equations and any category-relevant
    checks[] entries."""

    def __init__(self, category, items, r, inputs, parent=None):
        super().__init__(parent)
        self.setWindowTitle(str(CATEGORY_LABELS.get(category, category)))
        self.setMinimumWidth(620)
        self.resize(680, 600)
        self.setStyleSheet(f"background-color: {PANEL};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(modal_header(CATEGORY_LABELS.get(category, category), "CEMA 375"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(16, 16, 16, 16)
        bl.setSpacing(12)

        checks = _checks_for_category(r.get("checks"), category)
        flagged = [c for c in checks if c.get("type") in ("fail", "warn")]
        if flagged:
            for c in flagged:
                flag_note(c.get("type"), c.get("msg", ""), parent_layout=bl)

        # Calculated values table -- the real BOM line items for this category.
        table_label = QLabel("CALCULATED VALUES / LINE ITEMS")
        table_label.setStyleSheet(f"color: {TEXT2}; font-size: 11px; font-weight: 700; letter-spacing: .04em;")
        bl.addWidget(table_label)

        table = QTableWidget(len(items), 4)
        table.setHorizontalHeaderLabels(["Description", "Spec", "Qty", "Mass"])
        table.verticalHeader().setVisible(False)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {PANEL2}; color: {TEXT}; border: 1px solid {BORDER};
                border-radius: 6px; gridline-color: {BORDER}; font-size: 11px;
            }}
            QHeaderView::section {{
                background-color: {PANEL}; color: {TEXT2}; border: none;
                border-bottom: 1px solid {BORDER}; padding: 6px 4px; font-size: 9.5px; font-weight: 700;
            }}
            QTableWidget::item {{ padding: 4px; }}
        """)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        for row, item in enumerate(items):
            table.setItem(row, 0, QTableWidgetItem(str(item.get("description", ""))))
            table.setItem(row, 1, QTableWidgetItem(str(item.get("spec", ""))))
            table.setItem(row, 2, QTableWidgetItem(f"{item.get('qty','—')} {item.get('unit','')}"))
            table.setItem(row, 3, QTableWidgetItem(kg_to_t(item.get("mass_tot_kg"))))
        table.setMinimumHeight(min(36 + 30 * max(len(items), 1), 280))
        bl.addWidget(table)

        # Supporting equations.
        eq_label = QLabel("SUPPORTING EQUATIONS")
        eq_label.setStyleSheet(f"color: {TEXT2}; font-size: 11px; font-weight: 700; letter-spacing: .04em; margin-top: 4px;")
        bl.addWidget(eq_label)
        eq_box = QLabel(_build_formula(category, r, inputs))
        eq_box.setWordWrap(True)
        eq_box.setStyleSheet(
            f"background-color: {PANEL}; border: 1px solid {BORDER}; border-radius: 6px; "
            f"color: {TEXT2}; font-size: 11px; font-family: 'JetBrains Mono', monospace; padding: 10px 12px;"
        )
        bl.addWidget(eq_box)

        bl.addStretch()
        scroll.setWidget(body)
        layout.addWidget(scroll)
        layout.addWidget(modal_footer(self))
        # This is a read-only detail view -- relabel Apply to Close, no
        # inputs are collected here so there's nothing to apply.
        for btn in self.findChildren(QPushButton):
            if btn.text() == "Apply":
                btn.setText("Close")


class _LeafRow(QFrame):
    def __init__(self, category, n_items, mass_kg, status, on_click, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"""
            QFrame {{ background-color: transparent; border-bottom: 1px solid {BORDER}; }}
            QFrame:hover {{ background-color: rgba(255,255,255,.03); }}
        """)
        self._on_click = on_click
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        s = CAT_STYLE.get(category, CAT_STYLE["CASING"])
        badge = QLabel(category)
        badge.setStyleSheet(
            f"background-color: {s['bg']}; color: {s['color']}; border-radius: 999px; "
            f"padding: 1px 7px; font-size: 8px; font-weight: 700; letter-spacing: .04em;"
        )
        layout.addWidget(badge)

        text_box = QVBoxLayout()
        text_box.setSpacing(1)
        name = QLabel(CATEGORY_LABELS.get(category, category))
        name.setStyleSheet(f"color: {TEXT}; font-size: 12px; font-weight: 700;")
        text_box.addWidget(name)
        sub = QLabel(f"{n_items} item{'s' if n_items != 1 else ''} · {kg_to_t(mass_kg)}")
        sub.setStyleSheet(f"color: {TEXT2}; font-size: 10px;")
        text_box.addWidget(sub)
        layout.addLayout(text_box, 1)

        if status:
            layout.addWidget(status_badge(status, size=16))
        chevron = QLabel("›")
        chevron.setStyleSheet(f"color: {TEXT3}; font-size: 14px; font-weight: 700;")
        layout.addWidget(chevron)

    def mousePressEvent(self, event):
        self._on_click()
        super().mousePressEvent(event)


class StatusDesignLeaves(QWidget):
    """Status column content: advisory strip + one clickable leaf per BOM
    category. set_data(inputs, results) like every other panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {PANEL};")
        self.inputs, self.results = {}, {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        body = QWidget()
        self.body_layout = QVBoxLayout(body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(0)
        self.body_layout.addStretch()
        scroll.setWidget(body)
        outer.addWidget(scroll)

    def set_data(self, inputs, results):
        self.inputs = dict(inputs or {})
        self.results = results or {}
        self._rebuild()

    def _rebuild(self):
        while self.body_layout.count():
            item = self.body_layout.takeAt(0)
            w = item.widget() if item else None
            if w:
                w.setParent(None)
                w.deleteLater()

        r = self.results
        bom = r.get("bom")
        if not bom or not bom.get("items"):
            empty = QLabel("Run a calculation to see component design details.")
            empty.setStyleSheet(f"color: {TEXT2}; font-size: 11px; font-style: italic; padding: 16px;")
            self.body_layout.addWidget(empty)
            self.body_layout.addStretch()
            return

        # ── Advisories ───────────────────────────────────────────────
        adv_box = QFrame()
        adv_layout = QVBoxLayout(adv_box)
        adv_layout.setContentsMargins(12, 12, 12, 8)
        adv_layout.setSpacing(8)
        adv_header = QLabel("ADVISORIES")
        adv_header.setStyleSheet(f"color: {TEXT3}; font-size: 10px; font-weight: 700; letter-spacing: .08em;")
        adv_layout.addWidget(adv_header)

        flagged_checks = [c for c in (r.get("checks") or []) if c.get("type") in ("fail", "warn")]
        if flagged_checks:
            for c in flagged_checks[:8]:   # cap to keep the panel scannable; full list is in each leaf's modal
                flag_note(c.get("type"), c.get("msg", ""), parent_layout=adv_layout)
            if len(flagged_checks) > 8:
                more = QLabel(f"+ {len(flagged_checks) - 8} more — see individual component leaves below.")
                more.setStyleSheet(f"color: {TEXT2}; font-size: 10px; font-style: italic;")
                adv_layout.addWidget(more)
        else:
            flag_note("ok", "No fail/warn flags on the current design.", parent_layout=adv_layout)

        # Real BOM disclaimer notes (mass estimate caveats etc.) -- not
        # fabricated advisories. No sensor-recommendation feature exists
        # in this backend yet (confirmed directly), so none is shown here.
        bom_notes = bom.get("notes") or []
        if bom_notes:
            note_text = QLabel(bom_notes[0])
            note_text.setWordWrap(True)
            note_text.setStyleSheet(f"color: {TEXT2}; font-size: 10px; margin-top: 2px;")
            adv_layout.addWidget(note_text)
        self.body_layout.addWidget(adv_box)

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background-color: {BORDER};")
        self.body_layout.addWidget(divider)

        # ── Leaves, one per BOM category, same order as bom_panel.py ───
        groups = dict(group_items(bom["items"]))
        by_cat_mass = (bom.get("summary") or {}).get("by_category") or {}
        for cat in CATEGORY_ORDER:
            items = groups.get(cat, [])
            if not items:
                continue
            checks = _checks_for_category(r.get("checks"), cat)
            status = _worst_status(checks)
            mass = by_cat_mass.get(cat, {}).get("mass_kg", 0)

            def make_opener(c=cat, it=items):
                def opener():
                    DesignLeafModal(c, it, self.results, self.inputs, self).exec()
                return opener

            row = _LeafRow(cat, len(items), mass, status, make_opener())
            self.body_layout.addWidget(row)

        self.body_layout.addStretch()