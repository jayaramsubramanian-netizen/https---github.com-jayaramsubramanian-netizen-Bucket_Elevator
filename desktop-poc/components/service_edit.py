"""
components/service_edit.py -- Service Conditions dialog.
═══════════════════════════════════════════════════════════════════════════
Fifth section built in its own file. Shared widgets come from
dialog_helpers.py, same reasoning as the others -- avoids a circular
import with input_sidebar.py.

Backend support confirmed directly before writing any UI for this:
  - environment: "dry"|"humid"|"wet"|"submerged"|"corrosive" (models.py).
    Confirmed genuinely consumed in TWO places in the main calculation
    flow, not a stub: (1) drives pulley_lagging() selection -- wet/
    submerged applies a 0.85 friction-degradation factor, humid 0.92
    (calculations.py); (2) gates the bucket-material corrosion-
    suitability check (a "corrosive" environment + a bucket material
    with no corrosion resistance fails the check).
  - mu: belt-pulley friction coefficient, 0.1-0.6 (models.py). Feeds
    directly into the Euler/Eytelwein slip check and wrap-angle
    recommendation already shown elsewhere in this app (Belt Selection,
    Head & Tail Pulley) -- this is the one place to actually change it.
  - results already contain the real computed `lagging` object (mu_dry/
    mu_wet/mu_operating/slip_safe/lagging_type) reflecting whichever
    environment is currently set -- this dialog reads it, doesn't
    recompute anything.
"""
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QFrame, QScrollArea, QDoubleSpinBox, QComboBox

from theme import PANEL, PANEL2, BORDER, TEXT, TEXT2
from .dialog_helpers import fmt, section_head, field_row, styled_spinbox, modal_header, modal_footer, stat_box, flag_note

ENVIRONMENT_OPTIONS = [
    ("dry", "Dry — standard indoor"),
    ("humid", "Humid — moisture > 15% or condensing"),
    ("wet", "Wet — water spray / washdown"),
    ("submerged", "Submerged — submerged boot section"),
    ("corrosive", "Corrosive — chemical exposure"),
]


class ServiceEditDialog(QDialog):
    """Service Conditions -- operating environment and belt-pulley
    friction coefficient, plus the real computed lagging selection and
    any environment-driven material suitability flags. No engineering
    math lives here; every number shown is read straight from
    results.lagging / results.checks."""

    def __init__(self, inputs, results, parent=None):
        super().__init__(parent)
        self.inputs = dict(inputs)
        self.results = results or {}
        self.setWindowTitle("Service Conditions")
        self.setMinimumWidth(460)
        self.resize(480, 560)
        self.setStyleSheet(f"background-color: {PANEL};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(modal_header("Service Conditions", "CEMA 375 §3"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        body = QFrame()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(16, 16, 16, 16)
        bl.setSpacing(12)
        r = self.results
        lagging = r.get("lagging") or {}

        bl.addWidget(section_head("Operating Environment"))
        self.env_combo = QComboBox()
        self.env_combo.setMinimumHeight(28)
        self.env_combo.setStyleSheet(
            f"background-color: {PANEL2}; color: {TEXT}; border: 1px solid {BORDER}; "
            f"border-radius: 4px; padding: 5px 8px; font-size: 12px;"
        )
        current_env = self.inputs.get("environment", "dry")
        for i, (val, text) in enumerate(ENVIRONMENT_OPTIONS):
            self.env_combo.addItem(text, val)
            if val == current_env:
                self.env_combo.setCurrentIndex(i)
        bl.addWidget(self.env_combo)
        env_note = QLabel(
            "Drives pulley lagging selection (wet/submerged degrades friction by 15%, "
            "humid by 8%) and bucket-material corrosion suitability."
        )
        env_note.setWordWrap(True)
        env_note.setStyleSheet(f"color: {TEXT2}; font-size: 11px;")
        bl.addWidget(env_note)

        bl.addWidget(section_head("Belt-Pulley Friction Coefficient"))
        self.mu = styled_spinbox(QDoubleSpinBox())
        self.mu.setRange(0.1, 0.6); self.mu.setSingleStep(0.05)
        self.mu.setValue(float(self.inputs.get("mu", 0.35)))
        bl.addLayout(field_row(
            "μ (mu)", self.mu, "",
            note="0.35 typical bare steel pulley. Feeds the Euler/Eytelwein slip check "
                 "and wrap-angle recommendation shown in Belt Selection and Head & Tail Pulley."
        ))

        if lagging:
            bl.addWidget(section_head("Pulley Lagging (computed)"))
            bl.addWidget(stat_box([
                ("Type", str(lagging.get("lagging_type", "—")).replace("_", " ").title()),
                ("μ dry", fmt(lagging.get("mu_dry"), 2)),
                ("μ wet", fmt(lagging.get("mu_wet"), 2)),
                ("μ operating", fmt(lagging.get("mu_operating"), 2)),
            ]))
            slip_safe = lagging.get("slip_safe")
            if slip_safe is not None:
                bl.addWidget(flag_note(
                    "ok" if slip_safe else "fail",
                    f"Euler ratio {fmt(lagging.get('euler_ratio_lagged'), 3)} — "
                    f"{'slip safe' if slip_safe else 'SLIP RISK at this environment/friction setting'}."
                ))
            if lagging.get("recommendation"):
                rec_lbl = QLabel(lagging["recommendation"])
                rec_lbl.setWordWrap(True)
                rec_lbl.setStyleSheet(f"color: {TEXT2}; font-size: 11px;")
                bl.addWidget(rec_lbl)
        else:
            placeholder = QLabel("Run a calculation to see lagging selection "
                                  "(not applicable for chain drives).")
            placeholder.setStyleSheet(f"color: {TEXT2}; font-size: 11px; font-style: italic;")
            bl.addWidget(placeholder)

        # Environment-driven checks (corrosion suitability) -- pulled from
        # the real checks list rather than re-derived, filtered to fail/warn
        # only so this doesn't duplicate the many unrelated "ok" checks.
        env_checks = [c for c in (r.get("checks") or [])
                      if "corros" in (c.get("msg") or "").lower() and c.get("type") in ("fail", "warn")]
        if env_checks:
            bl.addWidget(section_head("Material Suitability"))
            checks_box = QVBoxLayout()
            checks_box.setSpacing(6)
            for c in env_checks:
                flag_note(c.get("type"), c.get("msg", ""), parent_layout=checks_box)
            bl.addLayout(checks_box)

        bl.addStretch()
        scroll.setWidget(body)
        layout.addWidget(scroll)
        layout.addWidget(modal_footer(self))

    def updated_inputs(self):
        self.inputs["environment"] = self.env_combo.currentData()
        self.inputs["mu"] = self.mu.value()
        return self.inputs