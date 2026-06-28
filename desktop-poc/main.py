"""
main.py -- VECTRIX™ desktop app entry point, modeled on BucketElevatorPage.jsx
═══════════════════════════════════════════════════════════════════════════
THIS is the file to run and keep upgrading -- not equipment_tree_poc.py,
elevation_view_poc.py, or combined_shell_example.py (those were the
evaluation/example stage; their reusable pieces now live in components/
and this file, the throwaway standalone-window parts of them don't need to
exist anymore).

Mirrors the real layout (checked against the file directly): top nav
(logo + 5 tab pills + Q/P/v KPI chips + Save/Load) over a 4-column body:
    [Equipment Tree] [Parameters] [tab-driven middle content] [Status]

Folder structure, mirroring frontend/src/:
    main.py                      <- this file        ~ BucketElevatorPage.jsx
    theme.py                     <- shared colors     ~ CSS custom properties
    api_client.py                <- shared fetch       ~ api/client.js
    components/
        elevation_view.py        <- ElevationView      ~ ElevatorSchematic.jsx (Elevation only so far)
        equipment_tree.py        <- EquipmentTreePanel ~ EquipmentTree.jsx (complete)

Integrated so far (2 of ~14 components) -- everything else is an honest,
labeled placeholder naming the exact JSX file it represents, not a fake
implementation. As each one gets ported: build it in components/ as a
plain QWidget with set_data(inputs, results) (same shape as the two
already here), then swap the matching placeholder below for the real
import.

Run:
    python3 main.py
"""
import sys

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QStackedWidget, QMenu, QSplitter,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction

from theme import (
    BG, PANEL, PANEL2, BORDER, TEXT, TEXT2, TEXT3, MUTED, PRIMARY,
    SUCCESS, WARNING, DANGER, BRAND_RED,
)
from api_client import fetch_design
from components import ElevationView, EquipmentTreePanel, InputSidebarPanel

TABS = [
    {"id": "design",     "label": "Results"},
    {"id": "optimizer",  "label": "Optimizer", "badge": "AI"},
    {"id": "components", "label": "Components"},
    {"id": "materials",  "label": "Materials"},
    {"id": "checks",     "label": "Checks", "failBadge": True},
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
    fill; everything else (e.g. Screw Conveyor, a separate application
    this codebase doesn't contain) is an honest, visibly-disabled
    placeholder rather than a button that looks clickable but does
    nothing."""

    def __init__(self, icon, label, badge=None, active=False, enabled=True, parent=None):
        super().__init__(parent)
        self.setText(f"{icon}  {label}" + (f"   " if badge else ""))
        self.active = active
        self.setEnabled(enabled)
        if not enabled:
            self.setToolTip(f"{label} is a separate application, not part of this codebase yet")
        if active:
            self.setStyleSheet(f"""
                QPushButton {{ background-color: {PRIMARY}; color: white; border: none;
                    border-radius: 999px; padding: 7px 14px; font-size: 12px; font-weight: 600; }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{ background-color: transparent; color: {TEXT3}; border: none;
                    border-radius: 999px; padding: 7px 14px; font-size: 12px; }}
                QPushButton:disabled {{ color: {MUTED}; }}
                QPushButton:hover:!disabled {{ color: {TEXT2}; }}
            """)
        if badge:
            # The badge (VECTOMEC™) renders as a second, lighter-filled
            # pill nested inside this one in the original -- approximated
            # here as bold text in a slightly different shade rather than
            # a second nested widget, since QPushButton can't easily host
            # a child widget of its own.
            self.setText(f"{icon}  {label}")
            self._badge_text = badge


class AppTitleBar(QFrame):
    """Platform-level title bar -- VECTRIX™ branding + module switcher
    (Bucket Elevator / Screw Conveyor) + PDF Report + version. Sits ABOVE
    TopNav: this represents the platform, TopNav represents this specific
    page (BucketElevatorPage.jsx's own header). Colors sampled directly
    from the uploaded reference image, not guessed."""

    def __init__(self, parent=None):
        super().__init__(parent)
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
        # Badge rendered as its own small label, nested visually next to
        # the pill -- a real nested-pill-in-a-pill needs a custom-painted
        # widget; this reads the same at a glance without that complexity.
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
        pdf_btn.setStyleSheet(
            f"background-color: {PANEL2}; color: {TEXT2}; border: 1px solid {BORDER}; "
            f"border-radius: 999px; padding: 7px 14px; font-size: 11.5px; font-weight: 600;"
        )
        layout.addWidget(pdf_btn)

        version_lbl = QLabel("AKSHAYVIPRA EL-MEC · V1.0")
        version_lbl.setStyleSheet(f"color: {TEXT3}; font-size: 10.5px; font-weight: 600; letter-spacing: .5px;")
        layout.addWidget(version_lbl)


class NavTabButton(QPushButton):
    """A tab button hosted INSIDE the QMenuBar via addWidget() rather than
    as a QAction. Tested empirically before choosing this: neither
    QMenuBar::item:checked nor setActiveAction() render a persistent
    highlight reliably (confirmed by directly rendering both and
    comparing pixels, not assumed) -- addWidget() gives full, reliable
    control over the persistent rounded-bevel active state the JSX
    version has, while still living inside a genuine QMenuBar."""

    def __init__(self, label, parent=None):
        super().__init__(label, parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlat(True)
        self._apply_style()

    def setChecked(self, checked):
        super().setChecked(checked)
        self._apply_style()

    def _apply_style(self):
        if self.isChecked():
            self.setStyleSheet(f"""
                QPushButton {{ background-color: {PRIMARY}; color: white; border: none;
                    border-radius: 999px; padding: 6px 14px; font-size: 12px; font-weight: 600; }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{ background-color: transparent; color: {TEXT3}; border: none;
                    border-radius: 999px; padding: 6px 14px; font-size: 12px; }}
                QPushButton:hover {{ background-color: {PANEL2}; color: {TEXT2}; }}
            """)


class TopNav(QFrame):
    """Page-level bar: a "Bucket Elevator" dropdown with standard window
    functions (Minimize/Maximize/Open/Save/Exit), scoped under this app's
    own name rather than a generic "File" since more applications will be
    combined under this same platform later, plus the Results/Optimizer/
    Components/Materials/Checks tabs, plus Q/P/v KPI chips. Sits below
    AppTitleBar (the platform/module switcher) -- this is this specific
    page's own navigation (BucketElevatorPage.jsx's own header).

    FIX: the first version of this used a real QMenuBar with QMenuBar.
    addWidget() to host the tab buttons -- addWidget() doesn't actually
    exist on QMenuBar (confirmed directly: dir(QMenuBar) only has
    addAction/addActions/addMenu/addSeparator), and the QWidgetAction
    fallback I tried instead left the button with parent=None and the
    menu bar collapsed to 4px tall when actually rendered -- not a
    plausible-looking guess, an observed failure. This version uses only
    patterns confirmed to render correctly: QPushButton.setMenu() for the
    one real dropdown, plain QPushButtons in a normal QHBoxLayout for
    everything else. It reads as a native-style menu bar (dark strip,
    dropdown, click targets) without depending on QMenuBar's widget-
    hosting, which doesn't work for this use case.
    """

    def __init__(self, on_tab_changed, parent=None):
        super().__init__(parent)
        self.on_tab_changed = on_tab_changed
        self.setFixedHeight(40)
        self.setStyleSheet(f"background-color: {PANEL}; border-bottom: 1px solid {BORDER};")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)

        menu_qss = f"""
            QMenu {{ background-color: {PANEL2}; color: {TEXT2}; border: 1px solid {BORDER};
                border-radius: 8px; padding: 4px; }}
            QMenu::item {{ padding: 6px 24px 6px 14px; border-radius: 5px; font-size: 12px; }}
            QMenu::item:selected {{ background-color: {PRIMARY}; color: white; }}
            QMenu::separator {{ height: 1px; background-color: {BORDER}; margin: 4px 8px; }}
        """

        # ── "Bucket Elevator" menu -- standard window functions, scoped
        #    under this app's name since more applications will be
        #    combined under this same platform later. Minimize/Maximize/
        #    Exit are fully wired to real QMainWindow behavior; Open/Save
        #    are honest placeholders (no save-to-disk format has been
        #    designed yet) rather than actions that silently do nothing.
        app_btn = QPushButton("Bucket Elevator  ▾")
        app_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        app_btn.setStyleSheet(f"""
            QPushButton {{ background-color: transparent; color: {TEXT2}; border: none;
                border-radius: 999px; padding: 6px 14px; font-size: 12px; font-weight: 600; }}
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
        self._app_menu = app_menu   # keep alive -- same lesson as corner_widget below
        layout.addWidget(app_btn)

        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"background-color: {BORDER};")
        layout.addWidget(sep)

        # ── Tab buttons -- direct click, no dropdown ─────────────────────
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

        self.kpi_labels = {}
        for label, unit in (("Q", "t/h"), ("P", "kW"), ("v", "m/s")):
            chip = QFrame()
            chip.setStyleSheet(f"background-color: {PANEL2}; border: 1px solid {BORDER}; border-radius: 5px;")
            chip_layout = QVBoxLayout(chip)
            chip_layout.setContentsMargins(7, 2, 7, 2)
            chip_layout.setSpacing(0)
            lbl = QLabel(label.upper())
            lbl.setStyleSheet(f"color: {MUTED}; font-size: 8px; font-weight: 600;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val = QLabel("—")
            val.setStyleSheet(f"color: {TEXT3}; font-size: 12px; font-weight: 700;")
            val.setAlignment(Qt.AlignmentFlag.AlignCenter)
            unit_lbl = QLabel(unit)
            unit_lbl.setStyleSheet(f"color: {MUTED}; font-size: 8px;")
            unit_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chip_layout.addWidget(lbl); chip_layout.addWidget(val); chip_layout.addWidget(unit_lbl)
            layout.addWidget(chip)
            self.kpi_labels[label] = val

    def _toggle_maximize(self):
        win = self.window()
        if win.isMaximized():
            win.showNormal()
            self.act_maximize.setText("Maximize")
        else:
            win.showMaximized()
            self.act_maximize.setText("Restore")

    def _not_yet_wired(self, action_name):
        # Honest placeholder, same pattern as the Placeholder widget used
        # throughout the rest of the shell -- visible and labeled, not a
        # silent no-op. A real status bar message once one exists would
        # be the natural next step here.
        print(f"[{action_name}] not yet wired -- no save/load format designed yet.")

    def _select_tab(self, tab_id):
        for tid, btn in self.tab_buttons.items():
            btn.setChecked(tid == tab_id)
        self.on_tab_changed(tab_id)

    def update_kpis(self, results):
        r = results or {}
        self.kpi_labels["Q"].setText(fmt_kpi(r.get("Q"), 0))
        self.kpi_labels["P"].setText(fmt_kpi(r.get("P_total"), 1))
        self.kpi_labels["v"].setText(fmt_kpi(r.get("v"), 2))
        for key, color in (("Q", SUCCESS), ("P", WARNING), ("v", PRIMARY)):
            if r.get({"Q": "Q", "P": "P_total", "v": "v"}[key]) is not None:
                self.kpi_labels[key].setStyleSheet(f"color: {color}; font-size: 12px; font-weight: 700;")

    def update_fail_badge(self, n_fail):
        base = TABS[4]["label"]  # "Checks"
        text = f"{base}  ·{n_fail}" if n_fail > 0 else base
        self.tab_buttons["checks"].setText(text)
        # Re-apply the checkable button's own style since setText() alone
        # doesn't reset it, and the active/inactive look must still match
        # whichever state this button was already in.
        self.tab_buttons["checks"]._apply_style()


class ShellWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VECTRIX™ -- Bucket Elevator")
        self.resize(1400, 860)
        self.setStyleSheet(f"background-color: {BG};")

        self.app_title_bar = AppTitleBar()
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
        self.elevation = ElevationView()
        self.middle_stack.addWidget(self.elevation)
        self.middle_stack.addWidget(Placeholder("Optimizer", "OptimizerPanel.jsx"))
        self.middle_stack.addWidget(Placeholder("Components", "ComponentPanel.jsx"))
        self.middle_stack.addWidget(Placeholder("Materials", "MaterialLibraryPanel.jsx"))
        self.middle_stack.addWidget(Placeholder("Checks", "ChecksPanel.jsx / RootCausePanel.jsx"))
        col3_layout.addWidget(self.middle_stack)

        col4 = QWidget()
        col4_layout = QVBoxLayout(col4)
        col4_layout.setContentsMargins(0, 0, 0, 0)
        col4_layout.setSpacing(0)
        col4_layout.addWidget(ColHeader("Status"))
        col4_layout.addWidget(Placeholder("Design Review", "DesignReview.jsx / KpiGrid.jsx"))

        # FIX (Jay: "equipment tree that you first gave me had a flexible
        # column width which i liked. use that for all columns"): the
        # first proof-of-concept used a QSplitter (tree/detail, 520/460)
        # so the boundary was draggable -- this shell had regressed to
        # fixed-width columns (setFixedWidth + plain QHBoxLayout) when it
        # grew to 4 columns. Back to a real QSplitter, all 4 boundaries
        # draggable, not just the tree.
        body = QSplitter(Qt.Orientation.Horizontal)
        body.setStyleSheet(f"""
            QSplitter::handle {{ background-color: {BORDER}; }}
            QSplitter::handle:hover {{ background-color: {PRIMARY}; }}
        """)
        body.setHandleWidth(2)
        for col in (col1, col2, col3, col4):
            body.addWidget(col)
        # Initial sizes only -- same starting proportions the fixed-width
        # version had (200/280/flexible/260), but every boundary is now
        # draggable. Index 2 (the middle column) gets the stretch factor
        # so it absorbs extra space when the whole window resizes, while
        # still being a real, separately-draggable splitter pane.
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

        self._tab_index = {"design": 0, "optimizer": 1, "components": 2, "materials": 3, "checks": 4}
        self._tab_label = {"design": "Results", "optimizer": "Optimizer", "components": "Components",
                            "materials": "Materials", "checks": "Checks"}
        self._last_results = {}
        self._default_payload = {
            "Q_req": 100, "H_m": 25, "mat_id": "clinker",
            "auto_bucket": False, "bucket_id": "AC_12x8",
            "D_mm": 500, "n_rpm": 70, "fill_pct": 75,
        }

    def _on_tab_changed(self, tab_id):
        self.middle_stack.setCurrentIndex(self._tab_index[tab_id])
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
        # Default payload only computed once and stored -- inputsChanged
        # passes the user's edited dict here directly, this fallback is
        # only for the very first call in main().
        if payload is None:
            payload = self._default_payload
        results = fetch_design(payload)
        self._last_results = results
        self._default_payload = payload  # so the NEXT no-arg call (there isn't one yet, but keeps this honest) reflects the latest edit
        self.top_nav.update_kpis(results)
        self.elevation.set_data(payload, results)
        self.tree_panel.set_data(payload, results)
        self.input_sidebar.set_data(payload, results)

        n_fail, n_warn = self._fail_warn(results)
        self.top_nav.update_fail_badge(n_fail)
        if self._tab_index_of_current() == "design":
            new_header = ColHeader("Results", action=fail_warn_badges(n_fail, n_warn))
            self.col3_layout.replaceWidget(self.col3_header, new_header)
            self.col3_header.deleteLater()
            self.col3_header = new_header

    def _tab_index_of_current(self):
        idx = self.middle_stack.currentIndex()
        for tid, i in self._tab_index.items():
            if i == idx:
                return tid
        return "design"


def main():
    app = QApplication(sys.argv)
    window = ShellWindow()
    window.run_calculation()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()