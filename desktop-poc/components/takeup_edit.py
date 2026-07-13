"""
components/takeup_edit.py -- Take-Up Selection dialog.
═══════════════════════════════════════════════════════════════════════════
First section built in its own file rather than added to the already-large
input_sidebar.py -- new sections go in their own importable module.

Shared widgets come from dialog_helpers.py, NOT from input_sidebar.py --
importing from input_sidebar.py here would create a circular import, since
input_sidebar.py imports TakeupEditDialog from this file.

Backend support confirmed directly (models.py + a live /calculate response):
  - takeup_type: "gravity" | "screw" | "hydraulic" | "auto"
  - K_takeup: take-up tension factor, 0.4-0.9
  - takeup_screw_d_mm / takeup_screw_len_m: screw overrides
  - takeup_hydraulic_bore_mm / takeup_hydraulic_pressure_bar
  - results contain takeup_gravity / takeup_screw / takeup_hydraulic, each
    fully computed with override_applied/override_adequate, plus a "primary"
    flag marking which one the solver actually used.

This dialog shows ALL THREE computed take-up types side by side -- the
backend computes all three regardless of selection, so showing only one
would hide comparison data the user already paid the calculation cost for.

SWEEP: MOSTLY CLEAN
───────────────────
Built on dialog_helpers' shared widgets (stat_box, field_row, flag_note,
n_way_selector), so it inherits their fixes -- same as casing_edit.py. Only
three changes:

  * _primary_badge used rgba(31,184,110,..) = v1 success (#1fb86e) while its
    text color is the imported v2 SUCCESS (#10b981) -- v2 green text on a v1
    green tint. Now SUCCESS_DIM / SUCCESS_BORDER. It was also a bare
    declaration; a QLabel has no children so nothing cascaded, but it's
    scoped now so no bare-declaration pattern remains to be copied.
  * plain_bg() / object-scoped scroll area, for consistency.
  * Three flush-left indentation breaks restored (`divider = QFrame()`, the
    Hydraulic block, and `def _section_header_row` -- the last of which sat
    OUTSIDE the class, so __init__ calling it would have raised
    AttributeError immediately).

CEMA HONESTY (retained, do not "tidy" away)
───────────────────────────────────────────
The hydraulic take-up carries an explicit warn note that it is sized using
standard cylinder mechanics and is NOT a published CEMA method. CEMA does
not define hydraulic take-up cylinder sizing; claiming CEMA backing for it
would be a fabricated citation.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea,
    QDoubleSpinBox,
)

from theme import (
    PANEL, PANEL2, BORDER, BORDER2, TEXT, TEXT2, TEXT3, MUTED,
    PRIMARY, SUCCESS, SUCCESS_DIM, SUCCESS_BORDER, WARNING, DANGER,
    R_PILL, scoped, plain_bg,
)
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
    used for this design -- distinct from what the selector above is set to,
    since "auto" only resolves to one of the other three at calculation time.

    Tint was v1 success while the text color is the imported v2 SUCCESS --
    two different greens in one badge. Both now from the same token."""
    lbl = QLabel("✓ SOLVER SELECTED THIS" if is_primary else "")
    if is_primary:
        lbl.setStyleSheet(scoped(
            lbl,
            f"background-color: {SUCCESS_DIM}; color: {SUCCESS}; "
            f"border: 1px solid {SUCCESS_BORDER}; border-radius: {R_PILL}px; "
            f"padding: 2px 9px; font-size: 9.5px; font-weight: 700;"
        ))
    return lbl


class TakeupEditDialog(QDialog):
    """Take-Up Selection -- gravity / screw / hydraulic / auto, with the real
    computed result for all three shown together.

    No buckling/tension math lives here. Every number shown (F_screw,
    d_core_min, SF_buckling, F_cylinder, counterweight mass, travel) is read
    straight from results -- this dialog only collects the override inputs and
    the type selection.
    """

    def __init__(self, inputs, results, parent=None):
        super().__init__(parent)
        self.inputs = dict(inputs)
        self.results = results or {}
        self.setWindowTitle("Take-Up Selection")
        self.setMinimumWidth(520)
        self.resize(560, 720)
        self.setStyleSheet(plain_bg(self, PANEL))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(modal_header("Take-Up Selection", "CEMA 375 §4"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(scoped(scroll, "border: none; background: transparent;"))
        body = QFrame()
        body.setStyleSheet(scoped(body, "background-color: transparent; border: none;"))
        bl = QVBoxLayout(body)
        bl.setContentsMargins(16, 16, 16, 16)
        bl.setSpacing(12)
        r = self.results

        # ── Type ─────────────────────────────────────────────────────
        bl.addWidget(section_head("Take-Up Type"))
        self._type_val = [self.inputs.get("takeup_type", "gravity")]
        bl.addLayout(n_way_selector(
            TAKEUP_TYPE_OPTIONS, self._type_val, self._on_type_change))
        type_note = QLabel(
            "Gravity: counterweight, recommended for H > 15m. Screw: threaded shank, "
            "short elevators H ≤ 15m. Hydraulic: cylinder, automatic constant-tension "
            "control — vendor-engineered, not a CEMA standard method (sized here using "
            "standard cylinder mechanics, flagged below). Auto: solver picks by H_m."
        )
        type_note.setWordWrap(True)
        type_note.setStyleSheet(f"color: {TEXT2}; font-size: 11px;")
        bl.addWidget(type_note)

        # ── Tension factor ───────────────────────────────────────────
        bl.addWidget(section_head("Take-Up Tension Factor"))
        self.k_takeup = styled_spinbox(QDoubleSpinBox())
        self.k_takeup.setRange(0.4, 0.9)
        self.k_takeup.setSingleStep(0.05)
        self.k_takeup.setValue(float(self.inputs.get("K_takeup", 0.7)))
        bl.addLayout(field_row(
            "K (tension factor)", self.k_takeup, "",
            note="0.7 typical for gravity take-up, 0.5 typical for screw. Affects T3 "
                 "tension sizing across the whole design, not just this section."
        ))

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(plain_bg(divider, BORDER2))
        bl.addWidget(divider)

        # ── Gravity (no overrides -- the only "input" would be structural
        # frame capacity, which isn't modeled as a numeric field anywhere in
        # this backend; verified directly, not assumed) ───────────────
        tg = r.get("takeup_gravity") or {}
        bl.addLayout(self._section_header_row("Gravity Take-Up", tg.get("primary")))
        if tg:
            bl.addWidget(stat_box([
                ("Counterweight (net)",
                 f"{fmt(tg.get('W_counterweight_kg_net'), 0)} kg"),
                ("Counterweight (gross)",
                 f"{fmt(tg.get('W_counterweight_kg_gross'), 0)} kg"),
                ("Travel required", f"{fmt(tg.get('travel_m'), 3)} m"),
            ]))
            note = QLabel(tg.get("note", ""))
            note.setWordWrap(True)
            note.setStyleSheet(f"color: {TEXT2}; font-size: 11px;")
            bl.addWidget(note)
        else:
            bl.addWidget(self._not_computed_note())

        # ── Screw ────────────────────────────────────────────────────
        ts = r.get("takeup_screw") or {}
        bl.addLayout(self._section_header_row("Screw Take-Up", ts.get("primary")))
        self.screw_d_override = styled_spinbox(QDoubleSpinBox())
        self.screw_d_override.setRange(0, 200)
        self.screw_d_override.setSingleStep(5)
        self.screw_d_override.setValue(float(self.inputs.get("takeup_screw_d_mm", 0)))
        self.screw_len_override = styled_spinbox(QDoubleSpinBox())
        self.screw_len_override.setRange(0, 10)
        self.screw_len_override.setSingleStep(0.1)
        self.screw_len_override.setValue(float(self.inputs.get("takeup_screw_len_m", 0)))

        if ts:
            adequate = ts.get("buckling_safe")
            bl.addWidget(stat_box(
                [("Force", f"{fmt((ts.get('F_screw_N') or 0) / 1000, 1)} kN"),
                 ("Core dia. (min)", f"{fmt(ts.get('d_core_min_mm'), 0)} mm"),
                 ("SF buckling", fmt(ts.get("SF_buckling"), 2)),
                 ("Turns required", fmt(ts.get("turns_required"), 0))],
                status=None if adequate is not False else "fail",
                note=ts.get("recommendation"),
            ))
            row = QHBoxLayout()
            row.addLayout(field_row("Core Dia. Override", self.screw_d_override, "mm",
                                    note="0 = auto from buckling check."))
            row.addLayout(field_row("Shank Length Override", self.screw_len_override, "m",
                                    note="0 = auto-derived from required travel."))
            bl.addLayout(row)
        else:
            # The spinboxes are still constructed above (not inside this else)
            # because updated_inputs() reads them unconditionally -- if they
            # only existed on the computed path, saving before the first
            # calculation would raise AttributeError.
            bl.addWidget(self._not_computed_note())

        # ── Hydraulic ────────────────────────────────────────────────
        th = r.get("takeup_hydraulic") or {}
        bl.addLayout(self._section_header_row("Hydraulic Take-Up", th.get("primary")))
        self.hyd_bore_override = styled_spinbox(QDoubleSpinBox())
        self.hyd_bore_override.setRange(0, 300)
        self.hyd_bore_override.setSingleStep(5)
        self.hyd_bore_override.setValue(
            float(self.inputs.get("takeup_hydraulic_bore_mm", 0)))
        self.hyd_pressure = styled_spinbox(QDoubleSpinBox())
        self.hyd_pressure.setRange(10, 350)
        self.hyd_pressure.setSingleStep(10)
        self.hyd_pressure.setValue(
            float(self.inputs.get("takeup_hydraulic_pressure_bar", 100)))

        if th:
            adequate = th.get("buckling_safe")
            # RETAINED: CEMA does not publish a hydraulic take-up cylinder
            # method. Claiming CEMA backing here would be a fabricated
            # citation. Say what it actually is.
            bl.addWidget(flag_note(
                "warn",
                "Sized using standard cylinder mechanics, not a published CEMA method — "
                "vendor-engineered selection. Verify against actual cylinder "
                "manufacturer data."
            ))
            bl.addWidget(stat_box(
                [("Force", f"{fmt((th.get('F_cylinder_N') or 0) / 1000, 1)} kN"),
                 ("Bore dia. (min)", f"{fmt(th.get('d_bore_min_mm'), 1)} mm"),
                 ("Stroke", f"{fmt(th.get('stroke_mm'), 0)} mm"),
                 ("SF buckling", fmt(th.get("SF_buckling"), 2))],
                status=None if adequate is not False else "fail",
                note=th.get("recommendation"),
            ))
            row2 = QHBoxLayout()
            row2.addLayout(field_row(
                "Bore Dia. Override", self.hyd_bore_override, "mm",
                note="0 = auto from force + operating pressure."))
            row2.addLayout(field_row(
                "Operating Pressure", self.hyd_pressure, "bar",
                note="100 bar common default — match actual power unit rating."))
            bl.addLayout(row2)
        else:
            bl.addWidget(self._not_computed_note())

        bl.addStretch()
        scroll.setWidget(body)
        layout.addWidget(scroll)
        layout.addWidget(modal_footer(self))

    def _section_header_row(self, title, is_primary):
        """NOTE: as pasted this sat at column 0, OUTSIDE the class -- and
        __init__ calls it three times, so the dialog could never have opened."""
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(section_head(title))
        row.addStretch()
        row.addWidget(_primary_badge(bool(is_primary)))
        return row

    def _not_computed_note(self):
        lbl = QLabel("Run a calculation to see this option's sizing.")
        lbl.setStyleSheet(
            f"color: {MUTED}; font-size: 10.5px; font-style: italic;")
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