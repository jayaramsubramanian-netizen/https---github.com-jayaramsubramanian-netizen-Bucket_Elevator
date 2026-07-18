"""
components/elevation_head_cad.py — ISO A3 Engineering Drawing: Head Detail
═══════════════════════════════════════════════════════════════════════════
Third CAD drawing tab. Shows the head section and discharge chute in TWO
sub-views side by side on one sheet:
  LEFT:  front elevation of the head (pulley face-on, chute, trajectory)
  RIGHT: side elevation of the head (pulley end-on, casing depth, chute,
         trajectory)

Both sub-views overlay the real computed discharge trajectory (the same
88-point arc used in the Trajectory chart tab), the real chute angle and
spout width from discharge_chute.performance / .geometry, and the real
hood/spoon sizing from discharge_chute.hood_spoon.

Bucket detail is intentionally NOT included here -- that will be its own
separate drawing per Jay's instruction.

As with elevation_side_cad.py, the sheet template (border, zones, Design
Input Parameters table, Bill of Materials table, title block) and all
drawing primitives (pens, fonts, SnapGroup, _ItemRecorder) are imported
and reused verbatim from elevation_cad.py rather than duplicated.
"""

import math
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QGraphicsScene, QGraphicsView,
)
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QBrush, QColor, QPainterPath, QPen

from .elevation_cad import (
    m, MM, A3_W_MM, A3_H_MM, DA_X_MM, DA_Y_MM, DA_W_MM, DA_H_MM,
    C, pen_visible, pen_hidden, pen_centre, pen_dim, no_pen,
    add_text, arrowhead, dim_h, dim_v, leader, centre_line, hatch_rect,
    SnapGroup, _ItemRecorder, _group_recorded_items,
    CADTemplate, CADSchematicView,
)


class HeadDetailCADDraw:
    """Draws the head-section + discharge-chute detail in two sub-views.
    Unlike the full-elevator elevations, this is always a single fixed
    scale chosen to make the head detail legible (no broken-view logic
    needed -- the head section itself is short)."""

    def __init__(self, scene, inputs, results, drawing_scale: Optional[int] = None):
        self.s = scene
        self._real_scene = scene
        self.inp, self.r = inputs or {}, results or {}
        self._user_scale = drawing_scale
        self._draw()

    def _draw(self):
        inp, r = self.inp, self.r
        D_head_mm = float(inp.get("D_mm") or 500)
        bkt = r.get("bucket") or {}
        CD_mm = float(bkt.get("P") or 178) + 120       # casing depth (side view)
        BW_mm = float(r.get("belt_w") or 350)           # casing width (front view)

        # Trajectory extent (real data) drives how much horizontal room
        # the chute + arc need beyond the pulley itself
        traj = r.get("trajectory") or []
        traj_x_max = max((p["x"] for p in traj), default=300.0)
        traj_y_min = min((p["y"] for p in traj), default=-300.0)

        # Fixed scale selection: pick the coarsest scale that keeps the
        # head+chute+trajectory envelope within HALF the drawing width
        # (since two sub-views sit side by side)
        envelope_h_mm = D_head_mm + abs(traj_y_min) + 150
        envelope_w_mm = D_head_mm + traj_x_max + 150
        avail_w_mm = DA_W_MM * 0.46
        avail_h_mm = DA_H_MM - 20

        target = self._user_scale or 4
        # Auto-widen only if not user-specified and it doesn't fit
        if not self._user_scale:
            from .elevation_cad import _choose_scale
            needed = max(envelope_h_mm / avail_h_mm, envelope_w_mm / avail_w_mm)
            for k in [4, 5, 8, 10, 20, 25, 50]:
                if envelope_h_mm / k <= avail_h_mm and envelope_w_mm / k <= avail_w_mm:
                    target = k
                    break
            else:
                target = 50

        K = target
        r["_draw_scale"] = K
        r["_draw_segments"] = 1
        sc = lambda mm_val: mm_val / K

        add_text(self._real_scene, DA_X_MM+1, DA_Y_MM+DA_H_MM-4.5,
                 f"SCALE 1:{K}  |  LEFT: FRONT VIEW OF HEAD  ·  RIGHT: SIDE VIEW OF HEAD",
                 1.8, color=C.TEXT_MUTED)
        add_text(self._real_scene, DA_X_MM+1, DA_Y_MM+2,
                 "HEAD SECTION & DISCHARGE CHUTE DETAIL — TRAJECTORY OVERLAID (BUCKET DETAIL: SEPARATE DRAWING)",
                 2.0, bold=True)

        col_w = DA_W_MM * 0.46
        gap = DA_W_MM * 0.08
        col1_cx = DA_X_MM + col_w/2 + 2   # front view centre
        col2_cx = DA_X_MM + col_w + gap + col_w/2 - 2  # side view centre
        pulley_cy = DA_Y_MM + DA_H_MM * 0.42

        # ── FRONT VIEW (left column) ────────────────────────────────
        front_rec = _ItemRecorder(self._real_scene)
        self.s = front_rec
        self._draw_front_view(col1_cx, pulley_cy, D_head_mm, BW_mm, K, sc)
        self.s = self._real_scene
        _group_recorded_items(front_rec, self._real_scene,
                              "Head front view — drag to reposition, snaps to 5mm grid")

        # ── SIDE VIEW (right column) ────────────────────────────────
        side_rec = _ItemRecorder(self._real_scene)
        self.s = side_rec
        self._draw_side_view(col2_cx, pulley_cy, D_head_mm, CD_mm, K, sc)
        self.s = self._real_scene
        _group_recorded_items(side_rec, self._real_scene,
                              "Head side view — drag to reposition, snaps to 5mm grid")

    # ── Trajectory overlay (shared by both sub-views) ──────────────────
    def _draw_trajectory_arc(self, origin_x, origin_y, sc, mirror_x=False):
        """Plot the real computed trajectory point cloud as a smooth
        path, anchored at (origin_x, origin_y) = the pulley centre in
        drawing mm. Physics convention is y-up; Qt scene is y-down, so
        y is negated. mirror_x flips the arc for the side view if needed."""
        s = self.s
        traj = self.r.get("trajectory") or []
        if len(traj) < 2:
            return

        path = QPainterPath()
        for i, pt in enumerate(traj):
            dx = sc(pt["x"]) * (-1 if mirror_x else 1)
            dy = -sc(pt["y"])   # flip: physics y-up -> Qt y-down
            x, y = origin_x + dx, origin_y + dy
            if i == 0:
                path.moveTo(m(x), m(y))
            else:
                path.lineTo(m(x), m(y))

        traj_pen = QPen(C.RED, m(0.35), Qt.PenStyle.SolidLine)
        s.addPath(path, traj_pen, QBrush(Qt.BrushStyle.NoBrush))

        # Arrowhead at the landing end showing direction of travel
        last = traj[-1]
        prev = traj[-2]
        lx = origin_x + sc(last["x"]) * (-1 if mirror_x else 1)
        ly = origin_y - sc(last["y"])
        ang = math.degrees(math.atan2(
            (-sc(last["y"])) - (-sc(prev["y"])),
            (sc(last["x"])*(-1 if mirror_x else 1)) - (sc(prev["x"])*(-1 if mirror_x else 1))
        ))
        arrowhead(s, lx, ly, ang, color=C.RED, size_mm=2.0)

        # Landing point label using real metrics
        tm = self.r.get("trajectory_metrics") or {}
        land_x = tm.get("land_x_m")
        if land_x is not None:
            add_text(s, lx+1.5, ly-2.0,
                     f"LAND: {land_x:.2f}m @ {tm.get('impact_velocity_mps',0):.1f}m/s",
                     1.6, color=C.RED)

    # ── FRONT view (pulley face-on) ─────────────────────────────────────
    def _draw_front_view(self, cx, cy, D_head_mm, BW_mm, K, sc):
        s, inp, r = self.s, self.inp, self.r
        rH = sc(D_head_mm / 2)

        centre_line(s, cx - rH - 8, cy, cx + rH + 8, cy)
        centre_line(s, cx, cy - rH - 8, cx, cy + rH + 8)

        # Pulley (visible)
        s.addEllipse(QRectF(m(cx-rH), m(cy-rH), m(rH*2), m(rH*2)),
                     pen_visible(0.5), QBrush(C.PULLEY))
        # Lagging (hidden line)
        lag = max(1.2, sc(15))
        s.addEllipse(QRectF(m(cx-rH-lag), m(cy-rH-lag), m((rH+lag)*2), m((rH+lag)*2)),
                     pen_hidden(), QBrush(Qt.BrushStyle.NoBrush))
        # Shaft + hub
        shaft_r = max(1.5, sc(float(r.get("d_mm") or 90)/2))
        s.addEllipse(QRectF(m(cx-shaft_r), m(cy-shaft_r), m(shaft_r*2), m(shaft_r*2)),
                     pen_hidden(), QBrush(QColor("#c8c8e0")))
        hub_r = max(0.6, shaft_r*0.3)
        s.addEllipse(QRectF(m(cx-hub_r), m(cy-hub_r), m(hub_r*2), m(hub_r*2)),
                     no_pen(), QBrush(C.VISIBLE))

        # Casing top (short stub, front view = width BW)
        cas_w = sc(BW_mm)
        cas_top_y = cy - rH - lag - 4
        s.addRect(QRectF(m(cx-cas_w/2), m(cas_top_y-10), m(cas_w), m(10)),
                  pen_visible(0.4), QBrush(C.CASING))
        hatch_rect(s, cx-cas_w/2, cas_top_y-10, 3, 10)
        hatch_rect(s, cx+cas_w/2-3, cas_top_y-10, 3, 10)

        # Discharge chute (front view: shown as a flared spout below/side
        # of the pulley, sized from real spout_width_mm)
        dc = r.get("discharge_chute") or {}
        geo = dc.get("geometry") or {}
        spout_w_mm = geo.get("spout_width_mm") or BW_mm * 0.7
        spout_w = sc(spout_w_mm)
        chute_y1 = cy + rH * 0.3
        chute_y2 = chute_y1 + sc(150)
        s.addLine(m(cx-spout_w/2), m(chute_y1), m(cx-spout_w/2*0.6), m(chute_y2), pen_visible(0.45))
        s.addLine(m(cx+spout_w/2), m(chute_y1), m(cx+spout_w/2*0.6), m(chute_y2), pen_visible(0.45))
        s.addLine(m(cx-spout_w/2*0.6), m(chute_y2), m(cx+spout_w/2*0.6), m(chute_y2), pen_visible(0.45))

        # Trajectory overlay (front view: material travels toward viewer/
        # away, so show as a simplified centred symbol + label rather than
        # the full arc, since the arc's real motion is in the depth axis
        # not visible face-on -- note this clearly rather than fake motion)
        add_text(s, cx - spout_w/2, chute_y2 + 3,
                 "Trajectory shown on SIDE VIEW →", 1.7, color=C.TEXT_MUTED)

        add_text(s, cx - rH - 6, cy - rH - lag - 14,
                 "FRONT VIEW — HEAD", 2.3, bold=True)
        dim_h(s, cx-rH, cy-rH-lag-6, cx+rH, cy-rH-lag-6,
              f"Ø{D_head_mm:.0f}", offset_mm=4, ext_mm=1.5)
        dim_h(s, cx-cas_w/2, cas_top_y-13, cx+cas_w/2, cas_top_y-13,
              f"BW={BW_mm:.0f}", offset_mm=3, ext_mm=1.5, size_mm=1.7)

    # ── SIDE view (pulley end-on, chute + trajectory visible) ───────────
    def _draw_side_view(self, cx, cy, D_head_mm, CD_mm, K, sc):
        s, inp, r = self.s, self.inp, self.r
        rH = sc(D_head_mm / 2)
        cas_d = sc(CD_mm)

        centre_line(s, cx - rH - 8, cy, cx + max(rH, sc(700)) + 8, cy)

        # Pulley end-on: rectangle spanning casing depth
        s.addRect(QRectF(m(cx - cas_d/2 - 4), m(cy - rH/3), m(cas_d + 8), m(rH/1.5)),
                  pen_visible(0.5), QBrush(C.PULLEY))
        lag = max(1.0, sc(15))
        s.addRect(QRectF(m(cx - cas_d/2 - 4 - lag), m(cy - rH/3 - lag),
                          m(cas_d + 8 + lag*2), m(rH/1.5 + lag*2)),
                  pen_hidden(), QBrush(Qt.BrushStyle.NoBrush))
        add_text(s, cx - cas_d/2, cy - rH/3 - lag - 4, "SIDE VIEW — HEAD", 2.3, bold=True)

        # Casing wall stub (side view shows depth)
        cas_top_y = cy - rH/3 - lag - 10
        s.addRect(QRectF(m(cx-cas_d/2), m(cas_top_y-8), m(cas_d), m(8)),
                  pen_visible(0.4), QBrush(C.CASING))

        # Discharge chute drawn at the REAL chute angle from vertical
        dc = r.get("discharge_chute") or {}
        perf = dc.get("performance") or {}
        chute_angle_deg = perf.get("chute_angle_deg", 45.0)
        chute_len = sc(250)
        chute_rad = math.radians(chute_angle_deg)
        release_x = cx + cas_d/2 * 0.3
        release_y = cy + rH * 0.2
        chute_x2 = release_x + chute_len * math.sin(chute_rad)
        chute_y2 = release_y + chute_len * math.cos(chute_rad)
        s.addLine(m(release_x), m(release_y), m(chute_x2), m(chute_y2), pen_visible(0.5))
        s.addLine(m(release_x+cas_d*0.15), m(release_y), m(chute_x2+cas_d*0.15), m(chute_y2), pen_visible(0.5))
        add_text(s, chute_x2+1.5, chute_y2-2,
                 f"Chute {chute_angle_deg:.0f}° (min {perf.get('min_angle_deg',0):.0f}°)",
                 1.7, color=QColor("#884400"))

        # ── Real trajectory arc overlay ─────────────────────────────
        self._draw_trajectory_arc(cx, cy, sc)

        dim_h(s, cx-cas_d/2, cy-rH/3-lag-14, cx+cas_d/2, cy-rH/3-lag-14,
              f"CD={CD_mm:.0f}", offset_mm=4, ext_mm=1.5, size_mm=1.7)

        # Hood/spoon note (real data, preliminary-sizing caveat honoured)
        hs = dc.get("hood_spoon") or {}
        if hs:
            add_text(s, cx - cas_d/2, cy + rH + 12,
                     f"Hood R={hs.get('hood_radius_m',0):.2f}m @ {hs.get('hood_angle_deg',0):.0f}°  ·  "
                     f"Spoon R={hs.get('spoon_radius_m',0):.2f}m @ {hs.get('spoon_angle_deg',0):.0f}°",
                     1.6, color=C.TEXT_MUTED)
            add_text(s, cx - cas_d/2, cy + rH + 15.5,
                     "Preliminary sizing — detailed CAD/DEM/CFD required for fabrication",
                     1.5, color=C.RED)


def build_head_scene(inputs: dict, results: dict,
                     sign_off: Optional[dict] = None,
                     drawing_scale: Optional[int] = None) -> QGraphicsScene:
    scene = QGraphicsScene()
    scene.setSceneRect(QRectF(m(-5), m(-5), m(A3_W_MM+10), m(A3_H_MM+10)))
    HeadDetailCADDraw(scene, inputs, results, drawing_scale)
    CADTemplate(scene, inputs, results, sign_off,
                view_title="HEAD SECTION & DISCHARGE CHUTE DETAIL")
    return scene


class HeadDetailCADWidget(QWidget):
    """Drop-in widget for the 'Head Detail' CAD tab."""

    SCALE_OPTIONS = [1, 2, 4, 5, 8, 10, 20, 25, 50]

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(6, 4, 6, 4)
        lbl = QLabel("Drawing scale:")
        lbl.setStyleSheet("color: #ddd; font-size: 13px;")
        toolbar.addWidget(lbl)
        self._scale_combo = QComboBox()
        self._scale_combo.setStyleSheet(
            "QComboBox { background: #f0f0eb; color: #1a1a1a; border: 1px solid #999; "
            "border-radius: 3px; padding: 3px 8px; font-size: 13px; }"
            "QComboBox::drop-down { border: none; }"
            "QComboBox QAbstractItemView { background: #f0f0eb; color: #1a1a1a; "
            "selection-background-color: #2266cc; selection-color: #ffffff; }"
        )
        self._scale_combo.addItem("Auto-fit (default 1:4)", None)
        for k in self.SCALE_OPTIONS:
            self._scale_combo.addItem(f"1:{k}", k)
        self._scale_combo.currentIndexChanged.connect(self._on_scale_changed)
        toolbar.addWidget(self._scale_combo)
        toolbar.addStretch()
        hint = QLabel("Left-drag a view to reposition (snaps to 5mm grid) · Middle-drag to pan · Wheel to zoom")
        hint.setStyleSheet("color: #888; font-size: 13px;")
        toolbar.addWidget(hint)
        toolbar_widget = QWidget()
        toolbar_widget.setLayout(toolbar)
        layout.addWidget(toolbar_widget)

        self._view = CADSchematicView()
        layout.addWidget(self._view)

        self._inputs: dict = {}
        self._results: dict = {}
        self._sign_off: Optional[dict] = None

    def _on_scale_changed(self):
        if self._inputs or self._results:
            self.set_data(self._inputs, self._results, self._sign_off)

    def set_data(self, inputs: dict, results: dict,
                 sign_off: Optional[dict] = None):
        self._inputs, self._results, self._sign_off = inputs, results, sign_off
        chosen_scale = self._scale_combo.currentData()
        scene = build_head_scene(inputs, results, sign_off, chosen_scale)
        self._view.setScene(scene)
        self._view.fit_sheet()

    def fit(self):
        self._view.fit_sheet()