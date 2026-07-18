"""
components/optimizer_panel.py -- multi-objective (NSGA-II) optimizer panel.
═══════════════════════════════════════════════════════════════════════════
Faithful port of frontend/src/components/OptimizerPanel.jsx -- same search
description, same sort options, same Pareto-front table columns, same
Apply/Export/Select-All/Clear actions, same material-preference and summary
strips.

Visually elevated beyond the bare JSX layout per direct feedback that the
original "is pretty bland" -- behavior unchanged, but this uses the same
card/badge design language as status_panel.py and dialog_helpers.py
(status_badge, neutral bordered cards with a colored accent, graduated
CR-deviation coloring) instead of one flat table with inline-colored text.
The data, columns and actions were not changed.

Architecture notes:
  - The NSGA-II run is a genuine ~3-30s blocking network call (confirmed:
    24.3s for a real 200x100 budget run) -- run on OptimizerWorker(QThread),
    never on the GUI thread.
  - PDF export is a second, smaller backend call -- also threaded
    (ReportWorker).
  - No optimization math lives here. Every number comes straight from the
    backend's Pareto-front response; sorting is a list re-order by an
    existing field, not a recomputation.

Backend sync (prior round): two real gaps were found and fixed in
vectrix_optimizer_v2.py before this UI was built --
  1. Boot bearing life was unconstrained (l10_boot_violation added,
     mirroring l10_violation).
  2. Belt-mode startup tension margin had no check in calculations.py's
     checks[], so it was invisible to the generic fail_count constraint
     (startup_margin_violation added; no-op for chain runs).
Both surface as display columns below (L10 Boot, Startup Margin).

BOX-IN-BOX + PALETTE SWEEP (this round)
───────────────────────────────────────
  * The material-preference card was a BARE declaration with a border, so
    its QLabel drew its own box inside the card. Qt reads a selector-less
    stylesheet as `* { ... }` -- it applies to the widget AND every
    descendant. Now object-scoped via theme.scoped().
  * That card's tint was rgba(74,158,255,.06)/.2 -- v1 primary (#4a9eff)
    -- while its inline <b> tag uses the imported v2 PRIMARY (#3b82f6).
    Two different blues in one sentence. Now PRIMARY_DIM / PRIMARY_RING.
  * The TABLE ROW HIGHLIGHTS were v1 too, and hardcoded as raw QColor
    triples: QColor(74,158,255,30) pinned, QColor(224,82,82,18)
    infeasible, QColor(31,184,110,14) top. All three are v1 literals. They
    now derive from the v2 tokens, so a pinned row's tint matches the
    PRIMARY the checkbox is drawn in.
  * _primary_button's hover was a hardcoded "#5aa8ff" in no palette ->
    PRIMARY_HOVER.
  * The sort combo was a hand-rolled BARE combo stylesheet -> shared
    styled_combo(). (A QComboBox owns an internal view, so a bare border
    lands inside it -- the same failure as material_library_panel.py's
    _input_style().)
  * Local _clear_layout() duplicated dialog_helpers.clear_layout() ->
    imported.

REAL BUG FIXED
──────────────
self._result and self._sort_by were never initialised in __init__ -- they're
only created in _on_result() / _rebuild_sorted_front(). _rebuild_status()
reads `self._result.get("n_pareto_points", 0)` directly (the `or {}` guard
covers only the FIRST reference, not that one), so any path reaching
_rebuild_status before a successful run raises AttributeError. Both are now
initialised up front, and _rebuild_status guards properly.

Four flush-left indentation breaks restored (`for sort_id, label in
SORT_OPTIONS:`, `def _select_all`, `self.export_btn.setEnabled(False)`,
`is_chain = ...`) -- as pasted, `def _select_all` sat outside the class.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QFileDialog, QScrollArea,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor

from theme import (
    PANEL, PANEL2, SURFACE, BORDER, BORDER2, TEXT, TEXT2, TEXT3, MUTED,
    PRIMARY, PRIMARY_HOVER, PRIMARY_DIM, PRIMARY_RING,
    SUCCESS, WARNING, DANGER, TEAL, R_SM, FF_MONO,
    scoped, plain_bg,
)
from api_client import optimize_elevator_v2, download_variant_report
from .dialog_helpers import (
    status_badge, flag_note, stat_box, section_head, styled_combo, clear_layout,
)

MONO_FAMILY = "JetBrains Mono"   # QFont.setFamily() wants a bare family name,
                                 # not the quoted CSS stack in theme.FF_MONO.


def fmt(v, digits=2, fb="—"):
    if v is None:
        return fb
    try:
        return f"{float(v):.{digits}f}"
    except (TypeError, ValueError):
        return fb


def _row_tint(color_hex, alpha):
    """Row highlight derived from a theme token. These were hardcoded QColor
    triples -- QColor(74,158,255,30) etc -- all of them v1 values, so a pinned
    row's tint disagreed with the v2 PRIMARY its checkbox was drawn in."""
    c = QColor(color_hex)
    c.setAlpha(alpha)
    return c


SORT_OPTIONS = [
    ("cr_deviation", "CR Match (closest to material preference)"),
    ("motor_kw", "Motor Power (lowest first)"),
    ("R_headshaft_N", "Structural Load (lowest first)"),
    ("L10_h", "Bearing Life (longest first)"),
]

TABLE_COLUMNS_BASE = [
    ("", 28), ("#", 30), ("RPM", 55), ("Bucket", 75), ("Fill %", 55),
    ("D mm", 55), ("Boot mm", 60),
]
TABLE_COLUMNS_CHAIN = [("Strands", 55), ("Teeth H/B", 70)]
TABLE_COLUMNS_TAIL = [
    ("Q t/h", 55), ("Motor kW", 65), ("Load kN", 60), ("L10 h", 65),
    ("L10 Boot h", 75), ("Startup Mgn", 80), ("CR", 50), ("CR Dev", 55),
]


def cr_dev_color(dev):
    """Mirrors OptimizerPanel.jsx's crDevColor() -- a graduated band across
    cr_deviation's own scale, not a recomputation: cr_deviation already
    arrives from the backend as the real, material-aware distance from the
    preferred CR range."""
    dev = dev or 0
    if dev >= 0.5:
        return DANGER
    if dev >= 0.1:
        return WARNING
    return TEAL


def to_variant_report_shape(p, rank):
    """Mirrors OptimizerPanel.jsx's toVariantReportShape() -- maps a Pareto
    point into the shape build_variant_report() expects."""
    return {
        "rpm": p.get("n_rpm"),
        "bucket_id": p.get("bucket_id"),
        "fill": p.get("fill_pct"),
        "speed": p.get("v_ms") or 0,
        "capacity": p.get("Q_th") or 0,
        "power": p.get("motor_kw"),
        "motor_kw": p.get("motor_kw"),
        "T1_kN": round((p.get("R_headshaft_N") or 0) / 100) / 10,
        "cr": p.get("cr") or 0,
        "rank": rank,
        "D_mm": p.get("D_mm"),
        "boot_pulley_D_mm": p.get("boot_pulley_D_mm"),
        "chain_n_strands": p.get("chain_n_strands"),
        "cr_deviation": p.get("cr_deviation"),
        "chain_sprocket_teeth": p.get("chain_sprocket_teeth"),
        "chain_boot_sprocket_teeth": p.get("chain_boot_sprocket_teeth"),
        "L10_h": p.get("L10_h"),
    }


class OptimizerWorker(QThread):
    """Runs the NSGA-II call off the GUI thread -- a genuine ~3-30s blocking
    network call, not a quick request."""

    resultReady = Signal(dict)
    errorOccurred = Signal(str)

    def __init__(self, base_input, parent=None):
        super().__init__(parent)
        self.base_input = base_input

    def run(self):
        try:
            self.resultReady.emit(optimize_elevator_v2(self.base_input))
        except Exception as e:
            self.errorOccurred.emit(str(e))


class ReportWorker(QThread):
    """Runs the PDF export off the GUI thread -- a multi-variant report
    request is a real network call, not instant."""

    done = Signal(str)
    errorOccurred = Signal(str)

    def __init__(self, candidates, inputs, save_path, parent=None):
        super().__init__(parent)
        self.candidates = candidates
        self.inputs = inputs
        self.save_path = save_path

    def run(self):
        try:
            path = download_variant_report(
                self.candidates, self.inputs, self.save_path)
            self.done.emit(path)
        except Exception as e:
            self.errorOccurred.emit(str(e))


def _primary_button(text):
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(scoped(
        btn,
        f"background-color: {PRIMARY}; color: white; border: none; "
        f"border-radius: {R_SM}px; padding: 10px 18px; font-size: 14px; "
        f"font-weight: 700;",
        # Hover was a hardcoded "#5aa8ff", in no palette. Now a real token.
        extra=("{sel}:disabled { background-color: %s; color: %s; }\n"
               "{sel}:hover:!disabled { background-color: %s; }"
               % (SURFACE, TEXT3, PRIMARY_HOVER)),
    ))
    return btn


def _secondary_button(text):
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(scoped(
        btn,
        f"background-color: {SURFACE}; color: {TEXT2}; "
        f"border: 1px solid {BORDER2}; border-radius: {R_SM}px; "
        f"padding: 8px 14px; font-size: 14px; font-weight: 600;",
        extra=("{sel}:disabled { color: %s; }\n"
               "{sel}:hover:!disabled { background-color: %s; color: %s; }"
               % (TEXT3, BORDER2, TEXT)),
    ))
    return btn


class OptimizerPanel(QWidget):
    """Port of OptimizerPanel.jsx's default export. Same set_data(inputs,
    results) shape as every other panel, though only `inputs` is used (the
    optimizer runs against current inputs, not the last-calculated results)
    -- kept for interface consistency with how main.py calls every panel."""

    def __init__(self, on_apply, parent=None):
        super().__init__(parent)
        self.on_apply = on_apply
        self.inputs = {}
        self._pareto_front = []
        self._sorted_front = []
        self._selected = set()
        self._worker = None
        self._report_worker = None
        # FIXED: these two were never initialised -- only created in
        # _on_result() / _rebuild_sorted_front(). _rebuild_status() reads
        # self._result.get(...) directly (the `or {}` guard covers only the
        # first reference), so any path reaching it before a successful run
        # raised AttributeError.
        self._result = {}
        self._sort_by = "cr_deviation"

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
        self.body_layout.setSpacing(12)

        intro = QLabel(
            "Multi-objective (NSGA-II) optimizer searches RPM × Bucket × Fill × Head & "
            "Boot Pulley Diameter space subject to CEMA speed limits and a 20,000h "
            "bearing-life floor (head and boot). Returns a genuine Pareto-efficient "
            'front — every row below is a real trade-off, not a single "best" answer.'
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {TEXT2}; font-size: 13px; line-height: 145%;")
        self.body_layout.addWidget(intro)

        self.run_btn = _primary_button("▶  RUN OPTIMIZER")
        self.run_btn.clicked.connect(self._run_optimizer)
        self.body_layout.addWidget(self.run_btn)

        self.status_box = QVBoxLayout()
        self.status_box.setSpacing(8)
        self.body_layout.addLayout(self.status_box)

        self.results_box = QVBoxLayout()
        self.results_box.setSpacing(10)
        self.body_layout.addLayout(self.results_box)

        self.body_layout.addStretch()
        scroll.setWidget(body)
        outer.addWidget(scroll)

    def set_data(self, inputs, results):
        self.inputs = dict(inputs or {})

    # ── Run ──────────────────────────────────────────────────────────
    def _run_optimizer(self):
        self.run_btn.setEnabled(False)
        self.run_btn.setText("⟳  OPTIMIZING (≈20-30s)…")
        clear_layout(self.status_box)
        clear_layout(self.results_box)
        self._selected = set()
        self._worker = OptimizerWorker(self.inputs, parent=self)
        self._worker.resultReady.connect(self._on_result)
        self._worker.errorOccurred.connect(self._on_error)
        self._worker.start()

    def _on_error(self, message):
        self.run_btn.setEnabled(True)
        self.run_btn.setText("▶  RUN OPTIMIZER")
        flag_note("fail", f"Optimizer run failed: {message}",
                  parent_layout=self.status_box)

    def _on_result(self, result):
        self.run_btn.setEnabled(True)
        self.run_btn.setText("▶  RUN OPTIMIZER")
        self._result = result or {}
        self._pareto_front = self._result.get("pareto_front") or []
        self._rebuild_sorted_front("cr_deviation")
        self._rebuild_status()
        self._rebuild_results()

    # ── Sorting ──────────────────────────────────────────────────────
    def _rebuild_sorted_front(self, sort_by):
        reverse = sort_by == "L10_h"   # longer life first; everything else ascending
        self._sort_by = sort_by
        self._sorted_front = sorted(
            self._pareto_front, key=lambda c: c.get(sort_by) or 0, reverse=reverse)

    def _on_sort_changed(self, index):
        self._rebuild_sorted_front(SORT_OPTIONS[index][0])
        self._selected = set()
        self._rebuild_status()
        self._rebuild_results()

    # ── Status strips (material preference + summary) ─────────────────
    def _rebuild_status(self):
        clear_layout(self.status_box)
        result = self._result or {}

        pref = result.get("material_preference")
        if pref:
            # SCOPED: the bare declaration gave this card's border to its own
            # QLabel. Tint was v1 primary while the inline <b> uses v2 PRIMARY
            # -- two blues in one sentence.
            box = QFrame()
            box.setStyleSheet(scoped(
                box,
                f"background-color: {PRIMARY_DIM}; "
                f"border: 1px solid {PRIMARY_RING}; border-radius: 7px;"
            ))
            bl = QVBoxLayout(box)
            bl.setContentsMargins(12, 10, 12, 10)
            cr_lo, cr_hi = (pref.get("cr_target_range") or [None, None])[:2]
            text = QLabel(
                f"{self.inputs.get('mat_id', 'Material')} prefers "
                f"<b style='color:{PRIMARY}'>{pref.get('bucket_style', '—')}</b> "
                f"({pref.get('discharge_type', '—')}), target CR "
                f"<span style='font-family:{MONO_FAMILY}'>"
                f"{fmt(cr_lo, 1)}–{fmt(cr_hi, 1)}</span>. "
                f"This is a strong default, not a wall — a different style can still "
                f"rank well if it wins decisively elsewhere."
            )
            text.setWordWrap(True)
            text.setTextFormat(Qt.TextFormat.RichText)
            text.setStyleSheet(f"color: {TEXT2}; font-size: 13px;")
            bl.addWidget(text)
            self.status_box.addWidget(box)

        n_points = result.get("n_pareto_points", 0)
        elapsed = result.get("elapsed_s")
        top = self._sorted_front[0] if self._sorted_front else None
        note = None
        if top:
            note = (f"Top by current sort: {top.get('n_rpm')} rpm · "
                    f"{top.get('bucket_id')} · {top.get('motor_kw')} kW")
        self.status_box.addWidget(stat_box(
            [("Pareto Points", str(n_points)),
             ("Solve Time", f"{fmt(elapsed, 2)} s"),
             ("Selected", str(len(self._selected)))],
            note=note,
        ))

        sort_row = QHBoxLayout()
        sort_row.addWidget(section_head("Sort By"))
        self.status_box.addLayout(sort_row)

        # Was a hand-rolled BARE combo stylesheet. A QComboBox owns an internal
        # view, so the border landed inside it. Shared styled_combo() now.
        self.sort_combo = styled_combo(QComboBox())
        for sort_id, label in SORT_OPTIONS:
            self.sort_combo.addItem(label, sort_id)
        idx = next((i for i, (sid, _) in enumerate(SORT_OPTIONS)
                    if sid == self._sort_by), 0)
        self.sort_combo.setCurrentIndex(idx)
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        self.status_box.addWidget(self.sort_combo)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        self.apply_btn = _secondary_button("✓ Apply Selected to Design")
        self.apply_btn.setEnabled(len(self._selected) == 1)
        self.apply_btn.clicked.connect(self._apply_selected)
        action_row.addWidget(self.apply_btn)
        self.export_btn = _secondary_button("⬇ Export Variants as PDF")
        self.export_btn.setEnabled(len(self._selected) > 0)
        self.export_btn.clicked.connect(self._export_selected)
        action_row.addWidget(self.export_btn)
        select_all_btn = _secondary_button("Select All")
        select_all_btn.clicked.connect(self._select_all)
        action_row.addWidget(select_all_btn)
        clear_btn = _secondary_button("Clear")
        clear_btn.clicked.connect(self._clear_selection)
        action_row.addWidget(clear_btn)
        self.status_box.addLayout(action_row)

        self.report_status = QLabel("")
        self.report_status.setWordWrap(True)
        self.report_status.setStyleSheet(f"color: {TEAL}; font-size: 13px;")
        self.status_box.addWidget(self.report_status)

    # ── Selection ────────────────────────────────────────────────────
    def _toggle_select(self, row):
        if row in self._selected:
            self._selected.discard(row)
        else:
            self._selected.add(row)
        self._rebuild_status()
        self._rebuild_results()

    def _select_all(self):
        self._selected = set(range(len(self._sorted_front)))
        self._rebuild_status()
        self._rebuild_results()

    def _clear_selection(self):
        self._selected = set()
        self._rebuild_status()
        self._rebuild_results()

    def _apply_selected(self):
        if len(self._selected) != 1:
            return
        c = self._sorted_front[next(iter(self._selected))]
        payload = {
            "rpm": c.get("n_rpm"),
            "bucket_id": c.get("bucket_id"),
            "fill": c.get("fill_pct"),
            "D_mm": c.get("D_mm"),
            "boot_pulley_D_mm": c.get("boot_pulley_D_mm"),
        }
        # Chain-only fields merged only when present -- a belt-mode result has
        # none, and merging None would clobber an existing value rather than
        # leave it untouched. Same guard the JSX uses.
        for key in ("chain_n_strands", "chain_sprocket_teeth",
                    "chain_boot_sprocket_teeth"):
            if c.get(key) is not None:
                payload[key] = c[key]
        if self.on_apply:
            self.on_apply(payload)

    def _export_selected(self):
        if not self._selected:
            return
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save Variant Report", "elevator_variants.pdf", "PDF Files (*.pdf)")
        if not save_path:
            return
        candidates = [
            to_variant_report_shape(self._sorted_front[i], rank + 1)
            for rank, i in enumerate(sorted(self._selected))
        ]
        self.export_btn.setEnabled(False)
        self.report_status.setText("Generating report…")
        self._report_worker = ReportWorker(
            candidates, self.inputs, save_path, parent=self)
        self._report_worker.done.connect(self._on_report_done)
        self._report_worker.errorOccurred.connect(self._on_report_error)
        self._report_worker.start()

    def _on_report_done(self, path):
        self.export_btn.setEnabled(len(self._selected) > 0)
        self.report_status.setStyleSheet(f"color: {SUCCESS}; font-size: 13px;")
        self.report_status.setText(f"Saved: {path}")

    def _on_report_error(self, message):
        self.export_btn.setEnabled(len(self._selected) > 0)
        self.report_status.setStyleSheet(f"color: {DANGER}; font-size: 13px;")
        self.report_status.setText(f"Export failed: {message}")

    # ── Results table ────────────────────────────────────────────────
    def _rebuild_results(self):
        clear_layout(self.results_box)
        if not self._sorted_front:
            empty = QLabel("No feasible Pareto points found for this configuration.")
            empty.setStyleSheet(
                f"color: {TEXT2}; font-size: 13px; font-style: italic;")
            self.results_box.addWidget(empty)
            return

        is_chain = (self.inputs.get("conveyor_type") or "belt") == "chain"
        columns = list(TABLE_COLUMNS_BASE)
        if is_chain:
            columns += TABLE_COLUMNS_CHAIN
        columns += TABLE_COLUMNS_TAIL

        table = QTableWidget(len(self._sorted_front), len(columns))
        table.setHorizontalHeaderLabels([c[0] for c in columns])
        table.verticalHeader().setVisible(False)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(False)
        # QHeaderView::section / ::item are INTENTIONAL descendant rules.
        table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {PANEL2}; color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: {R_SM}px; gridline-color: {BORDER};
                font-size: 13px;
            }}
            QHeaderView::section {{
                background-color: {PANEL}; color: {TEXT2}; border: none;
                border-bottom: 1px solid {BORDER}; padding: 6px 4px;
                font-size: 12px; font-weight: 700; letter-spacing: .04em;
            }}
            QTableWidget::item {{ padding: 4px; border: none; }}
        """)
        table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        table.setMinimumHeight(min(40 + 28 * len(self._sorted_front), 520))

        # Row tints, now derived from the v2 tokens instead of hardcoded v1
        # QColor triples.
        tint_pinned = _row_tint(PRIMARY, 30)
        tint_infeasible = _row_tint(DANGER, 18)
        tint_top = _row_tint(SUCCESS, 14)

        for row, c in enumerate(self._sorted_front):
            is_top = row == 0
            is_pinned = row in self._selected
            is_infeasible = c.get("feasible") is False
            bg = None
            if is_pinned:
                bg = tint_pinned
            elif is_infeasible:
                bg = tint_infeasible
            elif is_top:
                bg = tint_top

            col_i = 0

            def set_cell(text, color=TEXT, mono=True):
                nonlocal col_i
                item = QTableWidgetItem(text)
                item.setForeground(QColor(color))
                if mono:
                    f = item.font()
                    f.setFamily(MONO_FAMILY)
                    item.setFont(f)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if bg:
                    item.setBackground(bg)
                table.setItem(row, col_i, item)
                col_i += 1

            set_cell("☑" if is_pinned else "☐",
                     PRIMARY if is_pinned else TEXT3, mono=False)
            set_cell("★" if is_top else str(row + 1),
                     SUCCESS if is_top else TEXT3, mono=False)
            set_cell(str(c.get("n_rpm", "—")))
            set_cell(str(c.get("bucket_id", "—")), PRIMARY)
            set_cell(f"{c.get('fill_pct', '—')}%")
            set_cell(str(c.get("D_mm", "—")))
            set_cell(str(c.get("boot_pulley_D_mm", "—")))

            if is_chain:
                strands = c.get("chain_n_strands")
                set_cell(str(strands) if strands is not None else "—")
                ht = c.get("chain_sprocket_teeth")
                bt = c.get("chain_boot_sprocket_teeth")
                set_cell(f"{ht if ht is not None else '—'}/"
                         f"{bt if bt is not None else '—'}")

            set_cell(str(c.get("Q_th", "—")), SUCCESS)
            set_cell(str(c.get("motor_kw", "—")), WARNING)
            R = c.get("R_headshaft_N")
            set_cell(str(round(R / 1000)) if R is not None else "—")
            L10 = c.get("L10_h")
            set_cell(f"{L10:,.0f}" if L10 is not None else "—")
            L10b = c.get("L10_boot_h")
            set_cell(f"{L10b:,.0f}" if L10b is not None else "—")
            sm = c.get("startup_margin")
            set_cell(fmt(sm, 2) if sm is not None else "n/a")
            set_cell(str(c.get("cr", "—")))
            dev = c.get("cr_deviation")
            set_cell(fmt(dev, 3), cr_dev_color(dev))

        table.cellClicked.connect(lambda row, _col: self._toggle_select(row))
        self.results_box.addWidget(table)

        footer = QLabel(
            "Click any row to select / deselect. CR Dev = distance outside the "
            "material's preferred CR range (0 = exactly on target). L10 Boot and "
            "Startup Margin reflect the optimizer's own hard constraints (20,000h "
            "floor, ≥1.0 margin) — both already enforced in the search, shown here "
            "for visibility."
        )
        footer.setWordWrap(True)
        footer.setStyleSheet(f"color: {TEXT2}; font-size: 13px;")
        self.results_box.addWidget(footer)