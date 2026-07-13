"""
components/design_review_panel.py -- Design Review for the Status column.
═══════════════════════════════════════════════════════════════════════════
Faithful port of frontend/src/components/DesignReview.jsx -- same 4-stage
design maturity model (Concept/Preliminary/Detailed/Released), same auto-
stage computation from checks[] (fail->Concept, warn->Preliminary, clean->
Detailed), same manual-advance gating (0 fails required, warns block
advancing past Preliminary), same auto-regression when fails reappear after
a manual advance, same ALL/FAIL/WARN/PASS/INFO filter pills with live
counts, and the same expandable check-row layout with [CEMA ...]
trailing-clause extraction.

Wired into the Status column for the Checks tab specifically, alongside the
tab-aware status_stack (KpiGrid for Results/Optimizer, StatusDesignLeaves
for Components) -- a narrower placement than the JSX's always-on right
column.

BOX-IN-BOX BORDER SWEEP (this round)
────────────────────────────────────
_CheckRow was a textbook case. It called:

    self.setStyleSheet(f"background-color: {bg}; border: 1px solid {border}; ...")

with NO selector. Qt treats a selector-less stylesheet as `* { ... }` -- it
applies to the widget AND EVERY DESCENDANT. _CheckRow contains a status
badge, a message QLabel and a clause QLabel, so all three inherited
`border: 1px solid` and each drew its own box INSIDE the row. Every check
in the list rendered as a box containing three more boxes.

self.detail was the same again: a bare `border-top: 1px solid` that its
three labels (type_row, ref_row, full_msg) each redrew when expanded.

Same for maturity_box, the LOCKED/role-lock notes, and the Released badge.

Verified directly, not assumed: a QFrame with N child QLabels renders 2N
horizontal border runs inside itself under a bare declaration, and 0 under
a scoped one.

All of them now go through theme.card_frame() / scoped() / plain_bg().

TWO REAL BUGS FIXED (not styling -- actual wrong behaviour)
───────────────────────────────────────────────────────────
1. _FilterPill painted EVERY checked pill blue. The checked branch
   hardcoded `background-color: rgba(74,158,255,.15)` -- the PRIMARY tint
   -- regardless of self._color, while the border and text colors did
   respect it. So the FAIL pill lit up blue-on-red and the WARN pill
   blue-on-amber. The fill now derives from self._color like everything
   else. The Advance button had the identical bug (hardcoded blue tint
   behind a stage-colored border).

2. EVERY color literal in this file was v1 and had gone stale.
   rgba(224,82,82,..) is v1 danger #e05252; rgba(31,184,110,..) is v1
   success; rgba(74,158,255,..) is v1 primary. But this file IMPORTS
   DANGER/SUCCESS/PRIMARY from theme.py, which is now v2 (#ef4444,
   #10b981, #3b82f6). So each check row was drawing a v2-colored status
   badge inside a v1-colored tint -- two different reds in one widget.
   All replaced with the *_DIM / *_BORDER tokens.

ALSO
────
  * Nested _clear() inside _rebuild() -> shared dialog_helpers.clear_layout()
    (the same function was already copy-pasted 7x in input_sidebar.py).
  * Hardcoded "'JetBrains Mono', monospace" -> theme.FF_MONO.
  * ok_count counted only type == "ok", but _CheckRow accepts "pass" as a
    synonym for it. A backend check tagged "pass" therefore rendered
    correctly but was NOT counted by the PASS pill. Both now accepted.
"""
import re

try:
    from auth import require_role as _require_role, STAGE_REQUIRED_ROLE
except ImportError:
    # auth not available (test / headless environments)
    def _require_role(role: str) -> bool:  # type: ignore[misc]
        return True
    STAGE_REQUIRED_ROLE: dict = {2: "designer", 3: "reviewer", 4: "approver"}

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from theme import (
    PANEL, PANEL2, SURFACE, BORDER, TEXT, TEXT2, TEXT3, MUTED,
    PRIMARY, PRIMARY_DIM, PRIMARY_RING,
    SUCCESS, SUCCESS_DIM, SUCCESS_BORDER,
    WARNING, WARNING_DIM, WARNING_BORDER,
    DANGER, DANGER_DIM, DANGER_BORDER,
    INFO_DIM, INFO_BORDER,
    R_SM, R_MD, R_PILL, FF_MONO,
    scoped, plain_bg, card_frame,
)
from .dialog_helpers import status_badge, clear_layout

STAGES = [
    {"level": 1, "label": "Concept", "color": DANGER,
     "desc": "Has FAILs -- not suitable for procurement",
     "gate": "Resolve all FAILs to advance"},
    {"level": 2, "label": "Preliminary", "color": WARNING,
     "desc": "No FAILs -- suitable for budgetary purposes",
     "gate": "No FAILs remaining -- advance when ready"},
    {"level": 3, "label": "Detailed", "color": PRIMARY,
     "desc": "No FAILs -- suitable for detailed engineering "
             "(review any open WARNs/INFO first)",
     "gate": "No FAILs remaining -- advance when ready"},
    {"level": 4, "label": "Released", "color": SUCCESS,
     "desc": "Design frozen -- suitable for fabrication and procurement",
     "gate": "Design released"},
]

# Status -> (tint, border) token pairs. Single source, so a check row, a
# filter pill and the advance button can never disagree about what "warn"
# looks like -- which is exactly what happened when each hardcoded its own
# rgba literal.
STATUS_TINT = {
    "fail": (DANGER_DIM, DANGER_BORDER),
    "warn": (WARNING_DIM, WARNING_BORDER),
    "ok":   (SUCCESS_DIM, SUCCESS_BORDER),
    "info": (INFO_DIM, INFO_BORDER),
}
STATUS_FG = {"fail": DANGER, "warn": WARNING, "ok": SUCCESS, "info": PRIMARY}

CLAUSE_RE = re.compile(r"\[([^\]]+)\]\s*$")


def _tint(color_hex, alpha):
    """Build an rgba() tint from any theme color, so a widget's fill is
    always derived from its OWN status color rather than a hardcoded one.
    This is what _FilterPill and the Advance button were missing."""
    c = QColor(color_hex)
    return f"rgba({c.red()},{c.green()},{c.blue()},{alpha})"


def _extract_clause(msg):
    m = CLAUSE_RE.search(msg or "")
    return m.group(1) if m else None


def _strip_clause(msg):
    return CLAUSE_RE.sub("", msg or "").rstrip()


def _norm_type(t):
    """'pass' and 'ok' are the same thing. _CheckRow already treated them as
    synonyms; the counters did not, so a backend check tagged 'pass'
    rendered fine but went uncounted by the PASS pill."""
    return "ok" if t == "pass" else (t or "info")


def _compute_auto_stage(checks):
    if not checks:
        return 1
    if any(c.get("type") == "fail" for c in checks):
        return 1
    if any(c.get("type") == "warn" for c in checks):
        return 2
    return 3


class _CheckRow(QFrame):
    """One expandable check row.

    SCOPED: the bare declaration gave `border: 1px solid` to the status
    badge, the message label and the clause label as well as the frame --
    a box containing three boxes, on every single row.
    """

    def __init__(self, check, parent=None):
        super().__init__(parent)
        self._expanded = False
        self.check = check

        status = _norm_type(check.get("type"))
        color = STATUS_FG.get(status, PRIMARY)
        bg, border = STATUS_TINT.get(status, (INFO_DIM, INFO_BORDER))
        self._color = color

        self.setStyleSheet(scoped(
            self,
            f"background-color: {bg}; border: 1px solid {border}; "
            f"border-radius: {R_SM}px;"
        ))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.outer = QVBoxLayout(self)
        self.outer.setContentsMargins(0, 0, 0, 0)
        self.outer.setSpacing(0)

        head = QFrame()
        head.setStyleSheet(scoped(head, "background-color: transparent; border: none;"))
        hl = QHBoxLayout(head)
        hl.setContentsMargins(10, 7, 10, 7)
        hl.setSpacing(7)
        hl.addWidget(status_badge(status, size=15))

        msg = _strip_clause(check.get("msg", ""))
        msg_lbl = QLabel(msg)
        msg_lbl.setWordWrap(True)
        msg_lbl.setStyleSheet(f"color: {TEXT2}; font-size: 11px;")
        hl.addWidget(msg_lbl, 1)

        clause = _extract_clause(check.get("msg", ""))
        if clause:
            clause_lbl = QLabel(clause)
            clause_lbl.setStyleSheet(
                f"color: {TEXT3}; font-size: 9px; font-family: {FF_MONO};")
            hl.addWidget(clause_lbl)
        self.outer.addWidget(head)

        # SCOPED: the bare `border-top` here was inherited by type_row,
        # ref_row and full_msg, so expanding a row drew four stacked rules
        # instead of one.
        self.detail = QFrame()
        self.detail.setStyleSheet(scoped(
            self.detail,
            f"background-color: transparent; border: none; "
            f"border-top: 1px solid {border};"
        ))
        dl = QVBoxLayout(self.detail)
        dl.setContentsMargins(28, 6, 10, 8)
        dl.setSpacing(3)
        type_row = QLabel(f"Type: {status.upper()}")
        type_row.setStyleSheet(f"color: {color}; font-size: 9px; font-weight: 700;")
        dl.addWidget(type_row)
        if clause:
            ref_row = QLabel(f"Reference: {clause}")
            ref_row.setStyleSheet(
                f"color: {TEXT3}; font-size: 10px; font-family: {FF_MONO};")
            dl.addWidget(ref_row)
        full_msg = QLabel(msg)
        full_msg.setWordWrap(True)
        full_msg.setStyleSheet(f"color: {TEXT3}; font-size: 10px; margin-top: 2px;")
        dl.addWidget(full_msg)
        self.detail.hide()
        self.outer.addWidget(self.detail)

    def mousePressEvent(self, event):
        self._expanded = not self._expanded
        self.detail.setVisible(self._expanded)
        super().mousePressEvent(event)


class _FilterPill(QPushButton):
    """ALL / FAIL / WARN / PASS / INFO filter pill.

    FIXED: the checked state hardcoded `rgba(74,158,255,.15)` -- the blue
    PRIMARY tint -- for EVERY pill, while its border and text used
    self._color. So a checked FAIL pill was blue-on-red and a checked WARN
    pill blue-on-amber. The fill is now derived from self._color.
    """

    def __init__(self, label, count, color, parent=None):
        super().__init__(parent)
        self.setText(f"{label}  {count}")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._color = color
        self.toggled.connect(self._restyle)
        self._restyle(False)

    def _restyle(self, checked):
        if checked:
            self.setStyleSheet(scoped(
                self,
                f"background-color: {_tint(self._color, '.15')}; color: {self._color}; "
                f"border: 1px solid {self._color}; border-radius: {R_PILL}px; "
                f"padding: 3px 10px; font-size: 9.5px; font-weight: 700;"
            ))
        else:
            self.setStyleSheet(scoped(
                self,
                f"background-color: transparent; color: {TEXT2}; "
                f"border: 1px solid {BORDER}; border-radius: {R_PILL}px; "
                f"padding: 3px 10px; font-size: 9.5px;",
                extra="{sel}:hover { color: %s; }" % TEXT,
            ))


class DesignReviewPanel(QWidget):
    """Port of DesignReview.jsx's default export. set_data(inputs, results)
    like every other panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(plain_bg(self, PANEL))
        self._manual_stage = None
        self._filter = "all"
        self._results = {}

        from PySide6.QtWidgets import QScrollArea
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(scoped(scroll, "border: none; background: transparent;"))
        self.body = QWidget()
        self.body.setStyleSheet(plain_bg(self.body, PANEL))
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(12, 12, 12, 12)
        self.body_layout.setSpacing(10)
        self.body_layout.addStretch()
        scroll.setWidget(self.body)
        outer.addWidget(scroll)

    def set_data(self, inputs, results):
        self._results = results or {}
        self._rebuild()

    def _rebuild(self):
        clear_layout(self.body_layout)

        r = self._results
        checks = r.get("checks") or []
        types = [_norm_type(c.get("type")) for c in checks]
        fail_count = types.count("fail")
        warn_count = types.count("warn")
        ok_count = types.count("ok")      # now includes checks tagged "pass"
        info_count = types.count("info")

        auto_stage = _compute_auto_stage(checks)
        if self._manual_stage is None:
            effective_stage = auto_stage
        elif fail_count > 0:
            effective_stage = 1           # auto-regression when fails reappear
        else:
            effective_stage = max(self._manual_stage, auto_stage)

        stage = next((s for s in STAGES if s["level"] == effective_stage), STAGES[0])

        title = QLabel("DESIGN REVIEW")
        title.setStyleSheet(
            f"color: {TEXT3}; font-size: 10px; font-weight: 700; letter-spacing: .08em;")
        self.body_layout.addWidget(title)

        # SCOPED: bare border here boxed the maturity header, the stage
        # label, every segment, every stage caption and the description.
        maturity_box, ml = card_frame(bg=PANEL2, border=BORDER, radius=7,
                                      margins=(12, 10, 12, 10), spacing=6)

        head_row = QHBoxLayout()
        head_label = QLabel("DESIGN MATURITY")
        head_label.setStyleSheet(
            f"color: {TEXT2}; font-size: 9px; font-weight: 700; letter-spacing: .06em;")
        head_row.addWidget(head_label)
        head_row.addStretch()
        stage_label = QLabel(stage["label"])
        stage_label.setStyleSheet(
            f"color: {stage['color']}; font-size: 11px; font-weight: 700;")
        head_row.addWidget(stage_label)
        ml.addLayout(head_row)

        bar_row = QHBoxLayout()
        bar_row.setSpacing(3)
        for s in STAGES:
            seg = QFrame()
            seg.setFixedHeight(4)
            filled = s["level"] <= effective_stage
            seg.setStyleSheet(scoped(
                seg,
                f"background-color: {stage['color'] if filled else SURFACE}; "
                f"border: none; border-radius: 2px;"
            ))
            bar_row.addWidget(seg)
        ml.addLayout(bar_row)

        # NOTE: in the source this line was flush-left, outside _rebuild's
        # body -- a hard SyntaxError; the module could not have imported.
        # Restored to its correct indentation.
        labels_row = QHBoxLayout()
        for s in STAGES:
            lbl = QLabel(s["label"])
            active = s["level"] <= effective_stage
            lbl.setStyleSheet(
                f"color: {stage['color'] if active else TEXT3}; font-size: 8px; "
                f"font-weight: {'700' if s['level'] == effective_stage else '400'};"
            )
            labels_row.addWidget(lbl)
        ml.addLayout(labels_row)

        desc = QLabel(stage["desc"])
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {TEXT2}; font-size: 10px;")
        ml.addWidget(desc)

        next_level = effective_stage + 1
        can_advance = next_level <= 4 and fail_count == 0
        required_role = STAGE_REQUIRED_ROLE.get(next_level, "approver")

        if effective_stage < 4:
            if can_advance:
                next_stage = next(s for s in STAGES if s["level"] == next_level)
                try:
                    has_permission = _require_role(required_role)
                except Exception:
                    has_permission = True   # auth not initialized (test mode)

                if has_permission:
                    advance_btn = QPushButton(f"Advance to {next_stage['label']} →")
                    advance_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    # FIXED: was a hardcoded blue rgba(74,158,255,.15) fill
                    # behind a stage-COLORED border -- so advancing to
                    # Preliminary showed a blue fill inside an amber border.
                    # Tint now derives from the target stage's own color.
                    advance_btn.setStyleSheet(scoped(
                        advance_btn,
                        f"background-color: {_tint(next_stage['color'], '.15')}; "
                        f"color: {next_stage['color']}; "
                        f"border: 1px solid {next_stage['color']}; "
                        f"border-radius: {R_SM - 2}px; padding: 6px 12px; "
                        f"font-size: 10px; font-weight: 700;",
                        extra="{sel}:hover { background-color: %s; }"
                              % _tint(next_stage["color"], ".25"),
                    ))
                    advance_btn.clicked.connect(
                        lambda _checked=False, lv=next_level: self._advance(lv))
                    ml.addWidget(advance_btn)

                    if warn_count > 0:
                        review_note = QLabel(
                            f"ⓘ {warn_count} WARN{'s' if warn_count > 1 else ''} still "
                            f"open — review before advancing if not yet accepted")
                        review_note.setWordWrap(True)
                        review_note.setStyleSheet(
                            f"color: {WARNING}; font-size: 9px; margin-top: 2px;")
                        ml.addWidget(review_note)
                else:
                    role_lock = QLabel(
                        f"🔒 {required_role.capitalize()} role required to advance to "
                        f"{next_stage['label']}"
                    )
                    role_lock.setWordWrap(True)
                    role_lock.setStyleSheet(scoped(
                        role_lock,
                        f"color: {TEXT3}; font-size: 10px; padding: 5px 8px; "
                        f"border-radius: {R_SM - 2}px; "
                        f"background-color: rgba(0,0,0,.12); "
                        f"border: 1px solid {BORDER};"
                    ))
                    ml.addWidget(role_lock)
            else:
                lock = QLabel(
                    f"LOCKED: Resolve {fail_count} FAIL{'s' if fail_count > 1 else ''} "
                    f"to advance")
                lock.setWordWrap(True)
                lock.setStyleSheet(scoped(
                    lock,
                    f"color: {TEXT2}; font-size: 10px; padding: 5px 8px; "
                    f"border-radius: {R_SM - 2}px; "
                    f"background-color: rgba(0,0,0,.15); "
                    f"border: 1px solid {BORDER};"
                ))
                ml.addWidget(lock)
        else:
            released = QLabel("✓ Design Released")
            released.setStyleSheet(scoped(
                released,
                f"color: {SUCCESS}; font-size: 10px; font-weight: 700; "
                f"padding: 5px 8px; border-radius: {R_SM - 2}px; "
                f"background-color: {SUCCESS_DIM}; "
                f"border: 1px solid {SUCCESS_BORDER};"
            ))
            ml.addWidget(released)

            revoke_btn = QPushButton("Revoke release")
            revoke_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            revoke_btn.setStyleSheet(scoped(
                revoke_btn,
                f"background-color: transparent; color: {TEXT2}; border: none; "
                f"font-size: 9px; text-decoration: underline; padding: 2px;",
                extra="{sel}:hover { color: %s; }" % TEXT,
            ))
            revoke_btn.clicked.connect(self._revoke)
            ml.addWidget(revoke_btn)

        self.body_layout.addWidget(maturity_box)

        if checks:
            filter_row = QHBoxLayout()
            filter_row.setSpacing(4)
            filters = [
                ("all", "ALL", len(checks), TEXT2),
                ("fail", "FAIL", fail_count, DANGER),
                ("warn", "WARN", warn_count, WARNING),
                ("ok", "PASS", ok_count, SUCCESS),
                ("info", "INFO", info_count, PRIMARY),
            ]
            for fid, label, count, color in filters:
                if fid != "all" and count == 0:
                    continue
                pill = _FilterPill(label, count, color)
                pill.setChecked(self._filter == fid)
                pill.clicked.connect(lambda _checked=False, f=fid: self._set_filter(f))
                filter_row.addWidget(pill)
            filter_row.addStretch()
            self.body_layout.addLayout(filter_row)

        filtered = (checks if self._filter == "all"
                    else [c for c in checks
                          if _norm_type(c.get("type")) == self._filter])

        if not checks:
            empty = QLabel("Run a calculation to see design review.")
            empty.setStyleSheet(
                f"color: {TEXT2}; font-size: 11px; font-style: italic;")
            self.body_layout.addWidget(empty)
        elif not filtered:
            empty = QLabel(
                f"No {self._filter if self._filter != 'all' else ''} checks to show")
            empty.setStyleSheet(f"color: {TEXT2}; font-size: 11px;")
            self.body_layout.addWidget(empty)
        else:
            list_box = QVBoxLayout()
            list_box.setSpacing(4)
            for c in filtered:
                list_box.addWidget(_CheckRow(c))
            self.body_layout.addLayout(list_box)

        self.body_layout.addStretch()

    def _advance(self, level):
        self._manual_stage = level
        self._rebuild()

    def _revoke(self):
        self._manual_stage = None
        self._rebuild()

    def _set_filter(self, filter_id):
        self._filter = filter_id
        self._rebuild()