"""
components/components_library_panel.py -- VECTOMEC™ Components Library
═══════════════════════════════════════════════════════════════════════════
Browse, search, and manage custom components across 8 types:
    Belts · Chains · Buckets · Motors · Gearboxes · VFDs · Liners · Couplings

Architecture mirrors material_library_panel.py:
  - Type tab bar (switching between component types)
  - Browse table with Search + "New Component" button
  - Dynamic form built from the backend schema endpoint (so field definitions
    live in one place: custom_components.py, not duplicated here)
  - All network calls on background QThread workers
  - "Copy & Customize" available on every row

Part description is the unique identifier (part numbers assigned later).

THIS FILE IS WHY THE LIBRARY TABS STILL HAD THE ARROW / BOX-IN-BOX BUG
──────────────────────────────────────────────────────────────────────
It did NOT use dialog_helpers' shared field widgets. It rolled its own:

    def _input_style():
        return (f"background:{PANEL2};color:{TEXT};border:1px solid {BORDER};"
                f"border-radius:5px;padding:5px 8px;font-size:12px;")

...and applied that same string to QLineEdit, QTextEdit, QSpinBox AND
QDoubleSpinBox. Two separate failures follow from that:

1. BOX-IN-BOX. It's a BARE declaration (no selector), which Qt treats as
   `* { ... }` -- applying to the widget AND EVERY DESCENDANT. A QSpinBox is
   not a leaf widget: it contains an internal QLineEdit. So the border landed
   on that inner line edit too, drawing a box INSIDE the field. Same for
   QTextEdit, which has a viewport child.

2. THE ARROWS. Because these fields never went through styled_spinbox(), they
   got NONE of its fixes -- not the flat transparent arrow buttons, not the
   QPalette.ButtonText fix that makes the arrow glyphs visible on a dark
   theme, not the right-hand padding that stops the value text running under
   the arrows, not the 28px minimum height. They fell back to Fusion defaults
   inside a hand-styled box, which is exactly the "grey arrow box inside a
   grey field" that was reported.

Both are fixed the same way: delete _input_style() and use the shared
styled_spinbox() / styled_lineedit() / styled_combo() from dialog_helpers --
the same widgets every dialog already uses. This is the shared-helper argument
again: casing_edit.py needed almost no work precisely because it used them.

ALSO SWEPT
──────────
  * hdr / toolbar / tab_bar: bare `border-bottom` -> cascaded onto their title
    labels, search box and buttons. Now object-scoped via theme.scoped().
  * error_lbl used rgba(224,82,82,..) = v1 danger (#e05252) while importing v2
    DANGER (#ef4444) -- a v2 red text on a v1 red tint. Now DANGER_DIM /
    DANGER_BORDER.
  * The active type-tab used rgba(74,158,255,.12) = v1 primary. Now PRIMARY_DIM.
  * QTableWidget/QHeaderView::section/::item rules are INTENTIONAL descendant
    targeting and are kept -- that's the legitimate use of a descendant
    selector, unlike a bare declaration hitting children by accident.

REAL ERRORS FIXED
─────────────────
  * `def _reload` and `def _style_tab_btn` both sat at column 0 -- OUTSIDE
    their classes. _TypeBrowseView would have had no _reload method
    (AttributeError the moment you saved or deleted a component) and
    ComponentsLibraryPanel no _style_tab_btn (AttributeError in __init__, so
    the tab would never have opened at all). Restored as methods, along with
    five other flush-left breaks.
  * _load_type()'s guard `if self._worker and self._worker.isRunning(): return`
    silently DROPS a load request if one is already in flight. Switching type
    twice quickly leaves the second type permanently showing "Loading…", since
    nothing retries. Now the in-flight worker is cancelled and superseded --
    the same pattern MaterialSearchWidget already uses.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea,
    QPushButton, QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QStackedWidget, QGridLayout, QTextEdit, QDoubleSpinBox,
    QSpinBox, QComboBox, QCheckBox, QMessageBox,
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QColor

from theme import (
    PANEL, PANEL2, SURFACE, BORDER, BORDER2, TEXT, TEXT2, TEXT3, MUTED,
    PRIMARY, PRIMARY_DIM, SUCCESS, WARNING, DANGER, DANGER_DIM, DANGER_BORDER,
    R_SM, R_MD,
    scoped, plain_bg,
)
from .dialog_helpers import (
    styled_message_box, styled_spinbox, styled_lineedit, styled_combo,
)
from api_client import (
    fetch_component_types, list_components_api,
    create_component_api, update_component_api, delete_component_api,
)


def _styled_textedit(edit):
    """QTextEdit needs its own scoped rule -- it has a viewport child, so a
    bare declaration would border that too."""
    edit.setStyleSheet(f"""
        QTextEdit {{
            background-color: {SURFACE}; color: {TEXT};
            border: 1px solid {BORDER2}; border-radius: {R_SM}px;
            padding: 5px 8px; font-size: 12px;
        }}
        QTextEdit:focus {{ border: 1px solid {PRIMARY}; }}
    """)
    return edit


def _btn(text, primary=False, danger=False):
    """Scoped button. (A QPushButton has no styleable child widgets, so the
    old class-selector form was harmless here -- converted anyway so no
    non-object-scoped pattern remains to be copied into a widget where it
    WOULD bite. See status_design_leaves.py for one that did.)"""
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    if primary:
        btn.setStyleSheet(scoped(
            btn,
            f"background-color: {PRIMARY}; color: #fff; border: none; "
            f"border-radius: {R_SM}px; padding: 7px 14px; font-size: 11.5px; "
            f"font-weight: 700;",
            extra="{sel}:disabled { background-color: %s; color: %s; }"
                  % (SURFACE, TEXT3),
        ))
    else:
        color = DANGER if danger else TEXT2
        btn.setStyleSheet(scoped(
            btn,
            f"background-color: transparent; color: {color}; "
            f"border: 1px solid {BORDER2}; border-radius: {R_SM}px; "
            f"padding: 4px 10px; font-size: 10.5px;",
            extra="{sel}:hover { background-color: %s; }" % SURFACE,
        ))
    return btn


# ── Background workers ────────────────────────────────────────────────────
class _LoadWorker(QThread):
    done = Signal(list, dict)
    error = Signal(str)

    def __init__(self, component_type, parent=None):
        super().__init__(parent)
        self.component_type = component_type

    def run(self):
        try:
            components = list_components_api(self.component_type)
            try:
                schema_data = fetch_component_types()
            except Exception:
                schema_data = {}
            self.done.emit(components, schema_data)
        except Exception as e:
            self.error.emit(str(e))


class _SaveWorker(QThread):
    done = Signal(dict)
    error = Signal(str)

    def __init__(self, mode, comp_id, component_type, description, specs,
                 notes, parent=None):
        super().__init__(parent)
        self.mode, self.comp_id = mode, comp_id
        self.component_type, self.description = component_type, description
        self.specs, self.notes = specs, notes

    def run(self):
        try:
            if self.mode == "edit":
                result = update_component_api(
                    self.comp_id, self.description, self.specs, self.notes)
            else:
                result = create_component_api(
                    self.component_type, self.description, self.specs, self.notes)
            self.done.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class _DeleteWorker(QThread):
    done = Signal()
    error = Signal(str)

    def __init__(self, comp_id, parent=None):
        super().__init__(parent)
        self.comp_id = comp_id

    def run(self):
        try:
            delete_component_api(self.comp_id)
            self.done.emit()
        except Exception as e:
            self.error.emit(str(e))


# ── Dynamic form ──────────────────────────────────────────────────────────
class ComponentForm(QWidget):
    """Dynamic form built from the backend schema. Field types are inferred
    from the schema's python type name (int/float/str/bool)."""

    saved = Signal(dict)
    cancelled = Signal()

    def __init__(self, component_type: str, initial: dict, mode: str,
                 schema: list, type_label: str, parent=None):
        super().__init__(parent)
        self.component_type = component_type
        self.mode = mode
        self.schema = schema
        self._form_data = dict(initial)
        self._widgets: dict = {}
        self._worker = None
        self.setStyleSheet(plain_bg(self, PANEL))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Header ───────────────────────────────────────────────────
        # SCOPED: the bare border-bottom was landing on the title label and
        # both buttons.
        hdr = QFrame()
        hdr.setStyleSheet(scoped(
            hdr,
            f"background-color: {PANEL2}; border: none; "
            f"border-bottom: 1px solid {BORDER};"
        ))
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(14, 10, 14, 10)
        if mode == "edit":
            title_text = f"Edit: {initial.get('description', '')}"
        elif mode == "copy":
            title_text = f"Copy: {initial.get('description', '')}"
        else:
            singular = type_label[:-1] if type_label.endswith("s") else type_label
            title_text = f"New {singular}"
        title = QLabel(title_text)
        title.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: 700;")
        hl.addWidget(title, 1)
        cancel_btn = _btn("Cancel")
        cancel_btn.clicked.connect(self.cancelled)
        hl.addWidget(cancel_btn)
        self.save_btn = _btn("Save", primary=True)
        self.save_btn.clicked.connect(self._save)
        hl.addWidget(self.save_btn)
        outer.addWidget(hdr)

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

        # ── Form body ────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(scoped(scroll, "border: none; background: transparent;"))
        body = QWidget()
        body.setStyleSheet(plain_bg(body, PANEL))
        grid = QGridLayout(body)
        grid.setContentsMargins(14, 14, 14, 14)
        grid.setSpacing(12)

        # Description (always first)
        desc_lbl = QLabel("Description *")
        desc_lbl.setStyleSheet(f"color: {TEXT2}; font-size: 10.5px; font-weight: 600;")
        self.desc_edit = styled_lineedit(
            QLineEdit(str(initial.get("description") or "")),
            placeholder="Unique identifier for this component",
        )
        self.desc_edit.setDisabled(mode == "edit")
        grid.addWidget(desc_lbl, 0, 0)
        grid.addWidget(self.desc_edit, 0, 1)

        # Dynamic fields from schema. All three widget types now go through the
        # SHARED helpers -- so they pick up the spinbox arrow fix, the
        # ButtonText palette fix, the minimum height and the scoped borders,
        # exactly like every dialog field does.
        for row_idx, field_def in enumerate(schema, start=1):
            fname = field_def["field"]
            ftype_name = field_def["type"]
            default = field_def["default"]
            label = field_def["label"]
            hint = field_def["hint"]

            current_val = (initial.get("specs") or {}).get(fname, default)
            lbl = QLabel(f"{label}{' (' + hint + ')' if hint else ''}")
            lbl.setStyleSheet(f"color: {TEXT2}; font-size: 10.5px;")
            lbl.setWordWrap(True)

            if ftype_name == "float":
                w = styled_spinbox(QDoubleSpinBox())
                w.setRange(-999999, 999999)
                w.setDecimals(3)
                w.setValue(float(current_val or 0))
                w.valueChanged.connect(lambda v, f=fname: self._set_spec(f, v))
            elif ftype_name == "int":
                w = styled_spinbox(QSpinBox())
                w.setRange(-999999, 999999)
                w.setValue(int(current_val or 0))
                w.valueChanged.connect(lambda v, f=fname: self._set_spec(f, v))
            else:
                w = styled_lineedit(QLineEdit(str(current_val or "")))
                w.textChanged.connect(lambda v, f=fname: self._set_spec(f, v))

            col = (row_idx - 1) % 2 * 2
            actual_row = (row_idx - 1) // 2 + 1
            grid.addWidget(lbl, actual_row, col)
            grid.addWidget(w, actual_row, col + 1)
            self._widgets[fname] = w

        # Notes
        notes_row = len(schema) // 2 + 2
        notes_lbl = QLabel("Notes")
        notes_lbl.setStyleSheet(f"color: {TEXT2}; font-size: 10.5px;")
        self.notes_edit = _styled_textedit(QTextEdit(str(initial.get("notes") or "")))
        self.notes_edit.setMaximumHeight(60)
        grid.addWidget(notes_lbl, notes_row, 0)
        grid.addWidget(self.notes_edit, notes_row, 1, 1, 3)

        scroll.setWidget(body)
        outer.addWidget(scroll)

    def _set_spec(self, field: str, value):
        if "specs" not in self._form_data:
            self._form_data["specs"] = {}
        self._form_data["specs"][field] = value

    def _save(self):
        self.error_lbl.hide()
        description = self.desc_edit.text().strip()
        if not description:
            self._show_error("Description is required.")
            return

        specs = {}
        for fname, widget in self._widgets.items():
            if isinstance(widget, (QDoubleSpinBox, QSpinBox)):
                specs[fname] = widget.value()
            else:
                specs[fname] = widget.text().strip()

        self.save_btn.setEnabled(False)
        self.save_btn.setText("Saving…")
        comp_id = self._form_data.get("id", "")
        self._worker = _SaveWorker(
            self.mode, comp_id, self.component_type,
            description, specs, self.notes_edit.toPlainText().strip(),
            parent=self,
        )
        self._worker.done.connect(self._on_saved)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _show_error(self, msg):
        self.error_lbl.setText(msg)
        self.error_lbl.show()

    def _on_saved(self, result):
        self.save_btn.setEnabled(True)
        self.save_btn.setText("Save")
        self.saved.emit(result)

    def _on_error(self, msg):
        self.save_btn.setEnabled(True)
        self.save_btn.setText("Save")
        self._show_error(f"Save failed: {msg}")


# ── Type-specific browse view ─────────────────────────────────────────────
class _TypeBrowseView(QWidget):
    def __init__(self, component_type: str, type_label: str, parent=None):
        super().__init__(parent)
        self.component_type = component_type
        self.type_label = type_label
        self._components: list = []
        self._schema: list = []
        self._query = ""
        self._worker = None
        self._delete_worker = None
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._apply_filter)

        self._stack = QStackedWidget()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._stack)
        self._stack.addWidget(self._build_browse())
        self._form_placeholder = QWidget()
        self._stack.addWidget(self._form_placeholder)

    def load(self, components: list, schema: list):
        self._components = components
        self._schema = schema
        self._footer_lbl.setText(
            f"{len(components)} custom {self.type_label.lower()}  ·  "
            f"Add components using '+ New' or create from the design BOM"
        )
        self._apply_filter()

    def _build_browse(self):
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # SCOPED: the bare border-bottom was landing on the search box and the
        # New button too.
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
            QLineEdit(),
            placeholder=f"Search {self.type_label.lower()} by description…",
        )
        self._search_box.textChanged.connect(self._on_query_changed)
        tl.addWidget(self._search_box, 1)
        singular = (self.type_label[:-1] if self.type_label.endswith("s")
                    else self.type_label)
        new_btn = _btn(f"+ New {singular}", primary=True)
        new_btn.clicked.connect(self._open_create)
        tl.addWidget(new_btn)
        layout.addWidget(toolbar)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Description", "Key Specs", "Actions"])
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        # QHeaderView::section and QTableWidget::item are INTENTIONAL descendant
        # rules -- those sub-elements are exactly what we mean to style.
        self._table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {PANEL2}; color: {TEXT}; border: none;
                gridline-color: {BORDER}; font-size: 11px;
            }}
            QHeaderView::section {{
                background-color: {PANEL}; color: {TEXT2}; border: none;
                border-bottom: 1px solid {BORDER}; padding: 7px 8px;
                font-size: 9.5px; font-weight: 700;
            }}
            QTableWidget::item {{
                padding: 5px 8px; border: none;
                border-bottom: 1px solid {BORDER};
            }}
        """)
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(2, 195)
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

    def _on_query_changed(self, text):
        self._query = text
        self._debounce.start(300)

    def _summary_fields(self):
        """Pick up to 3 fields that make a good one-line summary.

        FIXED (#5): this was `self._schema[:3]` -- the first three schema fields,
        blindly. For buckets, field 1 is `style` (value "AA") and another early
        field is a LIST rendered as "AA / AC / C / HF / MF / SC" (the recommended-
        materials / style enumeration). So the Key Specs column printed
        "AA  ·  AA / AC / C / HF / MF / SC  ·  305 mm" -- the mangled row.
        (Schema field ORDER is decided by the backend; the panel must not assume
        the first three fields are good summary specs.)

        Rules: skip any field whose value is a list or contains " / " (an
        enumeration), and prefer fields that carry a unit hint (dimensions,
        capacities) since those read as real specs. Falls back to the first
        non-list fields if fewer than three qualify.
        """
        if not self._schema:
            return []

        def is_listy(field):
            # look at the first component that has a value for this field
            for comp in self._components:
                v = (comp.get("specs") or {}).get(field)
                if v is None or v == "":
                    continue
                if isinstance(v, (list, tuple)):
                    return True
                if isinstance(v, str) and (" / " in v or "," in v):
                    return True
                return False
            return False

        scalar = [f for f in self._schema if not is_listy(f["field"])]
        with_unit = [f for f in scalar if f.get("hint")]
        chosen = (with_unit + [f for f in scalar if f not in with_unit])[:3]
        if not chosen:                      # everything was list-valued; degrade gracefully
            chosen = self._schema[:3]
        return [f["field"] for f in chosen]

    def _apply_filter(self):
        q = self._query.lower()
        filtered = [c for c in self._components
                    if not q or q in c.get("description", "").lower()]
        self._table.setRowCount(len(filtered))
        key_fields = self._summary_fields()

        for row, comp in enumerate(filtered):
            desc_item = QTableWidgetItem(comp.get("description", ""))
            desc_item.setForeground(QColor(TEXT))
            self._table.setItem(row, 0, desc_item)

            specs = comp.get("specs") or {}
            spec_parts = []
            for f in key_fields:
                if f in specs and specs[f] not in ("", None):
                    val = specs[f]
                    if isinstance(val, (list, tuple)):
                        continue            # never fold a list into the summary line
                    schema_field = next(
                        (s for s in self._schema if s["field"] == f), None)
                    hint = schema_field["hint"] if schema_field else ""
                    spec_parts.append(f"{val}{' ' + hint if hint else ''}")
            spec_item = QTableWidgetItem("  ·  ".join(spec_parts) or "—")
            spec_item.setForeground(QColor(TEXT2))
            self._table.setItem(row, 1, spec_item)

            action_widget = QWidget()
            action_widget.setStyleSheet(
                scoped(action_widget, "background-color: transparent; border: none;"))
            al = QHBoxLayout(action_widget)
            al.setContentsMargins(4, 2, 4, 2)
            al.setSpacing(4)
            copy_btn = _btn("Copy")
            copy_btn.clicked.connect(lambda _, c=comp: self._open_copy(c))
            al.addWidget(copy_btn)
            edit_btn = _btn("Edit")
            edit_btn.clicked.connect(lambda _, c=comp: self._open_edit(c))
            al.addWidget(edit_btn)
            del_btn = _btn("Delete", danger=True)
            del_btn.clicked.connect(lambda _, c=comp: self._confirm_delete(c))
            al.addWidget(del_btn)
            self._table.setCellWidget(row, 2, action_widget)
            self._table.setRowHeight(row, 38)

    def _open_form(self, initial: dict, mode: str):
        form = ComponentForm(
            self.component_type, initial, mode, self._schema,
            self.type_label, parent=self,
        )
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
        self._reload()

    def _reload(self):
        """Reload from backend.

        NOTE: as pasted, `def _reload` sat at column 0 -- outside the class.
        _TypeBrowseView would have had no _reload method at all, so saving or
        deleting a component would raise AttributeError. Restored as a method.

        Walks up the widget hierarchy to find the parent ComponentsLibraryPanel
        and calls _load_type(force=True) so the cache is invalidated for this
        type only.
        """
        parent = self.parent()
        while parent is not None:
            if isinstance(parent, ComponentsLibraryPanel):
                parent._loaded_types.discard(self.component_type)
                parent._load_type(self.component_type, force=True)
                return
            parent = parent.parent()

        # Fallback: parent panel not found (e.g. testing in isolation). Held on
        # self so it isn't garbage-collected mid-run.
        self._worker = _LoadWorker(self.component_type, parent=self)
        self._worker.done.connect(lambda comps, schema_data: self.load(
            comps, (schema_data.get("schemas") or {}).get(self.component_type, [])
        ))
        self._worker.error.connect(lambda msg: print(f"Reload error: {msg}"))
        self._worker.start()

    def _open_create(self):
        defaults = {f["field"]: f["default"] for f in self._schema}
        self._open_form({"specs": defaults}, "create")

    def _open_copy(self, comp):
        initial = {**comp, "description": f"{comp['description']} (Copy)"}
        self._open_form(initial, "copy")

    def _open_edit(self, comp):
        self._open_form(comp, "edit")

    def _confirm_delete(self, comp):
        box = styled_message_box(
            QMessageBox.Icon.Question, "Delete Component",
            f'Delete "{comp.get("description")}"?\n\nThis cannot be undone.',
            self,
            buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if box.exec() != QMessageBox.StandardButton.Yes:
            return
        self._delete_worker = _DeleteWorker(comp.get("id"), parent=self)
        self._delete_worker.done.connect(self._reload)
        self._delete_worker.error.connect(
            lambda msg: styled_message_box(
                QMessageBox.Icon.Warning, "Delete failed", msg, self).exec()
        )
        self._delete_worker.start()


# ── Main panel ────────────────────────────────────────────────────────────
COMPONENT_TYPES_ORDER = [
    ("belt",     "Belts"),
    ("chain",    "Chains"),
    ("bucket",   "Buckets"),
    ("motor",    "Motors"),
    ("gearbox",  "Gearboxes"),
    ("vfd",      "VFDs / Drives"),
    ("liner",    "Liners"),
    ("coupling", "Couplings"),
]


class ComponentsLibraryPanel(QWidget):
    """Components Library tab -- 8 component types in a type-selector tab bar.
    set_data(inputs, results) wired by main.py; on each call it reloads the
    current type's list from the backend."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(plain_bg(self, PANEL))
        self._active_type = "belt"
        self._schema_cache: dict = {}
        self._loaded_types: set = set()
        self._worker = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # SCOPED: the bare border-bottom was landing on every type-tab button,
        # so each drew its own 1px border on top of its 2px active underline.
        tab_bar = QFrame()
        tab_bar.setStyleSheet(scoped(
            tab_bar,
            f"background-color: {PANEL2}; border: none; "
            f"border-bottom: 1px solid {BORDER};"
        ))
        tbl = QHBoxLayout(tab_bar)
        tbl.setContentsMargins(10, 0, 10, 0)
        tbl.setSpacing(0)
        self._type_btns: dict = {}
        for ctype, clabel in COMPONENT_TYPES_ORDER:
            btn = QPushButton(clabel)
            btn.setCheckable(True)
            btn.setChecked(ctype == self._active_type)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, t=ctype: self._switch_type(t))
            self._style_tab_btn(btn, ctype == self._active_type)
            tbl.addWidget(btn)
            self._type_btns[ctype] = btn
        tbl.addStretch()
        outer.addWidget(tab_bar)

        self._type_stack = QStackedWidget()
        self._type_views: dict = {}
        for ctype, clabel in COMPONENT_TYPES_ORDER:
            view = _TypeBrowseView(ctype, clabel)
            self._type_views[ctype] = view
            self._type_stack.addWidget(view)
        outer.addWidget(self._type_stack, 1)

        self._load_type(self._active_type)

    def _style_tab_btn(self, btn, active):
        """NOTE: as pasted, `def _style_tab_btn` sat at column 0 -- outside the
        class. ComponentsLibraryPanel would have had no such method, and
        __init__ calls it, so constructing this panel would have raised
        AttributeError immediately. Restored as a method.

        The active tint was rgba(74,158,255,.12) -- v1 primary -- behind v2
        PRIMARY text and underline. Now PRIMARY_DIM."""
        if active:
            btn.setStyleSheet(scoped(
                btn,
                f"background-color: {PRIMARY_DIM}; color: {PRIMARY}; "
                f"border: none; border-bottom: 2px solid {PRIMARY}; "
                f"padding: 6px 12px; font-size: 10px; font-weight: 700;"
            ))
        else:
            btn.setStyleSheet(scoped(
                btn,
                f"background-color: transparent; color: {TEXT3}; border: none; "
                f"border-bottom: 2px solid transparent; padding: 6px 12px; "
                f"font-size: 10px;",
                extra="{sel}:hover { color: %s; }" % TEXT2,
            ))

    def _switch_type(self, ctype: str):
        for t, btn in self._type_btns.items():
            btn.setChecked(t == ctype)
            self._style_tab_btn(btn, t == ctype)
        self._active_type = ctype
        idx = list(self._type_views.keys()).index(ctype)
        self._type_stack.setCurrentIndex(idx)
        self._load_type(ctype)

    def _load_type(self, ctype: str, force: bool = False):
        """Components don't change with calculation inputs, so there's no reason
        to hit the backend on every set_data() call from a tab switch -- hence
        the _loaded_types cache.

        FIXED: the old guard was
            if self._worker and self._worker.isRunning(): return
        which silently DROPPED the request if a load was already in flight.
        Switch type twice quickly and the second type sits on "Loading…"
        forever, because nothing ever retries it. Now an in-flight worker is
        cancelled and superseded -- the same pattern MaterialSearchWidget uses.
        """
        if not force and ctype in self._loaded_types:
            return

        if self._worker is not None and self._worker.isRunning():
            try:
                self._worker.done.disconnect()
                self._worker.error.disconnect()
            except (TypeError, RuntimeError):
                pass
            self._worker.quit()
            self._worker.wait()

        self._worker = _LoadWorker(ctype, parent=self)
        self._worker.done.connect(
            lambda comps, schema_data: self._on_loaded(ctype, comps, schema_data))
        self._worker.error.connect(
            lambda msg: print(f"ComponentsLibrary load error: {msg}"))
        self._worker.start()

    def _on_loaded(self, ctype: str, components: list, schema_data: dict):
        if schema_data:
            self._schema_cache = schema_data
        schemas = (schema_data.get("schemas")
                   or self._schema_cache.get("schemas") or {})
        self._type_views[ctype].load(components, schemas.get(ctype, []))
        self._loaded_types.add(ctype)

    def set_data(self, inputs, results):
        self._load_type(self._active_type)