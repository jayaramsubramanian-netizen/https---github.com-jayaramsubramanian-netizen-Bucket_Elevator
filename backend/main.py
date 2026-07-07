"""
main.py -- VECTRIX™ desktop app entry point, modeled on BucketElevatorPage.jsx
═══════════════════════════════════════════════════════════════════════════
THIS is the file to run and keep upgrading -- not equipment_tree_poc.py,
elevation_view_poc.py, or combined_shell_example.py.

FIXES this round (a real Windows screenshot still showed square-ish tab
pills after the previous app.setStyle("Fusion") fix): the previous attempt
used border-radius: 999px relying on it always exceeding half the
button's actual rendered height. That depends on the button's real height
being small and fixed -- here height was only ever a side-effect of
padding, not a literal setFixedHeight(), so the radius-vs-height
relationship the QSS engine actually rasterizes against wasn't as
predictable as intended. Every pill-shaped button (tab buttons, the
"Bucket Elevator" dropdown button, the module-switcher pills, the PDF
Report button) now gets an explicit setFixedHeight() plus a border-radius
set to exactly half that height -- the geometrically guaranteed way to
get a true stadium shape, rather than relying on a radius-larger-than-
the-box shortcut. border-style/border-width are also spelled out
longhand (rather than the border: none shorthand) to remove any chance
of a stylesheet parser treating the shorthand differently from the
explicit properties.
"""
import sys

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QStackedWidget, QMenu, QSplitter,
    QFileDialog, QMessageBox, QScrollArea,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QAction

from theme import (
    BG, PANEL, PANEL2, BORDER, TEXT, TEXT2, TEXT3, MUTED, PRIMARY,
    SUCCESS, WARNING, DANGER, BRAND_RED,
)
from api_client import fetch_design, download_pdf_report
from components.dialog_helpers import KPIChip, styled_message_box
from components import (
    ElevationView, EquipmentTreePanel, InputSidebarPanel, StatusPanel, OptimizerPanel,
    BomPanel, StatusDesignLeaves, MaintenancePanel, ChecksPanel, DesignReviewPanel,
    MaterialLibraryPanel, ChartsPanel,
)

TABS = [
    {"id": "design",     "label": "Results"},
    {"id": "optimizer",  "label": "Optimizer", "badge": "AI"},
    {"id": "checks",     "label": "Checks", "failBadge": True},
    {"id": "components", "label": "Components"},
    {"id": "maintenance","label": "Maintenance"},
    {"id": "materials",  "label": "Materials"},
]

TAB_PILL_HEIGHT = 34
TAB_PILL_RADIUS = TAB_PILL_HEIGHT // 2
MODULE_PILL_HEIGHT = 30
MODULE_PILL_RADIUS = MODULE_PILL_HEIGHT // 2


def fmt_kpi(v, dp):
    if v is None:
        return "—"
    try:
        return f"{float(v):.{dp}f}"
    except (TypeError, ValueError):
        return "—"


class ColHeader(QFrame):
    """Direct port of the JSX's shared ColHeader -- every column in the
    real app uses this same small component."""

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


def fail_warn_badges(n_fail, n_warn):
    """Small FAIL/WARN pill row -- port of the JSX's inline badge markup
    that appears in the middle column's ColHeader action slot when on the
    Results tab."""
    box = QWidget()
    layout = QHBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(5)
    if n_fail > 0:
        lbl = QLabel(f"{n_fail} FAIL")
        lbl.setStyleSheet(
            f"background-color: rgba(224,82,82,.12); color: {DANGER}; border: 1px solid rgba(224,82,82,.3); "
            f"border-radius: 999px; padding: 2px 7px; font-size: 8.5px; font-weight: 700;"
        )
        layout.addWidget(lbl)
    if n_warn > 0:
        lbl = QLabel(f"{n_warn} WARN")
        lbl.setStyleSheet(
            f"background-color: rgba(217,142,0,.12); color: {WARNING}; border: 1px solid rgba(217,142,0,.3); "
            f"border-radius: 999px; padding: 2px 7px; font-size: 8.5px; font-weight: 700;"
        )
        layout.addWidget(lbl)
    return box


class Placeholder(QWidget):
    """An honest, labeled gap -- not a fake implementation."""

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


class ModulePill(QPushButton):
    """One module switcher button in the platform title bar (Bucket
    Elevator / Screw Conveyor). Active module gets the solid primary
    fill; everything else (e.g. Screw Conveyor) is an honest, visibly-
    disabled placeholder rather than a button that looks clickable but
    does nothing.

    FIX: setFixedHeight(MODULE_PILL_HEIGHT) + an exact-half border-radius,
    same reasoning as NavTabButton below -- a true stadium shape needs a
    known, fixed height to compute the matching radius against, not a
    radius value assumed to always exceed whatever height padding alone
    produces."""

    def __init__(self, icon, label, badge=None, active=False, enabled=True, parent=None):
        super().__init__(parent)
        self.setText(f"{icon}  {label}" + (f"   " if badge else ""))
        self.active = active
        self.setEnabled(enabled)
        self.setFixedHeight(MODULE_PILL_HEIGHT)
        if not enabled:
            self.setToolTip(f"{label} is a separate application, not part of this codebase yet")
        if active:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {PRIMARY}; color: white;
                    border-style: none; border-width: 0px;
                    border-radius: {MODULE_PILL_RADIUS}px;
                    padding: 0px 14px; font-size: 12px; font-weight: 600;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent; color: {TEXT3};
                    border-style: none; border-width: 0px;
                    border-radius: {MODULE_PILL_RADIUS}px;
                    padding: 0px 14px; font-size: 12px;
                }}
                QPushButton:disabled {{ color: {MUTED}; }}
                QPushButton:hover:!disabled {{ color: {TEXT2}; }}
            """)
        if badge:
            self.setText(f"{icon}  {label}")
            self._badge_text = badge


class AppTitleBar(QFrame):
    """Platform-level title bar -- VECTRIX™ branding + module switcher
    (Bucket Elevator / Screw Conveyor) + PDF Report + version."""

    def __init__(self, on_tab_changed=None, on_pdf_clicked=None, parent=None):
        super().__init__(parent)
        self.on_pdf_clicked = on_pdf_clicked
        self.setFixedHeight(48)
        self.setStyleSheet(f"background-color: {PANEL}; border-bottom: 1px solid {BORDER};")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(14)

        icon = QLabel("⚙")
        icon.setFixedSize(30, 30)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(
            f"background-color: {BRAND_RED}; border-radius: 7px; color: white; font-size: 15px;"
        )
        layout.addWidget(icon)

        brand_box = QVBoxLayout(); brand_box.setSpacing(0)
        brand_title = QLabel("VECTRIX™")
        brand_title.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: 700;")
        brand_sub = QLabel("DESIGN PLATFORM")
        brand_sub.setStyleSheet(f"color: {TEXT3}; font-size: 8px; font-weight: 600; letter-spacing: 1px;")
        brand_box.addWidget(brand_title); brand_box.addWidget(brand_sub)
        layout.addLayout(brand_box)

        module_bar = QFrame()
        module_bar.setStyleSheet(f"background-color: {BG}; border: 1px solid {BORDER}; border-radius: 999px;")
        module_layout = QHBoxLayout(module_bar)
        module_layout.setContentsMargins(3, 3, 3, 3)
        module_layout.setSpacing(2)

        be_pill = ModulePill("⛏", "Bucket Elevator", badge="VECTOMEC™", active=True)
        module_layout.addWidget(be_pill)
        badge_lbl = QLabel("VECTOMEC™")
        badge_lbl.setStyleSheet(
            f"background-color: rgba(255,255,255,.18); color: white; border-radius: 999px; "
            f"padding: 2px 8px; font-size: 8.5px; font-weight: 700; margin-left: -8px;"
        )
        module_layout.addWidget(badge_lbl)

        sc_pill = ModulePill("🌀", "Screw Conveyor", active=False, enabled=False)
        module_layout.addWidget(sc_pill)
        layout.addWidget(module_bar)

        layout.addStretch()

        pdf_btn = QPushButton("⬇  PDF Report")
        pdf_btn.setFixedHeight(MODULE_PILL_HEIGHT)
        pdf_btn.setStyleSheet(
            f"background-color: {PANEL2}; color: {TEXT2}; "
            f"border-style: solid; border-width: 1px; border-color: {BORDER}; "
            f"border-radius: {MODULE_PILL_RADIUS}px; padding: 0px 14px; font-size: 11.5px; font-weight: 600;"
        )
        pdf_btn.clicked.connect(lambda: self.on_pdf_clicked() if self.on_pdf_clicked else None)
        layout.addWidget(pdf_btn)

        version_lbl = QLabel("AKSHAYVIPRA EL-MEC · V1.0")
        version_lbl.setStyleSheet(f"color: {TEXT3}; font-size: 10.5px; font-weight: 600; letter-spacing: .5px;")
        layout.addWidget(version_lbl)


class NavTabButton(QPushButton):
    """A tab button hosted in the top nav bar.

    FIX (this round): a real Windows screenshot still showed square-ish
    pills even after app.setStyle("Fusion") and removing setFlat(True).
    The remaining cause: border-radius: 999px was relied on to always
    exceed half the actual rendered height, but height here was only
    ever a side-effect of padding -- never a literal fixed value the
    radius was computed against. Now setFixedHeight(TAB_PILL_HEIGHT) is
    set explicitly and the radius is exactly half of it, the
    geometrically guaranteed way to get a true stadium shape. border-
    style/border-width are spelled out longhand rather than the
    `border: none` shorthand, removing any chance of a shorthand-vs-
    longhand parsing inconsistency in the stylesheet engine."""

    def __init__(self, label, parent=None):
        super().__init__(label, parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(TAB_PILL_HEIGHT)
        self._apply_style()

    def setChecked(self, checked):
        super().setChecked(checked)
        self._apply_style()

    def _apply_style(self):
        if self.isChecked():
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {PRIMARY}; color: white;
                    border-style: none; border-width: 0px;
                    border-radius: {TAB_PILL_RADIUS}px;
                    padding: 0px 16px; font-size: 12.5px; font-weight: 600;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent; color: {TEXT3};
                    border-style: none; border-width: 0px;
                    border-radius: {TAB_PILL_RADIUS}px;
                    padding: 0px 16px; font-size: 12.5px;
                }}
                QPushButton:hover {{ background-color: {PANEL2}; color: {TEXT2}; }}
            """)


class TopNav(QFrame):
    """Page-level bar: a "Bucket Elevator" dropdown with standard window
    functions, the tab pills, plus Q/P/v KPI chips.

    FIX (earlier round, still in effect): the bar was a hard 40px with
    KPI chips squeezed into the same 2px spacing as the tab buttons.
    Now 56px tall, and the three KPI chips get their own sub-layout with
    real spacing (8px) and larger type, independent of the tighter
    spacing the tab row still uses.

    FIX (earlier round, still documented here): QMenuBar.addWidget()
    doesn't actually exist (confirmed: dir(QMenuBar) only has
    addAction/addActions/addMenu/addSeparator). This version uses only
    patterns confirmed to render correctly: QPushButton.setMenu() for
    the one real dropdown, plain QPushButtons for everything else.
    """

    def __init__(self, on_tab_changed, parent=None):
        super().__init__(parent)
        self.on_tab_changed = on_tab_changed
        self.setFixedHeight(76)
        self.setStyleSheet(f"background-color: {PANEL}; border-bottom: 1px solid {BORDER};")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        menu_qss = f"""
            QMenu {{ background-color: {PANEL2}; color: {TEXT2}; border: 1px solid {BORDER};
                border-radius: 8px; padding: 4px; }}
            QMenu::item {{ padding: 6px 24px 6px 14px; border-radius: 5px; font-size: 12px; }}
            QMenu::item:selected {{ background-color: {PRIMARY}; color: white; }}
            QMenu::separator {{ height: 1px; background-color: {BORDER}; margin: 4px 8px; }}
        """

        app_btn = QPushButton("Bucket Elevator  ▾")
        app_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        app_btn.setFixedHeight(TAB_PILL_HEIGHT)
        app_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent; color: {TEXT2};
                border-style: none; border-width: 0px;
                border-radius: {TAB_PILL_RADIUS}px;
                padding: 0px 16px; font-size: 12.5px; font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {PANEL2}; }}
            QPushButton::menu-indicator {{ image: none; }}
        """)
        app_menu = QMenu(app_btn)
        app_menu.setStyleSheet(menu_qss)
        act_min = QAction("Minimize", self)
        act_min.triggered.connect(lambda: self.window().showMinimized())
        app_menu.addAction(act_min)
        self.act_maximize = QAction("Maximize", self)
        self.act_maximize.triggered.connect(self._toggle_maximize)
        app_menu.addAction(self.act_maximize)
        app_menu.addSeparator()
        act_open = QAction("Open Design...", self)
        act_open.setShortcut("Ctrl+O")
        act_open.triggered.connect(lambda: self._not_yet_wired("Open Design"))
        app_menu.addAction(act_open)
        act_save = QAction("Save Design", self)
        act_save.setShortcut("Ctrl+S")
        act_save.triggered.connect(lambda: self._not_yet_wired("Save Design"))
        app_menu.addAction(act_save)
        act_save_as = QAction("Save Design As...", self)
        act_save_as.triggered.connect(lambda: self._not_yet_wired("Save Design As"))
        app_menu.addAction(act_save_as)
        app_menu.addSeparator()
        act_exit = QAction("Exit", self)
        act_exit.setShortcut("Ctrl+Q")
        act_exit.triggered.connect(lambda: self.window().close())
        app_menu.addAction(act_exit)
        app_btn.setMenu(app_menu)
        self._app_menu = app_menu
        layout.addWidget(app_btn)

        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"background-color: {BORDER};")
        layout.addWidget(sep)

        self.tab_buttons = {}
        for t in TABS:
            label = t["label"]
            if t.get("badge"):
                label = f"{label}  ·{t['badge']}"
            btn = NavTabButton(label)
            btn.clicked.connect(lambda checked, tid=t["id"]: self._select_tab(tid))
            layout.addWidget(btn)
            self.tab_buttons[t["id"]] = btn
        self.tab_buttons["design"].setChecked(True)

        layout.addStretch()

        # FIX (Jay, third pass on this specific complaint): previous
        # rounds increased padding/spacing but kept the same basic chip
        # proportions -- confirmed against a real screenshot that 279 /
        # 25.0 / 1.83 were still hard to read at a glance. This is a
        # genuinely bigger change, not an incremental nudge: value text
        # nearly 50% larger (22px vs 15px) and bold, a fixed minimum
        # FIX (this round, see KPIChip class above for the full reasoning):
        # replaced the QFrame + 3-stacked-QLabel chip with a single
        # custom-painted widget -- no box-in-a-box, label and unit are
        # small corner marks around one large centered value, drawn
        # directly with QPainter instead of QSS-styled QLabels.
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(10)
        self.kpi_chips = {}
        for label, unit in (("Q", "t/h"), ("P", "kW"), ("v", "m/s")):
            chip = KPIChip(label, unit)
            kpi_row.addWidget(chip)
            self.kpi_chips[label] = chip
        layout.addLayout(kpi_row)

    def _toggle_maximize(self):
        win = self.window()
        if win.isMaximized():
            win.showNormal()
            self.act_maximize.setText("Maximize")
        else:
            win.showMaximized()
            self.act_maximize.setText("Restore")

    def _not_yet_wired(self, action_name):
        print(f"[{action_name}] not yet wired -- no save/load format designed yet.")

    def _select_tab(self, tab_id):
        for tid, btn in self.tab_buttons.items():
            btn.setChecked(tid == tab_id)
        self.on_tab_changed(tab_id)

    def update_kpis(self, results):
        """Capacity color reads results["cap_ok"] directly (already
        computed by the backend, a straight Q >= Q_req check in
        calculations.py) -- per the architecture rule that the frontend
        never duplicates engineering checks. P and v don't have an
        equivalent required-vs-actual concept in the backend, so they
        keep their original fixed categorical colors. set_value() handles
        both the text and the border/value color in one call now -- no
        separate accent step needed since KPIChip paints its own border."""
        r = results or {}
        if r.get("Q") is not None:
            cap_ok = r.get("cap_ok")
            q_color = SUCCESS if cap_ok else (DANGER if cap_ok is False else TEXT3)
            self.kpi_chips["Q"].set_value(fmt_kpi(r.get("Q"), 0), q_color)
        if r.get("P_total") is not None:
            self.kpi_chips["P"].set_value(fmt_kpi(r.get("P_total"), 1), WARNING)
        if r.get("v") is not None:
            self.kpi_chips["v"].set_value(fmt_kpi(r.get("v"), 2), PRIMARY)

    def update_fail_badge(self, n_fail):
        base = next(t["label"] for t in TABS if t["id"] == "checks")
        text = f"{base}  ·{n_fail}" if n_fail > 0 else base
        self.tab_buttons["checks"].setText(text)
        self.tab_buttons["checks"]._apply_style()


class _PdfReportWorker(QThread):
    """Background thread for the PDF report endpoint -- confirmed ~1-3s
    real call, not instant, so runs off the GUI thread same as every other
    network call in this codebase."""
    done = Signal(str)
    errorOccurred = Signal(str)
    def __init__(self, results, inputs, save_path, parent=None):
        super().__init__(parent)
        self.results, self.inputs, self.save_path = results, inputs, save_path
    def run(self):
        try:
            path = download_pdf_report(self.results, self.inputs, self.save_path)
            self.done.emit(path)
        except Exception as e:
            self.errorOccurred.emit(str(e))


class ShellWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VECTRIX™ -- Bucket Elevator")
        self.resize(1400, 860)
        self.setStyleSheet(f"background-color: {BG};")

        self.app_title_bar = AppTitleBar(on_pdf_clicked=self._on_pdf_clicked)
        self.top_nav = TopNav(on_tab_changed=self._on_tab_changed)

        col1 = QWidget()
        col1_layout = QVBoxLayout(col1)
        col1_layout.setContentsMargins(0, 0, 0, 0)
        col1_layout.setSpacing(0)
        col1_layout.addWidget(ColHeader("Equipment", "BE-001"))
        self.tree_panel = EquipmentTreePanel(show_detail=False, popup_on_click=True)
        col1_layout.addWidget(self.tree_panel)

        col2 = QWidget()
        col2_layout = QVBoxLayout(col2)
        col2_layout.setContentsMargins(0, 0, 0, 0)
        col2_layout.setSpacing(0)
        col2_layout.addWidget(ColHeader("Parameters", "CEMA 375 Inputs"))
        self.input_sidebar = InputSidebarPanel()
        self.input_sidebar.inputsChanged.connect(self.run_calculation)
        col2_layout.addWidget(self.input_sidebar)

        col3 = QWidget()
        col3_layout = QVBoxLayout(col3)
        col3_layout.setContentsMargins(0, 0, 0, 0)
        col3_layout.setSpacing(0)
        self.col3_layout = col3_layout
        self.col3_header = ColHeader("Results")
        col3_layout.addWidget(self.col3_header)
        self.middle_stack = QStackedWidget()

        # Results tab: elevation view + charts panel.
        # Wrapped in a QScrollArea so neither the elevation schematic nor the
        # charts are clipped when the window height is short -- direct user
        # feedback: "elevator schematic section does not scroll, making this
        # section be at the very bottom of the page". The internal splitter
        # remains flexible so the user can still resize the elevation/chart
        # proportion. The scroll area only activates when content overflows.
        results_scroll = QScrollArea()
        results_scroll.setWidgetResizable(True)
        results_scroll.setStyleSheet("QScrollArea{border:none;}")
        results_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        results_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        results_inner = QWidget()
        results_inner_layout = QVBoxLayout(results_inner)
        results_inner_layout.setContentsMargins(0, 0, 0, 0)
        results_inner_layout.setSpacing(0)

        results_splitter = QSplitter(Qt.Orientation.Vertical)
        results_splitter.setStyleSheet(
            f"QSplitter::handle{{background:{BORDER};height:4px;}}"
            f"QSplitter::handle:hover{{background:{PRIMARY};}}"
        )
        self.elevation = ElevationView()
        self.elevation.setMinimumHeight(300)
        results_splitter.addWidget(self.elevation)
        self.charts_panel = ChartsPanel()
        self.charts_panel.setMinimumHeight(300)
        results_splitter.addWidget(self.charts_panel)
        results_splitter.setStretchFactor(0, 55)
        results_splitter.setStretchFactor(1, 45)
        results_splitter.setSizes([420, 340])

        results_inner_layout.addWidget(results_splitter)
        results_scroll.setWidget(results_inner)
        self.middle_stack.addWidget(results_scroll)
        self.optimizer_panel = OptimizerPanel(on_apply=self._on_optimizer_apply)
        self.middle_stack.addWidget(self.optimizer_panel)
        self.checks_panel = ChecksPanel(on_apply_correction=self._on_apply_correction)
        self.middle_stack.addWidget(self.checks_panel)
        self.bom_panel = BomPanel()
        self.middle_stack.addWidget(self.bom_panel)
        self.maintenance_panel = MaintenancePanel()
        self.middle_stack.addWidget(self.maintenance_panel)
        self.material_library_panel = MaterialLibraryPanel()
        self.middle_stack.addWidget(self.material_library_panel)
        col3_layout.addWidget(self.middle_stack)

        col4 = QWidget()
        col4_layout = QVBoxLayout(col4)
        col4_layout.setContentsMargins(0, 0, 0, 0)
        col4_layout.setSpacing(0)
        col4_layout.addWidget(ColHeader("Status"))
        # FIX (direct instruction, this round): Status content is tab-aware.
        # KpiGrid (status_panel.py) for Results/Optimizer/Maintenance/
        # Materials -- the universal prior default, only ever asked to
        # diverge for specific tabs. StatusDesignLeaves for Components.
        # DesignReviewPanel (this round, new) for Checks -- "add the
        # Design Review elements from the jsx to the status section when
        # in the checks tab."
        self.status_stack = QStackedWidget()
        self.status_panel = StatusPanel()
        self.status_stack.addWidget(self.status_panel)          # index 0 -- KpiGrid
        self.status_leaves = StatusDesignLeaves()
        self.status_stack.addWidget(self.status_leaves)          # index 1 -- BOM design leaves
        self.design_review_panel = DesignReviewPanel()
        self.status_stack.addWidget(self.design_review_panel)    # index 2 -- Design Review
        col4_layout.addWidget(self.status_stack)
        self._status_view_for_tab = {
            "design": 0, "optimizer": 0, "components": 1,
            "maintenance": 0, "materials": 0, "checks": 2,
        }

        body = QSplitter(Qt.Orientation.Horizontal)
        body.setStyleSheet(f"""
            QSplitter::handle {{ background-color: {BORDER}; }}
            QSplitter::handle:hover {{ background-color: {PRIMARY}; }}
        """)
        body.setHandleWidth(2)
        for col in (col1, col2, col3, col4):
            body.addWidget(col)
        body.setSizes([200, 280, 700, 260])
        body.setStretchFactor(0, 0)
        body.setStretchFactor(1, 0)
        body.setStretchFactor(2, 1)
        body.setStretchFactor(3, 0)

        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self.app_title_bar)
        outer.addWidget(self.top_nav)
        outer.addWidget(body)
        self.setCentralWidget(container)

        self._tab_index = {"design": 0, "optimizer": 1, "checks": 2, "components": 3, "maintenance": 4, "materials": 5}
        self._tab_label = {"design": "Results", "optimizer": "Optimizer", "checks": "Checks",
                            "components": "Components", "maintenance": "Maintenance", "materials": "Materials"}
        self._last_results = {}
        self._default_payload = {
            "Q_req": 100, "H_m": 25, "mat_id": "clinker",
            "auto_bucket": False, "bucket_id": "AC_12x8",
            "D_mm": 500, "n_rpm": 70, "fill_pct": 75,
        }

    def _on_tab_changed(self, tab_id):
        self.middle_stack.setCurrentIndex(self._tab_index[tab_id])
        self.status_stack.setCurrentIndex(self._status_view_for_tab.get(tab_id, 0))
        action = fail_warn_badges(*self._fail_warn(self._last_results)) if tab_id == "design" else None
        new_header = ColHeader(self._tab_label[tab_id], action=action)
        self.col3_layout.replaceWidget(self.col3_header, new_header)
        self.col3_header.deleteLater()
        self.col3_header = new_header

    @staticmethod
    def _fail_warn(results):
        checks = (results or {}).get("checks", []) or []
        n_fail = sum(1 for c in checks if c.get("type") == "fail")
        n_warn = sum(1 for c in checks if c.get("type") == "warn")
        return n_fail, n_warn

    def run_calculation(self, payload=None):
        """Run a full recalculation and push results to every panel.

        Wrapped in try/except -- any error (HTTP 4xx from invalid inputs,
        backend 5xx, network drop, or a panel set_data crash) is caught here
        and shown to the user as a non-fatal error banner instead of killing
        the window. The previous result is kept so the user can still read
        what they last successfully calculated.

        The specific crash that prompted this fix: bucket_gap spinbox emitting
        an intermediate value mid-edit sent a 422 Unprocessable Entity from
        Pydantic validation, fetch_design() called resp.raise_for_status(),
        the resulting HTTPError propagated through the call stack with no
        catch, and Qt terminated the main window's event loop on the unhandled
        exception. The backend was healthy (200 OK logged for other requests);
        the crash was entirely in the client-side exception path."""
        if payload is None:
            payload = self._default_payload
        try:
            results = fetch_design(payload)
        except Exception as e:
            # Show the error in the col3 header area and return early,
            # keeping _last_results / _default_payload from the previous
            # successful calculation so the user can still read the UI.
            err_msg = str(e)
            if "422" in err_msg or "Unprocessable" in err_msg:
                user_msg = f"Validation error — check input values ({err_msg[:120]})"
            elif "ConnectionError" in type(e).__name__ or "Connection" in err_msg:
                user_msg = "Cannot reach backend — is the server running on port 8000?"
            else:
                user_msg = f"Calculation error: {err_msg[:200]}"
            # Replace the col3 header temporarily with an error notice
            err_header = ColHeader(f"⚠  {user_msg[:80]}")
            err_header.setStyleSheet(
                f"background-color: rgba(224,82,82,.12); border-bottom: 1px solid rgba(224,82,82,.35);"
                f"color: #e05252;"
            )
            self.col3_layout.replaceWidget(self.col3_header, err_header)
            self.col3_header.deleteLater()
            self.col3_header = err_header
            return

        self._last_results = results
        self._default_payload = payload
        try:
            self.top_nav.update_kpis(results)
            self.elevation.set_data(payload, results)
            self.charts_panel.set_data(payload, results)
            self.tree_panel.set_data(payload, results)
            self.input_sidebar.set_data(payload, results)
            self.bom_panel.set_data(payload, results)
            self.status_panel.set_data(payload, results)
            self.status_leaves.set_data(payload, results)
            self.maintenance_panel.set_data(payload, results)
            self.checks_panel.set_data(payload, results)
            self.design_review_panel.set_data(payload, results)
            self.material_library_panel.set_data(payload, results)
            self.optimizer_panel.set_data(payload, results)
        except Exception as e:
            import traceback
            traceback.print_exc()   # visible in the terminal for debugging
            # Non-fatal: results were saved, some panels may not have updated

        n_fail, n_warn = self._fail_warn(results)
        self.top_nav.update_fail_badge(n_fail)
        if self._tab_index_of_current() == "design":
            new_header = ColHeader("Results", action=fail_warn_badges(n_fail, n_warn))
            self.col3_layout.replaceWidget(self.col3_header, new_header)
            self.col3_header.deleteLater()
            self.col3_header = new_header

    def _on_optimizer_apply(self, variant):
        """Mirrors useElevatorCalc.js's applyOptimizer() exactly (read
        directly before writing this, not assumed): rpm -> n_rpm,
        fill -> fill_pct, auto_bucket forced False, and the v2-only
        fields (D_mm/boot_pulley_D_mm/chain_n_strands/sprocket teeth)
        only merged in when present -- a belt-mode result has no chain
        fields, and merging None over an existing value would clobber
        it rather than leave it untouched, same as the JSX's own
        `D_mm != null ? { D_mm } : {}` spread guards."""
        payload = dict(self._default_payload)
        payload["n_rpm"] = variant.get("rpm")
        payload["bucket_id"] = variant.get("bucket_id")
        payload["auto_bucket"] = False
        payload["fill_pct"] = variant.get("fill")
        for key in ("D_mm", "boot_pulley_D_mm", "chain_n_strands",
                    "chain_sprocket_teeth", "chain_boot_sprocket_teeth"):
            if variant.get(key) is not None:
                payload[key] = variant[key]
        self.run_calculation(payload)

    def _auto_pdf_filename(self):
        """Build the PDF filename from the VM model number -- the canonical
        identifier for this elevator configuration -- plus a timestamp."""
        r   = self._last_results or {}
        inp = self._default_payload or {}
        try:
            from api_client import fetch_model_number
            model_no = fetch_model_number(inp, r)
        except Exception:
            mat = str(inp.get("mat_id", "material")).capitalize()
            Q   = inp.get("Q_req", "")
            H   = inp.get("H_m", "")
            model_no = f"VM-BE_{mat}_{Q}tph_H{H}m"
        from datetime import datetime
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        return f"{model_no}_{stamp}.pdf"

    @staticmethod
    def _styled_message_box(icon, title, text, parent):
        return styled_message_box(icon, title, text, parent)

    def _on_pdf_clicked(self):
        """PDF Report button handler. Opens a save dialog, spins up a
        background worker, and updates the TopNav's version label with
        progress feedback while it runs -- same pattern as every other
        network-call button in this codebase."""
        if not self._last_results:
            self._styled_message_box(
                QMessageBox.Icon.Information, "No Results", "Run a calculation first.", self
            ).exec()
            return
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save PDF Report", self._auto_pdf_filename(), "PDF Files (*.pdf)"
        )
        if not save_path:
            return
        self._pdf_worker = _PdfReportWorker(
            self._last_results, self._default_payload, save_path, parent=self
        )
        self._pdf_worker.done.connect(self._on_pdf_done)
        self._pdf_worker.errorOccurred.connect(self._on_pdf_error)
        self._pdf_worker.start()
        # Update the version label to show progress
        for lbl in self.app_title_bar.findChildren(QLabel):
            if "EL-MEC" in (lbl.text() or ""):
                lbl.setText("Generating PDF…")
                self._pdf_version_lbl = lbl
                break

    def _on_pdf_done(self, path):
        if hasattr(self, "_pdf_version_lbl"):
            self._pdf_version_lbl.setText("AKSHAYVIPRA EL-MEC · V1.0")
        self._styled_message_box(
            QMessageBox.Icon.Information, "Report Saved", f"PDF saved to:\n{path}", self
        ).exec()

    def _on_pdf_error(self, msg):
        if hasattr(self, "_pdf_version_lbl"):
            self._pdf_version_lbl.setText("AKSHAYVIPRA EL-MEC · V1.0")
        self._styled_message_box(
            QMessageBox.Icon.Critical, "Report Failed", f"PDF generation failed:\n{msg}", self
        ).exec()

    def _on_apply_correction(self, param, value):
        """Mirrors RootCausePanel.jsx's setField(param, target) -- a
        single corrective param/value pair from a root-cause finding's
        Apply button gets merged directly into the live payload and
        recalculated, same pattern as _on_optimizer_apply just above but
        for one field instead of a whole variant."""
        payload = dict(self._default_payload)
        payload[param] = value
        self.run_calculation(payload)

    def _tab_index_of_current(self):
        idx = self.middle_stack.currentIndex()
        for tid, i in self._tab_index.items():
            if i == idx:
                return tid
        return "design"


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = ShellWindow()
    window.run_calculation()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()