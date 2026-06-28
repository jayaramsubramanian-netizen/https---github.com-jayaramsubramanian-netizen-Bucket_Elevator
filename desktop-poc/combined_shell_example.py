"""
combined_shell_example.py -- demonstrates how to actually combine the two
PoC files into one app, sharing a single fetch instead of two.
═══════════════════════════════════════════════════════════════════════════
This is the concrete answer to "how do I replace a section into my main
code": ElevationView (from elevation_view_poc.py) is ALREADY shaped to be
reused -- it's a plain QWidget that takes (inputs, results) as data and
draws them, with no fetch logic of its own. That's deliberate: a widget
that owns its own backend call can't be dropped into a shell that wants to
share one fetch across multiple tabs.

EquipmentTreeWindow (from equipment_tree_poc.py), by contrast, is NOT
shell-ready as-is -- it's a full QMainWindow that owns its own header,
input bar, AND fetch call. To reuse it here, the tree-building logic is
lifted into a plain QWidget (EquipmentTreePanel below) that takes data the
same way ElevationView does. This is the real refactor you'd repeat for
every other POC component as you fold it in: keep the drawing/rendering
logic, drop the standalone window/input-bar/fetch boilerplate, expose a
set_data(inputs, results) method.

Run:
    python3 combined_shell_example.py
"""
import sys
import requests

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QLineEdit, QPushButton, QComboBox, QSplitter, QTreeWidget,
    QTreeWidgetItem, QTextEdit, QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QFont

# Reuse the actual widget + helpers from the two PoC files directly --
# this IS the integration, not a rewrite.
from elevation_view_poc import ElevationView, fetch_design
from equipment_tree_poc import node_status, merge_status, fmt, STATUS_COLOR

API_BASE = "http://localhost:8000/api"
COLOR_BG, COLOR_PANEL, COLOR_BORDER = "#0a1628", "#0d1c2e", "#1c3050"
COLOR_TEXT, COLOR_TEXT2, COLOR_TEXT3 = "#e8f0fa", "#b0c4d8", "#5a7a9a"


class EquipmentTreePanel(QWidget):
    """Lifted from EquipmentTreeWindow's tree-building logic -- same
    node_status()/merge_status() calls, same leaf set, but as a plain
    QWidget with a set_data() method instead of a QMainWindow that owns
    its own fetch. This is the shape every POC component needs to be in
    before it can sit in a shared shell.

    show_detail=True (default): tree + inline detail panel, for standalone
    use (this is how combined_shell_example.py originally used it).
    show_detail=False: tree only, narrow -- matches the REAL EquipmentTree.
    jsx, which has no inline detail view at all; clicking a leaf there
    calls onNodeClick to open the relevant panel elsewhere in the app.
    Forcing the wider standalone layout into a 190-280px sidebar (the
    original's actual width) just truncated every label -- this isn't a
    cosmetic tweak, it's matching the component to the context it's
    actually being embedded in."""

    def __init__(self, parent=None, show_detail=True):
        super().__init__(parent)
        self.show_detail = show_detail
        self.results, self.inputs = {}, {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.setStyleSheet(f"""
            QTreeWidget {{ background-color: {COLOR_BG}; color: {COLOR_TEXT2};
                border: none; font-size: 12px; }}
            QTreeWidget::item {{ padding: 3px 2px; }}
        """)

        if show_detail:
            detail = QFrame()
            detail.setStyleSheet(f"background-color: {COLOR_PANEL};")
            dlayout = QVBoxLayout(detail)
            self.detail_title = QLabel("Select a leaf to see its checks")
            self.detail_title.setStyleSheet(f"color: {COLOR_TEXT2}; font-size: 12px; font-weight: 600; padding: 8px;")
            self.detail_text = QTextEdit()
            self.detail_text.setReadOnly(True)
            self.detail_text.setStyleSheet(f"background-color: {COLOR_BG}; color: {COLOR_TEXT2}; border: none; padding: 8px;")
            dlayout.addWidget(self.detail_title)
            dlayout.addWidget(self.detail_text)

            splitter = QSplitter(Qt.Orientation.Horizontal)
            splitter.addWidget(self.tree)
            splitter.addWidget(detail)
            splitter.setSizes([500, 400])
            layout.addWidget(splitter)
        else:
            self.detail_title = None
            self.detail_text = None
            layout.addWidget(self.tree)

    def set_data(self, inputs, results):
        """Same signature as ElevationView.set_data() -- this consistency
        is what lets the shell below treat every tab the same way."""
        self.inputs, self.results = inputs or {}, results or {}
        self._rebuild_tree()

    def _on_item_clicked(self, item, _col):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        # FIX (Pylance reportOptionalMemberAccess): checking self.show_detail
        # doesn't let Pyright narrow self.detail_title/detail_text -- they're
        # typed Optional since __init__ sets them to None when show_detail
        # is False, and the flag and the attributes are two different things
        # as far as the type checker is concerned. Checking the actual
        # attributes directly is both correct and lets Pyright narrow them.
        if not data or self.detail_title is None or self.detail_text is None:
            return
        status = data["status"]
        self.detail_title.setText(f"{data['label']} — {status.upper()}")
        self.detail_title.setStyleSheet(
            f"color: {STATUS_COLOR.get(status, COLOR_TEXT3)}; font-size: 13px; font-weight: 700; padding: 8px;"
        )
        checks = data.get("checks", [])
        text = "\n\n".join(f"[{c.get('type','?').upper()}] {c.get('msg','')}" for c in checks) or "No checks flagged."
        self.detail_text.setPlainText(text)

    def _rebuild_tree(self):
        # Trimmed to Process + Head Assembly for this example -- the full
        # version is the _rebuild_tree() already built in equipment_tree_poc.py;
        # the point here is the set_data() pattern, not re-listing every leaf.
        self.tree.clear()
        r, inp, checks = self.results, self.inputs, self.results.get("checks", []) or []
        mat = r.get("mat") or {}

        def section(label):
            item = QTreeWidgetItem(self.tree)
            item.setText(0, label)
            f = QFont(); f.setBold(True)
            item.setFont(0, f)
            item.setForeground(0, QBrush(QColor(COLOR_TEXT)))
            return item

        def leaf(parent, label, sub, status_result):
            status = status_result["status"] if isinstance(status_result, dict) else status_result
            checks_ = status_result["checks"] if isinstance(status_result, dict) else []
            item = QTreeWidgetItem(parent)
            item.setText(0, f"  {label}  ·  {sub}")
            item.setForeground(0, QBrush(QColor(STATUS_COLOR.get(status, COLOR_TEXT3))))
            item.setData(0, Qt.ItemDataRole.UserRole, {"label": label, "status": status, "checks": checks_})

        process = section("PROCESS")
        leaf(process, "Material", f"{mat.get('name','—')} ρ={fmt(r.get('rho'),0)}", "none")
        leaf(process, "Capacity", f"{fmt(r.get('Q'),1)} t/h", node_status(checks, "process", ["capacity"]))
        leaf(process, "Belt Speed", f"{fmt(r.get('v'),2)} m/s", node_status(checks, "process", ["speed"]))
        self.tree.expandAll()


class ShellWindow(QMainWindow):
    """The actual integration: one input bar, one fetch, both panels fed
    from the same result via set_data()."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("VECTRIX™ -- Combined Shell Example")
        self.resize(1100, 720)
        self.setStyleSheet(f"background-color: {COLOR_BG};")

        self.elevation = ElevationView()
        self.tree_panel = EquipmentTreePanel()

        tabs = QTabWidget()
        tabs.addTab(self.elevation, "Elevation")
        tabs.addTab(self.tree_panel, "Equipment Tree")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._build_input_bar())
        layout.addWidget(tabs)
        self.setCentralWidget(container)

    def _build_input_bar(self):
        bar = QFrame()
        bar.setFixedHeight(46)
        bar.setStyleSheet(f"background-color: {COLOR_PANEL}; border-bottom: 1px solid {COLOR_BORDER};")
        h = QHBoxLayout(bar)
        h.setContentsMargins(14, 6, 14, 6)
        self.in_mat = QLineEdit("clinker"); self.in_mat.setFixedWidth(90)
        self.in_bucket = QLineEdit("AC_12x8"); self.in_bucket.setFixedWidth(90)
        for w in (self.in_mat, self.in_bucket):
            w.setStyleSheet(f"background-color: {COLOR_BG}; color: {COLOR_TEXT}; border: 1px solid {COLOR_BORDER}; padding: 3px;")
            h.addWidget(w)
        h.addStretch()
        run_btn = QPushButton("Run Calculation")
        run_btn.setStyleSheet("background-color: #4a9eff; color: white; padding: 8px 16px; border-radius: 4px;")
        run_btn.clicked.connect(self.run_calculation)
        h.addWidget(run_btn)
        return bar

    def run_calculation(self):
        payload = {
            "Q_req": 100, "H_m": 25, "mat_id": self.in_mat.text() or "clinker",
            "auto_bucket": False, "bucket_id": self.in_bucket.text() or "AC_12x8",
            "D_mm": 500, "n_rpm": 70,
        }
        results = fetch_design(payload)   # ONE fetch
        self.elevation.set_data(payload, results)   # ...fed to both tabs
        self.tree_panel.set_data(payload, results)   # ...no second request


def main():
    app = QApplication(sys.argv)
    window = ShellWindow()
    window.run_calculation()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()