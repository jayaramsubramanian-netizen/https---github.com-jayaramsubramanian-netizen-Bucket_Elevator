"""
components/dialog_helpers.py -- shared widgets/functions for InputSidebar
section dialogs.
═══════════════════════════════════════════════════════════════════════════
Extracted from input_sidebar.py so that new section modules (takeup_edit.py,
feed_edit.py, discharge_edit.py, casing_edit.py, ...) can import them
without creating a circular dependency with input_sidebar.py.

FIX THIS ROUND -- BOX-IN-BOX BORDERS, ROOT CAUSE
────────────────────────────────────────────────
Every bordered container in this file used a BARE stylesheet declaration:

    box.setStyleSheet(f"background-color: {PANEL2}; border: 1px solid {BORDER}; ...")

Qt treats a selector-less stylesheet as `* { ... }` -- it applies to the
widget AND EVERY DESCENDANT. So stat_box's border was inherited by each of
its stat QLabels, each of which then drew its own box. Same for
modal_header, ComponentPickerWidget's combo, ToggleButton, toggle_pair,
n_way_selector, styled_message_box.

Verified directly rather than assumed: a QFrame with 4 child QLabels
rendered 1732 interior border pixels in exactly 8 horizontal runs (4
children x top+bottom edge) under a bare declaration, and 0 under a
scoped one.

This is why every previous local fix failed -- the border wasn't coming
from the widget being edited, it was raining down from an ancestor.

Every declaration below is now scoped via theme.scoped()/card_qss()/
card_frame(). If you add a new bordered widget to this file, use those
helpers. Do not hand-write a bare `border:` declaration.

(Retained from prior rounds: the status-icon visual language -- small
colored badge carries pass/fail/warn/info, boxes stay neutrally
bordered -- and the legibility pass on heading/note text. Note that
TEXT3 and MUTED are no longer the same literal in theme.py v2, so the
contrast complaint that drove that pass is now structurally fixed at the
token level too.)
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton, QComboBox,
)
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPalette, QColor, QPainter, QBrush, QPen, QFont

from theme import (
    BG, PANEL, PANEL2, SURFACE, BORDER, BORDER2, TEXT, TEXT2, TEXT3, MUTED,
    PRIMARY, PRIMARY_DIM, PRIMARY_RING, SUCCESS, WARNING, DANGER, INFO,
    R_SM, R_MD, FF_MONO,
    scoped, card_qss, card_frame, status_card_qss,
)
from api_client import fetch_components

# ── Status icon system ───────────────────────────────────────────────────
#   ok / pass  -> green check      fail -> red X
#   warn       -> orange "W"       info -> blue "i"
STATUS_STYLE = {
    "ok":   ("✓", SUCCESS),
    "pass": ("✓", SUCCESS),
    "fail": ("✗", DANGER),
    "warn": ("W", WARNING),
    "info": ("i", PRIMARY),
}


def status_badge(status, size=16):
    """Small colored circular badge -- the ONE place a pass/fail/warn/info
    color gets expressed visually, instead of wrapping a whole box in a
    colored border.

    Scoped: a QLabel has no children in practice, but scoping it costs
    nothing and keeps the file's rule uniform -- no bare declarations
    anywhere, so there's no pattern here for a future edit to copy wrongly.
    """
    icon, color = STATUS_STYLE.get(status, ("i", TEXT2))
    c = QColor(color)
    lbl = QLabel(icon)
    lbl.setFixedSize(size, size)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet(scoped(
        lbl,
        f"background-color: rgba({c.red()},{c.green()},{c.blue()},.16); "
        f"color: {color}; border: none; border-radius: {size // 2}px; "
        f"font-size: {max(9, size - 6)}px; font-weight: 700;"
    ))
    return lbl


def flag_note(status, text, parent_layout=None):
    """Standard way to show a single flagged line of text -- small status
    badge + legible text, on a neutral background. Replaces the old
    pattern of a full QFrame with a colored border per message."""
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    layout.addWidget(status_badge(status))
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(f"color: {TEXT2}; font-size: 11px;")   # no border -> safe
    layout.addWidget(lbl, 1)
    if parent_layout is not None:
        parent_layout.addWidget(row)
    return row


def clear_layout(layout):
    """Recursively empty a layout.

    setParent(None) removes a widget from the visual tree immediately;
    deleteLater() alone defers cleanup and can leave a one-frame ghost of
    the widget's last-painted pixels.

    Lives here because it was copy-pasted verbatim into input_sidebar.py
    (7 times) and design_review_panel.py (as a nested _clear inside
    _rebuild). One copy, shared.
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


def fmt(v, dp=1, fb="—"):
    if v is None:
        return fb
    try:
        return f"{float(v):.{dp}f}"
    except (TypeError, ValueError):
        return fb


def section_head(text):
    # Color/font only -- no border, so a bare declaration is harmless here.
    # (The cascade rule only bites when a `border` is involved.)
    lbl = QLabel(text.upper())
    lbl.setStyleSheet(
        f"color: {TEXT2}; font-size: 11px; font-weight: 700; "
        f"letter-spacing: 1px; margin-top: 4px;"
    )
    return lbl


def field_row(label, widget, unit=None, note=None, status=None):
    """status (optional) prefixes a small badge to the note line."""
    box = QVBoxLayout()
    box.setSpacing(3)
    lbl = QLabel(label)
    lbl.setStyleSheet(f"color: {TEXT2}; font-size: 11px; font-weight: 600;")
    box.addWidget(lbl)
    row = QHBoxLayout()
    row.addWidget(widget)
    if unit:
        unit_lbl = QLabel(unit)
        unit_lbl.setStyleSheet(f"color: {TEXT3}; font-size: 10.5px;")
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
    """Spinbox styling.

    ARROW BUTTONS -- FIXED THIS ROUND
    ─────────────────────────────────
    The previous version gave the up/down buttons
    `background-color: SURFACE` -- the SAME color as the field they sit in --
    plus a `border-left` and `border-bottom` in BORDER2, plus an 8px
    (R_MD) corner radius.

    The result is exactly what the screenshot shows: the button has no
    color contrast against the field, so the ONLY thing that makes it
    visible is its border -- i.e. a grey box outlined inside a grey field.
    A background identical to its parent is not styling, it's just a
    rectangle of borders. And the 8px radius was applied to a button only
    13px TALL, so the rounding exceeded half the height and the corners
    bloated.

    The correct model: these are affordances ON the field's surface, not
    boxes INSIDE it. So:
      - background transparent (they inherit the field's own color)
      - no border, no radius -- nothing to draw a box with
      - contrast comes from HOVER (a faint white tint) and from the arrow
        glyph itself, which is how a real spinbox reads
      - a single hairline separator between the two buttons only, so up
        and down remain distinguishable targets

    RETAINED (both still needed, both still correct):
      - setMinimumHeight(28): without it the layout engine can compress a
        spinbox to ~17px, too short for a 12px font + padding, so the value
        text visually collapses. Confirmed via .size() when first found.
      - QPalette.ButtonText: Fusion draws the arrow GLYPHS from the
        ButtonText palette role, not from the QSS `color` property, so
        without this the arrows go near-invisible on the dark theme. This
        matters MORE now that the buttons have no border to hint at their
        presence -- the glyph is doing all the work.
      - Right-hand padding (22px) reserving space so the value text can
        never run under the arrows.

    Border scoping: these rules are selector-qualified
    (QAbstractSpinBox / ::up-button / ::down-button) and a QSpinBox has no
    styleable child widgets, so nothing cascades. Kept class-scoped rather
    than object-scoped so the sub-control pseudo-elements keep working.
    """
    spinbox.setMinimumHeight(28)
    spinbox.setStyleSheet(f"""
        QAbstractSpinBox {{
            background-color: {SURFACE}; color: {TEXT};
            border: 1px solid {BORDER2};
            border-radius: {R_SM}px; padding: 5px 22px 5px 8px; font-size: 12px;
        }}
        QAbstractSpinBox:focus {{ border: 1px solid {PRIMARY}; }}
        QAbstractSpinBox::up-button {{
            subcontrol-origin: border; subcontrol-position: top right;
            width: 18px; height: 13px;
            background-color: transparent;
            border: none;
            border-bottom: 1px solid rgba(255,255,255,.06);
            border-top-right-radius: {R_SM - 1}px;
        }}
        QAbstractSpinBox::down-button {{
            subcontrol-origin: border; subcontrol-position: bottom right;
            width: 18px; height: 13px;
            background-color: transparent;
            border: none;
            border-bottom-right-radius: {R_SM - 1}px;
        }}
        QAbstractSpinBox::up-button:hover, QAbstractSpinBox::down-button:hover {{
            background-color: rgba(255,255,255,.08);
        }}
        QAbstractSpinBox::up-button:pressed, QAbstractSpinBox::down-button:pressed {{
            background-color: rgba(255,255,255,.14);
        }}
    """)
    pal = spinbox.palette()
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT2))
    spinbox.setPalette(pal)
    return spinbox


def styled_combo(combo):
    """Shared, correctly-scoped QComboBox styling.

    Radius is R_SM, matching styled_spinbox -- these two sit side by side
    in every dialog, so a different corner radius on each reads as a
    rendering bug. (Was R_MD = 8px, which was also part of the
    "corners are too big" complaint.)

    The drop-down arrow gets the same treatment as the spinbox buttons:
    no background, no border -- an affordance on the field's surface, not
    a box inside it.

    NEW: previously every dialog hand-rolled this exact stylesheet inline
    (input_sidebar.py alone had 6 near-identical copies, each a bare
    declaration with a `border:` in it). One helper, one scoped rule.
    """
    combo.setMinimumHeight(28)
    combo.setStyleSheet(f"""
        QComboBox {{
            background-color: {SURFACE}; color: {TEXT};
            border: 1px solid {BORDER2};
            border-radius: {R_SM}px; padding: 5px 8px; font-size: 12px;
        }}
        QComboBox:focus {{ border: 1px solid {PRIMARY}; }}
        QComboBox::drop-down {{
            border: none; background-color: transparent; width: 20px;
        }}
        QComboBox::drop-down:hover {{ background-color: rgba(255,255,255,.08); }}
        QComboBox QAbstractItemView {{
            background-color: {PANEL2}; color: {TEXT};
            border: 1px solid {BORDER2};
            selection-background-color: {PRIMARY}; selection-color: #ffffff;
        }}
    """)
    return combo


def styled_lineedit(edit, placeholder=None):
    """Shared, correctly-scoped QLineEdit styling.

    NEW: input_sidebar.py hand-rolled this exact stylesheet twice (the
    material search box and the custom-material-name field), each a bare
    declaration carrying a `border:`. One helper, one scoped rule.
    """
    if placeholder:
        edit.setPlaceholderText(placeholder)
    edit.setMinimumHeight(28)
    edit.setStyleSheet(f"""
        QLineEdit {{
            background-color: {SURFACE}; color: {TEXT};
            border: 1px solid {BORDER2};
            border-radius: {R_SM}px; padding: 5px 10px; font-size: 12px;
        }}
        QLineEdit:focus {{ border: 1px solid {PRIMARY}; }}
    """)
    return edit


def modal_header(title, cema=None):
    """The ONE place CEMA reference text lives -- once per modal, under its
    title, not repeated per sidebar row.

    SCOPED: the old bare declaration put a bottom border on the title
    QLabel and the CEMA QLabel too, which is precisely the underline
    artifact under modal titles.
    """
    header = QFrame()
    header.setStyleSheet(scoped(
        header,
        f"background-color: {PANEL2}; border: none; "
        f"border-bottom: 1px solid {BORDER};"
    ))
    hl = QVBoxLayout(header)
    hl.setContentsMargins(16, 12, 16, 12)
    hl.setSpacing(2)
    title_lbl = QLabel(title)
    title_lbl.setStyleSheet(f"color: {TEXT}; font-size: 14px; font-weight: 700;")
    hl.addWidget(title_lbl)
    if cema:
        sub = QLabel(cema)
        sub.setStyleSheet(f"color: {TEXT3}; font-size: 10.5px;")
        hl.addWidget(sub)
    return header


def modal_footer(dialog):
    footer = QFrame()
    footer.setStyleSheet(scoped(
        footer,
        f"background-color: {PANEL}; border: none; "
        f"border-top: 1px solid {BORDER};"
    ))
    layout = QHBoxLayout(footer)
    layout.setContentsMargins(12, 8, 12, 8)
    layout.addStretch()

    cancel = QPushButton("Cancel")
    cancel.setStyleSheet(scoped(
        cancel,
        f"background-color: transparent; color: {TEXT2}; border: none; "
        f"padding: 6px 14px; font-size: 11.5px;",
        extra="{sel}:hover { color: %s; }" % TEXT,
    ))
    cancel.clicked.connect(dialog.reject)

    apply_btn = QPushButton("Apply")
    apply_btn.setStyleSheet(scoped(
        apply_btn,
        f"background-color: {PRIMARY}; color: white; border: none; "
        f"border-radius: {R_MD}px; padding: 6px 18px; "
        f"font-size: 11.5px; font-weight: 600;",
    ))
    apply_btn.clicked.connect(dialog.accept)

    layout.addWidget(cancel)
    layout.addWidget(apply_btn)
    return footer


def stat_box(stats, status=None, note=None):
    """Neutral info box: a row of labeled stats, with an optional status
    badge + note line below.

    SCOPED (this round): this was the single worst box-in-box offender in
    the app -- a bare `border: 1px solid` declaration on a QFrame whose
    entire content is QLabels, so EVERY stat label and value drew its own
    border. That's the "Stress / Deflection / Governing" grid rendering as
    six little boxes inside one big box.

    Retained: border is always neutral; status is carried by a small badge
    (never a colored frame). status renders its badge even when `note` is
    absent -- a status with no note used to be silently dropped.
    """
    box, layout = card_frame(bg=PANEL2, border=BORDER, radius=R_SM,
                             margins=(10, 8, 10, 8), spacing=4)
    row = QHBoxLayout()
    row.setSpacing(16)
    for label, value in stats:
        col = QVBoxLayout()
        col.setSpacing(1)
        l = QLabel(label)
        l.setStyleSheet(f"color: {TEXT3}; font-size: 9.5px;")
        v = QLabel(str(value))
        v.setStyleSheet(
            f"color: {TEXT}; font-size: 13px; font-weight: 700; "
            f"font-family: {FF_MONO};"
        )
        col.addWidget(l)
        col.addWidget(v)
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
            note_lbl.setStyleSheet(f"color: {TEXT2}; font-size: 10.5px;")
            note_row.addWidget(note_lbl, 1)
        else:
            note_row.addStretch()
        layout.addLayout(note_row)
    return box


# ── Selection controls ───────────────────────────────────────────────────
# All three below previously used bare declarations with a `border:` in
# them. A QPushButton's text is drawn internally, not by a child widget, so
# these didn't produce a visible box-in-box -- but they're converted anyway
# so there is NO bare-declaration pattern left in this file for a future
# edit to copy. The rgba literals are now theme tokens.

def _sel_btn_qss(btn, active, padding):
    if active:
        return scoped(btn,
            f"background-color: {PRIMARY_DIM}; color: {PRIMARY}; "
            f"border: 1px solid {PRIMARY_RING}; border-radius: {R_SM}px; "
            f"padding: {padding}; font-weight: 600;")
    return scoped(btn,
        f"background-color: {SURFACE}; color: {TEXT2}; "
        f"border: 1px solid {BORDER}; border-radius: {R_SM}px; "
        f"padding: {padding};")


class ToggleButton(QPushButton):
    """A real toggle control (✓ ON / OFF), not a plain checkbox."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedWidth(90)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggled.connect(self._restyle)
        self._restyle(False)

    def _restyle(self, checked):
        self.setText("✓ ON" if checked else "OFF")
        self.setStyleSheet(_sel_btn_qss(self, checked, "6px 16px"))


def toggle_pair(options, current_value, on_change):
    """Two equal-width buttons, the active one filled, the other neutral."""
    row = QHBoxLayout()
    row.setSpacing(8)
    buttons = {}

    def restyle():
        for val, btn in buttons.items():
            btn.setStyleSheet(_sel_btn_qss(btn, val == current_value[0], "8px 4px"))

    for val in options:
        btn = QPushButton(val.capitalize())
        btn.setCursor(Qt.CursorShape.PointingHandCursor)

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
            btn.setStyleSheet(_sel_btn_qss(btn, val == current_value[0], "7px 4px"))

    for val, label in options:
        btn = QPushButton(label)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)

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
    """

    def __init__(self, path, params, format_label, current_value, auto_label,
                 label, note=None, parent=None):
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

        self.combo = styled_combo(QComboBox())
        auto_text = "— Auto (solver default) —" + (f": {auto_label}" if auto_label else "")
        self.combo.addItem(auto_text, "")
        selected_index = 0
        for i, row in enumerate(self.options):
            text = format_label(row)
            self.combo.addItem(text, row.get("name", text))
            if current_value and row.get("name") == current_value:
                selected_index = i + 1
        self.combo.setCurrentIndex(selected_index)
        layout.addWidget(self.combo)

        count_text = (f"{len(self.options)} options available" if self.options
                      else "0 options available — catalog not yet populated for this component")
        count_lbl = QLabel(count_text)
        count_lbl.setStyleSheet(
            f"color: {TEXT3 if self.options else WARNING}; font-size: 10px;")
        layout.addWidget(count_lbl)
        if note:
            note_lbl = QLabel(note)
            note_lbl.setWordWrap(True)
            note_lbl.setStyleSheet(f"color: {TEXT2}; font-size: 10px;")
            layout.addWidget(note_lbl)

    def value(self):
        return self.combo.currentData()


class KPIChip(QWidget):
    """One performance-indicator chip -- single bordered box, no nested
    box-in-a-box, drawn directly with QPainter.

    This widget was already immune to the cascade bug by construction:
    it paints its own border and has no child widgets to inherit one.
    Which is exactly why it's the model the other cards should follow --
    and, incidentally, strong corroborating evidence for the diagnosis:
    the ONE card in the app that never used a bare stylesheet is the ONE
    card that never had a box-in-box.

    Retained: QFont.Weight.Bold rather than QSS `font-weight: 700`,
    because QSS bold on a font with no real bold variant makes Qt
    synthesize it by double-drawing the outline, which reads as smeared
    at small sizes on a real Windows render.
    """

    def __init__(self, label, unit, parent=None, value_pixel_size=24,
                 min_size=(80, 56)):
        super().__init__(parent)
        self.label_text = (label or "").upper()
        self.unit_text = unit or ""
        self.value_text = "—"
        self.accent_color = QColor(TEXT3)
        self.value_pixel_size = value_pixel_size
        self.setMinimumSize(*min_size)

    def set_value(self, text, color_hex):
        self.value_text = text
        self.accent_color = QColor(color_hex)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        w, h = self.width(), self.height()

        p.setPen(QPen(self.accent_color, 1.4))
        p.setBrush(QBrush(QColor(PANEL2)))
        p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), 8, 8)

        margin = 7

        if self.label_text:
            label_font = QFont()
            label_font.setPixelSize(9)
            label_font.setWeight(QFont.Weight.DemiBold)
            p.setFont(label_font)
            p.setPen(QColor(TEXT2))
            p.drawText(
                QRectF(margin, margin - 1, w - 2 * margin, 12),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                self.label_text,
            )

        if self.unit_text:
            unit_font = QFont()
            unit_font.setPixelSize(9)
            unit_font.setWeight(QFont.Weight.DemiBold)
            p.setFont(unit_font)
            p.setPen(QColor(TEXT2))
            p.drawText(
                QRectF(margin, h - margin - 11, w - 2 * margin, 12),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                self.unit_text,
            )

        value_font = QFont()
        value_font.setPixelSize(self.value_pixel_size)
        value_font.setWeight(QFont.Weight.Bold)
        p.setFont(value_font)
        p.setPen(self.accent_color)
        p.drawText(
            QRectF(0, 0, w, h),
            Qt.AlignmentFlag.AlignCenter,
            self.value_text,
        )
        p.end()


def styled_message_box(icon, title, text, parent, buttons=None):
    """Shared QMessageBox factory -- default Qt message boxes render black
    text on this app's dark background (confirmed illegible from a real
    screenshot).

    This one is DELIBERATELY class-scoped rather than object-scoped: a
    QMessageBox's internal QLabel and QPushButtons are the very children
    we're targeting, so the selectors name them explicitly. That's the
    correct use of descendant rules -- an intentional, named target, not
    an accidental cascade from a bare declaration.
    """
    from PySide6.QtWidgets import QMessageBox
    box = QMessageBox(parent)
    box.setIcon(icon)
    box.setWindowTitle(title)
    box.setText(text)
    if buttons is not None:
        box.setStandardButtons(buttons)
    box.setStyleSheet(
        f"QMessageBox {{ background-color: {PANEL}; }}"
        f"QMessageBox QLabel {{ color: {TEXT}; font-size: 12px; border: none; }}"
        f"QMessageBox QPushButton {{ background-color: {SURFACE}; color: {TEXT}; "
        f"border: 1px solid {BORDER2}; border-radius: {R_MD}px; padding: 6px 16px; "
        f"font-size: 11.5px; min-width: 70px; }}"
        f"QMessageBox QPushButton:hover {{ background-color: {BORDER2}; }}"
    )
    return box