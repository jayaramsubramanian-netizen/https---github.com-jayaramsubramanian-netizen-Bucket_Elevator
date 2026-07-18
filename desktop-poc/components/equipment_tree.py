"""
components/equipment_tree.py -- complete PySide6 port of EquipmentTree.jsx
═══════════════════════════════════════════════════════════════════════════
Every section: Process, Mechanical Design (Head Assembly, Belt/Chain
Selection, Bucket Selection, Take-Up Selection, Discharge Section, Feed
Design, Casing Design), Power Transmission, Service Conditions.
node_status()/merge_status() are direct line-for-line ports of the real
EquipmentTree.jsx's own logic -- same backend-tag-first subsystem
filtering, same fail > warn > ok precedence.

This widget owns no fetch/network logic of its own -- it's a plain QWidget
that takes (inputs, results) via set_data(), the same contract as
ElevationView. See main.py's run_calculation() for how one fetch feeds
every panel.

show_detail=True: tree + inline detail panel (standalone use).
show_detail=False, popup_on_click=False: tree only, narrow -- matches the
REAL EquipmentTree.jsx, which has no inline detail view at all; clicking
a leaf there calls onNodeClick to open the relevant panel elsewhere.
show_detail=False, popup_on_click=True: tree only, but clicking a leaf
opens a QDialog with the same detail content the inline panel would have
shown. main.py's left column uses this mode -- now that the middle column
is dedicated to tab content (the schematic, etc.), there's no persistent
pane left over for inline detail, so a popup is the equivalent.

SWEEP NOTES (this round)
════════════════════════
This file came through in GOOD SHAPE. node_status() already does
subsystem-FIRST, keyword-second filtering -- the fix that stops one
subsystem's checks bleeding into another's node is present and correct
here. STATUS_COLOR / NONE_C are already v2-backed in theme.py, so every
tree node's color was already right. No hand-rolled field widgets, no
stale rgba() literals. Three changes only:

1. REAL DEFECT -- "MECHANICAL DESIGN" had no status rollup.

       mech = add_section(None, "MECHANICAL DESIGN")

   No status argument -> defaults to "none" -> the header always rendered
   in plain TEXT, never red or amber, EVEN WHEN A CHILD SECTION FAILED.
   Every other top-level section (PROCESS, POWER TRANSMISSION, SERVICE
   CONDITIONS) rolls its children up; this one silently didn't. On a
   collapsed tree, a failing head shaft or a failing chute was invisible
   at the top level.

   Now merges all seven child sections -- head, belt, bucket, take-up,
   chute, FEED and casing. The feed inclusion matters specifically: st_feed
   is the one rollup that folds in a non-check-derived status (fd's own
   warnings list plus s_boot), so an omitted feed would hide boot/feed
   warnings from the top level entirely. Same merge the JSX's
   subsystemBadge() performs.

2. BOX-IN-BOX in _show_detail_popup(). The header QFrame used a BARE
   stylesheet declaration containing `border-bottom` -- Qt reads a
   selector-less sheet as `* { ... }`, so it applied to the frame AND its
   descendants: both the title and the sub-label drew their own bottom
   border. Now object-scoped via theme.scoped().

3. THRESHOLD-IN-FRONTEND, flagged not changed (see below).
"""
from PySide6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QSplitter, QTextEdit, QFrame, QDialog, QPushButton,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QFont

from theme import (
    BG, PANEL, PANEL2, SURFACE, BORDER, BORDER2, TEXT, TEXT2, TEXT3,
    STATUS_COLOR, NONE_C, R_SM, scoped, plain_bg,
)


# ── Direct ports of EquipmentTree.jsx's own helpers ─────────────────────────
def node_status(checks, subsystem, keywords=None):
    """Port of nodeStatus(): subsystem-first, keyword-second filtering,
    fail > warn > ok precedence. Same function, same behaviour."""
    if not checks:
        return {"status": "none", "checks": []}
    in_subsystem = [c for c in checks if (c.get("subsystem") or "process") == subsystem]
    if keywords:
        kw = [k.lower() for k in keywords]
        matched = [c for c in in_subsystem if any(k in (c.get("msg") or "").lower() for k in kw)]
    else:
        matched = in_subsystem
    if not matched:
        return {"status": "none", "checks": []}
    if any(c.get("type") == "fail" for c in matched):
        return {"status": "fail", "checks": matched}
    if any(c.get("type") == "warn" for c in matched):
        return {"status": "warn", "checks": matched}
    return {"status": "ok", "checks": matched}


def merge_status(*statuses):
    """Port of mergeStatus()."""
    if "fail" in statuses:
        return "fail"
    if "warn" in statuses:
        return "warn"
    if all(s == "none" for s in statuses):
        return "none"
    return "ok"


def fmt(v, dp=1, suffix=""):
    """Port of the f() helper."""
    if v is None:
        return "—"
    try:
        return f"{float(v):.{dp}f}{suffix}"
    except (TypeError, ValueError):
        return "—"


class EquipmentTreePanel(QWidget):
    """Every section of EquipmentTree.jsx, as a plain QWidget with
    set_data(inputs, results) -- no embedded fetch, no embedded input bar.
    """

    def __init__(self, parent=None, show_detail=True, popup_on_click=False):
        super().__init__(parent)
        self.show_detail = show_detail
        self.popup_on_click = popup_on_click
        self.results, self.inputs = {}, {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.setStyleSheet(f"""
            QTreeWidget {{ background-color: {BG}; color: {TEXT2};
                border: none; font-size: 14px; outline: 0; }}
            QTreeWidget::item {{ padding: 3px 2px; border: none; }}
            QTreeWidget::item:selected {{ background-color: {PANEL}; }}
            QTreeWidget::item:hover {{ background-color: {PANEL}; }}
        """)

        if show_detail:
            detail = QFrame()
            detail.setStyleSheet(plain_bg(detail, PANEL))
            dlayout = QVBoxLayout(detail)
            self.detail_title = QLabel("Select a leaf to see its checks")
            self.detail_title.setStyleSheet(
                f"color: {TEXT2}; font-size: 14px; font-weight: 600; padding: 8px;")
            self.detail_text = QTextEdit()
            self.detail_text.setReadOnly(True)
            # QTextEdit has a viewport child, so this is object-scoped rather
            # than left as a bare declaration.
            self.detail_text.setStyleSheet(scoped(
                self.detail_text,
                f"background-color: {BG}; color: {TEXT2}; border: none; padding: 8px;"))
            dlayout.addWidget(self.detail_title)
            dlayout.addWidget(self.detail_text)

            splitter = QSplitter(Qt.Orientation.Horizontal)
            splitter.addWidget(self.tree)
            splitter.addWidget(detail)
            splitter.setSizes([520, 460])
            layout.addWidget(splitter)
        else:
            self.detail_title = None
            self.detail_text = None
            layout.addWidget(self.tree)

    def set_data(self, inputs, results):
        self.inputs, self.results = inputs or {}, results or {}
        self._rebuild_tree()

    @staticmethod
    def _detail_text_for(data):
        """Shared by the inline panel and the popup so the actual content
        logic (status text, check messages, the "computed not free-text"
        fallback) exists in exactly one place, not duplicated between
        them."""
        status = data["status"]
        checks = data.get("checks", [])
        if checks:
            return "\n\n".join(f"[{c.get('type','?').upper()}] {c.get('msg','')}" for c in checks)
        if status == "none":
            return "No status computed for this item — informational only."
        return (
            f"Status is {status.upper()}, computed directly from the result "
            f"(not from a free-text check message) — see the value shown under "
            f"this item in the tree."
        )

    def _on_item_clicked(self, item, _col):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        if self.popup_on_click:
            self._show_detail_popup(data)
            return
        if self.detail_title is None or self.detail_text is None:
            return
        status = data["status"]
        color = STATUS_COLOR.get(status, NONE_C)
        self.detail_title.setText(f"{data['label']}  —  {status.upper()}")
        self.detail_title.setStyleSheet(f"color: {color}; font-size: 15px; font-weight: 700; padding: 8px;")
        self.detail_text.setPlainText(self._detail_text_for(data))

    def _show_detail_popup(self, data):
        status = data["status"]
        color = STATUS_COLOR.get(status, NONE_C)
        dialog = QDialog(self)
        dialog.setWindowTitle(data["label"])
        dialog.setMinimumWidth(420)
        dialog.setStyleSheet(plain_bg(dialog, PANEL))
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # SCOPED: this was a bare declaration with a border-bottom, so Qt read
        # it as `* { ... }` and BOTH the title and the sub-label below drew
        # their own bottom border inside the header.
        header = QFrame()
        header.setStyleSheet(scoped(
            header,
            f"background-color: {PANEL2}; border: none; "
            f"border-bottom: 1px solid {BORDER};"
        ))
        hlayout = QVBoxLayout(header)
        hlayout.setContentsMargins(16, 12, 16, 12)
        title = QLabel(f"{data['label']}  —  {status.upper()}")
        title.setStyleSheet(f"color: {color}; font-size: 16px; font-weight: 700;")
        hlayout.addWidget(title)
        if data.get("sub"):
            sub = QLabel(data["sub"])
            sub.setStyleSheet(f"color: {TEXT3}; font-size: 13px;")
            hlayout.addWidget(sub)
        layout.addWidget(header)

        body = QTextEdit()
        body.setReadOnly(True)
        body.setPlainText(self._detail_text_for(data))
        body.setStyleSheet(scoped(
            body,
            f"background-color: {BG}; color: {TEXT2}; border: none; "
            f"padding: 14px; font-size: 14px;"))
        layout.addWidget(body)

        footer = QFrame()
        footer.setStyleSheet(scoped(
            footer, "background-color: transparent; border: none;"))
        flayout = QHBoxLayout(footer)
        flayout.setContentsMargins(12, 8, 12, 8)
        flayout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(scoped(
            close_btn,
            f"background-color: {SURFACE}; color: {TEXT2}; "
            f"border: 1px solid {BORDER2}; border-radius: {R_SM}px; "
            f"padding: 6px 16px; font-size: 14px;",
            extra="{sel}:hover { color: %s; }" % TEXT,
        ))
        close_btn.clicked.connect(dialog.accept)
        flayout.addWidget(close_btn)
        layout.addWidget(footer)

        dialog.exec()


    def fail_warn_ok_counts(self):
        """Exposed so a caller (main.py's TopNav) can show the same FAIL/
        WARN badge the original header carried, without this widget owning
        any badge UI of its own."""
        checks = self.results.get("checks", []) or []
        n_fail = sum(1 for c in checks if c.get("type") == "fail")
        n_warn = sum(1 for c in checks if c.get("type") == "warn")
        n_ok = sum(1 for c in checks if c.get("type") == "ok")
        return n_fail, n_warn, n_ok

    # ── Tree construction -- every section, faithfully ──────────────────
    def _rebuild_tree(self):
        self.tree.clear()
        r, inp = self.results, self.inputs
        checks = r.get("checks", []) or []
        casing_clearance = r.get("casing_clearance")

        s_capacity = node_status(checks, "process", ["capacity"])
        s_speed    = node_status(checks, "process", ["speed"])
        s_cr       = node_status(checks, "process", ["cr=", "centrifugal", "scatter"])
        s_slip     = node_status(checks, "belt", ["slip", "euler", "chain sf", "chain speed", "chain working", "sprocket"])
        s_shaft    = node_status(checks, "shaft", ["shaft", "governed by", "critical speed"])
        s_key      = node_status(checks, "shaft", ["keyway"])
        s_bearing  = node_status(checks, "shaft", ["bearing", "l10"])
        s_lagging  = node_status(checks, "pulley", ["lagging"])
        s_end_disc = node_status(checks, "pulley", ["end disc"])
        s_motor    = node_status(checks, "power")
        s_belt     = node_status(checks, "belt")
        s_tension_profile = node_status(checks, "belt", ["tension profile peak"])
        s_bolt     = node_status(checks, "bucket", ["bolt", "fatigue", "goodman"])
        s_digging  = node_status(checks, "bucket", ["digging efficiency", "spacing"])
        s_takeup   = node_status(checks, "takeup")
        s_casing   = node_status(checks, "casing")
        s_chute    = node_status(checks, "discharge", ["chute", "plugging", "dust", "mass flow", "funnel"])
        s_atex     = node_status(checks, "service", ["atex", "explosive", "dust control", "stainless"])
        s_abr      = node_status(checks, "process", ["abrasion", "ar400", "ar500", "liner"])
        s_boot     = node_status(checks, "boot_pulley")

        s_casing_clearance_status = (
            ("ok" if casing_clearance.get("clears") else "fail") if casing_clearance else "none"
        )

        st_process = merge_status(s_capacity["status"], s_speed["status"], s_cr["status"])
        st_head    = merge_status(s_shaft["status"], s_key["status"], s_bearing["status"], s_lagging["status"], s_end_disc["status"])
        st_belt    = merge_status(s_belt["status"], s_slip["status"], s_bolt["status"])
        st_bucket  = merge_status(s_bolt["status"], s_digging["status"])
        st_takeup  = s_takeup["status"]
        st_chute   = merge_status(s_chute["status"], s_casing_clearance_status)
        st_casing  = merge_status(s_casing["status"], s_abr["status"])

        bkt   = r.get("bucket") or {}
        mat   = r.get("mat") or r.get("material") or {}
        hub   = r.get("hub") or {}
        lag   = r.get("lagging") or {}
        tg    = r.get("takeup_gravity") or {}
        ts    = r.get("takeup_screw") or {}
        th    = r.get("takeup_hydraulic") or {}
        dc    = r.get("discharge_chute") or {}
        dcperf = dc.get("performance") or {}
        dcmnt  = dc.get("maintenance") or {}
        fd     = r.get("feed_design")
        chain  = r.get("chain_selected") or {}
        sprocket = r.get("sprocket") or {}
        boot_sprocket = r.get("boot_sprocket") or {}
        is_chain = bool(r.get("is_chain"))

        bkt_depth = bkt.get("depth_mm", bkt.get("H"))
        screw_d = ts.get("d_core_recommend_mm", ts.get("d_core_min_mm"))

        st_feed = merge_status(
            ("warn" if (fd and fd.get("warnings")) else "ok") if fd else "none",
            s_boot["status"],
        )

        # THRESHOLD-IN-FRONTEND: the 6.0 / 5.0 chain safety-factor bands are
        # engineering constants living in a UI file. chain_SF_actual is computed
        # in the backend; the VERDICT should come from there too, the way
        # cap_ok / speed_ok / cr_ok / l10_ok already do (chain_v_ok, read a few
        # lines below, is exactly the right pattern -- this one just never got
        # its equivalent). Values preserved exactly. See TASK_LIST.md item 2.
        chain_sf_actual = r.get("chain_SF_actual")
        if chain_sf_actual is not None and chain_sf_actual >= 6.0:
            chain_sf_status = "ok"
        elif chain_sf_actual is not None and chain_sf_actual >= 5.0:
            chain_sf_status = "warn"
        elif chain_sf_actual is not None and chain_sf_actual > 0:
            chain_sf_status = "fail"
        else:
            chain_sf_status = "none"

        def add_section(parent, label, status="none"):
            item = QTreeWidgetItem(parent if parent is not None else self.tree)
            item.setText(0, label)
            font = QFont(); font.setBold(True); font.setPointSize(11)
            item.setFont(0, font)
            color = QColor(STATUS_COLOR.get(status, TEXT)) if status != "none" else QColor(TEXT)
            item.setForeground(0, QBrush(color))
            return item

        def add_leaf(parent, label, sub, status_result, extra_msg=None):
            status = status_result["status"] if isinstance(status_result, dict) else status_result
            matched_checks = list(status_result["checks"]) if isinstance(status_result, dict) else []
            if extra_msg and not matched_checks:
                matched_checks = [{"type": status if status in ("ok", "warn", "fail") else "ok", "msg": extra_msg}]
            item = QTreeWidgetItem(parent)
            item.setText(0, f"  {label}")
            item.setForeground(0, QBrush(QColor(STATUS_COLOR.get(status, NONE_C))))
            font = QFont(); font.setPointSize(10)
            item.setFont(0, font)
            item.setData(0, Qt.ItemDataRole.UserRole, {"label": label, "sub": sub, "status": status, "checks": matched_checks})
            if sub:
                sub_item = QTreeWidgetItem(item)
                sub_item.setText(0, f"      {sub}")
                sub_item.setForeground(0, QBrush(QColor(TEXT3)))
                sub_font = QFont(); sub_font.setPointSize(8)
                sub_item.setFont(0, sub_font)
                sub_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            return item

        process = add_section(None, "PROCESS", st_process)
        add_leaf(process, "Material", f"{mat.get('name', inp.get('mat_id','—'))}  ρ={fmt(r.get('rho'), 0)} kg/m³", "none")
        add_leaf(process, "Capacity", f"{fmt(r.get('Q', r.get('Q_th')), 1)} t/h  req {inp.get('Q_req','—')} t/h", s_capacity)
        add_leaf(process, "Belt Speed", f"{fmt(r.get('v', r.get('v_ms')), 2)} m/s", s_speed)
        add_leaf(process, "Centrifugal Ratio", f"CR = {fmt(r.get('cr', r.get('centrifugal_ratio')), 3)}", s_cr)

        # FIXED: this was `add_section(None, "MECHANICAL DESIGN")` with NO status
        # argument -- so it defaulted to "none" and the header rendered in plain
        # TEXT no matter what, EVEN WHEN A CHILD SECTION FAILED. Every other
        # top-level section rolls its children up; this one silently didn't, so
        # on a collapsed tree a failing head shaft or chute was invisible at the
        # top level.
        #
        # st_feed is included deliberately: it's the one rollup that folds in a
        # status NOT derived from checks[] (feed_design's own warnings list, plus
        # s_boot). Omitting it would hide every boot/feed warning from the top
        # level. Same merge the JSX's subsystemBadge() performs.
        st_mech = merge_status(
            st_head, st_belt, st_bucket, st_takeup, st_chute, st_feed, st_casing,
        )
        mech = add_section(None, "MECHANICAL DESIGN", st_mech)

        head = add_section(mech, "Head Assembly", st_head)
        add_leaf(head, "Head Pulley", f"Ø{inp.get('D_mm','—')}mm  {inp.get('n_rpm','—')} rpm", "none")
        add_leaf(head, "Head Shaft", f"Ø{fmt(r.get('d_mm'), 1)}mm  {r.get('shaft_material','A36')}  {r.get('governed_by','—')}", s_shaft)
        add_leaf(head, "Hub & Key",
                 f"Hub Ø{fmt(hub.get('d_hub_mm'), 1)}mm  key {hub.get('b_key_mm','—')}×{hub.get('h_key_mm','—')}mm" if hub.get("d_hub_mm") else "—",
                 s_key)
        add_leaf(head, "Bearings", f"L10 {int(r['L10']):,} h" if r.get("L10") else "L10 — h", s_bearing)
        add_leaf(head, "Lagging",
                 f"{(lag.get('lagging_type') or '').replace('_',' ')}  μ={fmt(lag.get('mu_operating'), 2)}" if lag.get("lagging_type") else "—",
                 s_lagging)
        end_disc = r.get("end_disc") or {}
        add_leaf(head, "End Disc", f"min t={fmt(end_disc.get('t_governing_mm'), 1)}mm" if end_disc.get("t_governing_mm") else "—", s_end_disc)

        belt_sel = add_section(mech, "Chain Selection" if is_chain else "Belt Selection", st_belt)
        if is_chain:
            add_leaf(belt_sel, "Chain Series",
                     f"{chain.get('name')}  pitch {fmt(chain.get('pitch_mm'), 0)}mm  {chain.get('n_strands','—')} strand" if chain.get("name") else "—",
                     chain_sf_status)
            add_leaf(belt_sel, "Chain Working Load",
                     f"SF={fmt(chain_sf_actual, 2)}  Pull={fmt((r.get('chain_pull_N') or 0) / 1000, 1)}kN" if chain_sf_actual is not None else "—",
                     chain_sf_status)
            chain_v_ok = r.get("chain_v_ok")
            add_leaf(belt_sel, "Chain Speed", f"{fmt(r.get('v', r.get('v_ms')), 2)} m/s  max {fmt(chain.get('v_max_ms'), 2)} m/s",
                     "fail" if chain_v_ok is False else "ok" if chain_v_ok else "none")
            sprocket_smooth = sprocket.get("smooth")
            add_leaf(belt_sel, "Sprocket",
                     f"{sprocket.get('n_teeth')}T  PD={fmt(sprocket.get('PD_mm'), 0)}mm" if sprocket.get("n_teeth") else "—",
                     "warn" if sprocket_smooth is False else "ok" if sprocket_smooth else "none")
            boot_smooth = boot_sprocket.get("smooth")
            add_leaf(belt_sel, "Boot Sprocket",
                     f"{boot_sprocket.get('n_teeth')}T  PD={fmt(boot_sprocket.get('PD_mm'), 0)}mm" if boot_sprocket.get("n_teeth") else "—",
                     "warn" if boot_smooth is False else "ok" if boot_smooth else "none")
        else:
            add_leaf(belt_sel, "Belt", f"{r.get('belt_class') or (str(r['belt_ply']) + ' PLY' if r.get('belt_ply') else '—')}  {r.get('belt_w', r.get('belt_width_mm','—'))}mm", s_belt)
            tp = r.get("tension_profile") or {}
            add_leaf(belt_sel, "Tension Profile",
                     f"margin {fmt(tp.get('rating_margin'), 3)}  peak {fmt((tp.get('T_max_N') or 0)/1000, 1)}kN" if tp.get("rating_margin") is not None else "—",
                     s_tension_profile)
            add_leaf(belt_sel, "Belt Slip",
                     f"e^μθ={fmt(r.get('euler_ratio'), 3)}  {'✓ Safe' if r.get('slip_safe') else '✗ Risk'}" if r.get("euler_ratio") is not None else "—",
                     s_slip)

        bucket_sel = add_section(mech, "Bucket Selection", st_bucket)
        add_leaf(bucket_sel, "Bucket Series",
                 f"{bkt.get('id')}  {bkt.get('W', bkt.get('width_mm','—'))}×{bkt_depth or '—'}mm  {bkt.get('V', bkt.get('volume_L','—'))}L" if bkt.get("id") else "—",
                 "none")
        add_leaf(bucket_sel, "Bucket Count & Spacing",
                 f"{r.get('n_buckets')} buckets  ·  {fmt((r.get('spacing_actual_m', r.get('spacing', 0)) or 0) * 1000, 0)}mm spacing" if r.get("n_buckets") is not None else "—",
                 s_digging)
        bolt_fatigue = r.get("bolt_fatigue") or {}
        add_leaf(bucket_sel, "Bolt Fatigue",
                 f"Goodman {fmt(bolt_fatigue.get('goodman_ratio'), 3)}" if bolt_fatigue.get("goodman_ratio") is not None else "—",
                 s_bolt)

        takeup_sel = add_section(mech, "Take-Up Selection", st_takeup)
        add_leaf(takeup_sel, f"Gravity Take-Up{'  (active)' if tg.get('primary') else ''}",
                 f"{fmt(tg.get('W_counterweight_kg_gross'), 0)} kg  travel {fmt((tg.get('travel_m') or 0) * 1000, 0)} mm" if tg.get("W_counterweight_kg_gross") else "—",
                 s_takeup["status"] if tg.get("primary") else "none")
        ts_status = ("fail" if ts.get("buckling_safe") is False else "ok") if ts.get("primary") else ("warn" if ts.get("buckling_safe") is False else "none")
        add_leaf(takeup_sel, f"Screw Alternative{'  (active)' if ts.get('primary') else ''}",
                 f"d_core {fmt(screw_d, 1)}mm  SF {fmt(ts.get('SF_buckling'), 2)}" if screw_d else "—", ts_status)
        th_status = ("fail" if th.get("buckling_safe") is False else "ok") if th.get("primary") else ("warn" if th.get("buckling_safe") is False else "none")
        add_leaf(takeup_sel, f"Hydraulic Alternative{'  (active)' if th.get('primary') else ''}",
                 f"bore Ø{fmt(th.get('d_bore_use_mm'), 0)}mm  SF {fmt(th.get('SF_buckling'), 2)}" if th.get("d_bore_use_mm") else "—", th_status)

        discharge = add_section(mech, "Discharge Section", st_chute)
        add_leaf(discharge, "Type",
                 f"HF Continuous  CR={fmt(r.get('cr'), 3)}" if r.get("is_continuous") else f"Centrifugal  CR={fmt(r.get('cr'), 3)}",
                 "none")
        add_leaf(discharge, "Chute",
                 f"{fmt(dcperf.get('chute_angle_deg'), 1)}°  {(dcperf.get('flow_regime') or '').replace('_',' ') or '—'}" if dcperf.get("chute_angle_deg") else "—",
                 s_chute)
        add_leaf(discharge, "Liner",
                 f"{dcmnt.get('liner_material')}  {dcmnt.get('liner_thickness_mm','—')}mm" if dcmnt.get("liner_material") else "—",
                 "none")
        if casing_clearance:
            clears = casing_clearance.get("clears")
            add_leaf(discharge, "Casing Clearance",
                     f"Stream clears wall by {fmt((casing_clearance.get('clearance_m') or 0) * 1000, 0)}mm" if clears
                     else f"Strikes wall at x={fmt((casing_clearance.get('strike_x_m') or 0) * 1000, 0)}mm  (wall at {fmt((casing_clearance.get('casing_wall_x_m') or 0) * 1000, 0)}mm)",
                     "ok" if clears else "fail",
                     extra_msg=casing_clearance.get("recommendation"))

        feed = add_section(mech, "Feed Design", st_feed)
        add_leaf(feed, "Boot Pulley", f"Ø{inp.get('boot_pulley_D_mm', inp.get('D_mm','—'))}mm  Take-up point", s_boot)
        add_leaf(feed, "Boot Surge Volume",
                 f"{fd.get('V_surge_litres','—')}L  ({fd.get('t_surge_s',3)}s buffer)" if fd else "—", "none")
        add_leaf(feed, "Inlet Geometry",
                 f"{fd.get('inlet_width_mm','—')}×{fd.get('inlet_height_mm','—')}mm  v={fmt(fd.get('v_feed_mps'), 2)}m/s" if fd else "No data — run calculation",
                 "ok" if fd else "none")
        add_leaf(feed, "Loading Method", fd.get("loading_type") if fd else "—",
                 ("warn" if fd.get("warnings") else "ok") if fd else "none",
                 extra_msg=" / ".join(fd.get("warnings")) if fd and fd.get("warnings") else None)
        add_leaf(feed, "Boot Casing Height",
                 f"min {fd.get('boot_casing_height_mm','—')}mm below pulley CL" if fd else "—", "none")

        casing = add_section(mech, "Casing Design", st_casing)
        casing_panel = r.get("casing_panel") or {}
        add_leaf(casing, "Casing Panel",
                 f"δ={fmt(casing_panel.get('delta_actual_mm'), 1)}mm  t={fmt(casing_panel.get('t_use_mm'), 0)}mm" if casing_panel else "—",
                 st_casing)
        add_leaf(casing, "Casing Width",
                 f"Belt {r.get('belt_w','—')}mm  ·  head-section wall at {fmt((casing_clearance.get('casing_wall_x_m') or 0) * 1000, 0) if casing_clearance else '—'}mm from CL",
                 ("ok" if casing_clearance.get("clears") else "fail") if casing_clearance else "none",
                 extra_msg=casing_clearance.get("recommendation") if casing_clearance else None)

        power = add_section(None, "POWER TRANSMISSION", s_motor["status"])
        add_leaf(power, "Motor", f"{r.get('motor_kw', r.get('motor_kW','—'))} kW  ·  {r.get('motor_nominal_rpm', 1450)} rpm  ·  SF {inp.get('sf','—')}", s_motor)
        add_leaf(power, "Gearbox",
                 f"Ratio {fmt(r.get('gearbox_ratio'), 1)}:1  ·  T={fmt(r['T_Nm']/1000 if r.get('T_Nm') is not None else None, 2)}kNm" if r.get("gearbox_ratio") is not None else "—",
                 "none")
        add_leaf(power, "Total Power",
                 f"{fmt(r.get('P_total'), 2)} kW  ·  margin {('+' + fmt(r.get('motor_margin_pct'), 1) + '%') if r.get('motor_margin_pct') is not None else '—'}",
                 "none")
        # Startup dynamics tied to drive_start_type (Power Transmission's
        # newest real field) -- shock_check is tagged subsystem="belt" in
        # the backend (a genuine categorization, not an error: shock load
        # is a belt-tension concern), so node_status(checks, "power")
        # never catches it. Status read directly from the structured
        # result instead, same pattern power_edit.py already uses.
        sd = r.get("startup_dynamic") or {}
        sc = r.get("shock_check") or {}
        if sd:
            # THRESHOLD-IN-FRONTEND: the 1.0 / 1.1 startup-margin bands are
            # duplicated here AND in power_edit.py -- two copies of the same
            # engineering constant in two UI files, which is precisely how they
            # drift apart. One backend verdict alongside startup_margin would
            # replace both. Values preserved exactly. See TASK_LIST.md item 2.
            margin = sd.get("startup_margin")
            st_startup = "fail" if (margin or 0) < 1.0 else ("warn" if (margin or 0) < 1.1 else "ok")
            if sc and not sc.get("adequate_for_normal_shock"):
                st_startup = "warn" if st_startup == "ok" else st_startup
            add_leaf(power, "Startup Dynamics",
                     f"{inp.get('drive_start_type','soft_start')}  ·  peak {fmt((sd.get('T_peak_governing') or 0) / 1000, 1)}kN  "
                     f"·  margin {fmt(margin, 2)}",
                     st_startup,
                     extra_msg=sc.get("recommendation") if sc and not sc.get("adequate_for_normal_shock") else None)

        service = add_section(None, "SERVICE CONDITIONS", s_atex["status"])
        add_leaf(service, "Environment", f"{inp.get('environment','dry')}  μ={inp.get('mu','—')}", "none")
        if s_atex["status"] != "none":
            add_leaf(service, "Hazard Flags", "ATEX / dust control", s_atex)
        if s_abr["status"] != "none":
            add_leaf(service, "Abrasion Rating", f"Class {mat.get('abr_code','—')}/7", s_abr)

        self.tree.expandAll()