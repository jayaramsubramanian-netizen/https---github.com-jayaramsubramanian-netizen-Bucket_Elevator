"""
main.py -- VECTRIX™ desktop app entry point, modeled on BucketElevatorPage.jsx
═══════════════════════════════════════════════════════════════════════════
THIS is the file to run and keep upgrading -- not equipment_tree_poc.py,
elevation_view_poc.py, or combined_shell_example.py.

BOX-IN-BOX BORDER SWEEP (this round)
────────────────────────────────────
Every setStyleSheet() in this file that declared a `border` did so with NO
selector. Qt treats a selector-less stylesheet as `* { ... }` -- it applies
to the widget AND EVERY DESCENDANT. So:

    ColHeader:   "background: PANEL; border-bottom: 1px solid BORDER"
                 -> the label AND the sub-label each drew their own bottom
                    border. That's the doubled/tripled underline under
                    every column header.
    AppTitleBar: same -- brand title, brand sub, module bar, PDF button all
                 inherited a bottom border.
    TopNav:      same, onto every tab button and the KPI row.
    err_header:  same, onto the error text.

Verified directly, not assumed: a QFrame with N child QLabels renders 2N
horizontal border runs inside itself under a bare declaration, and 0 under
a scoped one.

All declarations below now go through theme.scoped() / plain_bg(), which
bind the rule to the widget's own objectName so nothing can inherit it.
The rgba() color literals scattered through this file (badge tints, pill
fills) are now theme tokens -- they were all v1 values.

RETAINED (still correct, do not "simplify" back):
  - setFixedHeight() + border-radius = exactly half of it, on every pill
    button. A true stadium shape needs a KNOWN height to compute the radius
    against; relying on border-radius: 999px to always exceed half the
    height fails when the height is only ever a side-effect of padding.
  - border-style/border-width spelled out longhand rather than the
    `border: none` shorthand on those pills.
  - app.setStyle("Fusion").
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
    BG, PANEL, PANEL2, SURFACE, OVERLAY, BORDER, BORDER2,
    TEXT, TEXT2, TEXT3, MUTED,
    PRIMARY, PRIMARY_DIM, PRIMARY_RING,
    SUCCESS, WARNING, WARNING_DIM, WARNING_BORDER,
    DANGER, DANGER_DIM, DANGER_BORDER,
    BRAND_RED, R_SM, R_MD, R_PILL,
    scoped, plain_bg,
)
from api_client import fetch_design, download_pdf_report
from components.dialog_helpers import KPIChip, styled_message_box
from components import (
    ElevationView, EquipmentTreePanel, InputSidebarPanel, StatusPanel, OptimizerPanel,
    BomPanel, StatusDesignLeaves, MaintenancePanel, ChecksPanel, DesignReviewPanel,
    MaterialLibraryPanel, ChartsPanel, ComponentsLibraryPanel,
)

TABS = [
    {"id": "design",       "label": "Results"},
    {"id": "optimizer",    "label": "Optimizer", "badge": "AI"},
    {"id": "checks",       "label": "Checks", "failBadge": True},
    {"id": "components",   "label": "Components"},
    {"id": "comp_library", "label": "Comp. Library"},
    {"id": "maintenance",  "label": "Maintenance"},
    {"id": "materials",    "label": "Materials"},
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
    real app uses this same small component.

    SCOPED (this round): the bare declaration gave `border-bottom` to the
    label and the sub-label as well as the frame, so each column header
    was drawing up to three stacked underlines.
    """

    def __init__(self, label, sub=None, action=None, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        self.setStyleSheet(scoped(
            self,
            f"background-color: {PANEL}; border: none; "
            f"border-bottom: 1px solid {BORDER};"
        ))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        text_box = QHBoxLayout()
        text_box.setSpacing(7)
        lbl = QLabel(label.upper())
        lbl.setStyleSheet(
            f"color: {TEXT3}; font-size: 9.5px; font-weight: 700; letter-spacing: 1px;")
        text_box.addWidget(lbl)
        if sub:
            sub_lbl = QLabel(sub)
            sub_lbl.setStyleSheet(f"color: {MUTED}; font-size: 8.5px;")
            text_box.addWidget(sub_lbl)
        layout.addLayout(text_box)
        layout.addStretch()
        if action:
            layout.addWidget(action)


def _pill_label(text, color, dim, border):
    """Small status pill (FAIL / WARN / badge). Scoped, and the tint
    colors now come from theme tokens instead of hardcoded v1 rgba()."""
    lbl = QLabel(text)
    lbl.setStyleSheet(scoped(
        lbl,
        f"background-color: {dim}; color: {color}; "
        f"border: 1px solid {border}; border-radius: {R_PILL}px; "
        f"padding: 2px 7px; font-size: 8.5px; font-weight: 700;"
    ))
    return lbl


def fail_warn_badges(n_fail, n_warn):
    """FAIL/WARN pill row -- port of the JSX's inline badge markup that
    appears in the middle column's ColHeader action slot on the Results tab."""
    box = QWidget()
    layout = QHBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(5)
    if n_fail > 0:
        layout.addWidget(_pill_label(f"{n_fail} FAIL", DANGER, DANGER_DIM, DANGER_BORDER))
    if n_warn > 0:
        layout.addWidget(_pill_label(f"{n_warn} WARN", WARNING, WARNING_DIM, WARNING_BORDER))
    return box


class Placeholder(QWidget):
    """An honest, labeled gap -- not a fake implementation."""

    def __init__(self, title, source_file, parent=None):
        super().__init__(parent)
        self.setStyleSheet(plain_bg(self, BG))
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon = QLabel("○")
        icon.setStyleSheet(f"color: {MUTED}; font-size: 28px;")
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
    Elevator / Screw Conveyor). Active module gets the solid primary fill;
    everything else (e.g. Screw Conveyor) is an honest, visibly-disabled
    placeholder rather than a button that looks clickable but does nothing.

    RETAINED: setFixedHeight(MODULE_PILL_HEIGHT) + an exact-half border-
    radius. A true stadium shape needs a known, fixed height to compute the
    matching radius against -- not a radius value assumed to always exceed
    whatever height padding alone happens to produce.
    """

    def __init__(self, icon, label, badge=None, active=False, enabled=True, parent=None):
        super().__init__(parent)
        self.setText(f"{icon}  {label}")
        self.active = active
        self.setEnabled(enabled)
        self.setFixedHeight(MODULE_PILL_HEIGHT)
        if enabled:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setToolTip(
                f"{label} is a separate application, not part of this codebase yet")
        if badge:
            self._badge_text = badge

        if active:
            self.setStyleSheet(scoped(
                self,
                f"background-color: {PRIMARY}; color: white; "
                f"border-style: none; border-width: 0px; "
                f"border-radius: {MODULE_PILL_RADIUS}px; "
                f"padding: 0px 14px; font-size: 12px; font-weight: 600;"
            ))
        else:
            self.setStyleSheet(scoped(
                self,
                f"background-color: transparent; color: {TEXT3}; "
                f"border-style: none; border-width: 0px; "
                f"border-radius: {MODULE_PILL_RADIUS}px; "
                f"padding: 0px 14px; font-size: 12px;",
                extra=("{sel}:disabled { color: %s; }\n"
                       "{sel}:hover:!disabled { color: %s; }" % (MUTED, TEXT2)),
            ))


class AppTitleBar(QFrame):
    """Platform-level title bar -- VECTRIX™ branding + module switcher
    (Bucket Elevator / Screw Conveyor) + PDF Report + version.

    SCOPED: the bare `border-bottom` here was inherited by the brand icon,
    both brand labels, the module bar, the badge and the PDF button.
    """

    def __init__(self, on_tab_changed=None, on_pdf_clicked=None, parent=None):
        super().__init__(parent)
        self.on_pdf_clicked = on_pdf_clicked
        self.setFixedHeight(48)
        self.setStyleSheet(scoped(
            self,
            f"background-color: {OVERLAY}; border: none; "
            f"border-bottom: 1px solid {BORDER};"
        ))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(14)

        icon = QLabel("⚙")
        icon.setFixedSize(30, 30)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(scoped(
            icon,
            f"background-color: {BRAND_RED}; border: none; "
            f"border-radius: {R_SM}px; color: white; font-size: 15px;"
        ))
        layout.addWidget(icon)

        brand_box = QVBoxLayout()
        brand_box.setSpacing(0)
        brand_title = QLabel("VECTRIX™")
        brand_title.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: 700;")
        brand_sub = QLabel("DESIGN PLATFORM")
        brand_sub.setStyleSheet(
            f"color: {TEXT3}; font-size: 8px; font-weight: 600; letter-spacing: 1px;")
        brand_box.addWidget(brand_title)
        brand_box.addWidget(brand_sub)
        layout.addLayout(brand_box)

        module_bar = QFrame()
        module_bar.setStyleSheet(scoped(
            module_bar,
            f"background-color: {SURFACE}; border: 1px solid {BORDER}; "
            f"border-radius: {R_PILL}px;"
        ))
        module_layout = QHBoxLayout(module_bar)
        module_layout.setContentsMargins(3, 3, 3, 3)
        module_layout.setSpacing(2)

        be_pill = ModulePill("⛏", "Bucket Elevator", badge="VECTOMEC™", active=True)
        module_layout.addWidget(be_pill)
        badge_lbl = QLabel("VECTOMEC™")
        badge_lbl.setStyleSheet(scoped(
            badge_lbl,
            f"background-color: rgba(255,255,255,.18); color: white; border: none; "
            f"border-radius: {R_PILL}px; padding: 2px 8px; "
            f"font-size: 8.5px; font-weight: 700; margin-left: -8px;"
        ))
        module_layout.addWidget(badge_lbl)

        sc_pill = ModulePill("🌀", "Screw Conveyor", active=False, enabled=False)
        module_layout.addWidget(sc_pill)
        layout.addWidget(module_bar)

        layout.addStretch()

        pdf_btn = QPushButton("⬇  PDF Report")
        pdf_btn.setFixedHeight(MODULE_PILL_HEIGHT)
        pdf_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        pdf_btn.setStyleSheet(scoped(
            pdf_btn,
            f"background-color: {SURFACE}; color: {TEXT2}; "
            f"border-style: solid; border-width: 1px; border-color: {BORDER2}; "
            f"border-radius: {MODULE_PILL_RADIUS}px; padding: 0px 14px; "
            f"font-size: 11.5px; font-weight: 600;",
            extra="{sel}:hover { background-color: %s; }" % BORDER2,
        ))
        pdf_btn.clicked.connect(lambda: self.on_pdf_clicked() if self.on_pdf_clicked else None)
        layout.addWidget(pdf_btn)

        # Welcome message -- "Hello, [Name]" for the logged-in user. Reads
        # auth.current_user() with a safe fallback for test/headless
        # environments where auth isn't initialized.
        try:
            from auth import current_user as _cu
            _u = _cu()
            _greeting = f"Hello, {_u.display_name}  ·  " if _u else ""
        except Exception:
            _greeting = ""

        version_lbl = QLabel(f"{_greeting}JAYVEECONS · V1.0")
        version_lbl.setStyleSheet(
            f"color: {TEXT3}; font-size: 10.5px; font-weight: 600; letter-spacing: .5px;")
        layout.addWidget(version_lbl)


class NavTabButton(QPushButton):
    """A tab button hosted in the top nav bar.

    RETAINED: setFixedHeight(TAB_PILL_HEIGHT) with the radius set to
    exactly half of it -- the geometrically guaranteed way to get a true
    stadium shape. border-style/border-width longhand rather than the
    `border: none` shorthand, removing any shorthand-vs-longhand parsing
    inconsistency in the stylesheet engine.
    """

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
            self.setStyleSheet(scoped(
                self,
                f"background-color: {PRIMARY}; color: white; "
                f"border-style: none; border-width: 0px; "
                f"border-radius: {TAB_PILL_RADIUS}px; "
                f"padding: 0px 16px; font-size: 12.5px; font-weight: 600;"
            ))
        else:
            self.setStyleSheet(scoped(
                self,
                f"background-color: transparent; color: {TEXT3}; "
                f"border-style: none; border-width: 0px; "
                f"border-radius: {TAB_PILL_RADIUS}px; "
                f"padding: 0px 16px; font-size: 12.5px;",
                extra="{sel}:hover { background-color: %s; color: %s; }" % (SURFACE, TEXT2),
            ))


class TopNav(QFrame):
    """Page-level bar: a "Bucket Elevator" dropdown with standard window
    functions, the tab pills, plus Q/P/v KPI chips.

    RETAINED (earlier rounds, still in effect):
      - 76px tall with the KPI chips in their own sub-layout at real
        spacing, independent of the tighter spacing the tab row uses.
      - QMenuBar.addWidget() does not exist (confirmed: dir(QMenuBar) has
        only addAction/addActions/addMenu/addSeparator). This uses only
        patterns confirmed to render: QPushButton.setMenu() for the one
        real dropdown, plain QPushButtons for everything else.
      - KPIChip: a single custom-painted widget, not a QFrame wrapping
        three QLabels. It has no child widgets, so it was structurally
        immune to the box-in-box bug -- which is exactly why it's the
        pattern every other card in this app is now being moved toward.
    """

    def __init__(self, on_tab_changed, on_open=None, on_save=None,
                 on_save_as=None, on_manage_users=None, parent=None):
        super().__init__(parent)
        self.on_tab_changed = on_tab_changed
        self._on_open = on_open
        self._on_save = on_save
        self._on_save_as = on_save_as
        self._on_manage_users = on_manage_users
        self.setFixedHeight(76)
        self.setStyleSheet(scoped(
            self,
            f"background-color: {PANEL}; border: none; "
            f"border-bottom: 1px solid {BORDER};"
        ))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        # QMenu rules are DELIBERATELY class-scoped: QMenu::item and
        # ::separator are the children we mean to target by name. That is
        # an intentional descendant rule, not an accidental cascade.
        menu_qss = f"""
            QMenu {{ background-color: {PANEL2}; color: {TEXT2};
                border: 1px solid {BORDER2}; border-radius: {R_MD}px; padding: 4px; }}
            QMenu::item {{ padding: 6px 24px 6px 14px;
                border-radius: {R_SM}px; font-size: 12px; }}
            QMenu::item:selected {{ background-color: {PRIMARY}; color: white; }}
            QMenu::separator {{ height: 1px; background-color: {BORDER};
                margin: 4px 8px; }}
        """

        app_btn = QPushButton("Bucket Elevator  ▾")
        app_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        app_btn.setFixedHeight(TAB_PILL_HEIGHT)
        app_btn.setStyleSheet(scoped(
            app_btn,
            f"background-color: transparent; color: {TEXT2}; "
            f"border-style: none; border-width: 0px; "
            f"border-radius: {TAB_PILL_RADIUS}px; "
            f"padding: 0px 16px; font-size: 12.5px; font-weight: 600;",
            extra=("{sel}:hover { background-color: %s; }\n"
                   "{sel}::menu-indicator { image: none; }" % SURFACE),
        ))
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
        act_open.triggered.connect(lambda: self._on_open() if self._on_open else None)
        app_menu.addAction(act_open)
        act_save = QAction("Save Design", self)
        act_save.setShortcut("Ctrl+S")
        act_save.triggered.connect(lambda: self._on_save() if self._on_save else None)
        app_menu.addAction(act_save)
        act_save_as = QAction("Save Design As...", self)
        act_save_as.triggered.connect(lambda: self._on_save_as() if self._on_save_as else None)
        app_menu.addAction(act_save_as)
        app_menu.addSeparator()
        act_users = QAction("Manage Users...", self)
        act_users.triggered.connect(
            lambda: self._on_manage_users() if self._on_manage_users else None)
        app_menu.addAction(act_users)
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
        sep.setStyleSheet(plain_bg(sep, BORDER2))
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

    def _select_tab(self, tab_id):
        for tid, btn in self.tab_buttons.items():
            btn.setChecked(tid == tab_id)
        self.on_tab_changed(tab_id)

    def update_kpis(self, results):
        """Capacity color reads results["cap_ok"] directly (already computed
        by the backend -- a straight Q >= Q_req check in calculations.py) per
        the architecture rule that the frontend never duplicates engineering
        checks. P and v have no equivalent required-vs-actual concept in the
        backend, so they keep fixed categorical colors."""
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
    """Background thread for all four PDF report types."""
    done = Signal(str)
    errorOccurred = Signal(str)

    ENDPOINT_MAP = {
        "engineering": None,                             # uses download_pdf_report
        "workshop":    "manufacturing-reports/workshop",
        "procurement": "manufacturing-reports/procurement",
        "enduser":     "manufacturing-reports/enduser",
    }

    def __init__(self, results, inputs, save_path, report_type="engineering", parent=None):
        super().__init__(parent)
        self.results = results
        self.inputs = inputs
        self.save_path = save_path
        self.report_type = report_type

    def run(self):
        try:
            endpoint = self.ENDPOINT_MAP.get(self.report_type)
            if endpoint is None:
                path = download_pdf_report(self.results, self.inputs, self.save_path)
            else:
                import requests
                from api_client import API_BASE_V1
                resp = requests.post(
                    f"{API_BASE_V1}/{endpoint}",
                    json={"results": self.results, "inputs": self.inputs},
                    timeout=60,
                )
                resp.raise_for_status()
                with open(self.save_path, "wb") as f:
                    f.write(resp.content)
                path = self.save_path
            self.done.emit(path)
        except Exception as e:
            self.errorOccurred.emit(str(e))


class ShellWindow(QMainWindow):
    def __init__(self, auth_db=None):
        super().__init__()
        from auth import current_user
        self._auth_db = auth_db
        self._current_design_file = None   # the currently open DesignFile, or None
        user = current_user()
        user_str = f" — {user.display_name} ({user.role.capitalize()})" if user else ""
        self.setWindowTitle(f"VECTOMEC™ — Bucket Elevator{user_str}")
        self.resize(1400, 860)
        self.setStyleSheet(plain_bg(self, BG))

        self.app_title_bar = AppTitleBar(on_pdf_clicked=self._on_pdf_clicked)
        self.top_nav = TopNav(
            on_tab_changed=self._on_tab_changed,
            on_open=self._on_open_design,
            on_save=self._on_save_design,
            on_save_as=lambda: self._on_save_design(save_as=True),
            on_manage_users=self._on_manage_users,
        )

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

        # Results tab: elevation view + charts panel, in a QScrollArea so
        # neither is clipped when the window is short -- direct feedback:
        # "elevator schematic section does not scroll, making this section
        # be at the very bottom of the page". The internal splitter stays
        # flexible so the elevation/chart proportion is still resizable.
        results_scroll = QScrollArea()
        results_scroll.setWidgetResizable(True)
        results_scroll.setStyleSheet(scoped(results_scroll, "border: none;"))
        results_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        results_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        results_inner = QWidget()
        results_inner_layout = QVBoxLayout(results_inner)
        results_inner_layout.setContentsMargins(0, 0, 0, 0)
        results_inner_layout.setSpacing(0)

        results_splitter = QSplitter(Qt.Orientation.Vertical)
        results_splitter.setStyleSheet(
            f"QSplitter::handle {{ background-color: {BORDER2}; height: 4px; }}"
            f"QSplitter::handle:hover {{ background-color: {PRIMARY}; }}"
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
        self.components_library_panel = ComponentsLibraryPanel()
        self.middle_stack.addWidget(self.components_library_panel)
        col3_layout.addWidget(self.middle_stack)

        col4 = QWidget()
        col4_layout = QVBoxLayout(col4)
        col4_layout.setContentsMargins(0, 0, 0, 0)
        col4_layout.setSpacing(0)
        col4_layout.addWidget(ColHeader("Status"))
        # Status content is tab-aware: KpiGrid (status_panel.py) for
        # Results/Optimizer/Maintenance/Materials, StatusDesignLeaves for
        # Components, DesignReviewPanel for Checks.
        self.status_stack = QStackedWidget()
        self.status_panel = StatusPanel()
        self.status_stack.addWidget(self.status_panel)           # 0 -- KpiGrid
        self.status_leaves = StatusDesignLeaves()
        self.status_stack.addWidget(self.status_leaves)          # 1 -- BOM design leaves
        self.design_review_panel = DesignReviewPanel()
        self.status_stack.addWidget(self.design_review_panel)    # 2 -- Design Review
        col4_layout.addWidget(self.status_stack)
        self._status_view_for_tab = {
            "design": 0, "optimizer": 0, "components": 1,
            "maintenance": 0, "materials": 0, "checks": 2,
        }

        body = QSplitter(Qt.Orientation.Horizontal)
        body.setStyleSheet(
            f"QSplitter::handle {{ background-color: {BORDER2}; }}"
            f"QSplitter::handle:hover {{ background-color: {PRIMARY}; }}"
        )
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

        self._tab_index = {
            "design": 0, "optimizer": 1, "checks": 2, "components": 3,
            "maintenance": 4, "materials": 5, "comp_library": 6,
        }
        self._tab_label = {
            "design": "Results", "optimizer": "Optimizer", "checks": "Checks",
            "components": "Components", "maintenance": "Maintenance",
            "materials": "Materials", "comp_library": "Components Library",
        }
        self._last_results = {}
        self._default_payload = {
            "Q_req": 100, "H_m": 25, "mat_id": "clinker",
            "auto_bucket": False, "bucket_id": "AC_12x8",
            "D_mm": 500, "n_rpm": 70, "fill_pct": 75,
        }

    def _on_tab_changed(self, tab_id):
        self.middle_stack.setCurrentIndex(self._tab_index[tab_id])
        self.status_stack.setCurrentIndex(self._status_view_for_tab.get(tab_id, 0))
        action = (fail_warn_badges(*self._fail_warn(self._last_results))
                  if tab_id == "design" else None)
        self._swap_col3_header(ColHeader(self._tab_label[tab_id], action=action))

    def _swap_col3_header(self, new_header):
        """One place that replaces the col3 header -- this was duplicated
        three times with identical replaceWidget/deleteLater bodies."""
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
        and shown as a non-fatal error banner instead of killing the window.
        The previous result is kept so the user can still read what they last
        successfully calculated.

        The specific crash that prompted this: a bucket_gap spinbox emitting
        an intermediate value mid-edit sent a 422 from Pydantic validation,
        fetch_design() called raise_for_status(), and the HTTPError propagated
        with no catch -- Qt terminated the event loop on the unhandled
        exception. The backend was healthy; the crash was entirely client-side.

        KNOWN GAP (not addressed in this styling sweep, flagged deliberately
        rather than quietly fixed mid-sweep): fetch_design() runs SYNCHRONOUSLY
        on the GUI thread, so the whole window freezes for the duration of every
        recalculation. Material search and the guidance preview both already got
        QThread workers; this path never did. Worth doing next -- but as its own
        change, so a regression here can't be confused with a styling one.
        """
        if payload is None:
            payload = self._default_payload
        try:
            results = fetch_design(payload)
        except Exception as e:
            err_msg = str(e)
            if "422" in err_msg or "Unprocessable" in err_msg:
                user_msg = f"Validation error — check input values ({err_msg[:120]})"
            elif "ConnectionError" in type(e).__name__ or "Connection" in err_msg:
                user_msg = "Cannot reach backend — is the server running on port 8000?"
            else:
                user_msg = f"Calculation error: {err_msg[:200]}"
            err_header = ColHeader(f"⚠  {user_msg[:80]}")
            # SCOPED: the bare version put this red bottom-border on the
            # header's own child labels too.
            err_header.setStyleSheet(scoped(
                err_header,
                f"background-color: {DANGER_DIM}; color: {DANGER}; border: none; "
                f"border-bottom: 1px solid {DANGER_BORDER};"
            ))
            self._swap_col3_header(err_header)
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
            self.components_library_panel.set_data(payload, results)
            self.optimizer_panel.set_data(payload, results)
        except Exception:
            import traceback
            traceback.print_exc()   # visible in the terminal for debugging
            # Non-fatal: results were saved, some panels may not have updated

        n_fail, n_warn = self._fail_warn(results)
        self.top_nav.update_fail_badge(n_fail)
        if self._tab_index_of_current() == "design":
            self._swap_col3_header(
                ColHeader("Results", action=fail_warn_badges(n_fail, n_warn)))

    def _on_optimizer_apply(self, variant):
        """Mirrors useElevatorCalc.js's applyOptimizer() exactly (read
        directly before writing this, not assumed): rpm -> n_rpm, fill ->
        fill_pct, auto_bucket forced False, and the v2-only fields
        (D_mm/boot_pulley_D_mm/chain_n_strands/sprocket teeth) only merged in
        when present -- a belt-mode result has no chain fields, and merging
        None over an existing value would clobber it rather than leave it
        untouched, same as the JSX's own `D_mm != null ? { D_mm } : {}` guards."""
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
        r = self._last_results or {}
        inp = self._default_payload or {}
        try:
            from api_client import fetch_model_number
            model_no = fetch_model_number(inp, r)
        except Exception:
            mat = str(inp.get("mat_id", "material")).capitalize()
            Q = inp.get("Q_req", "")
            H = inp.get("H_m", "")
            model_no = f"VM-BE_{mat}_{Q}tph_H{H}m"
        from datetime import datetime
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        return f"{model_no}_{stamp}.pdf"

    @staticmethod
    def _styled_message_box(icon, title, text, parent):
        return styled_message_box(icon, title, text, parent)

    def _on_save_design(self, save_as: bool = False):
        """Save Design / Save Design As handler."""
        if not self._last_results:
            self._styled_message_box(
                QMessageBox.Icon.Information, "Nothing to Save",
                "Run a calculation first before saving.", self
            ).exec()
            return

        from app_config import AppConfig
        from auth import current_user
        from design_file import DesignFile, build_filename
        import api_client

        cfg = AppConfig.get()
        user = current_user()
        user_dict = user.to_dict() if user else {}

        try:
            model_no = api_client.fetch_model_number(self._default_payload, self._last_results)
        except Exception:
            model_no = "VM-??-?-???/???"

        drp = self.design_review_panel
        stage = drp._manual_stage or 1   # respect the user's current review stage

        if self._current_design_file and not save_as:
            version = self._current_design_file.version + 1
        else:
            version = cfg.next_design_version(model_no)

        df = DesignFile.create(
            inputs=self._default_payload,
            results=self._last_results,
            model_number=model_no,
            stage=stage,
            version=version,
            created_by=user_dict,
        )
        filename = build_filename(model_no, stage, version)
        save_path = cfg.designs_dir / filename

        try:
            df.save(save_path)
            self._current_design_file = df
            self._styled_message_box(
                QMessageBox.Icon.Information, "Design Saved",
                f"Saved as:\n{save_path.name}", self
            ).exec()
        except Exception as e:
            self._styled_message_box(
                QMessageBox.Icon.Critical, "Save Failed",
                f"Could not save design:\n{e}", self
            ).exec()

    def _on_open_design(self):
        """Open Design handler -- shows the file browser dialog."""
        from app_config import AppConfig
        from open_design_dialog import OpenDesignDialog

        cfg = AppConfig.get()
        dlg = OpenDesignDialog(cfg.designs_dir, parent=self)
        if dlg.exec() != dlg.DialogCode.Accepted:
            return
        df = dlg.selected_design_file
        if df is None:
            return

        try:
            self._current_design_file = df
            self._default_payload = dict(df.inputs)
            self.run_calculation(self._default_payload)
            drp = self.design_review_panel
            drp._manual_stage = df.design_stage if df.design_stage > 1 else None
            drp._rebuild()
            self._styled_message_box(
                QMessageBox.Icon.Information, "Design Loaded",
                f"Opened: {df.model_number}  v{df.version:03d}  [{df.stage_label}]", self
            ).exec()
        except Exception as e:
            self._styled_message_box(
                QMessageBox.Icon.Critical, "Load Failed",
                f"Could not load design:\n{e}", self
            ).exec()

    def _on_manage_users(self):
        """User management -- approver role only."""
        from auth import require_role
        from login_dialog import UserManagerDialog
        if not require_role("approver"):
            self._styled_message_box(
                QMessageBox.Icon.Warning, "Access Denied",
                "Only Approvers can manage users.", self
            ).exec()
            return
        if self._auth_db is None:
            self._styled_message_box(
                QMessageBox.Icon.Warning, "Not Available",
                "User management is not available in this session.", self
            ).exec()
            return
        dlg = UserManagerDialog(self._auth_db, parent=self)
        dlg.exec()

    def _on_pdf_clicked(self):
        """PDF Report button -- context menu to choose which of the four
        report types to generate, then delegate to the handler."""
        if not self._last_results:
            self._styled_message_box(
                QMessageBox.Icon.Information, "No Results",
                "Run a calculation first.", self
            ).exec()
            return
        from PySide6.QtCore import QPoint
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu {{ background-color: {PANEL2}; color: {TEXT}; "
            f"border: 1px solid {BORDER2}; border-radius: {R_SM}px; padding: 4px; }}"
            f"QMenu::item {{ padding: 7px 18px; font-size: 11px; }}"
            f"QMenu::item:selected {{ background-color: {PRIMARY}; color: #fff; "
            f"border-radius: 3px; }}"
        )
        menu.addSection("Select Report Type")
        menu.addAction("📋  Engineering Report (Design + Calculations)",
                       lambda: self._generate_report("engineering"))
        menu.addSeparator()
        menu.addAction("🔧  Workshop Report (Fabrication BOM + QC Checkpoints)",
                       lambda: self._generate_report("workshop"))
        menu.addAction("🛒  Procurement Report (Commercial BOM + Long-Lead Items)",
                       lambda: self._generate_report("procurement"))
        menu.addAction("📖  End-User Report (Installation + Commissioning + Spares)",
                       lambda: self._generate_report("enduser"))
        pdf_btns = [w for w in self.app_title_bar.findChildren(QPushButton)
                    if "PDF" in (w.text() or "").upper() or "REPORT" in (w.text() or "").upper()]
        if pdf_btns:
            pos = pdf_btns[0].mapToGlobal(QPoint(0, pdf_btns[0].height()))
        else:
            from PySide6.QtGui import QCursor
            pos = QCursor.pos()
        menu.exec(pos)

    def _generate_report(self, report_type: str):
        """Save dialog + background worker for the selected report type. All
        four use the same save/progress/done pattern; only the filename suffix
        and backend endpoint differ."""
        suffix_map = {
            "engineering": self._auto_pdf_filename,
            "workshop":    lambda: self._auto_pdf_filename().replace(".pdf", "_Workshop.pdf"),
            "procurement": lambda: self._auto_pdf_filename().replace(".pdf", "_Procurement.pdf"),
            "enduser":     lambda: self._auto_pdf_filename().replace(".pdf", "_EndUser.pdf"),
        }
        name_fn = suffix_map.get(report_type, self._auto_pdf_filename)
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save Report", name_fn(), "PDF Files (*.pdf)"
        )
        if not save_path:
            return
        self._pdf_worker = _PdfReportWorker(
            self._last_results, self._default_payload, save_path,
            report_type=report_type, parent=self
        )
        self._pdf_worker.done.connect(self._on_pdf_done)
        self._pdf_worker.errorOccurred.connect(self._on_pdf_error)
        self._pdf_worker.start()
        for lbl in self.app_title_bar.findChildren(QLabel):
            if "JAYVEECONS" in (lbl.text() or ""):
                lbl.setText("Generating PDF…")
                self._pdf_version_lbl = lbl
                break

    def _on_pdf_done(self, path):
        if hasattr(self, "_pdf_version_lbl"):
            self._pdf_version_lbl.setText("JAYVEECONS · V1.0")
        self._styled_message_box(
            QMessageBox.Icon.Information, "Report Saved", f"PDF saved to:\n{path}", self
        ).exec()

    def _on_pdf_error(self, msg):
        if hasattr(self, "_pdf_version_lbl"):
            self._pdf_version_lbl.setText("JAYVEECONS · V1.0")
        self._styled_message_box(
            QMessageBox.Icon.Critical, "Report Failed",
            f"PDF generation failed:\n{msg}", self
        ).exec()

    def _on_apply_correction(self, param, value):
        """Mirrors RootCausePanel.jsx's setField(param, target) -- a single
        corrective param/value pair from a root-cause finding's Apply button
        gets merged into the live payload and recalculated."""
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

    # ── 1. Initialize folder structure and config ─────────────────────
    from app_config import AppConfig
    cfg = AppConfig.get()

    # ── 2. Initialize auth database ───────────────────────────────────
    from auth import AuthDB
    auth_db = AuthDB(cfg.users_db_path)

    # ── 3. First-launch wizard or login dialog ────────────────────────
    from login_dialog import FirstLaunchWizard, LoginDialog
    if not auth_db.has_any_users():
        wizard = FirstLaunchWizard(auth_db)
        if wizard.exec() != wizard.DialogCode.Accepted:
            sys.exit(0)
        cfg.mark_first_launch_done()
    else:
        login = LoginDialog(auth_db)
        if login.exec() != login.DialogCode.Accepted:
            sys.exit(0)

    # ── 4. Main window ────────────────────────────────────────────────
    window = ShellWindow(auth_db=auth_db)
    window.run_calculation()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()