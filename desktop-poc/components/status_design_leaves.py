"""
components/status_design_leaves.py -- Status column content for the
Components tab: advisory strip + one clickable leaf per BOM category,
each opening a detail modal with real line items and supporting equations.
═══════════════════════════════════════════════════════════════════════════

BOX-IN-BOX BORDER SWEEP (this round)
────────────────────────────────────
_LeafRow contained the subtlest instance of the bug in the whole app:

    self.setStyleSheet(f'''
        QFrame {{ background-color: transparent;
                  border-bottom: 1px solid {BORDER}; }}
        QFrame:hover {{ background-color: rgba(255,255,255,.03); }}
    ''')

This LOOKS correctly scoped -- it names a class rather than using a bare
declaration. It isn't. A QSS class selector matches the class AND ALL ITS
SUBCLASSES, and **QLabel is a QFrame subclass** (verified directly:
QLabel.__mro__ is QLabel -> QFrame -> QWidget -> QObject). So this rule
applied to the row AND to the category badge, the name label, the sub
label and the chevron -- five bottom borders per row instead of one.

That is worth internalising: `QFrame { border: ... }` is NOT a safe way to
scope. Only an objectName selector (`QFrame#name`) binds to one widget.
theme.scoped() does exactly that, and is used throughout below.

Also swept: the equations box, the BOM table (its QHeaderView/::item rules
are intentional descendant targeting and are kept), the modal body and
scroll areas.

OTHER REAL BUGS FIXED
─────────────────────
  * _rebuild()'s clear loop was NOT recursive -- it removed only
    item.widget() entries and silently left every addLayout() sub-layout
    behind. This is the exact bug checks_panel.py's docstring describes and
    fixes; this file was left with the broken version, so the advisory strip
    accumulated duplicate flag_note rows on every recalculation. Now uses
    the shared dialog_helpers.clear_layout().
  * Local fmt() duplicated dialog_helpers.fmt() with a different default dp
    (2 vs 1). Now imports the shared one and passes dp explicitly at every
    call site, so the displayed precision is unchanged.
  * Every color literal was v1 and stale (this file imports DANGER/WARNING/
    etc. from theme.py, which is now v2) -- the badge tints came from
    bom_panel's CAT_STYLE, which should be checked for the same problem.
  * Hardcoded "'JetBrains Mono', monospace" -> theme.FF_MONO.
  * Four flush-left indentation breaks restored (they were hard
    SyntaxErrors: the module could not have imported as pasted).
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea,
    QDialog, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView,
)
from PySide6.QtCore import Qt

from theme import (
    PANEL, PANEL2, SURFACE, BORDER, BORDER2, TEXT, TEXT2, TEXT3, MUTED,
    PRIMARY, SUCCESS, WARNING, DANGER, R_SM, R_PILL, FF_MONO,
    scoped, plain_bg,
)
from .dialog_helpers import (
    status_badge, flag_note, modal_header, modal_footer, clear_layout, fmt,
)
from .bom_panel import CATEGORY_ORDER, CAT_STYLE, group_items, kg_to_t

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


def _norm(t):
    return "ok" if t == "pass" else (t or "info")


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
    straight from already-computed results/inputs, nothing recomputed."""
    bkt = r.get("bucket") or {}

    if category == "SHAFT":
        boot_shaft = (r.get("boot_pulley") or {}).get("shaft") or {}
        return (
            f"Head shaft -- stress (ASME DE-Goodman) + deflection "
            f"(CEMA 0.0015 in/in):\n"
            f"  d_stress   = {fmt(r.get('d_stress_mm'), 1)} mm\n"
            f"  d_deflect  = {fmt(r.get('d_deflect_mm'), 1)} mm\n"
            f"  Governing  = {fmt(r.get('d_mm'), 1)} mm  "
            f"(by {r.get('governed_by','stress')})\n"
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
            f"  t_governing = "
            f"{fmt((r.get('pulley_shell') or {}).get('t_governing_mm'), 1)} mm\n"
            f"Boot pulley shell:\n"
            f"  t_governing = "
            f"{fmt((r.get('boot_shell') or {}).get('t_governing_mm'), 1)} mm\n"
            f"  [CEMA 375 §3,6]"
        )

    if category == "BELT":
        return (
            f"Q = (v / s) · Vb · η · ρ · 3.6\n"
            f"  v = {fmt(r.get('v'), 3)} m/s   s = {fmt(r.get('spacing'), 4)} m\n"
            f"  Vb = {bkt.get('V')} L   "
            f"η = {fmt((inputs.get('fill_pct') or 0) / 100, 2)}\n"
            f"  → Q = {fmt(r.get('Q'), 2)} t/h\n\n"
            f"Belt slip (Euler/Eytelwein): e^μθ = {fmt(r.get('euler_ratio'), 3)}\n"
            f"  μ = {inputs.get('mu')}   θ = {fmt(r.get('wrap_effective_deg'), 0)}°\n"
            f"  [CEMA 375 §4]"
        )

    if category == "DRIVE":
        return (
            f"P = (P_lift + P_digging) × Ceff\n"
            f"  P_lift = {fmt(r.get('P_lift'), 3)} kW   "
            f"P_digging = {fmt(r.get('P_digging'), 3)} kW\n"
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
            # No CEMA citation here, deliberately: CEMA does not publish a
            # hydraulic take-up cylinder method. This is standard cylinder
            # mechanics and is labeled as such rather than implying backing
            # the standard doesn't give.
            return (
                f"Hydraulic take-up -- standard cylinder mechanics "
                f"(not a CEMA-published method):\n"
                f"  Force = {fmt((th.get('F_cylinder_N') or 0) / 1000, 1)} kN\n"
                f"  Bore dia (min) = {fmt(th.get('d_bore_min_mm'), 1)} mm\n"
                f"  Stroke = {fmt(th.get('stroke_mm'), 0)} mm   "
                f"SF buckling = {fmt(th.get('SF_buckling'), 2)}"
            )
        return (
            f"Gravity take-up -- counterweight sizing:\n"
            f"  K (tension factor) = {inputs.get('K_takeup')}\n"
            f"  Counterweight (gross) = "
            f"{fmt(tg.get('W_counterweight_kg_gross'), 0)} kg\n"
            f"  Travel required = {fmt(tg.get('travel_m'), 3)} m\n"
            f"  [CEMA 375 §4]"
        )

    if category == "CASING":
        cp = r.get("casing_panel") or {}
        return (
            f"Panel deflection (CEMA 375 §7):\n"
            f"  δ_actual = {fmt(cp.get('delta_actual_mm'), 2)} mm   "
            f"δ_allow (L/360) = {fmt(cp.get('delta_allow_mm'), 2)} mm\n"
            f"  σ_max = {fmt(cp.get('sigma_max_MPa'), 1)} MPa   "
            f"SF yield = {fmt(cp.get('SF_yield'), 1)}\n"
            f"  t_use = {fmt(cp.get('t_use_mm'), 1)} mm   "
            f"Wind pressure = {inputs.get('wind_pressure_pa')} Pa"
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
            f"Head: P = {fmt(r.get('R_headshaft'), 0)} N   "
            f"n = {inputs.get('n_rpm')} rpm\n"
            f"  → L10 = {fmt(r.get('L10'), 0)} h\n"
            f"Boot: P = {fmt(boot_pulley.get('R_boot_N'), 0)} N\n"
            f"  → L10 = {fmt(boot_pulley.get('L10_boot_h'), 0)} h\n"
            f"  (20,000h floor enforced as a hard optimizer constraint, "
            f"both bearings)"
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
            f"  Confirm against actual panel module size and shop joining "
            f"practice."
        )

    return "No formula available for this category."


class DesignLeafModal(QDialog):
    """Detail modal for one BOM category -- the real line items as a table,
    plus the supporting equations and any category-relevant checks[]."""

    def __init__(self, category, items, r, inputs, parent=None):
        super().__init__(parent)
        label = CATEGORY_LABELS.get(category, category)
        self.setWindowTitle(str(label))
        self.setMinimumWidth(620)
        self.resize(680, 600)
        self.setStyleSheet(plain_bg(self, PANEL))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(modal_header(label, "CEMA 375"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(scoped(scroll, "border: none; background: transparent;"))
        body = QWidget()
        body.setStyleSheet(plain_bg(body, PANEL))
        bl = QVBoxLayout(body)
        bl.setContentsMargins(16, 16, 16, 16)
        bl.setSpacing(12)

        checks = _checks_for_category(r.get("checks"), category)
        for c in [c for c in checks if _norm(c.get("type")) in ("fail", "warn")]:
            flag_note(_norm(c.get("type")), c.get("msg", ""), parent_layout=bl)

        table_label = QLabel("CALCULATED VALUES / LINE ITEMS")
        table_label.setStyleSheet(
            f"color: {TEXT2}; font-size: 11px; font-weight: 700; letter-spacing: .04em;")
        bl.addWidget(table_label)

        table = QTableWidget(len(items), 4)
        table.setHorizontalHeaderLabels(["Description", "Spec", "Qty", "Mass"])
        table.verticalHeader().setVisible(False)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        # QHeaderView::section and QTableWidget::item are INTENTIONAL
        # descendant rules -- those sub-elements are exactly what we mean to
        # style. That's the legitimate use of a descendant selector, unlike
        # a bare declaration that hits children by accident.
        table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {PANEL2}; color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: {R_SM}px; gridline-color: {BORDER};
                font-size: 11px;
            }}
            QHeaderView::section {{
                background-color: {PANEL}; color: {TEXT2}; border: none;
                border-bottom: 1px solid {BORDER}; padding: 6px 4px;
                font-size: 9.5px; font-weight: 700;
            }}
            QTableWidget::item {{ padding: 4px; border: none; }}
        """)
        hh = table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        for row, item in enumerate(items):
            table.setItem(row, 0, QTableWidgetItem(str(item.get("description", ""))))
            table.setItem(row, 1, QTableWidgetItem(str(item.get("spec", ""))))
            table.setItem(row, 2, QTableWidgetItem(
                f"{item.get('qty','—')} {item.get('unit','')}"))
            table.setItem(row, 3, QTableWidgetItem(kg_to_t(item.get("mass_tot_kg"))))
        table.setMinimumHeight(min(36 + 30 * max(len(items), 1), 280))
        bl.addWidget(table)

        eq_label = QLabel("SUPPORTING EQUATIONS")
        eq_label.setStyleSheet(
            f"color: {TEXT2}; font-size: 11px; font-weight: 700; "
            f"letter-spacing: .04em; margin-top: 4px;")
        bl.addWidget(eq_label)

        eq_box = QLabel(_build_formula(category, r, inputs))
        eq_box.setWordWrap(True)
        eq_box.setStyleSheet(scoped(
            eq_box,
            f"background-color: {PANEL}; border: 1px solid {BORDER}; "
            f"border-radius: {R_SM}px; color: {TEXT2}; font-size: 11px; "
            f"font-family: {FF_MONO}; padding: 10px 12px;"
        ))
        bl.addWidget(eq_box)

        bl.addStretch()
        scroll.setWidget(body)
        layout.addWidget(scroll)
        layout.addWidget(modal_footer(self))

        # Read-only detail view -- relabel Apply to Close, since no inputs are
        # collected here and there is nothing to apply.
        for btn in self.findChildren(QPushButton):
            if btn.text() == "Apply":
                btn.setText("Close")


class _LeafRow(QFrame):
    """One clickable BOM-category leaf.

    THE SUBTLEST BOX-IN-BOX IN THE APP, fixed here. The old stylesheet was:

        QFrame { background-color: transparent;
                 border-bottom: 1px solid BORDER; }

    which LOOKS scoped -- it names a class rather than using a bare
    declaration. But a QSS class selector matches the class and ALL ITS
    SUBCLASSES, and QLabel IS a QFrame subclass (QLabel -> QFrame ->
    QWidget). So the badge, the name, the sub-label and the chevron each
    inherited `border-bottom` -- five stacked rules per row.

    Only an objectName selector (QFrame#name) binds to a single widget.
    theme.scoped() generates exactly that.
    """

    def __init__(self, category, n_items, mass_kg, status, on_click, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(scoped(
            self,
            f"background-color: transparent; border: none; "
            f"border-bottom: 1px solid {BORDER};",
            extra="{sel}:hover { background-color: rgba(255,255,255,.03); }",
        ))
        self._on_click = on_click

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        s = CAT_STYLE.get(category, CAT_STYLE["CASING"])
        badge = QLabel(category)
        badge.setStyleSheet(scoped(
            badge,
            f"background-color: {s['bg']}; color: {s['color']}; border: none; "
            f"border-radius: {R_PILL}px; padding: 1px 7px; font-size: 8px; "
            f"font-weight: 700; letter-spacing: .04em;"
        ))
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
        self.setStyleSheet(plain_bg(self, PANEL))
        self.inputs, self.results = {}, {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(scoped(scroll, "border: none; background: transparent;"))
        body = QWidget()
        body.setStyleSheet(plain_bg(body, PANEL))
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
        # FIXED: the old loop removed only item.widget() entries and left
        # every addLayout() sub-layout in place, so the advisory strip
        # accumulated duplicate flag_note rows on every recalculation. The
        # shared clear_layout() recurses into sub-layouts.
        clear_layout(self.body_layout)

        r = self.results
        bom = r.get("bom")
        if not bom or not bom.get("items"):
            empty = QLabel("Run a calculation to see component design details.")
            empty.setStyleSheet(
                f"color: {TEXT2}; font-size: 11px; font-style: italic; padding: 16px;")
            self.body_layout.addWidget(empty)
            self.body_layout.addStretch()
            return

        # ── Advisories ───────────────────────────────────────────────
        adv_box = QFrame()
        adv_box.setStyleSheet(scoped(
            adv_box, "background-color: transparent; border: none;"))
        adv_layout = QVBoxLayout(adv_box)
        adv_layout.setContentsMargins(12, 12, 12, 8)
        adv_layout.setSpacing(8)
        adv_header = QLabel("ADVISORIES")
        adv_header.setStyleSheet(
            f"color: {TEXT3}; font-size: 10px; font-weight: 700; letter-spacing: .08em;")
        adv_layout.addWidget(adv_header)

        flagged = [c for c in (r.get("checks") or [])
                   if _norm(c.get("type")) in ("fail", "warn")]
        if flagged:
            # Capped to keep the panel scannable; the full list is in each
            # leaf's modal.
            for c in flagged[:8]:
                flag_note(_norm(c.get("type")), c.get("msg", ""),
                          parent_layout=adv_layout)
            if len(flagged) > 8:
                more = QLabel(
                    f"+ {len(flagged) - 8} more — see individual component "
                    f"leaves below.")
                more.setWordWrap(True)
                more.setStyleSheet(
                    f"color: {TEXT2}; font-size: 10px; font-style: italic;")
                adv_layout.addWidget(more)
        else:
            flag_note("ok", "No fail/warn flags on the current design.",
                      parent_layout=adv_layout)

        # Real BOM disclaimer notes (mass-estimate caveats etc.) -- not
        # fabricated advisories. No sensor-recommendation feature exists in
        # this backend, so none is shown here.
        bom_notes = bom.get("notes") or []
        if bom_notes:
            note_text = QLabel(bom_notes[0])
            note_text.setWordWrap(True)
            note_text.setStyleSheet(f"color: {TEXT2}; font-size: 10px; margin-top: 2px;")
            adv_layout.addWidget(note_text)
        self.body_layout.addWidget(adv_box)

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(plain_bg(divider, BORDER2))
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

            self.body_layout.addWidget(
                _LeafRow(cat, len(items), mass, status, make_opener()))

        self.body_layout.addStretch()