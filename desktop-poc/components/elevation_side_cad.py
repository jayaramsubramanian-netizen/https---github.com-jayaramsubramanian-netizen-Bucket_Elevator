"""
components/elevation_side_cad.py — ISO A3 Engineering Drawing: Side Elevation
═══════════════════════════════════════════════════════════════════════════
Second CAD drawing tab. Shows the elevator viewed from the side (90° from
the front Elevation view): casing DEPTH (driven by bucket projection) is
the primary horizontal dimension instead of casing width, support leg
brackets are shown instead of shaft+drive extensions on both sides, and
the drive assembly is shown end-on (compact) since it's viewed from the
side rather than face-on.

Everything else -- sheet template, zone markers, Design Input Parameters
table, Bill of Materials table, title block, scale selection with the
same 1:8 default and broken-view fallback, structural elements (casing
joints, inspection doors, platforms, ladder), and the SnapGroup
draggable/grid-snap behaviour -- is imported and reused verbatim from
elevation_cad.py rather than duplicated, since none of that logic is
actually view-specific.
"""

import math
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QGraphicsScene, QGraphicsView,
)
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QBrush, QColor, QPainterPath, QPainter

from .elevation_cad import (
    # coordinate system + geometry constants
    m, MM, A3_W_MM, A3_H_MM, DA_X_MM, DA_Y_MM, DA_W_MM, DA_H_MM,
    _choose_scale,
    # colours + pens
    C, pen_visible, pen_hidden, pen_centre, pen_dim, pen_border, pen_frame,
    no_pen,
    # draw helpers (all accept either a real QGraphicsScene or an
    # _ItemRecorder -- see SceneLike in elevation_cad.py)
    add_text, arrowhead, dim_h, dim_v, leader, centre_line, hatch_rect,
    table_rows,
    # movable-view infrastructure
    SnapGroup, _ItemRecorder, _group_recorded_items,
    # shared template (border/zones/params table/BOM table/title block) --
    # fully reused, only the view_title differs
    CADTemplate,
    # shared view widgets
    CADSchematicView,
)


class SideElevationCADDraw:
    """Draws the elevator's side elevation in the drawing area. Casing
    DEPTH (from bucket projection) is the primary horizontal dimension.
    Support leg brackets (diagonal bracing) replace the shaft+drive
    extensions used on the front elevation, since viewed from the side
    those sit end-on and are better represented as a compact block."""

    DEFAULT_SCALE = 8

    def __init__(self, scene, inputs, results, drawing_scale: Optional[int] = None):
        self.s = scene
        self._real_scene = scene
        self.inp, self.r = inputs or {}, results or {}
        self._user_scale = drawing_scale
        self._draw()

    def _select_scale_and_layout(self, H_total_mm: float, avail_h_mm: float):
        """Identical policy to ElevationCADDraw: user's explicit scale is
        always honoured exactly; Auto-fit mode chooses/widens on its own."""
        if self._user_scale:
            target = self._user_scale
            if H_total_mm / target <= avail_h_mm:
                return target, 1
            return target, 2
        target = self.DEFAULT_SCALE
        if H_total_mm / target <= avail_h_mm:
            return target, 1
        if H_total_mm / target <= avail_h_mm * 2:
            return target, 2
        widened = _choose_scale(H_total_mm, avail_h_mm * 2)
        return widened, 2

    def _draw(self):
        inp, r = self.inp, self.r
        bkt = r.get("bucket") or {}

        H_m       = float(inp.get("H_m") or 25)
        D_head_mm = float(inp.get("D_mm") or 500)
        D_boot_mm = float(inp.get("boot_pulley_D_mm") or 300)
        # Casing DEPTH driven by bucket projection (front-to-back), not
        # belt width -- this is what makes the side view genuinely
        # different from the front elevation view.
        CD_mm = float(bkt.get("P") or 178) + 120

        H_total_mm = H_m*1000 + D_head_mm/2 + D_boot_mm/2 + 80
        avail_h_mm = DA_H_MM - 22
        K, n_seg = self._select_scale_and_layout(H_total_mm, avail_h_mm)
        r["_draw_scale"] = K
        r["_draw_segments"] = n_seg
        sc = lambda mm: mm / K

        if n_seg == 1:
            self._draw_single(sc, K, H_m, D_head_mm, D_boot_mm, CD_mm, avail_h_mm)
        else:
            self._draw_broken(sc, K, H_m, D_head_mm, D_boot_mm, CD_mm, avail_h_mm)

    def _envelope_offsets(self, CAS_D, leg_w, leg_ext):
        """Side view envelope is narrower/more symmetric than the front
        view (no drive assembly sticking out one side) -- legs extend
        a small, roughly symmetric amount either side."""
        left_extent  = -(CAS_D/2 + leg_w + leg_ext*0.3)
        right_extent = +(CAS_D/2 + leg_w + leg_ext*0.3)
        return (left_extent + right_extent) / 2   # ~0, kept for consistency with front view's pattern

    # ── Single (unbroken) view ─────────────────────────────────────────
    def _draw_single(self, sc, K, H_m, D_head_mm, D_boot_mm, CD_mm, avail_h_mm):
        real_scene = self._real_scene
        r = self.r

        MARGIN_T = 12.0
        H_draw = sc(H_m * 1000)
        rH = sc(D_head_mm / 2)
        rB = sc(D_boot_mm / 2)

        CAS_D = max(24.0, min(sc(CD_mm + 100), DA_W_MM * 0.45))
        leg_w = max(2.0, sc(150))     # leg bracket width
        leg_ext = max(3.0, sc(300))   # leg diagonal extent

        midX = DA_X_MM + DA_W_MM / 2
        headCY = DA_Y_MM + MARGIN_T + rH
        bootCY = headCY + rH + H_draw + rB
        cx_l = midX - CAS_D / 2
        cx_r = midX + CAS_D / 2

        add_text(real_scene, DA_X_MM+1, DA_Y_MM+DA_H_MM-4.5,
                 f"SCALE 1:{K}  |  CASING DEPTH SHOWN (VIEWED FROM DRIVE SIDE)",
                 1.8, color=C.TEXT_MUTED)

        rec = _ItemRecorder(real_scene)
        self.s = rec

        self._draw_side_body(midX, headCY, bootCY, cx_l, cx_r, CAS_D,
                             H_draw, rH, rB, leg_w, leg_ext,
                             D_head_mm, D_boot_mm, K)
        self._draw_side_dimensions(cx_l, cx_r, headCY, bootCY, H_m, CD_mm)

        self.s = real_scene
        _group_recorded_items(rec, real_scene,
                              "Side elevation view — drag to reposition, snaps to 5mm grid")

    # ── Broken (2-segment) view ────────────────────────────────────────
    def _draw_broken(self, sc, K, H_m, D_head_mm, D_boot_mm, CD_mm, avail_h_mm):
        real_scene = self._real_scene
        r = self.r

        MARGIN_T = 12.0
        rH = sc(D_head_mm / 2)
        rB = sc(D_boot_mm / 2)
        leg_w = max(2.0, sc(150))
        leg_ext = max(3.0, sc(300))

        max_draw_h = avail_h_mm - MARGIN_T
        max_real_mm_per_seg = max_draw_h * K
        H_total_real_mm = H_m * 1000
        seg_real_mm = min(H_total_real_mm / 2, max_real_mm_per_seg - 40)
        seg_real_mm = max(seg_real_mm, 200)
        H_draw_seg = sc(seg_real_mm)

        total_covered_mm = 2 * seg_real_mm
        if total_covered_mm < H_total_real_mm - 1:
            missing_mm = H_total_real_mm - total_covered_mm
            add_text(real_scene, DA_X_MM+1, DA_Y_MM+5.5,
                     f"⚠ INCOMPLETE AT THIS SCALE: {missing_mm/1000:.1f}m of casing not shown "
                     f"(2 segments insufficient at 1:{K}) — increase scale or use Auto-fit",
                     1.8, bold=True, color=C.RED)

        col_w = DA_W_MM * 0.46
        gap = DA_W_MM * 0.08
        col1_cx = DA_X_MM + col_w/2 + 2
        col2_cx = DA_X_MM + col_w + gap + col_w/2 - 2
        CAS_D = max(20.0, min(sc(CD_mm + 100), col_w * 0.55))

        add_text(real_scene, DA_X_MM+1, DA_Y_MM+DA_H_MM-4.5,
                 f"SCALE 1:{K} (BROKEN VIEW — 2 SEGMENTS)  |  CASING DEPTH SHOWN",
                 1.7, color=C.TEXT_MUTED)
        add_text(real_scene, DA_X_MM+1, DA_Y_MM+2,
                 f"OVERALL H = {H_m:.0f} m  (shown broken — drag segments to align, snaps to 5mm grid)",
                 2.0, bold=True)

        # HEAD segment
        headCY = DA_Y_MM + MARGIN_T + rH
        head_break_y = headCY + rH + H_draw_seg
        cx_l1, cx_r1 = col1_cx - CAS_D/2, col1_cx + CAS_D/2

        head_rec = _ItemRecorder(real_scene)
        self.s = head_rec
        self._draw_side_body(col1_cx, headCY, head_break_y, cx_l1, cx_r1,
                             CAS_D, H_draw_seg, rH, rH, leg_w, leg_ext,
                             D_head_mm, D_boot_mm, K,
                             draw_head=True, draw_boot=False)
        self._break_line_side(cx_l1, cx_r1, head_break_y)
        add_text(self.s, col1_cx - CAS_D/2 - 2, head_break_y + 5,
                 "MATCH LINE A-A", 2.0, bold=True, color=C.RED)
        self.s = real_scene
        _group_recorded_items(head_rec, real_scene,
                              "Side elevation — head segment (drag to reposition)")

        # BOOT segment
        bootCY = DA_Y_MM + DA_H_MM - 18 - rB
        boot_break_y = bootCY - rB - H_draw_seg
        cx_l2, cx_r2 = col2_cx - CAS_D/2, col2_cx + CAS_D/2

        boot_rec = _ItemRecorder(real_scene)
        self.s = boot_rec
        self._draw_side_body(col2_cx, boot_break_y, bootCY, cx_l2, cx_r2,
                             CAS_D, H_draw_seg, rH, rB, leg_w, leg_ext,
                             D_head_mm, D_boot_mm, K,
                             draw_head=False, draw_boot=True)
        self._break_line_side(cx_l2, cx_r2, boot_break_y)
        add_text(self.s, col2_cx - CAS_D/2 - 2, boot_break_y - 6,
                 "MATCH LINE A-A", 2.0, bold=True, color=C.RED)
        self.s = real_scene
        _group_recorded_items(boot_rec, real_scene,
                              "Side elevation — boot segment (drag to reposition)")

    def _break_line_side(self, x_l, x_r, y):
        s = self.s
        pen = pen_visible(0.4)
        mid = (x_l + x_r) / 2
        zig = 2.5
        path = QPainterPath()
        path.moveTo(m(x_l), m(y))
        path.lineTo(m(mid - zig), m(y - zig))
        path.lineTo(m(mid + zig), m(y + zig))
        path.lineTo(m(x_r), m(y))
        s.addPath(path, pen, QBrush(Qt.BrushStyle.NoBrush))

    # ── Shared body drawing (casing, legs, pulleys, structural elements) ──
    def _draw_side_body(self, midX, headCY, bootCY, cx_l, cx_r, CAS_D,
                        H_draw, rH, rB, leg_w, leg_ext,
                        D_head_mm, D_boot_mm, K,
                        draw_head=True, draw_boot=True):
        s = self.s
        inp, r = self.inp, self.r

        centre_line(s, midX, headCY - rH - 6, midX, bootCY + rB + 6)
        s.addRect(QRectF(m(cx_l), m(headCY), m(CAS_D), m(H_draw)),
                  pen_visible(0.5), QBrush(C.CASING))
        hatch_rect(s, cx_l, headCY, 4, H_draw)
        hatch_rect(s, cx_r-4, headCY, 4, H_draw)

        # Structural elements pass -- fully reused from the front
        # elevation view (stiffener rings, inspection doors, platforms,
        # ladder, balloon callouts). Now a standalone function (not a
        # method), so it can be called normally with no self-type
        # mismatch -- this replaces the earlier unbound-method call that
        # Pylance correctly flagged as a type error.
        from .elevation_cad import draw_structural_elements
        draw_structural_elements(s, self.inp, self.r,
                                  cx_l, cx_r, headCY, bootCY, CAS_D, H_draw, K)

        # Support leg brackets (side view specific -- replaces the
        # shaft+drive extensions used on the front elevation, since here
        # the shaft/drive sit end-on and are better shown as a compact
        # diagonal brace pair, matching real installation practice)
        leg_pen = pen_visible(0.4)
        leg_brush = QBrush(QColor("#d8d8c8"))
        for side, x_edge in [(-1, cx_l), (1, cx_r)]:
            leg_x = x_edge - (leg_w if side < 0 else 0)
            s.addRect(QRectF(m(leg_x), m(headCY + H_draw*0.12),
                              m(leg_w), m(H_draw*0.82)),
                      leg_pen, leg_brush)
            # Diagonal brace
            brace_x1 = x_edge
            brace_x2 = x_edge + side * leg_ext
            s.addLine(m(brace_x1), m(headCY + H_draw*0.18),
                       m(brace_x2), m(headCY + H_draw*0.55), leg_pen)

        if draw_head:
            self._draw_side_head(midX, headCY, rH, CAS_D, D_head_mm)
        if draw_boot:
            self._draw_side_boot(midX, bootCY, rB, CAS_D, D_boot_mm)

    def _draw_side_head(self, midX, headCY, rH, CAS_D, D_head_mm):
        s, inp = self.s, self.inp
        # Pulley shown end-on: a rectangle spanning casing depth
        s.addRect(QRectF(m(midX - CAS_D/2 - 5), m(headCY - rH/3),
                          m(CAS_D + 10), m(rH/1.5)),
                  pen_visible(0.5), QBrush(C.PULLEY))
        # Lagging outline (hidden line, end-on)
        s.addRect(QRectF(m(midX - CAS_D/2 - 8), m(headCY - rH/3 - 2),
                          m(CAS_D + 16), m(rH/1.5 + 4)),
                  pen_hidden(), QBrush(Qt.BrushStyle.NoBrush))
        add_text(s, midX - 8, headCY - rH/3 - 5.5, "HEAD", 2.2, bold=True)

        # Compact end-on drive block (gearbox + motor viewed from the side
        # sit behind the head pulley, shown as one combined block)
        drv_w, drv_h = 16.0, 8.0
        s.addRect(QRectF(m(midX + CAS_D/2 + 6), m(headCY - drv_h/2),
                          m(drv_w), m(drv_h)),
                  pen_visible(0.35), QBrush(C.DRIVE_GB))
        add_text(s, midX + CAS_D/2 + 7, headCY - drv_h/2 + 1.5,
                 "DRIVE", 1.8, bold=True)

    def _draw_side_boot(self, midX, bootCY, rB, CAS_D, D_boot_mm):
        s, inp = self.s, self.inp
        s.addRect(QRectF(m(midX - CAS_D/2 - 4), m(bootCY - rB/4),
                          m(CAS_D + 8), m(rB/2)),
                  pen_visible(0.5), QBrush(C.PULLEY))
        add_text(s, midX - 10, bootCY + rB/2 + 3.0,
                 "BOOT / T/U", 2.2, bold=True)

    def _draw_side_dimensions(self, cx_l, cx_r, headCY, bootCY, H_m, CD_mm):
        s = self.s
        dim_v(s, cx_l-4, headCY, cx_l-4, bootCY,
              f"H = {H_m:.0f} m", offset_mm=10, ext_mm=2)
        dim_h(s, cx_l, headCY-6, cx_r, headCY-6,
              f"CD = {CD_mm:.0f} mm", offset_mm=6, ext_mm=2)


def build_side_scene(inputs: dict, results: dict,
                     sign_off: Optional[dict] = None,
                     drawing_scale: Optional[int] = None) -> QGraphicsScene:
    scene = QGraphicsScene()
    scene.setSceneRect(QRectF(m(-5), m(-5), m(A3_W_MM+10), m(A3_H_MM+10)))
    # Draw first so the scale is computed before the title block reads it
    # (same ordering fix as the front elevation view)
    SideElevationCADDraw(scene, inputs, results, drawing_scale)
    CADTemplate(scene, inputs, results, sign_off,
                view_title="BUCKET ELEVATOR — SIDE ELEVATION")
    return scene


class SideElevationCADWidget(QWidget):
    """Drop-in widget for the 'Side Elevation' CAD tab. Same scale
    selector + interaction model as the front Elevation CAD tab."""

    SCALE_OPTIONS = [1, 2, 5, 8, 10, 20, 25, 50, 100, 125, 200, 250, 500]

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
        self._scale_combo.addItem("Auto-fit (default 1:8)", None)
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
        scene = build_side_scene(inputs, results, sign_off, chosen_scale)
        self._view.setScene(scene)
        self._view.fit_sheet()

    def fit(self):
        self._view.fit_sheet()