"""
components/checks_panel.py -- Checks tab center-console content.
═══════════════════════════════════════════════════════════════════════════
Faithful port of three real JSX files, stacked in the exact order
Bucketelevatorpage.jsx itself uses for the Checks tab (confirmed directly,
not assumed):
    RootCausePanel.jsx + DesignRecommendationsPanel.jsx + ChecksPanel.jsx

RootCausePanel reads results.root_cause (root_cause.py's analyse()) --
rich findings with contributing-factor "driver" bars and Apply-able
corrections, plus conflict detection when two findings ask for opposite
changes to the same input parameter.

DesignRecommendationsPanel reads results.design_recommendations
(structural.py's design_recommendations()) -- a simpler, structural-only
recommendation list (capacity/speed/CR/slip/bearing/headshaft). Confirmed
directly this is a narrower, older engine than root_cause.py -- both are
real and both are shown, matching the real JSX exactly rather than
picking one.

ChecksPanel reads results.checks directly -- the complete flat list,
unfiltered, plus a 2-column Design Summary grid.

Backend coverage audit (per direct instruction this round -- confirmed,
not assumed): root_cause.py already covered take-up (screw AND
hydraulic), casing panel deflection, casing clearance, discharge chute
angle, and bucket bolt fatigue. Genuinely missing and added this round
(root_cause.py): boot shaft bearing L10, chain safety factor, chain
speed -- all real, already-computed fields that previously had no
root-cause finding at all, confirmed via a real bug (the original head-
bearing finding's substring match would have silently swallowed boot-
bearing messages too) found and fixed during the same pass.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea, QPushButton, QGridLayout,
)
from PySide6.QtCore import Qt

from theme import PANEL, PANEL2, BORDER, TEXT, TEXT2, TEXT3, MUTED, PRIMARY, SUCCESS, WARNING, DANGER
from .dialog_helpers import status_badge, flag_note


def fmt(v, dp=2, fb="—"):
    if v is None:
        return fb
    try:
        return f"{float(v):.{dp}f}"
    except (TypeError, ValueError):
        return fb


# ── RootCausePanel port ──────────────────────────────────────────────────
def _driver_row(d, sev_color):
    box = QVBoxLayout()
    box.setSpacing(3)
    head = QHBoxLayout()
    head.setSpacing(8)
    label = QLabel(f"{d.get('label','')}  =  {d.get('current','—')}{(' ' + d['unit']) if d.get('unit') else ''}")
    label.setStyleSheet(f"color: {TEXT}; font-size: 11px; font-weight: 600;")
    head.addWidget(label, 1)
    priority = d.get("priority", 2)
    tag = QLabel("PRIMARY" if priority == 1 else f"#{priority}")
    tag.setStyleSheet(
        f"background-color: {'rgba(74,158,255,.15)' if priority == 1 else 'rgba(100,116,139,.15)'}; "
        f"color: {sev_color if priority == 1 else TEXT3}; border-radius: 999px; "
        f"padding: 1px 7px; font-size: 9px; font-weight: 700;"
    )
    head.addWidget(tag)
    box.addLayout(head)

    bar_bg = QFrame()
    bar_bg.setFixedHeight(4)
    bar_bg.setStyleSheet(f"background-color: {BORDER}; border-radius: 2px;")
    bar_layout = QHBoxLayout(bar_bg)
    bar_layout.setContentsMargins(0, 0, 0, 0)
    fill_pct = max(0, 100 - (priority - 1) * 30)
    fill = QFrame()
    fill.setStyleSheet(f"background-color: {sev_color if priority == 1 else TEXT3}; border-radius: 2px;")
    bar_layout.addWidget(fill, fill_pct)
    spacer = QFrame()
    spacer.setStyleSheet("background-color: transparent;")
    bar_layout.addWidget(spacer, 100 - fill_pct)
    box.addWidget(bar_bg)

    impact = QLabel(d.get("impact", ""))
    impact.setWordWrap(True)
    impact.setStyleSheet(f"color: {TEXT2}; font-size: 10.5px;")
    box.addWidget(impact)
    return box


def _correction_row(c, priority, has_conflict, on_apply):
    row = QFrame()
    row.setStyleSheet(
        f"background-color: {PANEL2}; border: 1px solid {'rgba(217,142,0,.35)' if has_conflict else BORDER}; "
        f"border-radius: 6px;"
    )
    layout = QHBoxLayout(row)
    layout.setContentsMargins(10, 8, 10, 8)
    layout.setSpacing(10)

    marker = QLabel(str(priority))
    marker.setFixedSize(22, 22)
    marker.setAlignment(Qt.AlignmentFlag.AlignCenter)
    marker.setStyleSheet(
        f"background-color: {'rgba(74,158,255,.15)' if priority == 1 else 'rgba(100,116,139,.12)'}; "
        f"color: {PRIMARY if priority == 1 else TEXT3}; border: 1px solid "
        f"{PRIMARY if priority == 1 else BORDER}; border-radius: 11px; font-size: 11px; font-weight: 700;"
    )
    layout.addWidget(marker)

    content = QVBoxLayout()
    content.setSpacing(4)
    head_row = QHBoxLayout()
    label = QLabel(c.get("label", ""))
    label.setStyleSheet(f"color: {TEXT}; font-size: 12px; font-weight: 700;")
    head_row.addWidget(label, 1)
    can_apply = (on_apply is not None and c.get("param") and c.get("param") != "bearing"
                 and c.get("target") is not None and not isinstance(c.get("target"), str))
    if can_apply:
        apply_btn = QPushButton("Apply")
        apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_btn.setStyleSheet(
            f"background-color: rgba(74,158,255,.15); color: {PRIMARY}; border: 1px solid {PRIMARY}; "
            f"border-radius: 4px; padding: 4px 12px; font-size: 10.5px; font-weight: 700;"
        )
        apply_btn.clicked.connect(lambda: on_apply(c["param"], c["target"]))
        head_row.addWidget(apply_btn)
    content.addLayout(head_row)

    value_row = QHBoxLayout()
    value_row.setSpacing(8)
    cur = QLabel(f"{c.get('current','—')}{(' ' + c['unit']) if c.get('unit') else ''}")
    cur.setStyleSheet(f"color: {TEXT2}; font-size: 11px; font-family: 'JetBrains Mono', monospace;")
    value_row.addWidget(cur)
    arrow = QLabel("→")
    arrow.setStyleSheet(f"color: {TEXT3}; font-size: 11px;")
    value_row.addWidget(arrow)
    tgt = QLabel(f"{c.get('target','—')}{(' ' + c['unit']) if c.get('unit') else ''}")
    tgt.setStyleSheet(f"color: {PRIMARY}; font-size: 11px; font-weight: 700; font-family: 'JetBrains Mono', monospace;")
    value_row.addWidget(tgt)
    change_pct = c.get("change_pct")
    if change_pct is not None and change_pct != 0:
        pct_color = WARNING if abs(change_pct) > 30 else TEXT3
        pct = QLabel(f"({'+' if change_pct > 0 else ''}{change_pct:.0f}%)")
        pct.setStyleSheet(f"color: {pct_color}; font-size: 10px;")
        value_row.addWidget(pct)
    value_row.addStretch()
    content.addLayout(value_row)

    if c.get("note"):
        note = QLabel(c["note"])
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {TEXT2}; font-size: 10.5px;")
        content.addWidget(note)

    if has_conflict:
        conflict_note = flag_note("warn", "See \"Conflicting Recommendations\" above before applying")
        content.addWidget(conflict_note)

    layout.addLayout(content, 1)
    return row


def _finding_card(finding, on_apply, conflict_params):
    sev = finding.get("severity", "warn")
    color = DANGER if sev == "fail" else WARNING
    bg = "rgba(224,82,82,.05)" if sev == "fail" else "rgba(217,142,0,.05)"
    border = "rgba(224,82,82,.2)" if sev == "fail" else "rgba(217,142,0,.2)"

    card = QFrame()
    card.setStyleSheet(f"background-color: {bg}; border: 1px solid {border}; border-radius: 7px;")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    head = QFrame()
    head.setStyleSheet(f"border-bottom: 1px solid {border};")
    hl = QHBoxLayout(head)
    hl.setContentsMargins(14, 12, 14, 12)
    hl.setSpacing(10)
    hl.addWidget(status_badge("fail" if sev == "fail" else "warn", size=18))
    text_box = QVBoxLayout()
    text_box.setSpacing(3)
    metric = QLabel(finding.get("failure_metric", ""))
    metric.setWordWrap(True)
    metric.setStyleSheet(f"color: {TEXT}; font-size: 12px; font-weight: 700;")
    text_box.addWidget(metric)
    expl = QLabel(finding.get("explanation", ""))
    expl.setWordWrap(True)
    expl.setStyleSheet(f"color: {TEXT2}; font-size: 11px;")
    text_box.addWidget(expl)
    hl.addLayout(text_box, 1)
    layout.addWidget(head)

    drivers = finding.get("drivers") or []
    if drivers:
        drv_box = QFrame()
        drv_box.setStyleSheet(f"border-bottom: 1px solid {border};")
        dl = QVBoxLayout(drv_box)
        dl.setContentsMargins(14, 10, 14, 10)
        dl.setSpacing(10)
        dl_head = QLabel("CONTRIBUTING FACTORS")
        dl_head.setStyleSheet(f"color: {TEXT3}; font-size: 9.5px; font-weight: 700; letter-spacing: .06em;")
        dl.addWidget(dl_head)
        for d in drivers:
            dl.addLayout(_driver_row(d, color))
        layout.addWidget(drv_box)

    corrections = finding.get("corrections") or []
    if corrections:
        corr_box = QFrame()
        cl = QVBoxLayout(corr_box)
        cl.setContentsMargins(14, 10, 14, 12)
        cl.setSpacing(8)
        cl_head = QLabel("SUGGESTED CORRECTIONS")
        cl_head.setStyleSheet(f"color: {TEXT3}; font-size: 9.5px; font-weight: 700; letter-spacing: .06em;")
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
    for fi, f in enumerate(findings):
        for c in f.get("corrections") or []:
            param = c.get("param")
            if not param:
                continue
            param_map.setdefault(param, []).append({
                "finding_label": f.get("failure_metric", ""),
                "current": c.get("current"), "target": c.get("target"), "unit": c.get("unit"),
            })
    conflicts = []
    for param, entries in param_map.items():
        targets = {e["target"] for e in entries}
        if len(targets) > 1:
            conflicts.append({"param": param, "entries": entries})
    return conflicts


class RootCauseSection(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(0, 0, 0, 0)
        self.layout_.setSpacing(10)

    def set_data(self, results, on_apply):
        while self.layout_.count():
            item = self.layout_.takeAt(0)
            w = item.widget() if item else None
            if w:
                w.setParent(None)
                w.deleteLater()

        findings = (results or {}).get("root_cause") or []
        checks = (results or {}).get("checks") or []
        fail_count = sum(1 for c in checks if c.get("type") == "fail")
        warn_count = sum(1 for c in checks if c.get("type") == "warn")

        header = QHBoxLayout()
        title = QLabel("ROOT CAUSE ANALYSIS")
        title.setStyleSheet(f"color: {TEXT3}; font-size: 11px; font-weight: 700; letter-spacing: .07em;")
        header.addWidget(title)
        header.addStretch()
        count_lbl = QLabel(f"{len(findings)} finding{'s' if len(findings) != 1 else ''}")
        count_lbl.setStyleSheet(f"color: {TEXT3}; font-size: 10px;")
        header.addWidget(count_lbl)
        self.layout_.addLayout(header)

        if not findings:
            if fail_count == 0 and warn_count == 0:
                ok_box = QFrame()
                ok_box.setStyleSheet("background-color: transparent;")
                ol = QVBoxLayout(ok_box)
                ol.setAlignment(Qt.AlignmentFlag.AlignCenter)
                ol.setContentsMargins(16, 24, 16, 24)
                icon = QLabel("✅")
                icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
                icon.setStyleSheet("font-size: 28px;")
                ol.addWidget(icon)
                msg = QLabel("All checks pass — no corrections required")
                msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
                msg.setStyleSheet(f"color: {SUCCESS}; font-size: 13px; font-weight: 700;")
                ol.addWidget(msg)
                self.layout_.addWidget(ok_box)
            return

        conflicts = _detect_conflicts(findings)
        conflict_params = [c["param"] for c in conflicts]
        if conflicts:
            conflict_box = QFrame()
            conflict_box.setStyleSheet("background-color: rgba(217,142,0,.08); border: 1px solid rgba(217,142,0,.3); border-radius: 7px;")
            cl = QVBoxLayout(conflict_box)
            cl.setContentsMargins(14, 12, 14, 12)
            cl.setSpacing(8)
            head_row = QHBoxLayout()
            head_row.addWidget(status_badge("warn", size=16))
            head_lbl = QLabel("Conflicting Recommendations")
            head_lbl.setStyleSheet(f"color: {WARNING}; font-size: 12px; font-weight: 700;")
            head_row.addWidget(head_lbl)
            head_row.addStretch()
            cl.addLayout(head_row)
            desc = QLabel(
                "The corrections below ask for different values for the same parameter. "
                "Applying one may worsen the other check — review both before changing this value."
            )
            desc.setWordWrap(True)
            desc.setStyleSheet(f"color: {TEXT2}; font-size: 11px;")
            cl.addWidget(desc)
            for c in conflicts:
                pbox = QFrame()
                pbox.setStyleSheet(f"background-color: {PANEL2}; border: 1px solid {BORDER}; border-radius: 5px;")
                pl = QVBoxLayout(pbox)
                pl.setContentsMargins(10, 8, 10, 8)
                pl.setSpacing(4)
                pname = QLabel(c["param"])
                pname.setStyleSheet(f"color: {TEXT}; font-size: 11px; font-weight: 700; font-family: 'JetBrains Mono', monospace;")
                pl.addWidget(pname)
                for e in c["entries"]:
                    erow = QHBoxLayout()
                    elabel = QLabel(e["finding_label"])
                    elabel.setStyleSheet(f"color: {TEXT2}; font-size: 10.5px;")
                    erow.addWidget(elabel, 1)
                    eval_lbl = QLabel(
                        f"{e['current']}{(' ' + e['unit']) if e.get('unit') else ''} → "
                        f"{e['target']}{(' ' + e['unit']) if e.get('unit') else ''}"
                    )
                    eval_lbl.setStyleSheet(f"color: {PRIMARY}; font-size: 10.5px; font-weight: 700; font-family: 'JetBrains Mono', monospace;")
                    erow.addWidget(eval_lbl)
                    pl.addLayout(erow)
                cl.addWidget(pbox)
            self.layout_.addWidget(conflict_box)

        sorted_findings = sorted(findings, key=lambda f: 0 if f.get("severity") == "fail" else 1)
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
        while self.layout_.count():
            item = self.layout_.takeAt(0)
            w = item.widget() if item else None
            if w:
                w.setParent(None)
                w.deleteLater()

        results = results or {}
        recs = results.get("design_recommendations") or []
        checks = results.get("checks") or []
        any_fail = any((c.get("type") or c.get("status")) == "fail" for c in checks)
        truly_clean = not recs and not any_fail

        if truly_clean:
            box = QFrame()
            box.setStyleSheet("background-color: rgba(31,184,110,.06); border: 1px solid rgba(31,184,110,.25); border-radius: 6px;")
            bl = QHBoxLayout(box)
            bl.setContentsMargins(14, 11, 14, 11)
            bl.setSpacing(10)
            bl.addWidget(status_badge("ok", size=20))
            text_box = QVBoxLayout()
            text_box.setSpacing(2)
            head = QLabel("Design passes all checks")
            head.setStyleSheet(f"color: {SUCCESS}; font-size: 12px; font-weight: 700;")
            text_box.addWidget(head)
            sub = QLabel("No corrective actions required for this configuration.")
            sub.setStyleSheet(f"color: {TEXT2}; font-size: 10px;")
            text_box.addWidget(sub)
            bl.addLayout(text_box, 1)
            self.layout_.addWidget(box)
            return

        header = QHBoxLayout()
        title = QLabel("DESIGN RECOMMENDATIONS")
        title.setStyleSheet(f"color: {TEXT3}; font-size: 11px; font-weight: 700; letter-spacing: .07em;")
        header.addWidget(title)
        fail_n = sum(1 for r in recs if r.get("status") == "fail")
        warn_n = sum(1 for r in recs if r.get("status") == "warn")
        if fail_n:
            f_badge = QLabel(f"{fail_n} FAIL")
            f_badge.setStyleSheet(f"background-color: rgba(224,82,82,.12); color: {DANGER}; border: 1px solid rgba(224,82,82,.3); border-radius: 999px; padding: 1px 7px; font-size: 9px; font-weight: 700;")
            header.addWidget(f_badge)
        if warn_n:
            w_badge = QLabel(f"{warn_n} WARN")
            w_badge.setStyleSheet(f"background-color: rgba(217,142,0,.12); color: {WARNING}; border: 1px solid rgba(217,142,0,.3); border-radius: 999px; padding: 1px 7px; font-size: 9px; font-weight: 700;")
            header.addWidget(w_badge)
        header.addStretch()
        self.layout_.addLayout(header)

        for rec in sorted(recs, key=lambda r: 0 if r.get("status") == "fail" else 1):
            status = rec.get("status", "warn")
            color = DANGER if status == "fail" else WARNING
            border = "rgba(224,82,82,.3)" if status == "fail" else "rgba(217,142,0,.3)"
            bg = "rgba(224,82,82,.05)" if status == "fail" else "rgba(217,142,0,.05)"
            card = QFrame()
            card.setStyleSheet(f"background-color: {bg}; border: 1px solid {border}; border-radius: 6px;")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(0)
            head = QFrame()
            head.setStyleSheet(f"background-color: {PANEL2}; border-bottom: 1px solid {border};")
            hl = QHBoxLayout(head)
            hl.setContentsMargins(12, 7, 12, 7)
            hl.setSpacing(8)
            hl.addWidget(status_badge(status, size=16))
            check_tag = QLabel(rec.get("check", ""))
            check_tag.setStyleSheet(f"color: {color}; font-size: 9.5px; font-weight: 700; letter-spacing: .08em;")
            hl.addWidget(check_tag)
            problem = QLabel(rec.get("problem", ""))
            problem.setWordWrap(True)
            problem.setStyleSheet(f"color: {TEXT2}; font-size: 10.5px;")
            hl.addWidget(problem, 1)
            cl.addWidget(head)

            actions_box = QVBoxLayout()
            actions_box.setContentsMargins(12, 8, 12, 10)
            actions_box.setSpacing(5)
            for j, action in enumerate(rec.get("actions") or []):
                arow = QHBoxLayout()
                arow.setSpacing(8)
                num = QLabel(f"{j+1}.")
                num.setStyleSheet(f"color: {color}; font-size: 9px; font-weight: 700; font-family: 'JetBrains Mono', monospace;")
                num.setFixedWidth(16)
                arow.addWidget(num)
                action_lbl = QLabel(action)
                action_lbl.setWordWrap(True)
                action_lbl.setStyleSheet(f"color: {TEXT2}; font-size: 11px;")
                arow.addWidget(action_lbl, 1)
                actions_box.addLayout(arow)
            cl.addLayout(actions_box)
            self.layout_.addWidget(card)


# ── ChecksPanel port (flat checks list + design summary grid) ───────────
class FlatChecksSection(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(0, 0, 0, 0)
        self.layout_.setSpacing(8)

    def set_data(self, inputs, results):
        while self.layout_.count():
            item = self.layout_.takeAt(0)
            w = item.widget() if item else None
            if w:
                w.setParent(None)
                w.deleteLater()

        inputs = inputs or {}
        results = results or {}
        checks = results.get("checks") or []

        checks_header = QLabel("ENGINEERING CHECKS")
        checks_header.setStyleSheet(f"color: {TEXT3}; font-size: 11px; font-weight: 700; letter-spacing: .07em;")
        self.layout_.addWidget(checks_header)

        if not checks:
            flag_note("info", "No checks available yet.", parent_layout=self.layout_)
        else:
            checks_box = QVBoxLayout()
            checks_box.setSpacing(5)
            for c in checks:
                status = c.get("type", "info")
                status = "ok" if status == "pass" else status
                flag_note(status, c.get("msg", ""), parent_layout=checks_box)
            self.layout_.addLayout(checks_box)

        summary_header = QLabel("DESIGN SUMMARY")
        summary_header.setStyleSheet(f"color: {TEXT3}; font-size: 11px; font-weight: 700; letter-spacing: .07em; margin-top: 6px;")
        self.layout_.addWidget(summary_header)

        mat = results.get("mat") or results.get("material") or {}
        bkt = results.get("bucket") or {}
        rho = results.get("rho", mat.get("rho_loose", inputs.get("custom_rho", "—")))
        T1, T2, T3, F_eff = results.get("T1"), results.get("T2"), results.get("T3"), results.get("F_eff")
        tight_side = (T3 + F_eff) / 1000 if (T3 is not None and F_eff is not None) else None

        summary = [
            ("Material", mat.get("name", inputs.get("mat_id", "—"))),
            ("Density", f"{rho} kg/m³"),
            ("Lift Height", f"{inputs.get('H_m', '—')} m"),
            ("Required Capacity", f"{inputs.get('Q_req', '—')} t/h"),
            ("Achieved Capacity", f"{fmt(results.get('Q'), 1)} t/h"),
            ("Belt Speed", f"{fmt(results.get('v'), 3)} m/s"),
            ("Head Pulley Dia.", f"{inputs.get('D_mm', '—')} mm @ {inputs.get('n_rpm', '—')} rpm"),
            ("Bucket Series", f"{bkt.get('id', '—')} — {bkt.get('V', '—')}L"),
            ("Belt Width", f"{results.get('belt_w', '—')} mm"),
            ("Lift Power", f"{fmt(results.get('P_lift'), 2)} kW"),
            ("Total Power", f"{fmt(results.get('P_total'), 2)} kW"),
            ("Motor", f"{results.get('motor_kw', '—')} kW"),
            ("Material Component T1", f"{fmt(T1/1000 if T1 is not None else None, 2)} kN"),
            ("Self-Weight Comp. T2", f"{fmt(T2/1000 if T2 is not None else None, 2)} kN"),
            ("Take-up / Slack T3", f"{fmt(T3/1000 if T3 is not None else None, 2)} kN"),
            ("Belt Tight Side (T3+Feff)", f"{fmt(tight_side, 2)} kN"),
            ("Min Shaft Dia.", f"{fmt(results.get('d_mm'), 1)} mm"),
            ("Shaft Material", results.get("shaft_material_name", "—")),
            ("Shaft Section", results.get("shaft_section", "—")),
            ("Hub Connection", results.get("shaft_hub_connection", "—")),
            ("Centrifugal Ratio", fmt(results.get("cr"), 3)),
            ("Discharge Angle", f"{fmt(results.get('theta_rel'), 1)}° from vertical"),
            ("Belt Length", f"{results.get('belt_length_total_m', '—')} m" if results.get("belt_length_total_m") is not None else "—"),
            ("Bucket Count", f"{results.get('n_buckets', '—')} off" if results.get("n_buckets") is not None else "—"),
            # New this round -- not in the original ChecksPanel.jsx, added so
            # the Design Summary reflects every component introduced this
            # session, not just the ones the original 2-column grid covered.
            ("Boot Shaft Dia.", f"{fmt((results.get('boot_pulley') or {}).get('shaft', {}).get('d_mm'), 1)} mm"),
            ("Take-Up Type", str(inputs.get("takeup_type", "gravity")).capitalize()),
            ("Chain Series", (results.get("chain_selected") or {}).get("name", "—") if results.get("is_chain") else "n/a (belt)"),
            ("Casing Plate", f"{fmt((results.get('casing_panel') or {}).get('t_use_mm'), 1)} mm"),
        ]

        grid = QGridLayout()
        grid.setSpacing(6)
        for i, (k, v) in enumerate(summary):
            row_box = QFrame()
            row_box.setStyleSheet(f"background-color: {PANEL2 if i % 2 == 0 else 'transparent'}; border-radius: 3px;")
            rl = QHBoxLayout(row_box)
            rl.setContentsMargins(10, 5, 10, 5)
            klabel = QLabel(k)
            klabel.setStyleSheet(f"color: {TEXT2}; font-size: 10.5px;")
            rl.addWidget(klabel)
            rl.addStretch()
            vlabel = QLabel(str(v))
            vlabel.setStyleSheet(f"color: {TEXT}; font-size: 10.5px; font-family: 'JetBrains Mono', monospace;")
            rl.addWidget(vlabel)
            grid.addWidget(row_box, i // 2, i % 2)
        self.layout_.addLayout(grid)


class ChecksPanel(QWidget):
    """Stacks RootCauseSection + DesignRecommendationsSection +
    FlatChecksSection, matching Bucketelevatorpage.jsx's real Checks-tab
    composition exactly. set_data(inputs, results) like every other panel;
    on_apply_correction(param, value) wired by main.py to merge a
    correction into the live payload and recalculate, mirroring
    RootCausePanel.jsx's setField prop."""

    def __init__(self, on_apply_correction=None, parent=None):
        super().__init__(parent)
        self.on_apply_correction = on_apply_correction
        self.setStyleSheet(f"background-color: {PANEL};")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        body = QWidget()
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