"""
components/dialog_helpers.py -- shared widgets/functions for InputSidebar
section dialogs.
═══════════════════════════════════════════════════════════════════════════
Extracted from input_sidebar.py so that new section modules (takeup_edit.py,
feed_edit.py, discharge_edit.py, casing_edit.py, ...) can import them
without creating a circular dependency with input_sidebar.py.

Every InputSidebar section dialog should import from here rather than keep
its own copy -- one shared module to change instead of N files drifting
apart, same reasoning theme.py documents for the color palette.

FIX (Jay: "green and red borders... very cheesy and 1960s. Modernize with
simple green checks or red Xs, blue 'i' and orange 'w'"): every pass/fail/
warn/info indicator in this app used a thick colored border + tinted
background wrapped around an entire box -- StatusCard, stat_box's
border_color, the Material-Based Design Guidance mismatch card, the casing
clearance card, etc, each reimplementing the same heavy treatment
independently. Replaced everywhere with ONE shared visual language: a
small colored icon badge (status_badge()) carries the status, boxes stay
neutrally bordered. flag_note() is the standard way to attach a status
to a line of text from here on -- new sections should use it instead of
inventing another colored card.

FIX (Jay: "discharge and feed modal text rendering is very small and
illegible especially on the grey/light blue headings and texts inside of
advisories"): confirmed the actual cause directly, not assumed -- TEXT3
and MUTED are the literal SAME color in theme.py (#5a7a9a), and nearly
every heading/note in this app used one of the two at 9-10.5px. That's a
genuinely low-contrast color at a genuinely small size, not just one or
the other. section_head and field_row's note text now use TEXT2 (#b0c4d8,
meaningfully brighter) at 11px instead, reserving TEXT3/MUTED for short,
truly secondary meta text only.
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton, QComboBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette, QColor

from theme import BG, PANEL, PANEL2, BORDER, TEXT, TEXT2, TEXT3, MUTED, PRIMARY, SUCCESS, WARNING, DANGER
from api_client import fetch_components

# ── Status icon system ───────────────────────────────────────────────────
# Four states used consistently across every modal from here on:
#   ok / pass  -> green check
#   fail       -> red X
#   warn       -> orange "W"
#   info       -> blue "i"
STATUS_STYLE = {
    "ok":   ("✓", SUCCESS),
    "pass": ("✓", SUCCESS),
    "fail": ("✗", DANGER),
    "warn": ("W", WARNING),
    "info": ("i", PRIMARY),
}


def status_badge(status, size=16):
    """Small colored circular badge -- the ONE place a pass/fail/warn/info
    color gets expressed visually now, instead of wrapping an entire box
    in a colored border. Returns a QLabel sized for inline use next to
    text (see flag_note() below) or standalone in a corner."""
    icon, color = STATUS_STYLE.get(status, ("i", TEXT2))
    c = QColor(color)
    lbl = QLabel(icon)
    lbl.setFixedSize(size, size)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet(
        f"background-color: rgba({c.red()},{c.green()},{c.blue()},.16); "
        f"color: {color}; border-radius: {size // 2}px; "
        f"font-size: {max(9, size - 6)}px; font-weight: 700;"
    )
    return lbl


def flag_note(status, text, parent_layout=None):
    """Standard way to show a single flagged line of text (a check
    result, a warning, an advisory) -- small status badge + legible
    text, on a neutral background. Replaces the old pattern of a full
    QFrame with a colored border/background per message. If
    parent_layout is given, adds itself directly; otherwise returns the
    QWidget to add manually."""
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    layout.addWidget(status_badge(status))
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(f"color: {TEXT2}; font-size: 11px;")
    layout.addWidget(lbl, 1)
    if parent_layout is not None:
        parent_layout.addWidget(row)
    return row


def fmt(v, dp=1, fb="—"):
    if v is None:
        return fb
    try:
        return f"{float(v):.{dp}f}"
    except (TypeError, ValueError):
        return fb


def section_head(text):
    lbl = QLabel(text.upper())
    lbl.setStyleSheet(f"color: {TEXT2}; font-size: 11px; font-weight: 700; letter-spacing: 1px; margin-top: 4px;")
    return lbl


def field_row(label, widget, unit=None, note=None, status=None):
    """status (optional) prefixes a small badge to the note line --
    replaces the old practice of coloring the note text itself by
    status, which relied on color alone (and on TEXT3/MUTED, which is
    where the legibility problem came from)."""
    box = QVBoxLayout()
    box.setSpacing(3)
    lbl = QLabel(label)
    lbl.setStyleSheet(f"color: {TEXT2}; font-size: 11px; font-weight: 600;")
    box.addWidget(lbl)
    row = QHBoxLayout()
    row.addWidget(widget)
    if unit:
        unit_lbl = QLabel(unit)
        unit_lbl.setStyleSheet(f"color: {TEXT2}; font-size: 10.5px;")
        row.addWidget(unit_lbl)
    box.addLayout(row)
    if status or note:
        if status:
            note_row = QHBoxLayout()
            note_row.setSpacing(6)
            note_row.addWidget(status_badge(status, size=14))
            if note:
                note_lbl = QLabel(note)
                note_lbl.setWordWrap(True)
                note_lbl.setStyleSheet(f"color: {TEXT2}; font-size: 10.5px;")
                note_row.addWidget(note_lbl, 1)
            else:
                note_row.addStretch()
            box.addLayout(note_row)
        else:
            note_lbl = QLabel(note)
            note_lbl.setStyleSheet(f"color: {TEXT2}; font-size: 10.5px;")
            note_lbl.setWordWrap(True)
            box.addWidget(note_lbl)
    return box


def styled_spinbox(spinbox):
    # FIX: the real bug here wasn't a font fallback issue (that was a
    # red herring I ruled out by checking .value()/.text() against the
    # rendered pixels, and by testing the same font-family string in
    # isolation, where it rendered fine). The actual cause: this widget
    # had no minimum height, so when the right column's combined content
    # needed more vertical space than the dialog's natural height gave
    # it, Qt's layout engine compressed individual spinboxes down to as
    # little as 17px tall -- confirmed directly via .size(). 17px isn't
    # enough room for a 12px font plus 5px top/bottom padding to render
    # without visually overlapping. Setting an explicit minimum height
    # makes this a hard floor the layout can't shrink past.
    spinbox.setMinimumHeight(28)
    # FIX (Jay: "lost silver color in the arrows" + "overlapping numbers"):
    # both trace back to the same cause. Switching the app to
    # app.setStyle("Fusion") (main.py, to fix the tab-pill rendering)
    # changed how QAbstractSpinBox's up/down sub-controls get laid out --
    # Fusion doesn't reserve the same implicit right-hand gap the native
    # Windows style did, so without an explicit padding-right the value
    # text and the arrow buttons started overlapping. And Fusion draws
    # the small arrow glyphs using the widget's ButtonText palette role,
    # not the QSS `color` property -- nothing was setting that role
    # explicitly, so the arrows defaulted to a near-invisible dark tone
    # against this dark theme once Fusion took over the rendering.
    # Fixed both together: explicit subcontrol geometry for the up/down
    # buttons (with real padding-right reserved so text can't run under
    # them) and a direct QPalette.ButtonText override so the arrows are
    # visibly silver-blue (TEXT2) again, matching how they looked under
    # the native style before Fusion was introduced.
    spinbox.setStyleSheet(f"""
        QAbstractSpinBox {{
            background-color: {PANEL2}; color: {TEXT}; border: 1px solid {BORDER};
            border-radius: 4px; padding: 5px 22px 5px 8px; font-size: 12px;
        }}
        QAbstractSpinBox::up-button {{
            subcontrol-origin: border; subcontrol-position: top right;
            width: 18px; height: 13px;
            border-left: 1px solid {BORDER}; border-bottom: 1px solid {BORDER};
            border-top-right-radius: 4px;
            background-color: {PANEL2};
        }}
        QAbstractSpinBox::down-button {{
            subcontrol-origin: border; subcontrol-position: bottom right;
            width: 18px; height: 13px;
            border-left: 1px solid {BORDER};
            border-bottom-right-radius: 4px;
            background-color: {PANEL2};
        }}
        QAbstractSpinBox::up-button:hover, QAbstractSpinBox::down-button:hover {{
            background-color: {BORDER};
        }}
    """)
    pal = spinbox.palette()
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT2))
    spinbox.setPalette(pal)
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
        sub.setStyleSheet(f"color: {TEXT2}; font-size: 10.5px;")
        hl.addWidget(sub)
    return header


def modal_footer(dialog):
    footer = QFrame()
    layout = QHBoxLayout(footer)
    layout.setContentsMargins(12, 8, 12, 8)
    layout.addStretch()
    cancel = QPushButton("Cancel")
    cancel.setStyleSheet(f"background-color: transparent; color: {TEXT2}; border: none; padding: 6px 14px;")
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


def stat_box(stats, status=None, note=None):
    """Neutral info box: a row of labeled stats, with an optional status
    badge + note line below.

    FIX (Jay: "green and red borders... very cheesy"): this used to take
    border_color/note_color and wrap the entire box in a colored frame.
    Border is now always neutral BORDER -- status is carried by a small
    badge next to the note text instead (see status_badge() above), the
    same visual language every modal now uses consistently.

    FIX (real bug found via screenshot review): the badge used to only
    render when `note` was also given -- a status passed with no note
    text (e.g. a liner wear rating box with no extra commentary) was
    silently dropped, leaving a HIGH-risk reading with no visual flag at
    all. status now always renders its badge on its own row when given,
    whether or not there's accompanying note text.
    """
    box = QFrame()
    box.setStyleSheet(f"background-color: {PANEL2}; border: 1px solid {BORDER}; border-radius: 5px;")
    layout = QVBoxLayout(box)
    layout.setContentsMargins(10, 8, 10, 8)
    layout.setSpacing(4)
    row = QHBoxLayout()
    row.setSpacing(16)
    for label, value in stats:
        col = QVBoxLayout()
        col.setSpacing(1)
        l = QLabel(label)
        l.setStyleSheet(f"color: {TEXT2}; font-size: 9.5px;")
        v = QLabel(str(value))
        v.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: 700; font-family: 'JetBrains Mono', monospace;")
        col.addWidget(l); col.addWidget(v)
        row.addLayout(col)
    row.addStretch()
    layout.addLayout(row)
    if status or note:
        note_row = QHBoxLayout()
        note_row.setSpacing(6)
        if status:
            note_row.addWidget(status_badge(status, size=14))
        if note:
            note_lbl = QLabel(note)
            note_lbl.setWordWrap(True)
            note_lbl.setStyleSheet(f"color: {TEXT2}; font-size: 10.5px; margin-top: 2px;")
            note_row.addWidget(note_lbl, 1)
        else:
            note_row.addStretch()
        layout.addLayout(note_row)
    return box


class ToggleButton(QPushButton):
    """A real toggle control (✓ ON / OFF), not a plain checkbox."""

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
                f"background-color: {PANEL2}; color: {TEXT2}; border: 1px solid {BORDER}; "
                f"border-radius: 5px; padding: 6px 16px;"
            )


def toggle_pair(options, current_value, on_change):
    """Two equal-width buttons, the active one filled, the other neutral."""
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
                    f"background-color: {PANEL2}; color: {TEXT2}; border: 1px solid {BORDER}; "
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


def n_way_selector(options, current_value, on_change):
    """Like toggle_pair but for 3+ mutually-exclusive options in one row
    (e.g. Take-Up Type: Gravity/Screw/Hydraulic/Auto). options is a list
    of (value, label) tuples."""
    row = QHBoxLayout()
    row.setSpacing(6)
    buttons = {}

    def restyle():
        for val, btn in buttons.items():
            active = val == current_value[0]
            if active:
                btn.setStyleSheet(
                    f"background-color: rgba(74,158,255,.15); color: {PRIMARY}; "
                    f"border: 1px solid {PRIMARY}; border-radius: 5px; padding: 7px 4px; font-weight: 600;"
                )
            else:
                btn.setStyleSheet(
                    f"background-color: {PANEL2}; color: {TEXT2}; border: 1px solid {BORDER}; "
                    f"border-radius: 5px; padding: 7px 4px;"
                )

    for val, label in options:
        btn = QPushButton(label)

        def clicked(checked, v=val):
            current_value[0] = v
            restyle()
            on_change(v)
        btn.clicked.connect(clicked)
        row.addWidget(btn)
        buttons[val] = btn
    restyle()
    return row


class ComponentPickerWidget(QWidget):
    """Real port of ComponentPicker.jsx: fetches a catalog list from a
    given API path + query params, shows it as a dropdown with "Auto
    (solver default)" as the first option. If the catalog is empty, this
    honestly shows "0 options available" rather than fabricating entries.

    Moved here from input_sidebar.py so power_edit.py (gearbox/drive
    model pickers) can reuse it without duplicating the implementation --
    same reasoning every other shared widget in this file follows."""

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
        count_lbl.setStyleSheet(f"color: {TEXT2 if self.options else WARNING}; font-size: 10px;")
        layout.addWidget(count_lbl)
        if note:
            note_lbl = QLabel(note)
            note_lbl.setWordWrap(True)
            note_lbl.setStyleSheet(f"color: {TEXT2}; font-size: 10px;")
            layout.addWidget(note_lbl)

    def value(self):
        return self.combo.currentData()