"""
components/maintenance_panel.py -- Reliability & Maintenance tab.
═══════════════════════════════════════════════════════════════════════════
Faithful port of frontend/src/components/MaintenanceCard.jsx, read directly
before writing this (not assumed) -- same 2x2 KPI grid, same Schedule/
Replacements sub-tabs, same interval badge / priority styling, same field
names throughout.

Backend confirmed real before building any UI: results.maintenance comes
from reliability.py's maintenance_schedule() (not the calculations.py stub
-- the real module is what's actually deployed, confirmed via a live
/calculate response: kpis, schedule (14 real items), replacements (5 real
items), notes all populated with genuine computed values, not placeholders).
Already arrives via the existing fetch_design() call, no new API wiring
needed -- same situation results.bom was already in before bom_panel.py.

New top-nav tab per direct instruction, positioned between Components and
Materials in main.py's TABS list and middle_stack.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea, QPushButton, QGridLayout,
)
from PySide6.QtCore import Qt

from theme import PANEL, PANEL2, BORDER, TEXT, TEXT2, TEXT3, MUTED, PRIMARY, SUCCESS, WARNING, DANGER
from .dialog_helpers import status_badge

# Mirrors MaintenanceCard.jsx's PRIORITY_STYLE -- CRITICAL/ROUTINE/ADVISORY,
# mapped onto the app's existing status_badge vocabulary (fail/info/none)
# rather than inventing a parallel color system.
PRIORITY_BADGE = {"CRITICAL": "fail", "ADVISORY": "info", "ROUTINE": None}
CAT_ICON = {"LUBRICATION": "🛢", "INSPECTION": "🔍", "ADJUSTMENT": "🔧", "CLEANING": "🧹"}


def fmt(v, dp=0, fb="—"):
    if v is None:
        return fb
    try:
        return f"{float(v):,.{dp}f}"
    except (TypeError, ValueError):
        return fb


class _KpiTile(QFrame):
    def __init__(self, label, value, unit, color, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {PANEL2}; border: 1px solid {BORDER}; border-radius: 6px;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(3)
        lbl = QLabel(label.upper())
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"color: {TEXT3}; font-size: 9px; font-weight: 600; letter-spacing: .06em;")
        layout.addWidget(lbl)
        val = QLabel(value)
        val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        val.setStyleSheet(f"color: {color}; font-size: 17px; font-weight: 700; font-family: 'JetBrains Mono', monospace;")
        layout.addWidget(val)
        u = QLabel(unit)
        u.setAlignment(Qt.AlignmentFlag.AlignCenter)
        u.setStyleSheet(f"color: {TEXT2}; font-size: 10px; font-family: 'JetBrains Mono', monospace;")
        layout.addWidget(u)


def _schedule_row(item, alt_bg):
    row = QFrame()
    row.setStyleSheet(f"background-color: {PANEL2 if alt_bg else 'transparent'}; border-bottom: 1px solid {BORDER};")
    layout = QHBoxLayout(row)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(12)

    priority = item.get("priority", "ROUTINE")
    badge_color = DANGER if priority == "CRITICAL" else (PRIMARY if priority == "ADVISORY" else TEXT3)
    interval_box = QFrame()
    interval_box.setFixedWidth(64)
    interval_box.setStyleSheet(
        f"background-color: rgba(224,82,82,.06); border: 1px solid {badge_color}; border-radius: 6px;"
        if priority == "CRITICAL" else
        f"background-color: transparent; border: 1px solid {BORDER}; border-radius: 6px;"
    )
    ib = QVBoxLayout(interval_box)
    ib.setContentsMargins(4, 8, 4, 8)
    ib.setSpacing(1)
    hrs = QLabel(fmt(item.get("interval_h")))
    hrs.setAlignment(Qt.AlignmentFlag.AlignCenter)
    hrs.setStyleSheet(f"color: {badge_color}; font-size: 15px; font-weight: 700; font-family: 'JetBrains Mono', monospace;")
    ib.addWidget(hrs)
    hrs_unit = QLabel("hours")
    hrs_unit.setAlignment(Qt.AlignmentFlag.AlignCenter)
    hrs_unit.setStyleSheet(f"color: {TEXT3}; font-size: 9px;")
    ib.addWidget(hrs_unit)
    wk = QLabel(f"~{item.get('interval_wk', '—')}wk")
    wk.setAlignment(Qt.AlignmentFlag.AlignCenter)
    wk.setStyleSheet(f"color: {TEXT3}; font-size: 9px;")
    ib.addWidget(wk)
    layout.addWidget(interval_box)

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
    row = QFrame()
    row.setStyleSheet(f"background-color: {PANEL2 if alt_bg else 'transparent'}; border-bottom: 1px solid {BORDER};")
    layout = QVBoxLayout(row)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(4)

    head_row = QHBoxLayout()
    head_row.setSpacing(10)
    comp = QLabel(item.get("component", ""))
    comp.setWordWrap(True)
    comp.setStyleSheet(f"color: {TEXT}; font-size: 12px; font-weight: 700;")
    head_row.addWidget(comp, 1)
    life_box = QVBoxLayout()
    life_box.setSpacing(0)
    is_critical = item.get("priority") == "CRITICAL"
    life = QLabel(f"{fmt(item.get('estimated_life_h'))}h")
    life.setAlignment(Qt.AlignmentFlag.AlignRight)
    life.setStyleSheet(
        f"color: {DANGER if is_critical else WARNING}; font-size: 15px; font-weight: 700; "
        f"font-family: 'JetBrains Mono', monospace;"
    )
    life_box.addWidget(life)
    yrs = QLabel(f"≈ {item.get('estimated_life_yr', '—')} yr")
    yrs.setAlignment(Qt.AlignmentFlag.AlignRight)
    yrs.setStyleSheet(f"color: {TEXT3}; font-size: 10px;")
    life_box.addWidget(yrs)
    head_row.addLayout(life_box)
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
    def __init__(self, label, parent=None):
        super().__init__(label, parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggled.connect(self._restyle)
        self._restyle(False)

    def _restyle(self, checked):
        if checked:
            self.setStyleSheet(
                f"QPushButton {{ background-color: transparent; color: {PRIMARY}; border: none; "
                f"border-bottom: 2px solid {PRIMARY}; padding: 9px 14px; font-size: 12px; font-weight: 700; }}"
            )
        else:
            self.setStyleSheet(
                f"QPushButton {{ background-color: transparent; color: {TEXT2}; border: none; "
                f"border-bottom: 2px solid transparent; padding: 9px 14px; font-size: 12px; }}"
            )


class MaintenancePanel(QWidget):
    """Port of MaintenanceCard.jsx's default export. set_data(inputs,
    results) like every other panel; reads results.maintenance."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {PANEL};")
        self._maint = None
        self._sub_tab = "schedule"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        self.body = QWidget()
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
        while self.body_layout.count():
            item = self.body_layout.takeAt(0)
            w = item.widget() if item else None
            if w:
                w.setParent(None)
                w.deleteLater()

        if not self._maint:
            empty = QLabel("Maintenance schedule not available — run a calculation first.")
            empty.setWordWrap(True)
            empty.setStyleSheet(f"color: {TEXT2}; font-size: 11px; font-style: italic; padding: 16px;")
            self.body_layout.addWidget(empty)
            self.body_layout.addStretch()
            return

        maint = self._maint
        kpis = maint.get("kpis") or {}
        schedule = sorted(maint.get("schedule") or [], key=lambda i: i.get("interval_h", 0))
        replacements = maint.get("replacements") or []
        notes = maint.get("notes") or []

        header = QFrame()
        header.setStyleSheet(f"background-color: {PANEL2}; border-bottom: 1px solid {BORDER};")
        hl = QVBoxLayout(header)
        hl.setContentsMargins(14, 10, 14, 10)
        title = QLabel("RELIABILITY & MAINTENANCE")
        title.setStyleSheet(f"color: {TEXT3}; font-size: 11px; font-weight: 700; letter-spacing: .08em;")
        hl.addWidget(title)
        self.body_layout.addWidget(header)

        kpi_frame = QFrame()
        kpi_frame.setStyleSheet(f"border-bottom: 1px solid {BORDER};")
        grid = QGridLayout(kpi_frame)
        grid.setContentsMargins(14, 12, 14, 12)
        grid.setSpacing(8)
        mtbf = kpis.get("mtbf_h")
        mtbf_color = DANGER if (mtbf is not None and mtbf < 8000) else TEXT2
        tiles = [
            ("Bearing L10", fmt(kpis.get("L10_hours")), "hours", PRIMARY),
            ("Belt Life Est.", fmt(kpis.get("belt_life_h")), "hours", WARNING),
            ("Grease Interval", fmt(kpis.get("grease_interval_h")), "hours", SUCCESS),
            ("Min Repl. Interval", fmt(mtbf), "hours", mtbf_color),
        ]
        for i, (label, value, unit, color) in enumerate(tiles):
            grid.addWidget(_KpiTile(label, value, unit, color), i // 2, i % 2)
        self.body_layout.addWidget(kpi_frame)

        sub_tabs = QFrame()
        sub_tabs.setStyleSheet(f"background-color: {PANEL2}; border-bottom: 1px solid {BORDER};")
        stl = QHBoxLayout(sub_tabs)
        stl.setContentsMargins(14, 0, 14, 0)
        stl.setSpacing(4)
        self.schedule_btn = _SubTabButton(f"Schedule ({len(schedule)})")
        self.schedule_btn.setChecked(self._sub_tab == "schedule")
        self.schedule_btn.clicked.connect(lambda: self._set_sub_tab("schedule"))
        stl.addWidget(self.schedule_btn)
        self.replacement_btn = _SubTabButton(f"Replacements ({len(replacements)})")
        self.replacement_btn.setChecked(self._sub_tab == "replacement")
        self.replacement_btn.clicked.connect(lambda: self._set_sub_tab("replacement"))
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