"""
components/power_edit.py -- Power Transmission dialog.
═══════════════════════════════════════════════════════════════════════════
Sixth and final core section. Shared widgets come from dialog_helpers.py --
avoids a circular import with input_sidebar.py.

Backend support confirmed directly before writing any UI for this --
including a real finding from that check, not assumed:

  GENUINELY CONSUMED (verified in calculations.py):
  - sf: motor service factor, 1.0-2.0 -- governs auto motor sizing margin
    (motor_margin_pct in results).
  - Ceff: drive efficiency factor override, 0-2.0 -- 0 = auto.
  - drive_start_type: "DOL"|"soft_start"|"VFD" -- drives the dynamic startup
    tension model (results.startup_dynamic).
  - startup_time_s_override -- 0 = auto from drive_start_type
    (DOL 2s, soft_start 5s, VFD 15s).

  REAL PYDANTIC FIELDS BUT NOT ACTUALLY CONSUMED (confirmed by exhaustive
  search -- grep for every usage across calculations.py found zero):
  - motor_kw_override, gearbox_model, drive_model. The API accepts them
    without error (they're valid model fields, and gearbox_model/drive_model
    are validated against real catalog tables), but the solver's actual
    motor/gearbox/drive selection logic never reads any of the three back.
    Same situation bearing_name was already found to be in -- shown here
    honestly as informational/BOM-reference only, not hidden and not silently
    treated as if they affect the calculation.

  results contain motor_kw, motor_sync_rpm, motor_nominal_rpm, gearbox_ratio,
  motor_margin_pct, T_Nm, startup_dynamic (T_peak_governing, startup_margin,
  mass_equivalent_kg), and shock_check (adequate_for_normal_shock,
  backstop_required) -- all fully computed; this dialog reads them.

SWEEP: CLEAN
────────────
Built entirely on dialog_helpers' shared widgets (stat_box, field_row,
flag_note, n_way_selector, ComponentPickerWidget), so it has NO bare bordered
containers, NO hand-rolled fields, NO stale rgba() literals -- it inherits
every fix automatically. Same as casing_edit.py. Only two cosmetic changes
(plain_bg, object-scoped scroll area), neither fixing a visible bug.

That is now the consistent result: every file built on the shared helpers
needed nothing; every file that hand-rolled its own field styling
(components_library_panel, material_library_panel, optimizer_panel,
service_edit, discharge_edit) carried the same two bugs.

THRESHOLD-IN-FRONTEND -- RESOLVED (TASK_LIST item 2)
Both bands below were engineering constants in this UI file, and the
startup-margin pair was ALSO duplicated in equipment_tree.py -- two copies
of one constant in two files. calculations.py now emits
`motor_margin_status` and `startup_margin_status`; both files read the one
verdict. Numbers relocated, not retuned.

Previously:
────────────────────────────────────────────
  * margin_status = "ok" if margin >= 10 else ("warn" if margin >= 0 ...)
    -- the 10% motor-margin band.
  * status = "ok" if startup_margin >= 1.1 else ("warn" if >= 1.0 ...)
    -- the 1.1 / 1.0 startup-margin bands.

Both are engineering constants living in the frontend. motor_margin_pct and
startup_margin are computed in the backend; the verdicts should come from
there too, the way cap_ok / speed_ok / cr_ok / l10_ok already do. Values
preserved exactly. See TASK_LIST.md item 2.

RENAMED LOCAL (real shadowing bug avoided)
──────────────────────────────────────────
`margin` was reused for BOTH motor_margin_pct and startup_margin in the same
scope. Harmless as written (the reads are sequential), but it is one edit away
from a silent cross-wiring of two unrelated engineering quantities. Renamed to
motor_margin / startup_margin.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QFrame, QScrollArea, QDoubleSpinBox,
)

from theme import PANEL, TEXT2, scoped, plain_bg
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
    """Power Transmission -- motor service factor, drive efficiency, starting
    method, plus the real computed motor/gearbox sizing and dynamic startup
    analysis. Gearbox/Drive/Motor override fields are shown honestly as
    informational-only, because the backend doesn't read them back into the
    calculation yet."""

    def __init__(self, inputs, results, parent=None):
        super().__init__(parent)
        self.inputs = dict(inputs)
        self.results = results or {}
        self.setWindowTitle("Power Transmission")
        self.setMinimumWidth(480)
        self.resize(500, 760)
        self.setStyleSheet(plain_bg(self, PANEL))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(modal_header("Power Transmission", "CEMA 375 §4"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(scoped(scroll, "border: none; background: transparent;"))
        body = QFrame()
        body.setStyleSheet(scoped(body, "background-color: transparent; border: none;"))
        bl = QVBoxLayout(body)
        bl.setContentsMargins(16, 16, 16, 16)
        bl.setSpacing(12)
        r = self.results

        # ── Motor sizing (computed) ──────────────────────────────────
        bl.addWidget(section_head("Motor Sizing"))
        bl.addWidget(stat_box([
            ("Motor", f"{fmt(r.get('motor_kw'), 0)} kW"),
            ("Sync RPM", f"{fmt(r.get('motor_sync_rpm'), 0)}"),
            ("Nominal RPM", f"{fmt(r.get('motor_nominal_rpm'), 0)}"),
        ]))

        motor_margin = r.get("motor_margin_pct")
        if motor_margin is not None:
            # RESOLVED (item 2): the 10% band now comes from the backend as
            # `motor_margin_status`, computed alongside motor_margin_pct.
            margin_status = r.get("motor_margin_status") or "fail"
            bl.addWidget(stat_box(
                [("Margin", f"{fmt(motor_margin, 1)}%"),
                 ("Output Torque", f"{fmt(r.get('T_Nm'), 0)} Nm"),
                 ("Gearbox Ratio", f"{fmt(r.get('gearbox_ratio'), 1)}:1")],
                status=margin_status,
            ))

        self.sf = styled_spinbox(QDoubleSpinBox())
        self.sf.setRange(1.0, 2.0)
        self.sf.setSingleStep(0.05)
        self.sf.setValue(float(self.inputs.get("sf", 1.25)))
        bl.addLayout(field_row(
            "Motor Service Factor", self.sf, "",
            note="1.25 typical. Governs auto motor sizing margin above."))

        self.ceff = styled_spinbox(QDoubleSpinBox())
        self.ceff.setRange(0, 2.0)
        self.ceff.setSingleStep(0.05)
        self.ceff.setValue(float(self.inputs.get("Ceff", 0)))
        bl.addLayout(field_row(
            "Drive Efficiency Override", self.ceff, "",
            note="0 = auto (typical 1.10-1.30). Set explicitly to match a known "
                 "gearbox/coupling efficiency datasheet."))

        # ── Informational-only selections ────────────────────────────
        bl.addWidget(section_head("Motor Selection (informational only)"))
        self.motor_kw_override = styled_spinbox(QDoubleSpinBox())
        self.motor_kw_override.setRange(0, 1000)
        self.motor_kw_override.setSingleStep(5)
        self.motor_kw_override.setValue(
            float(self.inputs.get("motor_kw_override", 0)))
        bl.addLayout(field_row(
            "Motor kW Override", self.motor_kw_override, "kW",
            note="Confirmed directly: this field is accepted by the API but not yet "
                 "read back into the calculation anywhere in the solver. Shown for "
                 "BOM/reference purposes only — the Motor Sizing numbers above are "
                 "unaffected by it.",
            status="info",
        ))

        bl.addWidget(section_head("Gearbox Selection (informational only)"))
        self.gearbox_picker = ComponentPickerWidget(
            "/components/gearboxes",
            {"torque_min": r.get("T_Nm") or 0},
            lambda row: (f"{row.get('name')}  Tn={row.get('Tn')}Nm  "
                         f"i={row.get('ratio_min')}-{row.get('ratio_max')}:1"),
            self.inputs.get("gearbox_model", ""), None, "Gearbox Model",
            note="Same caveat as Motor kW above — the solver's auto gearbox sizing "
                 "logic doesn't read this back yet. Live catalog lookup, BOM/reference "
                 "only.",
        )
        bl.addWidget(self.gearbox_picker)

        bl.addWidget(section_head("Drive / Starter Selection (informational only)"))
        self.drive_picker = ComponentPickerWidget(
            "/components/drives",
            {"pkw_min": r.get("motor_kw") or 0},
            lambda row: (f"{row.get('name')}  P_max={row.get('Pkw_max')}kW  "
                         f"{row.get('control', '')}"),
            self.inputs.get("drive_model", ""), None, "Drive / Starter Model",
            note="Same caveat — BOM/reference only, not yet read back into the "
                 "calculation.",
        )
        bl.addWidget(self.drive_picker)

        # ── Starting method ──────────────────────────────────────────
        bl.addWidget(section_head("Starting Method"))
        self._start_val = [self.inputs.get("drive_start_type", "soft_start")]
        bl.addLayout(n_way_selector(
            DRIVE_START_OPTIONS, self._start_val, self._on_start_change))

        self.startup_time_override = styled_spinbox(QDoubleSpinBox())
        self.startup_time_override.setRange(0, 60)
        self.startup_time_override.setSingleStep(1)
        self.startup_time_override.setValue(
            float(self.inputs.get("startup_time_s_override", 0)))
        bl.addLayout(field_row(
            "Startup Time Override", self.startup_time_override, "s",
            note="0 = auto from starting method (DOL 2s, soft start 5s, VFD 15s). Set "
                 "explicitly when the actual VFD/soft-starter ramp profile is known."
        ))

        # ── Startup tension (computed) ───────────────────────────────
        sd = r.get("startup_dynamic") or {}
        if sd:
            bl.addWidget(section_head("Startup Tension (computed)"))
            # Renamed from `margin` -- it previously shadowed motor_margin_pct
            # in the same scope. Harmless as written, but one edit from silently
            # cross-wiring two unrelated engineering quantities.
            startup_margin = sd.get("startup_margin")
            # RESOLVED (item 2): the 1.1 / 1.0 bands were ALSO duplicated in
            # equipment_tree.py. Both now read one backend verdict.
            status = r.get("startup_margin_status") or "fail"
            bl.addWidget(stat_box(
                [("Peak tension",
                  f"{fmt((sd.get('T_peak_governing') or 0) / 1000, 1)} kN"),
                 ("Belt rated",
                  f"{fmt((sd.get('belt_rated_N') or 0) / 1000, 1)} kN"),
                 ("Margin", fmt(startup_margin, 2)),
                 ("Governed by", sd.get("governing_method", "—"))],
                status=status,
            ))
            if sd.get("note"):
                note_lbl = QLabel(sd["note"])
                note_lbl.setWordWrap(True)
                note_lbl.setStyleSheet(f"color: {TEXT2}; font-size: 11px;")
                bl.addWidget(note_lbl)

        # ── Shock protection ─────────────────────────────────────────
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