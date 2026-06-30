"""
components/takeup_edit.py -- Take-Up Selection dialog.
═══════════════════════════════════════════════════════════════════════════
First section built in its own file rather than added to the already-large
input_sidebar.py, per direct instruction once that file passed ~2,500
lines -- new sections go in their own importable module going forward.

Shared widgets (styled_spinbox, field_row, stat_box, modal_header,
modal_footer, etc.) come from dialog_helpers.py, NOT from input_sidebar.py
-- importing from input_sidebar.py here would create a circular import,
since input_sidebar.py needs to import TakeupEditDialog from this file to
wire it into the sidebar's row list.

Backend support confirmed directly before writing any UI for this
(checked models.py + a live /calculate response, not assumed):
  - takeup_type: "gravity" | "screw" | "hydraulic" | "auto" (models.py)
  - K_takeup: take-up tension factor, 0.4-0.9 (models.py)
  - takeup_screw_d_mm / takeup_screw_len_m: screw overrides (models.py)
  - takeup_hydraulic_bore_mm / takeup_hydraulic_pressure_bar: hydraulic
    overrides (models.py)
  - results already contain takeup_gravity / takeup_screw / takeup_hydraulic,
    each fully computed with override_applied/override_adequate fields,
    and a "primary": true/false flag marking which one the solver actually
    used for this design (confirmed live: requesting takeup_type="gravity"
    on a 25m elevator returns takeup_gravity.primary=true, the other two
    still computed and shown for comparison, primary=false).

This dialog shows ALL THREE computed take-up types side by side (not just
the selected one) -- the backend already computes all three regardless of
which is selected, so showing only one would hide real comparison data
the user already paid the calculation cost for.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea,
    QDoubleSpinBox,
)

from theme import PANEL, PANEL2, BORDER, TEXT, TEXT2, TEXT3, MUTED, PRIMARY, SUCCESS, WARNING, DANGER
from .dialog_helpers import (
    fmt, section_head, field_row, styled_spinbox, modal_header, modal_footer,
    stat_box, n_way_selector, status_badge, flag_note,
)

TAKEUP_TYPE_OPTIONS = [
    ("gravity", "Gravity"),
    ("screw", "Screw"),
    ("hydraulic", "Hydraulic"),
    ("auto", "Auto"),
]


def _primary_badge(is_primary):
    """Small inline tag marking whichever take-up type the solver actually
    used for this specific design -- distinct from which type the combo
    above is currently set to, since "auto" only resolves to one of the
    other three at calculation time."""
    lbl = QLabel("✓ SOLVER SELECTED THIS" if is_primary else "")
    if is_primary:
        lbl.setStyleSheet(
            f"background-color: rgba(31,184,110,.15); color: {SUCCESS}; "
            f"border: 1px solid rgba(31,184,110,.35); border-radius: 999px; "
            f"padding: 2px 9px; font-size: 9.5px; font-weight: 700;"
        )
    return lbl


class TakeupEditDialog(QDialog):
    """Take-Up Selection -- gravity / screw / hydraulic / auto, with the
    real computed result for all three shown together (the backend
    computes every option regardless of which is selected, confirmed
    directly against a live response, so hiding two of them would throw
    away comparison data already paid for). The type currently marked
    "primary" by the solver is badged, separate from whatever the combo
    above is set to -- "auto" only resolves to a specific type once the
    calculation actually runs.

    Architecture note: no buckling/tension math lives here. Every number
    shown (F_screw, d_core_min, SF_buckling, F_cylinder, counterweight
    mass, travel) is read straight from results -- this dialog only
    collects the override inputs and the take-up type selection, exactly
    the same separation every other section in this app already follows.
    """

    def __init__(self, inputs, results, parent=None):
        super().__init__(parent)
        self.inputs = dict(inputs)
        self.results = results or {}
        self.setWindowTitle("Take-Up Selection")
        self.setMinimumWidth(520)
        self.resize(560, 720)
        self.setStyleSheet(f"background-color: {PANEL};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(modal_header("Take-Up Selection", "CEMA 375 §4"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        body = QFrame()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(16, 16, 16, 16)
        bl.setSpacing(12)
        r = self.results

        bl.addWidget(section_head("Take-Up Type"))
        self._type_val = [self.inputs.get("takeup_type", "gravity")]
        bl.addLayout(n_way_selector(TAKEUP_TYPE_OPTIONS, self._type_val, self._on_type_change))
        type_note = QLabel(
            "Gravity: counterweight, recommended for H > 15m. Screw: threaded shank, "
            "short elevators H ≤ 15m. Hydraulic: cylinder, automatic constant-tension "
            "control — vendor-engineered, not a CEMA standard method (sized here using "
            "standard cylinder mechanics, flagged below). Auto: solver picks by H_m."
        )
        type_note.setWordWrap(True)
        type_note.setStyleSheet(f"color: {TEXT2}; font-size: 11px;")
        bl.addWidget(type_note)

        bl.addWidget(section_head("Take-Up Tension Factor"))
        self.k_takeup = styled_spinbox(QDoubleSpinBox())
        self.k_takeup.setRange(0.4, 0.9); self.k_takeup.setSingleStep(0.05)
        self.k_takeup.setValue(float(self.inputs.get("K_takeup", 0.7)))
        bl.addLayout(field_row(
            "K (tension factor)", self.k_takeup, "",
            note="0.7 typical for gravity take-up, 0.5 typical for screw. Affects T3 "
                 "tension sizing across the whole design, not just this section."
        ))

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background-color: {BORDER}; margin: 4px 0;")
        bl.addWidget(divider)

        # ── Gravity (no overrides -- the only "input" is structural frame
        # capacity, which isn't modeled as a numeric field anywhere in
        # this backend; verified directly, not assumed) ─────────────────
        tg = r.get("takeup_gravity") or {}
        bl.addLayout(self._section_header_row("Gravity Take-Up", tg.get("primary")))
        if tg:
            bl.addWidget(stat_box(
                [("Counterweight (net)", f"{fmt(tg.get('W_counterweight_kg_net'), 0)} kg"),
                 ("Counterweight (gross)", f"{fmt(tg.get('W_counterweight_kg_gross'), 0)} kg"),
                 ("Travel required", f"{fmt(tg.get('travel_m'), 3)} m")],
            ))
            note = QLabel(tg.get("note", ""))
            note.setWordWrap(True)
            note.setStyleSheet(f"color: {TEXT2}; font-size: 11px;")
            bl.addWidget(note)
        else:
            bl.addWidget(self._not_computed_note())

        # ── Screw ─────────────────────────────────────────────────────
        ts = r.get("takeup_screw") or {}
        bl.addLayout(self._section_header_row("Screw Take-Up", ts.get("primary")))
        if ts:
            adequate = ts.get("buckling_safe")
            status = None if adequate is not False else "fail"
            bl.addWidget(stat_box(
                [("Force", f"{fmt((ts.get('F_screw_N') or 0) / 1000, 1)} kN"),
                 ("Core dia. (min)", f"{fmt(ts.get('d_core_min_mm'), 0)} mm"),
                 ("SF buckling", fmt(ts.get("SF_buckling"), 2)),
                 ("Turns required", fmt(ts.get("turns_required"), 0))],
                status=status,
                note=ts.get("recommendation"),
            ))
            row = QHBoxLayout()
            self.screw_d_override = styled_spinbox(QDoubleSpinBox())
            self.screw_d_override.setRange(0, 200); self.screw_d_override.setSingleStep(5)
            self.screw_d_override.setValue(float(self.inputs.get("takeup_screw_d_mm", 0)))
            row.addLayout(field_row("Core Dia. Override", self.screw_d_override, "mm",
                                     note="0 = auto from buckling check."))
            self.screw_len_override = styled_spinbox(QDoubleSpinBox())
            self.screw_len_override.setRange(0, 10); self.screw_len_override.setSingleStep(0.1)
            self.screw_len_override.setValue(float(self.inputs.get("takeup_screw_len_m", 0)))
            row.addLayout(field_row("Shank Length Override", self.screw_len_override, "m",
                                     note="0 = auto-derived from required travel."))
            bl.addLayout(row)
        else:
            self.screw_d_override = styled_spinbox(QDoubleSpinBox())
            self.screw_d_override.setRange(0, 200); self.screw_d_override.setSingleStep(5)
            self.screw_d_override.setValue(float(self.inputs.get("takeup_screw_d_mm", 0)))
            self.screw_len_override = styled_spinbox(QDoubleSpinBox())
            self.screw_len_override.setRange(0, 10); self.screw_len_override.setSingleStep(0.1)
            self.screw_len_override.setValue(float(self.inputs.get("takeup_screw_len_m", 0)))
            bl.addWidget(self._not_computed_note())

        # ── Hydraulic ─────────────────────────────────────────────────
        th = r.get("takeup_hydraulic") or {}
        bl.addLayout(self._section_header_row("Hydraulic Take-Up", th.get("primary")))
        if th:
            adequate = th.get("buckling_safe")
            status = None if adequate is not False else "fail"
            bl.addWidget(flag_note("warn",
                "Sized using standard cylinder mechanics, not a published CEMA method — "
                "vendor-engineered selection. Verify against actual cylinder manufacturer data."
            ))
            bl.addWidget(stat_box(
                [("Force", f"{fmt((th.get('F_cylinder_N') or 0) / 1000, 1)} kN"),
                 ("Bore dia. (min)", f"{fmt(th.get('d_bore_min_mm'), 1)} mm"),
                 ("Stroke", f"{fmt(th.get('stroke_mm'), 0)} mm"),
                 ("SF buckling", fmt(th.get("SF_buckling"), 2))],
                status=status,
                note=th.get("recommendation"),
            ))
            row2 = QHBoxLayout()
            self.hyd_bore_override = styled_spinbox(QDoubleSpinBox())
            self.hyd_bore_override.setRange(0, 300); self.hyd_bore_override.setSingleStep(5)
            self.hyd_bore_override.setValue(float(self.inputs.get("takeup_hydraulic_bore_mm", 0)))
            row2.addLayout(field_row("Bore Dia. Override", self.hyd_bore_override, "mm",
                                      note="0 = auto from force + operating pressure."))
            self.hyd_pressure = styled_spinbox(QDoubleSpinBox())
            self.hyd_pressure.setRange(10, 350); self.hyd_pressure.setSingleStep(10)
            self.hyd_pressure.setValue(float(self.inputs.get("takeup_hydraulic_pressure_bar", 100)))
            row2.addLayout(field_row("Operating Pressure", self.hyd_pressure, "bar",
                                      note="100 bar common default — match actual power unit rating."))
            bl.addLayout(row2)
        else:
            self.hyd_bore_override = styled_spinbox(QDoubleSpinBox())
            self.hyd_bore_override.setRange(0, 300); self.hyd_bore_override.setSingleStep(5)
            self.hyd_bore_override.setValue(float(self.inputs.get("takeup_hydraulic_bore_mm", 0)))
            self.hyd_pressure = styled_spinbox(QDoubleSpinBox())
            self.hyd_pressure.setRange(10, 350); self.hyd_pressure.setSingleStep(10)
            self.hyd_pressure.setValue(float(self.inputs.get("takeup_hydraulic_pressure_bar", 100)))
            bl.addWidget(self._not_computed_note())

        bl.addStretch()
        scroll.setWidget(body)
        layout.addWidget(scroll)
        layout.addWidget(modal_footer(self))

    def _section_header_row(self, title, is_primary):
        row = QHBoxLayout()
        row.setSpacing(8)
        head = section_head(title)
        row.addWidget(head)
        row.addStretch()
        row.addWidget(_primary_badge(bool(is_primary)))
        return row

    def _not_computed_note(self):
        lbl = QLabel("Run a calculation to see this option's sizing.")
        lbl.setStyleSheet(f"color: {MUTED}; font-size: 10.5px; font-style: italic;")
        return lbl

    def _on_type_change(self, value):
        self._type_val[0] = value

    def updated_inputs(self):
        self.inputs["takeup_type"] = self._type_val[0]
        self.inputs["K_takeup"] = self.k_takeup.value()
        self.inputs["takeup_screw_d_mm"] = self.screw_d_override.value()
        self.inputs["takeup_screw_len_m"] = self.screw_len_override.value()
        self.inputs["takeup_hydraulic_bore_mm"] = self.hyd_bore_override.value()
        self.inputs["takeup_hydraulic_pressure_bar"] = self.hyd_pressure.value()
        return self.inputs