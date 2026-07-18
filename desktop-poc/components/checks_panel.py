"""
components/checks_panel.py -- Checks tab center-console content.
═══════════════════════════════════════════════════════════════════════════
Faithful port of three real JSX files, stacked in the exact order
BucketElevatorPage.jsx uses for the Checks tab:
    RootCausePanel.jsx + DesignRecommendationsPanel.jsx + ChecksPanel.jsx

RootCausePanel reads results.root_cause (root_cause.py's analyse()) --
rich findings with contributing-factor "driver" bars and Apply-able
corrections, plus conflict detection when two findings ask for opposite
changes to the same input parameter.

DesignRecommendationsPanel reads results.design_recommendations
(structural.py's design_recommendations()) -- a narrower, structural-only
recommendation list. Both engines are real and both are shown, matching
the JSX rather than picking one.

ChecksPanel reads results.checks directly -- the complete flat list, plus
a 2-column Design Summary grid.

BOX-IN-BOX BORDER SWEEP (this round)
────────────────────────────────────
This was the worst file in the app, because the cascades NEST. Qt treats a
selector-less stylesheet as `* { ... }` -- it applies to the widget AND
EVERY DESCENDANT -- and this file had bare declarations at three levels
stacked inside each other:

    _finding_card   bare `border: 1px solid`   -> everything below boxes itself
      head          bare `border-bottom`       -> metric + explanation labels
      drv_box       bare `border-bottom`       -> header + every driver row
      _correction_row bare `border: 1px solid` -> marker, label, current,
                                                  arrow, target, %, note

So a single correction row rendered as a box, inside a box, inside a card,
with each of its own six labels boxed as well. Also: the conflict box, its
per-param boxes, DesignRecommendations' cards and their headers, and the
summary grid rows.

Verified directly, not assumed: a QFrame with N child QLabels renders 2N
horizontal border runs inside itself under a bare declaration, and 0 under
a scoped one.

All now go through theme.scoped() / card_frame() / plain_bg().

Legitimate exception, kept: the correction-row priority MARKER is a
circle that genuinely needs its own border+radius. It's now the ONLY
bordered thing inside a correction row, which is the whole point.

COLORS -- ALL WERE STALE
────────────────────────
Every rgba() literal here was v1: rgba(224,82,82,..) is v1 danger #e05252,
rgba(217,142,0,..) v1 warning, rgba(74,158,255,..) v1 primary,
rgba(100,116,139,..) v1 muted. But this file IMPORTS DANGER/WARNING/PRIMARY
from theme.py, which is now v2 (#ef4444/#f59e0b/#3b82f6). So every card
drew a v2-colored status badge inside a v1-colored tint -- two different
reds in the same widget. All replaced with *_DIM / *_BORDER tokens.

ALSO
────
  * clear_layout() was defined locally here (and in input_sidebar.py, and
    as a nested _clear in design_review_panel.py). Now imported from
    dialog_helpers. The recursive-sublayout fix this file's docstring
    describes is preserved -- that's exactly what the shared version does.
  * Hardcoded "'JetBrains Mono', monospace" -> theme.FF_MONO.
  * 'pass' accepted as a synonym for 'ok' in the flat checks list AND in
    the fail/warn counters (RootCauseSection counted only "fail"/"warn",
    which is fine, but FlatChecksSection normalised only at render time).

DRIVER BARS -- READ THIS BEFORE "IMPROVING" THEM
────────────────────────────────────────────────
_driver_row's bar length is `100 - (priority - 1) * 30` -- purely a
function of RANK, not of any measured contribution. It encodes ordering
while LOOKING like it encodes magnitude. I have not changed this and have
not invented a weight: if root_cause.py's driver dicts carry a real
contribution/share field, the bar should use that instead; if they don't,
this bar is decorative and the honest fix is to drop it for a rank chip.
Flagged, not silently altered. See the comment at _driver_row.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea,
    QPushButton, QGridLayout,
)
from PySide6.QtCore import Qt

from theme import (
    PANEL, PANEL2, SURFACE, BORDER, TEXT, TEXT2, TEXT3, MUTED,
    PRIMARY, PRIMARY_DIM, PRIMARY_RING,
    SUCCESS, SUCCESS_DIM, SUCCESS_BORDER,
    WARNING, WARNING_DIM, WARNING_BORDER,
    DANGER, DANGER_DIM, DANGER_BORDER,
    R_SM, R_MD, R_PILL, FF_MONO,
    scoped, plain_bg, card_frame,
)
from .dialog_helpers import status_badge, flag_note, clear_layout, fmt

# Single source of truth for status tinting -- so a finding card, a
# correction row, a recommendation card and a badge can never disagree
# about what "warn" looks like. That disagreement is exactly what the
# scattered rgba() literals produced.
SEV_FG     = {"fail": DANGER, "warn": WARNING, "ok": SUCCESS}
SEV_DIM    = {"fail": DANGER_DIM, "warn": WARNING_DIM, "ok": SUCCESS_DIM}
SEV_BORDER = {"fail": DANGER_BORDER, "warn": WARNING_BORDER, "ok": SUCCESS_BORDER}

MUTED_DIM = "rgba(100,116,139,.14)"


def _norm(t):
    """'pass' and 'ok' are the same status."""
    return "ok" if t == "pass" else (t or "info")


# ── RootCausePanel port ──────────────────────────────────────────────────
def _driver_row(d, sev_color):
    """One contributing-factor row.

    NOTE ON THE BAR (unchanged, deliberately): fill_pct below is derived
    from `priority` alone -- rank 1 = 100%, rank 2 = 70%, rank 3 = 40%.
    It is NOT a measured contribution. A viewer reads a bar as magnitude,
    so this currently implies a weight that was never computed. I've left
    it exactly as it was rather than substitute a number I'd have had to
    invent. If root_cause.py's driver dicts expose a real share/contribution
    field, wire the bar to that; if not, the honest replacement is a plain
    rank chip and no bar.
    """
    box = QVBoxLayout()
    box.setSpacing(3)

    head = QHBoxLayout()
    head.setSpacing(8)
    unit = f" {d['unit']}" if d.get("unit") else ""
    label = QLabel(f"{d.get('label','')}  =  {d.get('current','—')}{unit}")
    label.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: 600;")
    head.addWidget(label, 1)

    priority = d.get("priority", 2)
    is_primary = priority == 1
    tag = QLabel("PRIMARY" if is_primary else f"#{priority}")
    tag.setStyleSheet(scoped(
        tag,
        f"background-color: {PRIMARY_DIM if is_primary else MUTED_DIM}; "
        f"color: {sev_color if is_primary else TEXT3}; border: none; "
        f"border-radius: {R_PILL}px; padding: 1px 7px; "
        f"font-size: 12px; font-weight: 700;"
    ))
    head.addWidget(tag)
    box.addLayout(head)

    bar_bg = QFrame()
    bar_bg.setFixedHeight(4)
    bar_bg.setStyleSheet(scoped(
        bar_bg, f"background-color: {SURFACE}; border: none; border-radius: 2px;"))
    bar_layout = QHBoxLayout(bar_bg)
    bar_layout.setContentsMargins(0, 0, 0, 0)
    fill_pct = max(0, 100 - (priority - 1) * 30)
    fill = QFrame()
    fill.setStyleSheet(scoped(
        fill,
        f"background-color: {sev_color if is_primary else TEXT3}; "
        f"border: none; border-radius: 2px;"))
    bar_layout.addWidget(fill, fill_pct)
    spacer = QFrame()
    spacer.setStyleSheet(scoped(spacer, "background-color: transparent; border: none;"))
    bar_layout.addWidget(spacer, 100 - fill_pct)
    box.addWidget(bar_bg)

    impact = QLabel(d.get("impact", ""))
    impact.setWordWrap(True)
    impact.setStyleSheet(f"color: {TEXT2}; font-size: 13px;")
    box.addWidget(impact)
    return box


def _correction_row(c, priority, has_conflict, on_apply):
    """SCOPED: the bare `border: 1px solid` here was inherited by the
    marker, the label, the current/arrow/target values, the % delta and
    the note -- six boxes inside a box inside a card.

    The MARKER keeps its own border deliberately: it's a numbered circle,
    and a circle needs a border and a radius. It's now the only bordered
    thing in the row, which is exactly the intent."""
    row = QFrame()
    row.setStyleSheet(scoped(
        row,
        f"background-color: {PANEL2}; "
        f"border: 1px solid {WARNING_BORDER if has_conflict else BORDER}; "
        f"border-radius: {R_SM}px;"
    ))
    layout = QHBoxLayout(row)
    layout.setContentsMargins(10, 8, 10, 8)
    layout.setSpacing(10)

    is_primary = priority == 1
    marker = QLabel(str(priority))
    marker.setFixedSize(22, 22)
    marker.setAlignment(Qt.AlignmentFlag.AlignCenter)
    marker.setStyleSheet(scoped(
        marker,
        f"background-color: {PRIMARY_DIM if is_primary else MUTED_DIM}; "
        f"color: {PRIMARY if is_primary else TEXT3}; "
        f"border: 1px solid {PRIMARY if is_primary else BORDER}; "
        f"border-radius: 11px; font-size: 13px; font-weight: 700;"
    ))
    layout.addWidget(marker)

    content = QVBoxLayout()
    content.setSpacing(4)

    head_row = QHBoxLayout()
    label = QLabel(c.get("label", ""))
    label.setWordWrap(True)
    label.setStyleSheet(f"color: {TEXT}; font-size: 14px; font-weight: 700;")
    head_row.addWidget(label, 1)

    can_apply = (on_apply is not None and c.get("param")
                 and c.get("param") != "bearing"
                 and c.get("target") is not None
                 and not isinstance(c.get("target"), str))
    if can_apply:
        apply_btn = QPushButton("Apply")
        apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_btn.setStyleSheet(scoped(
            apply_btn,
            f"background-color: {PRIMARY_DIM}; color: {PRIMARY}; "
            f"border: 1px solid {PRIMARY}; border-radius: {R_SM - 2}px; "
            f"padding: 4px 12px; font-size: 13px; font-weight: 700;",
            extra="{sel}:hover { background-color: %s; }" % PRIMARY_RING,
        ))
        apply_btn.clicked.connect(
            lambda _checked=False, p=c["param"], t=c["target"]: on_apply(p, t))
        head_row.addWidget(apply_btn)
    content.addLayout(head_row)

    value_row = QHBoxLayout()
    value_row.setSpacing(8)
    unit = f" {c['unit']}" if c.get("unit") else ""
    cur = QLabel(f"{c.get('current','—')}{unit}")
    cur.setStyleSheet(f"color: {TEXT2}; font-size: 13px; font-family: {FF_MONO};")
    value_row.addWidget(cur)
    arrow = QLabel("→")
    arrow.setStyleSheet(f"color: {TEXT3}; font-size: 13px;")
    value_row.addWidget(arrow)
    tgt = QLabel(f"{c.get('target','—')}{unit}")
    tgt.setStyleSheet(
        f"color: {PRIMARY}; font-size: 13px; font-weight: 700; font-family: {FF_MONO};")
    value_row.addWidget(tgt)

    change_pct = c.get("change_pct")
    if change_pct is not None and change_pct != 0:
        pct_color = WARNING if abs(change_pct) > 30 else TEXT3
        pct = QLabel(f"({'+' if change_pct > 0 else ''}{change_pct:.0f}%)")
        pct.setStyleSheet(f"color: {pct_color}; font-size: 13px;")
        value_row.addWidget(pct)
    value_row.addStretch()
    content.addLayout(value_row)

    if c.get("note"):
        note = QLabel(c["note"])
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {TEXT2}; font-size: 13px;")
        content.addWidget(note)

    if has_conflict:
        content.addWidget(flag_note(
            "warn", 'See "Conflicting Recommendations" above before applying'))

    layout.addLayout(content, 1)
    return row


def _finding_card(finding, on_apply, conflict_params):
    """SCOPED at all three levels -- card, head, drv_box. Previously each
    was a bare declaration, so the cascades nested."""
    sev = finding.get("severity", "warn")
    color = SEV_FG.get(sev, WARNING)
    bg = SEV_DIM.get(sev, WARNING_DIM)
    border = SEV_BORDER.get(sev, WARNING_BORDER)

    card = QFrame()
    card.setStyleSheet(scoped(
        card,
        f"background-color: {bg}; border: 1px solid {border}; "
        f"border-radius: {R_MD - 1}px;"
    ))
    layout = QVBoxLayout(card)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    head = QFrame()
    head.setStyleSheet(scoped(
        head,
        f"background-color: transparent; border: none; "
        f"border-bottom: 1px solid {border};"
    ))
    hl = QHBoxLayout(head)
    hl.setContentsMargins(14, 12, 14, 12)
    hl.setSpacing(10)
    hl.addWidget(status_badge("fail" if sev == "fail" else "warn", size=18))
    text_box = QVBoxLayout()
    text_box.setSpacing(3)
    metric = QLabel(finding.get("failure_metric", ""))
    metric.setWordWrap(True)
    metric.setStyleSheet(f"color: {TEXT}; font-size: 14px; font-weight: 700;")
    text_box.addWidget(metric)
    expl = QLabel(finding.get("explanation", ""))
    expl.setWordWrap(True)
    expl.setStyleSheet(f"color: {TEXT2}; font-size: 13px;")
    text_box.addWidget(expl)
    hl.addLayout(text_box, 1)
    layout.addWidget(head)

    drivers = finding.get("drivers") or []
    if drivers:
        drv_box = QFrame()
        drv_box.setStyleSheet(scoped(
            drv_box,
            f"background-color: transparent; border: none; "
            f"border-bottom: 1px solid {border};"
        ))
        dl = QVBoxLayout(drv_box)
        dl.setContentsMargins(14, 10, 14, 10)
        dl.setSpacing(10)
        dl_head = QLabel("CONTRIBUTING FACTORS")
        dl_head.setStyleSheet(
            f"color: {TEXT3}; font-size: 12px; font-weight: 700; letter-spacing: .06em;")
        dl.addWidget(dl_head)
        for d in drivers:
            dl.addLayout(_driver_row(d, color))
        layout.addWidget(drv_box)

    corrections = finding.get("corrections") or []
    if corrections:
        corr_box = QFrame()
        corr_box.setStyleSheet(scoped(
            corr_box, "background-color: transparent; border: none;"))
        cl = QVBoxLayout(corr_box)
        cl.setContentsMargins(14, 10, 14, 12)
        cl.setSpacing(8)
        cl_head = QLabel("SUGGESTED CORRECTIONS")
        cl_head.setStyleSheet(
            f"color: {TEXT3}; font-size: 12px; font-weight: 700; letter-spacing: .06em;")
        cl.addWidget(cl_head)
        for c in corrections:
            has_conflict = c.get("param") in conflict_params
            cl.addWidget(_correction_row(c, c.get("priority", 1), has_conflict, on_apply))
        layout.addWidget(corr_box)

    return card


def _detect_conflicts(findings):
    """Mirrors RootCausePanel.jsx's conflict detection exactly: a conflict
    exists when 2+ corrections across all findings target the SAME input
    param with DIFFERENT target values."""
    param_map = {}
    for f in findings:
        for c in f.get("corrections") or []:
            param = c.get("param")
            if not param:
                continue
            param_map.setdefault(param, []).append({
                "finding_label": f.get("failure_metric", ""),
                "current": c.get("current"),
                "target": c.get("target"),
                "unit": c.get("unit"),
            })
    conflicts = []
    for param, entries in param_map.items():
        if len({e["target"] for e in entries}) > 1:
            conflicts.append({"param": param, "entries": entries})
    return conflicts


class RootCauseSection(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(0, 0, 0, 0)
        self.layout_.setSpacing(10)

    def set_data(self, results, on_apply):
        clear_layout(self.layout_)

        results = results or {}
        findings = results.get("root_cause") or []
        checks = results.get("checks") or []
        types = [_norm(c.get("type")) for c in checks]
        fail_count = types.count("fail")
        warn_count = types.count("warn")

        header = QHBoxLayout()
        title = QLabel("ROOT CAUSE ANALYSIS")
        title.setStyleSheet(
            f"color: {TEXT3}; font-size: 13px; font-weight: 700; letter-spacing: .07em;")
        header.addWidget(title)
        header.addStretch()
        count_lbl = QLabel(f"{len(findings)} finding{'s' if len(findings) != 1 else ''}")
        count_lbl.setStyleSheet(f"color: {TEXT3}; font-size: 13px;")
        header.addWidget(count_lbl)
        self.layout_.addLayout(header)

        if not findings:
            if fail_count == 0 and warn_count == 0:
                ok_box = QFrame()
                ok_box.setStyleSheet(scoped(
                    ok_box, "background-color: transparent; border: none;"))
                ol = QVBoxLayout(ok_box)
                ol.setAlignment(Qt.AlignmentFlag.AlignCenter)
                ol.setContentsMargins(16, 24, 16, 24)
                icon = QLabel("✓")
                icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
                icon.setStyleSheet(f"color: {SUCCESS}; font-size: 30px;")
                ol.addWidget(icon)
                msg = QLabel("All checks pass — no corrections required")
                msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
                msg.setStyleSheet(
                    f"color: {SUCCESS}; font-size: 15px; font-weight: 700;")
                ol.addWidget(msg)
                self.layout_.addWidget(ok_box)
            return

        conflicts = _detect_conflicts(findings)
        conflict_params = [c["param"] for c in conflicts]

        if conflicts:
            conflict_box = QFrame()
            conflict_box.setStyleSheet(scoped(
                conflict_box,
                f"background-color: {WARNING_DIM}; "
                f"border: 1px solid {WARNING_BORDER}; "
                f"border-radius: {R_MD - 1}px;"
            ))
            cl = QVBoxLayout(conflict_box)
            cl.setContentsMargins(14, 12, 14, 12)
            cl.setSpacing(8)

            head_row = QHBoxLayout()
            head_row.addWidget(status_badge("warn", size=16))
            head_lbl = QLabel("Conflicting Recommendations")
            head_lbl.setStyleSheet(
                f"color: {WARNING}; font-size: 14px; font-weight: 700;")
            head_row.addWidget(head_lbl)
            head_row.addStretch()
            cl.addLayout(head_row)

            desc = QLabel(
                "The corrections below ask for different values for the same parameter. "
                "Applying one may worsen the other check — review both before changing "
                "this value."
            )
            desc.setWordWrap(True)
            desc.setStyleSheet(f"color: {TEXT2}; font-size: 13px;")
            cl.addWidget(desc)

            for c in conflicts:
                pbox, pl = card_frame(bg=PANEL2, border=BORDER, radius=R_SM,
                                      margins=(10, 8, 10, 8), spacing=4)
                pname = QLabel(c["param"])
                pname.setStyleSheet(
                    f"color: {TEXT}; font-size: 13px; font-weight: 700; "
                    f"font-family: {FF_MONO};")
                pl.addWidget(pname)
                for e in c["entries"]:
                    erow = QHBoxLayout()
                    elabel = QLabel(e["finding_label"])
                    elabel.setWordWrap(True)
                    elabel.setStyleSheet(f"color: {TEXT2}; font-size: 13px;")
                    erow.addWidget(elabel, 1)
                    u = f" {e['unit']}" if e.get("unit") else ""
                    eval_lbl = QLabel(f"{e['current']}{u} → {e['target']}{u}")
                    eval_lbl.setStyleSheet(
                        f"color: {PRIMARY}; font-size: 13px; font-weight: 700; "
                        f"font-family: {FF_MONO};")
                    erow.addWidget(eval_lbl)
                    pl.addLayout(erow)
                cl.addWidget(pbox)
            self.layout_.addWidget(conflict_box)

        sorted_findings = sorted(
            findings, key=lambda f: 0 if f.get("severity") == "fail" else 1)
        for f in sorted_findings:
            self.layout_.addWidget(_finding_card(f, on_apply, conflict_params))


# ── DesignRecommendationsPanel port ──────────────────────────────────────
class DesignRecommendationsSection(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(0, 0, 0, 0)
        self.layout_.setSpacing(8)

    def set_data(self, results):
        clear_layout(self.layout_)

        results = results or {}
        recs = results.get("design_recommendations") or []
        checks = results.get("checks") or []
        any_fail = any(_norm(c.get("type") or c.get("status")) == "fail" for c in checks)
        truly_clean = not recs and not any_fail

        if truly_clean:
            box = QFrame()
            box.setStyleSheet(scoped(
                box,
                f"background-color: {SUCCESS_DIM}; "
                f"border: 1px solid {SUCCESS_BORDER}; border-radius: {R_SM}px;"
            ))
            bl = QHBoxLayout(box)
            bl.setContentsMargins(14, 11, 14, 11)
            bl.setSpacing(10)
            bl.addWidget(status_badge("ok", size=20))
            text_box = QVBoxLayout()
            text_box.setSpacing(2)
            head = QLabel("Design passes all checks")
            head.setStyleSheet(f"color: {SUCCESS}; font-size: 14px; font-weight: 700;")
            text_box.addWidget(head)
            sub = QLabel("No corrective actions required for this configuration.")
            sub.setStyleSheet(f"color: {TEXT2}; font-size: 13px;")
            text_box.addWidget(sub)
            bl.addLayout(text_box, 1)
            self.layout_.addWidget(box)
            return

        header = QHBoxLayout()
        title = QLabel("DESIGN RECOMMENDATIONS")
        title.setStyleSheet(
            f"color: {TEXT3}; font-size: 13px; font-weight: 700; letter-spacing: .07em;")
        header.addWidget(title)

        fail_n = sum(1 for r in recs if r.get("status") == "fail")
        warn_n = sum(1 for r in recs if r.get("status") == "warn")
        for count, label, fg, dim, brd in (
            (fail_n, "FAIL", DANGER, DANGER_DIM, DANGER_BORDER),
            (warn_n, "WARN", WARNING, WARNING_DIM, WARNING_BORDER),
        ):
            if not count:
                continue
            badge = QLabel(f"{count} {label}")
            badge.setStyleSheet(scoped(
                badge,
                f"background-color: {dim}; color: {fg}; "
                f"border: 1px solid {brd}; border-radius: {R_PILL}px; "
                f"padding: 1px 7px; font-size: 12px; font-weight: 700;"
            ))
            header.addWidget(badge)
        header.addStretch()
        self.layout_.addLayout(header)

        for rec in sorted(recs, key=lambda r: 0 if r.get("status") == "fail" else 1):
            status = rec.get("status", "warn")
            color = SEV_FG.get(status, WARNING)
            bg = SEV_DIM.get(status, WARNING_DIM)
            border = SEV_BORDER.get(status, WARNING_BORDER)

            card = QFrame()
            card.setStyleSheet(scoped(
                card,
                f"background-color: {bg}; border: 1px solid {border}; "
                f"border-radius: {R_SM}px;"
            ))
            cl = QVBoxLayout(card)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(0)

            head = QFrame()
            head.setStyleSheet(scoped(
                head,
                f"background-color: {PANEL2}; border: none; "
                f"border-bottom: 1px solid {border};"
            ))
            hl = QHBoxLayout(head)
            hl.setContentsMargins(12, 7, 12, 7)
            hl.setSpacing(8)
            hl.addWidget(status_badge(status, size=16))
            check_tag = QLabel(rec.get("check", ""))
            check_tag.setStyleSheet(
                f"color: {color}; font-size: 12px; font-weight: 700; "
                f"letter-spacing: .08em;")
            hl.addWidget(check_tag)
            problem = QLabel(rec.get("problem", ""))
            problem.setWordWrap(True)
            problem.setStyleSheet(f"color: {TEXT2}; font-size: 13px;")
            hl.addWidget(problem, 1)
            cl.addWidget(head)

            actions_box = QVBoxLayout()
            actions_box.setContentsMargins(12, 8, 12, 10)
            actions_box.setSpacing(5)
            for j, action in enumerate(rec.get("actions") or []):
                arow = QHBoxLayout()
                arow.setSpacing(8)
                num = QLabel(f"{j + 1}.")
                num.setStyleSheet(
                    f"color: {color}; font-size: 12px; font-weight: 700; "
                    f"font-family: {FF_MONO};")
                num.setFixedWidth(16)
                arow.addWidget(num)
                action_lbl = QLabel(action)
                action_lbl.setWordWrap(True)
                action_lbl.setStyleSheet(f"color: {TEXT2}; font-size: 13px;")
                arow.addWidget(action_lbl, 1)
                actions_box.addLayout(arow)
            cl.addLayout(actions_box)
            self.layout_.addWidget(card)


# ── ChecksPanel port (flat checks list + design summary grid) ────────────
class FlatChecksSection(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(0, 0, 0, 0)
        self.layout_.setSpacing(8)

    def set_data(self, inputs, results):
        clear_layout(self.layout_)

        inputs = inputs or {}
        results = results or {}
        checks = results.get("checks") or []

        checks_header = QLabel("ENGINEERING CHECKS")
        checks_header.setStyleSheet(
            f"color: {TEXT3}; font-size: 13px; font-weight: 700; letter-spacing: .07em;")
        self.layout_.addWidget(checks_header)

        if not checks:
            flag_note("info", "No checks available yet.", parent_layout=self.layout_)
        else:
            checks_box = QVBoxLayout()
            checks_box.setSpacing(5)
            for c in checks:
                flag_note(_norm(c.get("type")), c.get("msg", ""),
                          parent_layout=checks_box)
            self.layout_.addLayout(checks_box)

        summary_header = QLabel("DESIGN SUMMARY")
        summary_header.setStyleSheet(
            f"color: {TEXT3}; font-size: 13px; font-weight: 700; "
            f"letter-spacing: .07em; margin-top: 6px;")
        self.layout_.addWidget(summary_header)

        mat = results.get("mat") or results.get("material") or {}
        bkt = results.get("bucket") or {}
        rho = results.get("rho", mat.get("rho_loose", inputs.get("custom_rho", "—")))
        T1, T2 = results.get("T1"), results.get("T2")
        T3, F_eff = results.get("T3"), results.get("F_eff")
        tight_side = ((T3 + F_eff) / 1000
                      if (T3 is not None and F_eff is not None) else None)
        boot_shaft = (results.get("boot_pulley") or {}).get("shaft") or {}

        summary = [
            ("Material", mat.get("name", inputs.get("mat_id", "—"))),
            ("Density", f"{rho} kg/m³"),
            ("Lift Height", f"{inputs.get('H_m', '—')} m"),
            ("Required Capacity", f"{inputs.get('Q_req', '—')} t/h"),
            ("Achieved Capacity", f"{fmt(results.get('Q'), 1)} t/h"),
            ("Belt Speed", f"{fmt(results.get('v'), 3)} m/s"),
            ("Head Pulley Dia.",
             f"{inputs.get('D_mm', '—')} mm @ {inputs.get('n_rpm', '—')} rpm"),
            ("Bucket Series", f"{bkt.get('id', '—')} — {bkt.get('V', '—')}L"),
            ("Belt Width", f"{results.get('belt_w', '—')} mm"),
            ("Lift Power", f"{fmt(results.get('P_lift'), 2)} kW"),
            ("Total Power", f"{fmt(results.get('P_total'), 2)} kW"),
            ("Motor", f"{results.get('motor_kw', '—')} kW"),
            ("Material Component T1",
             f"{fmt(T1 / 1000 if T1 is not None else None, 2)} kN"),
            ("Self-Weight Comp. T2",
             f"{fmt(T2 / 1000 if T2 is not None else None, 2)} kN"),
            ("Take-up / Slack T3",
             f"{fmt(T3 / 1000 if T3 is not None else None, 2)} kN"),
            ("Belt Tight Side (T3+Feff)", f"{fmt(tight_side, 2)} kN"),
            ("Min Shaft Dia.", f"{fmt(results.get('d_mm'), 1)} mm"),
            ("Shaft Material", results.get("shaft_material_name", "—")),
            ("Shaft Section", results.get("shaft_section", "—")),
            ("Hub Connection", results.get("shaft_hub_connection", "—")),
            ("Centrifugal Ratio", fmt(results.get("cr"), 3)),
            ("Discharge Angle", f"{fmt(results.get('theta_rel'), 1)}° from vertical"),
            ("Belt Length",
             f"{results.get('belt_length_total_m')} m"
             if results.get("belt_length_total_m") is not None else "—"),
            ("Bucket Count",
             f"{results.get('n_buckets')} off"
             if results.get("n_buckets") is not None else "—"),
            ("Boot Shaft Dia.", f"{fmt(boot_shaft.get('d_mm'), 1)} mm"),
            ("Take-Up Type", str(inputs.get("takeup_type", "gravity")).capitalize()),
            ("Chain Series",
             (results.get("chain_selected") or {}).get("name", "—")
             if results.get("is_chain") else "n/a (belt)"),
            ("Casing Plate",
             f"{fmt((results.get('casing_panel') or {}).get('t_use_mm'), 1)} mm"),
        ]

        grid = QGridLayout()
        grid.setSpacing(6)
        for i, (k, v) in enumerate(summary):
            row_box = QFrame()
            # Zebra striping only -- no border, so nothing to cascade.
            row_box.setStyleSheet(scoped(
                row_box,
                f"background-color: {PANEL2 if i % 2 == 0 else 'transparent'}; "
                f"border: none; border-radius: 3px;"
            ))
            rl = QHBoxLayout(row_box)
            rl.setContentsMargins(10, 5, 10, 5)
            klabel = QLabel(k)
            klabel.setStyleSheet(f"color: {TEXT2}; font-size: 13px;")
            rl.addWidget(klabel)
            rl.addStretch()
            vlabel = QLabel(str(v))
            vlabel.setStyleSheet(
                f"color: {TEXT}; font-size: 13px; font-family: {FF_MONO};")
            rl.addWidget(vlabel)
            grid.addWidget(row_box, i // 2, i % 2)
        self.layout_.addLayout(grid)


class ChecksPanel(QWidget):
    """Stacks RootCauseSection + DesignRecommendationsSection +
    FlatChecksSection, matching BucketElevatorPage.jsx's real Checks-tab
    composition. set_data(inputs, results) like every other panel;
    on_apply_correction(param, value) is wired by main.py to merge a
    correction into the live payload and recalculate, mirroring
    RootCausePanel.jsx's setField prop."""

    def __init__(self, on_apply_correction=None, parent=None):
        super().__init__(parent)
        self.on_apply_correction = on_apply_correction
        self.setStyleSheet(plain_bg(self, PANEL))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(scoped(scroll, "border: none; background: transparent;"))
        body = QWidget()
        body.setStyleSheet(plain_bg(body, PANEL))
        self.body_layout = QVBoxLayout(body)
        self.body_layout.setContentsMargins(16, 16, 16, 16)
        self.body_layout.setSpacing(18)

        self.root_cause_section = RootCauseSection()
        self.body_layout.addWidget(self.root_cause_section)
        self.recommendations_section = DesignRecommendationsSection()
        self.body_layout.addWidget(self.recommendations_section)
        self.flat_checks_section = FlatChecksSection()
        self.body_layout.addWidget(self.flat_checks_section)
        self.body_layout.addStretch()

        scroll.setWidget(body)
        outer.addWidget(scroll)

    def set_data(self, inputs, results):
        self.root_cause_section.set_data(results, self.on_apply_correction)
        self.recommendations_section.set_data(results)
        self.flat_checks_section.set_data(inputs, results)