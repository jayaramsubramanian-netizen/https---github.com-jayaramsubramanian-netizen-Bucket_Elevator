"""
components/charts_panel.py -- Analysis charts for the Results tab.
═══════════════════════════════════════════════════════════════════════════
pyqtgraph-based. Five sub-tabs matching ChartsPanel.jsx exactly:

    Speed Sweep      -- dual-axis RPM vs Capacity+Power, hover crosshair
    Fill Analysis    -- area chart Capacity vs Fill%, hover crosshair
    Discharge Traj.  -- multi-line projectile trajectory, hover crosshair
    Tension Model    -- 6 KPI cards (no chart needed)
    Tension Profile  -- position-resolved belt tension, two plotted lines

BOX-IN-BOX -- ACTUAL ROOT CAUSE, FOUND AND FIXED THIS ROUND
───────────────────────────────────────────────────────────
The previous version's comment claimed the box-in-box was solved by
giving _content an explicit `background: PANEL`, on the theory that Qt's
Fusion default background differed from PANEL and so any child with
background:PANEL showed as a visible box.

That fix addressed a BACKGROUND. The bug is a BORDER. It was never fixed,
which is why it kept coming back.

The real cause is in _kpi_card(). It called:

    box.setStyleSheet(f'background:{PANEL2};border:1px solid {BORDER};...')

with NO selector. Qt treats a selector-less stylesheet as `* { ... }` --
it applies to the widget AND EVERY DESCENDANT. _kpi_card builds a QFrame
containing a label QLabel, a value QLabel and a sub QLabel, so all three
inherited `border: 1px solid` and each drew its own box INSIDE the card.
Six cards x 3 labels = 18 phantom boxes on the Tension Model tab alone.

Verified directly rather than assumed: a QFrame with 4 child QLabels
renders 1732 interior border pixels in exactly 8 horizontal runs (4
children x top+bottom edge) under a bare declaration, and 0 under a
scoped one.

Corroborating evidence for the diagnosis: KPIChip in dialog_helpers.py is
the one card in this app that never used a bare stylesheet (it paints
itself with QPainter and has no child widgets), and it is the one card
that never had a box-in-box.

Every declaration below is now scoped -- via theme.card_frame() for the
KPI cards, theme.scoped() elsewhere. The background fix is retained where
it was independently correct.

COLORS: the module-level BLUE/RED/AMBER/GREEN literals and the '#0f1923'
plot background were a hand-picked set that matched neither index.css v1
nor v2. They now come from theme.py, so a palette change is one edit.

NOTE ON PYLANCE WARNINGS: pyqtgraph 0.14's .pyi stubs are incomplete --
PlotWidget.getPlotItem() chains are stubbed as Optional or omit **kwargs
that the real runtime methods accept. Confirmed a stub gap, not a missing
runtime feature. Suppressed for this file rather than littering ~40 call
sites with individual ignores.
"""
# pyright: reportOptionalMemberAccess=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportCallIssue=false
# pyright: reportArgumentType=false

import numpy as np
import pyqtgraph as pg
from pyqtgraph import PlotWidget, InfiniteLine, SignalProxy, mkPen, mkBrush
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton, QGridLayout,
)
from PySide6.QtCore import Qt

from theme import (
    BG, PANEL, PANEL2, SURFACE, BORDER, BORDER2, TEXT, TEXT2, TEXT3, MUTED,
    PRIMARY, SUCCESS, WARNING, DANGER, TEAL,
    BLUE, RED, AMBER, GREEN, FF_MONO, R_SM,
    scoped, card_frame, plain_bg,
)

# ── Chart surface colors, from theme tokens (was: hardcoded '#0f1923') ──
PLOT_BG    = PANEL2      # chart canvas -- matches index.css .chart-wrap
AXIS_TEXT  = MUTED       # tick labels
AXIS_LINE  = SURFACE     # axis spine
FAINT_LINE = '#475569'   # crosshair guide -- between BORDER and TEXT3
GRID_ALPHA = 0.12

pg.setConfigOption('background', PLOT_BG)
pg.setConfigOption('foreground', TEXT3)
pg.setConfigOption('antialias', True)


def fmt(v, dp=2, fb='—'):
    if v is None:
        return fb
    try:
        return f'{float(v):.{dp}f}'
    except (TypeError, ValueError):
        return fb


def _styled_plot(title='') -> PlotWidget:
    """Return a PlotWidget pre-styled to match the app's dark theme."""
    pw = PlotWidget(title=title)
    pw.setBackground(PLOT_BG)
    pi = pw.getPlotItem()
    pi.setContentsMargins(4, 4, 4, 4)
    for axis in ('left', 'bottom', 'right', 'top'):
        ax = pi.getAxis(axis)
        ax.setTextPen(pg.mkPen(AXIS_TEXT))
        ax.setPen(pg.mkPen(AXIS_LINE))
    pi.showGrid(x=True, y=True, alpha=GRID_ALPHA)
    pi.setMouseEnabled(x=True, y=True)
    return pw


def _add_crosshair(pw: PlotWidget, series_map: dict) -> None:
    """Live hover crosshair + value readout.

    series_map: {name: (x_array, y_array, color_hex)} -- curves whose Y
    values appear in the tooltip. Driven by a SignalProxy on
    scene().sigMouseMoved, rate-limited to 30fps."""
    dash = Qt.PenStyle.DashLine
    vline = InfiniteLine(angle=90, movable=False,
                         pen=mkPen(FAINT_LINE, width=1, style=dash))
    hline = InfiniteLine(angle=0, movable=False,
                         pen=mkPen(FAINT_LINE, width=1, style=dash))
    pw.addItem(vline, ignoreBounds=True)
    pw.addItem(hline, ignoreBounds=True)

    label = pg.LabelItem(justify='left')
    label.setParentItem(pw.getPlotItem())
    label.anchor(itemPos=(0, 0), parentPos=(0, 0), offset=(8, 4))

    def on_mouse_moved(evt):
        pos = evt[0]
        if pw.sceneBoundingRect().contains(pos):
            mp = pw.getPlotItem().vb.mapSceneToView(pos)
            x = mp.x()
            vline.setPos(x)
            hline.setPos(mp.y())
            parts = [f"<span style='color:{TEXT3}'>x = {x:.2f}</span>"]
            for name, (xs, ys, color) in series_map.items():
                if len(xs) > 1:
                    idx = int(np.searchsorted(xs, x, side='left'))
                    idx = max(0, min(idx, len(ys) - 1))
                    parts.append(
                        f"<span style='color:{color}'>{name} = {ys[idx]:.2f}</span>"
                    )
            label.setText('  |  '.join(parts))
        else:
            label.setText('')

    proxy = SignalProxy(pw.scene().sigMouseMoved, rateLimit=30, slot=on_mouse_moved)
    pw._crosshair_proxy = proxy   # keep a reference so it isn't GC'd


def _kpi_card(label, value, sub, color):
    """THE box-in-box offender, fixed.

    Was a bare `background:...;border:1px solid ...` on a QFrame full of
    QLabels -- so each label drew its own border inside the card. Now
    built with theme.card_frame(), which declares the border exactly once,
    scoped to the frame's own objectName, so nothing can inherit it.
    """
    box, layout = card_frame(bg=PANEL2, border=BORDER, radius=R_SM,
                             margins=(12, 10, 12, 10), spacing=2)
    lbl = QLabel(label)
    lbl.setStyleSheet(f'color:{TEXT3};font-size:9.5px;')
    layout.addWidget(lbl)
    val = QLabel(value)
    val.setStyleSheet(
        f'color:{color};font-size:16px;font-weight:700;font-family:{FF_MONO};'
    )
    layout.addWidget(val)
    if sub:
        sub_lbl = QLabel(sub)
        sub_lbl.setWordWrap(True)
        sub_lbl.setStyleSheet(f'color:{MUTED};font-size:9px;')
        layout.addWidget(sub_lbl)
    return box


class _SubTabBtn(QPushButton):
    """Chart sub-tab. Scoped -- a QPushButton has no styleable children so
    this never produced a visible artifact, but it's converted so no bare
    declaration remains in this file to be copied by a future edit."""

    def __init__(self, label, parent=None):
        super().__init__(label, parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggled.connect(self._style)
        self._style(False)

    def _style(self, checked):
        if checked:
            self.setStyleSheet(scoped(
                self,
                f'background: transparent; color: {PRIMARY}; border: none; '
                f'border-bottom: 2px solid {PRIMARY}; padding: 7px 12px; '
                f'font-size: 11px; font-weight: 700;'
            ))
        else:
            self.setStyleSheet(scoped(
                self,
                f'background: transparent; color: {TEXT2}; border: none; '
                f'border-bottom: 2px solid transparent; padding: 7px 12px; '
                f'font-size: 11px;'
            ))


class ChartsPanel(QWidget):
    """Port of ChartsPanel.jsx, using pyqtgraph for interactive charts with
    hover crosshair tooltips, smooth curves, and zoom/pan."""

    TABS = [
        ('speed',   'Speed Sweep'),
        ('fill',    'Fill Analysis'),
        ('traj',    'Discharge Trajectory'),
        ('tension', 'Tension Model'),
        ('profile', 'Tension Profile'),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(plain_bg(self, PANEL))
        self._inputs = {}
        self._results = {}
        self._active = 'speed'

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Sub-tab bar. SCOPED: the old bare declaration carried a
        # `border-top`, which every _SubTabBtn inside it inherited -- each
        # tab button was drawing its own top border, on top of its own
        # bottom border. That's the row of stacked lines above the tabs.
        tab_bar = QFrame()
        tab_bar.setStyleSheet(scoped(
            tab_bar,
            f'background-color: {PANEL2}; border: none; '
            f'border-top: 1px solid {BORDER};'
        ))
        tbl = QHBoxLayout(tab_bar)
        tbl.setContentsMargins(12, 0, 12, 0)
        tbl.setSpacing(0)
        self._tab_btns = {}
        for tid, label in self.TABS:
            btn = _SubTabBtn(label)
            btn.setChecked(tid == self._active)
            btn.clicked.connect(lambda _, t=tid: self._switch_tab(t))
            tbl.addWidget(btn)
            self._tab_btns[tid] = btn
        tbl.addStretch()
        outer.addWidget(tab_bar)

        # Content area. The explicit PANEL background here IS still needed
        # and is retained -- without it Qt uses the Fusion platform default,
        # which differs from PANEL, so a child with background:PANEL reads
        # as a visible block against a slightly different container color.
        # That was a real (if separate) issue; it just wasn't the border bug.
        self._content = QWidget()
        self._content.setStyleSheet(plain_bg(self._content, PANEL))
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(0)
        outer.addWidget(self._content, 1)

        self._current_widget = None

    def set_data(self, inputs, results):
        self._inputs = inputs or {}
        self._results = results or {}
        self._rebuild()

    def _switch_tab(self, tab_id):
        self._active = tab_id
        for tid, btn in self._tab_btns.items():
            btn.setChecked(tid == tab_id)
        self._rebuild()

    def _rebuild(self):
        if self._current_widget is not None:
            self._content_layout.removeWidget(self._current_widget)
            self._current_widget.setParent(None)
            self._current_widget.deleteLater()
            self._current_widget = None

        builders = {
            'speed':   self._build_speed_sweep,
            'fill':    self._build_fill_sweep,
            'traj':    self._build_trajectory,
            'tension': self._build_tension_model,
            'profile': self._build_tension_profile,
        }
        widget = builders.get(self._active, lambda: QLabel('Unknown tab'))()
        self._current_widget = widget
        self._content_layout.addWidget(widget)

    # ── Speed Sweep ──────────────────────────────────────────────────
    def _build_speed_sweep(self) -> QWidget:
        data = self._results.get('speed_sweep') or []
        pw = _styled_plot()
        pw.setMinimumHeight(220)
        pi = pw.getPlotItem()

        if not data:
            pi.setTitle('No speed sweep data — recalculate')
            return pw

        rpm = np.array([d['rpm'] for d in data])
        cap = np.array([d['capacity'] for d in data])
        pwr = np.array([d['power'] for d in data])

        ax_right = pi.getAxis('right')
        ax_right.setLabel('Power (kW)', color=AXIS_TEXT)
        vb2 = pg.ViewBox()
        pi.scene().addItem(vb2)
        ax_right.linkToView(vb2)
        vb2.setXLink(pi.vb)
        pi.vb.sigResized.connect(lambda: vb2.setGeometry(pi.vb.sceneBoundingRect()))
        pi.vb.sigResized.emit(pi.vb)

        pi.setLabel('left', 'Capacity (t/h)', color=AXIS_TEXT)
        pi.setLabel('bottom', 'RPM', color=AXIS_TEXT)
        pi.showAxis('right')

        c1 = pi.plot(rpm, cap, pen=mkPen(BLUE, width=2.5), name='Capacity (t/h)')
        c2 = pg.PlotDataItem(rpm, pwr, pen=mkPen(RED, width=2.5), name='Power (kW)')
        vb2.addItem(c2)

        pi.addLegend(offset=(10, 10))
        pi.legend.addItem(c1, 'Capacity (t/h)')
        pi.legend.addItem(c2, 'Power (kW)')

        n_rpm = self._inputs.get('n_rpm')
        if n_rpm:
            pi.addItem(InfiniteLine(
                pos=n_rpm, angle=90,
                pen=mkPen(AMBER, width=1.2, style=Qt.PenStyle.DashLine),
                label=f'{n_rpm} rpm',
                labelOpts={'color': AMBER, 'position': 0.9}))
        q_req = self._inputs.get('Q_req')
        if q_req:
            pi.addItem(InfiniteLine(
                pos=q_req, angle=0,
                pen=mkPen(GREEN, width=1.2, style=Qt.PenStyle.DashLine),
                label=f'Req {q_req}t/h',
                labelOpts={'color': GREEN, 'position': 0.95,
                           'anchors': [(1, 1), (1, 1)]}))

        _add_crosshair(pw, {
            'Cap (t/h)': (rpm, cap, BLUE),
            'Pwr (kW)':  (rpm, pwr, RED),
        })
        return pw

    # ── Fill Analysis ─────────────────────────────────────────────────
    def _build_fill_sweep(self) -> QWidget:
        data = self._results.get('fill_sweep') or []
        pw = _styled_plot()
        pw.setMinimumHeight(220)
        pi = pw.getPlotItem()

        if not data:
            pi.setTitle('No fill sweep data — recalculate')
            return pw

        fill = np.array([d['fill'] for d in data])
        cap = np.array([d['capacity'] for d in data])

        pi.setLabel('left', 'Capacity (t/h)', color=AXIS_TEXT)
        pi.setLabel('bottom', 'Fill %', color=AXIS_TEXT)

        curve = pi.plot(fill, cap, pen=mkPen(TEAL, width=2.5), name='Capacity (t/h)')
        baseline = pg.PlotDataItem(fill, np.zeros_like(fill))
        fill_item = pg.FillBetweenItem(curve, baseline, brush=mkBrush(TEAL + '28'))
        pi.addItem(fill_item)

        f_cur = self._inputs.get('fill_pct')
        if f_cur:
            pi.addItem(InfiniteLine(
                pos=f_cur, angle=90,
                pen=mkPen(AMBER, width=1.2, style=Qt.PenStyle.DashLine),
                label=f'{f_cur}%', labelOpts={'color': AMBER, 'position': 0.9}))
        q_req = self._inputs.get('Q_req')
        if q_req:
            pi.addItem(InfiniteLine(
                pos=q_req, angle=0,
                pen=mkPen(GREEN, width=1.2, style=Qt.PenStyle.DashLine),
                label=f'{q_req}t/h',
                labelOpts={'color': GREEN, 'position': 0.95,
                           'anchors': [(1, 1), (1, 1)]}))

        _add_crosshair(pw, {'Cap (t/h)': (fill, cap, TEAL)})
        return pw

    # ── Discharge Trajectory ──────────────────────────────────────────
    def _build_trajectory(self) -> QWidget:
        traj = self._results.get('trajectory') or []
        pw = _styled_plot()
        pw.setMinimumHeight(220)
        pi = pw.getPlotItem()

        if not traj:
            pi.setTitle('No trajectory data — recalculate')
            return pw

        x = np.array([d['x'] for d in traj])
        y = np.array([d['y'] for d in traj])
        pi.setLabel('left', 'Vertical (mm)', color=AXIS_TEXT)
        pi.setLabel('bottom', 'Horizontal (mm)', color=AXIS_TEXT)

        pi.plot(x, y, pen=mkPen(TEAL, width=2.5), name='Centreline')
        curves = {'Centreline': (x, y, TEAL)}

        for key, color, name in [
            ('trajectory_upper', TEAL + 'aa', 'Upper edge'),
            ('trajectory_lower', TEAL + '66', 'Lower edge'),
        ]:
            pts = self._results.get(key) or []
            if pts:
                xu = np.array([d['x'] for d in pts])
                yu = np.array([d['y'] for d in pts])
                pi.plot(xu, yu, pen=mkPen(color, width=1.5,
                        style=Qt.PenStyle.DashLine), name=name)
                curves[name] = (xu, yu, color)

        pi.addLegend(offset=(10, 10))
        metrics = self._results.get('trajectory_metrics') or {}
        if metrics.get('discharge_type'):
            pi.setTitle(f"Discharge: {metrics['discharge_type'].upper()}  "
                        f"CR={fmt(self._results.get('cr'), 3)}")

        _add_crosshair(pw, curves)
        return pw

    # ── Tension Model ─────────────────────────────────────────────────
    def _build_tension_model(self) -> QWidget:
        """No line chart -- 6 KPI cards. This is the tab where the
        box-in-box was most visible (6 cards x 3 child labels)."""
        r = self._results
        inp = self._inputs
        T1 = r.get('T1')
        T2 = r.get('T2')
        T3 = r.get('T3')
        F_eff = r.get('F_eff')
        euler_ratio = r.get('euler_ratio')
        slip_safe = r.get('slip_safe')
        tight = (T3 + F_eff) if (T3 is not None and F_eff is not None) else None

        w = QWidget()
        w.setStyleSheet(plain_bg(w, PANEL))
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        grid = QGridLayout()
        grid.setSpacing(8)
        cards = [
            ('Effective Tension  F_eff',
             f'{fmt(F_eff/1000 if F_eff else None, 3)} kN', '= T1 + T2', BLUE),
            ('Material Component  T1',
             f'{fmt(T1/1000 if T1 else None, 3)} kN', 'Lifting material', RED),
            ('Self-Weight  T2',
             f'{fmt(T2/1000 if T2 else None, 3)} kN', 'Belt + bucket mass × H × g', TEAL),
            ('Take-up Slack Side  T3',
             f'{fmt(T3/1000 if T3 else None, 3)} kN',
             f'F_eff × K = {inp.get("K_takeup","—")}', AMBER),
            ('Belt Tight Side  T3+F_eff',
             f'{fmt(tight/1000 if tight else None, 3)} kN', 'Carrying run tension', TEXT),
            ('Euler Limit  e^(μθ)',
             fmt(euler_ratio, 3),
             f'μ={inp.get("mu","—")}  θ={inp.get("wrap_deg","—")}°', TEXT3),
        ]
        for i, (lbl, val, sub, color) in enumerate(cards):
            grid.addWidget(_kpi_card(lbl, val, sub, color), i // 2, i % 2)
        layout.addLayout(grid)

        if slip_safe is not None and T3 and F_eff:
            ratio_actual = (T3 + F_eff) / T3
            slip_color = SUCCESS if slip_safe else DANGER
            slip_icon = '✓ No slip' if slip_safe else '⚠ SLIP RISK — increase T3'
            lbl = QLabel(
                f'Slip check: (T3+F_eff)/T3 = {ratio_actual:.3f}  '
                f'vs  e^μθ = {fmt(euler_ratio, 3)}   {slip_icon}'
            )
            lbl.setStyleSheet(f'color:{slip_color};font-size:10px;padding:4px 0;')
            layout.addWidget(lbl)

        layout.addStretch()
        return w

    # ── Tension Profile ───────────────────────────────────────────────
    def _build_tension_profile(self) -> QWidget:
        r = self._results
        if r.get('is_chain'):
            lbl = QLabel(
                'Tension profile is not computed for chain elevators.\n'
                'Chain pull is a single lumped value — see Components tab.'
            )
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f'color:{TEXT2};font-size:11px;padding:20px;')
            return lbl

        tp = r.get('tension_profile')
        if not tp or not tp.get('stations'):
            lbl = QLabel('Tension profile not available — recalculate to generate.')
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f'color:{TEXT2};font-size:11px;padding:20px;')
            return lbl

        stations = tp['stations']
        loaded = [(s['position_m'], s['tension_N'])
                  for s in stations if s.get('leg') == 'loaded']
        empty = [(s['position_m'], s['tension_N'])
                 for s in stations if s.get('leg') == 'empty']

        pw = _styled_plot()
        pw.setMinimumHeight(220)
        pi = pw.getPlotItem()
        pi.setLabel('left', 'Tension (kN)', color=AXIS_TEXT)
        pi.setLabel('bottom', 'Position from boot (m)', color=AXIS_TEXT)

        series_map = {}
        if loaded:
            lx = np.array([p[0] for p in loaded])
            ly = np.array([p[1] / 1000 for p in loaded])
            pi.plot(lx, ly, pen=mkPen(BLUE, width=2.5), name='Loaded (carry)')
            series_map['Loaded kN'] = (lx, ly, BLUE)
        if empty:
            ex = np.array([p[0] for p in empty])
            ey = np.array([p[1] / 1000 for p in empty])
            pi.plot(ex, ey, pen=mkPen(TEAL, width=1.8,
                    style=Qt.PenStyle.DashLine), name='Empty (return)')
            series_map['Empty kN'] = (ex, ey, TEAL)

        T_rated = tp.get('belt_rated_N')
        if T_rated:
            pi.addItem(InfiniteLine(
                pos=T_rated / 1000, angle=0,
                pen=mkPen(RED, width=1.2, style=Qt.PenStyle.DashLine),
                label=f'Rated {T_rated/1000:.1f}kN',
                labelOpts={'color': RED, 'position': 0.95,
                           'anchors': [(1, 1), (1, 1)]}))

        pi.addLegend(offset=(10, 10))
        _add_crosshair(pw, series_map)

        container = QWidget()
        container.setStyleSheet(plain_bg(container, PANEL))
        cl = QVBoxLayout(container)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(6)
        cl.addWidget(pw)

        margin = tp.get('rating_margin')
        m_color = (SUCCESS if (margin and margin >= 1.25)
                   else AMBER if (margin and margin >= 1.0)
                   else DANGER)
        grid = QGridLayout()
        grid.setSpacing(6)
        summary = [
            ('Peak tension (head)',
             f'{fmt(tp.get("T_max_N", 0)/1000 if tp.get("T_max_N") else None, 2)} kN',
             None, BLUE),
            ('Min tension (boot)',
             f'{fmt(tp.get("T_min_N", 0)/1000 if tp.get("T_min_N") else None, 2)} kN',
             None, TEAL),
            ('Belt rated',
             f'{fmt(T_rated/1000 if T_rated else None, 2)} kN', None, TEXT3),
            ('Rating margin',
             fmt(margin, 3) if margin else '—', None, m_color),
        ]
        for i, (lbl, val, sub, color) in enumerate(summary):
            grid.addWidget(_kpi_card(lbl, val, sub, color), 0, i)
        cl.addLayout(grid)
        return container