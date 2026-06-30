"""
components/design_review_panel.py -- Design Review for the Status column.
═══════════════════════════════════════════════════════════════════════════
Faithful port of frontend/src/components/DesignReview.jsx, read directly
before writing this (not assumed) -- same 4-stage design maturity model
(Concept/Preliminary/Detailed/Released), same auto-stage computation from
checks[] (fail->Concept, warn->Preliminary, clean->Detailed), same manual-
advance gating (0 fails required, warns block advancing past Preliminary),
same auto-regression when fails reappear after a manual advance, same
ALL/FAIL/WARN/PASS/INFO filter pills with live counts, and the same
expandable check-row layout with [CEMA ...] trailing-clause extraction.

Per direct instruction this round: previously DesignReview.jsx was
persistent across all tabs in the real JSX (right column, always visible).
Here it's wired into the Status column specifically for the Checks tab,
alongside the existing tab-aware status_stack (KpiGrid for Results/
Optimizer, StatusDesignLeaves for Components) -- a third, narrower use
than the original always-on JSX placement, per "add the Design Review
elements from the jsx to the status section when in the checks tab."
"""
import re
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea, QPushButton,
)
from PySide6.QtCore import Qt

from theme import PANEL, PANEL2, BORDER, TEXT, TEXT2, TEXT3, MUTED, PRIMARY, SUCCESS, WARNING, DANGER
from .dialog_helpers import status_badge

STAGES = [
    {"level": 1, "label": "Concept", "color": DANGER,
     "desc": "Has FAILs -- not suitable for procurement",
     "gate": "Resolve all FAILs to advance"},
    {"level": 2, "label": "Preliminary", "color": WARNING,
     "desc": "No FAILs -- suitable for budgetary purposes",
     "gate": "Resolve all WARNs to advance"},
    {"level": 3, "label": "Detailed", "color": PRIMARY,
     "desc": "No FAILs or WARNs -- suitable for detailed engineering",
     "gate": "All checks PASS -- advance to Released to freeze design"},
    {"level": 4, "label": "Released", "color": SUCCESS,
     "desc": "Design frozen -- suitable for fabrication and procurement",
     "gate": "Design released"},
]

CLAUSE_RE = re.compile(r"\[([^\]]+)\]\s*$")


def _extract_clause(msg):
    m = CLAUSE_RE.search(msg or "")
    return m.group(1) if m else None


def _strip_clause(msg):
    return CLAUSE_RE.sub("", msg or "").rstrip()


def _compute_auto_stage(checks):
    if not checks:
        return 1
    if any(c.get("type") == "fail" for c in checks):
        return 1
    if any(c.get("type") == "warn" for c in checks):
        return 2
    return 3


class _CheckRow(QFrame):
    def __init__(self, check, parent=None):
        super().__init__(parent)
        self._expanded = False
        self.check = check
        status = check.get("type", "info")
        status = "ok" if status == "pass" else status
        color = {"fail": DANGER, "warn": WARNING, "ok": SUCCESS}.get(status, PRIMARY)
        bg = {"fail": "rgba(224,82,82,.06)", "warn": "rgba(217,142,0,.06)",
              "ok": "rgba(31,184,110,.06)"}.get(status, "rgba(74,158,255,.06)")
        border = {"fail": "rgba(224,82,82,.2)", "warn": "rgba(217,142,0,.2)",
                  "ok": "rgba(31,184,110,.2)"}.get(status, "rgba(74,158,255,.2)")
        self._color = color

        self.setStyleSheet(f"background-color: {bg}; border: 1px solid {border}; border-radius: 5px;")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.outer = QVBoxLayout(self)
        self.outer.setContentsMargins(0, 0, 0, 0)
        self.outer.setSpacing(0)

        head = QFrame()
        head.setStyleSheet("background-color: transparent;")
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
            clause_lbl.setStyleSheet(f"color: {TEXT3}; font-size: 9px; font-family: 'JetBrains Mono', monospace;")
            hl.addWidget(clause_lbl)
        self.outer.addWidget(head)

        self.detail = QFrame()
        self.detail.setStyleSheet(f"border-top: 1px solid {border};")
        dl = QVBoxLayout(self.detail)
        dl.setContentsMargins(28, 6, 10, 8)
        dl.setSpacing(3)
        type_row = QLabel(f"Type: {status.upper()}")
        type_row.setStyleSheet(f"color: {color}; font-size: 9px; font-weight: 700;")
        dl.addWidget(type_row)
        if clause:
            ref_row = QLabel(f"Reference: {clause}")
            ref_row.setStyleSheet(f"color: {TEXT3}; font-size: 10px; font-family: 'JetBrains Mono', monospace;")
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
            self.setStyleSheet(
                f"QPushButton {{ background-color: rgba(74,158,255,.15); color: {self._color}; "
                f"border: 1px solid {self._color}; border-radius: 999px; padding: 3px 10px; "
                f"font-size: 9.5px; font-weight: 700; }}"
            )
        else:
            self.setStyleSheet(
                f"QPushButton {{ background-color: transparent; color: {TEXT2}; "
                f"border: 1px solid {BORDER}; border-radius: 999px; padding: 3px 10px; font-size: 9.5px; }}"
            )


class DesignReviewPanel(QWidget):
    """Port of DesignReview.jsx's default export. set_data(inputs,
    results) like every other panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {PANEL};")
        self._manual_stage = None
        self._filter = "all"
        self._results = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        self.body = QWidget()
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
        while self.body_layout.count():
            item = self.body_layout.takeAt(0)
            w = item.widget() if item else None
            if w:
                w.setParent(None)
                w.deleteLater()

        r = self._results
        checks = r.get("checks") or []
        fail_count = sum(1 for c in checks if c.get("type") == "fail")
        warn_count = sum(1 for c in checks if c.get("type") == "warn")
        ok_count = sum(1 for c in checks if c.get("type") == "ok")
        info_count = sum(1 for c in checks if c.get("type") == "info")

        auto_stage = _compute_auto_stage(checks)
        if self._manual_stage is None:
            effective_stage = auto_stage
        elif fail_count > 0:
            effective_stage = 1
        elif warn_count > 0 and self._manual_stage > 2:
            effective_stage = 2
        else:
            effective_stage = max(self._manual_stage, auto_stage)

        stage = next((s for s in STAGES if s["level"] == effective_stage), STAGES[0])

        title = QLabel("DESIGN REVIEW")
        title.setStyleSheet(f"color: {TEXT3}; font-size: 10px; font-weight: 700; letter-spacing: .08em;")
        self.body_layout.addWidget(title)

        maturity_box = QFrame()
        maturity_box.setStyleSheet(f"background-color: {PANEL2}; border: 1px solid {BORDER}; border-radius: 7px;")
        ml = QVBoxLayout(maturity_box)
        ml.setContentsMargins(12, 10, 12, 10)
        ml.setSpacing(6)

        head_row = QHBoxLayout()
        head_label = QLabel("DESIGN MATURITY")
        head_label.setStyleSheet(f"color: {TEXT2}; font-size: 9px; font-weight: 700; letter-spacing: .06em;")
        head_row.addWidget(head_label)
        head_row.addStretch()
        stage_label = QLabel(stage["label"])
        stage_label.setStyleSheet(f"color: {stage['color']}; font-size: 11px; font-weight: 700;")
        head_row.addWidget(stage_label)
        ml.addLayout(head_row)

        bar_row = QHBoxLayout()
        bar_row.setSpacing(3)
        for s in STAGES:
            seg = QFrame()
            seg.setFixedHeight(4)
            seg.setStyleSheet(
                f"background-color: {stage['color'] if s['level'] <= effective_stage else BORDER}; border-radius: 2px;"
            )
            bar_row.addWidget(seg)
        ml.addLayout(bar_row)

        labels_row = QHBoxLayout()
        for s in STAGES:
            lbl = QLabel(s["label"])
            lbl.setStyleSheet(
                f"color: {stage['color'] if s['level'] <= effective_stage else TEXT3}; font-size: 8px; "
                f"font-weight: {'700' if s['level'] == effective_stage else '400'};"
            )
            labels_row.addWidget(lbl)
        ml.addLayout(labels_row)

        desc = QLabel(stage["desc"])
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {TEXT2}; font-size: 10px;")
        ml.addWidget(desc)

        next_level = effective_stage + 1
        can_advance = next_level <= 4 and fail_count == 0 and (warn_count == 0 if next_level < 4 else True)
        if effective_stage < 4:
            if can_advance:
                next_stage = next(s for s in STAGES if s["level"] == next_level)
                advance_btn = QPushButton(f"Advance to {next_stage['label']} ->")
                advance_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                advance_btn.setStyleSheet(
                    f"background-color: rgba(74,158,255,.15); color: {next_stage['color']}; "
                    f"border: 1px solid {next_stage['color']}; border-radius: 4px; padding: 6px 12px; "
                    f"font-size: 10px; font-weight: 700;"
                )
                advance_btn.clicked.connect(lambda: self._advance(next_level))
                ml.addWidget(advance_btn)
            else:
                if fail_count > 0:
                    lock_text = f"LOCKED: Resolve {fail_count} FAIL{'s' if fail_count > 1 else ''} to advance"
                elif warn_count > 0 and effective_stage >= 2:
                    lock_text = f"LOCKED: Resolve {warn_count} WARN{'s' if warn_count > 1 else ''} to advance to Detailed"
                else:
                    lock_text = f"LOCKED: {stage['gate']}"
                lock = QLabel(lock_text)
                lock.setWordWrap(True)
                lock.setStyleSheet(
                    f"color: {TEXT2}; font-size: 10px; padding: 5px 8px; border-radius: 4px; "
                    f"background-color: rgba(0,0,0,.15); border: 1px solid {BORDER};"
                )
                ml.addWidget(lock)
        else:
            released = QLabel("Design Released")
            released.setStyleSheet(
                f"color: {SUCCESS}; font-size: 10px; font-weight: 700; padding: 5px 8px; "
                f"border-radius: 4px; background-color: rgba(31,184,110,.1); border: 1px solid rgba(31,184,110,.25);"
            )
            ml.addWidget(released)
            revoke_btn = QPushButton("Revoke release")
            revoke_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            revoke_btn.setStyleSheet(
                f"background-color: transparent; color: {TEXT2}; border: none; font-size: 9px; "
                f"text-decoration: underline; padding: 2px;"
            )
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
                pill.clicked.connect(lambda checked, f=fid: self._set_filter(f))
                filter_row.addWidget(pill)
            filter_row.addStretch()
            self.body_layout.addLayout(filter_row)

        filtered = checks if self._filter == "all" else [c for c in checks if c.get("type") == self._filter]
        if not checks:
            empty = QLabel("Run a calculation to see design review.")
            empty.setStyleSheet(f"color: {TEXT2}; font-size: 11px; font-style: italic;")
            self.body_layout.addWidget(empty)
        elif not filtered:
            empty = QLabel(f"No {self._filter if self._filter != 'all' else ''} checks to show")
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