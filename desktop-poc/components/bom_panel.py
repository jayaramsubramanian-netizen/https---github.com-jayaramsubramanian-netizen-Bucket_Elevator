"""
components/bom_panel.py -- Bill of Materials display for the Components tab.
═══════════════════════════════════════════════════════════════════════════
Faithful port of frontend/src/components/BomPanel.jsx -- category grouping/
order, collapsible group headers, line-item layout (qty x tag + description,
spec line, notes + mass line), CSV export, and the footer total.

Both this panel and the Status column (status_design_leaves.py) are driven by
the same single source of truth -- results.bom's category list -- so they
cannot drift the way two hand-maintained layouts could. CATEGORY_ORDER and
CAT_STYLE below are the shared definitions; status_design_leaves imports them
from here.

DUPLICATE CLASS DEFINITION -- REMOVED
─────────────────────────────────────
_GroupHeader was defined TWICE in this file, byte-for-byte identical, back to
back. The second definition silently shadowed the first. Harmless at runtime,
but a real trap: an edit to the first copy would have had no effect whatsoever
and the "fix didn't take" would have been baffling. One definition now.

BOX-IN-BOX BORDER SWEEP (this round)
────────────────────────────────────
Every bordered container used a BARE stylesheet declaration (no selector). Qt
treats that as `* { ... }` -- it applies to the widget AND EVERY DESCENDANT:

    _item_row      bare `border-bottom` -> the qty, tag, description, unit,
                   spec, notes and mass labels EACH redrew it. Seven extra
                   rules per line item, across a full BOM.
    _GroupHeader   bare `border-bottom` -> arrow, badge, name, count, mass.
    header/footer  bare `border-bottom` / `border-top` -> their labels and
                   the CSV button.
    export_btn     bare `border: 1px solid` (a QPushButton has no styleable
                   children, so this one was harmless -- converted anyway so
                   no bare-declaration pattern remains to be copied).

Verified directly, not assumed: a QFrame with N child QLabels renders 2N
horizontal border runs inside itself under a bare declaration, and 0 under a
scoped one.

Note also (learned from status_design_leaves.py): `QFrame { border: ... }` is
NOT a safe alternative -- a QSS class selector matches all SUBCLASSES, and
QLabel IS a QFrame subclass. Only an objectName selector binds to one widget.

CAT_STYLE WAS HALF-STALE -- AND IT LEAKED INTO ANOTHER FILE
───────────────────────────────────────────────────────────
CAT_STYLE mixed v1 and v2 in the same table:

    SHAFT    rgba(167,139,250,.10)  -> matches v2 PURPLE   OK
    TAKE-UP  rgba(20,184,166,.10)   -> matches v2 TEAL     OK
    PULLEY   rgba(74,158,255,.10)   -> v1 primary  (v2 = 59,130,246)   STALE
    BELT     rgba(217,142,0,.10)    -> v1 warning  (v2 = 245,158,11)   STALE
    DRIVE    rgba(31,184,110,.10)   -> v1 success  (v2 = 16,185,129)   STALE
    CHUTE    rgba(224,82,82,.10)    -> v1 danger   (v2 = 239,68,68)    STALE
    BEARINGS "#60a5fa"              -> a hardcoded hex in no palette at all

...while the `color` field of each entry imported the v2 token. So four of the
nine badges drew v2-colored text on a v1-colored tint. And because
status_design_leaves.py imports CAT_STYLE from here, that clash propagated
into the Status column's leaf badges too -- one bad table, two panels wrong.

Every tint is now derived from its own theme token via _tint(), so fill and
text are guaranteed to be the same hue. BEARINGS' orphan #60a5fa is replaced
with PRIMARY (it was a lighter blue used to distinguish BEARINGS from PULLEY;
that distinction is preserved by using a stronger tint alpha instead of a
second, untracked blue).

ALSO
────
  * _rebuild()'s clear loop was not recursive -> shared clear_layout().
  * Hardcoded "'JetBrains Mono', monospace" -> theme.FF_MONO.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QScrollArea, QFileDialog,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from theme import (
    PANEL, PANEL2, SURFACE, BORDER, BORDER2, TEXT, TEXT2, TEXT3, MUTED,
    PRIMARY, SUCCESS, WARNING, DANGER, PURPLE, TEAL,
    R_SM, R_PILL, FF_MONO,
    scoped, plain_bg,
)
from .dialog_helpers import clear_layout


def _tint(color_hex, alpha=".10"):
    """rgba() tint derived from a theme color, so a badge's fill and its text
    are always the same hue. Mixing a hardcoded tint with an imported text
    color is exactly what made four of these badges two-toned."""
    c = QColor(color_hex)
    return f"rgba({c.red()},{c.green()},{c.blue()},{alpha})"


# Shared ordering -- status_design_leaves.py imports this so the two panels
# present categories identically.
CATEGORY_ORDER = ["SHAFT", "PULLEY", "BELT", "DRIVE", "TAKE-UP",
                  "CASING", "FASTENERS", "BEARINGS", "CHUTE"]

# Mirrors BomPanel.jsx's CAT_STYLE. Every tint now derives from the same theme
# token as its text color -- see the module docstring for what was wrong.
CAT_STYLE = {
    "SHAFT":     {"bg": _tint(PURPLE),          "color": PURPLE},
    "PULLEY":    {"bg": _tint(PRIMARY),         "color": PRIMARY},
    "BELT":      {"bg": _tint(WARNING),         "color": WARNING},
    "DRIVE":     {"bg": _tint(SUCCESS),         "color": SUCCESS},
    "TAKE-UP":   {"bg": _tint(TEAL),            "color": TEAL},
    "CASING":    {"bg": _tint(TEXT3),           "color": TEXT2},
    # BEARINGS shares PULLEY's blue but at a stronger tint, rather than
    # introducing a second, untracked blue (#60a5fa) that no palette owns.
    "BEARINGS":  {"bg": _tint(PRIMARY, ".18"),  "color": PRIMARY},
    "FASTENERS": {"bg": _tint(TEXT3),           "color": TEXT2},
    "CHUTE":     {"bg": _tint(DANGER),          "color": DANGER},
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
    groups by the fixed CATEGORY_ORDER (any unexpected category sorts after,
    alphabetically)."""
    groups = {}
    for item in items:
        groups.setdefault(item.get("category", "—"), []).append(item)
    return sorted(groups.items(),
                  key=lambda kv: (category_order_key(kv[0]), kv[0]))


class _CatBadge(QLabel):
    def __init__(self, cat, parent=None):
        super().__init__(cat, parent)
        s = CAT_STYLE.get(cat, CAT_STYLE["CASING"])
        self.setStyleSheet(scoped(
            self,
            f"background-color: {s['bg']}; color: {s['color']}; border: none; "
            f"border-radius: {R_PILL}px; padding: 1px 7px; font-size: 8.5px; "
            f"font-weight: 700; letter-spacing: .05em;"
        ))


class _GroupHeader(QFrame):
    """Collapsible category header.

    (This class was previously declared TWICE, identically -- the second copy
    shadowed the first. See module docstring.)

    SCOPED: the bare `border-bottom` was inherited by the arrow, the category
    badge, the name, the item count and the mass label."""

    def __init__(self, cat, items, group_mass, on_toggle, parent=None):
        super().__init__(parent)
        self.setStyleSheet(scoped(
            self,
            f"background-color: {PANEL2}; border: none; "
            f"border-bottom: 1px solid {BORDER};",
            extra="{sel}:hover { background-color: rgba(255,255,255,.03); }",
        ))
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
        name.setStyleSheet(
            f"color: {TEXT2}; font-size: 11px; font-weight: 700; "
            f"letter-spacing: .02em;")
        layout.addWidget(name)

        count = QLabel(f"{len(items)} items")
        count.setStyleSheet(f"color: {TEXT2}; font-size: 9.5px;")
        layout.addWidget(count)
        layout.addStretch()

        mass = QLabel(kg_to_t(group_mass))
        mass.setStyleSheet(
            f"color: {TEXT2}; font-size: 9.5px; font-family: {FF_MONO};")
        layout.addWidget(mass)

    def mousePressEvent(self, event):
        self._on_toggle()
        super().mousePressEvent(event)

    def set_open(self, open_):
        self.arrow.setText("▼" if open_ else "▶")


def _item_row(item, alt_bg):
    """SCOPED: the bare `border-bottom` here was inherited by SEVEN labels --
    qty, tag, description, unit, spec, notes and mass -- so every BOM line
    item drew eight horizontal rules instead of one."""
    row = QFrame()
    row.setStyleSheet(scoped(
        row,
        f"background-color: {PANEL2 if alt_bg else 'transparent'}; "
        f"border: none; border-bottom: 1px solid {BORDER};"
    ))
    layout = QVBoxLayout(row)
    layout.setContentsMargins(12, 7, 12, 5)
    layout.setSpacing(3)

    line1 = QHBoxLayout()
    line1.setSpacing(8)
    qty = QLabel(f"{item.get('qty', '—')}×")
    qty.setStyleSheet(
        f"color: {PRIMARY}; font-size: 11px; font-weight: 700; "
        f"font-family: {FF_MONO};")
    qty.setMinimumWidth(28)
    line1.addWidget(qty)

    tag = QLabel(str(item.get("tag", "")))
    tag.setStyleSheet(f"color: {TEXT2}; font-size: 9px; font-family: {FF_MONO};")
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
    spec.setStyleSheet(
        f"color: {TEXT2}; font-size: 10px; font-family: {FF_MONO}; "
        f"margin-left: 80px;")
    layout.addWidget(spec)

    line3 = QHBoxLayout()
    line3.setContentsMargins(80, 0, 0, 0)
    notes = QLabel(str(item.get("notes", "")))
    notes.setWordWrap(True)
    notes.setStyleSheet(f"color: {TEXT2}; font-size: 9.5px;")
    line3.addWidget(notes, 1)
    mass = QLabel(kg_to_t(item.get("mass_tot_kg")))
    mass.setStyleSheet(
        f"color: {TEXT2}; font-size: 9.5px; font-family: {FF_MONO};")
    line3.addWidget(mass)
    layout.addLayout(line3)

    return row


class BomPanel(QWidget):
    """Port of BomPanel.jsx's default export. set_data(inputs, results) like
    every other panel; reads results.bom directly."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(plain_bg(self, PANEL))
        self._expanded = set(CATEGORY_ORDER)
        self._bom = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.header = QFrame()
        self.header.setStyleSheet(scoped(
            self.header,
            f"background-color: {PANEL2}; border: none; "
            f"border-bottom: 1px solid {BORDER};"
        ))
        hl = QHBoxLayout(self.header)
        hl.setContentsMargins(12, 8, 12, 8)
        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title = QLabel("BILL OF MATERIALS")
        title.setStyleSheet(
            f"color: {TEXT3}; font-size: 10px; font-weight: 700; "
            f"letter-spacing: .08em;")
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
        self.export_btn.setStyleSheet(scoped(
            self.export_btn,
            f"background-color: transparent; color: {TEXT2}; "
            f"border: 1px solid {BORDER2}; border-radius: {R_SM - 1}px; "
            f"padding: 4px 10px; font-size: 10px; font-weight: 600;",
            extra="{sel}:hover { background-color: %s; color: %s; }" % (SURFACE, TEXT),
        ))
        self.export_btn.clicked.connect(self._export_csv)
        hl.addWidget(self.export_btn)
        outer.addWidget(self.header)

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

        self.footer = QFrame()
        self.footer.setStyleSheet(scoped(
            self.footer,
            f"background-color: {PANEL2}; border: none; "
            f"border-top: 2px solid {BORDER};"
        ))
        fl = QHBoxLayout(self.footer)
        fl.setContentsMargins(12, 10, 12, 10)
        fl_label = QLabel("Estimated total mass (±25% preliminary)")
        fl_label.setStyleSheet(f"color: {TEXT2}; font-size: 10px;")
        fl.addWidget(fl_label)
        fl.addStretch()
        self.total_lbl = QLabel("—")
        self.total_lbl.setStyleSheet(
            f"color: {TEXT}; font-size: 13px; font-weight: 700; "
            f"font-family: {FF_MONO};")
        fl.addWidget(self.total_lbl)
        self.footer.hide()
        outer.addWidget(self.footer)

    def set_data(self, inputs, results):
        results = results or {}
        self._bom = results.get("bom")
        self._rebuild()

    def _rebuild(self):
        clear_layout(self.body_layout)

        if not self._bom or not self._bom.get("items"):
            self.summary_lbl.setText("")
            self.footer.hide()
            empty = QLabel("BOM not available — run a calculation first.")
            empty.setStyleSheet(
                f"color: {TEXT2}; font-size: 11px; font-style: italic; padding: 16px;")
            self.body_layout.addWidget(empty)
            self.body_layout.addStretch()
            return

        bom = self._bom
        summary = bom.get("summary") or {}
        self.summary_lbl.setText(
            f"{summary.get('total_items', 0)} line items · "
            f"est. {kg_to_t(summary.get('total_mass_kg'))} steel  ·  "
            f"v{bom.get('version', '—')}"
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
            notes_box.setStyleSheet(scoped(
                notes_box, "background-color: transparent; border: none;"))
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
            writer.writerow(["Pos", "Tag", "Category", "Description", "Qty",
                             "Unit", "Spec", "Mass ea (kg)", "Mass tot (kg)",
                             "Notes"])
            for item in self._bom["items"]:
                writer.writerow([
                    item.get("pos"), item.get("tag"), item.get("category"),
                    item.get("description"), item.get("qty"), item.get("unit"),
                    item.get("spec"), fmt(item.get("mass_ea_kg")),
                    fmt(item.get("mass_tot_kg")), item.get("notes"),
                ])