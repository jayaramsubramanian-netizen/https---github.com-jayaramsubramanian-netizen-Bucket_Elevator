"""
components/service_edit.py -- Service Conditions dialog.
═══════════════════════════════════════════════════════════════════════════
Shared widgets come from dialog_helpers.py -- avoids a circular import with
input_sidebar.py.

Backend support confirmed directly before writing any UI for this:
  - environment: "dry"|"humid"|"wet"|"submerged"|"corrosive" (models.py).
    Genuinely consumed in TWO places in the main calculation flow, not a
    stub: (1) drives pulley_lagging() selection -- wet/submerged applies a
    0.85 friction-degradation factor, humid 0.92; (2) gates the
    bucket-material corrosion-suitability check.
  - mu: belt-pulley friction coefficient, 0.1-0.6 (models.py). Feeds the
    Euler/Eytelwein slip check and wrap-angle recommendation shown elsewhere
    (Belt Selection, Head & Tail Pulley) -- this is the one place to change it.
  - results contain the real computed `lagging` object (mu_dry/mu_wet/
    mu_operating/slip_safe/lagging_type) -- this dialog reads it.

SWEEP
─────
Built on dialog_helpers, so mostly clean. Two changes:

  * env_combo was a hand-rolled BARE combo stylesheet. Qt reads a
    selector-less sheet as `* { ... }` -- it applies to the widget AND every
    descendant, and a QComboBox owns an internal view, so the border landed
    inside it. It also missed every fix in the shared styled_combo() (flat
    drop-down arrow, matching 6px radius, scoped popup list). -> styled_combo().
  * plain_bg() / object-scoped scroll area; two flush-left indentation breaks
    restored (`current_env = ...` and the `if lagging:` block).

FIXED -- KEYWORD MATCHING NOW BOUNDED BY SUBSYSTEM
─────────────────────────────────────────────────
Previously:

    env_checks = [c for c in (r.get("checks") or [])
                  if "corros" in (c.get("msg") or "").lower() and ...]

That scanned the ENTIRE checks[] array for the substring "corros" with no
subsystem filter -- exactly the failure mode already fixed once in
EquipmentTree's nodeStatus(). Whole-array keyword matching is open-ended: any
future check in any subsystem whose message merely mentions corrosion would
surface here under "Material Suitability" as though it were a material finding.

The real tags, confirmed by grep rather than assumed:

    calculations.py:3946   subsystem="bucket"    "Bucket material {x} — corrosion
                                                  suitable [CEMA 550]"
    calculations.py:4032   subsystem="service"   "Corrosive material — 316L stainless
                                                  or coated casings/buckets
                                                  [CEMA 550 §B-4]"

Both ARE genuine material-suitability findings and both belong on this dialog,
so the visible behaviour is unchanged. The filter is now bounded to those two
subsystems rather than being open to every subsystem in the app.

(Note the bucket one at 3946 is an ok() check, and the type filter below keeps
only fail/warn -- so in practice the "service" finding is the one that renders.
The bucket subsystem is included because its FAIL counterpart belongs here too.)
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QFrame, QScrollArea, QDoubleSpinBox, QComboBox,
)

from theme import PANEL, PANEL2, BORDER, TEXT, TEXT2, scoped, plain_bg
from .dialog_helpers import (
    fmt, section_head, field_row, styled_spinbox, styled_combo,
    modal_header, modal_footer, stat_box, flag_note,
)

# Subsystems whose corrosion findings belong on THIS dialog. Confirmed against
# calculations.py (3946 -> "bucket", 4032 -> "service"), not guessed. Bounding
# the filter this way stops an unrelated subsystem's message from leaking in
# just because it happens to contain the word "corrosion".
ENV_CHECK_SUBSYSTEMS = ("service", "bucket")

ENVIRONMENT_OPTIONS = [
    ("dry", "Dry — standard indoor"),
    ("humid", "Humid — moisture > 15% or condensing"),
    ("wet", "Wet — water spray / washdown"),
    ("submerged", "Submerged — submerged boot section"),
    ("corrosive", "Corrosive — chemical exposure"),
]


class ServiceEditDialog(QDialog):
    """Service Conditions -- operating environment and belt-pulley friction
    coefficient, plus the real computed lagging selection and any
    environment-driven material suitability flags. No engineering math lives
    here; every number shown is read straight from results.lagging /
    results.checks."""

    def __init__(self, inputs, results, parent=None):
        super().__init__(parent)
        self.inputs = dict(inputs)
        self.results = results or {}
        self.setWindowTitle("Service Conditions")
        self.setMinimumWidth(460)
        self.resize(480, 560)
        self.setStyleSheet(plain_bg(self, PANEL))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(modal_header("Service Conditions", "CEMA 375 §3"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(scoped(scroll, "border: none; background: transparent;"))
        body = QFrame()
        body.setStyleSheet(scoped(body, "background-color: transparent; border: none;"))
        bl = QVBoxLayout(body)
        bl.setContentsMargins(16, 16, 16, 16)
        bl.setSpacing(12)

        r = self.results
        lagging = r.get("lagging") or {}

        # ── Environment ──────────────────────────────────────────────
        bl.addWidget(section_head("Operating Environment"))
        # Was a hand-rolled BARE combo stylesheet -- see module docstring.
        self.env_combo = styled_combo(QComboBox())
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
        env_note.setStyleSheet(f"color: {TEXT2}; font-size: 13px;")
        bl.addWidget(env_note)

        # ── Friction coefficient ─────────────────────────────────────
        bl.addWidget(section_head("Belt-Pulley Friction Coefficient"))
        self.mu = styled_spinbox(QDoubleSpinBox())
        self.mu.setRange(0.1, 0.6)
        self.mu.setSingleStep(0.05)
        self.mu.setValue(float(self.inputs.get("mu", 0.35)))
        bl.addLayout(field_row(
            "μ (mu)", self.mu, "",
            note="0.35 typical bare steel pulley. Feeds the Euler/Eytelwein slip check "
                 "and wrap-angle recommendation shown in Belt Selection and Head & Tail "
                 "Pulley."
        ))

        # ── Lagging (computed) ───────────────────────────────────────
        if lagging:
            bl.addWidget(section_head("Pulley Lagging (computed)"))
            bl.addWidget(stat_box([
                ("Type",
                 str(lagging.get("lagging_type", "—")).replace("_", " ").title()),
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
                rec_lbl.setStyleSheet(f"color: {TEXT2}; font-size: 13px;")
                bl.addWidget(rec_lbl)
        else:
            placeholder = QLabel(
                "Run a calculation to see lagging selection "
                "(not applicable for chain drives).")
            placeholder.setWordWrap(True)
            placeholder.setStyleSheet(
                f"color: {TEXT2}; font-size: 13px; font-style: italic;")
            bl.addWidget(placeholder)

        # ── Environment-driven checks ────────────────────────────────
        # FIXED: this used to keyword-match the WHOLE checks[] array for
        # "corros" with NO subsystem filter -- the same failure mode already
        # fixed in EquipmentTree's nodeStatus(). Any future check in ANY
        # subsystem whose message merely contained the substring would have
        # surfaced here under "Material Suitability".
        #
        # The correct tags, confirmed by grep rather than guessed:
        #   calculations.py:3946  subsystem="bucket"   bucket material corrosion suitability
        #   calculations.py:4032  subsystem="service"  corrosive material -> 316L / coated
        #
        # Both are genuinely material-suitability findings and both belong on
        # this dialog, so the visible behaviour is UNCHANGED -- but the filter is
        # now bounded to those two subsystems instead of being open-ended.
        env_checks = [
            c for c in (r.get("checks") or [])
            if c.get("subsystem") in ENV_CHECK_SUBSYSTEMS
            and "corros" in (c.get("msg") or "").lower()
            and c.get("type") in ("fail", "warn")
        ]
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