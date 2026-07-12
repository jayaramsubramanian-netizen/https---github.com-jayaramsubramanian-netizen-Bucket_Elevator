"""
components/elevation_bucket_cad.py — ISO A3 Engineering Drawing: Bucket Detail
═══════════════════════════════════════════════════════════════════════════
Fourth CAD drawing tab. Shows the selected bucket in three views on one sheet:
  LEFT:   front view — width (W) × height (H), with the real bolt hole
          pattern (count, spacing, diameter, edge distance) from the
          catalog's punch data
  RIGHT:  profile view — projection (P) × height (H), showing the
          characteristic scoop silhouette at the real front_angle_deg
  BOTTOM: bolt-hole detail callout — zoomed view of one bolt hole with
          its diameter and edge-distance dimensions called out clearly

Unlike the full-elevator elevations, buckets are small (~150-400mm) so
no broken-view logic is needed -- a single fixed scale is chosen to
comfortably fit both views side by side.

As with the other CAD tabs, the sheet template and all drawing
primitives are imported and reused verbatim from elevation_cad.py.
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


class BucketDetailCADDraw:
    """Draws the selected bucket in front + profile views plus a bolt-hole
    detail callout. Single fixed scale (no broken-view logic needed --
    buckets are small enough to always fit as one view)."""

    def __init__(self, scene, inputs, results, drawing_scale: Optional[int] = None):
        self.s = scene
        self._real_scene = scene
        self.inp, self.r = inputs or {}, results or {}
        self._user_scale = drawing_scale
        self._draw()

    def _draw(self):
        r = self.r
        bkt = r.get("bucket") or {}

        W_mm = float(bkt.get("W") or 305)
        H_mm = float(bkt.get("H") or 216)
        P_mm = float(bkt.get("P") or 203)
        front_angle_deg = float(bkt.get("front_angle_deg") or 45)

        # Fixed scale: pick the coarsest of a small set that keeps both
        # views comfortably within half the drawing width each
        avail_w_mm = DA_W_MM * 0.44
        avail_h_mm = DA_H_MM * 0.55   # leave room for the bolt detail callout below

        target = self._user_scale
        if not target:
            for k in [1, 2, 3, 4, 5]:
                if max(W_mm, P_mm) / k <= avail_w_mm and H_mm / k <= avail_h_mm:
                    target = k
                    break
            else:
                target = 5

        K = target
        r["_draw_scale"] = K
        r["_draw_segments"] = 1
        sc = lambda mm_val: mm_val / K

        add_text(self._real_scene, DA_X_MM+1, DA_Y_MM+DA_H_MM-4.5,
                 f"SCALE 1:{K}  |  LEFT: FRONT VIEW  ·  RIGHT: PROFILE VIEW  ·  BOTTOM: BOLT HOLE DETAIL",
                 1.8, color=C.TEXT_MUTED)
        catalog = bkt.get("catalog") or bkt.get("id") or "—"
        add_text(self._real_scene, DA_X_MM+1, DA_Y_MM+2,
                 f"BUCKET DETAIL — {catalog}  ({bkt.get('style','—')} style, {bkt.get('discharge_type','—')} discharge)",
                 2.0, bold=True)

        col_w = DA_W_MM * 0.46
        gap = DA_W_MM * 0.08
        col1_cx = DA_X_MM + col_w/2 + 2     # front view centre
        col2_cx = DA_X_MM + col_w + gap + col_w/2 - 2  # profile view centre
        views_cy = DA_Y_MM + DA_H_MM * 0.32

        # ── FRONT VIEW ────────────────────────────────────────────────
        front_rec = _ItemRecorder(self._real_scene)
        self.s = front_rec
        self._draw_front_view(col1_cx, views_cy, W_mm, H_mm, bkt, K, sc)
        self.s = self._real_scene
        _group_recorded_items(front_rec, self._real_scene,
                              "Bucket front view — drag to reposition, snaps to 5mm grid")

        # ── PROFILE VIEW ────────────────────────────────────────────────
        prof_rec = _ItemRecorder(self._real_scene)
        self.s = prof_rec
        self._draw_profile_view(col2_cx, views_cy, P_mm, H_mm, front_angle_deg, K, sc)
        self.s = self._real_scene
        _group_recorded_items(prof_rec, self._real_scene,
                              "Bucket profile view — drag to reposition, snaps to 5mm grid")

        # ── BOLT HOLE DETAIL CALLOUT ────────────────────────────────────
        detail_rec = _ItemRecorder(self._real_scene)
        self.s = detail_rec
        detail_cx = DA_X_MM + DA_W_MM * 0.5
        detail_cy = DA_Y_MM + DA_H_MM * 0.78
        self._draw_bolt_detail(detail_cx, detail_cy, bkt)
        self.s = self._real_scene
        _group_recorded_items(detail_rec, self._real_scene,
                              "Bolt hole detail — drag to reposition, snaps to 5mm grid")

        # ── Material / mass callout (fixed, not part of any group) ─────
        self._draw_material_note(bkt, r)

    # ── Front view: W x H with real bolt pattern ────────────────────────
    def _draw_front_view(self, cx, cy, W_mm, H_mm, bkt, K, sc):
        s = self.s
        w = sc(W_mm)
        h = sc(H_mm)

        centre_line(s, cx, cy - h/2 - 6, cx, cy + h/2 + 6)

        # Bucket body outline (simple box for front view -- AC/CD/KD
        # style buckets are essentially rectangular from the front)
        s.addRect(QRectF(m(cx - w/2), m(cy - h/2), m(w), m(h)),
                  pen_visible(0.5), QBrush(C.BUCKET))

        # Bolt hole pattern (real data): boltN holes, boltA_mm spacing,
        # boltB_mm edge distance from top, boltDia_mm hole diameter
        boltN = int(bkt.get("boltN") or 2)
        boltA_mm = float(bkt.get("boltA_mm") or 100)
        boltB_mm = float(bkt.get("boltB_mm") or 20)
        boltDia_mm = float(bkt.get("boltDia_mm") or 8)

        hole_r = max(0.4, sc(boltDia_mm) / 2)
        row_y = cy - h/2 + sc(boltB_mm)
        if boltN > 1:
            total_span = sc(boltA_mm) * (boltN - 1)
            start_x = cx - total_span / 2
            hole_xs = [start_x + i * sc(boltA_mm) for i in range(boltN)]
        else:
            hole_xs = [cx]

        for hx in hole_xs:
            s.addEllipse(QRectF(m(hx-hole_r), m(row_y-hole_r), m(hole_r*2), m(hole_r*2)),
                         pen_visible(0.35), QBrush(QColor("#ffffff")))
            centre_line(s, hx-hole_r*1.8, row_y, hx+hole_r*1.8, row_y)

        add_text(s, cx - w/2, cy - h/2 - 8, "FRONT VIEW", 2.3, bold=True)
        dim_h(s, cx-w/2, cy-h/2-4, cx+w/2, cy-h/2-4,
              f"W={W_mm:.0f}", offset_mm=3, ext_mm=1.2, size_mm=1.8)
        dim_v(s, cx-w/2-3, cy-h/2, cx-w/2-3, cy+h/2,
              f"H={H_mm:.0f}", offset_mm=4, ext_mm=1.2, size_mm=1.8)

        # Bolt pattern callout note
        add_text(s, cx - w/2, cy + h/2 + 3,
                 f"{boltN}× Ø{boltDia_mm:.1f} holes @ {boltA_mm:.1f} pitch, "
                 f"{boltB_mm:.1f} from top edge  ·  Punch: {bkt.get('punch','—')}",
                 1.6, color=C.TEXT_MUTED, max_w_mm=w+20)

    # ── Profile view: P x H showing the real scoop face angle ──────────
    def _draw_profile_view(self, cx, cy, P_mm, H_mm, front_angle_deg, K, sc):
        s = self.s
        p = sc(P_mm)
        h = sc(H_mm)

        centre_line(s, cx - p/2 - 4, cy, cx + p/2 + 8, cy)

        # Back wall (vertical, attaches to belt) at the left edge
        back_x = cx - p/2
        s.addLine(m(back_x), m(cy - h/2), m(back_x), m(cy + h/2), pen_visible(0.5))

        # Bottom (roughly horizontal, may be slightly curved for real
        # buckets but a straight line is an accurate simplification for
        # a detail-level drawing at this scale)
        bottom_y = cy + h/2

        # Front face: sloped at front_angle_deg from VERTICAL (0° would
        # be a vertical face; larger angles lean the face forward/back
        # depending on style). AC-style buckets use a steep face (~45-55°)
        # for clean centrifugal discharge.
        angle_rad = math.radians(front_angle_deg)
        front_top_x = back_x + p
        front_top_y = cy - h/2 + h * 0.15   # lip sits slightly below full back-wall height
        lean = h * math.tan(angle_rad) * 0.3  # visual lean amount, bounded

        path = QPainterPath()
        path.moveTo(m(back_x), m(cy - h/2))          # top of back wall
        path.lineTo(m(front_top_x), m(front_top_y))   # lip tip
        path.lineTo(m(front_top_x - lean*0.4), m(bottom_y))  # down to bottom-front
        path.lineTo(m(back_x), m(bottom_y))           # bottom-back
        path.closeSubpath()
        s.addPath(path, pen_visible(0.5), QBrush(C.BUCKET))

        add_text(s, cx - p/2, cy - h/2 - 8, "PROFILE VIEW", 2.3, bold=True)
        dim_h(s, back_x, cy-h/2-4, front_top_x, cy-h/2-4,
              f"P={P_mm:.0f}", offset_mm=3, ext_mm=1.2, size_mm=1.8)
        dim_v(s, back_x-3, cy-h/2, back_x-3, bottom_y,
              f"H={H_mm:.0f}", offset_mm=4, ext_mm=1.2, size_mm=1.8)

        # Angle callout with a small arc indicator
        add_text(s, front_top_x+1.5, front_top_y+2,
                 f"{front_angle_deg:.0f}° face", 1.8, bold=True, color=QColor("#884400"))

    # ── Bolt hole detail callout (zoomed) ────────────────────────────────
    def _draw_bolt_detail(self, cx, cy, bkt):
        s = self.s
        boltDia_mm = float(bkt.get("boltDia_mm") or 8)
        boltB_mm = float(bkt.get("boltB_mm") or 20)

        # Fixed legible detail scale (independent of the main view scale
        # so the hole is always readable regardless of bucket size)
        DETAIL_SCALE = 2.0   # 1mm real = 2mm drawn
        hole_r = boltDia_mm / 2 * DETAIL_SCALE
        edge_dist = boltB_mm * DETAIL_SCALE * 0.4  # visual edge distance (capped)

        # Detail boundary circle (ISO convention for a "detail view")
        boundary_r = hole_r + 8
        s.addEllipse(QRectF(m(cx-boundary_r), m(cy-boundary_r),
                             m(boundary_r*2), m(boundary_r*2)),
                     pen_visible(0.3), QBrush(Qt.BrushStyle.NoBrush))

        # Plate edge (top edge of the bucket back wall, shown straight)
        plate_y = cy - edge_dist
        s.addLine(m(cx-boundary_r*0.9), m(plate_y), m(cx+boundary_r*0.9), m(plate_y),
                  pen_visible(0.4))
        hatch_rect(s, cx-boundary_r*0.9, plate_y-3, boundary_r*1.8, 3)

        # Bolt hole
        s.addEllipse(QRectF(m(cx-hole_r), m(cy-hole_r), m(hole_r*2), m(hole_r*2)),
                     pen_visible(0.4), QBrush(QColor("#ffffff")))
        centre_line(s, cx-hole_r*1.6, cy, cx+hole_r*1.6, cy)
        centre_line(s, cx, cy-hole_r*1.6, cx, cy+hole_r*1.6)

        add_text(s, cx-boundary_r, cy-boundary_r-6, "BOLT HOLE DETAIL (NTS)", 2.0, bold=True)
        dim_h(s, cx-hole_r, cy+hole_r+3, cx+hole_r, cy+hole_r+3,
              f"Ø{boltDia_mm:.1f}", offset_mm=3, ext_mm=1.0, size_mm=1.7)
        dim_v(s, cx+hole_r+3, plate_y, cx+hole_r+3, cy,
              f"{boltB_mm:.1f} edge dist.", offset_mm=3, ext_mm=1.0, size_mm=1.6)

    # ── Material / mass note (fixed template annotation) ────────────────
    def _draw_material_note(self, bkt, r):
        s = self._real_scene
        checks = r.get("checks") or []
        mat_note = "—"
        for c in checks:
            if "bucket material" in c.get("msg", "").lower():
                mat_note = c["msg"].split("—")[0].replace("Bucket material", "").strip()
                break

        mass_kg = bkt.get("bucket_mass_kg")
        vol_l = bkt.get("V")
        add_text(s, DA_X_MM+1, DA_Y_MM+DA_H_MM-9,
                 f"Material: {mat_note}  ·  Mass: {mass_kg or '—'} kg  ·  "
                 f"Volume: {vol_l or '—'} L  ·  Recommended for: "
                 f"{', '.join(bkt.get('recommended_materials', [])[:4]) or '—'}",
                 1.7, color=C.TEXT_MUTED)


def build_bucket_scene(inputs: dict, results: dict,
                       sign_off: Optional[dict] = None,
                       drawing_scale: Optional[int] = None) -> QGraphicsScene:
    scene = QGraphicsScene()
    scene.setSceneRect(QRectF(m(-5), m(-5), m(A3_W_MM+10), m(A3_H_MM+10)))
    BucketDetailCADDraw(scene, inputs, results, drawing_scale)
    CADTemplate(scene, inputs, results, sign_off,
                view_title="BUCKET DETAIL")
    return scene


class BucketDetailCADWidget(QWidget):
    """Drop-in widget for the 'Bucket Detail' CAD tab."""

    SCALE_OPTIONS = [1, 2, 3, 4, 5, 8, 10]

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(6, 4, 6, 4)
        lbl = QLabel("Drawing scale:")
        lbl.setStyleSheet("color: #ddd; font-size: 11px;")
        toolbar.addWidget(lbl)
        self._scale_combo = QComboBox()
        self._scale_combo.setStyleSheet(
            "QComboBox { background: #f0f0eb; color: #1a1a1a; border: 1px solid #999; "
            "border-radius: 3px; padding: 3px 8px; font-size: 11px; }"
            "QComboBox::drop-down { border: none; }"
            "QComboBox QAbstractItemView { background: #f0f0eb; color: #1a1a1a; "
            "selection-background-color: #2266cc; selection-color: #ffffff; }"
        )
        self._scale_combo.addItem("Auto-fit (default)", None)
        for k in self.SCALE_OPTIONS:
            self._scale_combo.addItem(f"1:{k}", k)
        self._scale_combo.currentIndexChanged.connect(self._on_scale_changed)
        toolbar.addWidget(self._scale_combo)
        toolbar.addStretch()
        hint = QLabel("Left-drag a view to reposition (snaps to 5mm grid) · Middle-drag to pan · Wheel to zoom")
        hint.setStyleSheet("color: #888; font-size: 10px;")
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
        scene = build_bucket_scene(inputs, results, sign_off, chosen_scale)
        self._view.setScene(scene)
        self._view.fit_sheet()

    def fit(self):
        self._view.fit_sheet()