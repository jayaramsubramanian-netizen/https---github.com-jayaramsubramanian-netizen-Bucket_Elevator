"""
components/casing_edit.py -- Casing Design dialog.
═══════════════════════════════════════════════════════════════════════════
Fourth section built in its own file, after takeup_edit.py, feed_edit.py,
discharge_edit.py. Shared widgets come from dialog_helpers.py, same
reasoning as the others -- avoids a circular import with input_sidebar.py.

Backend support confirmed directly before writing any UI for this:
  - wind_pressure_pa: design wind pressure for panel deflection check
    (models.py). Default 800 Pa (open industrial); 600 Pa sheltered,
    1200 Pa exposed coastal, per AS1170.2 / ASCE 7-22 reference in the
    field's own description.
  - casing_t_override_mm: casing plate thickness override (models.py).
    0 = auto from panel deflection analysis.
  - results already contain casing_t_mm, casing_panel (deflection/stress/
    SF_yield/status), casing_stiffener (max/recommended spacing), and
    casing_bolts (seam + stiffener-band bolt counts) -- all fully
    computed, this dialog reads them rather than recomputing anything.

Built using the modernized status-icon system from the start (see
dialog_helpers.py's status_badge()/flag_note()) -- no colored-border
boxes anywhere in this file.
"""
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QFrame, QScrollArea, QDoubleSpinBox

from theme import PANEL, TEXT, TEXT2
from .dialog_helpers import fmt, section_head, field_row, styled_spinbox, modal_header, modal_footer, stat_box


class CasingEditDialog(QDialog):
    """Casing Design -- wind pressure and plate thickness override, plus
    the real computed panel deflection check, stiffener spacing, and
    bolt count. No engineering math lives here; every number shown is
    read straight from results.casing_panel / casing_stiffener /
    casing_bolts."""

    def __init__(self, inputs, results, parent=None):
        super().__init__(parent)
        self.inputs = dict(inputs)
        self.results = results or {}
        self.setWindowTitle("Casing Design")
        self.setMinimumWidth(460)
        self.resize(480, 640)
        self.setStyleSheet(f"background-color: {PANEL};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(modal_header("Casing Design", "CEMA 375 §7"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        body = QFrame()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(16, 16, 16, 16)
        bl.setSpacing(12)
        r = self.results
        cp = r.get("casing_panel") or {}
        cs = r.get("casing_stiffener") or {}
        cb = r.get("casing_bolts") or {}

        bl.addWidget(section_head("Design Wind Pressure"))
        self.wind_pressure = styled_spinbox(QDoubleSpinBox())
        self.wind_pressure.setRange(0, 5000); self.wind_pressure.setSingleStep(50)
        self.wind_pressure.setValue(float(self.inputs.get("wind_pressure_pa", 800)))
        bl.addLayout(field_row(
            "Wind Pressure", self.wind_pressure, "Pa",
            note="600 Pa sheltered · 800 Pa open industrial (default) · 1200 Pa exposed "
                 "coastal. Ref: AS1170.2 / ASCE 7-22."
        ))

        if cp:
            bl.addWidget(section_head("Panel Deflection"))
            status_map = {"ok": "ok", "warn": "warn", "fail": "fail"}
            status = status_map.get(cp.get("status") or "", None)
            bl.addWidget(stat_box(
                [("Deflection", f"{fmt(cp.get('delta_actual_mm'), 2)} mm"),
                 ("Allowable (L/360)", f"{fmt(cp.get('delta_allow_mm'), 2)} mm"),
                 ("Max stress", f"{fmt(cp.get('sigma_max_MPa'), 1)} MPa"),
                 ("SF yield", fmt(cp.get("SF_yield"), 1))],
                status=status,
                note=cp.get("recommendation"),
            ))

        bl.addWidget(section_head("Plate Thickness"))
        if cp:
            bl.addWidget(stat_box([
                ("Calculated", f"{fmt(cp.get('t_calc_mm'), 1)} mm"),
                ("In use", f"{fmt(cp.get('t_use_mm'), 1)} mm"),
                ("Panel pitch", f"{fmt(cp.get('a_mm'), 0)} mm"),
            ]))
        self.t_override = styled_spinbox(QDoubleSpinBox())
        self.t_override.setRange(0, 50); self.t_override.setSingleStep(1)
        self.t_override.setValue(float(self.inputs.get("casing_t_override_mm", 0)))
        override_status = "info" if cp.get("override_applied") else None
        bl.addLayout(field_row(
            "Plate Thickness Override", self.t_override, "mm",
            note="0 = auto-calculate from panel deflection analysis. Set to a preferred "
                 "standard plate thickness (e.g. 3, 4, 5, 6, 8) — solver re-checks "
                 "deflection with the specified thickness.",
            status=override_status,
        ))

        if cs:
            bl.addWidget(section_head("Stiffener Spacing"))
            bl.addWidget(stat_box([
                ("Max spacing", f"{fmt(cs.get('max_spacing_mm'), 0)} mm"),
                ("Recommended", f"{fmt(cs.get('recommended_mm'), 0)} mm"),
                ("Deflection limit", cs.get("defl_limit", "—")),
            ]))
            if cs.get("note"):
                note_lbl = QLabel(cs["note"])
                note_lbl.setWordWrap(True)
                note_lbl.setStyleSheet(f"color: {TEXT2}; font-size: 11px;")
                bl.addWidget(note_lbl)

        if cb:
            bl.addWidget(section_head("Fastener Count"))
            bl.addWidget(stat_box([
                ("Bolt size", cb.get("bolt_size", "—")),
                ("Seam bolts", str(cb.get("n_bolts_seams", "—"))),
                ("Stiffener bolts", str(cb.get("n_bolts_stiffeners", "—"))),
                ("Total", str(cb.get("n_bolts_total", "—"))),
            ]))

        bl.addStretch()
        scroll.setWidget(body)
        layout.addWidget(scroll)
        layout.addWidget(modal_footer(self))

    def updated_inputs(self):
        self.inputs["wind_pressure_pa"] = self.wind_pressure.value()
        self.inputs["casing_t_override_mm"] = self.t_override.value()
        return self.inputs