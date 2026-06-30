"""
components/feed_edit.py -- Feed Design dialog.
═══════════════════════════════════════════════════════════════════════════
Second section built in its own file, after takeup_edit.py, per the
established convention -- shared widgets come from dialog_helpers.py, not
input_sidebar.py, to avoid a circular import (input_sidebar.py needs to
import FeedEditDialog to wire it into the sidebar's row list).

Backend support confirmed directly before writing any UI for this:
  - Genuinely only ONE real override field exists: boot_inlet_height_override_mm
    (models.py) -- confirmed by exhaustive search, not assumed. This is
    the boot/feed inlet at the BOTTOM of the elevator -- the opening
    material enters through -- a separate thing from the discharge
    chute's catch-opening at the head section (Discharge Section's
    chute_x_offset_mm/chute_opening_height_mm). There is no surge-time
    override, no feeder-rate override, no clearance override anywhere
    in this backend; this dialog doesn't invent controls for things that
    don't have a real backend field behind them.
  - results.feed_design is a real, already-computed dict, but its shape
    BRANCHES depending on discharge type -- confirmed against two live
    /calculate responses, not assumed:
      continuous (spout-fed):  loading_leg_height_mm, loading_leg_width_mm,
                                spout_angle_deg, inlet_width_mm,
                                inlet_height_used_mm
      centrifugal (digging):   material_depth_mm, dig_zone_length_mm,
                                V_dig_m3, V_dig_litres
    Both branches share: loading_type, loading_note, Q_volumetric_m3s/h,
    v_feed_mps, V_surge_m3/litres, t_surge_s, boot_casing_height_mm,
    boot_pulley_radius_mm, bucket_projection_mm, bucket_depth_mm,
    clearance_mm, warnings. This dialog shows the shared fields always,
    and only the branch-specific fields that are actually present in the
    current response -- never both, never invented placeholders for the
    branch that isn't active.
"""
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QFrame, QScrollArea, QDoubleSpinBox

from theme import PANEL, TEXT2, MUTED
from .dialog_helpers import fmt, section_head, field_row, styled_spinbox, modal_header, modal_footer, stat_box, flag_note


class FeedEditDialog(QDialog):
    """Feed Design -- the boot inlet opening override, plus the real
    computed feed geometry (loading type, surge volume, boot casing
    height). No engineering math lives here; every number shown is read
    straight from results.feed_design, which already branches correctly
    on discharge type server-side."""

    def __init__(self, inputs, results, parent=None):
        super().__init__(parent)
        self.inputs = dict(inputs)
        self.results = results or {}
        self.setWindowTitle("Feed Design")
        self.setMinimumWidth(460)
        self.resize(480, 620)
        self.setStyleSheet(f"background-color: {PANEL};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(modal_header("Feed Design", "CEMA 375 §2f"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        body = QFrame()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(16, 16, 16, 16)
        bl.setSpacing(12)

        fd = self.results.get("feed_design") or {}

        if fd:
            bl.addWidget(section_head("Loading Type"))
            type_lbl = QLabel(fd.get("loading_type", "—"))
            type_lbl.setStyleSheet(f"color: {TEXT2}; font-size: 13px; font-weight: 700;")
            bl.addWidget(type_lbl)
            note_lbl = QLabel(fd.get("loading_note", ""))
            note_lbl.setWordWrap(True)
            # FIX (Jay: "text rendering is very small and illegible
            # especially on the grey/light blue headings and texts inside
            # of advisories"): TEXT3 (used here previously) and MUTED are
            # the literal same low-contrast color in theme.py -- this is
            # TEXT2 now, the same legibility pass applied across every
            # modal this round.
            note_lbl.setStyleSheet(f"color: {TEXT2}; font-size: 11.5px; line-height: 140%;")
            bl.addWidget(note_lbl)

            bl.addWidget(section_head("Volumetric Flow"))
            bl.addWidget(stat_box([
                ("Flow rate", f"{fmt(fd.get('Q_volumetric_m3h'), 1)} m³/h"),
                ("Feed velocity", f"{fmt(fd.get('v_feed_mps'), 2)} m/s"),
            ]))

            # ── Continuous (spout-fed) specific fields, only shown when
            # actually present in this response -- not invented for a
            # centrifugal design where they don't apply.
            if "loading_leg_height_mm" in fd:
                bl.addWidget(section_head("Loading Leg (Spout Feed)"))
                bl.addWidget(stat_box([
                    ("Leg height", f"{fmt(fd.get('loading_leg_height_mm'), 0)} mm"),
                    ("Leg width", f"{fmt(fd.get('loading_leg_width_mm'), 0)} mm"),
                    ("Spout angle", f"{fmt(fd.get('spout_angle_deg'), 0)}°"),
                ]))

            # ── Centrifugal (digging) specific fields, same logic.
            if "dig_zone_length_mm" in fd:
                bl.addWidget(section_head("Digging Zone"))
                bl.addWidget(stat_box([
                    ("Material depth", f"{fmt(fd.get('material_depth_mm'), 0)} mm"),
                    ("Dig zone length", f"{fmt(fd.get('dig_zone_length_mm'), 0)} mm"),
                    ("Volume", f"{fmt(fd.get('V_dig_litres'), 1)} L"),
                ]))

            bl.addWidget(section_head("Boot Inlet Opening"))
            bl.addWidget(stat_box([
                ("Width", f"{fmt(fd.get('inlet_width_mm'), 0)} mm"),
                ("Height (used)", f"{fmt(fd.get('inlet_height_used_mm'), 0)} mm"),
            ]))
            self.inlet_override = styled_spinbox(QDoubleSpinBox())
            self.inlet_override.setRange(0, 2000); self.inlet_override.setSingleStep(25)
            self.inlet_override.setValue(float(self.inputs.get("boot_inlet_height_override_mm", 0)))
            bl.addLayout(field_row(
                "Boot Inlet Height Override", self.inlet_override, "mm",
                note="The material-entry opening at the BOTTOM of the elevator (boot section) -- "
                     "not the discharge chute's catch-opening at the head, which lives in "
                     "Discharge Section instead. 0 = auto from bucket projection (centrifugal) "
                     "or loading leg dimensions (continuous)."
            ))

            bl.addWidget(section_head("Surge Capacity"))
            bl.addWidget(stat_box([
                ("Surge volume", f"{fmt(fd.get('V_surge_litres'), 1)} L"),
                ("Surge time", f"{fmt(fd.get('t_surge_s'), 1)} s"),
            ]))

            bl.addWidget(section_head("Boot Geometry"))
            bl.addWidget(stat_box([
                ("Boot casing height", f"{fmt(fd.get('boot_casing_height_mm'), 0)} mm"),
                ("Boot pulley radius", f"{fmt(fd.get('boot_pulley_radius_mm'), 0)} mm"),
                ("Bucket projection", f"{fmt(fd.get('bucket_projection_mm'), 0)} mm"),
                ("Clearance", f"{fmt(fd.get('clearance_mm'), 0)} mm"),
            ]))

            warnings = fd.get("warnings") or []
            if warnings:
                bl.addWidget(section_head("Warnings"))
                warn_box = QVBoxLayout()
                warn_box.setSpacing(6)
                for w in warnings:
                    flag_note("warn", w, parent_layout=warn_box)
                bl.addLayout(warn_box)
        else:
            self.inlet_override = styled_spinbox(QDoubleSpinBox())
            self.inlet_override.setRange(0, 2000); self.inlet_override.setSingleStep(25)
            self.inlet_override.setValue(float(self.inputs.get("boot_inlet_height_override_mm", 0)))
            placeholder = QLabel("Run a calculation to see feed geometry.")
            placeholder.setStyleSheet(f"color: {TEXT2}; font-size: 11px; font-style: italic;")
            bl.addWidget(placeholder)

        bl.addStretch()
        scroll.setWidget(body)
        layout.addWidget(scroll)
        layout.addWidget(modal_footer(self))

    def updated_inputs(self):
        self.inputs["boot_inlet_height_override_mm"] = self.inlet_override.value()
        return self.inputs