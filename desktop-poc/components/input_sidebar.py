"""
components/input_sidebar.py -- PySide6 port of InputSidebar.jsx
═══════════════════════════════════════════════════════════════════════════

BOX-IN-BOX BORDER SWEEP (this round)
────────────────────────────────────
Every bordered container in this file used a BARE stylesheet declaration
(no selector). Qt treats that as `* { ... }` -- it applies to the widget
AND EVERY DESCENDANT -- so each of these was stamping its border onto every
QLabel, QSpinBox and QComboBox inside it:

    SectionRow          -> border-bottom onto BOTH the label and the
                           summary label. This is the one that hits EVERY
                           row of the sidebar, which is why the sidebar
                           looked like a stack of nested boxes.
    quadrant_frame()    -> all four Shaft-dialog quadrants boxed their
                           own contents.
    wrap_box            -> the Geometric/Effective/Formula readouts.
    DynamicFillAdvisory -> all six stat labels + the note + the warning.
    StatusCard          -> headline + every stat.
    guidance card, bucket-recommendation card, chain-mode note frame.

Verified directly, not assumed: a QFrame with N child QLabels renders 2N
horizontal border runs inside itself under a bare declaration, and 0 under
a scoped one.

All of the above now go through theme.card_frame() / scoped() / plain_bg().

ALSO FIXED HERE
───────────────
  * DUPLICATE section_head(). This file imported section_head from
    dialog_helpers AND then defined its own module-level section_head()
    immediately below the imports, which silently shadowed the import.
    So dialog_helpers' legibility fix (TEXT2 @ 11px) never actually
    applied to this file -- it kept rendering the old TEXT3 @ 10px. Same
    for the old `quadrant_title`. The local copies are gone; the shared
    ones are used.
  * Six duplicated inline QComboBox stylesheets and two QLineEdit ones
    -> dialog_helpers.styled_combo() / styled_lineedit().
  * Hardcoded hex colors in _on_double_row_changed ("#94a3b8", "#f59e0b",
    "#3b82f6") -> theme tokens.

RETAINED (all still correct -- do not undo):
  * Threaded material search + debounce (MaterialSearchWorker) and the
    floating Qt.WindowType.Popup results list.
  * Threaded live guidance preview (GuidancePreviewWorker) -- it re-calls
    the BACKEND rather than duplicating the temperature/belt-limit logic
    in the frontend.
  * _detach_boot_spinbox() -- keeps boot_d_mm alive across rebuilds so the
    "match head pulley" toggle is reversible.
  * setParent(None) before deleteLater() in every rebuild, to avoid the
    one-frame ghost of the last-painted widget.
  * The chain-drive required_deg=None branch in _rebuild_wrap_card().
  * Section order (Belt/Bucket ahead of Pulley/Shaft) per the
    engineering-flow discussion.

STILL NOT PORTED (named, not silently absent -- these are FIDELITY gaps,
deliberately left for their own change so a regression can't be confused
with a styling one):
  * Status badges on sidebar rows + the Mechanical Design accordion
    rollup (subsystemBadge() in the JSX).
  * Accordion grouping/hierarchy -- this is still a flat 11-row list.
  * "Save overrides as custom material" bridge in ProcessEditDialog.
  * Chain-mode info note in ProcessEdit.
  * Standards footer.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea,
    QDialog, QPushButton, QDoubleSpinBox, QSpinBox, QLineEdit,
    QListWidget, QListWidgetItem, QAbstractSpinBox, QComboBox, QGridLayout,
)
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QTimer, QThread
from PySide6.QtGui import QPainter, QColor, QBrush, QPen

from theme import (
    BG, PANEL, PANEL2, SURFACE, BORDER, BORDER2,
    TEXT, TEXT2, TEXT3, MUTED,
    PRIMARY, PRIMARY_DIM, PRIMARY_RING, INFO_DIM, INFO_BORDER,
    SUCCESS, SUCCESS_DIM, SUCCESS_BORDER,
    WARNING, WARNING_DIM, WARNING_BORDER,
    DANGER, DANGER_DIM, DANGER_BORDER,
    R_SM, R_MD, FF_MONO,
    scoped, plain_bg, card_frame,
)
from api_client import search_materials, get_material, fetch_components, fetch_design
from .dialog_helpers import (
    fmt, section_head, field_row, styled_spinbox, styled_combo, styled_lineedit,
    modal_header, modal_footer, stat_box, ToggleButton, toggle_pair,
    status_badge, flag_note, ComponentPickerWidget,
)
from .takeup_edit import TakeupEditDialog
from .feed_edit import FeedEditDialog
from .discharge_edit import DischargeEditDialog
from .casing_edit import CasingEditDialog
from .service_edit import ServiceEditDialog
from .power_edit import PowerEditDialog

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


def sel_button_qss(btn, active, padding="8px"):
    """Scoped QSS for a selection button (drive type, strands, etc).
    Mirrors dialog_helpers' internal selection styling so all of them stay
    visually identical."""
    if active:
        return scoped(btn,
                      f"background-color: {PRIMARY_DIM}; color: {PRIMARY}; "
                      f"border: 1px solid {PRIMARY_RING}; border-radius: {R_SM}px; "
                      f"padding: {padding}; font-weight: 600;")
    return scoped(btn,
                  f"background-color: {SURFACE}; color: {TEXT2}; "
                  f"border: 1px solid {BORDER}; border-radius: {R_SM}px; "
                  f"padding: {padding};")


def scroll_area():
    """A borderless QScrollArea, scoped. Every dialog below used a bare
    'QScrollArea { border: none; }' -- class-scoped rather than object-
    scoped, so it also stripped borders from any nested scroll area. Never
    bit us (there are none), but it's the same class of imprecision."""
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setStyleSheet(scoped(sa, "border: none; background: transparent;"))
    return sa


def quadrant_frame():
    """One cell of a 2x2 grid -- a bordered container so the grid structure
    is visually obvious, not just implied by spacing.

    SCOPED: the bare version gave its border to every widget inside the
    quadrant -- which is why the Shaft dialog's four quadrants each looked
    like a box full of boxes.
    """
    return card_frame(bg=BG, border=BORDER, radius=R_SM,
                      margins=(12, 12, 12, 12), spacing=8)


def quadrant_title(text):
    """Quadrant-level title -- deliberately NO CEMA reference. That lives
    exactly once, in the modal's own header."""
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color: {TEXT}; font-size: 14px; font-weight: 700;")
    return lbl


def clear_layout(layout):
    """Recursively empty a layout.

    setParent(None) removes a widget from the visual tree immediately;
    deleteLater() alone defers cleanup and can leave a one-frame ghost of
    the widget's last-painted pixels (confirmed directly: a 'keyed
    connection' note lingered for a frame after switching to 'welded').

    This was copy-pasted verbatim in seven places in this file. One copy now.
    """
    while layout.count():
        item = layout.takeAt(0)
        if item is None:
            continue
        w = item.widget()
        if w:
            w.setParent(None)
            w.deleteLater()
        else:
            sub = item.layout()
            if sub:
                clear_layout(sub)


class SectionRow(QFrame):
    """Port of the JSX's SectionRow -- label + status badge + summary text + a
    pencil icon, the whole row clickable.

    depth=1 rows are the accordion children: indented, with a `└` connector, a
    slightly smaller/lighter label. depth=0 is a bare top-level row.

    SCOPED: the bare declaration carried `border-bottom`, which the row's label
    AND its summary label both inherited -- so every single sidebar row drew
    three horizontal rules instead of one.

    RETAINED: no CEMA reference on the row -- that lives once, on the accordion
    group header, exactly as the JSX does it.
    """

    def __init__(self, label, summary="", badge=None, depth=0,
                 clickable=True, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor if clickable
                       else Qt.CursorShape.ArrowCursor)
        self.setStyleSheet(scoped(
            self,
            f"background-color: transparent; border: none; "
            f"border-bottom: 1px solid {BORDER};",
            extra="{sel}:hover { background-color: rgba(255,255,255,.03); }",
        ))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12 + depth * 14, 8, 12, 8)
        layout.setSpacing(6)

        if depth > 0:
            elbow = QLabel("└")
            elbow.setStyleSheet(f"color: {BORDER2}; font-size: 13px;")
            elbow.setAlignment(Qt.AlignmentFlag.AlignTop)
            layout.addWidget(elbow)

        col = QVBoxLayout()
        col.setSpacing(2)

        top = QHBoxLayout()
        top.setSpacing(6)
        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"color: {TEXT2 if depth else TEXT}; "
            f"font-size: {12 if depth else 13}px; "
            f"font-weight: {600 if depth else 700};")
        top.addWidget(lbl)
        if badge:
            top.addWidget(StatusPill(badge))
        top.addStretch()
        if clickable:
            pencil = QLabel("✎")
            pencil.setStyleSheet(f"color: {PRIMARY}; font-size: 13px;")
            top.addWidget(pencil)
        col.addLayout(top)

        if summary:
            sum_lbl = QLabel(summary)
            sum_lbl.setStyleSheet(f"color: {TEXT3}; font-size: 13px;")
            sum_lbl.setWordWrap(False)
            col.addWidget(sum_lbl)

        layout.addLayout(col)

    def mousePressEvent(self, event):
        if self.cursor().shape() == Qt.CursorShape.PointingHandCursor:
            self.clicked()
        super().mousePressEvent(event)

    def clicked(self):
        pass  # overridden via direct assignment from the panel that creates this row


# ── Status badges ────────────────────────────────────────────────────────────
# Ported from the JSX's subsystemBadge(). The semantics are preserved EXACTLY,
# because they encode two fixes that were hard-won on the web side:
#
#   1. Filter by SUBSYSTEM FIRST, keyword second (never a bare keyword match
#      across the whole checks[] array). The old checkBadge() cross-contaminated
#      subsystems -- "material" alone matched process/shaft/bucket/service/
#      boot_pulley checks all at once. Same lesson already applied in
#      equipment_tree.node_status() and service_edit's corrosion filter.
#
#   2. No matches inside the subsystem is a REAL PASS, not "unevaluated" --
#      provided a calculation actually ran. Most materials genuinely emit ZERO
#      subsystem="service" checks (ATEX/hygroscopic are conditional), and
#      returning nothing there left Service Conditions permanently blank.
#
# Returns (label, color) or None. None means "no calculation has run yet".
BADGE_COLORS = {
    "FAIL": (DANGER, DANGER_DIM, DANGER_BORDER),
    "WARN": (WARNING, WARNING_DIM, WARNING_BORDER),
    "PASS": (SUCCESS, SUCCESS_DIM, SUCCESS_BORDER),
    "PENDING": (MUTED, "transparent", BORDER),
}


def subsystem_badge(results, subsystems, keywords=None):
    checks = (results or {}).get("checks") or []
    if not checks:
        return None   # genuinely nothing to report yet -- stays blank
    subs = [subsystems] if isinstance(subsystems, str) else list(subsystems)
    # `?? "process"` in the JSX -- an untagged check is treated as process.
    in_sub = [c for c in checks if (c.get("subsystem") or "process") in subs]
    if keywords:
        kw = [k.lower() for k in keywords]
        in_sub = [c for c in in_sub
                  if any(k in (c.get("msg") or "").lower() for k in kw)]
    if any(c.get("type") == "fail" for c in in_sub):
        return "FAIL"
    if any(c.get("type") == "warn" for c in in_sub):
        return "WARN"
    return "PASS"   # evaluated, nothing flagged -- see note 2 above


def merge_badges(*badges):
    """Rollup for an accordion header: FAIL beats WARN beats everything else.

    Mirrors the JSX exactly, including its asymmetry: a group whose children ALL
    pass shows NO badge (the JSX's `.find(FAIL) ?? .find(WARN)` returns
    undefined). Rows still show their own PASS. Kept rather than 'improved' --
    the group header is there to surface problems, and a column of PASS pills
    down the headers would drown the one that matters.
    """
    if any(b == "FAIL" for b in badges):
        return "FAIL"
    if any(b == "WARN" for b in badges):
        return "WARN"
    return None


class StatusPill(QLabel):
    def __init__(self, label, parent=None):
        super().__init__(label, parent)
        color, dim, border = BADGE_COLORS.get(label, BADGE_COLORS["PENDING"])
        self.setStyleSheet(scoped(
            self,
            f"background-color: {dim}; color: {color}; "
            f"border: 1px solid {border}; border-radius: 999px; "
            f"padding: 1px 7px; font-size: 12px; font-weight: 700;"
        ))


class AccordionGroup(QWidget):
    """Collapsible group header + its child rows -- port of the JSX's
    AccordionGroup. The header carries the group label, its CEMA reference (the
    ONE place a CEMA tag appears in the sidebar), a rollup badge, and a chevron
    that rotates on open.

    SCOPED: the header's `border-bottom` would otherwise be inherited by the
    label, the CEMA tag, the badge and the chevron alike.
    """

    def __init__(self, label, cema=None, badge=None, default_open=True, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._header = QFrame()
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.setStyleSheet(scoped(
            self._header,
            f"background-color: rgba(255,255,255,.025); border: none; "
            f"border-bottom: 1px solid {BORDER};",
            extra="{sel}:hover { background-color: rgba(255,255,255,.05); }",
        ))
        hl = QHBoxLayout(self._header)
        hl.setContentsMargins(12, 10, 12, 10)
        hl.setSpacing(8)

        title = QLabel(label)
        title.setStyleSheet(f"color: {TEXT}; font-size: 16px; font-weight: 700;")
        hl.addWidget(title)
        if cema:
            cema_lbl = QLabel(cema)
            cema_lbl.setStyleSheet(f"color: {TEXT3}; font-size: 13px;")
            hl.addWidget(cema_lbl)
        hl.addStretch()
        if badge:
            hl.addWidget(StatusPill(badge))
        self._chevron = QLabel()
        self._chevron.setStyleSheet(f"color: {TEXT3}; font-size: 14px;")
        hl.addWidget(self._chevron)

        self._header.mousePressEvent = lambda _e: self.toggle()
        outer.addWidget(self._header)

        self._body = QWidget()
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(0)
        outer.addWidget(self._body)

        self._open = default_open
        self._sync()

    def add_row(self, row):
        self._body_layout.addWidget(row)

    def toggle(self):
        self._open = not self._open
        self._sync()

    def _sync(self):
        self._chevron.setText("⌄" if self._open else "›")
        self._body.setVisible(self._open)


class DynamicFillBarWidget(QWidget):
    """Custom-painted horizontal range bar -- direct port of the JSX's
    inline-styled div stack: a track, a highlighted min-max band, a
    recommended-value tick, and a current-value dot (green if in range, red
    if not). Same pct() mapping as the original: clamp((v-30)/70*100, 0, 100),
    i.e. the 30-100% fill range mapped to the bar's full width.

    Custom-painted, so it has no children and was never affected by the
    cascade -- same structural immunity as KPIChip."""

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
        p.setBrush(QBrush(QColor(SURFACE)))
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
            in_range = ((self.min_v is None or self.cur_v >= self.min_v) and
                        (self.max_v is None or self.cur_v <= self.max_v))
            dot_color = QColor(SUCCESS if in_range else DANGER)
            p.setPen(QPen(QColor(PANEL2), 2))
            p.setBrush(QBrush(dot_color))
            p.drawEllipse(QPointF(xc, track_y + track_h / 2), 7, 7)
        p.end()

    def update_values(self, min_v, max_v, rec_v, cur_v):
        self.min_v, self.max_v, self.rec_v, self.cur_v = min_v, max_v, rec_v, cur_v
        self.update()


class DynamicFillAdvisory(QFrame):
    """The full advisory block: header, 6-stat row, the bar, note text, and a
    spacing warning when applicable -- the complete visual from ProcessEdit,
    not a text summary of it.

    SCOPED: the bare declaration boxed all six stat labels, the note and the
    warning line individually.
    """

    def __init__(self, results, current_fill_pct, parent=None):
        super().__init__(parent)
        r = results or {}
        df = r.get("dynamic_fill") or {}
        min_v, max_v = r.get("min_fill_pct"), r.get("max_fill_pct")
        rec_v = df.get("recommended_fill_pct")

        self.setStyleSheet(scoped(
            self,
            f"background-color: {INFO_DIM}; border: 1px solid {INFO_BORDER}; "
            f"border-radius: {R_SM}px;"
        ))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        head = QLabel("●  DYNAMIC FILL ADVISORY (CEMA §6)")
        head.setStyleSheet(
            f"color: {PRIMARY}; font-size: 13px; font-weight: 700; letter-spacing: .5px;")
        layout.addWidget(head)

        stats = QHBoxLayout()
        stats.setSpacing(16)
        in_range = ((min_v is None or current_fill_pct >= min_v) and
                    (max_v is None or current_fill_pct <= max_v))
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
            l.setStyleSheet(f"color: {TEXT3}; font-size: 12px;")
            v = QLabel(value)
            v.setStyleSheet(
                f"color: {color}; font-size: 15px; font-weight: 700; "
                f"font-family: {FF_MONO};")
            col.addWidget(l)
            col.addWidget(v)
            stats.addLayout(col)
        stats.addStretch()
        layout.addLayout(stats)

        self.bar = DynamicFillBarWidget(min_v, max_v, rec_v, current_fill_pct)
        layout.addWidget(self.bar)

        if df.get("note"):
            note = QLabel(df["note"])
            note.setWordWrap(True)
            note.setStyleSheet(f"color: {TEXT2}; font-size: 13px;")
            layout.addWidget(note)

        spacing_status = df.get("spacing_status")
        if spacing_status and spacing_status != "optimal":
            warn = QLabel(
                f"⚠ Spacing is {spacing_status.replace('_', ' ')} — adjust Bucket "
                f"Spacing Gap to approach {fmt(df.get('optimal_spacing_mm'), 0)}mm"
            )
            warn.setWordWrap(True)
            warn.setStyleSheet(f"color: {WARNING}; font-size: 13px; margin-top: 2px;")
            layout.addWidget(warn)


class MaterialSearchWorker(QThread):
    """Runs the /materials/search HTTP call off the GUI thread.

    The previous version called search_materials() directly inside
    textChanged's handler -- a synchronous network request on the GUI thread,
    on every keystroke. Not a PySide6 limitation; Qt fully supports async
    network calls (this is exactly what QThread is for). Confirmed by moving
    the call here: the freeze goes away regardless of request latency.
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


class GuidancePreviewWorker(QThread):
    """Runs a full /calculate request in the background so the Material-Based
    Design Guidance card reacts live to in-dialog edits (temperature, capacity,
    material) without the user having to Apply, close and reopen.

    The fix is NOT to recompute the temperature-vs-belt-limit logic in the
    frontend -- that would be exactly the duplicated physics the architecture
    forbids, and a second copy of the threshold could drift from
    BELT_TEMP_LIMITS in calculations.py. Instead this calls the same backend
    endpoint main.py's run_calculation() uses, eagerly on a debounce, and
    discards the result (never applied to the real payload) unless the user
    clicks Apply. No engineering logic exists here that didn't already exist
    in the backend.
    """
    resultsReady = Signal(dict)

    def __init__(self, payload, parent=None):
        super().__init__(parent)
        self.payload = payload

    def run(self):
        try:
            results = fetch_design(self.payload)
        except Exception:
            results = {}
        self.resultsReady.emit(results)


class MaterialChip(QLabel):
    def __init__(self, text, color, parent=None):
        super().__init__(text, parent)
        c = QColor(color)
        self.setStyleSheet(scoped(
            self,
            f"background-color: rgba({c.red()},{c.green()},{c.blue()},.15); "
            f"color: {color}; "
            f"border: 1px solid rgba({c.red()},{c.green()},{c.blue()},.4); "
            f"border-radius: 999px; padding: 2px 8px; "
            f"font-size: 12px; font-weight: 700;"
        ))


class MaterialSearchWidget(QWidget):
    """Port of MaterialSearchDropdown.jsx: type to search the live
    /materials/search endpoint, click a result to select it. Chips below the
    box show the selected material's category/density/abrasiveness.

    RETAINED (two separate real bugs, both still fixed):
      1. Every keystroke fired a blocking network call on the GUI thread ->
         300ms debounce + MaterialSearchWorker.
      2. The results list was an inline widget in this widget's own
         QVBoxLayout, so when it became visible the surrounding layout didn't
         reliably reflow and it overlapped the chip row and the Custom/Override
         section below. Rebuilt as a true floating popup (Qt.WindowType.Popup),
         which occupies no space in the surrounding layout at all -- that
         removes the whole category of overlap rather than chasing the exact
         reflow timing.
    """

    materialSelected = Signal(str)

    def __init__(self, current_mat_id, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.search_box = styled_lineedit(QLineEdit(), placeholder="Search materials...")
        self.search_box.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.search_box)

        # Floating popup, deliberately NOT added to `layout`.
        # QListWidget::item rules are intentional descendant targeting (the
        # items ARE what we mean to style), not an accidental cascade.
        self.results_popup = QListWidget(None)
        self.results_popup.setWindowFlags(Qt.WindowType.Popup)
        self.results_popup.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.results_popup.setStyleSheet(f"""
            QListWidget {{ background-color: {PANEL2}; color: {TEXT2};
                border: 1px solid {BORDER2}; border-radius: {R_MD}px;
                font-size: 14px; }}
            QListWidget::item {{ padding: 5px 8px; border: none; }}
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
            item = QListWidgetItem(
                f"{mat.get('name')}  ·  {mat.get('category')}  ·  "
                f"{fmt(mat.get('rho_loose'), 0)} kg/m³")
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
        clear_layout(self.chip_row)
        try:
            mat = get_material(mat_id)
        except Exception:
            mat = None
        if not mat:
            return
        name_lbl = QLabel(mat.get("name", mat_id))
        name_lbl.setStyleSheet(f"color: {TEXT}; font-size: 14px; font-weight: 600;")
        self.chip_row.addWidget(name_lbl)
        self.chip_row.addWidget(MaterialChip(mat.get("category", "—"), PRIMARY))
        self.chip_row.addWidget(MaterialChip(f"{fmt(mat.get('rho_loose'), 0)} kg/m³", TEXT3))
        abr = mat.get("abr_code")
        if abr is not None:
            self.chip_row.addWidget(
                MaterialChip(f"{ABR_HINT.get(abr, '—')} abr", SUCCESS if abr <= 3 else WARNING))
        self.chip_row.addStretch()


class OverridableSpinBox(QWidget):
    """Mirrors the JSX's OverridableField exactly: shows the real database
    default value when no override is active (not a bare 0/-1 sentinel), and
    snaps back to the sentinel if the user types the exact default back."""

    def __init__(self, label, db_value, sentinel, current_value, unit="", hint="",
                 is_int=False, parent=None):
        super().__init__(parent)
        self.db_value = db_value
        self.sentinel = sentinel
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {TEXT2}; font-size: 13px; font-weight: 600;")
        layout.addWidget(lbl)

        is_active = ((current_value > 0) if sentinel == 0
                     else (current_value is not None and current_value >= 0))
        display_value = current_value if is_active else (
            db_value if db_value is not None else sentinel)

        row = QHBoxLayout()
        self.spin = styled_spinbox(QSpinBox() if is_int else QDoubleSpinBox())
        # In this 2-column-within-2-column layout each field gets roughly a
        # quarter of the modal width -- too narrow for the native up/down
        # arrows to render without overlapping 4-digit values like "1298".
        # Removing them is also better UX here: an override is something you
        # type an exact value into, not nudge with tiny arrows.
        self.spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.spin.setRange(sentinel, 5000)
        self.spin.setValue(display_value if display_value is not None else sentinel)
        row.addWidget(self.spin)
        if unit:
            u = QLabel(unit)
            u.setStyleSheet(f"color: {TEXT3}; font-size: 13px;")
            row.addWidget(u)
        layout.addLayout(row)

        self.note = QLabel()
        self.note.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        self.note.setWordWrap(True)
        self._hint = hint
        self._update_note(is_active)
        layout.addWidget(self.note)
        self.spin.valueChanged.connect(self._on_value_changed)

    def _update_note(self, is_active):
        if self.db_value is None:
            text = "No calculation yet — showing placeholder until a material is selected"
        elif is_active:
            text = f"Overriding for this run — database default is {fmt(self.db_value, 1)}"
        else:
            text = "Database default for this material — edit to override for this run"
        if self._hint:
            text = f"{text}  ({self._hint})"
        self.note.setText(text)

    def _on_value_changed(self, value):
        is_active = self.db_value is None or abs(value - self.db_value) > 1e-9
        self._update_note(is_active)

    def value_or_sentinel(self):
        value = self.spin.value()
        if self.db_value is not None and abs(value - self.db_value) < 1e-9:
            return self.sentinel
        return value

    def update_db_value(self, new_db_value):
        """Refresh this field's database default to match whatever material is
        now selected.

        Selecting a different material via search only ever updated
        inputs["mat_id"] -- nothing told these 6 fields their db_value was now
        stale, so they kept showing the PREVIOUS material's numbers.

        Always resets to the new default (clearing any active override) rather
        than trying to decide whether a numeric override typed for the old
        material should carry over to a different one -- that ambiguity is
        exactly the kind of edge case worth avoiding outright, not handling
        cleverly."""
        self.db_value = new_db_value
        self.spin.setValue(new_db_value if new_db_value is not None else self.sentinel)
        self._update_note(False)


class ProcessEditDialog(QDialog):
    """Two columns: LEFT keeps drive type / Q_req / H_m / fill% / the real
    Dynamic Fill Advisory visual; RIGHT has the live Material Database Search
    and the Custom/Override Properties block (real DB defaults from
    results.mat_db_defaults, not sentinels).

    Material Temperature carries a live advisory showing the database's
    typical/CEMA-sourced max temperature for the selected material when one
    exists (temp_max, part of mat_db_defaults -- confirmed directly, no extra
    API call needed). All 80 static fallback-list materials currently return
    temp_max = None (confirmed in materials_lookup.py) -- CEMA 375/550
    per-material temperature data isn't integrated yet; that's real, not a
    display bug. When it's None the advisory says so and asks the user to
    enter a value from their own process conditions, rather than letting the
    unlabeled 20°C starting value imply a default that doesn't exist. The
    advisory is purely informational -- it never overwrites what the user typed.
    """

    def __init__(self, inputs, results, parent=None):
        super().__init__(parent)
        self.inputs = dict(inputs)
        self.results = results or {}
        self.setWindowTitle("Process Design")
        self.setMinimumWidth(760)
        self.resize(780, 700)
        self.setStyleSheet(plain_bg(self, PANEL))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(modal_header("Process Design", "CEMA 375 §4"))

        columns = QHBoxLayout()
        columns.setContentsMargins(16, 16, 16, 16)
        columns.setSpacing(20)

        left = QVBoxLayout()
        left.setSpacing(10)
        # Material/tonnage/height are decided BEFORE drive type, not after --
        # the order on screen matches the order you'd actually think it through.
        left.addWidget(section_head("Process Requirements"))
        row2 = QHBoxLayout()
        self.q_req = styled_spinbox(QDoubleSpinBox())
        self.q_req.setRange(1, 5000)
        self.q_req.setSingleStep(1)
        self.q_req.setValue(float(self.inputs.get("Q_req", 100)))
        row2.addLayout(field_row("Required Capacity", self.q_req, "t/h"))
        self.h_m = styled_spinbox(QDoubleSpinBox())
        self.h_m.setRange(1, 200)
        self.h_m.setSingleStep(0.5)
        self.h_m.setValue(float(self.inputs.get("H_m", 25)))
        row2.addLayout(field_row("Lift Height", self.h_m, "m"))
        left.addLayout(row2)

        self.material_temp = styled_spinbox(QDoubleSpinBox())
        self.material_temp.setRange(-30, 400)
        self.material_temp.setSingleStep(10)
        self.material_temp.setValue(float(self.inputs.get("material_temperature_c", 20)))
        left.addLayout(field_row(
            "Material Temperature", self.material_temp, "°C",
            note="20°C = ambient. Drives belt-vs-chain guidance below — set this for hot "
                 "materials (cement 80-120°C, clinker 150-300°C) before deciding drive type."
        ))

        # Temperature advisory -- separate from the static note above. This is
        # dynamic: it reflects the actual DB value for whichever material is
        # currently selected, and updates live in _on_material_selected().
        self.temp_advisory_box = QVBoxLayout()
        left.addLayout(self.temp_advisory_box)
        db_init = self.results.get("mat_db_defaults") or {}
        self._update_temp_advisory(db_init.get("temp_max"), db_init.get("name"))

        # Design Guidance -- material temperature and character advise drive
        # type and discharge style HERE, before the Drive Type decision below,
        # instead of only surfacing as a fail/warn check after a belt was
        # already chosen and a full calculation run. Checked against the
        # backend's actual bucket_recommendation() output, not a second copy
        # of that logic living here.
        self.guidance_box = QVBoxLayout()
        left.addLayout(self.guidance_box)
        self._rebuild_guidance()

        # Debounced LIVE preview, not a client-side threshold check -- see
        # GuidancePreviewWorker for why that's the architecturally correct fix
        # rather than a shortcut. Q_req is a trigger too, since
        # bucket_recommendation() takes Q_req as a real parameter on the
        # backend (not just material_temp_c), confirmed in calculations.py.
        self._guidance_debounce = QTimer(self)
        self._guidance_debounce.setSingleShot(True)
        self._guidance_debounce.setInterval(450)
        self._guidance_debounce.timeout.connect(self._refresh_guidance_preview)
        self._guidance_worker = None
        self.material_temp.valueChanged.connect(lambda _v: self._guidance_debounce.start())
        self.q_req.valueChanged.connect(lambda _v: self._guidance_debounce.start())

        left.addWidget(section_head("Drive Type"))
        drive_row = QHBoxLayout()
        self.belt_btn = QPushButton("🔵 Belt Drive")
        self.chain_btn = QPushButton("⛓ Chain Drive")
        for btn, val in ((self.belt_btn, "belt"), (self.chain_btn, "chain")):
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, v=val: self._set_drive_type(v))
            drive_row.addWidget(btn)
        self._set_drive_type(self.inputs.get("conveyor_type", "belt"), restyle_only=True)
        left.addLayout(drive_row)

        self.fill_pct = styled_spinbox(QSpinBox())
        self.fill_pct.setRange(30, 100)
        self.fill_pct.setSingleStep(5)
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
        sep.setStyleSheet(plain_bg(sep, BORDER2))
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
        override_note.setStyleSheet(f"color: {TEXT2}; font-size: 13px;")
        right.addWidget(override_note)

        self.custom_name = styled_lineedit(
            QLineEdit(str(self.inputs.get("custom_mat_name", ""))))
        right.addLayout(field_row(
            "Custom Display Name", self.custom_name,
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
                                          self.inputs.get("custom_flowability", 0),
                                          is_int=True, hint="1=Free 4=Sluggish")
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

        body = QWidget()
        body.setLayout(columns)
        scroll = scroll_area()
        scroll.setWidget(body)
        layout.addWidget(scroll)
        layout.addWidget(modal_footer(self))

    def _update_temp_advisory(self, temp_max, material_name=None):
        """Refresh the temperature advisory line.

        Honest either way: when the database has a real typical/CEMA-sourced
        value, show it as a labeled reference (never auto-applied -- the field
        above always keeps whatever the user typed). When it doesn't (None --
        true for every static fallback-list material right now), say so plainly
        and ask the user to enter a value themselves, rather than letting the
        unlabeled 20°C starting value imply a default that doesn't exist for
        that material."""
        name = material_name or "this material"
        clear_layout(self.temp_advisory_box)
        if temp_max is not None:
            flag_note("info",
                      f"Typical max on file for {name}: {fmt(temp_max, 0)}°C. "
                      f"Adjust the field above if your process conditions differ.",
                      parent_layout=self.temp_advisory_box)
        else:
            flag_note("warn",
                      f"No typical temperature on file for {name} — CEMA 375/550 "
                      f"per-material temperature data isn't integrated yet. Enter a "
                      f"value above based on your actual process conditions.",
                      parent_layout=self.temp_advisory_box)

    def _rebuild_advisory(self):
        clear_layout(self.advisory_box)
        if self.results.get("min_fill_pct") is not None or self.results.get("dynamic_fill"):
            self.advisory_box.addWidget(
                DynamicFillAdvisory(self.results, self.fill_pct.value()))

    def _rebuild_guidance(self):
        clear_layout(self.guidance_box)
        rec = self.results.get("bucket_recommendation")
        if not rec:
            return
        current_drive = self.inputs.get("conveyor_type", "belt")
        recommended_drive = rec.get("recommended_drive_type", "belt")
        mismatch = current_drive != recommended_drive

        # Neutral card throughout, with a small status_badge() carrying the
        # match/mismatch state next to the headline -- not a colored
        # background/border wrapped around the whole thing.
        outer, bl = card_frame(bg=PANEL2, border=BORDER, radius=R_MD,
                               margins=(14, 12, 14, 12), spacing=8)

        head_row = QHBoxLayout()
        head_row.setSpacing(8)
        head_row.addWidget(status_badge("fail" if mismatch else "ok", size=16))
        head = QLabel("MATERIAL-BASED DESIGN GUIDANCE")
        head.setStyleSheet(
            f"color: {TEXT2}; font-size: 13px; font-weight: 700; letter-spacing: .6px;")
        head_row.addWidget(head)
        head_row.addStretch()
        bl.addLayout(head_row)

        drive_line = QLabel(
            f"You've selected {current_drive.upper()}, but material temperature "
            f"suggests {recommended_drive.upper()}"
            if mismatch else
            f"{current_drive.capitalize()} matches the material-temperature recommendation"
        )
        drive_line.setWordWrap(True)
        drive_line.setStyleSheet(f"color: {TEXT}; font-size: 15px; font-weight: 700;")
        bl.addWidget(drive_line)

        reason1 = QLabel(rec.get("drive_type_reasoning", ""))
        reason1.setWordWrap(True)
        reason1.setStyleSheet(f"color: {TEXT2}; font-size: 14px;")
        bl.addWidget(reason1)

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(plain_bg(divider, BORDER))
        bl.addWidget(divider)

        discharge_line = QLabel(
            f"Discharge character: {rec.get('discharge_type', '—').capitalize()} "
            f"({rec.get('recommended_style', '—')} style)"
        )
        discharge_line.setStyleSheet(f"color: {TEXT}; font-size: 14px; font-weight: 700;")
        bl.addWidget(discharge_line)

        reason2 = QLabel(rec.get("reasoning", ""))
        reason2.setWordWrap(True)
        reason2.setStyleSheet(f"color: {TEXT2}; font-size: 14px;")
        bl.addWidget(reason2)

        # This note used to claim "Based on the last calculated result -- click
        # Apply..." which became false once _refresh_guidance_preview() started
        # keeping the card current as the user types. Replaced with what IS
        # still true: it's a live preview, not the calculation that gets saved.
        live_note = QLabel(
            "Live preview — updates automatically as you edit material, temperature, or "
            "capacity above. Click Apply to save these changes to the design."
        )
        live_note.setWordWrap(True)
        live_note.setStyleSheet(f"color: {MUTED}; font-size: 13px; margin-top: 2px;")
        bl.addWidget(live_note)

        self.guidance_box.addWidget(outer)

    def _preview_payload(self):
        """A full calculation payload reflecting the dialog's CURRENT (possibly
        unapplied) field values, for the live guidance preview only -- this is
        never what gets sent on Apply (that's still updated_inputs(), built
        fresh from final widget state)."""
        payload = dict(self.inputs)
        payload["Q_req"] = self.q_req.value()
        payload["H_m"] = self.h_m.value()
        payload["material_temperature_c"] = self.material_temp.value()
        payload["mat_id"] = self.material_search.current_mat_id
        payload["fill_pct"] = self.fill_pct.value()
        return payload

    def _refresh_guidance_preview(self):
        if self._guidance_worker is not None and self._guidance_worker.isRunning():
            self._guidance_worker.resultsReady.disconnect()
            self._guidance_worker.quit()
            self._guidance_worker.wait()
        self._guidance_worker = GuidancePreviewWorker(self._preview_payload(), parent=self)
        self._guidance_worker.resultsReady.connect(self._on_guidance_preview_ready)
        self._guidance_worker.start()

    def _on_guidance_preview_ready(self, results):
        if not results:
            return
        # Only refresh the guidance-relevant field -- not the whole results dict
        # -- so a background preview can't silently overwrite other fields (wrap
        # angle, shaft sizing) that this or another open dialog is still showing
        # from the last actually-Applied calculation.
        self.results["bucket_recommendation"] = results.get("bucket_recommendation")
        self._rebuild_guidance()

    def _on_material_selected(self, mat_id):
        self.inputs["mat_id"] = mat_id
        # This used to be the entire method -- updating mat_id but never
        # refreshing the 6 override fields, which is why they kept showing the
        # previous material's numbers. get_material() uses the same field names
        # as results.mat_db_defaults, confirmed against a real API response.
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
            self._update_temp_advisory(mat.get("temp_max"), mat.get("name"))
        # Material selection affects the drive-type/discharge recommendation as
        # much as temperature does -- same debounced live-preview path, not a
        # separate one-off fetch that could drift out of sync.
        self._guidance_debounce.start()

    def _set_drive_type(self, value, restyle_only=False):
        if not restyle_only:
            self.inputs["conveyor_type"] = value
        for btn, val in ((self.belt_btn, "belt"), (self.chain_btn, "chain")):
            btn.setChecked(val == value)
            btn.setStyleSheet(sel_button_qss(btn, val == value, padding="8px"))
        # Mismatch warning is a straight comparison against the last-calculated
        # recommendation, not a recalculation -- safe to refresh immediately on
        # toggle.
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


class StatusCard(QFrame):
    """Status badge + title + a row of labeled stats -- port of PulleyEdit's
    "Wrap Angle Adequate" / "Wrap Angle — Slip Risk" block.

    Neutral box throughout, with a small status_badge() next to the headline
    carrying the color -- the same visual language every modal uses now.

    SCOPED: the bare declaration boxed the headline and every stat label.
    """

    def __init__(self, adequate, title_ok, title_warn, stats, note=None, parent=None):
        super().__init__(parent)
        self.setStyleSheet(scoped(
            self,
            f"background-color: {PANEL2}; border: 1px solid {BORDER}; "
            f"border-radius: {R_SM}px;"
        ))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)
        head_row = QHBoxLayout()
        head_row.setSpacing(8)
        head_row.addWidget(status_badge("ok" if adequate else "warn", size=16))
        head = QLabel(title_ok if adequate else title_warn)
        head.setStyleSheet(
            f"color: {TEXT2}; font-size: 13px; font-weight: 700; letter-spacing: .5px;")
        head_row.addWidget(head)
        head_row.addStretch()
        layout.addLayout(head_row)
        row = QHBoxLayout()
        row.setSpacing(16)
        for label, value in stats:
            col = QVBoxLayout()
            col.setSpacing(1)
            l = QLabel(label)
            l.setStyleSheet(f"color: {TEXT3}; font-size: 12px;")
            v = QLabel(str(value))
            v.setStyleSheet(
                f"color: {TEXT}; font-size: 15px; font-weight: 700; "
                f"font-family: {FF_MONO};")
            col.addWidget(l)
            col.addWidget(v)
            row.addLayout(col)
        row.addStretch()
        layout.addLayout(row)
        if note and not adequate:
            note_lbl = QLabel(note)
            note_lbl.setWordWrap(True)
            note_lbl.setStyleSheet(f"color: {TEXT2}; font-size: 13px;")
            layout.addWidget(note_lbl)


class PulleyEditDialog(QDialog):
    """Head & Tail Pulley -- Wrap Angle card, head:boot diameter ratio check,
    a real toggle for the boot-match setting, and Pulley Shell Thickness (head
    + boot, independently overridable).

    Shell thickness lives HERE, not in the Shaft modal -- an earlier round read
    "move bearings to shaft" as also covering shell thickness, which wasn't
    asked for. Bearing selection is in the Shaft modal, where it belongs.
    """

    def __init__(self, inputs, results, parent=None):
        super().__init__(parent)
        self.inputs = dict(inputs)
        self.results = results or {}
        self.setWindowTitle("Head & Tail Pulley")
        self.setMinimumWidth(440)
        self.setStyleSheet(plain_bg(self, PANEL))
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
        self.d_mm.setRange(100, 1500)
        self.d_mm.setSingleStep(25)
        self.d_mm.setValue(float(self.inputs.get("D_mm", 500)))
        self.d_mm.valueChanged.connect(self._refresh_derived)
        row1.addLayout(field_row("Head Pulley Dia.", self.d_mm, "mm"))
        self.n_rpm = styled_spinbox(QDoubleSpinBox())
        self.n_rpm.setRange(10, 300)
        self.n_rpm.setSingleStep(5)
        self.n_rpm.setValue(float(self.inputs.get("n_rpm", 70)))
        row1.addLayout(field_row("Shaft Speed", self.n_rpm, "rpm"))
        body_layout.addLayout(row1)

        r = self.results
        # SCOPED: the bare wrap_box declaration boxed the Geometric, Effective
        # and Formula readouts individually.
        wrap_box, wl = card_frame(bg=PANEL2, border=BORDER, radius=R_SM,
                                  margins=(10, 8, 10, 8), spacing=6)
        wl.addWidget(section_head("Wrap Angle (derived)"))
        wrow = QHBoxLayout()
        # Verified both sides before changing anything: the backend math is
        # correct -- 500mm vs 525mm boot diameter on a 25m elevator genuinely
        # produces 179.9°, not 180.0° (confirmed via direct API calls; the
        # effect is much more visible on a shorter elevator or a larger
        # diameter difference, e.g. 169.6° at 2m + 500mm difference). The bug
        # was DISPLAY PRECISION: rounding to 0 decimals rendered a real 179.9°
        # as "180°" and looked unresponsive. 1 decimal now.
        for label, value, color in (
            ("Geometric", f"{fmt(r.get('wrap_geom_deg'), 1)}°", TEXT),
            ("Effective", f"{fmt(r.get('wrap_effective_deg'), 1)}°", PRIMARY),
        ):
            col = QVBoxLayout()
            l = QLabel(label)
            l.setStyleSheet(f"color: {TEXT3}; font-size: 12px;")
            v = QLabel(value)
            v.setStyleSheet(
                f"color: {color}; font-size: 17px; font-weight: 700; "
                f"font-family: {FF_MONO};")
            col.addWidget(l)
            col.addWidget(v)
            wrow.addLayout(col)
        formula_col = QVBoxLayout()
        fl = QLabel("Formula")
        fl.setStyleSheet(f"color: {TEXT3}; font-size: 12px;")
        fv = QLabel("180° + 2·arcsin((R_H−R_B)/C)")
        fv.setStyleSheet(f"color: {TEXT2}; font-size: 13px;")
        formula_col.addWidget(fl)
        formula_col.addWidget(fv)
        wrow.addLayout(formula_col)
        wrow.addStretch()
        wl.addLayout(wrow)
        # Honest about what this is: the architecture keeps all physics in the
        # backend (a frontend shadow of this formula is exactly the duplicate-
        # calculation failure mode), so this reflects the last APPLIED
        # calculation, not a live preview of an unapplied edit.
        stale_note = QLabel(
            "Reflects the last calculated result. Click Apply to see this update "
            "for a new diameter.")
        stale_note.setWordWrap(True)
        stale_note.setStyleSheet(f"color: {MUTED}; font-size: 12px; margin-top: 2px;")
        wl.addWidget(stale_note)

        self.snub_toggle = ToggleButton()
        self.snub_toggle.setChecked(bool(self.inputs.get("snub_pulley", False)))
        snub_row = field_row(
            "Snub pulley on return side (+30°)", self.snub_toggle,
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
        self.boot_d_mm.setRange(100, 1000)
        self.boot_d_mm.setSingleStep(25)
        self.boot_d_mm.setValue(float(self.inputs.get("boot_pulley_D_mm", 300)))
        self.boot_d_mm.valueChanged.connect(self._refresh_derived)
        self.boot_field_box = QVBoxLayout()
        body_layout.addLayout(self.boot_field_box)

        self.locked_label = QLabel()
        self.locked_label.setStyleSheet(
            f"color: {SUCCESS}; font-size: 14px; padding: 4px 0 8px;")
        body_layout.addWidget(self.locked_label)
        self._on_same_as_head(self.same_as_head.isChecked())

        self.head_shell_override = self._build_shell_section(
            body_layout, "Head Pulley Shell Thickness", r.get("pulley_shell") or {},
            self.inputs.get("pulley_shell_t_override_mm", 0),
        )
        self.boot_shell_override = self._build_shell_section(
            body_layout, "Tail (Boot) Pulley Shell Thickness", r.get("boot_shell") or {},
            self.inputs.get("boot_shell_t_override_mm", 0),
        )

        body_layout.addStretch()
        scroll = scroll_area()
        scroll.setWidget(body)
        layout.addWidget(scroll)
        layout.addWidget(modal_footer(self))

    def _build_shell_section(self, bl, title, shell, current_override):
        """One Head- or Tail-pulley shell thickness block: stat box + its own
        independent override field."""
        bl.addWidget(section_head(title))
        if shell:
            bl.addWidget(stat_box([
                ("CEMA min", f"{fmt(shell.get('t_cema_mm'), 0)} mm"),
                ("Pressure min", f"{fmt(shell.get('t_pressure_mm'), 2)} mm"),
                ("Governing", f"{fmt(shell.get('t_governing_mm'), 0)} mm"),
            ]))
        override = styled_spinbox(QDoubleSpinBox())
        override.setRange(0, 50)
        override.setSingleStep(1)
        override.setValue(float(current_override))
        status = None
        if shell.get("override_applied"):
            status = "ok" if shell.get("override_pass") else "fail"
            note = (f"{fmt(shell.get('t_use_mm'),0)}mm meets calculated minimum "
                    f"{fmt(shell.get('t_calc_mm'),0)}mm"
                    if shell.get("override_pass") else
                    f"{fmt(shell.get('t_use_mm'),0)}mm is BELOW calculated minimum "
                    f"{fmt(shell.get('t_calc_mm'),0)}mm")
        else:
            note = ("0 = auto from CEMA Pulley Standard minimum + belt-pressure check. "
                    "Specify to verify a standard plate gauge.")
        bl.addLayout(field_row("Shell Thickness Override", override, "mm",
                               note=note, status=status))
        return override

    def _rebuild_wrap_card(self):
        clear_layout(self.wrap_card_box)
        wr = self.results.get("wrap_recommendation")
        if not wr:
            return
        required_deg = wr.get("required_deg")
        if required_deg is None:
            # required_deg is NOT a missing-key case that `.get("required_deg", 0)`
            # was meant to guard -- it's a key that's PRESENT with value None, by
            # design, for chain drives (confirmed in calculations.py: chain mode
            # returns required_deg=None, config="N/A (chain drive)"). Wrap-angle
            # adequacy is a belt-friction concept (Euler/Eytelwein slip); it
            # doesn't apply when a chain positively engages a sprocket. Rather
            # than force a fake ADEQUATE/INADEQUATE verdict onto a value that was
            # never computed, show the honest reason the card doesn't apply.
            note, nl = card_frame(bg=PANEL2, border=BORDER, radius=R_SM,
                                  margins=(10, 8, 10, 8), spacing=4)
            lbl = QLabel(
                "Wrap angle adequacy doesn't apply to chain drives — chain positively "
                "engages the sprocket rather than relying on belt-friction wrap."
            )
            lbl.setWordWrap(True)
            lbl.setStyleSheet(f"color: {TEXT2}; font-size: 13px;")
            nl.addWidget(lbl)
            self.wrap_card_box.addWidget(note)
            return
        effective = self.results.get("wrap_effective_deg")
        if effective is None:
            effective = self.inputs.get("wrap_deg", 180)
        adequate = effective >= required_deg
        card = StatusCard(
            adequate, "WRAP ANGLE ADEQUATE", "WRAP ANGLE — SLIP RISK",
            [("Required", f"{fmt(required_deg, 1)}°"),
             ("Current", f"{fmt(effective, 1)}°"),
             ("Config", wr.get("config", "—"))],
            note=wr.get("recommendation"),
        )
        self.wrap_card_box.addWidget(card)

    def _refresh_derived(self):
        if not self.same_as_head.isChecked():
            self._set_boot_field()

    def _detach_boot_spinbox(self):
        """self.boot_d_mm is created once and REUSED across every rebuild of
        boot_field_box -- its value has to survive toggling "same as head" on
        and off. clear_layout() deletes every widget it finds with no
        exceptions, and boot_d_mm was getting swept up the moment it was first
        added: toggling ON destroyed the spinbox, then toggling OFF tried to
        reuse the now-dead widget -- which is exactly why the field never came
        back. Detaching it with setParent(None) (and NO deleteLater) before any
        clear keeps it alive and reusable indefinitely."""
        self.boot_d_mm.setParent(None)

    def _set_boot_field(self):
        self._detach_boot_spinbox()
        clear_layout(self.boot_field_box)
        ratio = self.d_mm.value() / max(self.boot_d_mm.value(), 1)
        ok = ratio <= 2.0
        note = f"Head:Boot ratio = {ratio:.2f} (CEMA §3.2 limit ≤ 2.00)"
        box = field_row("Boot Pulley Diameter", self.boot_d_mm, "mm",
                        note=note, status=None if ok else "warn")
        self.boot_field_box.addLayout(box)

    def _on_same_as_head(self, checked):
        self._detach_boot_spinbox()
        self.boot_d_mm.setEnabled(not checked)
        if checked:
            clear_layout(self.boot_field_box)
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
    """Belt / Chain Selection -- combines BeltEdit and ChainEdit from the JSX
    into one modal that switches content based on conveyor_type, the same way
    EquipmentTree.jsx switches its own Belt/Chain section."""

    def __init__(self, inputs, results, parent=None):
        super().__init__(parent)
        self.inputs = dict(inputs)
        self.results = results or {}
        self.is_chain = bool(self.results.get("is_chain"))
        title = "Chain Selection" if self.is_chain else "Belt Selection"
        self.setWindowTitle(title)
        self.setMinimumWidth(460)
        self.setStyleSheet(plain_bg(self, PANEL))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(modal_header(title, "CEMA 375 §4"))

        scroll = scroll_area()
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
        margin_bad = (tp.get("rating_margin") is not None and tp["rating_margin"] < 1.0)

        bl.addWidget(section_head("Belt Configuration"))
        bl.addWidget(stat_box([
            ("Auto Width", f"{fmt(r.get('belt_w'), 0)} mm"),
            ("Plies", f"{r.get('belt_ply', '—')}"
                      + (" (override)" if r.get("belt_ply_is_override") else "")),
            ("Eff. Tension (sizing basis)", f"{fmt((r.get('F_eff') or 0) / 1000, 1)} kN"),
        ]))

        if tp.get("T_max_N") is not None:
            note = None
            if margin_bad:
                note = ("Ply count above is sized for effective tension only — peak tension "
                        "(including empty-leg self-weight) exceeds belt rating. Increase belt "
                        "width, or set Belt Ply Override below to a higher count.")
            bl.addWidget(stat_box(
                [("Peak Tension (actual max, full loop)",
                  f"{fmt(tp.get('T_max_N', 0) / 1000, 1)} kN"),
                 ("Belt Rated", f"{fmt((tp.get('belt_rated_N') or 0) / 1000, 1)} kN"),
                 ("Margin", fmt(tp.get("rating_margin"), 2))],
                status="fail" if margin_bad else None,
                note=note,
            ))

        self.belt_ply_override = styled_spinbox(QSpinBox())
        self.belt_ply_override.setRange(0, 10)
        self.belt_ply_override.setSingleStep(1)
        self.belt_ply_override.setValue(int(self.inputs.get("belt_ply_override", 0)))
        ply_note = (f"0 = auto (currently {r.get('belt_ply')}"
                    f"{', from your override' if r.get('belt_ply_is_override') else ''}). "
                    f"Set > 0 to pick a specific ply count."
                    if r.get("belt_ply") is not None else
                    "0 = auto-calculate from peak tension. Set > 0 to pick a specific ply count.")
        bl.addLayout(field_row("Belt Ply Override", self.belt_ply_override, note=ply_note))

        self.belt_width_override = styled_spinbox(QDoubleSpinBox())
        self.belt_width_override.setRange(0, 1500)
        self.belt_width_override.setSingleStep(25)
        self.belt_width_override.setValue(float(self.inputs.get("belt_width_override_mm", 0)))
        bl.addLayout(field_row(
            "Belt Width Override", self.belt_width_override, "mm",
            note="0 = auto-select from bucket width. Set > 0 to specify exact width."))

        bl.addWidget(section_head("Belt Type"))
        self.belt_type_combo = styled_combo(QComboBox())
        belt_types = [("EP", "EP — Fabric ply (standard)"),
                      ("ST", "ST — Steel cord (high tension)")]
        current_belt_type = self.inputs.get("belt_type", "EP")
        for i, (val, text) in enumerate(belt_types):
            self.belt_type_combo.addItem(text, val)
            if val == current_belt_type:
                self.belt_type_combo.setCurrentIndex(i)
        bl.addWidget(self.belt_type_combo)
        type_note = QLabel("ST belts use herringbone lagging — not diamond groove")
        type_note.setStyleSheet(f"color: {TEXT2}; font-size: 13px;")
        bl.addWidget(type_note)

        bl.addWidget(section_head("Belt Cover Grade"))
        self.belt_grade_combo = styled_combo(QComboBox())
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
        grade_note = QLabel(
            "Grade M for abrasive materials (abr ≥ 4). Grade N for grain/light minerals.")
        grade_note.setWordWrap(True)
        grade_note.setStyleSheet(f"color: {TEXT2}; font-size: 13px;")
        bl.addWidget(grade_note)

    # ── Chain mode ────────────────────────────────────────────────────
    def _build_chain_content(self, bl):
        r = self.results
        cs = r.get("chain_selected")
        sp = r.get("sprocket")
        bsp = r.get("boot_sprocket")

        bl.addWidget(section_head("Chain Series"))
        self.chain_series_combo = styled_combo(QComboBox())
        self.chain_series_combo.addItem("Auto — select by pull force", "")
        current_chain = self.inputs.get("chain_series", "")
        for i, (val, text) in enumerate(CHAIN_OPTIONS, start=1):
            self.chain_series_combo.addItem(text, val)
            if val == current_chain:
                self.chain_series_combo.setCurrentIndex(i)
        bl.addWidget(self.chain_series_combo)
        if cs:
            flag_note("ok",
                      f"Selected: {cs.get('name')} — pull "
                      f"{fmt((r.get('chain_pull_N') or 0) / 1000, 1)}kN  "
                      f"SF={fmt(r.get('chain_SF_actual'), 2)}",
                      parent_layout=bl)

        row = QHBoxLayout()
        strands_col = QVBoxLayout()
        strands_lbl = QLabel("No. of Strands")
        strands_lbl.setStyleSheet(f"color: {TEXT2}; font-size: 13px; font-weight: 600;")
        strands_col.addWidget(strands_lbl)
        self._strands_val = [int(self.inputs.get("chain_n_strands", 1))]
        strands_row = QHBoxLayout()
        strands_buttons = {}

        def restyle_strands():
            for n, btn in strands_buttons.items():
                btn.setStyleSheet(
                    sel_button_qss(btn, n == self._strands_val[0], padding="7px 4px"))

        for n, label in ((1, "1 — Single"), (2, "2 — SC Double")):
            btn = QPushButton(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

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
        self.chain_sf.setRange(3, 12)
        self.chain_sf.setSingleStep(0.5)
        self.chain_sf.setValue(float(self.inputs.get("chain_sf", 6.0)))
        row.addLayout(field_row("Chain SF", self.chain_sf,
                                note="CEMA default 6.0; 8.0 for shock/abrasive"))
        bl.addLayout(row)

        bl.addWidget(section_head("Sprocket"))
        self.sprocket_teeth = styled_spinbox(QSpinBox())
        self.sprocket_teeth.setRange(0, 32)
        self.sprocket_teeth.setSingleStep(1)
        self.sprocket_teeth.setValue(int(self.inputs.get("chain_sprocket_teeth", 0)))
        bl.addLayout(field_row(
            "Sprocket Teeth Override", self.sprocket_teeth,
            note="0 = auto from D_mm. Recommend 10–20 teeth for smooth chain engagement."))
        if sp:
            bl.addWidget(stat_box(
                [("PD", f"{fmt(sp.get('PD_mm'), 0)} mm"),
                 ("Teeth", str(sp.get("n_teeth", "—"))),
                 ("Smooth", "Yes" if sp.get("smooth") else "No")],
                status=None if sp.get("smooth") else "warn",
                note=sp.get("note") if not sp.get("smooth") else None,
            ))

        bl.addWidget(section_head("Boot Sprocket"))
        self.boot_sprocket_teeth = styled_spinbox(QSpinBox())
        self.boot_sprocket_teeth.setRange(0, 32)
        self.boot_sprocket_teeth.setSingleStep(1)
        self.boot_sprocket_teeth.setValue(
            int(self.inputs.get("chain_boot_sprocket_teeth", 0)))
        bl.addLayout(field_row(
            "Boot Sprocket Teeth Override", self.boot_sprocket_teeth,
            note="0 = auto from boot pulley diameter. Same physical relationship as the head "
                 "sprocket — the boot/tail wheel engages the chain too, not a smooth-faced pulley."
        ))
        if bsp:
            bl.addWidget(stat_box(
                [("PD", f"{fmt(bsp.get('PD_mm'), 0)} mm"),
                 ("Teeth", str(bsp.get("n_teeth", "—"))),
                 ("Smooth", "Yes" if bsp.get("smooth") else "No")],
                status=None if bsp.get("smooth") else "warn",
                note=bsp.get("note") if not bsp.get("smooth") else None,
            ))

        if r.get("chain_v_ok") is not None:
            bl.addWidget(section_head("Chain Speed Check"))
            ok = r["chain_v_ok"]
            v_max = (cs or {}).get("v_max_ms", "—")
            text = (f"Speed {fmt(r.get('v'), 2)} m/s ≤ chain rated {v_max} m/s" if ok else
                    f"Speed {fmt(r.get('v'), 2)} m/s EXCEEDS chain rated {v_max} m/s")
            bl.addWidget(flag_note("ok" if ok else "fail", text))

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
    """Bucket Selection -- fetches the real 40-row bucket catalog live from
    /components/buckets (confirmed: exactly the 6 styles AA/AC/C/MF/HF/SC the
    JSX hardcodes, same 40 total sizes), grouped by style. Only the descriptive
    text per style (BUCKET_STYLE_INFO) isn't available from the API and is kept
    as a small lookup -- the actual dimensions driving every calculation come
    from the live catalog, not a duplicated copy.

    auto_bucket lives here, not in Design Requirements -- confirmed against the
    real JSX before assuming otherwise.
    """

    def __init__(self, inputs, results, parent=None):
        super().__init__(parent)
        self.inputs = dict(inputs)
        self.results = results or {}
        self.setWindowTitle("Bucket Selection")
        self.setMinimumWidth(460)
        self.setStyleSheet(plain_bg(self, PANEL))
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

        scroll = scroll_area()
        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(16, 16, 16, 16)
        bl.setSpacing(10)
        r = self.results

        bl.addWidget(section_head("Auto-Select"))
        self.auto_toggle = ToggleButton()
        self.auto_toggle.setChecked(bool(self.inputs.get("auto_bucket", True)))
        self.auto_toggle.toggled.connect(self._on_auto_toggled)
        bl.addLayout(field_row(
            "Auto-select smallest adequate series", self.auto_toggle,
            note="Auto picks the smallest size that meets Q_req at current speed and fill"))

        rec = r.get("bucket_recommendation")
        if rec:
            current_style = (self.inputs.get("bucket_id", "") or "").split("_")[0]
            is_current = current_style == rec.get("recommended_style")
            card, cl = card_frame(bg=PANEL2, border=BORDER, radius=R_SM,
                                  margins=(10, 8, 10, 8), spacing=6)
            head_row = QHBoxLayout()
            head_row.setSpacing(8)
            head_row.addWidget(status_badge("ok" if is_current else "info", size=15))
            head = QLabel("CURRENT STYLE MATCHES RECOMMENDATION" if is_current
                          else "RECOMMENDATION FOR THIS MATERIAL")
            head.setStyleSheet(f"color: {TEXT2}; font-size: 13px; font-weight: 700;")
            head_row.addWidget(head)
            head_row.addStretch()
            cl.addLayout(head_row)
            alt = rec.get("alternative_style")
            style_lbl = QLabel(
                f"{rec.get('recommended_style')} style"
                + (f"   (alt: {alt})" if alt != rec.get("recommended_style") else ""))
            style_lbl.setStyleSheet(f"color: {TEXT}; font-size: 14px; font-weight: 700;")
            cl.addWidget(style_lbl)
            reasoning = QLabel(rec.get("reasoning", ""))
            reasoning.setWordWrap(True)
            reasoning.setStyleSheet(f"color: {TEXT2}; font-size: 13px;")
            cl.addWidget(reasoning)
            for note in rec.get("notes") or []:
                flag_note("warn", note, parent_layout=cl)
            bl.addWidget(card)

        bl.addWidget(section_head("Bucket Style"))
        self.style_combo = styled_combo(QComboBox())
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
        self.style_desc.setStyleSheet(f"color: {TEXT2}; font-size: 13px;")
        bl.addWidget(self.style_desc)

        bl.addWidget(section_head("Size"))
        self.belt_width_note = QLabel()
        self.belt_width_note.setStyleSheet(
            f"color: {PRIMARY}; font-size: 12px; font-weight: 700;")
        bl.addWidget(self.belt_width_note)
        self.size_combo = styled_combo(QComboBox())
        # Connected exactly once, here -- _populate_sizes() used to
        # disconnect/reconnect this on every call, which raised a RuntimeWarning
        # the first time (nothing was connected yet to disconnect). A single
        # permanent connection plus blockSignals() during repopulation (below)
        # is the correct pattern.
        self.size_combo.currentIndexChanged.connect(self._rebuild_size_summary)
        bl.addWidget(self.size_combo)
        self.size_warn = QLabel()
        self.size_warn.setWordWrap(True)
        self.size_warn.setStyleSheet(f"color: {WARNING}; font-size: 13px;")
        bl.addWidget(self.size_warn)

        self.size_summary_box = QVBoxLayout()
        bl.addLayout(self.size_summary_box)

        self._populate_sizes(current_bucket_id)
        self._update_auto_state(self.auto_toggle.isChecked())

        bl.addWidget(section_head("Spacing"))
        self.bucket_gap = styled_spinbox(QDoubleSpinBox())
        self.bucket_gap.setRange(0, 200)
        self.bucket_gap.setSingleStep(5)
        self.bucket_gap.setValue(float(self.inputs.get("bucket_gap", 25)))
        bl.addLayout(field_row(
            "Bucket Spacing Gap", self.bucket_gap, "mm",
            note="Gap added beyond bucket projection for spacing. CEMA default 25mm. "
                 "Continuous elevators typically 0mm."))

        bl.addWidget(section_head("Double-Row Configuration (HG)"))
        self.double_row_toggle = ToggleButton()
        self.double_row_toggle.setChecked(int(self.inputs.get("n_rows", 1)) == 2)
        self.double_row_toggle.toggled.connect(self._on_double_row_changed)
        bl.addLayout(field_row(
            "Double-Row (HG)", self.double_row_toggle, "",
            note="Two half-width buckets per pitch position, staggered by half a pitch. "
                 "Belt drive only — chain not valid. Belt width is automatically "
                 "validated (min 2× bucket width + 50mm). Capacity formula is "
                 "unchanged; advantage is smoother flow at higher speed [CEMA 375 §6 DR]."))

        self._dr_status_box = QVBoxLayout()
        bl.addLayout(self._dr_status_box)
        self._on_double_row_changed(self.double_row_toggle.isChecked())

        bl.addWidget(section_head("Plate Thickness"))
        bt = r.get("bucket_thickness")
        if bt:
            bl.addWidget(stat_box([
                ("Catalogue gauge", f"{fmt(bt.get('t_implied_mm'), 1)} mm"),
                ("Specified", f"{fmt(bt.get('t_override_mm'), 1)} mm"),
                ("Mass", f"{fmt(bt.get('mass_scaled_kg'), 1)} kg"),
            ]))
        self.thickness_override = styled_spinbox(QDoubleSpinBox())
        self.thickness_override.setRange(0, 20)
        self.thickness_override.setSingleStep(0.5)
        self.thickness_override.setValue(
            float(self.inputs.get("bucket_thickness_override_mm", 0)))
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
        style = force_style or (
            bucket_id.split("_")[0] if bucket_id and "_" in bucket_id
            else self.style_combo.currentData())
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
            self.belt_width_note.setText(
                f"Belt {fmt(belt_w,0)}mm → max W={fmt(max_w,0)}mm")
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
                f"({fmt(belt_w,0)}mm − 50mm clearance). Increase belt width override to "
                f"unlock them."
            )
        else:
            self.size_warn.setText("")
        self._current_rows = {b.get("bucket_id"): b for b in rows_to_show}
        self._rebuild_size_summary()

    def _rebuild_size_summary(self, _index=None):
        clear_layout(self.size_summary_box)
        if self.auto_toggle.isChecked():
            flag_note("ok", "Auto-select active — disable the toggle above to pick a "
                            "specific size", parent_layout=self.size_summary_box)
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

    def _on_double_row_changed(self, checked: bool):
        """Inline status note when double-row is toggled. Hardcoded hex colors
        (#94a3b8 / #f59e0b / #3b82f6) replaced with the shared flag_note()
        visual language + theme tokens."""
        clear_layout(self._dr_status_box)
        if not checked:
            return
        conv = (self.inputs.get("conveyor_type", "belt") or "belt").lower()
        if conv == "chain":
            flag_note("warn",
                      "Chain drive selected — double-row requires belt drive. "
                      "Switch to Belt Drive in the Belt/Chain section.",
                      parent_layout=self._dr_status_box)
        else:
            flag_note("info",
                      "n_rows=2 active. Belt width will be validated "
                      "(≥ 2×bucket.W + 50mm). Model family → HG.",
                      parent_layout=self._dr_status_box)

    def updated_inputs(self):
        self.inputs["auto_bucket"] = self.auto_toggle.isChecked()
        if not self.auto_toggle.isChecked():
            self.inputs["bucket_id"] = self.size_combo.currentData()
        self.inputs["bucket_gap"] = self.bucket_gap.value()
        self.inputs["n_rows"] = 2 if self.double_row_toggle.isChecked() else 1
        self.inputs["bucket_thickness_override_mm"] = self.thickness_override.value()
        return self.inputs


class ShaftEditDialog(QDialog):
    """Shaft Design -- 4-quadrant grid: Head Shaft (top-left), Boot Shaft
    (bottom-left), Head Shaft Bearing (top-right), Boot Shaft Bearing
    (bottom-right). The 2-column grid uses width instead of just height, and is
    wrapped in a QScrollArea regardless of how tall any quadrant gets.

    Pulley Shell Thickness is NOT here -- it's in Head & Tail Pulley.

    Boot Shaft / Boot Shaft Bearing: checked first, not assumed. The backend
    already computes a complete, independent boot shaft sizing and bearing load
    (different span, no drive torque, different reaction load than the head
    shaft) under results.boot_pulley.{shaft, R_boot_N, L10_boot_h} -- confirmed
    against a real API response before any UI was written for it.

    Bearing selection (both quadrants) is labeled honestly as informational
    only: bearing_name is a real model field but isn't actually read anywhere
    in calculations.py, and there's no boot-specific equivalent at all.
    """

    def __init__(self, inputs, results, parent=None):
        super().__init__(parent)
        self.inputs = dict(inputs)
        self.results = results or {}
        self.setWindowTitle("Shaft Design")
        self.setMinimumWidth(820)
        self.resize(900, 680)
        self.setStyleSheet(plain_bg(self, PANEL))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(modal_header("Shaft Design", "CEMA 375 §4"))

        scroll = scroll_area()
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

        # The seal/bearing-grease temperature checks ARE genuinely tagged
        # subsystem="shaft" in the backend (correct categorization -- they're
        # shaft-bearing concerns), but this quadrant used to treat ANY
        # shaft-subsystem fail/warn as reason to put a red border around the
        # Stress/Deflection/Governing numbers -- conflating "something in the
        # shaft subsystem needs attention" with "the diameter sizing itself is
        # wrong". Same lesson already applied in EquipmentTree's nodeStatus():
        # filter by subsystem tag FIRST, then by keyword scoped within it,
        # rather than whole-array matching. Only checks whose message is
        # actually about diameter governing / critical speed colorize the
        # dimensions box. Everything else shaft-subsystem (seals, bearing
        # grease, keyway, material) is still shown -- as its own separate note
        # below, not wrapped around numbers it has nothing to do with.
        shaft_checks = [c for c in (r.get("checks") or []) if c.get("subsystem") == "shaft"]
        SIZING_KEYWORDS = ("governed by", "critical speed")
        sizing_checks = [c for c in shaft_checks
                         if any(k in (c.get("msg") or "").lower() for k in SIZING_KEYWORDS)]
        other_checks = [c for c in shaft_checks if c not in sizing_checks]

        sizing_fail = any(c.get("type") == "fail" for c in sizing_checks)
        sizing_warn = any(c.get("type") == "warn" for c in sizing_checks)
        sizing_status = "fail" if sizing_fail else "warn" if sizing_warn else None
        note = None
        if sizing_status:
            note = next((c.get("msg") for c in sizing_checks
                         if c.get("type") == sizing_status), None)
        if r.get("d_mm") is not None:
            bl.addWidget(stat_box(
                [("Stress", f"{fmt(r.get('d_stress_mm'), 1)} mm"),
                 ("Deflection", f"{fmt(r.get('d_deflect_mm'), 1)} mm"),
                 ("Governing", f"{fmt(r.get('d_mm'), 1)} mm"),
                 ("Governed by", r.get("governed_by", "—"))],
                status=sizing_status, note=note,
            ))

        other_flags = [c for c in other_checks if c.get("type") in ("fail", "warn")]
        if other_flags:
            flags_box = QVBoxLayout()
            flags_box.setSpacing(6)
            for c in other_flags:
                flag_note(c.get("type"), c.get("msg", ""), parent_layout=flags_box)
            bl.addLayout(flags_box)

        bl.addWidget(section_head("Shaft Material"))
        self.material_combo = styled_combo(QComboBox())
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
            f"Selected: {r.get('shaft_material_name')} · "
            f"τ_allow={fmt(r.get('shaft_tau_allow_MPa'), 0)}MPa. "
            f"Also governs the boot shaft below — one grade for both."
            if r.get("shaft_material_name") else
            "Higher grades permit a smaller shaft diameter for the same load, at higher "
            "material cost."
        )
        mat_note.setWordWrap(True)
        mat_note.setStyleSheet(f"color: {TEXT2}; font-size: 13px;")
        bl.addWidget(mat_note)

        bl.addWidget(section_head("Shaft Section"))
        self._section_val = [self.inputs.get("shaft_section", "solid")]
        bl.addLayout(toggle_pair(["solid", "hollow"], self._section_val,
                                 self._on_section_change))
        self.bore_box = QVBoxLayout()
        bl.addLayout(self.bore_box)
        self.bore_ratio = styled_spinbox(QDoubleSpinBox())
        self.bore_ratio.setRange(0.1, 0.85)
        self.bore_ratio.setSingleStep(0.05)
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
        self.shaft_override.setRange(0, 500)
        self.shaft_override.setSingleStep(5)
        self.shaft_override.setValue(float(self.inputs.get("shaft_d_override_mm", 0)))
        bl.addLayout(field_row(
            "Head Shaft Dia. Override", self.shaft_override, "mm",
            note="0 = auto from stress/deflection check. Specify to force a standard bar size."))
        bl.addStretch()
        return frame

    # ── Bottom-left ───────────────────────────────────────────────────
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
        note.setStyleSheet(f"color: {TEXT2}; font-size: 13px;")
        bl.addWidget(note)
        span_note = QLabel(f"Span: {fmt(boot_shaft.get('span_mm'), 0)} mm.")
        span_note.setStyleSheet(f"color: {MUTED}; font-size: 13px;")
        bl.addWidget(span_note)

        # Backend supports boot_shaft_section / boot_shaft_bore_ratio /
        # boot_shaft_d_override_mm (calculations.py v1.10.0 -- previously
        # bore_ratio was hardcoded to 0.0 with no override path at all, even
        # though the same shaft_diameter_governing_hollow() the head shaft uses
        # already accepted these parameters). Material grade is NOT duplicated
        # here -- confirmed in calculations.py: the boot shaft is sized using the
        # same _tau_allow_Pa as the head shaft; one grade governs both by design
        # (a bucket elevator doesn't mix shaft material grades within one
        # machine). No hub-connection control either: the boot pulley is
        # free-running with zero drive torque (T_Nm=0 in the actual sizing call),
        # so there genuinely is no keyed-vs-welded decision to make -- explained
        # here rather than offering a control that wouldn't do anything.
        mat_share_note = QLabel(
            "Uses the same material grade as Head Shaft (above) — one grade governs both.")
        mat_share_note.setWordWrap(True)
        mat_share_note.setStyleSheet(
            f"color: {MUTED}; font-size: 13px; font-style: italic;")
        bl.addWidget(mat_share_note)

        bl.addWidget(section_head("Boot Shaft Section"))
        self._boot_section_val = [self.inputs.get("boot_shaft_section", "solid")]
        bl.addLayout(toggle_pair(["solid", "hollow"], self._boot_section_val,
                                 self._on_boot_section_change))
        self.boot_bore_box = QVBoxLayout()
        bl.addLayout(self.boot_bore_box)
        self.boot_bore_ratio = styled_spinbox(QDoubleSpinBox())
        self.boot_bore_ratio.setRange(0.1, 0.85)
        self.boot_bore_ratio.setSingleStep(0.05)
        self.boot_bore_ratio.setValue(float(self.inputs.get("boot_shaft_bore_ratio", 0.5)))
        self._rebuild_boot_bore_field(boot_shaft)

        bl.addWidget(section_head("No Hub Connection — Free-Running"))
        no_hub_note = QLabel(
            "Boot pulley carries zero drive torque, so there's no keyed-vs-welded "
            "decision here — that control only applies to the driven (head) shaft.")
        no_hub_note.setWordWrap(True)
        no_hub_note.setStyleSheet(f"color: {MUTED}; font-size: 13px;")
        bl.addWidget(no_hub_note)

        bl.addWidget(section_head("Boot Shaft Diameter Override"))
        self.boot_shaft_override = styled_spinbox(QDoubleSpinBox())
        self.boot_shaft_override.setRange(0, 500)
        self.boot_shaft_override.setSingleStep(5)
        self.boot_shaft_override.setValue(
            float(self.inputs.get("boot_shaft_d_override_mm", 0)))
        bl.addLayout(field_row(
            "Boot Shaft Dia. Override", self.boot_shaft_override, "mm",
            note="0 = auto from bending/deflection check. Specify to force a standard bar size."))
        bl.addStretch()
        return frame

    def _on_boot_section_change(self, value):
        self._boot_section_val[0] = value
        self._rebuild_boot_bore_field(self._last_boot_shaft_results)

    def _rebuild_boot_bore_field(self, boot_shaft):
        self._last_boot_shaft_results = boot_shaft
        clear_layout(self.boot_bore_box)
        if self._boot_section_val[0] == "hollow":
            bs = boot_shaft or {}
            note = (
                f"OD {fmt(bs.get('d_mm'),0)}mm · ID≈{fmt(bs.get('d_inner_mm'),0)}mm · "
                f"~{fmt(bs.get('mass_saving_pct'),0)}% mass reduction vs equivalent solid shaft."
                if bs.get("bore_ratio") else
                "Typical hollow shaft practice: 0.4-0.7. Same fabrication/weight trade-off as "
                "the head shaft."
            )
            self.boot_bore_box.addLayout(
                field_row("Boot Bore Ratio (ID/OD)", self.boot_bore_ratio, note=note))

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
            lambda row: (f"{row.get('name')}  bore={row.get('bore')}mm  "
                         f"C={row.get('C')}kN  {row.get('type','')}  {row.get('seal','')}"),
            self.inputs.get("bearing_name", ""), None, "Bearing Selection",
            note=(f"Showing bore {fmt(bore_min,0)}–{fmt(bore_max,0)} mm. Informational only "
                  f"right now — the solver doesn't yet read a selected bearing back into "
                  f"the calculation." if bore_min else None),
        )
        bl.addWidget(self.bearing_picker)
        bl.addStretch()
        return frame

    # ── Bottom-right ──────────────────────────────────────────────────
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
        bore_min, bore_max = ((boot_shaft_d, boot_shaft_d * 1.9)
                              if boot_shaft_d else (None, None))
        self.boot_bearing_picker = ComponentPickerWidget(
            "/components/bearings", {"bore_min": bore_min, "bore_max": bore_max},
            lambda row: (f"{row.get('name')}  bore={row.get('bore')}mm  "
                         f"C={row.get('C')}kN  {row.get('type','')}  {row.get('seal','')}"),
            self.inputs.get("boot_bearing_name", ""), None, "Bearing Selection",
            note=(f"Showing bore {fmt(bore_min,0)}–{fmt(bore_max,0)} mm. Informational only — "
                  f"there's no boot-specific override field in the backend yet, same caveat "
                  f"as the head bearing above." if bore_min else None),
        )
        bl.addWidget(self.boot_bearing_picker)
        bl.addStretch()
        return frame

    def _on_section_change(self, value):
        self._section_val[0] = value
        self._rebuild_bore_field()

    def _rebuild_bore_field(self):
        clear_layout(self.bore_box)
        if self._section_val[0] == "hollow":
            r = self.results
            note = (
                f"OD {fmt(r.get('d_mm'),0)}mm · ID≈{fmt(r.get('shaft_d_inner_mm'),0)}mm · "
                f"~{fmt(r.get('shaft_mass_saving_pct'),0)}% mass reduction vs equivalent solid "
                f"shaft. Typical practice 0.4-0.7; CEMA does not mandate a ratio."
                if r.get("shaft_bore_ratio") else
                "Typical hollow shaft practice: 0.4-0.7. Higher ratio = larger required OD but "
                "greater net mass savings."
            )
            self.bore_box.addLayout(
                field_row("Bore Ratio (ID/OD)", self.bore_ratio, note=note))

    def _on_hub_change(self, value):
        self._hub_val[0] = value
        self._rebuild_hub_info()

    def _rebuild_hub_info(self):
        clear_layout(self.hub_info_box)
        r = self.results
        if self._hub_val[0] == "welded" and r.get("weld_check"):
            wc = r["weld_check"]
            self.hub_info_box.addWidget(stat_box(
                [("Throat", f"{fmt(wc.get('t_throat_mm'), 1)} mm"),
                 ("τ actual", f"{fmt(wc.get('tau_torsion_MPa'), 1)} MPa"),
                 ("τ allow", f"{fmt(wc.get('weld_allow_MPa'), 1)} MPa"),
                 ("Governed by", (wc.get("governed_by") or "—").replace("_", " "))],
                note="E70xx fillet weld, allowable independent of shaft material grade "
                     "(weld metal governs).",
            ))
        elif self._hub_val[0] == "keyed":
            lbl = QLabel("Standard ASME B17.1 keyed connection. Field-serviceable — pulley "
                         "can be removed without re-welding.")
            lbl.setWordWrap(True)
            lbl.setStyleSheet(f"color: {TEXT2}; font-size: 13px;")
            self.hub_info_box.addWidget(lbl)

    def updated_inputs(self):
        self.inputs["shaft_material"] = self.material_combo.currentData()
        self.inputs["shaft_section"] = self._section_val[0]
        self.inputs["shaft_bore_ratio"] = self.bore_ratio.value()
        self.inputs["shaft_hub_connection"] = self._hub_val[0]
        self.inputs["shaft_d_override_mm"] = self.shaft_override.value()
        self.inputs["bearing_name"] = self.bearing_picker.value()
        self.inputs["boot_bearing_name"] = self.boot_bearing_picker.value()
        self.inputs["boot_shaft_section"] = self._boot_section_val[0]
        self.inputs["boot_shaft_bore_ratio"] = self.boot_bore_ratio.value()
        self.inputs["boot_shaft_d_override_mm"] = self.boot_shaft_override.value()
        return self.inputs


class InputSidebarPanel(QWidget):
    """Port of InputSidebar.jsx -- accordion groups of SectionRow summaries,
    each opening a modal. set_data(inputs, results) like every other component;
    emits inputsChanged(dict) when the user applies an edit.

    GROUPING (this round) -- THREE groups, not the JSX's four
    ────────────────────────────────────────────────────────────
    Built from Jay's stated decision logic, which differs from the JSX in one
    deliberate way:

      DESIGN REQUIREMENTS   everything the CUSTOMER specifies, entered together:
                            material + properties, tonnage + height, AND service
                            conditions (dirty/clean/windy). The JSX makes Service
                            Conditions its own top-level group; here it is a
                            customer input like any other, so it groups with them.

      MECHANICAL DESIGN     everything DERIVED-then-chosen: belt/chain, bucket,
                            pulley, shaft, take-up, discharge, feed, casing.

      POWER TRANSMISSION    derived from the design and sized by the user to
                            match it -- its own group, as in the JSX.

    ROW ORDER inside Mechanical is the PySide order (Belt/Chain and Bucket ahead
    of Pulley and Shaft), NOT the JSX's. That was a prior deliberate decision --
    decide material/tonnage/height, then drive type and bucket, THEN the
    pulley/shaft sizing that depends on them. Jay's logic tree only constrains
    Pulley to sit immediately before Shaft (head pulley -> tail pulley -> head
    shaft -> head bearing -> tail shaft -> tail bearing), which it does.

    BADGE SCOPING -- one deliberate divergence from the JSX
    ──────────────────────────────────────────────────────
    The JSX badges Head & Tail Pulley with ["shaft","pulley","boot_pulley"],
    because in the JSX PulleyEdit CONTAINS the head-shaft bearing picker and the
    shell thickness -- so a shaft problem is actionable from that modal.

    This port moved bearings out: PulleyEditDialog owns wrap angle, boot pulley
    and shell thickness; ShaftEditDialog owns head shaft, head bearing, boot
    shaft and boot bearing (steps 3-6 of Jay's logic tree). Keeping "shaft" on
    the pulley badge would therefore mark Head & Tail Pulley FAIL for something
    the user CANNOT fix from that dialog -- the badge would point at the wrong
    door. Each badge is scoped to what its dialog actually owns.

    STILL NOT PORTED (named, not silently absent):
      * Equipment-tree -> dialog routing (openSectionRef in the JSX).
      * "Save overrides as custom material" bridge in ProcessEditDialog.
    """

    inputsChanged = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.inputs, self.results = {}, {}
        self.setStyleSheet(plain_bg(self, PANEL))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = scroll_area()
        self.list_widget = QWidget()
        self.list_widget.setStyleSheet(plain_bg(self.list_widget, PANEL))
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(0)
        self.list_layout.addStretch()
        scroll.setWidget(self.list_widget)
        outer.addWidget(scroll)

        # Remembers which groups the user collapsed, so a recalculation (which
        # rebuilds every row) doesn't spring them all back open mid-edit.
        self._open_state = {}

    def set_data(self, inputs, results):
        self.inputs, self.results = dict(inputs or {}), results or {}
        self._rebuild_list()

    # ── Badges ────────────────────────────────────────────────────────
    # BOOT-BEARING TAGGING (confirmed by grep, not assumed):
    #   calculations.py:3870  Bearing L10 < 20,000h        subsystem="shaft"
    #   calculations.py:4391  Boot bearing L10 / upgrade   subsystem="boot_pulley"
    #
    # So "boot_pulley" is a MIXED tag: it carries boot pulley GEOMETRY checks
    # (head:boot ratio, boot shell) AND boot BEARING checks. Those two belong on
    # different rows in this port -- geometry is step 2 (Pulley dialog), the boot
    # bearing is step 6 (Shaft dialog's bottom-right quadrant).
    #
    # Splitting them by keyword within the subsystem, rather than giving the whole
    # tag to one row. Subsystem first, keyword second -- the same order of
    # operations as everywhere else. Without this, a boot-bearing failure would
    # badge Head & Tail Pulley, whose dialog has no bearing control at all.
    BOOT_BEARING_KW = ("bearing", "l10")

    def _badges(self):
        r = self.results
        checks = r.get("checks") or []

        def boot_split(want_bearing):
            """boot_pulley checks, partitioned into bearing vs geometry."""
            out = []
            for c in checks:
                if (c.get("subsystem") or "") != "boot_pulley":
                    continue
                msg = (c.get("msg") or "").lower()
                is_brg = any(k in msg for k in self.BOOT_BEARING_KW)
                if is_brg == want_bearing:
                    out.append(c)
            return out

        def verdict(subset):
            if not checks:
                return None
            if any(c.get("type") == "fail" for c in subset):
                return "FAIL"
            if any(c.get("type") == "warn" for c in subset):
                return "WARN"
            return "PASS"

        shaft_checks = [c for c in checks
                        if (c.get("subsystem") or "") == "shaft"] + boot_split(True)
        pulley_checks = [c for c in checks
                         if (c.get("subsystem") or "") == "pulley"] + boot_split(False)

        b = {
            "process":   subsystem_badge(r, "process"),
            # Geometry only -- NOT shaft, NOT boot bearings. See the class docstring.
            "pulleys":   verdict(pulley_checks),
            "belt":      subsystem_badge(r, "belt"),
            "bucket":    subsystem_badge(r, "bucket"),
            "takeup":    subsystem_badge(r, "takeup"),
            # Owns ALL shaft checks (sizing, keyway, critical speed, seals, and the
            # head-bearing L10 that calculations.py tags subsystem="shaft"), PLUS
            # the boot-bearing checks tagged boot_pulley -- because the boot bearing
            # is chosen in this dialog, not the pulley one.
            "shaft":     verdict(shaft_checks),
            "discharge": subsystem_badge(r, "discharge"),
            "casing":    subsystem_badge(r, "casing"),
            "service":   subsystem_badge(r, "service"),
            "power":     subsystem_badge(r, "power"),
            "chain":     subsystem_badge(r, "belt",
                                         ["chain sf", "chain speed", "sprocket"]),
        }
        # Feed is NOT a subsystem_badge: feed_design carries its own warnings[]
        # list rather than emitting checks[] entries. Same special-case as the
        # JSX, and the same reason equipment_tree's MECHANICAL rollup had to fold
        # st_feed in explicitly -- a feed warning is invisible to any
        # checks[]-based rollup.
        fd = r.get("feed_design")
        if fd:
            b["feed"] = "WARN" if fd.get("warnings") else "PASS"
        else:
            b["feed"] = "PENDING" if checks else None
        return b

    def _add_row(self, group, label, summary, opener, badge=None):
        row = SectionRow(label, summary, badge=badge, depth=1)
        row.clicked = opener
        group.add_row(row)

    def _add_group(self, key, label, cema, badge, default_open):
        grp = AccordionGroup(label, cema=cema, badge=badge,
                             default_open=self._open_state.get(key, default_open))
        grp._header.mousePressEvent = lambda _e, k=key, g=grp: self._toggle_group(k, g)
        self.list_layout.addWidget(grp)
        return grp

    def _toggle_group(self, key, grp):
        grp.toggle()
        self._open_state[key] = grp._open

    def _rebuild_list(self):
        clear_layout(self.list_layout)
        b = self._badges()
        is_chain = bool(self.results.get("is_chain"))

        # ── 1. DESIGN REQUIREMENTS -- what the customer specifies ──────
        req = self._add_group(
            "requirements", "Design Requirements", "CEMA 375",
            merge_badges(b["process"], b["service"]), True)

        mat = self.results.get("mat") or {}
        mat_name = mat.get("name", self.inputs.get("mat_id", "—"))
        self._add_row(
            req, "Material & Duty",
            f"{self.inputs.get('Q_req','—')}t/h · {self.inputs.get('H_m','—')}m · "
            f"{mat_name} · Fill {self.inputs.get('fill_pct','—')}%",
            self._open_process_dialog, b["process"])
        self._add_row(
            req, "Service Conditions", self._service_summary(),
            self._open_service_dialog, b["service"])

        # ── 2. MECHANICAL DESIGN -- derived, then chosen ───────────────
        mech_badge = merge_badges(
            b["chain"] if is_chain else b["belt"],
            b["bucket"], b["pulleys"], b["shaft"], b["takeup"],
            b["discharge"], b["feed"], b["casing"],
        )
        mech = self._add_group(
            "mechanical", "Mechanical Design", "CEMA 375", mech_badge, True)

        self._add_row(
            mech, "Chain Selection" if is_chain else "Belt Selection",
            self._chain_summary() if is_chain else self._belt_summary(),
            self._open_belt_chain_dialog, b["chain"] if is_chain else b["belt"])

        bkt = self.results.get("bucket") or {}
        self._add_row(
            mech, "Bucket Selection",
            f"{'Auto: ' if self.inputs.get('auto_bucket') else ''}"
            f"{bkt.get('id', 'auto')} series · {fmt(bkt.get('V'), 1)}L · "
            f"Gap {self.inputs.get('bucket_gap','—')}mm",
            self._open_bucket_dialog, b["bucket"])

        boot_pulley = self.results.get("boot_pulley") or {}
        boot_d = boot_pulley.get("boot_D_mm", self.inputs.get("boot_pulley_D_mm", "—"))
        wrap = self.results.get("wrap_effective_deg", self.inputs.get("wrap_deg", 180))
        self._add_row(
            mech, "Head & Tail Pulley",
            f"D_H {self.inputs.get('D_mm','—')}mm · D_B {boot_d}mm · "
            f"{self.inputs.get('n_rpm','—')}rpm · Wrap {fmt(wrap, 1)}°",
            self._open_pulley_dialog, b["pulleys"])

        self._add_row(
            mech, "Shaft & Bearings",
            f"{self.inputs.get('shaft_material','A36')} · "
            f"Ø{fmt(self.results.get('d_mm'), 1)}mm · "
            f"{self.inputs.get('shaft_section','solid')} · "
            f"{self.inputs.get('shaft_hub_connection','keyed')}",
            self._open_shaft_dialog, b["shaft"])

        self._add_row(mech, "Take-Up Selection", self._takeup_summary(),
                      self._open_takeup_dialog, b["takeup"])
        self._add_row(mech, "Discharge Section", self._discharge_summary(),
                      self._open_discharge_dialog, b["discharge"])
        self._add_row(mech, "Feed Design", self._feed_summary(),
                      self._open_feed_dialog, b["feed"])
        self._add_row(mech, "Casing Design", self._casing_summary(),
                      self._open_casing_dialog, b["casing"])

        # ── 3. POWER TRANSMISSION -- derived from the design above ─────
        power = self._add_group(
            "power", "Power Transmission", "CEMA 375 §4", b["power"], False)
        self._add_row(power, "Motor & Drive", self._power_summary(),
                      self._open_power_dialog, b["power"])

        self.list_layout.addStretch()

        # Standards footer -- ported from the JSX, was missing here entirely.
        footer = QLabel("CEMA 375-2017 · ISO 281 · ASME B17.1")
        footer.setStyleSheet(scoped(
            footer,
            f"color: {TEXT3}; font-size: 13px; padding: 8px 12px; "
            f"border: none; border-top: 1px solid {BORDER};"
        ))
        self.list_layout.addWidget(footer)

    # ── Summaries ─────────────────────────────────────────────────────
    def _discharge_summary(self):
        r = self.results
        dc = r.get("discharge_chute") or {}
        perf = dc.get("performance") or {}
        dtype = r.get("discharge_type", "—")
        liner = self.inputs.get("chute_liner_id", "auto")
        return f"{str(dtype).capitalize()} · {liner} liner · {fmt(perf.get('chute_angle_deg'), 0)}°"

    def _feed_summary(self):
        fd = self.results.get("feed_design") or {}
        if fd:
            return (f"{fd.get('loading_type', '—')} · "
                    f"Surge {fmt(fd.get('V_surge_litres'), 0)}L")
        return "Run calculation to see boot feed geometry"

    def _casing_summary(self):
        cp = self.results.get("casing_panel") or {}
        t_use = cp.get("t_use_mm")
        if t_use is not None:
            return f"{fmt(t_use, 1)}mm plate · {cp.get('status', '—')}"
        return "Run calculation to see casing sizing"

    def _service_summary(self):
        env = self.inputs.get("environment", "dry")
        return f"{env.capitalize()} · μ={fmt(self.inputs.get('mu', 0.35), 2)}"

    def _power_summary(self):
        r = self.results
        if r.get("motor_kw") is not None:
            return (f"{fmt(r.get('motor_kw'), 0)}kW · "
                    f"{self.inputs.get('drive_start_type', 'soft_start')}")
        return "Run calculation to see motor sizing"

    def _takeup_summary(self):
        takeup_type = self.inputs.get("takeup_type", "gravity")
        tg = self.results.get("takeup_gravity") or {}
        ts = self.results.get("takeup_screw") or {}
        th = self.results.get("takeup_hydraulic") or {}
        primary = next((d for d in (tg, ts, th) if d.get("primary")), None)
        if primary is tg and tg:
            return (f"{takeup_type} · "
                    f"{fmt(tg.get('W_counterweight_kg_gross'), 0)}kg counterweight")
        if primary is ts and ts:
            return (f"{takeup_type} · {fmt(ts.get('d_core_min_mm'), 0)}mm core · "
                    f"SF={fmt(ts.get('SF_buckling'), 1)}")
        if primary is th and th:
            return (f"{takeup_type} · {fmt(th.get('d_bore_min_mm'), 0)}mm bore @ "
                    f"{fmt(th.get('operating_bar'), 0)}bar")
        return f"{takeup_type} take-up"

    def _belt_summary(self):
        r = self.results
        ply = (str(r["belt_ply"]) + " PLY") if r.get("belt_ply") else "auto"
        return (f"{r.get('belt_class') or ply} · {fmt(r.get('belt_w'), 0)}mm · "
                f"{self.inputs.get('belt_type', 'EP')}")

    def _chain_summary(self):
        cs = self.results.get("chain_selected") or {}
        return f"{cs.get('name', 'auto')} · SF={fmt(self.results.get('chain_SF_actual'), 2)}"

    # ── Dialog openers ────────────────────────────────────────────────
    def _open_dialog(self, dialog_cls):
        dlg = dialog_cls(self.inputs, self.results, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.inputsChanged.emit(dlg.updated_inputs())

    def _open_process_dialog(self):
        self._open_dialog(ProcessEditDialog)

    def _open_belt_chain_dialog(self):
        self._open_dialog(BeltChainEditDialog)

    def _open_bucket_dialog(self):
        self._open_dialog(BucketEditDialog)

    def _open_pulley_dialog(self):
        self._open_dialog(PulleyEditDialog)

    def _open_shaft_dialog(self):
        self._open_dialog(ShaftEditDialog)

    def _open_takeup_dialog(self):
        self._open_dialog(TakeupEditDialog)

    def _open_discharge_dialog(self):
        self._open_dialog(DischargeEditDialog)

    def _open_feed_dialog(self):
        self._open_dialog(FeedEditDialog)

    def _open_casing_dialog(self):
        self._open_dialog(CasingEditDialog)

    def _open_service_dialog(self):
        self._open_dialog(ServiceEditDialog)

    def _open_power_dialog(self):
        self._open_dialog(PowerEditDialog)