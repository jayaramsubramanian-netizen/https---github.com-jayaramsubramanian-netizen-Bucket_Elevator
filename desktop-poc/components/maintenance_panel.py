"""
components/maintenance_panel.py -- Reliability & Maintenance tab.
═══════════════════════════════════════════════════════════════════════════
Faithful port of frontend/src/components/MaintenanceCard.jsx -- same 2x2 KPI
grid, same Schedule/Replacements sub-tabs, same interval badge / priority
styling, same field names throughout.

Backend confirmed real before building any UI: results.maintenance comes from
reliability.py's maintenance_schedule() (not the calculations.py stub -- the
real module is what's deployed, confirmed via a live /calculate response:
kpis, schedule (14 real items), replacements (5 real items), notes all
populated with genuine computed values). Already arrives via the existing
fetch_design() call, no new API wiring needed.

BOX-IN-BOX BORDER SWEEP (this round)
────────────────────────────────────
Every bordered container here used a BARE stylesheet declaration (no
selector). Qt treats that as `* { ... }` -- it applies to the widget AND
EVERY DESCENDANT:

    _schedule_row     bare `border-bottom` -> the task, component and trigger
                      labels each redrew it. 14 schedule rows x 3 extra rules.
    _replacement_row  bare `border-bottom` -> component, action, spec, notes
                      and the "yr" label, all boxed.
    header            -> the title label
    kpi_frame         -> (KPIChips are custom-painted with no children, so
                          these survived -- see below)
    sub_tabs          -> both sub-tab buttons drew their own bottom border
                          ON TOP OF their own :checked underline, which is
                          why the active tab's underline looked doubled.

Verified directly, not assumed: a QFrame with N child QLabels renders 2N
horizontal border runs inside itself under a bare declaration, and 0 under a
scoped one.

Note also (learned from status_design_leaves.py): `QFrame { border: ... }` is
NOT a safe alternative -- a QSS class selector matches all SUBCLASSES, and
QLabel IS a QFrame subclass. Only an objectName selector binds to one widget.
theme.scoped() generates exactly that.

WHY THE KPI CHIPS ALREADY LOOKED RIGHT
──────────────────────────────────────
KPIChip is custom-painted (QPainter) and has no child widgets, so it was
structurally immune to the cascade -- nothing inside it to inherit a border.
That's the same reason TopNav's Q/P/v chips were never affected. Reusing it
here rather than hand-rolling a second lookalike was the right call, and it
is also why this panel's chips were the one part of it that rendered
correctly.

COLORS
──────
This file is the FIRST in the sweep with no stale color literals -- it uses
only theme constants (PRIMARY/SUCCESS/WARNING/DANGER/TEXT*), no hardcoded
rgba(). Nothing to fix. It therefore picks up the v2 palette automatically.

ARCHITECTURE VIOLATION -- FLAGGED, NOT SILENTLY CHANGED
───────────────────────────────────────────────────────
    mtbf_color = DANGER if (mtbf is not None and mtbf < 8000) else TEXT2

That 8,000 h limit is an engineering constant living in the frontend. The
project rule is that the frontend is pure I/O, precisely so a threshold here
can't drift from the backend's. reliability.py computes mtbf_h; it should
also return the verdict (e.g. `mtbf_ok`), the way calculations.py returns
cap_ok / l10_ok. Value preserved unchanged -- flagged, not "fixed" by
inventing a field that doesn't exist. Marked THRESHOLD-IN-FRONTEND below.
(Same class of issue as status_panel.py's 50/80 kN headshaft limits.)

ALSO
────
  * _rebuild()'s clear loop was not recursive -> shared clear_layout().
  * Three flush-left indentation breaks restored -- including `def _rebuild`
    itself, which as pasted sat at module level, outside the class. That is a
    hard error: MaintenancePanel would have had no _rebuild method and
    set_data() would raise AttributeError on the first call.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea,
    QPushButton, QGridLayout,
)
from PySide6.QtCore import Qt

from theme import (
    PANEL, PANEL2, SURFACE, BORDER, TEXT, TEXT2, TEXT3, MUTED,
    PRIMARY, SUCCESS, WARNING, DANGER,
    scoped, plain_bg,
)
from .dialog_helpers import status_badge, KPIChip, clear_layout

# Mirrors MaintenanceCard.jsx's PRIORITY_STYLE -- CRITICAL/ROUTINE/ADVISORY,
# mapped onto the app's existing status_badge vocabulary rather than inventing
# a parallel color system.
PRIORITY_BADGE = {"CRITICAL": "fail", "ADVISORY": "info", "ROUTINE": None}
CAT_ICON = {"LUBRICATION": "🛢", "INSPECTION": "🔍",
            "ADJUSTMENT": "🔧", "CLEANING": "🧹"}


def fmt(v, dp=0, fb="—"):
    if v is None:
        return fb
    try:
        return f"{float(v):,.{dp}f}"
    except (TypeError, ValueError):
        return fb


def _row_frame(alt_bg):
    """Shared, SCOPED zebra row. Both _schedule_row and _replacement_row used
    the identical bare declaration, so both were cascading their bottom border
    onto every label they contained."""
    row = QFrame()
    row.setStyleSheet(scoped(
        row,
        f"background-color: {PANEL2 if alt_bg else 'transparent'}; "
        f"border: none; border-bottom: 1px solid {BORDER};"
    ))
    return row


def _schedule_row(item, alt_bg):
    row = _row_frame(alt_bg)
    layout = QHBoxLayout(row)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(12)

    priority = item.get("priority", "ROUTINE")
    badge_color = (DANGER if priority == "CRITICAL"
                   else (PRIMARY if priority == "ADVISORY" else TEXT3))

    # KPIChip is the same custom-painted widget TopNav's Q/P/v chips use --
    # reused rather than hand-rolling a second lookalike that could drift.
    # It has no child widgets, so it never suffered the border cascade.
    interval_chip_box = QVBoxLayout()
    interval_chip_box.setSpacing(2)
    interval_chip = KPIChip("", "hrs", min_size=(64, 50), value_pixel_size=15)
    interval_chip.set_value(fmt(item.get("interval_h")), badge_color)
    interval_chip_box.addWidget(interval_chip)
    wk = QLabel(f"~{item.get('interval_wk', '—')}wk")
    wk.setAlignment(Qt.AlignmentFlag.AlignCenter)
    wk.setStyleSheet(f"color: {TEXT3}; font-size: 9px;")
    interval_chip_box.addWidget(wk)
    layout.addLayout(interval_chip_box)

    content = QVBoxLayout()
    content.setSpacing(3)
    head_row = QHBoxLayout()
    head_row.setSpacing(8)
    icon = QLabel(CAT_ICON.get(item.get("category", ""), "•"))
    icon.setStyleSheet("font-size: 13px;")
    head_row.addWidget(icon)
    task = QLabel(item.get("task", ""))
    task.setWordWrap(True)
    task.setStyleSheet(f"color: {TEXT}; font-size: 12px; font-weight: 700;")
    head_row.addWidget(task, 1)
    badge_status = PRIORITY_BADGE.get(priority)
    if badge_status:
        head_row.addWidget(status_badge(badge_status, size=15))
    content.addLayout(head_row)

    comp = QLabel(item.get("component", ""))
    comp.setStyleSheet(f"color: {TEXT2}; font-size: 11px;")
    content.addWidget(comp)
    trigger = QLabel(item.get("trigger", ""))
    trigger.setWordWrap(True)
    trigger.setStyleSheet(f"color: {TEXT2}; font-size: 10.5px;")
    content.addWidget(trigger)
    layout.addLayout(content, 1)
    return row


def _replacement_row(item, alt_bg):
    row = _row_frame(alt_bg)
    layout = QVBoxLayout(row)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(4)

    head_row = QHBoxLayout()
    head_row.setSpacing(10)
    comp = QLabel(item.get("component", ""))
    comp.setWordWrap(True)
    comp.setStyleSheet(f"color: {TEXT}; font-size: 12px; font-weight: 700;")
    head_row.addWidget(comp, 1)

    is_critical = item.get("priority") == "CRITICAL"
    life_chip_box = QVBoxLayout()
    life_chip_box.setSpacing(2)
    life_chip = KPIChip("", "hrs", min_size=(74, 50), value_pixel_size=15)
    life_chip.set_value(fmt(item.get("estimated_life_h")),
                        DANGER if is_critical else WARNING)
    life_chip_box.addWidget(life_chip)
    yrs = QLabel(f"≈ {item.get('estimated_life_yr', '—')} yr")
    yrs.setAlignment(Qt.AlignmentFlag.AlignCenter)
    yrs.setStyleSheet(f"color: {TEXT3}; font-size: 9px;")
    life_chip_box.addWidget(yrs)
    head_row.addLayout(life_chip_box)
    layout.addLayout(head_row)

    action = QLabel(item.get("action", ""))
    action.setWordWrap(True)
    action.setStyleSheet(f"color: {PRIMARY}; font-size: 11.5px; font-weight: 600;")
    layout.addWidget(action)
    spec = QLabel(item.get("material_spec", ""))
    spec.setWordWrap(True)
    spec.setStyleSheet(f"color: {TEXT2}; font-size: 10.5px;")
    layout.addWidget(spec)
    notes = QLabel(item.get("notes", ""))
    notes.setWordWrap(True)
    notes.setStyleSheet(f"color: {TEXT2}; font-size: 10.5px;")
    layout.addWidget(notes)
    return row


class _SubTabButton(QPushButton):
    """SCOPED. The class-selector form previously used here happened to be
    harmless (a QPushButton has no styleable child widgets), but the PARENT
    sub_tabs frame's bare `border-bottom` was landing on these buttons -- so
    the active tab drew its own 2px primary underline AND an inherited 1px
    border, which is the doubled underline."""

    def __init__(self, label, parent=None):
        super().__init__(label, parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggled.connect(self._restyle)
        self._restyle(False)

    def _restyle(self, checked):
        if checked:
            self.setStyleSheet(scoped(
                self,
                f"background-color: transparent; color: {PRIMARY}; border: none; "
                f"border-bottom: 2px solid {PRIMARY}; padding: 9px 14px; "
                f"font-size: 12px; font-weight: 700;"
            ))
        else:
            self.setStyleSheet(scoped(
                self,
                f"background-color: transparent; color: {TEXT2}; border: none; "
                f"border-bottom: 2px solid transparent; padding: 9px 14px; "
                f"font-size: 12px;",
                extra="{sel}:hover { color: %s; }" % TEXT,
            ))


class MaintenancePanel(QWidget):
    """Port of MaintenanceCard.jsx's default export. set_data(inputs, results)
    like every other panel; reads results.maintenance."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(plain_bg(self, PANEL))
        self._maint = None
        self._sub_tab = "schedule"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(scoped(scroll, "border: none; background: transparent;"))
        self.body = QWidget()
        self.body.setStyleSheet(plain_bg(self.body, PANEL))
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(0)
        self.body_layout.addStretch()
        scroll.setWidget(self.body)
        outer.addWidget(scroll)

    def set_data(self, inputs, results):
        results = results or {}
        self._maint = results.get("maintenance")
        self._rebuild()

    def _rebuild(self):
        # NOTE: as pasted, `def _rebuild` sat at column 0 -- OUTSIDE the class.
        # MaintenancePanel would have had no _rebuild method at all and
        # set_data() would raise AttributeError on the first calculation.
        # Restored to a method. Also: the old clear loop was not recursive.
        clear_layout(self.body_layout)

        if not self._maint:
            empty = QLabel(
                "Maintenance schedule not available — run a calculation first.")
            empty.setWordWrap(True)
            empty.setStyleSheet(
                f"color: {TEXT2}; font-size: 11px; font-style: italic; padding: 16px;")
            self.body_layout.addWidget(empty)
            self.body_layout.addStretch()
            return

        maint = self._maint
        kpis = maint.get("kpis") or {}
        schedule = sorted(maint.get("schedule") or [],
                          key=lambda i: i.get("interval_h", 0))
        replacements = maint.get("replacements") or []
        notes = maint.get("notes") or []

        header = QFrame()
        header.setStyleSheet(scoped(
            header,
            f"background-color: {PANEL2}; border: none; "
            f"border-bottom: 1px solid {BORDER};"
        ))
        hl = QVBoxLayout(header)
        hl.setContentsMargins(14, 10, 14, 10)
        title = QLabel("RELIABILITY & MAINTENANCE")
        title.setStyleSheet(
            f"color: {TEXT3}; font-size: 11px; font-weight: 700; letter-spacing: .08em;")
        hl.addWidget(title)
        self.body_layout.addWidget(header)

        kpi_frame = QFrame()
        kpi_frame.setStyleSheet(scoped(
            kpi_frame,
            f"background-color: transparent; border: none; "
            f"border-bottom: 1px solid {BORDER};"
        ))
        grid = QGridLayout(kpi_frame)
        grid.setContentsMargins(14, 12, 14, 12)
        grid.setSpacing(8)

        mtbf = kpis.get("mtbf_h")
        # THRESHOLD-IN-FRONTEND (see module docstring): this 8,000 h limit is an
        # engineering constant that belongs in reliability.py, returned as a
        # verdict alongside mtbf_h the way calculations.py returns cap_ok/l10_ok.
        # Value preserved exactly -- flagged, not silently altered.
        mtbf_color = DANGER if (mtbf is not None and mtbf < 8000) else TEXT2

        tiles = [
            ("Bearing L10", fmt(kpis.get("L10_hours")), "hrs", PRIMARY),
            ("Belt Life Est.", fmt(kpis.get("belt_life_h")), "hrs", WARNING),
            ("Grease Interval", fmt(kpis.get("grease_interval_h")), "hrs", SUCCESS),
            ("Min Repl. Interval", fmt(mtbf), "hrs", mtbf_color),
        ]
        for i, (label, value, unit, color) in enumerate(tiles):
            chip = KPIChip(label, unit, min_size=(140, 62), value_pixel_size=19)
            chip.set_value(value, color)
            grid.addWidget(chip, i // 2, i % 2)
        self.body_layout.addWidget(kpi_frame)

        sub_tabs = QFrame()
        sub_tabs.setStyleSheet(scoped(
            sub_tabs,
            f"background-color: {PANEL2}; border: none; "
            f"border-bottom: 1px solid {BORDER};"
        ))
        stl = QHBoxLayout(sub_tabs)
        stl.setContentsMargins(14, 0, 14, 0)
        stl.setSpacing(4)
        self.schedule_btn = _SubTabButton(f"Schedule ({len(schedule)})")
        self.schedule_btn.setChecked(self._sub_tab == "schedule")
        self.schedule_btn.clicked.connect(
            lambda _checked=False: self._set_sub_tab("schedule"))
        stl.addWidget(self.schedule_btn)
        self.replacement_btn = _SubTabButton(f"Replacements ({len(replacements)})")
        self.replacement_btn.setChecked(self._sub_tab == "replacement")
        self.replacement_btn.clicked.connect(
            lambda _checked=False: self._set_sub_tab("replacement"))
        stl.addWidget(self.replacement_btn)
        stl.addStretch()
        self.body_layout.addWidget(sub_tabs)

        if self._sub_tab == "schedule":
            for i, item in enumerate(schedule):
                self.body_layout.addWidget(_schedule_row(item, alt_bg=(i % 2 != 0)))
        else:
            for i, item in enumerate(replacements):
                self.body_layout.addWidget(_replacement_row(item, alt_bg=(i % 2 != 0)))

        if notes:
            notes_box = QFrame()
            notes_box.setStyleSheet(scoped(
                notes_box, "background-color: transparent; border: none;"))
            nl = QVBoxLayout(notes_box)
            nl.setContentsMargins(14, 10, 14, 14)
            nl.setSpacing(4)
            for n in notes:
                lbl = QLabel(f"*  {n}")
                lbl.setWordWrap(True)
                lbl.setStyleSheet(f"color: {TEXT2}; font-size: 10.5px;")
                nl.addWidget(lbl)
            self.body_layout.addWidget(notes_box)

        self.body_layout.addStretch()

    def _set_sub_tab(self, tab_id):
        self._sub_tab = tab_id
        self._rebuild()