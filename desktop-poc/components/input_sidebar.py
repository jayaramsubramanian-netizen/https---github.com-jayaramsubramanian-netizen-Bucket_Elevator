"""
components/input_sidebar.py -- PySide6 port of InputSidebar.jsx
═══════════════════════════════════════════════════════════════════════════
Started, not complete -- InputSidebar.jsx is ~2,500 lines covering 11
sections. This round goes deeper on the 2 sections already started
(Process Design, Head & Tail Pulley) rather than spreading wider, per
direct feedback comparing this against the real rendering.

Changes this round:
    - CEMA reference removed from the sidebar's leaf rows entirely --
      it now appears exactly once per section, in that section's own
      modal header, matching how the JSX actually uses it (not repeated
      on every line of the summary list).
    - Process Design modal expanded to two columns: the original fields
      stay on the left; Material Database Search (a real, live search
      against /materials/search, not a static list) and the Custom/
      Override Properties block (OverridableField equivalents, showing
      real DB defaults pulled from results.mat_db_defaults) on the right.
    - The Dynamic Fill Advisory is now the real visual the JSX has -- a
      stat row plus a custom-painted horizontal range bar with a
      recommended-value tick and a current-value dot -- not plain text.
    - Head & Tail Pulley modal gained the "Wrap Angle Adequate" status
      card (green/amber depending on results.wrap_recommendation),
      the head:boot diameter ratio check, and the boot-pulley toggle now
      reads as a real toggle control with a "Boot locked to head" message
      when active, matching the real rendering.

Deliberate reorganization, not a faithful copy: the real JSX currently
has "Head Shaft Bearing" and "Pulley Shell Thickness" living inside
PulleyEdit. Per direct feedback, those conceptually belong with Shaft
Design, not Pulley -- they are NOT included here, and will land in the
Shaft Design modal when that gets built, not be reproduced here just
because that's where they happen to sit in the original.

Still not ported at all (still in the summary-only list, named
explicitly): Belt/Chain Selection, Bucket Selection, Take-Up Selection,
Shaft Design, Discharge Section, Feed Design, Casing Design, Service
Conditions, Power Transmission.

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
    ("belt",      "Belt / Chain Selection"),
    ("bucket",    "Bucket Selection"),
    ("takeup",    "Take-Up Selection"),
    ("discharge", "Discharge Section"),
    ("feed",      "Feed Design"),
    ("casing",    "Casing Design"),
    ("service",   "Service Conditions"),
    ("power",     "Power Transmission"),
]

ABR_HINT = {1: "Low", 2: "Low", 3: "Med", 4: "Med", 5: "High", 6: "High", 7: "V.High"}
FLOW_HINT = {1: "Free", 2: "Free", 3: "Average", 4: "Sluggish"}


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
    (real DB defaults from results.mat_db_defaults, not sentinels)."""

    def __init__(self, inputs, results, parent=None):
        super().__init__(parent)
        self.inputs = dict(inputs)
        self.results = results or {}
        self.setWindowTitle("Process Design")
        self.setMinimumWidth(760)
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

        layout.addLayout(columns)
        layout.addWidget(modal_footer(self))

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

    def updated_inputs(self):
        self.inputs["Q_req"] = self.q_req.value()
        self.inputs["H_m"] = self.h_m.value()
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

    def _summary_for(self, section_id):
        r = self.results
        bkt = r.get("bucket") or {}
        if section_id == "belt":
            return f"{r.get('belt_w', 'auto')}mm · {self.inputs.get('belt_type', 'EP')} · {r.get('belt_ply', '—')} ply"
        if section_id == "bucket":
            return f"{bkt.get('id', 'auto')} series · {bkt.get('V', '—')}L · Gap {self.inputs.get('bucket_gap', '—')}mm"
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