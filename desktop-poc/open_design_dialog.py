"""
open_design_dialog.py — VECTOMEC™ Open Design File Browser
"""
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QComboBox, QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from theme import PANEL, PANEL2, BORDER, TEXT, TEXT2, TEXT3, PRIMARY, SUCCESS, WARNING, DANGER
from design_file import list_design_files, DesignFile

STAGE_COLORS = {
    1: DANGER, 2: WARNING, 3: PRIMARY, 4: SUCCESS,
}


class OpenDesignDialog(QDialog):
    """Browse, filter, and open saved .vmdesign files.

    self.selected_design_file is set to the loaded DesignFile if the
    user accepts, otherwise None."""

    def __init__(self, designs_dir: Path, parent=None):
        super().__init__(parent)
        self.designs_dir = designs_dir
        self.selected_design_file: DesignFile | None = None
        self._all_entries: list[dict] = []
        self.setWindowTitle("VECTOMEC™ — Open Design")
        self.setModal(True)
        self.setMinimumSize(780, 480)
        self.setStyleSheet(f"background-color:{PANEL};color:{TEXT};")
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Header
        header = QLabel("Open Design")
        header.setStyleSheet(f"color:{TEXT};font-size:14px;font-weight:700;")
        layout.addWidget(header)

        # Filter row
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search by model number...")
        self.search_box.setStyleSheet(
            f"background:{PANEL2};color:{TEXT};border:1px solid {BORDER};"
            f"border-radius:5px;padding:5px 10px;font-size:11px;"
        )
        self.search_box.textChanged.connect(self._apply_filter)
        filter_row.addWidget(self.search_box, 1)

        self.stage_filter = QComboBox()
        self.stage_filter.setStyleSheet(
            f"background:{PANEL2};color:{TEXT};border:1px solid {BORDER};"
            f"border-radius:5px;padding:5px 10px;font-size:11px;"
        )
        self.stage_filter.addItem("All stages", 0)
        for stage, label in [(1,"CONCEPT"),(2,"PRELIMINARY"),(3,"DETAILED"),(4,"RELEASED")]:
            self.stage_filter.addItem(label, stage)
        self.stage_filter.currentIndexChanged.connect(self._apply_filter)
        filter_row.addWidget(self.stage_filter)
        layout.addLayout(filter_row)

        # Table
        cols = ["Model Number", "Version", "Stage", "Modified", "Created By"]
        self.table = QTableWidget(0, len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(False)
        self.table.setStyleSheet(
            f"QTableWidget{{background:{PANEL2};color:{TEXT};border:none;"
            f"gridline-color:{BORDER};font-size:11px;}}"
            f"QHeaderView::section{{background:{PANEL};color:{TEXT2};border:none;"
            f"border-bottom:1px solid {BORDER};padding:7px 8px;"
            f"font-size:9.5px;font-weight:700;letter-spacing:.04em;}}"
            f"QTableWidget::item{{padding:6px 8px;border-bottom:1px solid {BORDER};}}"
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.doubleClicked.connect(self._open_selected)
        self.table.selectionModel().selectionChanged.connect(self._on_selection)
        layout.addWidget(self.table, 1)

        # Footer
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{BORDER};")
        layout.addWidget(sep)

        self.status_lbl = QLabel("No file selected")
        self.status_lbl.setStyleSheet(f"color:{TEXT3};font-size:10px;")
        layout.addWidget(self.status_lbl)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{TEXT2};border:1px solid {BORDER};"
            f"border-radius:5px;padding:7px 18px;font-size:11.5px;}}"
        )
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        self.open_btn = QPushButton("Open")
        self.open_btn.setEnabled(False)
        self.open_btn.setStyleSheet(
            f"QPushButton{{background:{PRIMARY};color:#fff;border:none;border-radius:5px;"
            f"padding:7px 18px;font-size:11.5px;font-weight:700;}}"
            f"QPushButton:disabled{{background:{PANEL2};color:{TEXT3};}}"
        )
        self.open_btn.clicked.connect(self._open_selected)
        btn_row.addWidget(self.open_btn)
        layout.addLayout(btn_row)

    def _load(self):
        self._all_entries = list_design_files(self.designs_dir)
        self._apply_filter()

    def _apply_filter(self):
        query = self.search_box.text().lower()
        stage_filter = self.stage_filter.currentData() or 0
        filtered = [
            e for e in self._all_entries
            if (not query or query in e["model_number"].lower())
            and (not stage_filter or e["stage"] == stage_filter)
        ]
        self.table.setRowCount(len(filtered))
        for row, e in enumerate(filtered):
            stage_color = STAGE_COLORS.get(e["stage"], TEXT2)

            items = [
                (e["model_number"], TEXT, True),
                (f"v{e['version']:03d}", TEXT2, False),
                (e["stage_label"], stage_color, True),
                (e["modified_at"][:16].replace("T", "  "), TEXT2, False),
                (e["created_by"], TEXT2, False),
            ]
            for col, (val, color, bold) in enumerate(items):
                item = QTableWidgetItem(str(val))
                item.setForeground(QColor(color))
                if bold:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                item.setData(Qt.ItemDataRole.UserRole, e["path"])
                self.table.setItem(row, col, item)
            self.table.setRowHeight(row, 36)

        count = len(filtered)
        total = len(self._all_entries)
        suffix = f" (filtered from {total})" if count != total else ""
        self.status_lbl.setText(f"{count} design{'s' if count != 1 else ''} found{suffix}")

    def _on_selection(self):
        selected = self.table.selectedItems()
        self.open_btn.setEnabled(bool(selected))
        if selected:
            path = selected[0].data(Qt.ItemDataRole.UserRole)
            self.status_lbl.setText(str(path))

    def _open_selected(self):
        selected = self.table.selectedItems()
        if not selected:
            return
        path: Path = selected[0].data(Qt.ItemDataRole.UserRole)
        try:
            self.selected_design_file = DesignFile.load(path)
            self.accept()
        except Exception as e:
            self.status_lbl.setText(f"Error loading file: {e}")
            self.status_lbl.setStyleSheet(f"color:{DANGER};font-size:10px;")