"""
components/discharge_edit.py -- Discharge Section dialog.
═══════════════════════════════════════════════════════════════════════════
Third section built in its own file, after takeup_edit.py and feed_edit.py.
Shared widgets come from dialog_helpers.py, same reasoning as the other
two -- avoids a circular import with input_sidebar.py.

Backend support confirmed directly before writing any UI for this:
  - discharge_type_override: "" | "centrifugal" | "continuous" (models.py)
    -- forces discharge character independent of bucket style, for
    non-standard applications. Empty = auto from bucket style.
  - chute_liner_id: real 7-entry catalog (chute_flow.py LINER_CATALOGUE) --
    auto, mild_steel, ar400, nat_rubber, uhmwpe, ceramic_tile, ptfe, each
    with a real friction coefficient and thickness, not placeholder names.
  - chute_x_offset_mm / chute_opening_height_mm: chute inlet positioning
    overrides (models.py). CONFIRMED directly in calculations.py (the
    function uses inp.D_mm/2000.0, the HEAD pulley radius, as its
    trajectory release-point reference) that "chute" here means the
    DISCHARGE chute's own catch-opening at the head section -- the mouth
    that catches material flying off the bucket discharge -- NOT the
    boot/feed inlet at the bottom of the elevator, which is a completely
    separate opening handled in Feed Design (boot_inlet_height_override_mm).
    Labels below say "Discharge Chute" explicitly to remove the ambiguity
    that prompted this check in the first place.
  - chute_angle_override_deg: back-plate angle override -- the chute
    angle is a real fabrication parameter the solver previously only
    derived, with no way to ask "if I build it at 45°, does it still
    clear the mass-flow requirement" (confirmed in models.py's comment).
  - results already contain discharge_chute (performance/geometry/
    maintenance/hood_spoon), casing_clearance, and stream_chute, all
    fully computed -- this dialog reads them, doesn't recompute anything.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea,
    QDoubleSpinBox, QComboBox,
)

from theme import PANEL, PANEL2, BORDER, TEXT, TEXT2, TEXT3, MUTED, SUCCESS, WARNING, DANGER
from .dialog_helpers import (
    fmt, section_head, field_row, styled_spinbox, modal_header, modal_footer,
    stat_box, n_way_selector, status_badge, flag_note,
)

DISCHARGE_TYPE_OPTIONS = [
    ("", "Auto (from bucket style)"),
    ("centrifugal", "Force Centrifugal"),
    ("continuous", "Force Continuous"),
]

# Real liner catalogue, mirrored from chute_flow.py's ChuteFlowEngine.LINER_CATALOGUE
# -- descriptive text only here; the actual friction/thickness data the
# calculation uses lives in the backend, this is just the dropdown labels.
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
    """Discharge Section -- discharge type override, chute liner
    selection, discharge chute position/angle overrides, plus the real
    computed chute performance, maintenance, and casing-clearance data.
    No engineering math lives here; every number shown is read straight
    from results.discharge_chute / results.casing_clearance."""

    def __init__(self, inputs, results, parent=None):
        super().__init__(parent)
        self.inputs = dict(inputs)
        self.results = results or {}
        self.setWindowTitle("Discharge Section")
        self.setMinimumWidth(500)
        self.resize(520, 740)
        self.setStyleSheet(f"background-color: {PANEL};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(modal_header("Discharge Section", "CEMA 375 §5"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        body = QFrame()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(16, 16, 16, 16)
        bl.setSpacing(12)
        r = self.results
        dc = r.get("discharge_chute") or {}
        perf = dc.get("performance") or {}
        maint = dc.get("maintenance") or {}
        geom = dc.get("geometry") or {}
        cc = r.get("casing_clearance") or {}

        bl.addWidget(section_head("Discharge Type"))
        self._dtype_val = [self.inputs.get("discharge_type_override", "")]
        bl.addLayout(n_way_selector(DISCHARGE_TYPE_OPTIONS, self._dtype_val, self._on_dtype_change))
        current_type = r.get("discharge_type", "—")
        dtype_note = QLabel(
            f"Currently resolving to: {str(current_type).capitalize()} "
            f"({'auto from bucket style' if not self._dtype_val[0] else 'overridden'})."
        )
        dtype_note.setWordWrap(True)
        dtype_note.setStyleSheet(f"color: {TEXT2}; font-size: 11px;")
        bl.addWidget(dtype_note)

        if perf:
            bl.addWidget(section_head("Chute Angle"))
            adequate = perf.get("angle_adequate")
            status = "ok" if adequate is not False else "fail"
            bl.addWidget(stat_box(
                [("Chute angle", f"{fmt(perf.get('chute_angle_deg'), 1)}°"),
                 ("Min required", f"{fmt(perf.get('min_angle_deg'), 1)}°"),
                 ("Flow regime", perf.get("flow_regime", "—").replace("_", " ").title()),
                 ("Governed by", perf.get("governed_by", "—"))],
                status=status if adequate is False else None,
                note=None if adequate is not False else
                     f"Below minimum — steepen to ≥{fmt(perf.get('mass_flow_angle_deg'), 0)}° for mass flow.",
            ))
            cap = perf.get("capacity_check") or {}
            if cap:
                loading_pct = cap.get("loading_pct") or 0
                load_status = "ok" if loading_pct < 40 else ("warn" if loading_pct < 60 else "fail")
                bl.addWidget(stat_box(
                    [("Loading", f"{fmt(loading_pct, 1)}%"),
                     ("Stream depth", f"{fmt((cap.get('stream_depth_m') or 0) * 1000, 0)} mm")],
                    status=load_status,
                    note=cap.get("note"),
                ))

        bl.addWidget(section_head("Chute Liner"))
        self.liner_combo = QComboBox()
        self.liner_combo.setMinimumHeight(28)
        self.liner_combo.setStyleSheet(
            f"background-color: {PANEL2}; color: {TEXT}; border: 1px solid {BORDER}; "
            f"border-radius: 4px; padding: 5px 8px; font-size: 12px;"
        )
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
            wear_status = {"LOW": "ok", "MODERATE": "warn", "HIGH": "fail"}.get(maint.get("wear_rating") or "", None)
            bl.addWidget(stat_box(
                [("Wear rating", maint.get("wear_rating", "—")),
                 ("Plugging risk", maint.get("plugging_risk", "—")),
                 ("Dust risk", maint.get("dust_risk", "—"))],
                status=wear_status,
            ))

        # FIX (Jay: "are these meant to be outlet offset and opening
        # height for the discharge or inlet offset of the feed side and
        # is in the wrong modal?"): confirmed directly in calculations.py
        # -- this is the DISCHARGE chute's own catch-opening at the head
        # section (where material flying off the bucket discharge lands),
        # not the boot/feed inlet at the bottom (that's a separate
        # opening, handled by Feed Design's boot_inlet_height_override_mm).
        # Labels now say "Discharge Chute" explicitly instead of the bare
        # "Inlet"/"Opening" that made this genuinely ambiguous.
        bl.addWidget(section_head("Discharge Chute Position"))
        row1 = QHBoxLayout()
        self.chute_x_offset = styled_spinbox(QDoubleSpinBox())
        self.chute_x_offset.setRange(0, 500); self.chute_x_offset.setSingleStep(10)
        self.chute_x_offset.setValue(float(self.inputs.get("chute_x_offset_mm", 0)))
        row1.addLayout(field_row("Catch Opening Offset", self.chute_x_offset, "mm",
                                  note="How far the discharge chute's mouth is set back from the "
                                       "casing wall. 0 = flush with wall − 10mm clearance."))
        self.chute_opening_height = styled_spinbox(QDoubleSpinBox())
        self.chute_opening_height.setRange(0, 1000); self.chute_opening_height.setSingleStep(25)
        self.chute_opening_height.setValue(float(self.inputs.get("chute_opening_height_mm", 0)))
        row1.addLayout(field_row("Catch Opening Height", self.chute_opening_height, "mm",
                                  note="Vertical size of the discharge chute's mouth. "
                                       "0 = auto from head pulley diameter."))
        bl.addLayout(row1)

        self.chute_angle_override = styled_spinbox(QDoubleSpinBox())
        self.chute_angle_override.setRange(0, 90); self.chute_angle_override.setSingleStep(5)
        self.chute_angle_override.setValue(float(self.inputs.get("chute_angle_override_deg", 0)))
        angle_status = None
        angle_note = "0 = auto (trajectory-derived)."
        if dc.get("angle_is_override"):
            angle_status = "info"
            angle_note = f"Overriding — auto-derived value was {fmt(geom.get('back_plate_angle_deg'), 0)}°."
        bl.addLayout(field_row("Discharge Chute Back-Plate Angle Override", self.chute_angle_override, "°",
                                note=angle_note, status=angle_status))

        if geom:
            bl.addWidget(section_head("Chute Geometry"))
            bl.addWidget(stat_box([
                ("Throw distance", f"{fmt((geom.get('throw_distance_m') or 0) * 1000, 0)} mm"),
                ("Spout width", f"{fmt(geom.get('spout_width_mm'), 0)} mm"),
                ("Throat velocity", f"{fmt(geom.get('throat_velocity_mps'), 2)} m/s"),
            ]))
            if geom.get("note"):
                geom_note = QLabel(geom["note"])
                geom_note.setWordWrap(True)
                geom_note.setStyleSheet(f"color: {TEXT2}; font-size: 11px;")
                bl.addWidget(geom_note)

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