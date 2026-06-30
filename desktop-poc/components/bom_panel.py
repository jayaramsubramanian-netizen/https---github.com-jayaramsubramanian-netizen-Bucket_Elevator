"""
components/bom_panel.py -- Bill of Materials display for the Components tab.
═══════════════════════════════════════════════════════════════════════════
Faithful port of frontend/src/components/BomPanel.jsx, read directly before
writing this (not assumed) -- category grouping/order, collapsible group
headers, line-item layout (qty x tag + description, spec line, notes +
mass line), CSV export, and the footer total all match the real JSX.

Per direct instruction this round: replaces ComponentPanel.jsx's old
tabbed (Belt/Chain, Buckets, Shaft & Bearings, Drive) + separate row-by-row
structural leaf approach entirely. Both panels are now driven by the same
single source of truth -- results.bom's category list -- so the Components
tab (this file) and the Status column (status_design_leaves.py) can never
drift out of sync the way two independently-hand-maintained layouts could.

Confirmed directly before building: results.bom already arrives via the
existing fetch_design() call (no new API wiring needed) -- and three real
gaps were found and fixed in bom.py itself this round (boot shaft and boot
shaft bearing were entirely absent from their categories; the take-up line
was hardcoded to a gravity counterweight regardless of takeup_type) before
any UI was built on top of it.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QScrollArea, QFileDialog,
)
from PySide6.QtCore import Qt

from theme import PANEL, PANEL2, BORDER, TEXT, TEXT2, TEXT3, MUTED, PRIMARY, SUCCESS, WARNING, DANGER, PURPLE, TEAL

# Mirrors BomPanel.jsx's CAT_STYLE exactly -- same category order too,
# which both this file and status_design_leaves.py use as the single
# shared ordering so the two panels never drift apart.
CATEGORY_ORDER = ["SHAFT", "PULLEY", "BELT", "DRIVE", "TAKE-UP", "CASING", "FASTENERS", "BEARINGS", "CHUTE"]

CAT_STYLE = {
    "SHAFT":     {"bg": "rgba(167,139,250,.10)", "color": PURPLE},
    "PULLEY":    {"bg": "rgba(74,158,255,.10)",   "color": PRIMARY},
    "BELT":      {"bg": "rgba(217,142,0,.10)",    "color": WARNING},
    "DRIVE":     {"bg": "rgba(31,184,110,.10)",   "color": SUCCESS},
    "TAKE-UP":   {"bg": "rgba(20,184,166,.10)",   "color": TEAL},
    "CASING":    {"bg": "rgba(148,163,184,.10)",  "color": TEXT2},
    "BEARINGS":  {"bg": "rgba(74,158,255,.10)",   "color": "#60a5fa"},
    "FASTENERS": {"bg": "rgba(148,163,184,.10)",  "color": TEXT2},
    "CHUTE":     {"bg": "rgba(224,82,82,.10)",    "color": DANGER},
}


def fmt(v, dp=1, fb="—"):
    if v is None:
        return fb
    try:
        return f"{float(v):.{dp}f}"
    except (TypeError, ValueError):
        return fb


def kg_to_t(kg):
    if kg is None:
        return "—"
    try:
        kg = float(kg)
    except (TypeError, ValueError):
        return "—"
    return f"{kg / 1000:.2f} t" if kg >= 1000 else f"{kg:.0f} kg"


def category_order_key(cat):
    try:
        return CATEGORY_ORDER.index(cat)
    except ValueError:
        return len(CATEGORY_ORDER)


def group_items(items):
    """Mirrors BomPanel.jsx's groupItems() -- group by category, then sort
    groups by the fixed CATEGORY_ORDER (any unexpected category sorts
    after, alphabetically)."""
    groups = {}
    for item in items:
        groups.setdefault(item.get("category", "—"), []).append(item)
    return sorted(groups.items(), key=lambda kv: (category_order_key(kv[0]), kv[0]))


class _CatBadge(QLabel):
    def __init__(self, cat, parent=None):
        super().__init__(cat, parent)
        s = CAT_STYLE.get(cat, CAT_STYLE["CASING"])
        self.setStyleSheet(
            f"background-color: {s['bg']}; color: {s['color']}; "
            f"border-radius: 999px; padding: 1px 7px; font-size: 8.5px; "
            f"font-weight: 700; letter-spacing: .05em;"
        )


class _GroupHeader(QFrame):
    toggled_signal = None  # set per-instance below

    def __init__(self, cat, items, group_mass, on_toggle, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {PANEL2}; border-bottom: 1px solid {BORDER};")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._on_toggle = on_toggle
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 7, 12, 7)
        layout.setSpacing(8)

        self.arrow = QLabel("▶")
        self.arrow.setStyleSheet(f"color: {TEXT3}; font-size: 8px;")
        layout.addWidget(self.arrow)
        layout.addWidget(_CatBadge(cat))
        name = QLabel(cat)
        name.setStyleSheet(f"color: {TEXT2}; font-size: 11px; font-weight: 700; letter-spacing: .02em;")
        layout.addWidget(name)
        count = QLabel(f"{len(items)} items")
        count.setStyleSheet(f"color: {TEXT2}; font-size: 9.5px;")
        layout.addWidget(count)
        layout.addStretch()
        mass = QLabel(kg_to_t(group_mass))
        mass.setStyleSheet(f"color: {TEXT2}; font-size: 9.5px; font-family: 'JetBrains Mono', monospace;")
        layout.addWidget(mass)

    def mousePressEvent(self, event):
        self._on_toggle()
        super().mousePressEvent(event)

    def set_open(self, open_):
        self.arrow.setText("▼" if open_ else "▶")


def _item_row(item, alt_bg):
    row = QFrame()
    row.setStyleSheet(
        f"background-color: {PANEL2 if alt_bg else 'transparent'}; border-bottom: 1px solid {BORDER};"
    )
    layout = QVBoxLayout(row)
    layout.setContentsMargins(12, 7, 12, 5)
    layout.setSpacing(3)

    line1 = QHBoxLayout()
    line1.setSpacing(8)
    qty = QLabel(f"{item.get('qty', '—')}×")
    qty.setStyleSheet(f"color: {PRIMARY}; font-size: 11px; font-weight: 700; font-family: 'JetBrains Mono', monospace;")
    qty.setMinimumWidth(28)
    line1.addWidget(qty)
    tag = QLabel(str(item.get("tag", "")))
    tag.setStyleSheet(f"color: {TEXT2}; font-size: 9px; font-family: 'JetBrains Mono', monospace;")
    tag.setMinimumWidth(52)
    line1.addWidget(tag)
    desc = QLabel(str(item.get("description", "")))
    desc.setWordWrap(True)
    desc.setStyleSheet(f"color: {TEXT}; font-size: 11px; font-weight: 600;")
    line1.addWidget(desc, 1)
    unit = QLabel(str(item.get("unit", "")))
    unit.setStyleSheet(f"color: {TEXT2}; font-size: 9.5px;")
    line1.addWidget(unit)
    layout.addLayout(line1)

    spec = QLabel(str(item.get("spec", "")))
    spec.setWordWrap(True)
    spec.setStyleSheet(f"color: {TEXT2}; font-size: 10px; font-family: 'JetBrains Mono', monospace; margin-left: 80px;")
    layout.addWidget(spec)

    line3 = QHBoxLayout()
    line3.setContentsMargins(80, 0, 0, 0)
    notes = QLabel(str(item.get("notes", "")))
    notes.setWordWrap(True)
    notes.setStyleSheet(f"color: {TEXT2}; font-size: 9.5px;")
    line3.addWidget(notes, 1)
    mass = QLabel(kg_to_t(item.get("mass_tot_kg")))
    mass.setStyleSheet(f"color: {TEXT2}; font-size: 9.5px; font-family: 'JetBrains Mono', monospace;")
    line3.addWidget(mass)
    layout.addLayout(line3)

    return row


class BomPanel(QWidget):
    """Port of BomPanel.jsx's default export. set_data(inputs, results)
    like every other panel; reads results.bom directly."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {PANEL};")
        self._expanded = set(CATEGORY_ORDER)
        self._bom = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.header = QFrame()
        self.header.setStyleSheet(f"background-color: {PANEL2}; border-bottom: 1px solid {BORDER};")
        hl = QHBoxLayout(self.header)
        hl.setContentsMargins(12, 8, 12, 8)
        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title = QLabel("BILL OF MATERIALS")
        title.setStyleSheet(f"color: {TEXT3}; font-size: 10px; font-weight: 700; letter-spacing: .08em;")
        title_row.addWidget(title)
        self.summary_lbl = QLabel("")
        self.summary_lbl.setStyleSheet(f"color: {TEXT2}; font-size: 9.5px;")
        title_row.addWidget(self.summary_lbl)
        title_row.addStretch()
        title_box.addLayout(title_row)
        hl.addLayout(title_box)
        hl.addStretch()
        self.export_btn = QPushButton("⬇ CSV")
        self.export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_btn.setStyleSheet(
            f"background-color: transparent; color: {TEXT2}; border: 1px solid {BORDER}; "
            f"border-radius: 5px; padding: 4px 10px; font-size: 10px; font-weight: 600;"
        )
        self.export_btn.clicked.connect(self._export_csv)
        hl.addWidget(self.export_btn)
        outer.addWidget(self.header)

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

        self.footer = QFrame()
        self.footer.setStyleSheet(f"background-color: {PANEL2}; border-top: 2px solid {BORDER};")
        fl = QHBoxLayout(self.footer)
        fl.setContentsMargins(12, 10, 12, 10)
        fl_label = QLabel("Estimated total mass (±25% preliminary)")
        fl_label.setStyleSheet(f"color: {TEXT2}; font-size: 10px;")
        fl.addWidget(fl_label)
        fl.addStretch()
        self.total_lbl = QLabel("—")
        self.total_lbl.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: 700; font-family: 'JetBrains Mono', monospace;")
        fl.addWidget(self.total_lbl)
        self.footer.hide()
        outer.addWidget(self.footer)

    def set_data(self, inputs, results):
        results = results or {}
        self._bom = results.get("bom")
        self._rebuild()

    def _rebuild(self):
        while self.body_layout.count():
            item = self.body_layout.takeAt(0)
            w = item.widget() if item else None
            if w:
                w.setParent(None)
                w.deleteLater()

        if not self._bom or not self._bom.get("items"):
            self.summary_lbl.setText("")
            self.footer.hide()
            empty = QLabel("BOM not available — run a calculation first.")
            empty.setStyleSheet(f"color: {TEXT2}; font-size: 11px; font-style: italic; padding: 16px;")
            self.body_layout.addWidget(empty)
            self.body_layout.addStretch()
            return

        bom = self._bom
        summary = bom.get("summary") or {}
        self.summary_lbl.setText(
            f"{summary.get('total_items', 0)} line items · est. {kg_to_t(summary.get('total_mass_kg'))} steel  ·  v{bom.get('version', '—')}"
        )

        for cat, items in group_items(bom["items"]):
            is_open = cat in self._expanded
            group_mass = (summary.get("by_category") or {}).get(cat, {}).get("mass_kg", 0)

            def make_toggle(c=cat):
                def toggle():
                    if c in self._expanded:
                        self._expanded.discard(c)
                    else:
                        self._expanded.add(c)
                    self._rebuild()
                return toggle

            header = _GroupHeader(cat, items, group_mass, make_toggle())
            header.set_open(is_open)
            self.body_layout.addWidget(header)

            if is_open:
                for i, item in enumerate(items):
                    self.body_layout.addWidget(_item_row(item, alt_bg=(i % 2 == 0)))

        notes = bom.get("notes") or []
        if notes:
            notes_box = QFrame()
            nl = QVBoxLayout(notes_box)
            nl.setContentsMargins(12, 10, 12, 10)
            nl.setSpacing(3)
            for note in notes:
                lbl = QLabel(f"·  {note}")
                lbl.setWordWrap(True)
                lbl.setStyleSheet(f"color: {TEXT2}; font-size: 9.5px;")
                nl.addWidget(lbl)
            self.body_layout.addWidget(notes_box)

        self.body_layout.addStretch()
        self.total_lbl.setText(kg_to_t(summary.get("total_mass_kg")))
        self.footer.show()

    def _export_csv(self):
        if not self._bom or not self._bom.get("items"):
            return
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save BOM", "VECTOMEC_BOM.csv", "CSV Files (*.csv)"
        )
        if not save_path:
            return
        import csv
        with open(save_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Pos", "Tag", "Category", "Description", "Qty", "Unit",
                              "Spec", "Mass ea (kg)", "Mass tot (kg)", "Notes"])
            for item in self._bom["items"]:
                writer.writerow([
                    item.get("pos"), item.get("tag"), item.get("category"), item.get("description"),
                    item.get("qty"), item.get("unit"), item.get("spec"),
                    fmt(item.get("mass_ea_kg")), fmt(item.get("mass_tot_kg")), item.get("notes"),
                ])