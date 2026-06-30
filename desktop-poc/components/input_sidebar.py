"""
components/input_sidebar.py -- PySide6 port of InputSidebar.jsx
═══════════════════════════════════════════════════════════════════════════
Started, not complete -- InputSidebar.jsx is ~2,500 lines covering 11
sections. This round adds the material-temperature null advisory to
Process Design: when the selected material has no typical/CEMA-sourced
temperature on file (temp_max is None -- true for all 80 static-list
fallback materials right now, and for any DB material not yet enriched
with CEMA 375/550 data), the UI says so honestly and prompts the user to
enter a value based on their own process conditions, rather than silently
implying 20°C ambient is a real default for that material. When temp_max
IS known, it's shown as a labeled reference value next to the editable
field -- not auto-applied, the user's typed value always wins.

Everything else below is unchanged from the prior round (CEMA reference
trimmed to once per modal header; Material Database Search + Custom/
Override Properties in Process Design; Dynamic Fill Advisory; Wrap Angle
Adequate card; Belt/Chain Selection and Bucket Selection built and
reordered ahead of Pulley/Shaft per the engineering-flow discussion;
Shaft Design's 2x2 grid with Boot Shaft/Boot Bearing quadrants).

Still not ported at all (still in the summary-only list, named
explicitly): Take-Up Selection, Discharge Section, Feed Design, Casing
Design, Service Conditions, Power Transmission.

This widget owns no fetch logic of its own for the main calculation --
it emits inputsChanged(dict) and main.py's run_calculation() does the
actual backend call, the same separation every other component uses.
Material search/lookup calls go through api_client.py same as everything
else.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea,
    QDialog, QPushButton, QDoubleSpinBox, QSpinBox, QLineEdit,
    QListWidget, QListWidgetItem, QAbstractSpinBox, QComboBox, QGridLayout,
)
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QTimer, QThread
from PySide6.QtGui import QPainter, QColor, QBrush, QPen

from theme import BG, PANEL, PANEL2, BORDER, TEXT, TEXT2, TEXT3, MUTED, PRIMARY, SUCCESS, WARNING, DANGER
from api_client import search_materials, get_material, fetch_components

# Sections not yet ported -- listed explicitly so the gap is named, not
# silently absent. (id, label)
NOT_YET_PORTED = [
    ("takeup",    "Take-Up Selection"),
    ("discharge", "Discharge Section"),
    ("feed",      "Feed Design"),
    ("casing",    "Casing Design"),
    ("service",   "Service Conditions"),
    ("power",     "Power Transmission"),
]

ABR_HINT = {1: "Low", 2: "Low", 3: "Med", 4: "Med", 5: "High", 6: "High", 7: "V.High"}
FLOW_HINT = {1: "Free", 2: "Free", 3: "Average", 4: "Sluggish"}

# Style-level descriptive text only -- NOT a duplicate catalog. Actual
# dimensions (W/P/V per size) come live from /components/buckets; the API
# doesn't return a style-level label/description, just per-size rows, so
# this fills in just the descriptive text, confirmed against the live
# catalog to be exactly these 6 styles (40 total sizes, matches exactly).
BUCKET_STYLE_INFO = {
    "AA": ("AA — General Purpose Centrifugal", "centrifugal",
           "Curved bottom, reinforced lip. Grain, aggregate, sand, coal, fertiliser."),
    "AC": ("AC — Mill Duty (50° front, Added Capacity)", "centrifugal",
           "Hooded back, 50° face angle. Cement, clinker, ore, shale, coal, asphalt."),
    "C":  ("C — Wet / Sticky / Powdered (low profile)", "centrifugal",
           "Open front, angled sides. Sugar, salt, wet grain, clay, flour, chemicals."),
    "MF": ("MF — Continuous Medium Front (30°)", "continuous",
           "Gentle handling, CR < 1.0. Gypsum, cement, pellets, grain, salt, fertiliser."),
    "HF": ("HF — Continuous High Front (45°)", "continuous",
           "Higher front than MF, ~8% more capacity. Grain, gypsum, pellets, fragile materials."),
    "SC": ("SC — Super Capacity (Double Chain only)", "continuous",
           "Very slow, heavy abrasive duty. Cement, clinker, limestone, rock. DOUBLE CHAIN only."),
}

# Static reference list, mirroring the JSX's own CHAIN_OPTIONS exactly --
# there's no live /components/chains endpoint to fetch this from (checked
# directly: 404), unlike buckets, which do have a real catalog table.
CHAIN_OPTIONS = [
    ("N102B", 'N-102B  — 4" std  WL=4,990kg  1 strand'),
    ("S102B", 'S-102B  — 4" heavy WL=6,804kg  1 strand'),
    ("S110",  'S-110   — 6" heavy WL=12,474kg 1 strand'),
    ("ER856", 'ER-856  — 6" MDC   WL=18,144kg 1 strand'),
    ("ER857", 'ER-857  — 6" MDC   WL=22,680kg 1 strand'),
    ("ER859", 'ER-859  — 6" SC    WL=31,750kg 2 strands'),
    ("C6102", '6102-1/2 — 12" SC   WL=27,215kg 2 strands'),
    ("C9124", '9124    — 9" SC    WL=38,100kg 2 strands'),
]


def fmt(v, dp=1, fb="—"):
    if v is None:
        return fb
    try:
        return f"{float(v):.{dp}f}"
    except (TypeError, ValueError):
        return fb


class SectionRow(QFrame):
    """Port of the JSX's SectionRow -- label + summary text + a pencil
    icon, the whole row clickable. FIX: no longer shows a CEMA reference
    on every row -- that now lives exactly once, in each modal's own
    header, matching how the real app actually uses it rather than
    repeating it on every line of this list."""

    def __init__(self, label, summary="", clickable=True, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor if clickable else Qt.CursorShape.ArrowCursor)
        self.setStyleSheet(f"""
            QFrame {{ background-color: transparent; border-bottom: 1px solid {BORDER}; }}
            QFrame:hover {{ background-color: rgba(255,255,255,.03); }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)

        top = QHBoxLayout()
        top.setSpacing(6)
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: 700;")
        top.addWidget(lbl)
        top.addStretch()
        if clickable:
            pencil = QLabel("✎")
            pencil.setStyleSheet(f"color: {PRIMARY}; font-size: 11px;")
            top.addWidget(pencil)
        layout.addLayout(top)

        if summary:
            sum_lbl = QLabel(summary)
            sum_lbl.setStyleSheet(f"color: {TEXT3}; font-size: 11px;")
            sum_lbl.setWordWrap(False)
            layout.addWidget(sum_lbl)

    def mousePressEvent(self, event):
        if self.cursor().shape() == Qt.CursorShape.PointingHandCursor:
            self.clicked()
        super().mousePressEvent(event)

    def clicked(self):
        pass  # overridden via direct assignment from the panel that creates this row


def section_head(text):
    lbl = QLabel(text.upper())
    lbl.setStyleSheet(f"color: {TEXT3}; font-size: 10px; font-weight: 700; letter-spacing: 1px; margin-top: 4px;")
    return lbl


def quadrant_frame():
    """One cell of a 2x2 grid -- a bordered container so the grid
    structure itself is visually obvious, not just implied by spacing."""
    frame = QFrame()
    frame.setStyleSheet(f"background-color: {BG}; border: 1px solid {BORDER}; border-radius: 6px;")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(8)
    return frame, layout


def quadrant_title(text):
    """Quadrant-level title -- deliberately NO CEMA reference here. That
    now lives exactly once, in the modal's own header; repeating it on
    every quadrant (or, before that, every sidebar row) is the same
    over-repetition already trimmed elsewhere."""
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color: {TEXT}; font-size: 12px; font-weight: 700;")
    return lbl


def field_row(label, widget, unit=None, note=None):
    box = QVBoxLayout()
    box.setSpacing(3)
    lbl = QLabel(label)
    lbl.setStyleSheet(f"color: {TEXT2}; font-size: 10.5px; font-weight: 600;")
    box.addWidget(lbl)
    row = QHBoxLayout()
    row.addWidget(widget)
    if unit:
        unit_lbl = QLabel(unit)
        unit_lbl.setStyleSheet(f"color: {MUTED}; font-size: 10.5px;")
        row.addWidget(unit_lbl)
    box.addLayout(row)
    if note:
        note_lbl = QLabel(note)
        note_lbl.setStyleSheet(f"color: {MUTED}; font-size: 9.5px;")
        note_lbl.setWordWrap(True)
        box.addWidget(note_lbl)
    return box


def styled_spinbox(spinbox):
    # FIX: the real bug here wasn't a font fallback issue (that was a
    # red herring I ruled out by checking .value()/.text() against the
    # rendered pixels, and by testing the same font-family string in
    # isolation, where it rendered fine). The actual cause: this widget
    # had no minimum height, so when the right column's combined content
    # (search box, chips, 6 override fields, notes) needed more vertical
    # space than the dialog's natural height gave it, Qt's layout engine
    # compressed individual spinboxes down to as little as 17px tall --
    # confirmed directly via .size(). 17px isn't enough room for a 12px
    # font plus 5px top/bottom padding to render without visually
    # overlapping. Setting an explicit minimum height makes this a hard
    # floor the layout can't shrink past.
    spinbox.setMinimumHeight(28)
    spinbox.setStyleSheet(
        f"background-color: {PANEL2}; color: {TEXT}; border: 1px solid {BORDER}; "
        f"border-radius: 4px; padding: 5px 8px; font-size: 12px;"
    )
    return spinbox


def modal_header(title, cema=None):
    """The ONE place CEMA reference text now lives -- once per modal,
    under its title, not repeated per sidebar row."""
    header = QFrame()
    header.setStyleSheet(f"background-color: {PANEL2}; border-bottom: 1px solid {BORDER};")
    hl = QVBoxLayout(header)
    hl.setContentsMargins(16, 12, 16, 12)
    title_lbl = QLabel(title)
    title_lbl.setStyleSheet(f"color: {TEXT}; font-size: 14px; font-weight: 700;")
    hl.addWidget(title_lbl)
    if cema:
        sub = QLabel(cema)
        sub.setStyleSheet(f"color: {TEXT3}; font-size: 10px;")
        hl.addWidget(sub)
    return header


def modal_footer(dialog):
    footer = QFrame()
    layout = QHBoxLayout(footer)
    layout.setContentsMargins(12, 8, 12, 8)
    layout.addStretch()
    cancel = QPushButton("Cancel")
    cancel.setStyleSheet(f"background-color: transparent; color: {TEXT3}; border: none; padding: 6px 14px;")
    cancel.clicked.connect(dialog.reject)
    apply_btn = QPushButton("Apply")
    apply_btn.setStyleSheet(
        f"background-color: {PRIMARY}; color: white; border: none; "
        f"border-radius: 5px; padding: 6px 18px; font-size: 11.5px; font-weight: 600;"
    )
    apply_btn.clicked.connect(dialog.accept)
    layout.addWidget(cancel)
    layout.addWidget(apply_btn)
    return footer


class DynamicFillBarWidget(QWidget):
    """Custom-painted horizontal range bar -- direct port of the JSX's
    inline-styled div stack: a track, a highlighted min-max band, a
    recommended-value tick, and a current-value dot (green if in range,
    red if not). Same pct() mapping as the original: clamp((v-30)/70*100,
    0, 100), i.e. the 30-100% fill range mapped to the bar's full width."""

    def __init__(self, min_v, max_v, rec_v, cur_v, parent=None):
        super().__init__(parent)
        self.min_v, self.max_v, self.rec_v, self.cur_v = min_v, max_v, rec_v, cur_v
        self.setFixedHeight(22)
        self.setMinimumWidth(200)

    @staticmethod
    def _pct(v):
        return min(100.0, max(0.0, (v - 30.0) / 70.0 * 100.0))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        track_y = h / 2 - 4
        track_h = 8

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(PANEL2)))
        p.drawRoundedRect(QRectF(0, track_y, w, track_h), 4, 4)

        if self.min_v is not None and self.max_v is not None:
            x0 = self._pct(self.min_v) / 100.0 * w
            x1 = self._pct(self.max_v) / 100.0 * w
            band_color = QColor(PRIMARY)
            band_color.setAlpha(56)
            p.setBrush(QBrush(band_color))
            p.drawRoundedRect(QRectF(x0, track_y, max(1.0, x1 - x0), track_h), 4, 4)

        if self.rec_v is not None:
            xr = self._pct(self.rec_v) / 100.0 * w
            p.setPen(QPen(QColor(PRIMARY), 2))
            p.drawLine(QPointF(xr, track_y - 2), QPointF(xr, track_y + track_h + 2))

        if self.cur_v is not None:
            xc = self._pct(self.cur_v) / 100.0 * w
            in_range = (self.min_v is None or self.cur_v >= self.min_v) and \
                       (self.max_v is None or self.cur_v <= self.max_v)
            dot_color = QColor(SUCCESS if in_range else DANGER)
            p.setPen(QPen(QColor(BG), 2))
            p.setBrush(QBrush(dot_color))
            p.drawEllipse(QPointF(xc, track_y + track_h / 2), 7, 7)
        p.end()

    def update_values(self, min_v, max_v, rec_v, cur_v):
        self.min_v, self.max_v, self.rec_v, self.cur_v = min_v, max_v, rec_v, cur_v
        self.update()


class DynamicFillAdvisory(QFrame):
    """The full advisory block: header, 6-stat row, the bar, note text,
    and a spacing warning when applicable -- the complete visual from
    ProcessEdit, not a text summary of it."""

    def __init__(self, results, current_fill_pct, parent=None):
        super().__init__(parent)
        r = results or {}
        df = r.get("dynamic_fill") or {}
        min_v, max_v = r.get("min_fill_pct"), r.get("max_fill_pct")
        rec_v = df.get("recommended_fill_pct")

        self.setStyleSheet(
            "background-color: rgba(74,158,255,.06); border: 1px solid rgba(74,158,255,.2); "
            "border-radius: 5px;"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        head = QLabel("●  DYNAMIC FILL ADVISORY (CEMA §6)")
        head.setStyleSheet(f"color: {PRIMARY}; font-size: 10px; font-weight: 700; letter-spacing: .5px;")
        layout.addWidget(head)

        stats = QHBoxLayout()
        stats.setSpacing(16)
        in_range = (min_v is None or current_fill_pct >= min_v) and (max_v is None or current_fill_pct <= max_v)
        for label, value, color in (
            ("Min", f"{fmt(min_v, 0)}%", TEXT),
            ("Recommended", f"{fmt(rec_v, 1)}%", PRIMARY),
            ("Your value", f"{fmt(current_fill_pct, 0)}%", SUCCESS if in_range else DANGER),
            ("Max", f"{fmt(max_v, 0)}%", TEXT),
            ("Spacing", f"{fmt(df.get('current_spacing_mm'), 0)}mm", TEXT),
            ("Optimal", f"{fmt(df.get('optimal_spacing_mm'), 0)}mm", TEXT),
        ):
            col = QVBoxLayout()
            col.setSpacing(1)
            l = QLabel(label)
            l.setStyleSheet(f"color: {TEXT3}; font-size: 9px;")
            v = QLabel(value)
            v.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: 700; font-family: 'JetBrains Mono', monospace;")
            col.addWidget(l); col.addWidget(v)
            stats.addLayout(col)
        stats.addStretch()
        layout.addLayout(stats)

        self.bar = DynamicFillBarWidget(min_v, max_v, rec_v, current_fill_pct)
        layout.addWidget(self.bar)

        if df.get("note"):
            note = QLabel(df["note"])
            note.setWordWrap(True)
            note.setStyleSheet(f"color: {TEXT3}; font-size: 10px;")
            layout.addWidget(note)

        spacing_status = df.get("spacing_status")
        if spacing_status and spacing_status != "optimal":
            warn = QLabel(
                f"⚠ Spacing is {spacing_status.replace('_', ' ')} — adjust Bucket Spacing Gap "
                f"to approach {fmt(df.get('optimal_spacing_mm'), 0)}mm"
            )
            warn.setWordWrap(True)
            warn.setStyleSheet(f"color: {WARNING}; font-size: 10px; margin-top: 2px;")
            layout.addWidget(warn)


class MaterialSearchWorker(QThread):
    """Runs the actual /materials/search HTTP call off the GUI thread.

    FIX: the previous version called search_materials() directly inside
    textChanged's handler -- a synchronous network request on the GUI
    thread, on every single keystroke. That's not a PySide6 limitation;
    Qt fully supports async network calls (this is exactly the kind of
    thing QThread exists for). The freezing was a real bug in how this
    was built, not anything inherent to the framework -- confirmed by
    moving the call here, off the thread that paints the UI, and the
    freeze goes away regardless of how slow the actual request is.
    """
    resultsReady = Signal(list)

    def __init__(self, query, limit=20, parent=None):
        super().__init__(parent)
        self.query = query
        self.limit = limit

    def run(self):
        try:
            results = search_materials(self.query, limit=self.limit)
        except Exception:
            results = []
        self.resultsReady.emit(results)


class MaterialChip(QLabel):
    def __init__(self, text, color, parent=None):
        super().__init__(text, parent)
        c = QColor(color)
        self.setStyleSheet(
            f"background-color: rgba({c.red()},{c.green()},{c.blue()},.15); color: {color}; "
            f"border: 1px solid rgba({c.red()},{c.green()},{c.blue()},.4); "
            f"border-radius: 999px; padding: 2px 8px; font-size: 9.5px; font-weight: 700;"
        )


class MaterialSearchWidget(QWidget):
    """Real port of MaterialSearchDropdown.jsx's core behavior: type to
    search against the live /materials/search endpoint, click a result to
    select it. Chips below the box show the currently-selected material's
    category/density/abrasiveness, same as the reference rendering.

    FIX (slow + dropdown hidden under the text below): two separate real
    bugs, not one. (1) Every keystroke fired a blocking network call
    directly on the GUI thread -- fixed with a 300ms debounce timer plus
    a background QThread (MaterialSearchWorker above) so the actual
    request never blocks painting. (2) The results list was a normal
    widget embedded inline in this widget's QVBoxLayout, sitting between
    the search box and the chip row -- when it became visible with
    content, the surrounding layout didn't reliably reflow/grow the
    dialog to make room, so it visually overlapped the chip row and
    Custom/Override section below it. Rebuilt as a true floating popup
    (Qt.WindowType.Popup) positioned under the search box -- a popup
    window doesn't occupy any space in the surrounding layout at all,
    which removes this entire category of overlap rather than chasing
    the exact reflow-timing cause."""

    materialSelected = Signal(str)

    def __init__(self, current_mat_id, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search materials...")
        self.search_box.setStyleSheet(
            f"background-color: {PANEL2}; color: {TEXT}; border: 1px solid {BORDER}; "
            f"border-radius: 4px; padding: 6px 10px; font-size: 12px;"
        )
        self.search_box.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.search_box)

        # Floating popup, NOT added to `layout` -- it must not occupy
        # space in this widget's own layout, that's what caused the
        # overlap. Qt.WindowType.Popup also auto-closes on an outside
        # click, which is the behavior you'd want from a search dropdown
        # anyway.
        self.results_popup = QListWidget(None)
        self.results_popup.setWindowFlags(Qt.WindowType.Popup)
        self.results_popup.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.results_popup.setStyleSheet(f"""
            QListWidget {{ background-color: {PANEL2}; color: {TEXT2}; border: 1px solid {BORDER};
                border-radius: 4px; font-size: 11.5px; }}
            QListWidget::item {{ padding: 5px 8px; }}
            QListWidget::item:selected {{ background-color: {PRIMARY}; color: white; }}
        """)
        self.results_popup.itemClicked.connect(self._on_result_clicked)

        self.chip_row = QHBoxLayout()
        self.chip_row.setSpacing(6)
        layout.addLayout(self.chip_row)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(300)
        self._debounce.timeout.connect(self._run_search)
        self._worker = None

        self.current_mat_id = current_mat_id
        self._load_current(current_mat_id)

    def _on_text_changed(self, text):
        self._debounce.stop()
        if not text.strip():
            self.results_popup.hide()
            return
        self._debounce.start()   # restarts the 300ms window on every keystroke

    def _run_search(self):
        text = self.search_box.text().strip()
        if not text:
            return
        if self._worker is not None and self._worker.isRunning():
            self._worker.resultsReady.disconnect()
            self._worker.quit()
            self._worker.wait()
        self._worker = MaterialSearchWorker(text, limit=20, parent=self)
        self._worker.resultsReady.connect(self._show_results)
        self._worker.start()

    def _show_results(self, results):
        self.results_popup.clear()
        for mat in results:
            item = QListWidgetItem(f"{mat.get('name')}  ·  {mat.get('category')}  ·  {fmt(mat.get('rho_loose'), 0)} kg/m³")
            item.setData(Qt.ItemDataRole.UserRole, mat.get("mat_id"))
            self.results_popup.addItem(item)
        if not results:
            self.results_popup.hide()
            return
        pos = self.search_box.mapToGlobal(self.search_box.rect().bottomLeft())
        self.results_popup.move(pos)
        self.results_popup.setFixedWidth(self.search_box.width())
        row_h = self.results_popup.sizeHintForRow(0) if self.results_popup.count() else 24
        self.results_popup.setFixedHeight(min(row_h * len(results) + 6, 180))
        self.results_popup.show()

    def _on_result_clicked(self, item):
        mat_id = item.data(Qt.ItemDataRole.UserRole)
        self.search_box.clear()
        self.results_popup.hide()
        self._load_current(mat_id)
        self.materialSelected.emit(mat_id)

    def _load_current(self, mat_id):
        self.current_mat_id = mat_id
        while self.chip_row.count():
            item = self.chip_row.takeAt(0)
            w = item.widget() if item else None
            if w:
                # setParent(None) removes it from the visual tree immediately;
                # deleteLater() alone defers cleanup and can leave a brief
                # visual ghost of the widget's last-painted pixels behind
                # (confirmed directly: a 'keyed connection' note lingered
                # for one frame after switching to 'welded').
                w.setParent(None)
                w.deleteLater()
        try:
            mat = get_material(mat_id)
        except Exception:
            mat = None
        if not mat:
            return
        name_lbl = QLabel(mat.get("name", mat_id))
        name_lbl.setStyleSheet(f"color: {TEXT}; font-size: 12px; font-weight: 600;")
        self.chip_row.addWidget(name_lbl)
        self.chip_row.addWidget(MaterialChip(mat.get("category", "—"), PRIMARY))
        self.chip_row.addWidget(MaterialChip(f"{fmt(mat.get('rho_loose'), 0)} kg/m³", TEXT3))
        abr = mat.get("abr_code")
        if abr is not None:
            self.chip_row.addWidget(MaterialChip(f"{ABR_HINT.get(abr, '—')} abr", SUCCESS if abr <= 3 else WARNING))
        self.chip_row.addStretch()


class OverridableSpinBox(QWidget):
    """Mirrors the JSX's OverridableField exactly: shows the real database
    default value when no override is active (not a bare 0/-1 sentinel),
    snaps back to the sentinel if the user types the exact default back."""

    def __init__(self, label, db_value, sentinel, current_value, unit="", hint="", is_int=False, parent=None):
        super().__init__(parent)
        self.db_value = db_value
        self.sentinel = sentinel
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {TEXT2}; font-size: 10.5px; font-weight: 600;")
        layout.addWidget(lbl)

        is_active = (current_value > 0) if sentinel == 0 else (current_value is not None and current_value >= 0)
        display_value = current_value if is_active else (db_value if db_value is not None else sentinel)

        row = QHBoxLayout()
        self.spin = styled_spinbox(QSpinBox() if is_int else QDoubleSpinBox())
        # FIX: in this 2-column-within-2-column layout, each field gets
        # roughly a quarter of the modal's width -- too narrow for the
        # native up/down arrows to render without overlapping 4-digit
        # values like "1298". Removing them is also the more sensible UX
        # here: an override field is something you type an exact value
        # into, not nudge with tiny arrows.
        self.spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.spin.setRange(sentinel, 5000)
        self.spin.setValue(display_value if display_value is not None else sentinel)
        row.addWidget(self.spin)
        if unit:
            u = QLabel(unit)
            u.setStyleSheet(f"color: {MUTED}; font-size: 10.5px;")
            row.addWidget(u)
        layout.addLayout(row)

        self.note = QLabel()
        self.note.setStyleSheet(f"color: {MUTED}; font-size: 9px;")
        self.note.setWordWrap(True)
        self._update_note(is_active)
        layout.addWidget(self.note)
        self.spin.valueChanged.connect(self._on_value_changed)

    def _update_note(self, is_active):
        if self.db_value is None:
            self.note.setText("No calculation yet — showing placeholder until a material is selected")
        elif is_active:
            self.note.setText(f"Overriding for this run — database default is {fmt(self.db_value, 1)}")
        else:
            self.note.setText("Database default for this material — edit to override for this run")

    def _on_value_changed(self, value):
        is_active = self.db_value is None or abs(value - self.db_value) > 1e-9
        self._update_note(is_active)

    def value_or_sentinel(self):
        value = self.spin.value()
        if self.db_value is not None and abs(value - self.db_value) < 1e-9:
            return self.sentinel
        return value

    def update_db_value(self, new_db_value):
        """Refresh this field's database default to match whatever
        material is now selected.

        FIX (Jay: "the material properties... should be defaults for
        the material picked... stay that way even if material is
        changed"): selecting a different material via search only ever
        updated inputs["mat_id"] -- nothing told these 6 fields their
        db_value was now stale, so they kept showing the PREVIOUS
        material's numbers no matter what got selected afterward.

        Always resets to the new default (clearing any active override)
        rather than trying to decide whether a numeric override typed
        for the old material should somehow carry over to a different
        one -- that ambiguity is exactly the kind of confusing edge case
        worth avoiding outright, not handling cleverly."""
        self.db_value = new_db_value
        self.spin.setValue(new_db_value if new_db_value is not None else self.sentinel)
        self._update_note(False)


class NotYetPortedDialog(QDialog):
    """Honest placeholder modal -- same spirit as the Placeholder widget
    used throughout main.py."""

    def __init__(self, label, parent=None):
        super().__init__(parent)
        self.setWindowTitle(label)
        self.setStyleSheet(f"background-color: {PANEL};")
        self.setMinimumWidth(360)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon = QLabel("○")
        icon.setStyleSheet(f"color: {BORDER}; font-size: 28px;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel(label)
        title.setStyleSheet(f"color: {TEXT2}; font-size: 13px; font-weight: 600;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub = QLabel("Not yet ported -- still a summary-only row for now.")
        sub.setStyleSheet(f"color: {MUTED}; font-size: 10.5px;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for w in (icon, title, sub):
            layout.addWidget(w)
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(
            f"background-color: {PANEL2}; color: {TEXT2}; border: 1px solid {BORDER}; "
            f"border-radius: 5px; padding: 6px 16px; font-size: 11px; margin-top: 12px;"
        )
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)


class ProcessEditDialog(QDialog):
    """Expanded to two columns, per direct feedback that the material
    section was missing entirely: LEFT keeps drive type / Q_req / H_m /
    fill% / the real Dynamic Fill Advisory visual; RIGHT adds the live
    Material Database Search and the Custom/Override Properties block
    (real DB defaults from results.mat_db_defaults, not sentinels).

    NEW this round: Material Temperature now carries a live advisory
    showing the database's typical/CEMA-sourced max temperature for the
    selected material, when one exists (temp_max field, part of
    mat_db_defaults since mat_db_defaults = dict(get_material(...)) on
    the backend -- confirmed directly, no extra API call needed). All 80
    static fallback-list materials currently return temp_max = None
    (confirmed in materials_lookup.py) -- CEMA 375/550 per-material
    temperature data isn't integrated yet, this is real, not a display
    bug. When it's None, the advisory says so honestly and prompts the
    user to enter a value themselves based on their own process
    conditions, rather than silently treating the 20°C starting value as
    if it meant something for that material. The advisory is purely
    informational -- it never overwrites whatever the user has typed
    into the field above it."""

    def __init__(self, inputs, results, parent=None):
        super().__init__(parent)
        self.inputs = dict(inputs)
        self.results = results or {}
        self.setWindowTitle("Process Design")
        self.setMinimumWidth(760)
        self.resize(780, 700)
        self.setStyleSheet(f"background-color: {PANEL};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(modal_header("Process Design", "CEMA 375 §4"))

        columns = QHBoxLayout()
        columns.setContentsMargins(16, 16, 16, 16)
        columns.setSpacing(20)

        left = QVBoxLayout()
        left.setSpacing(10)
        # FIX (Jay: decide material/tonnage/height BEFORE drive type, not
        # after): this used to put Drive Type first. Swapped so the order
        # on screen matches the order you'd actually think through it.
        left.addWidget(section_head("Process Requirements"))
        row2 = QHBoxLayout()
        self.q_req = styled_spinbox(QDoubleSpinBox())
        self.q_req.setRange(1, 5000); self.q_req.setSingleStep(1)
        self.q_req.setValue(float(self.inputs.get("Q_req", 100)))
        row2.addLayout(field_row("Required Capacity", self.q_req, "t/h"))
        self.h_m = styled_spinbox(QDoubleSpinBox())
        self.h_m.setRange(1, 200); self.h_m.setSingleStep(0.5)
        self.h_m.setValue(float(self.inputs.get("H_m", 25)))
        row2.addLayout(field_row("Lift Height", self.h_m, "m"))
        left.addLayout(row2)

        self.material_temp = styled_spinbox(QDoubleSpinBox())
        self.material_temp.setRange(-30, 400); self.material_temp.setSingleStep(10)
        self.material_temp.setValue(float(self.inputs.get("material_temperature_c", 20)))
        left.addLayout(field_row(
            "Material Temperature", self.material_temp, "°C",
            note="20°C = ambient. Drives belt-vs-chain guidance below — set this for hot "
                 "materials (cement 80-120°C, clinker 150-300°C) before deciding drive type."
        ))

        # ── Temperature advisory -- separate from the note above, which
        # is static guidance text. This is dynamic: it reflects the
        # actual database value for whichever material is currently
        # selected, and updates live in _on_material_selected() below.
        self.temp_advisory = QLabel()
        self.temp_advisory.setWordWrap(True)
        left.addWidget(self.temp_advisory)
        db_init = self.results.get("mat_db_defaults") or {}
        self._update_temp_advisory(db_init.get("temp_max"), db_init.get("name"))

        # ── Design Guidance -- the actual point of this round: material
        # temperature and character now advise drive type and discharge
        # style HERE, before the Drive Type decision below, instead of
        # only ever surfacing as a fail/warn check after a belt was
        # already chosen and a full calculation run. Mirrors the BEUMER
        # reference chart's structure: temperature gates belt feasibility,
        # material character gates continuous vs centrifugal -- both
        # checked against the backend's actual bucket_recommendation()
        # output, not a second copy of that logic living here.
        self.guidance_box = QVBoxLayout()
        left.addLayout(self.guidance_box)
        self._rebuild_guidance()

        left.addWidget(section_head("Drive Type"))
        drive_row = QHBoxLayout()
        self.belt_btn = QPushButton("🔵 Belt Drive")
        self.chain_btn = QPushButton("⛓ Chain Drive")
        for btn, val in ((self.belt_btn, "belt"), (self.chain_btn, "chain")):
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, v=val: self._set_drive_type(v))
            drive_row.addWidget(btn)
        self._set_drive_type(self.inputs.get("conveyor_type", "belt"), restyle_only=True)
        left.addLayout(drive_row)


        self.fill_pct = styled_spinbox(QSpinBox())
        self.fill_pct.setRange(30, 100); self.fill_pct.setSingleStep(5)
        self.fill_pct.setValue(int(self.inputs.get("fill_pct", 75)))
        left.addLayout(field_row(
            "Bucket Fill Factor", self.fill_pct, "%",
            note="Grain 75-90% · Minerals 60-75% · Cohesive 40-65%"
        ))

        self.advisory_box = QVBoxLayout()
        left.addLayout(self.advisory_box)
        self._rebuild_advisory()
        self.fill_pct.valueChanged.connect(self._rebuild_advisory)

        left.addStretch()
        columns.addLayout(left, 1)

        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"background-color: {BORDER};")
        columns.addWidget(sep)

        right = QVBoxLayout()
        right.setSpacing(10)
        right.addWidget(section_head("Material Database Search"))
        self.material_search = MaterialSearchWidget(self.inputs.get("mat_id", "wheat"))
        self.material_search.materialSelected.connect(self._on_material_selected)
        right.addWidget(self.material_search)

        right.addWidget(section_head("Custom / Override Properties"))
        override_note = QLabel(
            "Leave at 0 / -1 to use database values. Overrides apply to this run only "
            "and are not saved as a material -- for a reusable named material, use the "
            "Materials tab instead."
        )
        override_note.setWordWrap(True)
        override_note.setStyleSheet(f"color: {TEXT3}; font-size: 10px;")
        right.addWidget(override_note)

        self.custom_name = QLineEdit(str(self.inputs.get("custom_mat_name", "")))
        self.custom_name.setStyleSheet(
            f"background-color: {PANEL2}; color: {TEXT}; border: 1px solid {BORDER}; "
            f"border-radius: 4px; padding: 5px 8px; font-size: 12px;"
        )
        right.addLayout(field_row("Custom Display Name", self.custom_name,
                                   note="Optional -- shown in reports when overrides are active"))

        db = self.results.get("mat_db_defaults") or {}
        row3 = QHBoxLayout()
        self.ov_rho = OverridableSpinBox("Bulk Density", db.get("rho_loose"), 0,
                                          self.inputs.get("custom_rho", 0), unit="kg/m³")
        row3.addWidget(self.ov_rho)
        self.ov_aor = OverridableSpinBox("Angle of Repose", db.get("angle_repose"), 0,
                                          self.inputs.get("custom_aor", 0), unit="°")
        row3.addWidget(self.ov_aor)
        right.addLayout(row3)

        row4 = QHBoxLayout()
        self.ov_abr = OverridableSpinBox("Abrasiveness 1-7", db.get("abr_code"), 0,
                                          self.inputs.get("custom_abr", 0), is_int=True,
                                          hint="1=Low 7=V.High")
        row4.addWidget(self.ov_abr)
        self.ov_flow = OverridableSpinBox("Flowability 1-4", db.get("flowability"), 0,
                                           self.inputs.get("custom_flowability", 0), is_int=True,
                                           hint="1=Free 4=Sluggish")
        row4.addWidget(self.ov_flow)
        right.addLayout(row4)

        row5 = QHBoxLayout()
        self.ov_moisture = OverridableSpinBox("Moisture %", db.get("moisture_pct"), -1,
                                               self.inputs.get("custom_moisture", -1), unit="%")
        row5.addWidget(self.ov_moisture)
        self.ov_cohesion = OverridableSpinBox("Cohesion kPa", db.get("cohesion"), -1,
                                               self.inputs.get("custom_cohesion", -1), unit="kPa")
        row5.addWidget(self.ov_cohesion)
        right.addLayout(row5)

        right.addStretch()
        columns.addLayout(right, 1)

        # FIX: this was the one dialog still missing a QScrollArea --
        # every other dialog already got this fix when the Shaft modal
        # overflowed the screen with no scrollbar. Adding the Design
        # Guidance card just now made this column taller, which is what
        # actually surfaced it here (cramped/overlapping text, not a
        # rendering bug in the card itself).
        body = QWidget()
        body.setLayout(columns)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        scroll.setWidget(body)
        layout.addWidget(scroll)
        layout.addWidget(modal_footer(self))

    def _update_temp_advisory(self, temp_max, material_name=None):
        """Refresh the temperature advisory line.

        Honest either way: when the database has a real typical/CEMA-
        sourced value for the selected material, show it as a labeled
        reference (not auto-applied -- the field above always keeps
        whatever the user typed). When it doesn't (None -- true for
        every static fallback-list material right now, and for any DB
        material not yet enriched with CEMA 375/550 data), say so
        plainly and ask the user to enter a value themselves rather than
        letting the unlabeled 20°C starting value imply a default that
        doesn't actually exist for that material."""
        name = material_name or "this material"
        if temp_max is not None:
            self.temp_advisory.setText(
                f"ℹ Typical max on file for {name}: {fmt(temp_max, 0)}°C. "
                f"Adjust the field above if your process conditions differ."
            )
            self.temp_advisory.setStyleSheet(f"color: {TEXT3}; font-size: 9.5px;")
        else:
            self.temp_advisory.setText(
                f"⚠ No typical temperature on file for {name} — CEMA 375/550 per-material "
                f"temperature data isn't integrated yet. Enter a value above based on your "
                f"actual process conditions."
            )
            self.temp_advisory.setStyleSheet(f"color: {WARNING}; font-size: 9.5px;")

    def _rebuild_advisory(self):
        while self.advisory_box.count():
            item = self.advisory_box.takeAt(0)
            w = item.widget() if item else None
            if w:
                # setParent(None) removes it from the visual tree immediately;
                # deleteLater() alone defers cleanup and can leave a brief
                # visual ghost of the widget's last-painted pixels behind
                # (confirmed directly: a 'keyed connection' note lingered
                # for one frame after switching to 'welded').
                w.setParent(None)
                w.deleteLater()
        if self.results.get("min_fill_pct") is not None or self.results.get("dynamic_fill"):
            self.advisory_box.addWidget(DynamicFillAdvisory(self.results, self.fill_pct.value()))

    def _rebuild_guidance(self):
        while self.guidance_box.count():
            item = self.guidance_box.takeAt(0)
            w = item.widget() if item else None
            if w:
                w.setParent(None)
                w.deleteLater()
        rec = self.results.get("bucket_recommendation")
        if not rec:
            return
        current_drive = self.inputs.get("conveyor_type", "belt")
        recommended_drive = rec.get("recommended_drive_type", "belt")
        mismatch = current_drive != recommended_drive

        box = QFrame()
        box.setStyleSheet(
            f"background-color: {'rgba(224,82,82,.08)' if mismatch else 'rgba(31,184,110,.07)'}; "
            f"border: 1px solid {'rgba(224,82,82,.3)' if mismatch else 'rgba(31,184,110,.25)'}; border-radius: 5px;"
        )
        bl = QVBoxLayout(box)
        bl.setContentsMargins(10, 8, 10, 8)
        bl.setSpacing(4)
        head = QLabel("●  MATERIAL-BASED DESIGN GUIDANCE")
        head.setStyleSheet(f"color: {PRIMARY}; font-size: 10px; font-weight: 700; letter-spacing: .5px;")
        bl.addWidget(head)

        drive_line = QLabel(
            f"⚠ You've selected {current_drive.upper()}, but material temperature suggests {recommended_drive.upper()}"
            if mismatch else
            f"✓ {current_drive.capitalize()} matches the material-temperature recommendation"
        )
        drive_line.setWordWrap(True)
        drive_line.setStyleSheet(f"color: {DANGER if mismatch else SUCCESS}; font-size: 11px; font-weight: 700;")
        bl.addWidget(drive_line)

        reason1 = QLabel(rec.get("drive_type_reasoning", ""))
        reason1.setWordWrap(True)
        reason1.setStyleSheet(f"color: {TEXT3}; font-size: 10px;")
        bl.addWidget(reason1)

        discharge_line = QLabel(
            f"Discharge character: {rec.get('discharge_type', '—').capitalize()} ({rec.get('recommended_style', '—')} style)"
        )
        discharge_line.setStyleSheet(f"color: {TEXT2}; font-size: 11px; font-weight: 600;")
        discharge_line.setContentsMargins(0, 4, 0, 0)
        bl.addWidget(discharge_line)

        reason2 = QLabel(rec.get("reasoning", ""))
        reason2.setWordWrap(True)
        reason2.setStyleSheet(f"color: {TEXT3}; font-size: 10px;")
        bl.addWidget(reason2)

        stale_note = QLabel("Based on the last calculated result — click Apply after changing "
                             "material or temperature to refresh this guidance.")
        stale_note.setWordWrap(True)
        stale_note.setStyleSheet(f"color: {MUTED}; font-size: 9px; margin-top: 2px;")
        bl.addWidget(stale_note)

        self.guidance_box.addWidget(box)

    def _on_material_selected(self, mat_id):
        self.inputs["mat_id"] = mat_id
        # FIX: this used to be the entire method -- updating mat_id but
        # never refreshing the 6 override fields, which is exactly why
        # they kept showing the previous material's numbers regardless
        # of what got selected. get_material() uses the same field names
        # (rho_loose, angle_repose, abr_code, flowability, moisture_pct,
        # cohesion) as results.mat_db_defaults did when these fields were
        # first built, confirmed directly against a real API response.
        try:
            mat = get_material(mat_id)
        except Exception:
            mat = None
        if mat:
            self.ov_rho.update_db_value(mat.get("rho_loose"))
            self.ov_aor.update_db_value(mat.get("angle_repose"))
            self.ov_abr.update_db_value(mat.get("abr_code"))
            self.ov_flow.update_db_value(mat.get("flowability"))
            self.ov_moisture.update_db_value(mat.get("moisture_pct"))
            self.ov_cohesion.update_db_value(mat.get("cohesion"))
            # NEW: keep the temperature advisory in sync with whichever
            # material is now selected, same trigger point as the
            # override fields above -- one place this gets refreshed,
            # not a second parallel code path that could drift out of
            # sync with it.
            self._update_temp_advisory(mat.get("temp_max"), mat.get("name"))

    def _set_drive_type(self, value, restyle_only=False):
        if not restyle_only:
            self.inputs["conveyor_type"] = value
        for btn, val in ((self.belt_btn, "belt"), (self.chain_btn, "chain")):
            btn.setChecked(val == value)
            if val == value:
                btn.setStyleSheet(f"background-color: rgba(74,158,255,.15); color: {PRIMARY}; "
                                   f"border: 1px solid {PRIMARY}; border-radius: 5px; padding: 8px; font-weight: 600;")
            else:
                btn.setStyleSheet(f"background-color: {PANEL2}; color: {TEXT3}; "
                                   f"border: 1px solid {BORDER}; border-radius: 5px; padding: 8px;")
        # Mismatch warning is a straight comparison against the last-
        # calculated recommendation, not a recalculation -- safe to
        # refresh immediately on toggle, same way the bore-ratio field
        # refreshes immediately on the solid/hollow toggle elsewhere.
        if hasattr(self, "guidance_box"):
            self._rebuild_guidance()

    def updated_inputs(self):
        self.inputs["Q_req"] = self.q_req.value()
        self.inputs["H_m"] = self.h_m.value()
        self.inputs["material_temperature_c"] = self.material_temp.value()
        self.inputs["mat_id"] = self.material_search.current_mat_id
        self.inputs["fill_pct"] = self.fill_pct.value()
        self.inputs["custom_mat_name"] = self.custom_name.text().strip()
        self.inputs["custom_rho"] = self.ov_rho.value_or_sentinel()
        self.inputs["custom_aor"] = self.ov_aor.value_or_sentinel()
        self.inputs["custom_abr"] = self.ov_abr.value_or_sentinel()
        self.inputs["custom_flowability"] = self.ov_flow.value_or_sentinel()
        self.inputs["custom_moisture"] = self.ov_moisture.value_or_sentinel()
        self.inputs["custom_cohesion"] = self.ov_cohesion.value_or_sentinel()
        return self.inputs


class ToggleButton(QPushButton):
    """A real toggle control (✓ ON / OFF) matching the reference
    rendering, not a plain checkbox."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedWidth(90)
        self.toggled.connect(self._restyle)
        self._restyle(False)

    def _restyle(self, checked):
        self.setText("✓ ON" if checked else "OFF")
        if checked:
            self.setStyleSheet(
                f"background-color: rgba(74,158,255,.15); color: {PRIMARY}; "
                f"border: 1px solid {PRIMARY}; border-radius: 5px; padding: 6px 16px; font-weight: 600;"
            )
        else:
            self.setStyleSheet(
                f"background-color: {PANEL2}; color: {TEXT3}; border: 1px solid {BORDER}; "
                f"border-radius: 5px; padding: 6px 16px;"
            )


class StatusCard(QFrame):
    """Green/amber card with a title + a row of labeled stats -- port of
    PulleyEdit's "Wrap Angle Adequate"/"Wrap Angle — Slip Risk" block."""

    def __init__(self, adequate, title_ok, title_warn, stats, note=None, parent=None):
        super().__init__(parent)
        color = SUCCESS if adequate else WARNING
        bg = "rgba(31,184,110,.07)" if adequate else "rgba(217,142,0,.10)"
        border = "rgba(31,184,110,.25)" if adequate else "rgba(217,142,0,.35)"
        self.setStyleSheet(f"background-color: {bg}; border: 1px solid {border}; border-radius: 5px;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)
        head = QLabel(title_ok if adequate else title_warn)
        head.setStyleSheet(f"color: {color}; font-size: 10px; font-weight: 700; letter-spacing: .5px;")
        layout.addWidget(head)
        row = QHBoxLayout()
        row.setSpacing(16)
        for label, value in stats:
            col = QVBoxLayout()
            col.setSpacing(1)
            l = QLabel(label)
            l.setStyleSheet(f"color: {TEXT3}; font-size: 9px;")
            v = QLabel(str(value))
            v.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: 700; font-family: 'JetBrains Mono', monospace;")
            col.addWidget(l); col.addWidget(v)
            row.addLayout(col)
        row.addStretch()
        layout.addLayout(row)
        if note and not adequate:
            note_lbl = QLabel(note)
            note_lbl.setWordWrap(True)
            note_lbl.setStyleSheet(f"color: {WARNING}; font-size: 10px;")
            layout.addWidget(note_lbl)


class PulleyEditDialog(QDialog):
    """Head & Tail Pulley -- has the Wrap Angle Adequate card, the
    head:boot diameter ratio check, a real toggle control for the
    boot-match setting, and Pulley Shell Thickness (head + boot,
    independently overridable). Shell thickness was briefly moved to the
    Shaft modal in an earlier round, on the assumption that "move
    bearings to shaft" extended to it too -- corrected back here since
    that wasn't actually asked for. Bearing selection lives in the
    Shaft modal instead, where it conceptually belongs."""

    def __init__(self, inputs, results, parent=None):
        super().__init__(parent)
        self.inputs = dict(inputs)
        self.results = results or {}
        self.setWindowTitle("Head & Tail Pulley")
        self.setMinimumWidth(440)
        self.setStyleSheet(f"background-color: {PANEL};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(modal_header("Head & Tail Pulley", "CEMA 375 §3,6"))

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 16, 16, 16)
        body_layout.setSpacing(10)

        body_layout.addWidget(section_head("Head Pulley"))
        row1 = QHBoxLayout()
        self.d_mm = styled_spinbox(QDoubleSpinBox())
        self.d_mm.setRange(100, 1500); self.d_mm.setSingleStep(25)
        self.d_mm.setValue(float(self.inputs.get("D_mm", 500)))
        self.d_mm.valueChanged.connect(self._refresh_derived)
        row1.addLayout(field_row("Head Pulley Dia.", self.d_mm, "mm"))
        self.n_rpm = styled_spinbox(QDoubleSpinBox())
        self.n_rpm.setRange(10, 300); self.n_rpm.setSingleStep(5)
        self.n_rpm.setValue(float(self.inputs.get("n_rpm", 70)))
        row1.addLayout(field_row("Shaft Speed", self.n_rpm, "rpm"))
        body_layout.addLayout(row1)

        r = self.results
        wrap_box = QFrame()
        wrap_box.setStyleSheet(f"background-color: {PANEL2}; border: 1px solid {BORDER}; border-radius: 5px;")
        wl = QVBoxLayout(wrap_box)
        wl.setContentsMargins(10, 8, 10, 8)
        wl.addWidget(section_head("Wrap Angle (derived)"))
        wrow = QHBoxLayout()
        # FIX (Jay: "wrap angle computation does not seem to change with
        # boot pulley dia"): verified both sides before touching anything.
        # Backend math is correct -- 500mm vs 525mm boot diameter on a 25m
        # elevator genuinely produces 179.9°, not 180.0° (confirmed via
        # direct API calls; the effect gets much more visible on a shorter
        # elevator or a larger diameter difference, e.g. 169.6° at 2m +
        # 500mm difference). The bug was display precision: this rounded
        # to 0 decimals, so a real 179.9° rendered as "180°" and looked
        # unresponsive. Now shows 1 decimal so the genuine change is visible.
        for label, value, color in (
            ("Geometric", f"{fmt(r.get('wrap_geom_deg'), 1)}°", TEXT),
            ("Effective", f"{fmt(r.get('wrap_effective_deg'), 1)}°", PRIMARY),
        ):
            col = QVBoxLayout()
            l = QLabel(label); l.setStyleSheet(f"color: {TEXT3}; font-size: 9px;")
            v = QLabel(value); v.setStyleSheet(f"color: {color}; font-size: 15px; font-weight: 700; font-family: 'JetBrains Mono', monospace;")
            col.addWidget(l); col.addWidget(v)
            wrow.addLayout(col)
        formula_col = QVBoxLayout()
        fl = QLabel("Formula"); fl.setStyleSheet(f"color: {TEXT3}; font-size: 9px;")
        fv = QLabel("180° + 2·arcsin((R_H−R_B)/C)"); fv.setStyleSheet(f"color: {TEXT3}; font-size: 10px;")
        formula_col.addWidget(fl); formula_col.addWidget(fv)
        wrow.addLayout(formula_col)
        wrow.addStretch()
        wl.addLayout(wrow)
        # Honest about what this is: the architecture deliberately keeps
        # all physics in the backend (a frontend shadow of this formula
        # is exactly the kind of duplicate calculation you flagged as
        # the JSX's old failure mode) -- so this reflects the last
        # Applied calculation, not a live preview of an unapplied edit.
        stale_note = QLabel("Reflects the last calculated result. Click Apply to see this update for a new diameter.")
        stale_note.setWordWrap(True)
        stale_note.setStyleSheet(f"color: {MUTED}; font-size: 9px; margin-top: 2px;")
        wl.addWidget(stale_note)

        self.snub_toggle = ToggleButton()
        self.snub_toggle.setChecked(bool(self.inputs.get("snub_pulley", False)))
        snub_row = field_row("Snub pulley on return side (+30°)", self.snub_toggle,
                              note="Adds one snub pulley. Use when Euler check requires wrap > 180°.")
        wl.addLayout(snub_row)
        body_layout.addWidget(wrap_box)

        self.wrap_card_box = QVBoxLayout()
        body_layout.addLayout(self.wrap_card_box)
        self._rebuild_wrap_card()

        body_layout.addWidget(section_head("Boot (Tail) Pulley"))
        self.same_as_head = ToggleButton()
        self.same_as_head.setChecked(bool(self.inputs.get("boot_pulley_same_as_head", False)))
        self.same_as_head.toggled.connect(self._on_same_as_head)
        body_layout.addLayout(field_row("Match head pulley diameter", self.same_as_head))

        self.boot_d_mm = styled_spinbox(QDoubleSpinBox())
        self.boot_d_mm.setRange(100, 1000); self.boot_d_mm.setSingleStep(25)
        self.boot_d_mm.setValue(float(self.inputs.get("boot_pulley_D_mm", 300)))
        self.boot_d_mm.valueChanged.connect(self._refresh_derived)
        self.boot_field_box = QVBoxLayout()
        body_layout.addLayout(self.boot_field_box)

        self.locked_label = QLabel()
        self.locked_label.setStyleSheet(f"color: {SUCCESS}; font-size: 12px; padding: 4px 0 8px;")
        body_layout.addWidget(self.locked_label)
        self._on_same_as_head(self.same_as_head.isChecked())

        # Pulley Shell Thickness -- moved back here per direct correction:
        # an earlier round read "move bearings to the shaft modal" as
        # also covering shell thickness, which wasn't actually asked for.
        # This belongs with head/boot pulley diameter, not shaft sizing.
        self.head_shell_override = self._build_shell_section(
            body_layout, "Head Pulley Shell Thickness", r.get("pulley_shell") or {},
            self.inputs.get("pulley_shell_t_override_mm", 0),
        )
        self.boot_shell_override = self._build_shell_section(
            body_layout, "Tail (Boot) Pulley Shell Thickness", r.get("boot_shell") or {},
            self.inputs.get("boot_shell_t_override_mm", 0),
        )

        body_layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        scroll.setWidget(body)
        layout.addWidget(scroll)
        layout.addWidget(modal_footer(self))

    def _build_shell_section(self, bl, title, shell, current_override):
        """One Head- or Tail-pulley shell thickness block: stat box +
        its own independent override field."""
        bl.addWidget(section_head(title))
        if shell:
            bl.addWidget(stat_box([
                ("CEMA min", f"{fmt(shell.get('t_cema_mm'), 0)} mm"),
                ("Pressure min", f"{fmt(shell.get('t_pressure_mm'), 2)} mm"),
                ("Governing", f"{fmt(shell.get('t_governing_mm'), 0)} mm"),
            ]))
        override = styled_spinbox(QDoubleSpinBox())
        override.setRange(0, 50); override.setSingleStep(1)
        override.setValue(float(current_override))
        if shell.get("override_applied"):
            note = (f"✓ {fmt(shell.get('t_use_mm'),0)}mm meets calculated minimum {fmt(shell.get('t_calc_mm'),0)}mm"
                    if shell.get("override_pass") else
                    f"⚠ {fmt(shell.get('t_use_mm'),0)}mm is BELOW calculated minimum {fmt(shell.get('t_calc_mm'),0)}mm")
        else:
            note = "0 = auto from CEMA Pulley Standard minimum + belt-pressure check. Specify to verify a standard plate gauge."
        bl.addLayout(field_row("Shell Thickness Override", override, "mm", note=note))
        return override

    def _rebuild_wrap_card(self):
        while self.wrap_card_box.count():
            item = self.wrap_card_box.takeAt(0)
            w = item.widget() if item else None
            if w:
                # setParent(None) removes it from the visual tree immediately;
                # deleteLater() alone defers cleanup and can leave a brief
                # visual ghost of the widget's last-painted pixels behind
                # (confirmed directly: a 'keyed connection' note lingered
                # for one frame after switching to 'welded').
                w.setParent(None)
                w.deleteLater()
        wr = self.results.get("wrap_recommendation")
        if not wr:
            return
        effective = self.results.get("wrap_effective_deg", self.inputs.get("wrap_deg", 180))
        adequate = effective >= wr.get("required_deg", 0)
        card = StatusCard(
            adequate, "✓ WRAP ANGLE ADEQUATE", "⚠ WRAP ANGLE — SLIP RISK",
            [("Required", f"{fmt(wr.get('required_deg'), 1)}°"),
             ("Current", f"{fmt(effective, 1)}°"),
             ("Config", wr.get("config", "—"))],
            note=wr.get("recommendation"),
        )
        self.wrap_card_box.addWidget(card)

    def _refresh_derived(self):
        if not self.same_as_head.isChecked():
            self._set_boot_field()

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget() if item else None
            if w:
                # setParent(None) removes it from the visual tree immediately;
                # deleteLater() alone defers cleanup and can leave a brief
                # visual ghost of the widget's last-painted pixels behind
                # (confirmed directly: a 'keyed connection' note lingered
                # for one frame after switching to 'welded').
                w.setParent(None)
                w.deleteLater()
            elif item is not None:
                sub = item.layout()
                if sub:
                    self._clear_layout(sub)

    def _detach_boot_spinbox(self):
        """FIX (Jay: "boot pulley once toggled to match head pulley cannot
        be reversed"): self.boot_d_mm is created once and reused across
        every rebuild of boot_field_box -- its value has to survive
        toggling "same as head" on and off. _clear_layout() below
        deletes every widget it finds with no exceptions, and
        boot_d_mm was getting swept up in that the moment it was first
        added: toggling ON cleared the box (destroying the spinbox),
        then toggling back OFF tried to reuse the now-dead widget,
        which is exactly why the field never came back. Detaching it
        with setParent(None) (no deleteLater) before any clear runs
        keeps it alive and reusable indefinitely."""
        self.boot_d_mm.setParent(None)

    def _set_boot_field(self):
        self._detach_boot_spinbox()
        self._clear_layout(self.boot_field_box)
        ratio = self.d_mm.value() / max(self.boot_d_mm.value(), 1)
        ok = ratio <= 2.0
        note = f"Head:Boot ratio = {ratio:.2f} (CEMA §3.2 limit ≤ 2.00)" + ("" if ok else "  ⚠")
        box = field_row("Boot Pulley Diameter", self.boot_d_mm, "mm", note=note)
        self.boot_field_box.addLayout(box)
        note_item = box.itemAt(box.count() - 1)
        note_label = note_item.widget() if note_item else None
        if note_label and not ok:
            note_label.setStyleSheet(f"color: {WARNING}; font-size: 9.5px;")

    def _on_same_as_head(self, checked):
        self._detach_boot_spinbox()
        self.boot_d_mm.setEnabled(not checked)
        if checked:
            self._clear_layout(self.boot_field_box)
            self.locked_label.setText(f"Boot locked to head: {self.d_mm.value():.0f} mm")
            self.locked_label.show()
        else:
            self.locked_label.hide()
            self._set_boot_field()

    def updated_inputs(self):
        self.inputs["D_mm"] = self.d_mm.value()
        self.inputs["n_rpm"] = self.n_rpm.value()
        self.inputs["snub_pulley"] = self.snub_toggle.isChecked()
        self.inputs["boot_pulley_same_as_head"] = self.same_as_head.isChecked()
        self.inputs["boot_pulley_D_mm"] = self.boot_d_mm.value()
        self.inputs["pulley_shell_t_override_mm"] = self.head_shell_override.value()
        self.inputs["boot_shell_t_override_mm"] = self.boot_shell_override.value()
        return self.inputs


class BeltChainEditDialog(QDialog):
    """Belt / Chain Selection -- combines BeltEdit and ChainEdit from the
    JSX into one modal that switches content based on conveyor_type,
    the same way EquipmentTree.jsx already switches its own Belt/Chain
    Selection section. Moved up in the sidebar order per the engineering-
    flow discussion: drive type is decided right after Design
    Requirements, well before Pulley/Shaft, so this should sit right
    after it too, not buried in the middle of the list."""

    def __init__(self, inputs, results, parent=None):
        super().__init__(parent)
        self.inputs = dict(inputs)
        self.results = results or {}
        self.is_chain = bool(self.results.get("is_chain"))
        title = "Chain Selection" if self.is_chain else "Belt Selection"
        self.setWindowTitle(title)
        self.setMinimumWidth(460)
        self.setStyleSheet(f"background-color: {PANEL};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(modal_header(title, "CEMA 375 §4"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(16, 16, 16, 16)
        bl.setSpacing(10)

        if self.is_chain:
            self._build_chain_content(bl)
        else:
            self._build_belt_content(bl)

        bl.addStretch()
        scroll.setWidget(body)
        layout.addWidget(scroll)
        layout.addWidget(modal_footer(self))

    # ── Belt mode ─────────────────────────────────────────────────────
    def _build_belt_content(self, bl):
        r = self.results
        tp = r.get("tension_profile") or {}
        margin_bad = tp.get("rating_margin") is not None and tp["rating_margin"] < 1.0

        bl.addWidget(section_head("Belt Configuration"))
        bl.addWidget(stat_box([
            ("Auto Width", f"{fmt(r.get('belt_w'), 0)} mm"),
            ("Plies", f"{r.get('belt_ply', '—')}" + (" (override)" if r.get("belt_ply_is_override") else "")),
            ("Eff. Tension (sizing basis)", f"{fmt((r.get('F_eff') or 0) / 1000, 1)} kN"),
        ]))

        if tp.get("T_max_N") is not None:
            note = None
            if margin_bad:
                note = ("⚠ Ply count above is sized for effective tension only — peak tension "
                        "(including empty-leg self-weight) exceeds belt rating. Increase belt "
                        "width, or set Belt Ply Override below to a higher count.")
            bl.addWidget(stat_box(
                [("Peak Tension (actual max, full loop)", f"{fmt(tp.get('T_max_N', 0) / 1000, 1)} kN"),
                 ("Belt Rated", f"{fmt((tp.get('belt_rated_N') or 0) / 1000, 1)} kN"),
                 ("Margin", fmt(tp.get("rating_margin"), 2))],
                border_color=DANGER if margin_bad else None,
                note=note, note_color=DANGER,
            ))

        self.belt_ply_override = styled_spinbox(QSpinBox())
        self.belt_ply_override.setRange(0, 10); self.belt_ply_override.setSingleStep(1)
        self.belt_ply_override.setValue(int(self.inputs.get("belt_ply_override", 0)))
        ply_note = (f"0 = auto (currently {r.get('belt_ply')}"
                    f"{', from your override' if r.get('belt_ply_is_override') else ''}). "
                    f"Set > 0 to pick a specific ply count."
                    if r.get("belt_ply") is not None else
                    "0 = auto-calculate from peak tension. Set > 0 to pick a specific ply count.")
        bl.addLayout(field_row("Belt Ply Override", self.belt_ply_override, note=ply_note))

        self.belt_width_override = styled_spinbox(QDoubleSpinBox())
        self.belt_width_override.setRange(0, 1500); self.belt_width_override.setSingleStep(25)
        self.belt_width_override.setValue(float(self.inputs.get("belt_width_override_mm", 0)))
        bl.addLayout(field_row("Belt Width Override", self.belt_width_override, "mm",
                                note="0 = auto-select from bucket width. Set > 0 to specify exact width."))

        bl.addWidget(section_head("Belt Type"))
        self.belt_type_combo = QComboBox()
        self.belt_type_combo.setMinimumHeight(28)
        self.belt_type_combo.setStyleSheet(
            f"background-color: {PANEL2}; color: {TEXT}; border: 1px solid {BORDER}; "
            f"border-radius: 4px; padding: 5px 8px; font-size: 12px;"
        )
        belt_types = [("EP", "EP — Fabric ply (standard)"), ("ST", "ST — Steel cord (high tension)")]
        current_belt_type = self.inputs.get("belt_type", "EP")
        for i, (val, text) in enumerate(belt_types):
            self.belt_type_combo.addItem(text, val)
            if val == current_belt_type:
                self.belt_type_combo.setCurrentIndex(i)
        bl.addWidget(self.belt_type_combo)
        type_note = QLabel("ST belts use herringbone lagging — not diamond groove")
        type_note.setStyleSheet(f"color: {MUTED}; font-size: 9.5px;")
        bl.addWidget(type_note)

        bl.addWidget(section_head("Belt Cover Grade"))
        self.belt_grade_combo = QComboBox()
        self.belt_grade_combo.setMinimumHeight(28)
        self.belt_grade_combo.setStyleSheet(
            f"background-color: {PANEL2}; color: {TEXT}; border: 1px solid {BORDER}; "
            f"border-radius: 4px; padding: 5px 8px; font-size: 12px;"
        )
        belt_grades = [
            ("", "Auto — solver selects grade"),
            ("M", "M — Abrasion resistant (DIN 22102 Grade M)"),
            ("N", "N — General duty (DIN 22102 Grade N)"),
            ("W", "W — Oil and heat resistant"),
        ]
        current_grade = self.inputs.get("belt_grade", "")
        for i, (val, text) in enumerate(belt_grades):
            self.belt_grade_combo.addItem(text, val)
            if val == current_grade:
                self.belt_grade_combo.setCurrentIndex(i)
        bl.addWidget(self.belt_grade_combo)
        grade_note = QLabel("Grade M for abrasive materials (abr ≥ 4). Grade N for grain/light minerals.")
        grade_note.setWordWrap(True)
        grade_note.setStyleSheet(f"color: {MUTED}; font-size: 9.5px;")
        bl.addWidget(grade_note)

    # ── Chain mode ────────────────────────────────────────────────────
    def _build_chain_content(self, bl):
        r = self.results
        cs = r.get("chain_selected")
        sp = r.get("sprocket")
        bsp = r.get("boot_sprocket")

        bl.addWidget(section_head("Chain Series"))
        self.chain_series_combo = QComboBox()
        self.chain_series_combo.setMinimumHeight(28)
        self.chain_series_combo.setStyleSheet(
            f"background-color: {PANEL2}; color: {TEXT}; border: 1px solid {BORDER}; "
            f"border-radius: 4px; padding: 5px 8px; font-size: 12px; font-family: 'JetBrains Mono', monospace;"
        )
        self.chain_series_combo.addItem("Auto — select by pull force", "")
        current_chain = self.inputs.get("chain_series", "")
        for i, (val, text) in enumerate(CHAIN_OPTIONS, start=1):
            self.chain_series_combo.addItem(text, val)
            if val == current_chain:
                self.chain_series_combo.setCurrentIndex(i)
        bl.addWidget(self.chain_series_combo)
        if cs:
            sel_note = QLabel(
                f"✓ Selected: {cs.get('name')} — pull {fmt((r.get('chain_pull_N') or 0) / 1000, 1)}kN  "
                f"SF={fmt(r.get('chain_SF_actual'), 2)}"
            )
            sel_note.setStyleSheet(f"color: {SUCCESS}; font-size: 10px;")
            bl.addWidget(sel_note)

        row = QHBoxLayout()
        strands_col = QVBoxLayout()
        strands_lbl = QLabel("No. of Strands")
        strands_lbl.setStyleSheet(f"color: {TEXT2}; font-size: 10.5px; font-weight: 600;")
        strands_col.addWidget(strands_lbl)
        self._strands_val = [int(self.inputs.get("chain_n_strands", 1))]
        strands_row = QHBoxLayout()
        strands_buttons = {}

        def restyle_strands():
            for n, btn in strands_buttons.items():
                active = n == self._strands_val[0]
                btn.setStyleSheet(
                    (f"background-color: rgba(74,158,255,.15); color: {PRIMARY}; "
                     f"border: 1px solid {PRIMARY}; border-radius: 5px; padding: 7px 4px; font-weight: 600;")
                    if active else
                    (f"background-color: {PANEL2}; color: {TEXT3}; border: 1px solid {BORDER}; "
                     f"border-radius: 5px; padding: 7px 4px;")
                )

        for n, label in ((1, "1 — Single"), (2, "2 — SC Double")):
            btn = QPushButton(label)

            def clicked(checked, v=n):
                self._strands_val[0] = v
                restyle_strands()
            btn.clicked.connect(clicked)
            strands_row.addWidget(btn)
            strands_buttons[n] = btn
        restyle_strands()
        strands_col.addLayout(strands_row)
        row.addLayout(strands_col)

        self.chain_sf = styled_spinbox(QDoubleSpinBox())
        self.chain_sf.setRange(3, 12); self.chain_sf.setSingleStep(0.5)
        self.chain_sf.setValue(float(self.inputs.get("chain_sf", 6.0)))
        row.addLayout(field_row("Chain SF", self.chain_sf, note="CEMA default 6.0; 8.0 for shock/abrasive"))
        bl.addLayout(row)

        bl.addWidget(section_head("Sprocket"))
        self.sprocket_teeth = styled_spinbox(QSpinBox())
        self.sprocket_teeth.setRange(0, 32); self.sprocket_teeth.setSingleStep(1)
        self.sprocket_teeth.setValue(int(self.inputs.get("chain_sprocket_teeth", 0)))
        bl.addLayout(field_row("Sprocket Teeth Override", self.sprocket_teeth,
                                note="0 = auto from D_mm. Recommend 10–20 teeth for smooth chain engagement."))
        if sp:
            bl.addWidget(stat_box(
                [("PD", f"{fmt(sp.get('PD_mm'), 0)} mm"), ("Teeth", str(sp.get("n_teeth", "—"))),
                 ("Smooth", "✓ Yes" if sp.get("smooth") else "⚠ No")],
                border_color=None if sp.get("smooth") else WARNING,
                note=sp.get("note") if not sp.get("smooth") else None, note_color=WARNING,
            ))

        bl.addWidget(section_head("Boot Sprocket"))
        self.boot_sprocket_teeth = styled_spinbox(QSpinBox())
        self.boot_sprocket_teeth.setRange(0, 32); self.boot_sprocket_teeth.setSingleStep(1)
        self.boot_sprocket_teeth.setValue(int(self.inputs.get("chain_boot_sprocket_teeth", 0)))
        bl.addLayout(field_row(
            "Boot Sprocket Teeth Override", self.boot_sprocket_teeth,
            note="0 = auto from boot pulley diameter. Same physical relationship as the head "
                 "sprocket — the boot/tail wheel engages the chain too, not a smooth-faced pulley."
        ))
        if bsp:
            bl.addWidget(stat_box(
                [("PD", f"{fmt(bsp.get('PD_mm'), 0)} mm"), ("Teeth", str(bsp.get("n_teeth", "—"))),
                 ("Smooth", "✓ Yes" if bsp.get("smooth") else "⚠ No")],
                border_color=None if bsp.get("smooth") else WARNING,
                note=bsp.get("note") if not bsp.get("smooth") else None, note_color=WARNING,
            ))

        if r.get("chain_v_ok") is not None:
            bl.addWidget(section_head("Chain Speed Check"))
            ok = r["chain_v_ok"]
            v_max = (cs or {}).get("v_max_ms", "—")
            speed_note = QFrame()
            speed_note.setStyleSheet(
                f"background-color: {'rgba(31,184,110,.08)' if ok else 'rgba(224,82,82,.10)'}; "
                f"border: 1px solid {'rgba(31,184,110,.3)' if ok else 'rgba(224,82,82,.3)'}; border-radius: 5px;"
            )
            sl = QVBoxLayout(speed_note)
            sl.setContentsMargins(10, 6, 10, 6)
            text = (f"✓ Speed {fmt(r.get('v'), 2)} m/s ≤ chain rated {v_max} m/s" if ok else
                    f"⚠ Speed {fmt(r.get('v'), 2)} m/s EXCEEDS chain rated {v_max} m/s")
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color: {SUCCESS if ok else DANGER}; font-size: 11px;")
            sl.addWidget(lbl)
            bl.addWidget(speed_note)

    def updated_inputs(self):
        if self.is_chain:
            self.inputs["chain_series"] = self.chain_series_combo.currentData()
            self.inputs["chain_n_strands"] = self._strands_val[0]
            self.inputs["chain_sf"] = self.chain_sf.value()
            self.inputs["chain_sprocket_teeth"] = self.sprocket_teeth.value()
            self.inputs["chain_boot_sprocket_teeth"] = self.boot_sprocket_teeth.value()
        else:
            self.inputs["belt_ply_override"] = self.belt_ply_override.value()
            self.inputs["belt_width_override_mm"] = self.belt_width_override.value()
            self.inputs["belt_type"] = self.belt_type_combo.currentData()
            self.inputs["belt_grade"] = self.belt_grade_combo.currentData()
        return self.inputs


class BucketEditDialog(QDialog):
    """Bucket Selection -- fetches the real 40-row bucket catalog live
    from /components/buckets (confirmed directly: exactly the 6 styles
    AA/AC/C/MF/HF/SC the JSX hardcodes, same 40 total sizes), grouped by
    style. Only the descriptive text per style (BUCKET_STYLE_INFO above)
    isn't available from the API and is kept as a small lookup -- the
    actual dimensions driving every calculation come from the live
    catalog, not a duplicated copy.

    auto_bucket lives here, not in Design Requirements -- confirmed
    against the real JSX before assuming otherwise; this is also where
    the bucket-aware fill % discussion from the engineering-flow
    question actually resolves: the recommendation card and size
    constraints below are what should inform revisiting Bucket Fill
    Factor in Design Requirements, once a bucket is actually chosen."""

    def __init__(self, inputs, results, parent=None):
        super().__init__(parent)
        self.inputs = dict(inputs)
        self.results = results or {}
        self.setWindowTitle("Bucket Selection")
        self.setMinimumWidth(460)
        self.setStyleSheet(f"background-color: {PANEL};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(modal_header("Bucket Selection", "CEMA 375 §6"))

        try:
            all_buckets = fetch_components("/components/buckets")
        except Exception:
            all_buckets = []
        self.catalog = {}
        for b in all_buckets:
            self.catalog.setdefault(b.get("style"), []).append(b)
        for style_rows in self.catalog.values():
            style_rows.sort(key=lambda b: b.get("V_L", 0))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(16, 16, 16, 16)
        bl.setSpacing(10)
        r = self.results

        bl.addWidget(section_head("Auto-Select"))
        self.auto_toggle = ToggleButton()
        self.auto_toggle.setChecked(bool(self.inputs.get("auto_bucket", True)))
        self.auto_toggle.toggled.connect(self._on_auto_toggled)
        bl.addLayout(field_row("Auto-select smallest adequate series", self.auto_toggle,
                                note="Auto picks the smallest size that meets Q_req at current speed and fill"))

        rec = r.get("bucket_recommendation")
        if rec:
            current_style = (self.inputs.get("bucket_id", "") or "").split("_")[0]
            is_current = current_style == rec.get("recommended_style")
            card = QFrame()
            card.setStyleSheet(
                f"background-color: {'rgba(31,184,110,.08)' if is_current else 'rgba(74,158,255,.07)'}; "
                f"border: 1px solid {'rgba(31,184,110,.3)' if is_current else 'rgba(74,158,255,.3)'}; border-radius: 5px;"
            )
            cl = QVBoxLayout(card)
            cl.setContentsMargins(10, 8, 10, 8)
            cl.setSpacing(4)
            head = QLabel("✓ CURRENT STYLE MATCHES RECOMMENDATION" if is_current else "●  RECOMMENDATION FOR THIS MATERIAL")
            head.setStyleSheet(f"color: {SUCCESS if is_current else PRIMARY}; font-size: 10px; font-weight: 700;")
            cl.addWidget(head)
            style_lbl = QLabel(f"{rec.get('recommended_style')} style" +
                                (f"   (alt: {rec.get('alternative_style')})" if rec.get("alternative_style") != rec.get("recommended_style") else ""))
            style_lbl.setStyleSheet(f"color: {TEXT}; font-size: 12px; font-weight: 700;")
            cl.addWidget(style_lbl)
            reasoning = QLabel(rec.get("reasoning", ""))
            reasoning.setWordWrap(True)
            reasoning.setStyleSheet(f"color: {TEXT3}; font-size: 11px;")
            cl.addWidget(reasoning)
            for note in rec.get("notes") or []:
                note_lbl = QLabel(f"⚠ {note}")
                note_lbl.setWordWrap(True)
                note_lbl.setStyleSheet(f"color: {WARNING}; font-size: 10px;")
                cl.addWidget(note_lbl)
            bl.addWidget(card)

        bl.addWidget(section_head("Bucket Style"))
        self.style_combo = QComboBox()
        self.style_combo.setMinimumHeight(28)
        self.style_combo.setStyleSheet(
            f"background-color: {PANEL2}; color: {TEXT}; border: 1px solid {BORDER}; "
            f"border-radius: 4px; padding: 5px 8px; font-size: 12px;"
        )
        current_bucket_id = self.inputs.get("bucket_id", "AC_12x8")
        current_style = current_bucket_id.split("_")[0] if "_" in current_bucket_id else "AA"
        for style in self.catalog.keys():
            label = BUCKET_STYLE_INFO.get(style, (style, "", ""))[0]
            self.style_combo.addItem(label, style)
        idx = self.style_combo.findData(current_style)
        if idx >= 0:
            self.style_combo.setCurrentIndex(idx)
        self.style_combo.currentIndexChanged.connect(self._on_style_changed)
        bl.addWidget(self.style_combo)
        self.style_desc = QLabel()
        self.style_desc.setWordWrap(True)
        self.style_desc.setStyleSheet(f"color: {MUTED}; font-size: 9.5px;")
        bl.addWidget(self.style_desc)

        bl.addWidget(section_head("Size"))
        self.belt_width_note = QLabel()
        self.belt_width_note.setStyleSheet(f"color: {PRIMARY}; font-size: 9px; font-weight: 700;")
        bl.addWidget(self.belt_width_note)
        self.size_combo = QComboBox()
        self.size_combo.setMinimumHeight(28)
        self.size_combo.setStyleSheet(
            f"background-color: {PANEL2}; color: {TEXT}; border: 1px solid {BORDER}; "
            f"border-radius: 4px; padding: 5px 8px; font-size: 12px; font-family: 'JetBrains Mono', monospace;"
        )
        # Connected exactly once, here -- _populate_sizes() used to
        # disconnect/reconnect this on every call, which raised a
        # RuntimeWarning the first time (nothing was connected yet to
        # disconnect). A single permanent connection plus blockSignals()
        # during repopulation (already done below) is the correct pattern.
        self.size_combo.currentIndexChanged.connect(self._rebuild_size_summary)
        bl.addWidget(self.size_combo)
        self.size_warn = QLabel()
        self.size_warn.setWordWrap(True)
        self.size_warn.setStyleSheet(f"color: {WARNING}; font-size: 10px;")
        bl.addWidget(self.size_warn)

        self.size_summary_box = QVBoxLayout()
        bl.addLayout(self.size_summary_box)

        self._populate_sizes(current_bucket_id)
        self._update_auto_state(self.auto_toggle.isChecked())

        bl.addWidget(section_head("Spacing"))
        self.bucket_gap = styled_spinbox(QDoubleSpinBox())
        self.bucket_gap.setRange(0, 200); self.bucket_gap.setSingleStep(5)
        self.bucket_gap.setValue(float(self.inputs.get("bucket_gap", 25)))
        bl.addLayout(field_row("Bucket Spacing Gap", self.bucket_gap, "mm",
                                note="Gap added beyond bucket projection for spacing. CEMA default 25mm. "
                                     "Continuous elevators typically 0mm."))

        bl.addWidget(section_head("Plate Thickness"))
        bt = r.get("bucket_thickness")
        if bt:
            bl.addWidget(stat_box([
                ("Catalogue gauge", f"{fmt(bt.get('t_implied_mm'), 1)} mm"),
                ("Specified", f"{fmt(bt.get('t_override_mm'), 1)} mm"),
                ("Mass", f"{fmt(bt.get('mass_scaled_kg'), 1)} kg"),
            ]))
        self.thickness_override = styled_spinbox(QDoubleSpinBox())
        self.thickness_override.setRange(0, 20); self.thickness_override.setSingleStep(0.5)
        self.thickness_override.setValue(float(self.inputs.get("bucket_thickness_override_mm", 0)))
        bl.addLayout(field_row(
            "Plate Thickness Override", self.thickness_override, "mm",
            note="0 = catalogue standard gauge for the selected series. Heavier gauge adds wear "
                 "allowance and dead load; mass scales linearly from catalogue reference (not "
                 "independently structurally validated)."
        ))

        bl.addStretch()
        scroll.setWidget(body)
        layout.addWidget(scroll)
        layout.addWidget(modal_footer(self))

    def _resolved_belt_w(self):
        override = self.inputs.get("belt_width_override_mm", 0) or 0
        if override > 0:
            return override
        return self.results.get("belt_w") or self.results.get("belt_width_mm")

    def _on_style_changed(self):
        style = self.style_combo.currentData()
        rows = self.catalog.get(style, [])
        if rows:
            mid = rows[len(rows) // 2]
            self._populate_sizes(mid.get("bucket_id"), force_style=style)
        self.inputs["auto_bucket"] = False
        self.auto_toggle.setChecked(False)

    def _populate_sizes(self, bucket_id, force_style=None):
        style = force_style or (bucket_id.split("_")[0] if bucket_id and "_" in bucket_id else self.style_combo.currentData())
        info = BUCKET_STYLE_INFO.get(style, (style, "", f"{style} series"))
        self.style_desc.setText(info[2] + (
            "   ●  Continuous discharge — CR must be < 1.0" if info[1] == "continuous" else ""
        ))

        belt_w = self._resolved_belt_w()
        max_w = (belt_w - 50) if belt_w else None
        rows = self.catalog.get(style, [])
        filtered = [b for b in rows if max_w is None or b.get("W_mm", 0) <= max_w]
        hidden = len(rows) - len(filtered)
        rows_to_show = filtered if filtered else rows

        if belt_w:
            self.belt_width_note.setText(f"Belt {fmt(belt_w,0)}mm → max W={fmt(max_w,0)}mm")
        else:
            self.belt_width_note.setText("")

        self.size_combo.blockSignals(True)
        self.size_combo.clear()
        selected_index = len(rows_to_show) // 2
        for i, b in enumerate(rows_to_show):
            self.size_combo.addItem(b.get("catalog", b.get("bucket_id")), b.get("bucket_id"))
            if b.get("bucket_id") == bucket_id:
                selected_index = i
        if rows_to_show:
            self.size_combo.setCurrentIndex(selected_index)
        self.size_combo.blockSignals(False)

        if hidden > 0:
            self.size_warn.setText(
                f"⚠ {hidden} size{'s' if hidden > 1 else ''} hidden — wider than belt "
                f"({fmt(belt_w,0)}mm − 50mm clearance). Increase belt width override to unlock them."
            )
        else:
            self.size_warn.setText("")
        self._current_rows = {b.get("bucket_id"): b for b in rows_to_show}
        self._rebuild_size_summary()

    def _rebuild_size_summary(self, _index=None):
        while self.size_summary_box.count():
            item = self.size_summary_box.takeAt(0)
            w = item.widget() if item else None
            if w:
                w.setParent(None)
                w.deleteLater()
        if self.auto_toggle.isChecked():
            note = QLabel("Auto-select active — disable toggle above to pick a specific size")
            note.setStyleSheet(f"color: {SUCCESS}; font-size: 10px;")
            self.size_summary_box.addWidget(note)
            return
        bucket_id = self.size_combo.currentData()
        row = getattr(self, "_current_rows", {}).get(bucket_id)
        if row:
            self.size_summary_box.addWidget(stat_box([
                ("Width", f"{fmt(row.get('W_mm'), 0)} mm"),
                ("Projection", f"{fmt(row.get('P_mm'), 0)} mm"),
                ("Volume", f"{fmt(row.get('V_L'), 2)} L"),
                ("Style", row.get("style", "—")),
            ]))

    def _on_auto_toggled(self, checked):
        self.inputs["auto_bucket"] = checked
        self._update_auto_state(checked)
        self._rebuild_size_summary()

    def _update_auto_state(self, auto_on):
        self.size_combo.setEnabled(not auto_on)

    def updated_inputs(self):
        self.inputs["auto_bucket"] = self.auto_toggle.isChecked()
        if not self.auto_toggle.isChecked():
            self.inputs["bucket_id"] = self.size_combo.currentData()
        self.inputs["bucket_gap"] = self.bucket_gap.value()
        self.inputs["bucket_thickness_override_mm"] = self.thickness_override.value()
        return self.inputs


class ComponentPickerWidget(QWidget):
    """Real port of ComponentPicker.jsx: fetches a catalog list from a
    given API path + query params, shows it as a dropdown with "Auto
    (solver default)" as the first option. If the catalog is empty (e.g.
    bearings -- confirmed directly: /components/bearings currently
    returns zero rows, a pre-existing gap, not something this round
    broke), this honestly shows "0 options available" rather than
    fabricating entries."""

    def __init__(self, path, params, format_label, current_value, auto_label, label, note=None, parent=None):
        super().__init__(parent)
        self.path, self.params, self.format_label = path, params, format_label
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        layout.addWidget(section_head(label))

        try:
            self.options = fetch_components(path, params)
        except Exception:
            self.options = []

        self.combo = QComboBox()
        self.combo.setStyleSheet(
            f"background-color: {PANEL2}; color: {TEXT}; border: 1px solid {BORDER}; "
            f"border-radius: 4px; padding: 5px 8px; font-size: 12px;"
        )
        self.combo.setMinimumHeight(28)
        auto_text = f"— Auto (solver default) —" + (f": {auto_label}" if auto_label else "")
        self.combo.addItem(auto_text, "")
        selected_index = 0
        for i, row in enumerate(self.options):
            text = format_label(row)
            self.combo.addItem(text, row.get("name", text))
            if current_value and row.get("name") == current_value:
                selected_index = i + 1
        self.combo.setCurrentIndex(selected_index)
        layout.addWidget(self.combo)

        count_text = f"{len(self.options)} options available" if self.options else "0 options available — catalog not yet populated for this component"
        count_lbl = QLabel(count_text)
        count_lbl.setStyleSheet(f"color: {MUTED if self.options else WARNING}; font-size: 9.5px;")
        layout.addWidget(count_lbl)
        if note:
            note_lbl = QLabel(note)
            note_lbl.setWordWrap(True)
            note_lbl.setStyleSheet(f"color: {MUTED}; font-size: 9.5px;")
            layout.addWidget(note_lbl)

    def value(self):
        return self.combo.currentData()


def stat_box(stats, border_color=None, note=None, note_color=None):
    """Neutral info box: a row of labeled stats, optionally tinted by
    border_color, with an optional note line. Used for Shaft Sizing
    (border color reflects fail/warn/ok), Head Shaft Bearing, and Pulley
    Shell Thickness (neutral, no fail/warn logic of their own)."""
    box = QFrame()
    color = border_color or BORDER
    box.setStyleSheet(f"background-color: {PANEL2}; border: 1px solid {color}; border-radius: 5px;")
    layout = QVBoxLayout(box)
    layout.setContentsMargins(10, 8, 10, 8)
    layout.setSpacing(4)
    row = QHBoxLayout()
    row.setSpacing(16)
    for label, value in stats:
        col = QVBoxLayout()
        col.setSpacing(1)
        l = QLabel(label)
        l.setStyleSheet(f"color: {TEXT3}; font-size: 9px;")
        v = QLabel(str(value))
        v.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: 700; font-family: 'JetBrains Mono', monospace;")
        col.addWidget(l); col.addWidget(v)
        row.addLayout(col)
    row.addStretch()
    layout.addLayout(row)
    if note:
        note_lbl = QLabel(note)
        note_lbl.setWordWrap(True)
        note_lbl.setStyleSheet(f"color: {note_color or TEXT3}; font-size: 10px; margin-top: 2px;")
        layout.addWidget(note_lbl)
    return box


def toggle_pair(options, current_value, on_change):
    """Port of the solid/hollow and keyed/welded button pairs -- two
    equal-width buttons, the active one filled, the other neutral."""
    row = QHBoxLayout()
    row.setSpacing(8)
    buttons = {}

    def restyle():
        for val, btn in buttons.items():
            active = val == current_value[0]
            if active:
                btn.setStyleSheet(
                    f"background-color: rgba(74,158,255,.15); color: {PRIMARY}; "
                    f"border: 1px solid {PRIMARY}; border-radius: 5px; padding: 8px 4px; font-weight: 600;"
                )
            else:
                btn.setStyleSheet(
                    f"background-color: {PANEL2}; color: {TEXT3}; border: 1px solid {BORDER}; "
                    f"border-radius: 5px; padding: 8px 4px;"
                )

    for val in options:
        btn = QPushButton(val.capitalize())

        def clicked(checked, v=val):
            current_value[0] = v
            restyle()
            on_change(v)
        btn.clicked.connect(clicked)
        row.addWidget(btn)
        buttons[val] = btn
    restyle()
    return row


class ShaftEditDialog(QDialog):
    """Shaft Design -- 4-quadrant grid: Head Shaft (top-left), Boot Shaft
    (bottom-left), Head Shaft Bearing (top-right), Boot Shaft Bearing
    (bottom-right). Restructured from one long column per direct
    feedback: the previous version had no scrollbar and ran off the
    bottom of a real screen. The 2-column grid uses width instead of
    just height, and is wrapped in a QScrollArea as a safety net
    regardless of how tall any one quadrant's content gets.

    Pulley Shell Thickness is NOT here -- moved back to Head & Tail
    Pulley per direct correction: an earlier round over-extended "move
    bearings to the shaft modal" into also moving shell thickness, which
    wasn't actually asked for and isn't where it conceptually belongs.

    Boot Shaft and Boot Shaft Bearing are new. Checked first, not
    assumed: the backend already computes a complete, independent boot
    shaft sizing and bearing load (different span, no drive torque,
    different reaction load than the head shaft) and exposes all of it
    under results.boot_pulley.{shaft, R_boot_N, L10_boot_h} -- confirmed
    directly against a real API response before writing any UI for it,
    no backend change was needed for this part.

    Bearing selection (both quadrants) is labeled honestly as
    informational only: bearing_name is a real model field but isn't
    actually read anywhere in calculations.py, and there's no
    boot-specific equivalent at all -- found this while building the
    boot quadrant and chose to say so rather than quietly build more UI
    on a foundation that doesn't function yet.
    """

    def __init__(self, inputs, results, parent=None):
        super().__init__(parent)
        self.inputs = dict(inputs)
        self.results = results or {}
        self.setWindowTitle("Shaft Design")
        self.setMinimumWidth(820)
        self.resize(900, 680)
        self.setStyleSheet(f"background-color: {PANEL};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(modal_header("Shaft Design", "CEMA 375 §4"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        body = QWidget()
        grid = QGridLayout(body)
        grid.setContentsMargins(16, 16, 16, 16)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)
        r = self.results

        grid.addWidget(self._build_head_shaft_quadrant(r), 0, 0)
        grid.addWidget(self._build_boot_shaft_quadrant(r), 1, 0)
        grid.addWidget(self._build_head_bearing_quadrant(r), 0, 1)
        grid.addWidget(self._build_boot_bearing_quadrant(r), 1, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        scroll.setWidget(body)
        layout.addWidget(scroll)
        layout.addWidget(modal_footer(self))

    # ── Top-left ──────────────────────────────────────────────────────
    def _build_head_shaft_quadrant(self, r):
        frame, bl = quadrant_frame()
        bl.addWidget(quadrant_title("Head Shaft"))

        shaft_checks = [c for c in (r.get("checks") or []) if c.get("subsystem") == "shaft"]
        shaft_fail = any(c.get("type") == "fail" for c in shaft_checks)
        shaft_warn = any(c.get("type") == "warn" for c in shaft_checks)
        border_color = DANGER if shaft_fail else WARNING if shaft_warn else None
        note, note_color = None, None
        if shaft_fail or shaft_warn:
            msg_type = "fail" if shaft_fail else "warn"
            match = next((c.get("msg") for c in shaft_checks if c.get("type") == msg_type), None)
            if match:
                note = ("⚠ " if shaft_fail else "ℹ ") + match
                note_color = DANGER if shaft_fail else WARNING
        if r.get("d_mm") is not None:
            bl.addWidget(stat_box(
                [("Stress", f"{fmt(r.get('d_stress_mm'), 1)} mm"),
                 ("Deflection", f"{fmt(r.get('d_deflect_mm'), 1)} mm"),
                 ("Governing", f"{fmt(r.get('d_mm'), 1)} mm"),
                 ("Governed by", r.get("governed_by", "—"))],
                border_color=border_color, note=note, note_color=note_color,
            ))

        bl.addWidget(section_head("Shaft Material"))
        self.material_combo = QComboBox()
        self.material_combo.setStyleSheet(
            f"background-color: {PANEL2}; color: {TEXT}; border: 1px solid {BORDER}; "
            f"border-radius: 4px; padding: 5px 8px; font-size: 12px;"
        )
        self.material_combo.setMinimumHeight(28)
        materials = [
            ("A36", "A36 Mild Steel (τ=42 MPa) — standard"),
            ("1045_HR", "1045 Hot-Rolled (τ=52 MPa) — higher capacity"),
            ("1045_CD", "1045 Cold-Drawn (τ=70 MPa) — precision machined"),
            ("4140_QT", "4140 Q&T Alloy (τ=110 MPa) — heavy/impact duty"),
        ]
        current_material = self.inputs.get("shaft_material", "A36")
        for i, (val, text) in enumerate(materials):
            self.material_combo.addItem(text, val)
            if val == current_material:
                self.material_combo.setCurrentIndex(i)
        bl.addWidget(self.material_combo)
        mat_note = QLabel(
            f"Selected: {r.get('shaft_material_name')} · τ_allow={fmt(r.get('shaft_tau_allow_MPa'), 0)}MPa. "
            f"Also governs the boot shaft below — one grade for both."
            if r.get("shaft_material_name") else
            "Higher grades permit a smaller shaft diameter for the same load, at higher material cost."
        )
        mat_note.setWordWrap(True)
        mat_note.setStyleSheet(f"color: {MUTED}; font-size: 9.5px;")
        bl.addWidget(mat_note)

        bl.addWidget(section_head("Shaft Section"))
        self._section_val = [self.inputs.get("shaft_section", "solid")]
        bl.addLayout(toggle_pair(["solid", "hollow"], self._section_val, self._on_section_change))
        self.bore_box = QVBoxLayout()
        bl.addLayout(self.bore_box)
        self.bore_ratio = styled_spinbox(QDoubleSpinBox())
        self.bore_ratio.setRange(0.1, 0.85); self.bore_ratio.setSingleStep(0.05)
        self.bore_ratio.setValue(float(self.inputs.get("shaft_bore_ratio", 0.5)))
        self._rebuild_bore_field()

        bl.addWidget(section_head("Hub Connection"))
        self._hub_val = [self.inputs.get("shaft_hub_connection", "keyed")]
        bl.addLayout(toggle_pair(["keyed", "welded"], self._hub_val, self._on_hub_change))
        self.hub_info_box = QVBoxLayout()
        bl.addLayout(self.hub_info_box)
        self._rebuild_hub_info()

        bl.addWidget(section_head("Shaft Diameter Override"))
        self.shaft_override = styled_spinbox(QDoubleSpinBox())
        self.shaft_override.setRange(0, 500); self.shaft_override.setSingleStep(5)
        self.shaft_override.setValue(float(self.inputs.get("shaft_d_override_mm", 0)))
        bl.addLayout(field_row("Head Shaft Dia. Override", self.shaft_override, "mm",
                                note="0 = auto from stress/deflection check. Specify to force a standard bar size."))
        bl.addStretch()
        return frame

    # ── Bottom-left -- new ────────────────────────────────────────────
    def _build_boot_shaft_quadrant(self, r):
        frame, bl = quadrant_frame()
        bl.addWidget(quadrant_title("Boot Shaft"))
        boot_pulley = r.get("boot_pulley") or {}
        boot_shaft = boot_pulley.get("shaft") or {}
        if boot_shaft.get("d_mm") is not None:
            bl.addWidget(stat_box(
                [("Stress", f"{fmt(boot_shaft.get('d_stress_mm'), 1)} mm"),
                 ("Deflection", f"{fmt(boot_shaft.get('d_deflect_mm'), 1)} mm"),
                 ("Governing", f"{fmt(boot_shaft.get('d_mm'), 1)} mm"),
                 ("Governed by", boot_shaft.get("governed_by", "—"))],
            ))
        note_text = boot_shaft.get("note") or (
            "Free-running shaft (no drive torque) — bending/deflection governs, "
            "not torsion. No keyway required."
        )
        note = QLabel(note_text)
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {TEXT3}; font-size: 10px;")
        bl.addWidget(note)
        span_note = QLabel(f"Span: {fmt(boot_shaft.get('span_mm'), 0)} mm.")
        span_note.setStyleSheet(f"color: {MUTED}; font-size: 9.5px;")
        bl.addWidget(span_note)
        gap_note = QLabel(
            "No diameter override for the boot shaft yet -- this quadrant is read-only "
            "for now. Say if you'd like one added, mirroring shaft_d_override_mm above."
        )
        gap_note.setWordWrap(True)
        gap_note.setStyleSheet(f"color: {MUTED}; font-size: 9.5px; font-style: italic; margin-top: 4px;")
        bl.addWidget(gap_note)
        bl.addStretch()
        return frame

    # ── Top-right ─────────────────────────────────────────────────────
    def _build_head_bearing_quadrant(self, r):
        frame, bl = quadrant_frame()
        bl.addWidget(quadrant_title("Head Shaft Bearing"))
        shaft_d = r.get("d_mm") or 0
        if shaft_d:
            bl.addWidget(stat_box([
                ("Calc shaft d", f"{fmt(shaft_d, 1)} mm"),
                ("L10", f"{int(r.get('L10', 0)):,} h"),
                ("Radial load", f"{fmt((r.get('R_headshaft') or 0) / 1000, 1)} kN"),
            ]))
        bore_min, bore_max = (shaft_d, shaft_d * 1.9) if shaft_d else (None, None)
        self.bearing_picker = ComponentPickerWidget(
            "/components/bearings", {"bore_min": bore_min, "bore_max": bore_max},
            lambda row: f"{row.get('name')}  bore={row.get('bore')}mm  C={row.get('C')}kN  {row.get('type','')}  {row.get('seal','')}",
            self.inputs.get("bearing_name", ""), None, "Bearing Selection",
            note=(f"Showing bore {fmt(bore_min,0)}–{fmt(bore_max,0)} mm. Informational only right now -- "
                  f"the solver doesn't yet read a selected bearing back into the calculation."
                  if bore_min else None),
        )
        bl.addWidget(self.bearing_picker)
        bl.addStretch()
        return frame

    # ── Bottom-right -- new ───────────────────────────────────────────
    def _build_boot_bearing_quadrant(self, r):
        frame, bl = quadrant_frame()
        bl.addWidget(quadrant_title("Boot Shaft Bearing"))
        boot_pulley = r.get("boot_pulley") or {}
        boot_shaft = boot_pulley.get("shaft") or {}
        boot_shaft_d = boot_shaft.get("d_mm") or 0
        if boot_shaft_d:
            bl.addWidget(stat_box([
                ("Calc shaft d", f"{fmt(boot_shaft_d, 1)} mm"),
                ("L10", f"{int(boot_pulley.get('L10_boot_h', 0)):,} h"),
                ("Radial load", f"{fmt((boot_pulley.get('R_boot_N') or 0) / 1000, 1)} kN"),
            ]))
        bore_min, bore_max = (boot_shaft_d, boot_shaft_d * 1.9) if boot_shaft_d else (None, None)
        self.boot_bearing_picker = ComponentPickerWidget(
            "/components/bearings", {"bore_min": bore_min, "bore_max": bore_max},
            lambda row: f"{row.get('name')}  bore={row.get('bore')}mm  C={row.get('C')}kN  {row.get('type','')}  {row.get('seal','')}",
            self.inputs.get("boot_bearing_name", ""), None, "Bearing Selection",
            note=(f"Showing bore {fmt(bore_min,0)}–{fmt(bore_max,0)} mm. Informational only -- there's no "
                  f"boot-specific override field in the backend yet, same caveat as the head bearing above."
                  if bore_min else None),
        )
        bl.addWidget(self.boot_bearing_picker)
        bl.addStretch()
        return frame

    def _on_section_change(self, value):
        self._section_val[0] = value
        self._rebuild_bore_field()

    def _rebuild_bore_field(self):
        while self.bore_box.count():
            item = self.bore_box.takeAt(0)
            w = item.widget() if item else None
            if w:
                # setParent(None) removes it from the visual tree immediately;
                # deleteLater() alone defers cleanup and can leave a brief
                # visual ghost of the widget's last-painted pixels behind
                # (confirmed directly: a 'keyed connection' note lingered
                # for one frame after switching to 'welded').
                w.setParent(None)
                w.deleteLater()
        if self._section_val[0] == "hollow":
            r = self.results
            note = (
                f"OD {fmt(r.get('d_mm'),0)}mm · ID≈{fmt(r.get('shaft_d_inner_mm'),0)}mm · "
                f"~{fmt(r.get('shaft_mass_saving_pct'),0)}% mass reduction vs equivalent solid shaft. "
                f"Typical practice 0.4-0.7; CEMA does not mandate a ratio."
                if r.get("shaft_bore_ratio") else
                "Typical hollow shaft practice: 0.4-0.7. Higher ratio = larger required OD but greater net mass savings."
            )
            self.bore_box.addLayout(field_row("Bore Ratio (ID/OD)", self.bore_ratio, note=note))

    def _on_hub_change(self, value):
        self._hub_val[0] = value
        self._rebuild_hub_info()

    def _rebuild_hub_info(self):
        while self.hub_info_box.count():
            item = self.hub_info_box.takeAt(0)
            w = item.widget() if item else None
            if w:
                # setParent(None) removes it from the visual tree immediately;
                # deleteLater() alone defers cleanup and can leave a brief
                # visual ghost of the widget's last-painted pixels behind
                # (confirmed directly: a 'keyed connection' note lingered
                # for one frame after switching to 'welded').
                w.setParent(None)
                w.deleteLater()
        r = self.results
        if self._hub_val[0] == "welded" and r.get("weld_check"):
            wc = r["weld_check"]
            self.hub_info_box.addWidget(stat_box(
                [("Throat", f"{fmt(wc.get('t_throat_mm'), 1)} mm"),
                 ("τ actual", f"{fmt(wc.get('tau_torsion_MPa'), 1)} MPa"),
                 ("τ allow", f"{fmt(wc.get('weld_allow_MPa'), 1)} MPa"),
                 ("Governed by", (wc.get("governed_by") or "—").replace("_", " "))],
                note="E70xx fillet weld, allowable independent of shaft material grade (weld metal governs).",
            ))
        elif self._hub_val[0] == "keyed":
            lbl = QLabel("Standard ASME B17.1 keyed connection. Field-serviceable — pulley can be "
                          "removed without re-welding.")
            lbl.setWordWrap(True)
            lbl.setStyleSheet(f"color: {TEXT3}; font-size: 10px;")
            self.hub_info_box.addWidget(lbl)

    def updated_inputs(self):
        self.inputs["shaft_material"] = self.material_combo.currentData()
        self.inputs["shaft_section"] = self._section_val[0]
        self.inputs["shaft_bore_ratio"] = self.bore_ratio.value()
        self.inputs["shaft_hub_connection"] = self._hub_val[0]
        self.inputs["shaft_d_override_mm"] = self.shaft_override.value()
        self.inputs["bearing_name"] = self.bearing_picker.value()
        self.inputs["boot_bearing_name"] = self.boot_bearing_picker.value()
        return self.inputs


class InputSidebarPanel(QWidget):
    """Port of InputSidebar.jsx -- a scrollable list of SectionRow
    summaries, each opening a modal. set_data(inputs, results) like every
    other component; emits inputsChanged(dict) when the user applies an
    edit, which main.py listens to and re-runs the calculation with."""

    inputsChanged = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.inputs, self.results = {}, {}
        self.setStyleSheet(f"background-color: {BG};")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        self.list_widget = QWidget()
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(0)
        self.list_layout.addStretch()
        scroll.setWidget(self.list_widget)
        outer.addWidget(scroll)

    def set_data(self, inputs, results):
        self.inputs, self.results = dict(inputs or {}), results or {}
        self._rebuild_list()

    def _rebuild_list(self):
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item is None:
                continue
            w = item.widget()
            if w:
                # setParent(None) removes it from the visual tree immediately;
                # deleteLater() alone defers cleanup and can leave a brief
                # visual ghost of the widget's last-painted pixels behind
                # (confirmed directly: a 'keyed connection' note lingered
                # for one frame after switching to 'welded').
                w.setParent(None)
                w.deleteLater()

        mat = self.results.get("mat") or {}
        mat_name = mat.get("name", self.inputs.get("mat_id", "—"))
        summary = f"{self.inputs.get('Q_req','—')}t/h · {self.inputs.get('H_m','—')}m · {mat_name} · Fill {self.inputs.get('fill_pct','—')}%"
        process_row = SectionRow("Design Requirements", summary)
        process_row.clicked = lambda: self._open_process_dialog()
        self.list_layout.addWidget(process_row)

        # FIX (engineering-flow discussion): Belt/Chain and Bucket Selection
        # moved here, right after Design Requirements -- this used to sit
        # after Pulley/Shaft, the reverse of the order you'd actually
        # decide things in (material/tonnage/height, then drive type and
        # bucket, THEN pulley/shaft sizing that depends on them).
        is_chain = bool(self.results.get("is_chain"))
        belt_summary = (self._chain_summary() if is_chain else self._belt_summary())
        belt_row = SectionRow("Chain Selection" if is_chain else "Belt Selection", belt_summary)
        belt_row.clicked = lambda: self._open_belt_chain_dialog()
        self.list_layout.addWidget(belt_row)

        bkt = self.results.get("bucket") or {}
        bucket_summary = (f"{'Auto: ' if self.inputs.get('auto_bucket') else ''}{bkt.get('id', 'auto')} series · "
                           f"{fmt(bkt.get('V'), 1)}L · Gap {self.inputs.get('bucket_gap','—')}mm")
        bucket_row = SectionRow("Bucket Selection", bucket_summary)
        bucket_row.clicked = lambda: self._open_bucket_dialog()
        self.list_layout.addWidget(bucket_row)

        boot_pulley = self.results.get("boot_pulley") or {}
        boot_d = boot_pulley.get("boot_D_mm", self.inputs.get("boot_pulley_D_mm", "—"))
        wrap = self.results.get("wrap_effective_deg", self.inputs.get("wrap_deg", 180))
        pulley_summary = f"D_H {self.inputs.get('D_mm','—')}mm · D_B {boot_d}mm · {self.inputs.get('n_rpm','—')}rpm · Wrap {wrap}°"
        pulley_row = SectionRow("Head & Tail Pulley", pulley_summary)
        pulley_row.clicked = lambda: self._open_pulley_dialog()
        self.list_layout.addWidget(pulley_row)

        shaft_summary = (f"{self.inputs.get('shaft_material','A36')} · Ø{fmt(self.results.get('d_mm'), 1)}mm · "
                          f"{self.inputs.get('shaft_section','solid')} · {self.inputs.get('shaft_hub_connection','keyed')}")
        shaft_row = SectionRow("Shaft Design", shaft_summary)
        shaft_row.clicked = lambda: self._open_shaft_dialog()
        self.list_layout.addWidget(shaft_row)

        for sid, label in NOT_YET_PORTED:
            row = SectionRow(label, self._summary_for(sid))
            row.clicked = lambda l=label: self._open_not_yet_ported(l)
            self.list_layout.addWidget(row)

        self.list_layout.addStretch()

    def _belt_summary(self):
        r = self.results
        return f"{r.get('belt_class') or (str(r['belt_ply']) + ' PLY' if r.get('belt_ply') else 'auto')} · {fmt(r.get('belt_w'), 0)}mm"

    def _chain_summary(self):
        r = self.results
        cs = r.get("chain_selected") or {}
        return f"{cs.get('name', 'auto')} · SF={fmt(r.get('chain_SF_actual'), 2)}"

    def _summary_for(self, section_id):
        r = self.results
        if section_id == "takeup":
            return f"{self.inputs.get('takeup_type', 'gravity')} take-up"
        if section_id == "discharge":
            return f"{'HF continuous' if r.get('is_continuous') else 'Centrifugal'} · CR={fmt(r.get('cr'), 3)}"
        if section_id == "feed":
            fd = r.get("feed_design")
            return f"{fd.get('loading_type')} · Surge {fd.get('V_surge_litres')}L" if fd else "Run calculation to see boot feed geometry"
        if section_id == "casing":
            return f"{self.inputs.get('casing_t_override_mm', 'auto')} mm plate"
        if section_id == "service":
            return f"{self.inputs.get('environment', 'dry')} · μ={self.inputs.get('mu', '—')}"
        if section_id == "power":
            return f"SF {self.inputs.get('sf', '—')} · K {self.inputs.get('K_takeup', '—')}"
        return ""

    def _open_process_dialog(self):
        dlg = ProcessEditDialog(self.inputs, self.results, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.inputsChanged.emit(dlg.updated_inputs())

    def _open_belt_chain_dialog(self):
        dlg = BeltChainEditDialog(self.inputs, self.results, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.inputsChanged.emit(dlg.updated_inputs())

    def _open_bucket_dialog(self):
        dlg = BucketEditDialog(self.inputs, self.results, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.inputsChanged.emit(dlg.updated_inputs())

    def _open_pulley_dialog(self):
        dlg = PulleyEditDialog(self.inputs, self.results, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.inputsChanged.emit(dlg.updated_inputs())

    def _open_shaft_dialog(self):
        dlg = ShaftEditDialog(self.inputs, self.results, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.inputsChanged.emit(dlg.updated_inputs())

    def _open_not_yet_ported(self, label):
        NotYetPortedDialog(label, self).exec()