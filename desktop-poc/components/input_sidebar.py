"""
components/input_sidebar.py -- PySide6 port of InputSidebar.jsx
═══════════════════════════════════════════════════════════════════════════
Started, not complete -- InputSidebar.jsx is ~2,500 lines covering 11
sections (Process Design, Head & Tail Pulley, Belt/Chain, Bucket, Take-Up,
Shaft, Discharge, Feed, Casing, Service, Power). Porting all of them in one
pass wasn't realistic to do faithfully -- this round does 2 fully, for
real, and lists the rest honestly.

The actual JSX architecture (checked directly, not assumed): EVERY section,
including Process Design itself, is a SectionRow summary line that opens a
modal when clicked -- this isn't a sidebar with inline forms, it's a list
of summaries, each backed by a popup edit form. That's exactly the
QDialog popup pattern already built for the equipment tree's leaf detail
view, reused here for a second purpose (editing inputs, not just viewing
them).

Done for real, with working data flow:
    - Design Requirements (ProcessEdit's core fields: drive type, Q_req,
      H_m, fill_pct, material id)
    - Head & Tail Pulley (PulleyEdit's core fields: D_mm, n_rpm, boot
      pulley diameter/match-head toggle)

Deliberately simplified, not silently dropped: ProcessEdit's Dynamic Fill
Advisory bar and PulleyEdit's wrap-angle formula box are real, fairly
elaborate visual components in the JSX (live min/max/recommended bars,
a derived-wrap-angle formula readout). This round shows the same
underlying numbers as plain text in the modal rather than fully
recreating those visual treatments -- the priority for this round was
real data flow (edit -> recalculate -> everything updates), not visual
parity on every advisory panel. Flagging this honestly rather than
pretending it's pixel-for-pixel done.

Not yet ported at all (still in the summary-only list, named explicitly):
Belt/Chain Selection, Bucket Selection, Take-Up Selection, Shaft Design,
Discharge Section, Feed Design, Casing Design, Service Conditions, Power
Transmission. Each is shown as a real SectionRow with whatever summary
text can be computed from actual result data, clicking just says so isn't
wired yet -- not a fake form, an honest gap.

This widget owns no fetch logic -- it emits inputsChanged(dict) when the
user applies a change, and main.py's run_calculation() is what actually
calls the backend with the new inputs, the same separation ElevationView
and EquipmentTreePanel already use.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea,
    QDialog, QPushButton, QDoubleSpinBox, QSpinBox, QLineEdit, QCheckBox,
)
from PySide6.QtCore import Qt, Signal

from theme import BG, PANEL, PANEL2, BORDER, TEXT, TEXT2, TEXT3, MUTED, PRIMARY

# Sections not yet ported -- listed explicitly so the gap is named, not
# silently absent. (id, label, cema)
NOT_YET_PORTED = [
    ("belt",      "Belt / Chain Selection", "CEMA 375 §4"),
    ("bucket",    "Bucket Selection",        "CEMA 375 §6"),
    ("takeup",    "Take-Up Selection",       "CEMA 375 §4"),
    ("shaft",     "Shaft Design",            "CEMA 375 §4"),
    ("discharge", "Discharge Section",       "CEMA 375 §5"),
    ("feed",      "Feed Design",             "CEMA 375 §4"),
    ("casing",    "Casing Design",           "CEMA 375 §7"),
    ("service",   "Service Conditions",      "v1.3.0"),
    ("power",     "Power Transmission",      "CEMA 375 §4"),
]


def fmt(v, dp=1, fb="—"):
    if v is None:
        return fb
    try:
        return f"{float(v):.{dp}f}"
    except (TypeError, ValueError):
        return fb


class SectionRow(QFrame):
    """Direct port of the JSX's SectionRow -- label + summary text +
    optional status badge + a pencil icon, the whole row clickable."""

    def __init__(self, label, summary="", cema="", clickable=True, parent=None):
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
        if cema:
            cema_lbl = QLabel(cema)
            cema_lbl.setStyleSheet(f"color: {TEXT3}; font-size: 9px;")
            top.addWidget(cema_lbl)
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


def field_row(label, widget, unit=None, note=None):
    """One labeled input row inside a modal -- label above, input (+ unit
    suffix) below, optional note. Mirrors the JSX's F component's layout,
    not its exact pixel styling."""
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
    spinbox.setStyleSheet(
        f"background-color: {PANEL2}; color: {TEXT}; border: 1px solid {BORDER}; "
        f"border-radius: 4px; padding: 5px 8px; font-size: 12px;"
    )
    return spinbox


class NotYetPortedDialog(QDialog):
    """Honest placeholder modal -- same spirit as the Placeholder widget
    used throughout main.py, just shaped as a dialog since that's the
    interaction this list uses."""

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
    """Port of ProcessEdit's core fields: drive type, Q_req, H_m, fill_pct,
    material id. The Dynamic Fill Advisory bar (live min/max/recommended
    fill with a visual range indicator) is shown as plain text here rather
    than fully recreated -- see this module's own docstring."""

    def __init__(self, inputs, results, parent=None):
        super().__init__(parent)
        self.inputs = dict(inputs)
        self.setWindowTitle("Process Design")
        self.setMinimumWidth(420)
        self.setStyleSheet(f"background-color: {PANEL};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setStyleSheet(f"background-color: {PANEL2}; border-bottom: 1px solid {BORDER};")
        hl = QVBoxLayout(header)
        hl.setContentsMargins(16, 12, 16, 12)
        title = QLabel("Process Design")
        title.setStyleSheet(f"color: {TEXT}; font-size: 14px; font-weight: 700;")
        sub = QLabel("CEMA 375 §4")
        sub.setStyleSheet(f"color: {TEXT3}; font-size: 10px;")
        hl.addWidget(title); hl.addWidget(sub)
        layout.addWidget(header)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 16, 16, 16)
        body_layout.setSpacing(12)

        drive_row = QHBoxLayout()
        self.belt_btn = QPushButton("🔵 Belt Drive")
        self.chain_btn = QPushButton("⛓ Chain Drive")
        for btn, val in ((self.belt_btn, "belt"), (self.chain_btn, "chain")):
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, v=val: self._set_drive_type(v))
            drive_row.addWidget(btn)
        self._set_drive_type(self.inputs.get("conveyor_type", "belt"), restyle_only=True)
        body_layout.addLayout(drive_row)

        row2 = QHBoxLayout()
        self.q_req = styled_spinbox(QDoubleSpinBox())
        self.q_req.setRange(1, 5000); self.q_req.setSingleStep(1)
        self.q_req.setValue(float(self.inputs.get("Q_req", 100)))
        row2.addLayout(field_row("Required Capacity", self.q_req, "t/h"))
        self.h_m = styled_spinbox(QDoubleSpinBox())
        self.h_m.setRange(1, 200); self.h_m.setSingleStep(0.5)
        self.h_m.setValue(float(self.inputs.get("H_m", 25)))
        row2.addLayout(field_row("Lift Height", self.h_m, "m"))
        body_layout.addLayout(row2)

        self.mat_id = QLineEdit(str(self.inputs.get("mat_id", "wheat")))
        self.mat_id.setStyleSheet(
            f"background-color: {PANEL2}; color: {TEXT}; border: 1px solid {BORDER}; "
            f"border-radius: 4px; padding: 5px 8px; font-size: 12px;"
        )
        body_layout.addLayout(field_row(
            "Material ID", self.mat_id, note="Plain text id for now (e.g. wheat, clinker, cement) "
            "-- the real searchable material picker with live density/category chips is a separate piece."
        ))

        self.fill_pct = styled_spinbox(QSpinBox())
        self.fill_pct.setRange(30, 100); self.fill_pct.setSingleStep(5)
        self.fill_pct.setValue(int(self.inputs.get("fill_pct", 75)))
        body_layout.addLayout(field_row(
            "Bucket Fill Factor", self.fill_pct, "%",
            note="Grain 75-90% · Minerals 60-75% · Cohesive 40-65%"
        ))

        r = results or {}
        if r.get("min_fill_pct") is not None or r.get("dynamic_fill"):
            advisory = QLabel(
                f"Dynamic fill advisory (CEMA §6) -- min {fmt(r.get('min_fill_pct'), 0)}%, "
                f"max {fmt(r.get('max_fill_pct'), 0)}%, recommended "
                f"{fmt((r.get('dynamic_fill') or {}).get('recommended_fill_pct'), 0)}%. "
                f"Shown as text only this round -- see module docstring."
            )
            advisory.setWordWrap(True)
            advisory.setStyleSheet(
                f"background-color: rgba(74,158,255,.06); border: 1px solid rgba(74,158,255,.2); "
                f"border-radius: 5px; padding: 8px 12px; color: {TEXT3}; font-size: 10.5px;"
            )
            body_layout.addWidget(advisory)

        body_layout.addStretch()
        layout.addWidget(body)
        layout.addWidget(self._build_footer())

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

    def _build_footer(self):
        footer = QFrame()
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setStyleSheet(f"background-color: transparent; color: {TEXT3}; border: none; padding: 6px 14px;")
        cancel.clicked.connect(self.reject)
        apply_btn = QPushButton("Apply")
        apply_btn.setStyleSheet(
            f"background-color: {PRIMARY}; color: white; border: none; "
            f"border-radius: 5px; padding: 6px 18px; font-size: 11.5px; font-weight: 600;"
        )
        apply_btn.clicked.connect(self.accept)
        layout.addWidget(cancel)
        layout.addWidget(apply_btn)
        return footer

    def updated_inputs(self):
        self.inputs["Q_req"] = self.q_req.value()
        self.inputs["H_m"] = self.h_m.value()
        self.inputs["mat_id"] = self.mat_id.text().strip() or "wheat"
        self.inputs["fill_pct"] = self.fill_pct.value()
        return self.inputs


class PulleyEditDialog(QDialog):
    """Port of PulleyEdit's core fields: head pulley diameter/RPM, boot
    pulley diameter with a match-head toggle. The wrap-angle formula
    readout (geometric/effective/formula, three-column box) is shown as
    plain text here -- see this module's own docstring."""

    def __init__(self, inputs, results, parent=None):
        super().__init__(parent)
        self.inputs = dict(inputs)
        self.setWindowTitle("Head & Tail Pulley")
        self.setMinimumWidth(420)
        self.setStyleSheet(f"background-color: {PANEL};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setStyleSheet(f"background-color: {PANEL2}; border-bottom: 1px solid {BORDER};")
        hl = QVBoxLayout(header)
        hl.setContentsMargins(16, 12, 16, 12)
        title = QLabel("Head & Tail Pulley")
        title.setStyleSheet(f"color: {TEXT}; font-size: 14px; font-weight: 700;")
        sub = QLabel("CEMA 375 §3,6")
        sub.setStyleSheet(f"color: {TEXT3}; font-size: 10px;")
        hl.addWidget(title); hl.addWidget(sub)
        layout.addWidget(header)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 16, 16, 16)
        body_layout.setSpacing(12)

        row1 = QHBoxLayout()
        self.d_mm = styled_spinbox(QDoubleSpinBox())
        self.d_mm.setRange(100, 1500); self.d_mm.setSingleStep(25)
        self.d_mm.setValue(float(self.inputs.get("D_mm", 500)))
        row1.addLayout(field_row("Head Pulley Dia.", self.d_mm, "mm"))
        self.n_rpm = styled_spinbox(QDoubleSpinBox())
        self.n_rpm.setRange(10, 300); self.n_rpm.setSingleStep(5)
        self.n_rpm.setValue(float(self.inputs.get("n_rpm", 70)))
        row1.addLayout(field_row("Shaft Speed", self.n_rpm, "rpm"))
        body_layout.addLayout(row1)

        r = results or {}
        wrap_box = QLabel(
            f"Wrap angle (derived) -- geometric {fmt(r.get('wrap_geom_deg'), 0, '—')}°, "
            f"effective {fmt(r.get('wrap_effective_deg'), 0, '—')}°. "
            f"180° + 2·arcsin((R_H−R_B)/C). Plain text only this round."
        )
        wrap_box.setWordWrap(True)
        wrap_box.setStyleSheet(
            f"background-color: {PANEL2}; border: 1px solid {BORDER}; border-radius: 5px; "
            f"padding: 8px 12px; color: {TEXT3}; font-size: 10.5px;"
        )
        body_layout.addWidget(wrap_box)

        self.same_as_head = QCheckBox("Boot pulley same diameter as head")
        self.same_as_head.setStyleSheet(f"color: {TEXT2}; font-size: 11px;")
        self.same_as_head.setChecked(bool(self.inputs.get("boot_pulley_same_as_head", False)))
        self.same_as_head.toggled.connect(self._on_same_as_head)
        body_layout.addWidget(self.same_as_head)

        self.boot_d_mm = styled_spinbox(QDoubleSpinBox())
        self.boot_d_mm.setRange(100, 1000); self.boot_d_mm.setSingleStep(25)
        self.boot_d_mm.setValue(float(self.inputs.get("boot_pulley_D_mm", 300)))
        self.boot_row = field_row("Boot Pulley Dia.", self.boot_d_mm, "mm")
        body_layout.addLayout(self.boot_row)
        self._on_same_as_head(self.same_as_head.isChecked())

        body_layout.addStretch()
        layout.addWidget(body)
        layout.addWidget(self._build_footer())

    def _on_same_as_head(self, checked):
        self.boot_d_mm.setEnabled(not checked)

    def _build_footer(self):
        footer = QFrame()
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setStyleSheet(f"background-color: transparent; color: {TEXT3}; border: none; padding: 6px 14px;")
        cancel.clicked.connect(self.reject)
        apply_btn = QPushButton("Apply")
        apply_btn.setStyleSheet(
            f"background-color: {PRIMARY}; color: white; border: none; "
            f"border-radius: 5px; padding: 6px 18px; font-size: 11.5px; font-weight: 600;"
        )
        apply_btn.clicked.connect(self.accept)
        layout.addWidget(cancel)
        layout.addWidget(apply_btn)
        return footer

    def updated_inputs(self):
        self.inputs["D_mm"] = self.d_mm.value()
        self.inputs["n_rpm"] = self.n_rpm.value()
        self.inputs["boot_pulley_same_as_head"] = self.same_as_head.isChecked()
        self.inputs["boot_pulley_D_mm"] = self.boot_d_mm.value()
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
                w.deleteLater()

        mat = self.results.get("mat") or {}
        mat_name = mat.get("name", self.inputs.get("mat_id", "—"))
        summary = f"{self.inputs.get('Q_req','—')}t/h · {self.inputs.get('H_m','—')}m · {mat_name} · Fill {self.inputs.get('fill_pct','—')}%"
        process_row = SectionRow("Design Requirements", summary, "CEMA 375")
        process_row.clicked = lambda: self._open_process_dialog()
        self.list_layout.addWidget(process_row)

        # FIX: was reading the raw inp.boot_pulley_D_mm directly, which is
        # never actually set when boot_pulley_same_as_head is true (same
        # class of bug already fixed in ElevationView/EquipmentTree --
        # toggling "same as head" sets the flag but never touches this raw
        # field). Reading the backend's already-resolved value instead.
        boot_pulley = self.results.get("boot_pulley") or {}
        boot_d = boot_pulley.get("boot_D_mm", self.inputs.get("boot_pulley_D_mm", "—"))
        wrap = self.results.get("wrap_effective_deg", self.inputs.get("wrap_deg", 180))
        pulley_summary = f"D_H {self.inputs.get('D_mm','—')}mm · D_B {boot_d}mm · {self.inputs.get('n_rpm','—')}rpm · Wrap {wrap}°"
        pulley_row = SectionRow("Head & Tail Pulley", pulley_summary, "CEMA 375 §3,6")
        pulley_row.clicked = lambda: self._open_pulley_dialog()
        self.list_layout.addWidget(pulley_row)

        for sid, label, cema in NOT_YET_PORTED:
            row = SectionRow(label, self._summary_for(sid), cema)
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
        if section_id == "shaft":
            return f"{self.inputs.get('shaft_material', 'A36')} · Ø{fmt(r.get('d_mm'), 1)}mm"
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

    def _open_not_yet_ported(self, label):
        NotYetPortedDialog(label, self).exec()