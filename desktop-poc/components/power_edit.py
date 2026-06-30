"""
components/power_edit.py -- Power Transmission dialog.
═══════════════════════════════════════════════════════════════════════════
Sixth and final core section. Shared widgets come from dialog_helpers.py,
same reasoning as the others -- avoids a circular import with
input_sidebar.py.

Backend support confirmed directly before writing any UI for this --
including a real, important finding from that check, not assumed:

  GENUINELY CONSUMED (verified in calculations.py):
  - sf: motor service factor, 1.0-2.0 (models.py) -- governs auto motor
    sizing margin (motor_margin_pct in results).
  - Ceff: drive efficiency factor override, 0-2.0 (models.py) -- 0 = auto.
  - drive_start_type: "DOL"|"soft_start"|"VFD" (models.py) -- drives the
    dynamic startup tension model (results.startup_dynamic).
  - startup_time_s_override: time to reach full belt speed (models.py) --
    0 = auto from drive_start_type (DOL 2s, soft_start 5s, VFD 15s).

  REAL PYDANTIC FIELDS BUT NOT ACTUALLY CONSUMED (confirmed by exhaustive
  search -- grep for every usage across calculations.py found zero):
  - motor_kw_override, gearbox_model, drive_model. The API will accept
    them without error (they're valid model fields, and gearbox_model/
    drive_model are validated against real catalog tables), but the
    solver's actual motor/gearbox/drive selection logic (select_motor(),
    etc.) never reads any of the three back. Same situation bearing_name
    was already found to be in (ShaftEditDialog) -- shown here honestly
    as informational/BOM-reference only, using the same live
    ComponentPickerWidget catalog lookups as bearings already use, not
    hidden and not silently treated as if they affect the calculation.

  results already contain motor_kw, motor_sync_rpm, motor_nominal_rpm,
  gearbox_ratio, motor_margin_pct, T_Nm, startup_dynamic (T_peak_governing,
  startup_margin, mass_equivalent_kg), and shock_check
  (adequate_for_normal_shock, backstop_required) -- all fully computed,
  this dialog reads them rather than recomputing anything.
"""
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QFrame, QScrollArea, QDoubleSpinBox

from theme import PANEL, TEXT2
from .dialog_helpers import (
    fmt, section_head, field_row, styled_spinbox, modal_header, modal_footer,
    stat_box, n_way_selector, flag_note, ComponentPickerWidget,
)

DRIVE_START_OPTIONS = [
    ("DOL", "DOL (1-3s, highest peak tension)"),
    ("soft_start", "Soft Start (3-8s, default)"),
    ("VFD", "VFD (5-30s, lowest peak tension)"),
]


class PowerEditDialog(QDialog):
    """Power Transmission -- motor service factor, drive efficiency,
    starting method, plus the real computed motor/gearbox sizing and
    dynamic startup analysis. Gearbox/Drive/Motor override fields are
    shown honestly as informational-only where the backend doesn't
    actually read them back into the calculation yet."""

    def __init__(self, inputs, results, parent=None):
        super().__init__(parent)
        self.inputs = dict(inputs)
        self.results = results or {}
        self.setWindowTitle("Power Transmission")
        self.setMinimumWidth(480)
        self.resize(500, 760)
        self.setStyleSheet(f"background-color: {PANEL};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(modal_header("Power Transmission", "CEMA 375 §4"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        body = QFrame()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(16, 16, 16, 16)
        bl.setSpacing(12)
        r = self.results

        bl.addWidget(section_head("Motor Sizing"))
        bl.addWidget(stat_box([
            ("Motor", f"{fmt(r.get('motor_kw'), 0)} kW"),
            ("Sync RPM", f"{fmt(r.get('motor_sync_rpm'), 0)}"),
            ("Nominal RPM", f"{fmt(r.get('motor_nominal_rpm'), 0)}"),
        ]))
        margin = r.get("motor_margin_pct")
        if margin is not None:
            margin_status = "ok" if margin >= 10 else ("warn" if margin >= 0 else "fail")
            bl.addWidget(stat_box(
                [("Margin", f"{fmt(margin, 1)}%"), ("Output Torque", f"{fmt(r.get('T_Nm'), 0)} Nm"),
                 ("Gearbox Ratio", f"{fmt(r.get('gearbox_ratio'), 1)}:1")],
                status=margin_status,
            ))

        self.sf = styled_spinbox(QDoubleSpinBox())
        self.sf.setRange(1.0, 2.0); self.sf.setSingleStep(0.05)
        self.sf.setValue(float(self.inputs.get("sf", 1.25)))
        bl.addLayout(field_row("Motor Service Factor", self.sf, "",
                                note="1.25 typical. Governs auto motor sizing margin above."))

        self.ceff = styled_spinbox(QDoubleSpinBox())
        self.ceff.setRange(0, 2.0); self.ceff.setSingleStep(0.05)
        self.ceff.setValue(float(self.inputs.get("Ceff", 0)))
        bl.addLayout(field_row("Drive Efficiency Override", self.ceff, "",
                                note="0 = auto (typical 1.10-1.30). Set explicitly to match "
                                     "a known gearbox/coupling efficiency datasheet."))

        bl.addWidget(section_head("Motor Selection (informational only)"))
        self.motor_kw_override = styled_spinbox(QDoubleSpinBox())
        self.motor_kw_override.setRange(0, 1000); self.motor_kw_override.setSingleStep(5)
        self.motor_kw_override.setValue(float(self.inputs.get("motor_kw_override", 0)))
        bl.addLayout(field_row(
            "Motor kW Override", self.motor_kw_override, "kW",
            note="Confirmed directly: this field is accepted by the API but not yet read "
                 "back into the calculation anywhere in the solver. Shown for BOM/reference "
                 "purposes only -- the Motor Sizing numbers above are unaffected by it.",
            status="info",
        ))

        bl.addWidget(section_head("Gearbox Selection (informational only)"))
        self.gearbox_picker = ComponentPickerWidget(
            "/components/gearboxes",
            {"torque_min": r.get("T_Nm") or 0},
            lambda row: f"{row.get('name')}  Tn={row.get('Tn')}Nm  i={row.get('ratio_min')}-{row.get('ratio_max')}:1",
            self.inputs.get("gearbox_model", ""), None, "Gearbox Model",
            note="Same caveat as Motor kW above -- the solver's auto gearbox sizing logic "
                 "doesn't read this back yet. Live catalog lookup, BOM/reference only.",
        )
        bl.addWidget(self.gearbox_picker)

        bl.addWidget(section_head("Drive / Starter Selection (informational only)"))
        self.drive_picker = ComponentPickerWidget(
            "/components/drives",
            {"pkw_min": r.get("motor_kw") or 0},
            lambda row: f"{row.get('name')}  P_max={row.get('Pkw_max')}kW  {row.get('control', '')}",
            self.inputs.get("drive_model", ""), None, "Drive / Starter Model",
            note="Same caveat -- BOM/reference only, not yet read back into the calculation.",
        )
        bl.addWidget(self.drive_picker)

        bl.addWidget(section_head("Starting Method"))
        self._start_val = [self.inputs.get("drive_start_type", "soft_start")]
        bl.addLayout(n_way_selector(DRIVE_START_OPTIONS, self._start_val, self._on_start_change))
        self.startup_time_override = styled_spinbox(QDoubleSpinBox())
        self.startup_time_override.setRange(0, 60); self.startup_time_override.setSingleStep(1)
        self.startup_time_override.setValue(float(self.inputs.get("startup_time_s_override", 0)))
        bl.addLayout(field_row(
            "Startup Time Override", self.startup_time_override, "s",
            note="0 = auto from starting method (DOL 2s, soft start 5s, VFD 15s). Set "
                 "explicitly when the actual VFD/soft-starter ramp profile is known."
        ))

        sd = r.get("startup_dynamic") or {}
        if sd:
            bl.addWidget(section_head("Startup Tension (computed)"))
            margin = sd.get("startup_margin")
            status = "ok" if (margin or 0) >= 1.1 else ("warn" if (margin or 0) >= 1.0 else "fail")
            bl.addWidget(stat_box(
                [("Peak tension", f"{fmt((sd.get('T_peak_governing') or 0) / 1000, 1)} kN"),
                 ("Belt rated", f"{fmt((sd.get('belt_rated_N') or 0) / 1000, 1)} kN"),
                 ("Margin", fmt(margin, 2)),
                 ("Governed by", sd.get("governing_method", "—"))],
                status=status,
            ))
            if sd.get("note"):
                note_lbl = QLabel(sd["note"])
                note_lbl.setWordWrap(True)
                note_lbl.setStyleSheet(f"color: {TEXT2}; font-size: 11px;")
                bl.addWidget(note_lbl)

        sc = r.get("shock_check") or {}
        if sc:
            bl.addWidget(section_head("Shock Protection"))
            adequate = sc.get("adequate_for_normal_shock")
            bl.addWidget(flag_note(
                "ok" if adequate else "warn",
                sc.get("recommendation", "")
            ))

        bl.addStretch()
        scroll.setWidget(body)
        layout.addWidget(scroll)
        layout.addWidget(modal_footer(self))

    def _on_start_change(self, value):
        self._start_val[0] = value

    def updated_inputs(self):
        self.inputs["sf"] = self.sf.value()
        self.inputs["Ceff"] = self.ceff.value()
        self.inputs["motor_kw_override"] = self.motor_kw_override.value()
        self.inputs["gearbox_model"] = self.gearbox_picker.value()
        self.inputs["drive_model"] = self.drive_picker.value()
        self.inputs["drive_start_type"] = self._start_val[0]
        self.inputs["startup_time_s_override"] = self.startup_time_override.value()
        return self.inputs