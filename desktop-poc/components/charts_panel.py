"""
components/charts_panel.py -- Analysis charts for the Results tab.
═══════════════════════════════════════════════════════════════════════════
Port of frontend/src/components/ChartsPanel.jsx (427 lines, read directly
before writing this). Five sub-tabs, same as the real JSX:

    Speed Sweep      — Capacity & Power vs RPM (dual-axis line chart)
    Fill Analysis    — Capacity vs Fill % (area chart)
    Discharge Traj.  — Projectile trajectory x/y (line chart, SVG)
    Tension Model    — Six KPI cards (T1/T2/T3/F_eff/ratio/euler)
    Tension Profile  — Position-resolved per-station SVG belt tension diagram

All data from results dict -- no recomputation. All fields null-guarded
per ChartsPanel.jsx's own v1.9.9 note about the tension_ratio crash
(was accessing results.tension_ratio which doesn't exist; T1/T2 are real
and the ratio is trivially derived from them).

Backend fields confirmed present before building (real /calculate response):
    speed_sweep:  [{rpm, speed, capacity, power, cr}, ...]  19 items
    fill_sweep:   [{fill, capacity}, ...]                   15 items
    trajectory:   [{x, y}, ...]                             20 items
    trajectory_upper/lower: same shape (belt-edge bands)
    trajectory_metrics: {discharge_type, land_x_m, land_y_m, onset_angle_deg}
    tension_profile: {stations:[{position_m, leg, tension_N},...], T_max_N,
                      T_min_N, belt_rated_N, rating_margin, T_max_location,
                      note, ...}
    T1, T2, T3, F_eff, euler_ratio, slip_safe -- top-level results fields
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea, QPushButton,
    QGridLayout,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPainterPath, QFont

from theme import PANEL, PANEL2, BORDER, TEXT, TEXT2, TEXT3, PRIMARY, SUCCESS, WARNING, DANGER, TEAL


def fmt(v, dp=2, fb="—"):
    if v is None:
        return fb
    try:
        return f"{float(v):.{dp}f}"
    except (TypeError, ValueError):
        return fb


BLUE    = "#3b82f6"
RED     = "#ef4444"
AMBER   = "#f59e0b"


class _SubTabBtn(QPushButton):
    def __init__(self, label, parent=None):
        super().__init__(label, parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggled.connect(self._style)
        self._style(False)

    def _style(self, checked):
        if checked:
            self.setStyleSheet(
                f"QPushButton{{background:transparent;color:{PRIMARY};border:none;"
                f"border-bottom:2px solid {PRIMARY};padding:7px 12px;"
                f"font-size:11px;font-weight:700;}}"
            )
        else:
            self.setStyleSheet(
                f"QPushButton{{background:transparent;color:{TEXT2};border:none;"
                f"border-bottom:2px solid transparent;padding:7px 12px;font-size:11px;}}"
            )


class _InlineChart(QWidget):
    """Minimal custom QPainter line/area chart -- avoids a heavy charting
    dependency while staying faithful to the JSX's Recharts charts.
    Renders a series of (x, y) point pairs with optional dual Y axes,
    reference lines, and a legend."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(200)
        self.series = []     # [{data:[(x,y),...], color:str, name:str, area:bool}]
        self.ref_x  = []     # [{x:float, color:str, label:str}]
        self.ref_y  = []     # [{y:float, color:str, label:str}]
        self.x_label = ""
        self.y_label = ""
        self.dual_y  = False
        self.series2 = []    # second-axis series when dual_y=True
        self.setStyleSheet(f"background:{PANEL2};border-radius:6px;")

    def set_data(self, series, ref_x=None, ref_y=None, x_label="", y_label="", dual_y=False, series2=None):
        self.series  = series or []
        self.ref_x   = ref_x  or []
        self.ref_y   = ref_y  or []
        self.x_label = x_label
        self.y_label = y_label
        self.dual_y  = dual_y
        self.series2 = series2 or []
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        ml, mr, mt, mb = 50, 50, 14, 36

        all_data = [pt for s in self.series + self.series2 for pt in s["data"]]
        if not all_data:
            p.setPen(QColor(TEXT3))
            p.drawText(0, 0, w, h, Qt.AlignmentFlag.AlignCenter, "No data")
            p.end()
            return

        xs = [pt[0] for pt in all_data]
        # Left axis covers series 1
        ys1 = [pt[1] for s in self.series  for pt in s["data"]]
        ys2 = [pt[1] for s in self.series2 for pt in s["data"]]

        x_min, x_max = min(xs), max(xs)
        y1_min, y1_max = (min(ys1), max(ys1)) if ys1 else (0, 1)
        y2_min, y2_max = (min(ys2), max(ys2)) if ys2 else (y1_min, y1_max)

        # expand range slightly
        def expand(lo, hi):
            r = max(hi - lo, 1)
            return lo - r * 0.05, hi + r * 0.05
        x_min, x_max = expand(x_min, x_max)
        y1_min, y1_max = expand(y1_min, y1_max)
        y2_min, y2_max = expand(y2_min, y2_max)
        x_range  = max(x_max - x_min, 1e-9)
        y1_range = max(y1_max - y1_min, 1e-9)
        y2_range = max(y2_max - y2_min, 1e-9)

        cw = w - ml - mr
        ch = h - mt - mb

        def px(x):
            return ml + (x - x_min) / x_range * cw

        def py1(y):
            return mt + ch - (y - y1_min) / y1_range * ch

        def py2(y):
            return mt + ch - (y - y2_min) / y2_range * ch

        # Grid
        p.setPen(QPen(QColor(BORDER), 0.7))
        for i in range(5):
            x = ml + i * cw / 4
            p.drawLine(int(x), mt, int(x), mt + ch)
            y = mt + i * ch / 4
            p.drawLine(ml, int(y), ml + cw, int(y))

        # Axes
        p.setPen(QPen(QColor(TEXT3), 1))
        p.drawLine(ml, mt, ml, mt + ch)
        p.drawLine(ml, mt + ch, ml + cw, mt + ch)

        # Axis labels
        small = QFont()
        small.setPixelSize(9)
        p.setFont(small)
        p.setPen(QColor(TEXT3))

        # Y1 ticks
        for i in range(5):
            frac = i / 4
            val = y1_min + frac * y1_range
            y = mt + ch - frac * ch
            p.drawText(2, int(y) - 6, ml - 6, 14, Qt.AlignmentFlag.AlignRight, fmt(val, 0))

        # Y2 ticks (right axis)
        if self.dual_y and self.series2:
            for i in range(5):
                frac = i / 4
                val = y2_min + frac * y2_range
                y = mt + ch - frac * ch
                p.drawText(ml + cw + 2, int(y) - 6, mr - 4, 14, Qt.AlignmentFlag.AlignLeft, fmt(val, 0))

        # X ticks
        for i in range(5):
            frac = i / 4
            val = x_min + frac * x_range
            x = ml + frac * cw
            p.drawText(int(x) - 20, mt + ch + 2, 40, 14, Qt.AlignmentFlag.AlignCenter, fmt(val, 0))

        if self.x_label:
            p.drawText(ml, h - 4, cw, 14, Qt.AlignmentFlag.AlignCenter, self.x_label)

        # Reference lines
        for rx in self.ref_x:
            xv = rx.get("x")
            if xv is not None and x_min <= xv <= x_max:
                xi = px(xv)
                p.setPen(QPen(QColor(rx.get("color", AMBER)), 1.2, Qt.PenStyle.DashLine))
                p.drawLine(int(xi), mt, int(xi), mt + ch)
                lbl = rx.get("label", "")
                if lbl:
                    p.setPen(QColor(rx.get("color", AMBER)))
                    p.drawText(int(xi) + 3, mt + 12, lbl)

        for ry in self.ref_y:
            yv = ry.get("y")
            if yv is not None and y1_min <= yv <= y1_max:
                yi = py1(yv)
                p.setPen(QPen(QColor(ry.get("color", SUCCESS)), 1.2, Qt.PenStyle.DashLine))
                p.drawLine(ml, int(yi), ml + cw, int(yi))
                lbl = ry.get("label", "")
                if lbl:
                    p.setPen(QColor(ry.get("color", SUCCESS)))
                    p.drawText(ml + cw - 80, int(yi) - 3, lbl)

        # Area fill (series 1 only, if area=True)
        for s in self.series:
            if s.get("area") and s["data"]:
                path = QPainterPath()
                path.moveTo(px(s["data"][0][0]), mt + ch)
                for x, y in s["data"]:
                    path.lineTo(px(x), py1(y))
                path.lineTo(px(s["data"][-1][0]), mt + ch)
                path.closeSubpath()
                fill = QColor(s["color"])
                fill.setAlphaF(0.15)
                p.fillPath(path, fill)

        # Lines -- series 1 (left axis)
        for s in self.series:
            if not s["data"]:
                continue
            p.setPen(QPen(QColor(s["color"]), 2))
            pts = s["data"]
            for i in range(1, len(pts)):
                p.drawLine(int(px(pts[i-1][0])), int(py1(pts[i-1][1])),
                           int(px(pts[i][0])),   int(py1(pts[i][1])))

        # Lines -- series 2 (right axis)
        for s in self.series2:
            if not s["data"]:
                continue
            p.setPen(QPen(QColor(s["color"]), 2))
            pts = s["data"]
            for i in range(1, len(pts)):
                p.drawLine(int(px(pts[i-1][0])), int(py2(pts[i-1][1])),
                           int(px(pts[i][0])),   int(py2(pts[i][1])))

        # Legend
        legend_x = ml + 4
        for s in self.series + self.series2:
            p.setPen(QPen(QColor(s["color"]), 2))
            p.drawLine(legend_x, mt + 8, legend_x + 16, mt + 8)
            p.setPen(QColor(TEXT3))
            p.setFont(small)
            p.drawText(legend_x + 20, mt + 2, 160, 14, Qt.AlignmentFlag.AlignLeft, s.get("name", ""))
            legend_x += 160

        p.end()


def _tension_profile_svg(tp, inputs, w_widget, h_widget):
    """Hand-drawn SVG widget matching the JSX's custom SVG tension profile chart.
    Returns a QLabel displaying the SVG."""
    if not tp or not tp.get("stations"):
        lbl = QLabel("Tension profile not available — recalculate to generate.")
        lbl.setStyleSheet(f"color:{TEXT2};font-size:11px;padding:20px;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return lbl

    stations  = tp["stations"]
    loaded    = [s for s in stations if s.get("leg") == "loaded"]
    empty     = [s for s in stations if s.get("leg") == "empty"]
    T_max     = tp.get("T_max_N")
    T_min     = tp.get("T_min_N")
    T_rated   = tp.get("belt_rated_N")
    margin    = tp.get("rating_margin")
    H_m       = float(inputs.get("H_m") or 25)

    W_draw, H_draw = 560, 200
    cl, cb_edge, cr_edge, ct = 52, H_draw - 24, W_draw - 18, 14
    cw = cr_edge - cl
    ch = cb_edge - ct

    if T_max is None or T_min is None:
        lbl = QLabel("Insufficient tension data.")
        lbl.setStyleSheet(f"color:{TEXT2};font-size:11px;padding:20px;")
        return lbl

    T_top   = (max(T_max, T_rated) if T_rated else T_max) * 1.06
    T_bot   = T_min * 0.88
    T_range = max(T_top - T_bot, 1)

    def px(pos):
        return cl + (pos / H_m) * cw

    def py(T):
        return cb_edge - ((T - T_bot) / T_range) * ch

    def grid_y_labels():
        lines = []
        for i in range(5):
            T_g = T_bot + (i / 4) * T_range
            y   = py(T_g)
            lines.append(
                f'<line x1="{cl}" y1="{y:.1f}" x2="{cr_edge}" y2="{y:.1f}" '
                f'stroke="#ffffff12" stroke-width="0.5" stroke-dasharray="3,3"/>'
                f'<text x="{cl-3}" y="{y+3:.1f}" font-size="8" fill="#64748b" text-anchor="end">'
                f'{T_g/1000:.1f}</text>'
            )
        return "\n".join(lines)

    def grid_x_labels():
        lines = []
        for i in range(5):
            pos = (i / 4) * H_m
            x   = px(pos)
            lines.append(
                f'<line x1="{x:.1f}" y1="{ct}" x2="{x:.1f}" y2="{cb_edge}" '
                f'stroke="#ffffff12" stroke-width="0.5" stroke-dasharray="3,3"/>'
                f'<text x="{x:.1f}" y="{cb_edge+13}" font-size="8" fill="#64748b" text-anchor="middle">'
                f'{pos:.0f}m</text>'
            )
        return "\n".join(lines)

    def points_to_path(pts, pos_key="position_m", t_key="tension_N"):
        if not pts:
            return ""
        d = " ".join(
            f"{'M' if i == 0 else 'L'}{px(s[pos_key]):.1f} {py(s[t_key]):.1f}"
            for i, s in enumerate(pts)
        )
        return d

    rated_line = ""
    if T_rated is not None:
        ry = py(T_rated)
        if ct <= ry <= cb_edge:
            rated_line = (
                f'<line x1="{cl}" y1="{ry:.1f}" x2="{cr_edge}" y2="{ry:.1f}" '
                f'stroke="{RED}" stroke-width="1.2" stroke-dasharray="6,3"/>'
                f'<text x="{cr_edge-2}" y="{ry-3:.1f}" font-size="8" fill="{RED}" text-anchor="end">'
                f'Rated {T_rated/1000:.1f}kN</text>'
            )

    peak_marker = ""
    if loaded:
        pk = loaded[-1]
        pkx, pky = px(pk["position_m"]), py(pk["tension_N"])
        peak_marker = (
            f'<circle cx="{pkx:.1f}" cy="{pky:.1f}" r="4" fill="{BLUE}" stroke="#f1f5f9" stroke-width="1"/>'
            f'<text x="{pkx-5:.1f}" y="{pky-8:.1f}" font-size="8" fill="{BLUE}" text-anchor="end">'
            f'{pk["tension_N"]/1000:.2f}kN</text>'
        )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W_draw}" height="{H_draw}" 
        style="background:{PANEL2};border-radius:6px;display:block;">
      {grid_y_labels()}
      {grid_x_labels()}
      <line x1="{cl}" y1="{ct}" x2="{cl}" y2="{cb_edge}" stroke="#64748b" stroke-width="1"/>
      <line x1="{cl}" y1="{cb_edge}" x2="{cr_edge}" y2="{cb_edge}" stroke="#64748b" stroke-width="1"/>
      <text x="{cl-30}" y="{ct+ch//2}" font-size="8" fill="#64748b" text-anchor="middle"
        transform="rotate(-90,{cl-30},{ct+ch//2})">Tension (kN)</text>
      <text x="{cl+cw//2}" y="{H_draw-3}" font-size="8" fill="#64748b" text-anchor="middle">
        Position from boot (m)</text>
      {rated_line}
      <path d="{points_to_path(loaded)}" fill="none" stroke="{BLUE}" stroke-width="2.5"/>
      <path d="{points_to_path(empty)}" fill="none" stroke="{TEAL}" stroke-width="1.8" stroke-dasharray="6,3"/>
      {peak_marker}
      <line x1="{cl+4}" y1="12" x2="{cl+20}" y2="12" stroke="{BLUE}" stroke-width="2.5"/>
      <text x="{cl+24}" y="16" font-size="8" fill="#94a3b8">Loaded (carry)</text>
      <line x1="{cl+100}" y1="12" x2="{cl+116}" y2="12" stroke="{TEAL}" stroke-width="1.8" stroke-dasharray="5,3"/>
      <text x="{cl+120}" y="16" font-size="8" fill="#94a3b8">Empty (return)</text>
    </svg>"""

    lbl = QLabel()
    lbl.setTextFormat(Qt.TextFormat.RichText)
    lbl.setText(svg)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setMinimumHeight(H_draw + 8)
    lbl.setWordWrap(False)
    return lbl


def _kpi_card(label, value, sub, color):
    box = QFrame()
    box.setStyleSheet(
        f"background:{PANEL2};border:1px solid {BORDER};border-radius:6px;"
    )
    layout = QVBoxLayout(box)
    layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(2)
    lbl = QLabel(label)
    lbl.setStyleSheet(f"color:{TEXT2};font-size:9.5px;")
    layout.addWidget(lbl)
    val = QLabel(value)
    val.setStyleSheet(f"color:{color};font-size:16px;font-weight:700;font-family:'JetBrains Mono',monospace;")
    layout.addWidget(val)
    if sub:
        sub_lbl = QLabel(sub)
        sub_lbl.setWordWrap(True)
        sub_lbl.setStyleSheet(f"color:{TEXT3};font-size:9px;")
        layout.addWidget(sub_lbl)
    return box


class ChartsPanel(QWidget):
    """Port of ChartsPanel.jsx. Five sub-tabs, same order.
    set_data(inputs, results) called by the parent Results tab widget."""

    TABS = [
        ("speed",   "Speed Sweep"),
        ("fill",    "Fill Analysis"),
        ("traj",    "Discharge Trajectory"),
        ("tension", "Tension Model"),
        ("profile", "Tension Profile"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:{PANEL};")
        self._inputs  = {}
        self._results = {}
        self._active  = "speed"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Sub-tab bar
        tab_bar = QFrame()
        tab_bar.setStyleSheet(f"background:{PANEL2};border-top:1px solid {BORDER};")
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

        # Content area
        self.content_scroll = QScrollArea()
        self.content_scroll.setWidgetResizable(True)
        self.content_scroll.setStyleSheet("QScrollArea{border:none;}")
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(12, 10, 12, 10)
        self.content_layout.setSpacing(8)
        self.content_scroll.setWidget(self.content_widget)
        outer.addWidget(self.content_scroll)

    def set_data(self, inputs, results):
        self._inputs  = inputs  or {}
        self._results = results or {}
        self._rebuild()

    def _switch_tab(self, tab_id):
        self._active = tab_id
        for tid, btn in self._tab_btns.items():
            btn.setChecked(tid == tab_id)
        self._rebuild()

    def _rebuild(self):
        def _clear(layout):
            while layout.count():
                item = layout.takeAt(0)
                w = item.widget() if item else None
                if w:
                    w.setParent(None)
                    w.deleteLater()
                elif item:
                    sub = item.layout()
                    if sub:
                        _clear(sub)
        _clear(self.content_layout)

        r = self._results
        inp = self._inputs
        tab = self._active

        title_map = {
            "speed":   "CAPACITY & POWER VS BELT SPEED (RPM SWEEP)",
            "fill":    "CAPACITY VS BUCKET FILL FACTOR",
            "traj":    "DISCHARGE TRAJECTORY (PROJECTILE — RELATIVE TO HEAD PULLEY CENTRE)",
            "tension": "BELT TENSION MODEL — CEMA 375 §4 DECOMPOSITION",
            "profile": "POSITION-RESOLVED BELT TENSION PROFILE — CEMA 375 §4.07",
        }
        title = QLabel(title_map.get(tab, ""))
        title.setStyleSheet(f"color:{TEXT2};font-size:10px;font-weight:700;letter-spacing:.06em;")
        self.content_layout.addWidget(title)

        if tab == "speed":
            self._build_speed_sweep()
        elif tab == "fill":
            self._build_fill_sweep()
        elif tab == "traj":
            self._build_trajectory()
        elif tab == "tension":
            self._build_tension_model()
        elif tab == "profile":
            self._build_tension_profile()

        self.content_layout.addStretch()

    def _build_speed_sweep(self):
        data = self._results.get("speed_sweep") or []
        if not data:
            self.content_layout.addWidget(QLabel("No speed sweep data — recalculate."))
            return
        chart = _InlineChart()
        chart.setMinimumHeight(220)
        cap_pts   = [(d["rpm"], d["capacity"]) for d in data if "rpm" in d and "capacity" in d]
        power_pts = [(d["rpm"], d["power"])    for d in data if "rpm" in d and "power"    in d]
        chart.set_data(
            series=[{"data": cap_pts,   "color": BLUE, "name": "Capacity (t/h)"}],
            series2=[{"data": power_pts, "color": RED,  "name": "Power (kW)"}],
            ref_x=[{"x": self._inputs.get("n_rpm"),  "color": AMBER,  "label": ""}],
            ref_y=[{"y": self._inputs.get("Q_req"),  "color": SUCCESS, "label": f"Req {self._inputs.get('Q_req')}t/h"}],
            x_label="RPM", dual_y=True,
        )
        self.content_layout.addWidget(chart)

    def _build_fill_sweep(self):
        data = self._results.get("fill_sweep") or []
        if not data:
            self.content_layout.addWidget(QLabel("No fill sweep data — recalculate."))
            return
        chart = _InlineChart()
        chart.setMinimumHeight(220)
        pts = [(d["fill"], d["capacity"]) for d in data if "fill" in d and "capacity" in d]
        chart.set_data(
            series=[{"data": pts, "color": TEAL, "name": "Capacity (t/h)", "area": True}],
            ref_x=[{"x": self._inputs.get("fill_pct"),  "color": AMBER,  "label": f"{self._inputs.get('fill_pct')}%"}],
            ref_y=[{"y": self._inputs.get("Q_req"),     "color": SUCCESS, "label": f"{self._inputs.get('Q_req')}t/h"}],
            x_label="Fill %",
        )
        self.content_layout.addWidget(chart)

    def _build_trajectory(self):
        traj = self._results.get("trajectory") or []
        if not traj:
            self.content_layout.addWidget(QLabel("No trajectory data — recalculate."))
            return
        chart = _InlineChart()
        chart.setMinimumHeight(220)
        pts = [(d["x"], d["y"]) for d in traj if "x" in d and "y" in d]
        upper_pts = [(d["x"], d["y"]) for d in (self._results.get("trajectory_upper") or []) if "x" in d and "y" in d]
        lower_pts = [(d["x"], d["y"]) for d in (self._results.get("trajectory_lower") or []) if "x" in d and "y" in d]

        series = [{"data": pts, "color": TEAL, "name": "Centreline Y (mm)"}]
        if upper_pts:
            series.append({"data": upper_pts, "color": f"{TEAL}88", "name": "Upper edge"})
        if lower_pts:
            series.append({"data": lower_pts, "color": f"{TEAL}55", "name": "Lower edge"})
        chart.set_data(series=series, x_label="Horizontal (mm)", y_label="Vertical (mm)")
        self.content_layout.addWidget(chart)

        r = self._results
        metrics = r.get("trajectory_metrics") or {}
        info_row = QHBoxLayout()
        info_row.setSpacing(20)
        info_row.addStretch()
        for label, val, color in [
            ("Release angle", f"{fmt(r.get('theta_rel'), 1)}° from vertical", TEXT),
            ("CR", fmt(r.get("cr"), 3), SUCCESS if (r.get("cr") or 0) > 1 else AMBER),
            ("Head pulley", f"Ø{self._inputs.get('D_mm','—')}mm", TEXT),
            ("Discharge type", metrics.get("discharge_type") or "—", PRIMARY),
        ]:
            pair = QHBoxLayout()
            pair.setSpacing(4)
            k = QLabel(label + ":")
            k.setStyleSheet(f"color:{TEXT2};font-size:10px;")
            pair.addWidget(k)
            v = QLabel(str(val))
            v.setStyleSheet(f"color:{color};font-size:10px;font-weight:700;font-family:'JetBrains Mono',monospace;")
            pair.addWidget(v)
            info_row.addLayout(pair)
        info_row.addStretch()
        self.content_layout.addLayout(info_row)

    def _build_tension_model(self):
        r = self._results
        inp = self._inputs
        T1 = r.get("T1")
        T2 = r.get("T2")
        T3 = r.get("T3")
        F_eff = r.get("F_eff")
        tension_ratio = (T1 / T2) if (T1 is not None and T2 is not None and T2 != 0) else None
        euler_ratio = r.get("euler_ratio")
        slip_safe   = r.get("slip_safe")

        grid = QGridLayout()
        grid.setSpacing(8)
        cards = [
            ("Effective Tension  F_eff",
             f"{fmt(F_eff/1000 if F_eff else None, 3)} kN" if F_eff else "—",
             "= T1 + T2  (total load at head shaft)", BLUE),
            ("Material Component  T1",
             f"{fmt(T1/1000 if T1 else None, 3)} kN" if T1 else "—",
             "G × g × H / v  (lifting material)", RED),
            ("Self-Weight Component  T2",
             f"{fmt(T2/1000 if T2 else None, 3)} kN" if T2 else "—",
             "(belt + bucket mass) × H × g", TEAL),
            ("Take-up Tension  T3  (slack side)",
             f"{fmt(T3/1000 if T3 else None, 3)} kN" if T3 else "—",
             f"F_eff × K = {inp.get('K_takeup','—')}  (slack-side minimum)", AMBER),
            ("Belt Tight Side  (T3 + F_eff)",
             f"{fmt((T3+F_eff)/1000 if (T3 and F_eff) else None, 3)} kN" if (T3 and F_eff) else "—",
             "actual belt tension on carrying run", TEXT),
            ("Euler Limit  e^(μθ)",
             fmt(euler_ratio, 3) if euler_ratio else "—",
             f"μ={inp.get('mu','—')}  θ={inp.get('wrap_deg','—')}°", TEXT3),
        ]
        for i, (label, value, sub, color) in enumerate(cards):
            grid.addWidget(_kpi_card(label, value, sub, color), i // 2, i % 2)
        self.content_layout.addLayout(grid)

        if slip_safe is not None and T3 and F_eff:
            ratio_actual = (T3 + F_eff) / T3
            slip_color = SUCCESS if slip_safe else DANGER
            slip_icon = "✓ No slip  (T3 adequate)" if slip_safe else "⚠ SLIP RISK — increase T3"
            slip_lbl = QLabel(
                f"Slip check: (T3 + F_eff) / T3 = {ratio_actual:.3f}  vs  "
                f"e^μθ = {fmt(euler_ratio, 3)}   "
                f"{slip_icon}"
            )
            slip_lbl.setStyleSheet(f"color:{slip_color};font-size:10px;padding:6px 0;")
            self.content_layout.addWidget(slip_lbl)

    def _build_tension_profile(self):
        r = self._results
        if r.get("is_chain"):
            lbl = QLabel(
                "Tension profile is not computed for chain elevators.\n"
                "Chain pull is a single lumped value — see Components tab."
            )
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color:{TEXT2};font-size:11px;padding:20px;")
            self.content_layout.addWidget(lbl)
            return

        tp = r.get("tension_profile")
        chart_widget = _tension_profile_svg(tp, self._inputs, self.width(), 200)
        self.content_layout.addWidget(chart_widget)

        if tp:
            T_max  = tp.get("T_max_N")
            T_min  = tp.get("T_min_N")
            T_rated = tp.get("belt_rated_N")
            margin = tp.get("rating_margin")
            m_ok   = margin is not None and margin >= 1.0
            m_warn = margin is not None and margin >= 0.9 and margin < 1.0
            m_color = SUCCESS if m_ok else (AMBER if m_warn else DANGER)

            grid = QGridLayout()
            grid.setSpacing(8)
            summary_cards = [
                ("Peak tension  (head)", f"{fmt(T_max/1000 if T_max else None, 2)} kN" if T_max else "—", None, BLUE),
                ("Min tension  (boot)",  f"{fmt(T_min/1000 if T_min else None, 2)} kN" if T_min else "—", None, TEAL),
                ("Belt rated",           f"{fmt(T_rated/1000 if T_rated else None, 2)} kN" if T_rated else "—", None, TEXT3),
                ("Rating margin",        fmt(margin, 3) if margin is not None else "—", None, m_color),
            ]
            for i, (label, value, sub, color) in enumerate(summary_cards):
                grid.addWidget(_kpi_card(label, value, sub, color), 0, i)
            self.content_layout.addLayout(grid)

            note_parts = []
            if tp.get("T_max_location"):
                note_parts.append(tp["T_max_location"])
            if tp.get("note"):
                note_parts.append(tp["note"])
            if margin is not None:
                if margin < 1.0:
                    note_parts.append("✗ Peak tension exceeds belt rating — upgrade belt or reduce load")
                elif margin < 1.25:
                    note_parts.append("⚠ Margin <1.25 — verify with belt manufacturer")
                else:
                    note_parts.append("✓ Adequate belt margin")
            if note_parts:
                note_lbl = QLabel("  ·  ".join(note_parts))
                note_lbl.setWordWrap(True)
                note_color = DANGER if (margin is not None and margin < 1.0) else \
                             AMBER  if (margin is not None and margin < 1.25) else SUCCESS
                note_lbl.setStyleSheet(f"color:{note_color if margin else TEXT2};font-size:10px;padding:4px 0;")
                self.content_layout.addWidget(note_lbl)