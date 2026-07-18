"""
components/discharge_edit.py -- Discharge Section dialog.
═══════════════════════════════════════════════════════════════════════════
Discharge type override, chute liner selection, chute position/angle
overrides, plus the real computed chute performance, maintenance, geometry
and casing-clearance data. No engineering math lives here; every number
shown is read straight from results.discharge_chute / results.casing_clearance.

STRUCTURE RESTORED
──────────────────
The source arrived scrambled, not merely de-indented: the "Discharge Type"
block sat ABOVE the class definition entirely (module level, referencing
`bl` and `self` which don't exist there), LINER_OPTIONS was spliced into the
middle of __init__, and self.liner_combo was constructed BEFORE the constant
it populates from. As pasted this could not import.

Reconstructed into the order the code clearly intends:
    setup -> discharge type -> chute angle -> liner -> chute position
          -> angle override -> geometry -> casing clearance
Worth diffing against the real file, since that order is inferred from
context rather than read.

BOX-IN-BOX SWEEP
────────────────
Mostly clean -- this file is built on dialog_helpers' shared widgets
(stat_box, field_row, flag_note, n_way_selector), so it inherits their fixes,
same as casing_edit.py. Only one real offender:

    self.liner_combo.setStyleSheet(f"background-color: {PANEL2}; ... "
                                   f"border: 1px solid {BORDER}; ...")

A hand-rolled combo stylesheet, and a BARE one (no selector) -- which Qt
treats as `* { ... }`, applying to the widget AND every descendant. A
QComboBox is not a leaf widget (it owns an internal view/line-edit), so the
border landed inside it too. It also missed every fix in the shared
styled_combo(): the flat drop-down arrow, the matching 6px radius, the
scoped popup list styling. Replaced with styled_combo().

That is the same failure as components_library_panel.py's _input_style():
any file that hand-rolls its own field styling silently opts out of every
fix made to the shared helpers.

THRESHOLD-IN-FRONTEND (flagged, not changed)
────────────────────────────────────────────
    load_status = "ok" if loading_pct < 40 else ("warn" if loading_pct < 60 else "fail")

The 40% / 60% chute-loading bands are engineering constants living in the
frontend. chute_flow.py already computes loading_pct and returns a `note`;
it should also return the verdict, the way calculations.py returns cap_ok /
speed_ok / cr_ok. Values preserved exactly -- flagged, not "fixed" by
inventing a backend field that doesn't exist. (Same class of issue as
status_panel.py's 50/80 kN headshaft limits and maintenance_panel.py's
8,000 h MTBF limit -- see the task list.)
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea,
    QDoubleSpinBox, QComboBox,
)

from theme import (
    PANEL, PANEL2, BORDER, TEXT, TEXT2, TEXT3, MUTED,
    SUCCESS, WARNING, DANGER,
    scoped, plain_bg,
)
from .dialog_helpers import (
    fmt, section_head, field_row, styled_spinbox, styled_combo,
    modal_header, modal_footer, stat_box, n_way_selector, status_badge, flag_note,
)

DISCHARGE_TYPE_OPTIONS = [
    ("", "Auto (from bucket style)"),
    ("centrifugal", "Force Centrifugal"),
    ("continuous", "Force Continuous"),
]

# Real liner catalogue, mirrored from chute_flow.py's
# ChuteFlowEngine.LINER_CATALOGUE -- descriptive text only. The actual
# friction/thickness data the calculation uses lives in the backend; this is
# just the dropdown labels.
LINER_OPTIONS = [
    ("auto", "Auto (CEMA wear-index selection)"),
    ("mild_steel", "Mild Steel (unlined)"),
    ("ar400", "AR400 Wear Plate"),
    ("nat_rubber", "Natural Rubber (NR)"),
    ("uhmwpe", "UHMW-PE Sheet"),
    ("ceramic_tile", "Ceramic Tile (Al₂O₃)"),
    ("ptfe", "PTFE / Teflon Sheet"),
]


class DischargeEditDialog(QDialog):
    """Discharge Section -- discharge type override, chute liner selection,
    chute position/angle overrides, plus the real computed chute performance,
    maintenance, and casing-clearance data."""

    def __init__(self, inputs, results, parent=None):
        super().__init__(parent)
        self.inputs = dict(inputs)
        self.results = results or {}
        self.setWindowTitle("Discharge Section")
        self.setMinimumWidth(500)
        self.resize(520, 740)
        self.setStyleSheet(plain_bg(self, PANEL))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(modal_header("Discharge Section", "CEMA 375 §5"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(scoped(scroll, "border: none; background: transparent;"))
        body = QFrame()
        body.setStyleSheet(scoped(body, "background-color: transparent; border: none;"))
        bl = QVBoxLayout(body)
        bl.setContentsMargins(16, 16, 16, 16)
        bl.setSpacing(12)

        r = self.results
        dc = r.get("discharge_chute") or {}
        perf = dc.get("performance") or {}
        maint = dc.get("maintenance") or {}
        geom = dc.get("geometry") or {}
        cc = r.get("casing_clearance") or {}

        # ── Discharge type ───────────────────────────────────────────
        bl.addWidget(section_head("Discharge Type"))
        self._dtype_val = [self.inputs.get("discharge_type_override", "")]
        bl.addLayout(n_way_selector(
            DISCHARGE_TYPE_OPTIONS, self._dtype_val, self._on_dtype_change))
        current_type = r.get("discharge_type", "—")
        dtype_note = QLabel(
            f"Currently resolving to: {str(current_type).capitalize()} "
            f"({'auto from bucket style' if not self._dtype_val[0] else 'overridden'})."
        )
        dtype_note.setWordWrap(True)
        dtype_note.setStyleSheet(f"color: {TEXT2}; font-size: 13px;")
        bl.addWidget(dtype_note)

        # ── Chute angle ──────────────────────────────────────────────
        if perf:
            bl.addWidget(section_head("Chute Angle"))
            adequate = perf.get("angle_adequate")
            bl.addWidget(stat_box(
                [("Chute angle", f"{fmt(perf.get('chute_angle_deg'), 1)}°"),
                 ("Min required", f"{fmt(perf.get('min_angle_deg'), 1)}°"),
                 ("Flow regime",
                  (perf.get("flow_regime") or "—").replace("_", " ").title()),
                 ("Governed by", perf.get("governed_by", "—"))],
                status="fail" if adequate is False else None,
                note=(None if adequate is not False else
                      f"Below minimum — steepen to "
                      f"≥{fmt(perf.get('mass_flow_angle_deg'), 0)}° for mass flow."),
            ))

            cap = perf.get("capacity_check") or {}
            if cap:
                loading_pct = cap.get("loading_pct") or 0
                # THRESHOLD-IN-FRONTEND: the 40%/60% bands are engineering
                # constants that belong in chute_flow.py, returned as a verdict
                # alongside loading_pct. Preserved exactly -- flagged, not
                # silently altered. See module docstring.
                load_status = ("ok" if loading_pct < 40
                               else ("warn" if loading_pct < 60 else "fail"))
                bl.addWidget(stat_box(
                    [("Loading", f"{fmt(loading_pct, 1)}%"),
                     ("Stream depth",
                      f"{fmt((cap.get('stream_depth_m') or 0) * 1000, 0)} mm")],
                    status=load_status,
                    note=cap.get("note"),
                ))

        # ── Chute liner ──────────────────────────────────────────────
        bl.addWidget(section_head("Chute Liner"))
        # Was a hand-rolled BARE combo stylesheet -- see module docstring.
        # styled_combo() is the shared, scoped one every other dialog uses.
        self.liner_combo = styled_combo(QComboBox())
        current_liner = self.inputs.get("chute_liner_id", "auto")
        for i, (val, text) in enumerate(LINER_OPTIONS):
            self.liner_combo.addItem(text, val)
            if val == current_liner:
                self.liner_combo.setCurrentIndex(i)
        bl.addWidget(self.liner_combo)

        if maint:
            bl.addWidget(stat_box([
                ("Selected", maint.get("liner_material", "—")),
                ("Grade", maint.get("liner_grade", "—")),
                ("Thickness", f"{fmt(maint.get('liner_thickness_mm'), 0)} mm"),
            ]))
            wear_status = {"LOW": "ok", "MODERATE": "warn", "HIGH": "fail"}.get(
                maint.get("wear_rating") or "", None)
            bl.addWidget(stat_box(
                [("Wear rating", maint.get("wear_rating", "—")),
                 ("Plugging risk", maint.get("plugging_risk", "—")),
                 ("Dust risk", maint.get("dust_risk", "—"))],
                status=wear_status,
            ))

        # ── Chute position ───────────────────────────────────────────
        bl.addWidget(section_head("Discharge Chute Position"))
        row1 = QHBoxLayout()
        self.chute_x_offset = styled_spinbox(QDoubleSpinBox())
        self.chute_x_offset.setRange(0, 500)
        self.chute_x_offset.setSingleStep(10)
        self.chute_x_offset.setValue(float(self.inputs.get("chute_x_offset_mm", 0)))
        row1.addLayout(field_row(
            "Catch Opening Offset", self.chute_x_offset, "mm",
            note="How far the discharge chute's mouth is set back from the casing "
                 "wall. 0 = flush with wall − 10mm clearance."))

        self.chute_opening_height = styled_spinbox(QDoubleSpinBox())
        self.chute_opening_height.setRange(0, 1000)
        self.chute_opening_height.setSingleStep(25)
        self.chute_opening_height.setValue(
            float(self.inputs.get("chute_opening_height_mm", 0)))
        row1.addLayout(field_row(
            "Catch Opening Height", self.chute_opening_height, "mm",
            note="Vertical size of the discharge chute's mouth. 0 = auto from head "
                 "pulley diameter."))
        bl.addLayout(row1)

        # ── Back-plate angle override ────────────────────────────────
        self.chute_angle_override = styled_spinbox(QDoubleSpinBox())
        self.chute_angle_override.setRange(0, 90)
        self.chute_angle_override.setSingleStep(5)
        self.chute_angle_override.setValue(
            float(self.inputs.get("chute_angle_override_deg", 0)))
        angle_status = None
        angle_note = "0 = auto (trajectory-derived)."
        if dc.get("angle_is_override"):
            angle_status = "info"
            angle_note = (f"Overriding — auto-derived value was "
                          f"{fmt(geom.get('back_plate_angle_deg'), 0)}°.")
        bl.addLayout(field_row(
            "Discharge Chute Back-Plate Angle Override", self.chute_angle_override,
            "°", note=angle_note, status=angle_status))

        # ── Geometry ─────────────────────────────────────────────────
        if geom:
            bl.addWidget(section_head("Chute Geometry"))
            bl.addWidget(stat_box([
                ("Throw distance",
                 f"{fmt((geom.get('throw_distance_m') or 0) * 1000, 0)} mm"),
                ("Spout width", f"{fmt(geom.get('spout_width_mm'), 0)} mm"),
                ("Throat velocity", f"{fmt(geom.get('throat_velocity_mps'), 2)} m/s"),
            ]))
            if geom.get("note"):
                geom_note = QLabel(geom["note"])
                geom_note.setWordWrap(True)
                geom_note.setStyleSheet(f"color: {TEXT2}; font-size: 13px;")
                bl.addWidget(geom_note)

        # ── Casing clearance ─────────────────────────────────────────
        if cc:
            bl.addWidget(section_head("Casing Clearance"))
            clears = cc.get("clears")
            bl.addWidget(stat_box(
                [("CR", fmt(cc.get("cr"), 3)),
                 ("Centrifugal risk", "Yes" if cc.get("centrifugal_risk") else "No")],
                status=None if clears is not False else "fail",
                note=cc.get("recommendation"),
            ))

        bl.addStretch()
        scroll.setWidget(body)
        layout.addWidget(scroll)
        layout.addWidget(modal_footer(self))

    def _on_dtype_change(self, value):
        self._dtype_val[0] = value

    def updated_inputs(self):
        self.inputs["discharge_type_override"] = self._dtype_val[0]
        self.inputs["chute_liner_id"] = self.liner_combo.currentData()
        self.inputs["chute_x_offset_mm"] = self.chute_x_offset.value()
        self.inputs["chute_opening_height_mm"] = self.chute_opening_height.value()
        self.inputs["chute_angle_override_deg"] = self.chute_angle_override.value()
        return self.inputs