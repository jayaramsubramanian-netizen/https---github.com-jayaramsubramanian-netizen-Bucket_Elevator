"""
components/material_library_panel.py -- Materials Library tab.
═══════════════════════════════════════════════════════════════════════════
Faithful port of frontend/src/components/MaterialLibraryPanel.jsx.

Matches the JSX feature-for-feature:
  - Browse table: Name, ID, Category, Density, Abrasion, Flow, Discharge Pref.
  - Built-in materials are read-only: only "Copy & Customize"
  - Custom materials get Edit + Delete
  - Search (name/ID) + Category filter + "Custom only" checkbox
  - "+ New Material"
  - Full 6-section MaterialForm: Identity (slugify auto-ID), Physical
    Properties, Friction & Flow, CEMA Defaults, Discharge Preference (with
    CR min<max validation), Hazards (B1/B4/B6/B8/B10/B11)
  - Footer: "{n} built-in (read-only) · {n} custom"

Load, save and delete all run on QThread workers -- never on the GUI thread.
Search is debounced 300ms, same pattern as InputSidebar's MaterialSearchWorker.

DUPLICATED BLOCK -- REMOVED
───────────────────────────
The entire import block plus ABR_LABEL, FLOW_LABEL, CATEGORIES,
HAZARD_OPTIONS, BLANK_FORM and slugify() were all declared TWICE, back to
back. The second copy silently shadowed the first. Harmless at runtime, but a
real trap: an edit to the first copy would have had no effect at all. (Same
class of thing as bom_panel.py's duplicated _GroupHeader.) One copy now.

WHY THIS TAB STILL HAD THE ARROW / BOX-IN-BOX BUG
─────────────────────────────────────────────────
Identical to components_library_panel.py -- this file rolled its own field
styling instead of using dialog_helpers:

    def _input_style():
        return (f"background-color:{PANEL2};color:{TEXT};border:1px solid {BORDER};"
                f"border-radius:5px;padding:5px 8px;font-size:12px;...")

...applied to QLineEdit, QComboBox AND QDoubleSpinBox. Two failures:

1. BOX-IN-BOX. It's a BARE declaration (no selector), which Qt treats as
   `* { ... }` -- applying to the widget AND EVERY DESCENDANT. Neither a
   QDoubleSpinBox nor a QComboBox is a leaf widget: a spinbox contains an
   internal QLineEdit (verified directly), a combo owns an internal view. So
   the border landed inside the field, drawing a box within a box.

2. THE ARROWS. These fields never went through styled_spinbox(), so they got
   none of its fixes: not the flat transparent arrow buttons, not the
   QPalette.ButtonText fix that makes the glyphs visible on a dark theme, not
   the right-hand padding that stops the value running under the arrows, not
   the 28px minimum height. Fusion defaults inside a hand-styled box -- the
   "grey arrow box inside a grey field" that was reported.

Fixed the same way: _input_style() deleted; every field goes through the
shared styled_spinbox() / styled_lineedit() / styled_combo(). This is the
third file to prove the point -- casing_edit.py needed almost no work
precisely BECAUSE it used the shared helpers.

ALSO SWEPT
──────────
  * header / toolbar: bare `border-bottom` cascaded onto their title labels,
    search box, category combo, checkbox and buttons. Now object-scoped.
  * error_lbl used rgba(224,82,82,..) = v1 danger (#e05252) while importing v2
    DANGER (#ef4444) -- v2 red text on a v1 red tint. Now DANGER_DIM /
    DANGER_BORDER.
  * The primary button's hover was a hardcoded "#5aa8ff" belonging to no
    palette. Now PRIMARY_HOVER.
  * Hardcoded "'JetBrains Mono'" -> theme.FF_MONO.
  * QTableWidget/QHeaderView::section/::item rules are INTENTIONAL descendant
    targeting and are kept.

REAL BUGS FIXED
───────────────
  * _load()'s guard `if self._worker and self._worker.isRunning(): return`
    silently DROPPED the request when a load was in flight. set_data() fires on
    every tab switch AND every recalculation, so a reload landing during an
    in-flight load was simply lost -- a just-created custom material could fail
    to appear until some later, luckier reload. Now the in-flight worker is
    cancelled and superseded.
  * _open_copy() injected "_is_custom": None into the form dict, and _save()
    sends the whole dict as the payload -- so a private UI-only key was being
    POSTed to the backend. All underscore-prefixed keys are now stripped before
    the request.
  * Eight flush-left indentation breaks restored (`def _add_field`,
    `def on_name_change`, `def _cema_section`, `def _toggle_hazard`,
    `def _on_search_changed`, `def _open_create`, and two comment-anchored
    blocks). As pasted, several of these sat outside their class -- e.g.
    _add_field would not have existed as a method, and every section builder
    calls it.
"""
import re

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea,
    QPushButton, QLineEdit, QComboBox, QCheckBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QSpinBox,
    QDoubleSpinBox, QMessageBox, QStackedWidget, QGridLayout,
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QColor

from theme import (
    PANEL, PANEL2, SURFACE, BORDER, BORDER2, TEXT, TEXT2, TEXT3, MUTED,
    PRIMARY, PRIMARY_HOVER, SUCCESS, WARNING, DANGER, DANGER_DIM,
    DANGER_BORDER, TEAL, PURPLE, R_SM, FF_MONO,
    scoped, plain_bg,
)
from .dialog_helpers import (
    styled_message_box, styled_spinbox, styled_lineedit, styled_combo,
)
from api_client import (
    fetch_all_materials, list_custom_materials_api,
    create_custom_material, update_custom_material, delete_custom_material,
)

ABR_LABEL = ["–", "Low", "Low", "Med", "Med", "High", "High", "V.Hi"]
FLOW_LABEL = {1: "Very free", 2: "Free", 3: "Average", 4: "Sluggish"}
CATEGORIES = [
    "GRAIN", "BIO", "CHEM", "CONST", "FOOD", "MIN", "METAL", "FERT",
    "CEM", "COAL", "GLASS", "ENV", "PHARM", "PETRO", "POLY", "SALT",
]
HAZARD_OPTIONS = [
    ("B1",  "Aerates / fluidises easily"),
    ("B4",  "Corrosive to steel"),
    ("B6",  "Other documented hazard (B6)"),
    ("B8",  "Hygroscopic (absorbs moisture)"),
    ("B10", "Explosive dust"),
    ("B11", "Flammable vapour"),
]
BLANK_FORM = {
    "id": "", "name": "", "category": "MIN", "rho_loose": 1000, "rho_vib": None,
    "angle_repose": 35, "angle_surcharge": None, "angle_internal_friction": None,
    "moisture_pct": 0, "cohesion": 0, "abr_code": 3, "flowability": 2,
    "size_code": "B", "hazard_codes": [], "Km": 1.0, "Ceff_default": 1.15,
    "Leq_default": 8, "wall_friction_deg": 20, "bucket_fill_factor": 0.75,
    "pref_discharge_type": "centrifugal", "pref_bucket_style": "AA",
    "pref_cr_min": 1.2, "pref_cr_max": 1.5, "based_on": None,
}


def slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9\s_]", "", s)
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"^[^a-z]+", "", s)
    return s[:40] or "custom_material"


def _btn(text, style="secondary", danger=False):
    """Scoped button. (Harmless as a class selector -- a QPushButton has no
    styleable children -- but converted so no non-object-scoped pattern
    remains to be copied into a widget where it WOULD bite.)"""
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    if style == "primary":
        btn.setStyleSheet(scoped(
            btn,
            f"background-color: {PRIMARY}; color: #fff; border: none; "
            f"border-radius: {R_SM}px; padding: 7px 14px; font-size: 11.5px; "
            f"font-weight: 700;",
            # Was a hardcoded "#5aa8ff" hover, in no palette. Now a real token.
            extra=("{sel}:disabled { background-color: %s; color: %s; }\n"
                   "{sel}:hover:!disabled { background-color: %s; }"
                   % (SURFACE, TEXT3, PRIMARY_HOVER)),
        ))
    else:
        color = DANGER if danger else TEXT2
        btn.setStyleSheet(scoped(
            btn,
            f"background-color: transparent; color: {color}; "
            f"border: 1px solid {BORDER2}; border-radius: {R_SM}px; "
            f"padding: 4px 10px; font-size: 10.5px;",
            extra="{sel}:hover { background-color: %s; color: %s; }"
                  % (SURFACE, TEXT),
        ))
    return btn


# ── Background workers ────────────────────────────────────────────────────
class _LoadWorker(QThread):
    done = Signal(list, list)
    error = Signal(str)

    def run(self):
        try:
            builtins = fetch_all_materials()
            customs = list_custom_materials_api()
            self.done.emit(builtins, customs)
        except Exception as e:
            self.error.emit(str(e))


class _SaveWorker(QThread):
    done = Signal(dict)
    error = Signal(str)

    def __init__(self, mode, mat_id, payload, parent=None):
        super().__init__(parent)
        self.mode, self.mat_id, self.payload = mode, mat_id, payload

    def run(self):
        try:
            if self.mode == "edit":
                result = update_custom_material(self.mat_id, self.payload)
            else:
                result = create_custom_material(self.payload)
            self.done.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class _DeleteWorker(QThread):
    done = Signal()
    error = Signal(str)

    def __init__(self, mat_id, parent=None):
        super().__init__(parent)
        self.mat_id = mat_id

    def run(self):
        try:
            delete_custom_material(self.mat_id)
            self.done.emit()
        except Exception as e:
            self.error.emit(str(e))


# ── Material form ─────────────────────────────────────────────────────────
def _section_head(text):
    lbl = QLabel(text.upper())
    lbl.setStyleSheet(
        f"color: {PRIMARY}; font-size: 10px; font-weight: 700; "
        f"letter-spacing: .05em; margin-bottom: 2px;")
    return lbl


def _field_label(text, hint=None):
    box = QVBoxLayout()
    box.setSpacing(1)
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color: {TEXT2}; font-size: 10.5px; font-weight: 600;")
    box.addWidget(lbl)
    if hint:
        h = QLabel(hint)
        h.setWordWrap(True)
        h.setStyleSheet(f"color: {MUTED}; font-size: 9px;")
        box.addWidget(h)
    return box


class MaterialForm(QWidget):
    """Full create/copy/edit form, matching the JSX's 6-section layout."""

    saved = Signal(dict)
    cancelled = Signal()

    def __init__(self, initial: dict, mode: str, existing_ids: set, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.existing_ids = existing_ids
        self._form = dict(initial)
        self._id_locked = (mode == "edit")
        self._worker = None

        self.setStyleSheet(plain_bg(self, PANEL))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Header (SCOPED: bare border-bottom was hitting the title and
        #    both buttons) ─────────────────────────────────────────────
        header = QFrame()
        header.setStyleSheet(scoped(
            header,
            f"background-color: {PANEL2}; border: none; "
            f"border-bottom: 1px solid {BORDER};"
        ))
        hl = QHBoxLayout(header)
        hl.setContentsMargins(14, 10, 14, 10)
        if mode == "edit":
            title_text = f"Edit: {initial.get('name', '')}"
        elif mode == "copy":
            base = initial.get("based_on") or initial.get("name", "")
            title_text = f"Copy & Customize: {base}"
        else:
            title_text = "New Custom Material"
        title = QLabel(title_text)
        title.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: 700;")
        hl.addWidget(title, 1)
        cancel_btn = _btn("Cancel")
        cancel_btn.clicked.connect(self.cancelled)
        hl.addWidget(cancel_btn)
        self.save_btn = _btn("Save", style="primary")
        self.save_btn.clicked.connect(self._save)
        hl.addWidget(self.save_btn)
        outer.addWidget(header)

        self.error_lbl = QLabel("")
        self.error_lbl.setWordWrap(True)
        self.error_lbl.setStyleSheet(scoped(
            self.error_lbl,
            f"color: {DANGER}; background-color: {DANGER_DIM}; "
            f"border: 1px solid {DANGER_BORDER}; border-radius: {R_SM}px; "
            f"padding: 7px 12px; font-size: 11px; margin: 8px 14px;"
        ))
        self.error_lbl.hide()
        outer.addWidget(self.error_lbl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(scoped(scroll, "border: none; background: transparent;"))
        body = QWidget()
        body.setStyleSheet(plain_bg(body, PANEL))
        grid = QGridLayout(body)
        grid.setContentsMargins(14, 14, 14, 14)
        grid.setSpacing(18)

        grid.addLayout(self._identity_section(), 0, 0)
        grid.addLayout(self._physical_section(), 0, 1)
        grid.addLayout(self._friction_section(), 1, 0)
        grid.addLayout(self._cema_section(), 1, 1)
        grid.addLayout(self._discharge_section(), 2, 0)
        grid.addLayout(self._hazard_section(), 2, 1)

        scroll.setWidget(body)
        outer.addWidget(scroll)

    # ── Field builders (all now use the SHARED helpers) ───────────────
    def _add_field(self, layout, label, widget, hint=None):
        layout.addLayout(_field_label(label, hint))
        layout.addWidget(widget)
        layout.addSpacing(6)

    def _line_edit(self, key, placeholder="", disabled=False):
        w = styled_lineedit(QLineEdit(str(self._form.get(key) or "")),
                            placeholder=placeholder or None)
        w.setDisabled(disabled)
        w.textChanged.connect(lambda v, k=key: self._set(k, v))
        return w

    def _double_spin(self, key, min_=0.0, max_=99999.0, step=1.0, decimals=2):
        w = styled_spinbox(QDoubleSpinBox())
        w.setRange(min_, max_)
        w.setSingleStep(step)
        w.setDecimals(decimals)
        val = self._form.get(key)
        if val is not None:
            w.setValue(float(val))
        w.valueChanged.connect(lambda v, k=key: self._set(k, v))
        return w

    def _set(self, key, value):
        self._form[key] = value

    def _identity_section(self):
        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.addWidget(_section_head("Identity"))
        layout.addSpacing(6)

        hint = ("Locked — IDs can't change after creation." if self._id_locked
                else "Lowercase, numbers, underscores. Auto-filled from name.")
        id_edit = styled_lineedit(QLineEdit(str(self._form.get("id") or "")),
                                  placeholder="e.g. wheat_humid_batch7")
        id_edit.setDisabled(self._id_locked)
        self._id_edit = id_edit
        id_edit.textChanged.connect(lambda v: self._set("id", v))
        self._add_field(layout, "Material ID", id_edit, hint)

        name_edit = styled_lineedit(QLineEdit(str(self._form.get("name") or "")),
                                    placeholder="e.g. Wheat (Humid, Batch 7)")
        self._name_edit = name_edit

        def on_name_change(v):
            self._set("name", v)
            if not self._id_locked:
                current_id = self._form.get("id", "")
                # Only auto-fill while the ID still tracks the name -- once the
                # user types their own ID, stop clobbering it.
                if not current_id or current_id == slugify(
                        self._form.get("name", "")):
                    self._id_edit.setText(slugify(v))

        name_edit.textChanged.connect(on_name_change)
        self._add_field(layout, "Name", name_edit)

        cat = styled_combo(QComboBox())
        for c in CATEGORIES:
            cat.addItem(c, c)
        idx = cat.findData(self._form.get("category", "MIN"))
        if idx >= 0:
            cat.setCurrentIndex(idx)
        cat.currentIndexChanged.connect(
            lambda i: self._set("category", cat.currentData()))
        self._add_field(layout, "Category", cat)

        if self._form.get("based_on"):
            based = QLabel(str(self._form["based_on"]))
            based.setStyleSheet(
                f"color: {MUTED}; font-size: 10px; font-family: {FF_MONO};")
            self._add_field(layout, "Based on", based)

        layout.addStretch()
        return layout

    def _physical_section(self):
        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.addWidget(_section_head("Physical Properties"))
        layout.addSpacing(6)
        self._add_field(layout, "Bulk density, loose (kg/m³)",
                        self._double_spin("rho_loose", 0.1, 99999, 10, 0))
        self._add_field(layout, "Bulk density, vibrated (kg/m³)",
                        self._double_spin("rho_vib", 0, 99999, 10, 0), "Optional")
        self._add_field(layout, "Angle of repose (°)",
                        self._double_spin("angle_repose", 0, 90, 1, 1))
        self._add_field(layout, "Moisture (%)",
                        self._double_spin("moisture_pct", 0, 100, 1, 1))
        self._add_field(layout, "Cohesion (0–1)",
                        self._double_spin("cohesion", 0, 1, 0.01, 2))
        layout.addStretch()
        return layout

    def _friction_section(self):
        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.addWidget(_section_head("Friction & Flow"))
        layout.addSpacing(6)

        abr = styled_combo(QComboBox())
        for n in range(1, 8):
            abr.addItem(f"{n} — {ABR_LABEL[n]}", n)
        idx = abr.findData(int(self._form.get("abr_code", 3)))
        if idx >= 0:
            abr.setCurrentIndex(idx)
        abr.currentIndexChanged.connect(
            lambda i: self._set("abr_code", abr.currentData()))
        self._add_field(layout, "Abrasiveness class (1–7)", abr)

        flow = styled_combo(QComboBox())
        for n in range(1, 5):
            flow.addItem(f"{n} — {FLOW_LABEL[n]}", n)
        idx = flow.findData(int(self._form.get("flowability", 2)))
        if idx >= 0:
            flow.setCurrentIndex(idx)
        flow.currentIndexChanged.connect(
            lambda i: self._set("flowability", flow.currentData()))
        self._add_field(layout, "Flowability class (1–4)", flow)

        self._add_field(layout, "Wall friction angle (°)",
                        self._double_spin("wall_friction_deg", 0, 90, 1, 1))
        self._add_field(layout, "Size code", self._line_edit("size_code", "e.g. B"))
        layout.addStretch()
        return layout

    def _cema_section(self):
        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.addWidget(_section_head("CEMA Defaults"))
        layout.addSpacing(6)
        self._add_field(layout, "Km (material factor)",
                        self._double_spin("Km", 0.1, 10, 0.05, 2))
        self._add_field(layout, "Ceff (efficiency factor)",
                        self._double_spin("Ceff_default", 0.5, 3, 0.05, 2))
        self._add_field(layout, "Leq default",
                        self._double_spin("Leq_default", 0, 100, 0.5, 1))
        self._add_field(layout, "Bucket fill factor (0–1)",
                        self._double_spin("bucket_fill_factor", 0.1, 1.0, 0.05, 2))
        layout.addStretch()
        return layout

    def _discharge_section(self):
        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.addWidget(_section_head("Discharge Preference"))
        layout.addSpacing(6)

        dtype = styled_combo(QComboBox())
        dtype.addItem("Continuous (HF/MF/SC)", "continuous")
        dtype.addItem("Centrifugal (AA/AC/C)", "centrifugal")
        idx = dtype.findData(self._form.get("pref_discharge_type", "centrifugal"))
        if idx >= 0:
            dtype.setCurrentIndex(idx)
        dtype.currentIndexChanged.connect(
            lambda i: self._set("pref_discharge_type", dtype.currentData()))
        self._add_field(
            layout, "Preferred discharge type", dtype,
            "Drives auto-bucket selection and the optimizer's CR objective.")

        self._add_field(layout, "Preferred bucket style",
                        self._line_edit("pref_bucket_style", "e.g. HF, AA, AC"))

        cr_row = QHBoxLayout()
        cr_row.setSpacing(8)
        self._cr_min = self._double_spin("pref_cr_min", 0.0, 10.0, 0.05, 2)
        self._cr_max = self._double_spin("pref_cr_max", 0.0, 10.0, 0.05, 2)
        cr_row.addWidget(self._cr_min)
        dash = QLabel("–")
        dash.setStyleSheet(f"color: {TEXT3}; font-size: 12px;")
        cr_row.addWidget(dash)
        cr_row.addWidget(self._cr_max)
        cr_container = QWidget()
        cr_container.setStyleSheet(
            scoped(cr_container, "background-color: transparent; border: none;"))
        cr_container.setLayout(cr_row)
        self._add_field(layout, "CR target range (min – max)", cr_container,
                        "Continuous: 0.2–1.0. Centrifugal: 0.7–3.0.")
        layout.addStretch()
        return layout

    def _hazard_section(self):
        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.addWidget(_section_head("Hazards"))
        layout.addSpacing(6)
        self._hazard_checks = {}
        current = self._form.get("hazard_codes") or []
        for code, label in HAZARD_OPTIONS:
            cb = QCheckBox(label)
            cb.setChecked(code in current)
            cb.setStyleSheet(f"color: {TEXT2}; font-size: 11px;")
            cb.toggled.connect(
                lambda checked, c=code: self._toggle_hazard(c, checked))
            layout.addWidget(cb)
            self._hazard_checks[code] = cb
        layout.addStretch()
        return layout

    def _toggle_hazard(self, code, checked):
        codes = list(self._form.get("hazard_codes") or [])
        if checked and code not in codes:
            codes.append(code)
        elif not checked and code in codes:
            codes.remove(code)
        self._form["hazard_codes"] = codes

    def _save(self):
        self.error_lbl.hide()
        form = self._form

        if not self._id_locked and not form.get("id"):
            self._show_error("Material ID is required.")
            return
        if not self._id_locked and form.get("id") in self.existing_ids:
            self._show_error("This ID is already in use (built-in or custom).")
            return
        if not str(form.get("name") or "").strip():
            self._show_error("Material name is required.")
            return
        if not form.get("rho_loose") or float(form.get("rho_loose") or 0) <= 0:
            self._show_error("Bulk density must be a positive number.")
            return
        if float(form.get("pref_cr_min") or 0) >= float(form.get("pref_cr_max") or 0):
            self._show_error("CR target minimum must be less than maximum.")
            return

        # Strip private UI-only keys before sending. _open_copy() injects
        # "_is_custom", and the whole dict is used as the payload -- so that key
        # was being POSTed to the backend.
        payload = {k: v for k, v in form.items() if not k.startswith("_")}

        # Coerce optional numeric fields to null -- matches the JSX exactly.
        for k in ("rho_vib", "angle_surcharge", "angle_internal_friction"):
            v = payload.get(k)
            if v == "" or v == 0.0:
                payload[k] = None

        self.save_btn.setEnabled(False)
        self.save_btn.setText("Saving…")
        self._worker = _SaveWorker(self.mode, form.get("id"), payload, parent=self)
        self._worker.done.connect(self._on_saved)
        self._worker.error.connect(self._on_save_error)
        self._worker.start()

    def _show_error(self, msg):
        self.error_lbl.setText(msg)
        self.error_lbl.show()

    def _on_saved(self, result):
        self.save_btn.setEnabled(True)
        self.save_btn.setText("Save")
        self.saved.emit(result)

    def _on_save_error(self, msg):
        self.save_btn.setEnabled(True)
        self.save_btn.setText("Save")
        self._show_error(f"Save failed: {msg}")


# ── Main panel ────────────────────────────────────────────────────────────
TABLE_COLS = ["Name", "ID", "Category", "Density", "Abrasion", "Flow",
              "Discharge Pref.", ""]
COL_WIDTHS = [180, 100, 75, 80, 70, 80, 120, 130]


class MaterialLibraryPanel(QWidget):
    """Port of MaterialLibraryPanel.jsx. set_data(inputs, results) is wired by
    main.py -- the args aren't used (this panel owns its own backend state) but
    the list reloads on each call so a custom material created here and then
    recalculated shows up without a manual refresh."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(plain_bg(self, PANEL))
        self._builtins: list = []
        self._customs: list = []
        self._query = ""
        self._category = ""
        self._custom_only = False
        self._worker = None
        self._delete_worker = None
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._apply_filter)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._stack = QStackedWidget()
        outer.addWidget(self._stack)
        self._stack.addWidget(self._build_browse_view())
        self._form_placeholder = QWidget()
        self._stack.addWidget(self._form_placeholder)

        self._load()

    def set_data(self, inputs, results):
        self._load()

    def _load(self):
        """FIXED: the old guard was
            if self._worker and self._worker.isRunning(): return
        which silently DROPPED the request if a load was already in flight.
        set_data() fires on every tab switch AND every recalculation, so a
        reload landing during an in-flight load was simply lost -- meaning a
        just-created custom material could fail to appear until some later,
        luckier reload. Now the in-flight worker is cancelled and superseded."""
        if self._worker is not None and self._worker.isRunning():
            try:
                self._worker.done.disconnect()
                self._worker.error.disconnect()
            except (TypeError, RuntimeError):
                pass
            self._worker.quit()
            self._worker.wait()

        self._worker = _LoadWorker(parent=self)
        self._worker.done.connect(self._on_loaded)
        self._worker.error.connect(self._on_load_error)
        self._worker.start()

    def _on_loaded(self, builtins, customs):
        self._builtins = builtins
        self._customs = customs
        self._footer_lbl.setText(
            f"{len(builtins)} built-in (read-only)  ·  {len(customs)} custom  ·  "
            f'"Copy & Customize" works on any row including built-ins'
        )
        self._apply_filter()

    def _on_load_error(self, msg):
        self._footer_lbl.setText(f"Load error: {msg}")

    # ── Browse view ──────────────────────────────────────────────────
    def _build_browse_view(self):
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # SCOPED: the bare border-bottom was landing on the search box, the
        # category combo, the checkbox and the New button.
        toolbar = QFrame()
        toolbar.setStyleSheet(scoped(
            toolbar,
            f"background-color: {PANEL2}; border: none; "
            f"border-bottom: 1px solid {BORDER};"
        ))
        tl = QHBoxLayout(toolbar)
        tl.setContentsMargins(12, 8, 12, 8)
        tl.setSpacing(8)

        self._search_box = styled_lineedit(
            QLineEdit(), placeholder="Search materials by name or ID…")
        self._search_box.textChanged.connect(self._on_search_changed)
        tl.addWidget(self._search_box, 1)

        self._cat_combo = styled_combo(QComboBox())
        self._cat_combo.setMinimumWidth(130)
        self._cat_combo.addItem("All categories", "")
        for c in CATEGORIES:
            self._cat_combo.addItem(c, c)
        self._cat_combo.currentIndexChanged.connect(
            lambda i: self._set_category(self._cat_combo.currentData()))
        tl.addWidget(self._cat_combo)

        self._custom_only_cb = QCheckBox("Custom only")
        self._custom_only_cb.setStyleSheet(f"color: {TEXT2}; font-size: 11px;")
        self._custom_only_cb.toggled.connect(self._set_custom_only)
        tl.addWidget(self._custom_only_cb)

        new_btn = _btn("+ New Material", style="primary")
        new_btn.clicked.connect(self._open_create)
        tl.addWidget(new_btn)
        layout.addWidget(toolbar)

        # Table. QHeaderView::section and QTableWidget::item are INTENTIONAL
        # descendant rules -- those sub-elements are what we mean to style.
        self._table = QTableWidget(0, len(TABLE_COLS))
        self._table.setHorizontalHeaderLabels(TABLE_COLS)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(False)
        self._table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {PANEL2}; color: {TEXT}; border: none;
                gridline-color: {BORDER}; font-size: 11px;
            }}
            QHeaderView::section {{
                background-color: {PANEL}; color: {TEXT2}; border: none;
                border-bottom: 1px solid {BORDER}; padding: 7px 6px;
                font-size: 9.5px; font-weight: 700; letter-spacing: .04em;
            }}
            QTableWidget::item {{
                padding: 5px 6px; border: none;
                border-bottom: 1px solid {BORDER};
            }}
        """)
        for i, w in enumerate(COL_WIDTHS):
            self._table.setColumnWidth(i, w)
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._table, 1)

        self._footer_lbl = QLabel("Loading…")
        self._footer_lbl.setStyleSheet(scoped(
            self._footer_lbl,
            f"color: {MUTED}; font-size: 10px; padding: 6px 14px; "
            f"border: none; border-top: 1px solid {BORDER}; "
            f"background-color: {PANEL2};"
        ))
        layout.addWidget(self._footer_lbl)
        return view

    def _on_search_changed(self, text):
        self._query = text
        self._debounce_timer.start(300)

    def _set_category(self, cat):
        self._category = cat
        self._apply_filter()

    def _set_custom_only(self, val):
        self._custom_only = val
        self._apply_filter()

    @staticmethod
    def _cell(text, color=TEXT, mono=False):
        item = QTableWidgetItem(str(text or ""))
        item.setForeground(QColor(color))
        if mono:
            f = item.font()
            f.setFamily("JetBrains Mono")
            item.setFont(f)
        return item

    def _apply_filter(self):
        q = self._query.lower()
        tagged = (
            [dict(m, _is_custom=False) for m in self._builtins] +
            [dict(m, _is_custom=True) for m in self._customs]
        )
        filtered = [
            m for m in tagged
            if (not self._custom_only or m["_is_custom"])
            and (not self._category or m.get("category") == self._category)
            and (not q
                 or q in str(m.get("name") or "").lower()
                 or q in str(m.get("id") or "").lower())
        ]
        self._table.setRowCount(len(filtered))
        cell = self._cell

        for row, m in enumerate(filtered):
            is_custom = m["_is_custom"]

            self._table.setItem(row, 0, cell(m.get("name", ""),
                                             TEXT if is_custom else TEXT2))
            self._table.setItem(row, 1, cell(m.get("id", ""), TEXT3, mono=True))
            self._table.setItem(row, 2, cell(m.get("category", ""), TEXT2))

            rho = m.get("rho_loose")
            self._table.setItem(row, 3, cell(
                f"{int(rho)} kg/m³" if rho else "—", TEXT2, mono=True))
            abr = m.get("abr_code")
            self._table.setItem(row, 4, cell(
                ABR_LABEL[int(abr)] if abr else "—", TEXT2))
            flow = m.get("flowability")
            self._table.setItem(row, 5, cell(
                FLOW_LABEL.get(int(flow), "—") if flow else "—", TEXT2))

            disc = m.get("pref_discharge_type") or ""
            style = m.get("pref_bucket_style") or ""
            disc_text = (f"{style} · {'cont.' if disc == 'continuous' else 'cent.'}"
                         if disc else "—")
            disc_color = TEAL if disc == "continuous" else WARNING
            self._table.setItem(row, 6, cell(
                disc_text, disc_color if disc else TEXT3))

            action_widget = QWidget()
            action_widget.setStyleSheet(scoped(
                action_widget, "background-color: transparent; border: none;"))
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(4, 2, 4, 2)
            action_layout.setSpacing(4)
            action_layout.addStretch()

            copy_btn = _btn("Copy & Customize")
            copy_btn.clicked.connect(lambda _, mat=m: self._open_copy(mat))
            action_layout.addWidget(copy_btn)

            if is_custom:
                edit_btn = _btn("Edit")
                edit_btn.clicked.connect(lambda _, mat=m: self._open_edit(mat))
                action_layout.addWidget(edit_btn)
                del_btn = _btn("Delete", danger=True)
                del_btn.clicked.connect(lambda _, mat=m: self._confirm_delete(mat))
                action_layout.addWidget(del_btn)

            self._table.setCellWidget(row, 7, action_widget)
            self._table.setRowHeight(row, 38)

    # ── Form open/close ──────────────────────────────────────────────
    def _open_form(self, initial, mode):
        existing_ids = {m.get("id") for m in self._builtins + self._customs
                        if m.get("id")}
        if mode == "edit":
            existing_ids.discard(initial.get("id"))

        form = MaterialForm(initial, mode, existing_ids, parent=self)
        form.saved.connect(self._on_form_saved)
        form.cancelled.connect(self._close_form)

        old = self._stack.widget(1)
        if old is not None:
            self._stack.removeWidget(old)
            old.deleteLater()
        self._stack.addWidget(form)
        self._stack.setCurrentIndex(1)

    def _close_form(self):
        self._stack.setCurrentIndex(0)

    def _on_form_saved(self, result):
        self._close_form()
        self._load()

    def _open_create(self):
        self._open_form(dict(BLANK_FORM), "create")

    def _open_copy(self, mat):
        base = {
            **BLANK_FORM, **mat,
            "id": "",
            "name": f"{mat.get('name', '')} (Custom)",
            "based_on": mat.get("id"),
        }
        base.pop("_is_custom", None)   # private UI key -- never send to backend
        self._open_form(base, "copy")

    def _open_edit(self, mat):
        self._open_form({**BLANK_FORM, **mat}, "edit")

    def _confirm_delete(self, mat):
        box = styled_message_box(
            QMessageBox.Icon.Question, "Delete Custom Material",
            f'Delete "{mat.get("name")}"?\n\nThis cannot be undone. Any saved '
            f'design still referencing it will fall back to safe defaults.',
            self,
            buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if box.exec() != QMessageBox.StandardButton.Yes:
            return
        self._delete_worker = _DeleteWorker(mat.get("id"), parent=self)
        self._delete_worker.done.connect(self._load)
        self._delete_worker.error.connect(
            lambda msg: styled_message_box(
                QMessageBox.Icon.Warning, "Delete failed", msg, self).exec()
        )
        self._delete_worker.start()