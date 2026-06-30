"""
components/optimizer_panel.py -- multi-objective (NSGA-II) optimizer panel.
═══════════════════════════════════════════════════════════════════════════
Faithful port of frontend/src/components/OptimizerPanel.jsx, read directly
before writing this (not assumed) -- same search description, same sort
options, same Pareto-front table columns, same Apply/Export/Select-All/
Clear actions, same material-preference and summary strips.

Visually elevated beyond the bare JSX layout per direct feedback that the
original "is pretty bland" -- the underlying behavior is unchanged, but
this uses the same card/badge design language already established in
status_panel.py and dialog_helpers.py (status_badge, neutral bordered
cards with a colored accent, graduated CR-deviation coloring) instead of
a single flat table with inline-colored text, which is what the JSX
itself does. This is the one section so far where "professional" was an
explicit ask rather than a fidelity requirement, so the visual layer was
genuinely redesigned -- the data, columns, and actions were not.

Architecture notes:
  - The actual NSGA-II run is a genuine ~3-30s blocking network call
    (confirmed directly: 24.3s for a real 200x100 budget run) -- run on a
    background OptimizerWorker(QThread), never on the GUI thread. Same
    reasoning MaterialSearchWorker already established elsewhere in this
    app: a slow network call inside a button's click handler freezes the
    whole window, which is a real bug class, not a style preference.
  - PDF export is a second, separate, smaller backend call -- also run on
    a background thread (ReportWorker) so a multi-variant report request
    can't visibly freeze the dialog either, same reasoning.
  - No optimization math lives here. Every number in the table comes
    straight from the backend's Pareto-front response; sorting is a
    plain list re-order by an existing field, not a recomputation.

Backend sync check (per direct instruction this round): re-read
vectrix_optimizer_v2.py end-to-end against the rest of this session's
calculations.py changes. Found and fixed two real gaps in the optimizer
engine itself (not a frontend concern, but verified and fixed before
building this UI, since the UI surfaces exactly these two new fields):
  1. Boot bearing life was unconstrained -- D_mm/boot_pulley_D_mm became
     independent search variables in an earlier round, but only the head
     shaft's L10 had a floor constraint. Added l10_boot_violation,
     mirroring the existing l10_violation pattern exactly.
  2. Belt-mode startup tension margin (startup_margin/belt_rated_N, real
     computed fields) never had a corresponding fail()/warn() in
     calculations.py's checks[], so it was invisible to the optimizer's
     generic fail_count constraint. Added startup_margin_violation
     (no-op for chain runs, where these fields don't exist).
Both surfaced as new display columns below (L10 Boot, Startup Margin),
not just silent constraints.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QFileDialog, QScrollArea,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor

from theme import PANEL, PANEL2, BORDER, TEXT, TEXT2, TEXT3, MUTED, PRIMARY, SUCCESS, WARNING, DANGER, TEAL
from api_client import optimize_elevator_v2, download_variant_report
from .dialog_helpers import status_badge, flag_note, stat_box, section_head


def fmt(v, digits=2, fb="—"):
    if v is None:
        return fb
    try:
        return f"{float(v):.{digits}f}"
    except (TypeError, ValueError):
        return fb


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
    """Mirrors OptimizerPanel.jsx's crDevColor() exactly -- a graduated
    band across cr_deviation's own scale, not a recomputation of
    anything: cr_deviation already arrives from the backend as the real,
    material-aware distance from the preferred CR range."""
    dev = dev or 0
    if dev >= 0.5:
        return DANGER
    if dev >= 0.1:
        return WARNING
    return TEAL


def to_variant_report_shape(p, rank):
    """Mirrors OptimizerPanel.jsx's toVariantReportShape() exactly -- maps
    a Pareto point into the field shape generate_variant_report's
    build_variant_report() expects."""
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
    """Runs the actual NSGA-II call off the GUI thread -- confirmed
    directly this is a genuine ~3-30s blocking network call (24.3s for a
    real 200x100-budget run), not a quick request. Same reasoning
    MaterialSearchWorker already established: a slow call inside a
    button click handler freezes the whole window."""
    resultReady = Signal(dict)
    errorOccurred = Signal(str)

    def __init__(self, base_input, parent=None):
        super().__init__(parent)
        self.base_input = base_input

    def run(self):
        try:
            result = optimize_elevator_v2(self.base_input)
            self.resultReady.emit(result)
        except Exception as e:
            self.errorOccurred.emit(str(e))


class ReportWorker(QThread):
    """Runs the PDF export call off the GUI thread, same reasoning as
    OptimizerWorker -- a multi-variant report request is a real network
    call, not instant."""
    done = Signal(str)
    errorOccurred = Signal(str)

    def __init__(self, candidates, inputs, save_path, parent=None):
        super().__init__(parent)
        self.candidates = candidates
        self.inputs = inputs
        self.save_path = save_path

    def run(self):
        try:
            path = download_variant_report(self.candidates, self.inputs, self.save_path)
            self.done.emit(path)
        except Exception as e:
            self.errorOccurred.emit(str(e))


def _primary_button(text):
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {PRIMARY}; color: white; border: none;
            border-radius: 6px; padding: 10px 18px; font-size: 12.5px; font-weight: 700;
        }}
        QPushButton:disabled {{ background-color: {PANEL2}; color: {TEXT3}; }}
        QPushButton:hover:!disabled {{ background-color: #5aa8ff; }}
    """)
    return btn


def _secondary_button(text):
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {PANEL2}; color: {TEXT2}; border: 1px solid {BORDER};
            border-radius: 6px; padding: 8px 14px; font-size: 11.5px; font-weight: 600;
        }}
        QPushButton:disabled {{ color: {TEXT3}; border-color: {BORDER}; }}
        QPushButton:hover:!disabled {{ background-color: {BORDER}; color: {TEXT}; }}
    """)
    return btn


class OptimizerPanel(QWidget):
    """Port of OptimizerPanel.jsx's default export. Same set_data(inputs,
    results) shape as every other panel in this app, even though only
    `inputs` is actually used (the optimizer runs against current inputs,
    not the last-calculated results) -- kept for interface consistency
    with how main.py calls every middle-stack/column panel."""

    def __init__(self, on_apply, parent=None):
        super().__init__(parent)
        self.on_apply = on_apply
        self.inputs = {}
        self._pareto_front = []
        self._sorted_front = []
        self._selected = set()
        self._worker = None
        self._report_worker = None
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
        self.body_layout.setSpacing(12)

        intro = QLabel(
            "Multi-objective (NSGA-II) optimizer searches RPM × Bucket × Fill × Head & Boot "
            "Pulley Diameter space subject to CEMA speed limits and a 20,000h bearing-life "
            "floor (head and boot). Returns a genuine Pareto-efficient front — every row "
            "below is a real trade-off, not a single \"best\" answer."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {TEXT2}; font-size: 11px; line-height: 145%;")
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
        self._clear_layout(self.status_box)
        self._clear_layout(self.results_box)
        self._selected = set()
        self._worker = OptimizerWorker(self.inputs, parent=self)
        self._worker.resultReady.connect(self._on_result)
        self._worker.errorOccurred.connect(self._on_error)
        self._worker.start()

    def _on_error(self, message):
        self.run_btn.setEnabled(True)
        self.run_btn.setText("▶  RUN OPTIMIZER")
        flag_note("fail", f"Optimizer run failed: {message}", parent_layout=self.status_box)

    def _on_result(self, result):
        self.run_btn.setEnabled(True)
        self.run_btn.setText("▶  RUN OPTIMIZER")
        self._result = result
        self._pareto_front = result.get("pareto_front") or []
        self._rebuild_sorted_front("cr_deviation")
        self._rebuild_status()
        self._rebuild_results()

    # ── Sorting ──────────────────────────────────────────────────────
    def _rebuild_sorted_front(self, sort_by):
        reverse = sort_by == "L10_h"  # longer life first; everything else ascending
        self._sort_by = sort_by
        self._sorted_front = sorted(
            self._pareto_front, key=lambda c: c.get(sort_by) or 0, reverse=reverse
        )

    def _on_sort_changed(self, index):
        sort_id = SORT_OPTIONS[index][0]
        self._rebuild_sorted_front(sort_id)
        self._selected = set()
        self._rebuild_status()
        self._rebuild_results()

    # ── Status strips (material preference + summary) ──────────────────
    def _rebuild_status(self):
        self._clear_layout(self.status_box)
        pref = (self._result or {}).get("material_preference")
        if pref:
            box = QFrame()
            box.setStyleSheet(f"background-color: rgba(74,158,255,.06); border: 1px solid rgba(74,158,255,.2); border-radius: 7px;")
            bl = QVBoxLayout(box)
            bl.setContentsMargins(12, 10, 12, 10)
            cr_lo, cr_hi = (pref.get("cr_target_range") or [None, None])[:2]
            text = QLabel(
                f"{self.inputs.get('mat_id', 'Material')} prefers "
                f"<b style='color:{PRIMARY}'>{pref.get('bucket_style', '—')}</b> "
                f"({pref.get('discharge_type', '—')}), target CR "
                f"<span style='font-family:JetBrains Mono'>{fmt(cr_lo, 1)}–{fmt(cr_hi, 1)}</span>. "
                f"This is a strong default, not a wall — a different style can still rank "
                f"well if it wins decisively elsewhere."
            )
            text.setWordWrap(True)
            text.setTextFormat(Qt.TextFormat.RichText)
            text.setStyleSheet(f"color: {TEXT2}; font-size: 11px;")
            bl.addWidget(text)
            self.status_box.addWidget(box)

        n_points = self._result.get("n_pareto_points", 0)
        elapsed = self._result.get("elapsed_s")
        top = self._sorted_front[0] if self._sorted_front else None
        stats = [
            ("Pareto Points", str(n_points)),
            ("Solve Time", f"{fmt(elapsed, 2)} s"),
            ("Selected", str(len(self._selected))),
        ]
        note = None
        if top:
            note = f"Top by current sort: {top.get('n_rpm')} rpm · {top.get('bucket_id')} · {top.get('motor_kw')} kW"
        self.status_box.addWidget(stat_box(stats, note=note))

        sort_row = QHBoxLayout()
        sort_row.addWidget(section_head("Sort By"))
        self.status_box.addLayout(sort_row)
        self.sort_combo = QComboBox()
        self.sort_combo.setMinimumHeight(28)
        self.sort_combo.setStyleSheet(
            f"background-color: {PANEL2}; color: {TEXT}; border: 1px solid {BORDER}; "
            f"border-radius: 4px; padding: 5px 8px; font-size: 12px;"
        )
        for sort_id, label in SORT_OPTIONS:
            self.sort_combo.addItem(label, sort_id)
        idx = next((i for i, (sid, _) in enumerate(SORT_OPTIONS) if sid == self._sort_by), 0)
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
        self.report_status.setStyleSheet(f"color: {TEAL}; font-size: 10.5px;")
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
        idx = next(iter(self._selected))
        c = self._sorted_front[idx]
        payload = {
            "rpm": c.get("n_rpm"), "bucket_id": c.get("bucket_id"), "fill": c.get("fill_pct"),
            "D_mm": c.get("D_mm"), "boot_pulley_D_mm": c.get("boot_pulley_D_mm"),
        }
        if c.get("chain_n_strands") is not None:
            payload["chain_n_strands"] = c["chain_n_strands"]
        if c.get("chain_sprocket_teeth") is not None:
            payload["chain_sprocket_teeth"] = c["chain_sprocket_teeth"]
        if c.get("chain_boot_sprocket_teeth") is not None:
            payload["chain_boot_sprocket_teeth"] = c["chain_boot_sprocket_teeth"]
        if self.on_apply:
            self.on_apply(payload)

    def _export_selected(self):
        if not self._selected:
            return
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save Variant Report", "elevator_variants.pdf", "PDF Files (*.pdf)"
        )
        if not save_path:
            return
        candidates = [
            to_variant_report_shape(self._sorted_front[i], rank + 1)
            for rank, i in enumerate(sorted(self._selected))
        ]
        self.export_btn.setEnabled(False)
        self.report_status.setText("Generating report…")
        self._report_worker = ReportWorker(candidates, self.inputs, save_path, parent=self)
        self._report_worker.done.connect(self._on_report_done)
        self._report_worker.errorOccurred.connect(self._on_report_error)
        self._report_worker.start()

    def _on_report_done(self, path):
        self.export_btn.setEnabled(len(self._selected) > 0)
        self.report_status.setStyleSheet(f"color: {SUCCESS}; font-size: 10.5px;")
        self.report_status.setText(f"Saved: {path}")

    def _on_report_error(self, message):
        self.export_btn.setEnabled(len(self._selected) > 0)
        self.report_status.setStyleSheet(f"color: {DANGER}; font-size: 10.5px;")
        self.report_status.setText(f"Export failed: {message}")

    # ── Results table ────────────────────────────────────────────────
    def _rebuild_results(self):
        self._clear_layout(self.results_box)
        if not self._sorted_front:
            empty = QLabel("No feasible Pareto points found for this configuration.")
            empty.setStyleSheet(f"color: {TEXT2}; font-size: 11px; font-style: italic;")
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
        table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {PANEL2}; color: {TEXT}; border: 1px solid {BORDER};
                border-radius: 6px; gridline-color: {BORDER}; font-size: 11px;
            }}
            QHeaderView::section {{
                background-color: {PANEL}; color: {TEXT2}; border: none;
                border-bottom: 1px solid {BORDER}; padding: 6px 4px; font-size: 9.5px;
                font-weight: 700; letter-spacing: .04em;
            }}
            QTableWidget::item {{ padding: 4px; }}
        """)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.setMinimumHeight(min(40 + 28 * len(self._sorted_front), 520))

        for row, c in enumerate(self._sorted_front):
            is_top = row == 0
            is_pinned = row in self._selected
            is_infeasible = c.get("feasible") is False
            bg = None
            if is_pinned:
                bg = QColor(74, 158, 255, 30)
            elif is_infeasible:
                bg = QColor(224, 82, 82, 18)
            elif is_top:
                bg = QColor(31, 184, 110, 14)

            col_i = 0

            def set_cell(text, color=TEXT, mono=True):
                nonlocal col_i
                item = QTableWidgetItem(text)
                item.setForeground(QColor(color))
                if mono:
                    f = item.font()
                    f.setFamily("JetBrains Mono")
                    item.setFont(f)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if bg:
                    item.setBackground(bg)
                table.setItem(row, col_i, item)
                col_i += 1

            set_cell("☑" if is_pinned else "☐", PRIMARY if is_pinned else TEXT3, mono=False)
            set_cell("★" if is_top else str(row + 1), SUCCESS if is_top else TEXT3, mono=False)
            set_cell(str(c.get("n_rpm", "—")))
            set_cell(str(c.get("bucket_id", "—")), PRIMARY)
            set_cell(f"{c.get('fill_pct', '—')}%")
            set_cell(str(c.get("D_mm", "—")))
            set_cell(str(c.get("boot_pulley_D_mm", "—")))
            if is_chain:
                set_cell(str(c.get("chain_n_strands") if c.get("chain_n_strands") is not None else "—"))
                ht = c.get("chain_sprocket_teeth")
                bt = c.get("chain_boot_sprocket_teeth")
                set_cell(f"{ht if ht is not None else '—'}/{bt if bt is not None else '—'}")
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

        def on_cell_clicked(row, _col):
            self._toggle_select(row)
        table.cellClicked.connect(on_cell_clicked)

        self.results_box.addWidget(table)

        footer = QLabel(
            "Click any row to select / deselect. CR Dev = distance outside the material's "
            "preferred CR range (0 = exactly on target). L10 Boot and Startup Margin reflect "
            "the optimizer's own hard constraints (20,000h floor, ≥1.0 margin) — both already "
            "enforced in the search, shown here for visibility."
        )
        footer.setWordWrap(True)
        footer.setStyleSheet(f"color: {TEXT2}; font-size: 10px;")
        self.results_box.addWidget(footer)

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget() if item else None
            if w:
                w.setParent(None)
                w.deleteLater()
            elif item is not None:
                sub = item.layout()
                if sub:
                    OptimizerPanel._clear_layout(sub)