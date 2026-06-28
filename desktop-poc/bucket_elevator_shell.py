"""
bucket_elevator_shell.py -- PySide6 shell modeled on BucketElevatorPage.jsx
═══════════════════════════════════════════════════════════════════════════
Mirrors the REAL layout (checked directly against the file, not recalled
from memory): top nav (logo + 5 tab pills + Q/P/v KPI chips + Save/Load)
over a 4-column body:
    [Equipment Tree] [Parameters] [tab-driven middle content] [Status]

This is a SHELL, not a finished app -- the point is to give every future
ported component an obvious, already-correct place to land, one at a time,
the same way BucketElevatorPage.jsx already organizes the real one.

Integrated so far (2 of ~14 components):
    - ElevationView      -> middle column, "Results" tab
    - EquipmentTreePanel -> left column

Everything else is an explicit, labeled placeholder -- not a fake
implementation pretending to be real, just a marked spot. As each one
gets ported, the pattern is the same as the last round's combined_shell_
example.py: build it as a plain QWidget with set_data(inputs, results),
then swap the placeholder in this file for the real widget.

No input bar, per your note -- one fixed scenario auto-loads at startup.
InputSidebar.jsx is what will eventually drive real inputs into the
Parameters column; until that's ported, there's nothing for an input bar
here to usefully control.

Run:
    python3 bucket_elevator_shell.py
"""
import sys
import requests

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QStackedWidget, QSizePolicy,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

from elevation_view_poc import ElevationView, fetch_design
from equipment_tree_poc import node_status  # noqa: F401  (kept available for the next panel to use)
from combined_shell_example import EquipmentTreePanel

API_BASE = "http://localhost:8000/api"

# ── Colors -- same palette used throughout every PoC so far ────────────────
BG, PANEL, PANEL2, BORDER = "#0a1628", "#0d1c2e", "#0f2138", "#1c3050"
TEXT, TEXT2, TEXT3, MUTED = "#e8f0fa", "#b0c4d8", "#5a7a9a", "#5a7a9a"
PRIMARY, SUCCESS, WARNING, DANGER = "#4a9eff", "#1fb86e", "#d98e00", "#e05252"

TABS = [
    {"id": "design",     "label": "Results"},
    {"id": "optimizer",  "label": "Optimizer", "badge": "AI"},
    {"id": "components", "label": "Components"},
    {"id": "materials",  "label": "Materials"},
    {"id": "checks",     "label": "Checks"},
]


def fmt_kpi(v, dp):
    if v is None:
        return "—"
    try:
        return f"{float(v):.{dp}f}"
    except (TypeError, ValueError):
        return "—"


class ColHeader(QFrame):
    """Direct port of the JSX's shared ColHeader -- every column in the
    real app uses this same small component; mirroring that consistency
    here rather than four different ad-hoc headers."""

    def __init__(self, label, sub=None, action=None, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        self.setStyleSheet(f"background-color: {PANEL}; border-bottom: 1px solid {BORDER};")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        text_box = QHBoxLayout()
        text_box.setSpacing(7)
        lbl = QLabel(label.upper())
        lbl.setStyleSheet(f"color: {TEXT3}; font-size: 9.5px; font-weight: 700; letter-spacing: 1px;")
        text_box.addWidget(lbl)
        if sub:
            sub_lbl = QLabel(sub)
            sub_lbl.setStyleSheet(f"color: {MUTED}; font-size: 8.5px;")
            text_box.addWidget(sub_lbl)
        layout.addLayout(text_box)
        layout.addStretch()
        if action:
            layout.addWidget(action)


class Placeholder(QWidget):
    """An honest, labeled gap -- not a fake implementation. Each of these
    is a TODO with the exact JSX source named, so it's obvious what to
    port next and where it goes."""

    def __init__(self, title, source_file, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {BG};")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon = QLabel("○")
        icon.setStyleSheet(f"color: {BORDER}; font-size: 28px;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"color: {TEXT3}; font-size: 13px; font-weight: 600;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        source_lbl = QLabel(f"not yet ported  ·  {source_file}")
        source_lbl.setStyleSheet(f"color: {MUTED}; font-size: 10px;")
        source_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for w in (icon, title_lbl, source_lbl):
            layout.addWidget(w)


class TabPill(QPushButton):
    def __init__(self, label, badge=None, parent=None):
        super().__init__(label, parent)
        self.setCheckable(True)
        self.badge = badge
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_style()

    def setChecked(self, checked):
        super().setChecked(checked)
        self._apply_style()

    def _apply_style(self):
        if self.isChecked():
            self.setStyleSheet(f"""
                QPushButton {{ background-color: {PANEL}; color: {TEXT}; border: none;
                    border-radius: 999px; padding: 6px 14px; font-size: 11.5px; font-weight: 600; }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{ background-color: transparent; color: {TEXT3}; border: none;
                    border-radius: 999px; padding: 6px 14px; font-size: 11.5px; }}
                QPushButton:hover {{ color: {TEXT2}; }}
            """)


class TopNav(QFrame):
    """Logo + tab pills + Q/P/v KPI chips + Save/Load -- the ONE place
    these performance numbers live. Deliberately not repeated anywhere
    inside the Results tab's content (see ElevationView's own docstring
    for why that duplication was removed)."""

    def __init__(self, on_tab_changed, parent=None):
        super().__init__(parent)
        self.on_tab_changed = on_tab_changed
        self.setFixedHeight(52)
        self.setStyleSheet(f"background-color: {PANEL}; border-bottom: 1px solid {BORDER};")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(14)

        # Brand
        brand_icon = QLabel("⛏")
        brand_icon.setFixedSize(28, 28)
        brand_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_icon.setStyleSheet(
            f"background-color: rgba(74,158,255,.12); border: 1px solid rgba(74,158,255,.3); "
            f"border-radius: 6px; color: {PRIMARY}; font-size: 13px;"
        )
        layout.addWidget(brand_icon)
        brand_box = QVBoxLayout(); brand_box.setSpacing(0)
        title = QLabel("Bucket Elevator")
        title.setStyleSheet(f"color: {TEXT}; font-size: 12px; font-weight: 700;")
        sub = QLabel("VECTOMEC™ · CEMA 375")
        sub.setStyleSheet(f"color: {TEXT3}; font-size: 9px;")
        brand_box.addWidget(title); brand_box.addWidget(sub)
        layout.addLayout(brand_box)

        # Tab pills
        pill_bar = QFrame()
        pill_bar.setStyleSheet(f"background-color: {BG}; border: 1px solid {BORDER}; border-radius: 999px;")
        pill_layout = QHBoxLayout(pill_bar)
        pill_layout.setContentsMargins(3, 3, 3, 3)
        pill_layout.setSpacing(2)
        self.pills = {}
        for t in TABS:
            pill = TabPill(t["label"])
            pill.clicked.connect(lambda checked, tid=t["id"]: self._select_tab(tid))
            pill_layout.addWidget(pill)
            self.pills[t["id"]] = pill
        self.pills["design"].setChecked(True)
        layout.addWidget(pill_bar)

        layout.addStretch()

        # KPI chips (Q / P / v) -- the one and only place these appear
        self.kpi_labels = {}
        for label, unit in (("Q", "t/h"), ("P", "kW"), ("v", "m/s")):
            chip = QFrame()
            chip.setStyleSheet(f"background-color: {PANEL2}; border: 1px solid {BORDER}; border-radius: 5px;")
            chip_layout = QVBoxLayout(chip)
            chip_layout.setContentsMargins(7, 3, 7, 3)
            chip_layout.setSpacing(0)
            lbl = QLabel(label.upper())
            lbl.setStyleSheet(f"color: {MUTED}; font-size: 8.5px; font-weight: 600;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val = QLabel("—")
            val.setStyleSheet(f"color: {TEXT3}; font-size: 13px; font-weight: 700;")
            val.setAlignment(Qt.AlignmentFlag.AlignCenter)
            unit_lbl = QLabel(unit)
            unit_lbl.setStyleSheet(f"color: {MUTED}; font-size: 8.5px;")
            unit_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chip_layout.addWidget(lbl); chip_layout.addWidget(val); chip_layout.addWidget(unit_lbl)
            layout.addWidget(chip)
            self.kpi_labels[label] = val

        save_btn = QPushButton("💾 Save / Load")
        save_btn.setStyleSheet(
            f"background-color: {PANEL2}; color: {TEXT2}; border: 1px solid {BORDER}; "
            f"border-radius: 5px; padding: 6px 12px; font-size: 11px;"
        )
        layout.addWidget(save_btn)

    def _select_tab(self, tab_id):
        for tid, pill in self.pills.items():
            pill.setChecked(tid == tab_id)
        self.on_tab_changed(tab_id)

    def update_kpis(self, results):
        r = results or {}
        self.kpi_labels["Q"].setText(fmt_kpi(r.get("Q"), 0))
        self.kpi_labels["P"].setText(fmt_kpi(r.get("P_total"), 1))
        self.kpi_labels["v"].setText(fmt_kpi(r.get("v"), 2))
        for key, color in (("Q", SUCCESS), ("P", WARNING), ("v", PRIMARY)):
            if r.get({"Q": "Q", "P": "P_total", "v": "v"}[key]) is not None:
                self.kpi_labels[key].setStyleSheet(f"color: {color}; font-size: 13px; font-weight: 700;")


class ShellWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VECTRIX™ -- Bucket Elevator (PySide6 shell)")
        self.resize(1400, 860)
        self.setStyleSheet(f"background-color: {BG};")

        self.top_nav = TopNav(on_tab_changed=self._on_tab_changed)

        # ── Column 1: Equipment Tree -- INTEGRATED ──────────────────────
        col1 = QWidget()
        col1.setFixedWidth(200)
        col1_layout = QVBoxLayout(col1)
        col1_layout.setContentsMargins(0, 0, 0, 0)
        col1_layout.setSpacing(0)
        col1_layout.addWidget(ColHeader("Equipment", "BE-001"))
        self.tree_panel = EquipmentTreePanel(show_detail=False)
        col1_layout.addWidget(self.tree_panel)
        col1.setStyleSheet(f"border-right: 1px solid {BORDER};")

        # ── Column 2: Parameters -- NOT YET PORTED ──────────────────────
        col2 = QWidget()
        col2.setFixedWidth(280)
        col2_layout = QVBoxLayout(col2)
        col2_layout.setContentsMargins(0, 0, 0, 0)
        col2_layout.setSpacing(0)
        col2_layout.addWidget(ColHeader("Parameters", "CEMA 375 Inputs"))
        col2_layout.addWidget(Placeholder("Parameters", "InputSidebar.jsx"))
        col2.setStyleSheet(f"border-right: 1px solid {BORDER};")

        # ── Column 3: tab-driven middle content ─────────────────────────
        col3 = QWidget()
        col3_layout = QVBoxLayout(col3)
        self.col3_layout = col3_layout   # stored directly -- see _on_tab_changed
        col3_layout.setContentsMargins(0, 0, 0, 0)
        col3_layout.setSpacing(0)
        self.col3_header = ColHeader("Results")
        col3_layout.addWidget(self.col3_header)
        self.middle_stack = QStackedWidget()
        self.elevation = ElevationView()                                    # INTEGRATED
        self.middle_stack.addWidget(self.elevation)                          # "design" (index 0)
        self.middle_stack.addWidget(Placeholder("Optimizer", "OptimizerPanel.jsx"))      # index 1
        self.middle_stack.addWidget(Placeholder("Components", "ComponentPanel.jsx"))     # index 2
        self.middle_stack.addWidget(Placeholder("Materials", "MaterialLibraryPanel.jsx"))# index 3
        self.middle_stack.addWidget(Placeholder("Checks", "ChecksPanel.jsx / RootCausePanel.jsx"))  # index 4
        col3_layout.addWidget(self.middle_stack)
        col3.setStyleSheet(f"border-right: 1px solid {BORDER};")

        # ── Column 4: Status -- NOT YET PORTED ───────────────────────────
        col4 = QWidget()
        col4.setFixedWidth(260)
        col4_layout = QVBoxLayout(col4)
        col4_layout.setContentsMargins(0, 0, 0, 0)
        col4_layout.setSpacing(0)
        col4_layout.addWidget(ColHeader("Status"))
        col4_layout.addWidget(Placeholder("Design Review", "DesignReview.jsx / KpiGrid.jsx"))

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        for col in (col1, col2, col3, col4):
            body_layout.addWidget(col)
        body_layout.setStretchFactor(col3, 1)   # only the middle column grows

        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self.top_nav)
        outer.addWidget(body)
        self.setCentralWidget(container)

        self._tab_index = {"design": 0, "optimizer": 1, "components": 2, "materials": 3, "checks": 4}
        self._tab_label = {"design": "Results", "optimizer": "Optimizer", "components": "Components",
                            "materials": "Materials", "checks": "Checks"}

    def _on_tab_changed(self, tab_id):
        self.middle_stack.setCurrentIndex(self._tab_index[tab_id])
        # Rebuild the header with the right label -- ColHeader has no
        # update-in-place method yet, simplest correct thing is to replace it.
        # FIX (Pylance reportOptionalMemberAccess): this used to fetch the
        # layout via self.middle_stack.parentWidget().layout() -- parentWidget()
        # is typed Optional[QWidget] in Qt's stubs (a widget genuinely might
        # not have a parent at call time, even though this one always does
        # by construction), so .layout() on it was a real, not just
        # type-checker-only, gap. Using the layout reference stored directly
        # in __init__ removes the Optional entirely instead of asserting past it.
        new_header = ColHeader(self._tab_label[tab_id])
        self.col3_layout.replaceWidget(self.col3_header, new_header)
        self.col3_header.deleteLater()
        self.col3_header = new_header

    def run_calculation(self):
        payload = {
            "Q_req": 100, "H_m": 25, "mat_id": "clinker",
            "auto_bucket": False, "bucket_id": "AC_12x8",
            "D_mm": 500, "n_rpm": 70,
        }
        results = fetch_design(payload)        # ONE fetch
        self.top_nav.update_kpis(results)       # ...feeds the KPI chips
        self.elevation.set_data(payload, results)    # ...feeds the Results tab
        self.tree_panel.set_data(payload, results)   # ...feeds the Equipment Tree


def main():
    app = QApplication(sys.argv)
    window = ShellWindow()
    window.run_calculation()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()