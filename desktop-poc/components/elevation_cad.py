"""
components/elevation_cad.py — ISO A3 Engineering Drawing: Elevation View
═══════════════════════════════════════════════════════════════════════════
Replaces the QPainter-based elevation view with a proper QGraphicsScene
engineering drawing conforming to ISO A3 landscape, ISO 5457 (sheet layout),
ISO 128 (line conventions), and ISO 7200 (title block).

Coordinate system
─────────────────
1 scene unit = 1 physical mm.  The QGraphicsView transform maps scene
mm to screen pixels — at 96 dpi that is 3.779 px/mm.  All geometry is
specified in mm; the view handles zoom/pan.  y increases downward
(QGraphicsScene default).

Sheet layout (ISO A3 landscape 420×297mm)
─────────────────────────────────────────
  ┌─────────────────────────────────────────────────────────────────────┐
  │ zones (5mm strip, inside outer margin, outside frame line)          │
  │  ┌──────────────────────────────────────────────────────────────┐   │
  │  │ left notes panel    │  ELEVATION DRAWING  │  right panels    │   │
  │  │ 55mm wide           │  250mm wide         │  85mm wide       │   │
  │  │ Boot/TU table       │  (main schematic)   │  KPI notes       │   │
  │  │                     │                     │  217mm tall      │   │
  │  │                     │                     ├──────────────────│   │
  │  │                     │                     │  TITLE BLOCK     │   │
  │  │                     │                     │  60mm tall       │   │
  │  └──────────────────────────────────────────────────────────────┘   │
  └─────────────────────────────────────────────────────────────────────┘

ISO 128 line conventions
────────────────────────
  A – Continuous thick  0.50mm  Visible outlines, frame lines
  B – Dashed medium     0.25mm  Hidden lines  dash 2mm / gap 0.5mm
  C – Chain thin        0.35mm  Centre lines  10mm / 1mm / 2mm / 1mm
  D – Dimension         0.25mm  Dimension + projection lines, arrowheads
  E – Hatching          0.18mm  Section hatching, 45°, 2.5mm pitch
  Frame/border          0.70mm

Vertical scale is auto-selected from ISO 5455 standard scales to fit
the elevator height in the 217mm available drawing height.
Horizontal: casing shown at readable width (30-50mm); dimension callouts
carry the real belt-width figure. Note "Width NTS — see dimensions"
added to drawing.

New tab
───────
The main ElevationView container in elevation_view.py is updated to add
an "Eng. Drawing" tab that shows this view alongside the existing 5
QPainter schematic tabs.
"""

import math
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGraphicsScene, QGraphicsView,
    QGraphicsRectItem, QGraphicsLineItem, QGraphicsTextItem,
    QGraphicsEllipseItem, QGraphicsPathItem, QGraphicsPolygonItem,
    QGraphicsItem,
)
from PySide6.QtCore import Qt, QRectF, QPointF, QLineF
from PySide6.QtGui import (
    QPen, QBrush, QColor, QFont, QPainterPath, QPolygonF,
    QTransform, QPainter, QFontMetricsF,
)

# ─── Sheet constants (ISO A3 landscape, ISO 5457) ─────────────────────────────
A3_W = 420.0
A3_H = 297.0
FRAME_L  = 20.0    # binding margin
FRAME_R  = 10.0
FRAME_T  = 10.0
FRAME_B  = 10.0
ZONE_STRIP   = 5.0     # zone label strip width inside outer margin
RIGHT_W  = 85.0    # right column (KPI + title block)
LEFT_W   = 55.0    # left column (boot/TU notes)
TITLE_H  = 60.0    # title block height at bottom of right column

# Inner frame origin and size
FX = FRAME_L
FY = FRAME_T
FW = A3_W - FRAME_L - FRAME_R   # 390mm
FH = A3_H - FRAME_T - FRAME_B   # 277mm

# Drawing area (center pane)
DA_X = FX + LEFT_W              # 75mm
DA_Y = FY                       # 10mm
DA_W = FW - LEFT_W - RIGHT_W    # 250mm
DA_H = FH - TITLE_H             # 217mm  (full height minus title strip)

# Right column split
KPI_X = FX + FW - RIGHT_W       # 325mm
KPI_Y = FY                      # 10mm
KPI_W = RIGHT_W                 # 85mm
KPI_H = FH - TITLE_H            # 217mm

TB_X  = KPI_X                   # title block x
TB_Y  = FY + FH - TITLE_H       # 227mm  (bottom of frame - title height)
TB_W  = RIGHT_W                 # 85mm
TB_H  = TITLE_H                 # 60mm

# Left notes panel
LN_X = FX                       # 20mm
LN_Y = FY                       # 10mm
LN_W = LEFT_W                   # 55mm
LN_H = FH - TITLE_H             # 217mm

# ─── ISO 5455 standard scales ─────────────────────────────────────────────────
_ISO_SCALES = [1, 2, 5, 10, 20, 25, 50, 100, 125, 200, 250, 500, 1000]


def _choose_scale(real_height_mm: float, available_mm: float = DA_H - 10) -> int:
    """Return the smallest ISO 5455 scale K such that
    real_height_mm / K ≤ available_mm."""
    for k in _ISO_SCALES:
        if real_height_mm / k <= available_mm:
            return k
    return _ISO_SCALES[-1]


# ─── Colour palette (light CAD theme) ─────────────────────────────────────────
class _C:
    BG        = QColor("#fafaf7")   # cream sheet
    BORDER    = QColor("#1a1a1a")   # frame/border
    VISIBLE   = QColor("#1a1a1a")   # visible outlines
    HIDDEN    = QColor("#555555")   # hidden dashed
    CENTRE    = QColor("#0000aa")   # centre line (blue convention)
    DIM       = QColor("#444444")   # dimension lines
    HATCH     = QColor("#333333")   # hatching
    TEXT      = QColor("#1a1a1a")
    TEXT_MUTED= QColor("#555555")
    PANEL_BG  = QColor("#f0f0eb")
    TITLE_HDR = QColor("#d8d8d0")
    TABLE_ALT = QColor("#f5f5f0")
    RED_WARN  = QColor("#cc2200")
    AMBER     = QColor("#cc6600")
    GREEN     = QColor("#006600")


# ─── ISO 128 pens ─────────────────────────────────────────────────────────────
def _pen_visible(w=0.5):
    return QPen(_C.VISIBLE, w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap)

def _pen_hidden():
    p = QPen(_C.HIDDEN, 0.25, Qt.PenStyle.CustomDashLine)
    p.setDashPattern([8.0, 2.0])
    p.setCapStyle(Qt.PenCapStyle.FlatCap)
    return p

def _pen_centre():
    p = QPen(_C.CENTRE, 0.35, Qt.PenStyle.CustomDashLine)
    p.setDashPattern([28.0, 2.8, 5.6, 2.8])   # 10/1/2/1mm at scene units
    p.setCapStyle(Qt.PenCapStyle.FlatCap)
    return p

def _pen_dim():
    return QPen(_C.DIM, 0.25, Qt.PenStyle.SolidLine)

def _pen_hatch():
    return QPen(_C.HATCH, 0.18, Qt.PenStyle.SolidLine)

def _pen_border():
    return QPen(_C.BORDER, 0.70, Qt.PenStyle.SolidLine)

def _pen_frame():
    return QPen(_C.BORDER, 0.35, Qt.PenStyle.SolidLine)

def _no_pen():
    return QPen(Qt.PenStyle.NoPen)


# ─── Font helpers ─────────────────────────────────────────────────────────────
def _font(size_mm: float, bold: bool = False) -> QFont:
    """ISO text height in mm → QFont (approximate, for scene coords)."""
    pt = size_mm * 2.835   # mm → pt at 72dpi standard
    f = QFont("Arial Narrow", 0)
    f.setPointSizeF(pt)
    f.setBold(bold)
    return f


# ─── Geometry helpers ─────────────────────────────────────────────────────────
def _add_text(scene: QGraphicsScene, x: float, y: float, text: str,
              size_mm: float = 2.5, bold: bool = False,
              color: QColor = _C.TEXT,
              align: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft,
              parent: Optional[QGraphicsItem] = None) -> QGraphicsTextItem:
    item = QGraphicsTextItem(text, parent)
    item.setDefaultTextColor(color)
    item.setFont(_font(size_mm, bold))
    if not parent:
        scene.addItem(item)
    br = item.boundingRect()
    if align == Qt.AlignmentFlag.AlignCenter:
        item.setPos(x - br.width() / 2, y - br.height() / 2)
    elif align == Qt.AlignmentFlag.AlignRight:
        item.setPos(x - br.width(), y)
    else:
        item.setPos(x, y)
    return item


def _arrowhead(scene: QGraphicsScene, tip_x: float, tip_y: float,
               angle_deg: float, color: QColor = _C.DIM,
               size: float = 2.5) -> QGraphicsPolygonItem:
    """Filled arrowhead (ISO 128 type 1). angle_deg is the direction
    the arrow POINTS (0 = right, 90 = down)."""
    rad = math.radians(angle_deg)
    half = 0.4
    b1 = QPointF(tip_x - size * math.cos(rad - half),
                 tip_y - size * math.sin(rad - half))
    b2 = QPointF(tip_x - size * math.cos(rad + half),
                 tip_y - size * math.sin(rad + half))
    poly = QPolygonF([QPointF(tip_x, tip_y), b1, b2])
    item = scene.addPolygon(poly, _no_pen(), QBrush(color))
    return item


def _dim_horizontal(scene: QGraphicsScene,
                    x1: float, y1: float, x2: float, y2: float,
                    label: str, offset: float = 6.0,
                    ext: float = 2.5, size_mm: float = 2.5) -> None:
    """ISO 128 horizontal dimension line at y = min(y1,y2) - offset."""
    dim_y = min(y1, y2) - offset
    dp = _pen_dim()
    # Extension lines
    scene.addLine(x1, y1, x1, dim_y - ext, dp)
    scene.addLine(x2, y2, x2, dim_y - ext, dp)
    # Dimension line
    scene.addLine(x1, dim_y, x2, dim_y, dp)
    # Arrowheads
    _arrowhead(scene, x1, dim_y, 0 if x2 > x1 else 180)
    _arrowhead(scene, x2, dim_y, 180 if x2 > x1 else 0)
    # Label
    _add_text(scene, (x1 + x2) / 2, dim_y - size_mm * 1.2, label,
              size_mm, align=Qt.AlignmentFlag.AlignCenter)


def _dim_vertical(scene: QGraphicsScene,
                  x1: float, y1: float, x2: float, y2: float,
                  label: str, offset: float = 6.0,
                  ext: float = 2.5, size_mm: float = 2.5) -> None:
    """ISO 128 vertical dimension line at x = min(x1,x2) - offset."""
    dim_x = min(x1, x2) - offset
    dp = _pen_dim()
    scene.addLine(x1, y1, dim_x - ext, y1, dp)
    scene.addLine(x2, y2, dim_x - ext, y2, dp)
    scene.addLine(dim_x, y1, dim_x, y2, dp)
    _arrowhead(scene, dim_x, y1, 270 if y2 > y1 else 90)
    _arrowhead(scene, dim_x, y2, 90 if y2 > y1 else 270)
    mid_y = (y1 + y2) / 2
    t = _add_text(scene, dim_x - size_mm * 0.5, mid_y, label, size_mm)
    t.setTransformOriginPoint(t.boundingRect().center())
    t.setRotation(-90)
    t.setPos(dim_x - t.boundingRect().height() * 0.5 - ext * 0.5, mid_y + t.boundingRect().width() / 2)


def _centre_line(scene: QGraphicsScene,
                 x1: float, y1: float, x2: float, y2: float) -> QGraphicsLineItem:
    return scene.addLine(x1, y1, x2, y2, _pen_centre())


def _hatch_rect(scene: QGraphicsScene,
                x: float, y: float, w: float, h: float,
                angle_deg: float = 45, pitch: float = 2.5) -> None:
    """Fill a rectangle with ISO hatching lines clipped to the rect."""
    hp = _pen_hatch()
    rad = math.radians(angle_deg)
    diag = math.sqrt(w * w + h * h)
    cx, cy = x + w / 2, y + h / 2
    steps = int(diag / pitch) + 2
    for i in range(-steps, steps + 1):
        d = i * pitch
        dx = d * math.cos(rad + math.pi / 2)
        dy = d * math.sin(rad + math.pi / 2)
        lx1 = cx + dx - diag * math.cos(rad)
        ly1 = cy + dy - diag * math.sin(rad)
        lx2 = cx + dx + diag * math.cos(rad)
        ly2 = cy + dy + diag * math.sin(rad)
        # Clip to bounding box (simple AABB check on endpoints via QPainterPath)
        path = QPainterPath()
        path.addRect(QRectF(x, y, w, h))
        line_path = QPainterPath()
        line_path.moveTo(lx1, ly1)
        line_path.lineTo(lx2, ly2)
        clipped = path.intersected(line_path)
        if not clipped.isEmpty():
            for j in range(clipped.elementCount() - 1):
                e1 = clipped.elementAt(j)
                e2 = clipped.elementAt(j + 1)
                if e1.isMoveTo() or e2.isCurveTo():
                    continue
                scene.addLine(e1.x, e1.y, e2.x, e2.y, hp)


def _leader(scene: QGraphicsScene,
            tip_x: float, tip_y: float,
            text_x: float, text_y: float,
            label: str, size_mm: float = 2.5) -> None:
    """Leader line with arrowhead and horizontal text shelf."""
    dp = _pen_dim()
    scene.addLine(tip_x, tip_y, text_x, text_y, dp)
    shelf_len = 8.0
    scene.addLine(text_x, text_y, text_x + shelf_len, text_y, dp)
    angle = math.degrees(math.atan2(tip_y - text_y, tip_x - text_x))
    _arrowhead(scene, tip_x, tip_y, angle)
    _add_text(scene, text_x + shelf_len + 0.5, text_y - size_mm * 0.8, label, size_mm)


# ─── ISO A3 Drawing Template ───────────────────────────────────────────────────
class CADTemplate:
    """Draws the ISO A3 sheet, frame, zones, title block, KPI panel,
    and boot/takeup notes panel.  All static geometry is added here;
    the actual elevator drawing is added by ElevationCADView after."""

    def __init__(self, scene: QGraphicsScene,
                 inputs: dict, results: dict,
                 sign_off: Optional[dict] = None):
        self.s = scene
        self.inp = inputs or {}
        self.r   = results or {}
        self.so  = sign_off or {}
        self._build()

    def _build(self):
        self._draw_sheet_bg()
        self._draw_border_and_zones()
        self._draw_left_notes_panel()
        self._draw_kpi_panel()
        self._draw_title_block()

    # ── Sheet background ──────────────────────────────────────────────
    def _draw_sheet_bg(self):
        bg = self.s.addRect(QRectF(0, 0, A3_W, A3_H),
                             _no_pen(), QBrush(_C.BG))
        bg.setZValue(-10)

    # ── Border, outer margin, and zone markers ────────────────────────
    def _draw_border_and_zones(self):
        s = self.s
        # Outer sheet edge (thin)
        s.addRect(QRectF(0, 0, A3_W, A3_H), _pen_frame(), QBrush(Qt.BrushStyle.NoBrush))
        # Inner frame (thick)
        s.addRect(QRectF(FX, FY, FW, FH), _pen_border(), QBrush(Qt.BrushStyle.NoBrush))
        # Centring marks (ISO 5457 §5.3)
        for cx in [A3_W / 2]:
            s.addLine(cx, 0, cx, FY - 1, _pen_frame())
            s.addLine(cx, A3_H, cx, A3_H - FY + 1, _pen_frame())
        for cy in [A3_H / 2]:
            s.addLine(0, cy, FX - 1, cy, _pen_frame())
            s.addLine(A3_W, cy, A3_W - FX + 1, cy, _pen_frame())

        # Zone lines and labels (ISO 5457 §5.2)
        n_col, n_row = 8, 4
        col_letters = "ABCDEFGH"
        zone_pen = _pen_frame()
        zone_pen.setColor(_C.TEXT_MUTED)

        for i in range(n_col + 1):
            x = FX + i * FW / n_col
            s.addLine(x, 0,  x, FY,  zone_pen)
            s.addLine(x, A3_H - FY, x, A3_H, zone_pen)

        for i in range(n_row + 1):
            y = FY + i * FH / n_row
            s.addLine(0,  y, FX, y,  zone_pen)
            s.addLine(A3_W - FX, y, A3_W, y, zone_pen)

        for i in range(n_col):
            cx = FX + (i + 0.5) * FW / n_col
            _add_text(s, cx, 1.0, col_letters[i], 2.5,
                      color=_C.TEXT_MUTED, align=Qt.AlignmentFlag.AlignCenter)
            _add_text(s, cx, A3_H - FY + 1.0, col_letters[i], 2.5,
                      color=_C.TEXT_MUTED, align=Qt.AlignmentFlag.AlignCenter)

        for i in range(n_row):
            cy = FY + (i + 0.5) * FH / n_row
            _add_text(s, 1.0, cy, str(i + 1), 2.5,
                      color=_C.TEXT_MUTED, align=Qt.AlignmentFlag.AlignCenter)
            _add_text(s, A3_W - FX + 1.0, cy, str(i + 1), 2.5,
                      color=_C.TEXT_MUTED, align=Qt.AlignmentFlag.AlignCenter)

        # Panel separator lines
        # Left panel right edge
        s.addLine(FX + LEFT_W, FY, FX + LEFT_W, FY + FH, _pen_visible())
        # Right panel left edge
        s.addLine(KPI_X, FY, KPI_X, FY + FH, _pen_visible())
        # Title block top edge
        s.addLine(KPI_X, TB_Y, FX + FW, TB_Y, _pen_visible())

    # ── Left notes panel: boot/takeup ────────────────────────────────
    def _draw_left_notes_panel(self):
        s, r, inp = self.s, self.r, self.inp
        x0, y0, w, h = LN_X, LN_Y, LN_W, LN_H
        pad = 1.5

        # Panel header
        s.addRect(QRectF(x0, y0, w, 8), _pen_visible(), QBrush(_C.TITLE_HDR))
        _add_text(s, x0 + w / 2, y0 + 1.5, "BOOT & TAKE-UP",
                  2.5, bold=True, align=Qt.AlignmentFlag.AlignCenter)

        boot     = r.get("boot_pulley") or {}
        tg       = r.get("takeup")      or {}
        mnt      = r.get("maintenance") or {}
        kpis     = mnt.get("kpis")      or {}

        rows = [
            ("Boot pulley Ø",  f"{boot.get('boot_D_mm') or inp.get('boot_pulley_D_mm','—')} mm"),
            ("Boot shaft Ø",   f"{boot.get('shaft_d_mm') or '—'} mm"),
            ("Boot bearing L10", f"{r.get('L10_boot') or r.get('L10') or '—':.0f} h" if isinstance(r.get('L10_boot') or r.get('L10'), (int, float)) else "—"),
            ("Take-up type",   str(inp.get("takeup_type", "screw")).capitalize()),
            ("Take-up position", str(inp.get("takeup_position", "boot")).capitalize()),
            ("T/U travel (grav.)", f"{tg.get('travel_mm') or '—'} mm" if tg else "—"),
            ("T/U counterweight", f"{tg.get('W_counterweight_kg_gross') or '—'} kg" if tg else "—"),
            ("Boot outlet H",  f"{inp.get('boot_outlet_height_mm', 600)} mm"),
            ("Feed chute",     f"45° min · {inp.get('H_m', 25)}m shaft"),
            ("Casing width",   f"{r.get('belt_w') or '—'} mm"),
        ]

        y_row = y0 + 9.5
        row_h = (h - 10) / max(len(rows), 1)
        for i, (label, value) in enumerate(rows):
            row_y = y_row + i * row_h
            if i % 2 == 0:
                s.addRect(QRectF(x0, row_y, w, row_h),
                           _no_pen(), QBrush(_C.TABLE_ALT))
            s.addLine(x0, row_y + row_h, x0 + w, row_y + row_h, _pen_frame())
            _add_text(s, x0 + pad, row_y + 0.8, label, 2.0, color=_C.TEXT_MUTED)
            _add_text(s, x0 + pad, row_y + row_h * 0.45, value, 2.5, bold=True)

        # Panel border
        s.addRect(QRectF(x0, y0, w, h), _pen_visible(), QBrush(Qt.BrushStyle.NoBrush))

    # ── Right KPI panel ───────────────────────────────────────────────
    def _draw_kpi_panel(self):
        s, r, inp = self.s, self.r, self.inp
        x0, y0, w, h = KPI_X, KPI_Y, KPI_W, KPI_H
        pad = 1.5

        s.addRect(QRectF(x0, y0, w, 8), _pen_visible(), QBrush(_C.TITLE_HDR))
        _add_text(s, x0 + w / 2, y0 + 1.5, "PERFORMANCE",
                  2.5, bold=True, align=Qt.AlignmentFlag.AlignCenter)

        def _fmt(v, dp=1, unit=""):
            if v is None:
                return "—"
            try:
                return f"{float(v):.{dp}f}{' ' + unit if unit else ''}"
            except Exception:
                return str(v)

        Q_req = inp.get("Q_req")
        Q_ach = r.get("Q")
        q_color = _C.GREEN if (Q_ach and Q_req and Q_ach >= Q_req) else _C.RED_WARN

        cr = r.get("cr")
        cr_color = (_C.GREEN if cr and 1.0 <= cr <= 1.8
                    else _C.AMBER if cr and 0.85 <= cr < 1.0
                    else _C.RED_WARN)

        bkt = r.get("bucket") or {}
        kpis = [
            ("Required Q",       f"{Q_req or '—'} t/h",          _C.TEXT),
            ("Achieved Q",       _fmt(Q_ach, 1, "t/h"),           q_color),
            ("Belt speed",       _fmt(r.get("v"), 2, "m/s"),      _C.TEXT),
            ("CR",               _fmt(cr, 3),                     cr_color),
            ("Discharge θ",      _fmt(r.get("theta_rel"), 1, "°"), _C.TEXT),
            ("Motor power",      f"{r.get('motor_kw') or '—'} kW", _C.TEXT),
            ("Head pulley Ø",    f"{inp.get('D_mm') or '—'} mm", _C.TEXT),
            ("Head RPM",         f"{inp.get('n_rpm') or '—'} rpm", _C.TEXT),
            ("Head shaft Ø",     _fmt(r.get("d_mm"), 0, "mm"),    _C.TEXT),
            ("Bearing L10",      f"{r.get('L10') or '—':.0f} h" if isinstance(r.get("L10"), (int, float)) else "—",
                                 _C.GREEN if (r.get("L10") or 0) > 100000 else _C.AMBER),
            ("Bucket series",    bkt.get("id") or "—",            _C.TEXT),
            ("Bucket W×P×D",     f"{bkt.get('W','—')}×{bkt.get('P','—')}×{bkt.get('H','—')}mm", _C.TEXT),
            ("Spacing",          _fmt((r.get("spacing") or 0) * 1000, 0, "mm"), _C.TEXT),
            ("No. of buckets",   str(r.get("n_buckets") or "—"),  _C.TEXT),
            ("Fill factor",      f"{inp.get('fill_pct', 75)} %",  _C.TEXT),
            ("Material",         (r.get("mat") or {}).get("name") or inp.get("mat_id") or "—", _C.TEXT),
            ("Lift height",      f"{inp.get('H_m') or '—'} m",   _C.TEXT),
        ]

        y_row = y0 + 9.5
        row_h = (h - 10) / max(len(kpis), 1)
        for i, (label, value, color) in enumerate(kpis):
            ry = y_row + i * row_h
            if i % 2 == 0:
                s.addRect(QRectF(x0, ry, w, row_h), _no_pen(), QBrush(_C.TABLE_ALT))
            s.addLine(x0, ry + row_h, x0 + w, ry + row_h, _pen_frame())
            _add_text(s, x0 + pad, ry + 0.8, label, 2.0, color=_C.TEXT_MUTED)
            _add_text(s, x0 + pad, ry + row_h * 0.45, value, 2.5, bold=True, color=color)

        s.addRect(QRectF(x0, y0, w, h), _pen_visible(), QBrush(Qt.BrushStyle.NoBrush))

    # ── Title block (ISO 7200) ────────────────────────────────────────
    def _draw_title_block(self):
        s, r, inp = self.s, self.r, self.inp
        x0, y0, w, h = TB_X, TB_Y, TB_W, TB_H
        pad = 1.2

        try:
            from model_number import generate_model_number
            model_no = generate_model_number(inp, r)
        except Exception:
            model_no = "VM-??-?-???/???"

        s.addRect(QRectF(x0, y0, w, h), _pen_visible(), QBrush(_C.PANEL_BG))

        # Row 1: company + model number
        s.addRect(QRectF(x0, y0, w, 12), _pen_visible(), QBrush(_C.TITLE_HDR))
        _add_text(s, x0 + pad, y0 + pad, "JAYVEECONS", 3.0, bold=True)
        _add_text(s, x0 + pad, y0 + 6, "Engineering & Design", 2.0, color=_C.TEXT_MUTED)
        _add_text(s, x0 + w / 2 + pad, y0 + 1.5, model_no, 3.5, bold=True,
                  align=Qt.AlignmentFlag.AlignCenter)

        # Row 2: drawing title
        s.addLine(x0, y0 + 12, x0 + w, y0 + 12, _pen_visible())
        _add_text(s, x0 + pad, y0 + 12.5, "BUCKET ELEVATOR — ELEVATION VIEW", 2.5, bold=True)

        # Row 3: project/material
        s.addLine(x0, y0 + 20, x0 + w, y0 + 20, _pen_visible())
        mat_name = (r.get("mat") or {}).get("name") or inp.get("mat_id") or "—"
        _add_text(s, x0 + pad, y0 + 20.5, f"Material: {mat_name}", 2.0)
        _add_text(s, x0 + pad, y0 + 24, f"Lift: {inp.get('H_m','—')} m  Q: {inp.get('Q_req','—')} t/h", 2.0)

        # Row 4: scale / sheet / date
        s.addLine(x0, y0 + 30, x0 + w, y0 + 30, _pen_visible())
        s.addLine(x0 + w / 2, y0 + 30, x0 + w / 2, y0 + 45, _pen_visible())

        _add_text(s, x0 + pad, y0 + 30.5, "SCALE", 1.8, color=_C.TEXT_MUTED)
        _add_text(s, x0 + pad, y0 + 33.5, f"1:{r.get('_draw_scale', '—')}", 2.5, bold=True)
        _add_text(s, x0 + w / 2 + pad, y0 + 30.5, "SHEET", 1.8, color=_C.TEXT_MUTED)
        _add_text(s, x0 + w / 2 + pad, y0 + 33.5, "1 of 1", 2.5)

        # Row 5: sign-offs
        s.addLine(x0, y0 + 45, x0 + w, y0 + 45, _pen_visible())
        col3 = w / 3
        for i, role in enumerate(["DRAWN", "CHECKED", "APPROVED"]):
            cx = x0 + i * col3
            if i > 0:
                s.addLine(cx, y0 + 45, cx, y0 + h, _pen_visible())
            name = self.so.get(role.lower(), {}).get("display_name") or "—"
            date = self.so.get(role.lower(), {}).get("signed_at", "")[:10] or "—"
            _add_text(s, cx + pad, y0 + 45.5, role, 1.8, color=_C.TEXT_MUTED)
            _add_text(s, cx + pad, y0 + 48.5, name, 2.0, bold=True)
            _add_text(s, cx + pad, y0 + 53, date, 1.8, color=_C.TEXT_MUTED)

        # ISO standard note at very bottom
        from datetime import datetime
        _add_text(s, x0 + pad, y0 + h - 3,
                  f"VECTOMEC™  ISO A3  {datetime.now().strftime('%Y-%m-%d')}  THIRD ANGLE PROJ.",
                  1.8, color=_C.TEXT_MUTED)


# ─── Elevation drawing geometry ────────────────────────────────────────────────
class ElevationCADView:
    """Draws the full elevator elevation in the DA_X/DA_Y drawing area.
    All coordinates are in scene mm.  Scale is auto-selected so the
    elevator fits in the DA_H available height."""

    def __init__(self, scene: QGraphicsScene, inputs: dict, results: dict):
        self.s   = scene
        self.inp = inputs or {}
        self.r   = results or {}
        self._build()

    def _build(self):
        inp, r = self.inp, self.r

        # ── Auto-scale ────────────────────────────────────────────────
        H_m = float(inp.get("H_m") or 25)
        D_head_mm = float(inp.get("D_mm") or 500)
        D_boot_mm = float(inp.get("boot_pulley_D_mm") or 300)
        BW_mm   = float(r.get("belt_w") or 350)
        bkt     = r.get("bucket") or {}
        spacing_m = float(r.get("spacing") or 0.20)

        H_total_mm = H_m * 1000 + D_head_mm / 2 + D_boot_mm / 2 + 60
        K = _choose_scale(H_total_mm, DA_H - 15)
        # Store scale on results for title block
        r["_draw_scale"] = K

        def sc(mm): return mm / K    # scale: real mm → drawing mm

        # ── Drawing area origin ────────────────────────────────────────
        # Place elevator centred horizontally in the drawing area.
        # Use a normalized casing width (readable), not true scale.
        CASING_DRAW_W = min(DA_W * 0.5, max(30.0, sc(BW_mm + 200)))
        MARGIN_TOP    = 8.0    # space above head pulley
        MARGIN_BOTTOM = 12.0   # space below boot

        # Full elevator height in drawing mm
        H_draw = sc(H_m * 1000)
        rH = sc(D_head_mm / 2)
        rB = sc(D_boot_mm / 2)
        total_h = rH * 2 + H_draw + rB * 2

        # Origin: top of head pulley circle
        ox = DA_X + (DA_W - CASING_DRAW_W) / 2    # left edge of casing
        oy = DA_Y + MARGIN_TOP                       # top of drawing area + margin

        headCY = oy + rH                # head pulley centre y
        bootCY = headCY + rH + H_draw + rB   # boot pulley centre y
        midX   = ox + CASING_DRAW_W / 2       # horizontal centre

        s = self.s

        # ── NTS note ──────────────────────────────────────────────────
        _add_text(s, DA_X + 1, DA_Y + DA_H - 4,
                  f"VERTICAL SCALE 1:{K}  |  HORIZONTAL WIDTH NTS — SEE DIMENSION CALLOUTS",
                  2.0, color=_C.TEXT_MUTED)

        # ── Centre line (entire elevator height) ──────────────────────
        _centre_line(s, midX, headCY - rH - 5, midX, bootCY + rB + 5)

        # ── Casing ────────────────────────────────────────────────────
        cx_l = ox
        cx_r = ox + CASING_DRAW_W
        # Main casing outline (visible A)
        cas_rect = QRectF(cx_l, headCY, CASING_DRAW_W, H_draw)
        s.addRect(cas_rect, _pen_visible(0.5), QBrush(Qt.BrushStyle.NoBrush))
        # Light hatching on casing walls (indicate structural section)
        _hatch_rect(s, cx_l, headCY, 4, H_draw, angle_deg=45, pitch=2.5)
        _hatch_rect(s, cx_r - 4, headCY, 4, H_draw, angle_deg=45, pitch=2.5)

        # Belt strands (visible A, on carry and return side)
        belt_offset = CASING_DRAW_W * 0.18
        bltL = midX - belt_offset
        bltR = midX + belt_offset
        s.addLine(bltL, headCY, bltL, bootCY, _pen_visible(0.5))   # carry side
        s.addLine(bltR, headCY, bltR, bootCY, _pen_visible(0.35))  # return side

        # ── Buckets on carry side ──────────────────────────────────────
        bucket_pitch_draw = sc(spacing_m * 1000)
        bkt_W_draw = max(3.0, sc(float(bkt.get("P") or 178) * 0.8))
        bkt_H_draw = max(2.0, sc(float(bkt.get("H") or 216) * 0.6))
        n_visible = min(int(H_draw / bucket_pitch_draw) + 1, 20)
        for i in range(n_visible):
            by = headCY + i * bucket_pitch_draw + bucket_pitch_draw * 0.3
            if by + bkt_H_draw > bootCY - 2:
                break
            bpath = QPainterPath()
            bpath.moveTo(bltL, by)
            bpath.lineTo(bltL - bkt_W_draw, by)
            bpath.quadTo(bltL - bkt_W_draw - 1.5, by + bkt_H_draw * 0.5,
                          bltL - bkt_W_draw, by + bkt_H_draw)
            bpath.lineTo(bltL, by + bkt_H_draw)
            bpath.closeSubpath()
            s.addPath(bpath, _pen_visible(0.35), QBrush(QColor("#e8e8ff")))

        # ── Head pulley ────────────────────────────────────────────────
        # Lagging ring (outer, dashed for hidden surface)
        lagging_pen = _pen_hidden()
        lagging_pen.setColor(QColor("#333333"))
        s.addEllipse(midX-(rH+sc(15)), headCY-(rH+sc(15)), (rH+sc(15))*2, (rH+sc(15))*2,
                      lagging_pen, QBrush(Qt.BrushStyle.NoBrush))
        # Pulley body (visible, light fill)
        s.addEllipse(midX-rH, headCY-rH, rH*2, rH*2,
                      _pen_visible(0.5), QBrush(QColor("#d8d8f0")))
        # Shaft stubs (hidden line — inside pulley)
        shaft_r = max(2.0, sc(float(r.get("d_mm") or 90) / 2))
        s.addEllipse(midX-shaft_r, headCY-shaft_r, shaft_r*2, shaft_r*2,
                      _pen_hidden(), QBrush(QColor("#aaaacc")))
        # Hub marker
        s.addEllipse(midX-shaft_r*0.3, headCY-shaft_r*0.3, shaft_r*0.6, shaft_r*0.6,
                      _no_pen(), QBrush(_C.VISIBLE))
        # Shaft projections (visible, extend outside casing)
        shaft_ext = 10
        s.addLine(cx_l - shaft_ext, headCY - shaft_r, cx_l, headCY - shaft_r, _pen_visible(0.35))
        s.addLine(cx_l - shaft_ext, headCY + shaft_r, cx_l, headCY + shaft_r, _pen_visible(0.35))
        s.addLine(cx_r, headCY - shaft_r, cx_r + shaft_ext, headCY - shaft_r, _pen_visible(0.35))
        s.addLine(cx_r, headCY + shaft_r, cx_r + shaft_ext, headCY + shaft_r, _pen_visible(0.35))
        # Shaft end brackets
        brk_pen = _pen_visible(0.5)
        for sx in [cx_l - shaft_ext, cx_r + shaft_ext]:
            s.addLine(sx, headCY - shaft_r - 2, sx, headCY + shaft_r + 2, brk_pen)
        # Drive assembly (motor/gearbox boxes) on the right
        drive_x = cx_r + shaft_ext + 2
        gb_w, gb_h = 14, 10
        s.addRect(QRectF(drive_x, headCY - gb_h / 2, gb_w, gb_h),
                   _pen_visible(0.35), QBrush(QColor("#d0e8d0")))
        _add_text(s, drive_x + 1, headCY - 1, "GB", 2.0, bold=True)
        motor_x = drive_x + gb_w + 1
        s.addRect(QRectF(motor_x, headCY - gb_h / 2 - 1, gb_w + 2, gb_h + 2),
                   _pen_visible(0.35), QBrush(QColor("#c8e8c8")))
        _add_text(s, motor_x + 1, headCY - 1, "M", 2.0, bold=True)
        s.addLine(cx_r + shaft_ext, headCY, drive_x, headCY, _pen_visible(0.35))

        # HEAD SECTION label
        _add_text(s, midX, oy + 1.5, "HEAD SECTION", 2.5, bold=True,
                  align=Qt.AlignmentFlag.AlignCenter)

        # ── Boot pulley ────────────────────────────────────────────────
        s.addEllipse(midX-rB, bootCY-rB, rB*2, rB*2,
                      _pen_visible(0.5), QBrush(QColor("#d8d8f0")))
        shaft_rB = max(1.5, sc(float(inp.get("boot_pulley_D_mm") or 300) * 0.12))
        s.addEllipse(midX-shaft_rB, bootCY-shaft_rB, shaft_rB*2, shaft_rB*2,
                      _pen_hidden(), QBrush(QColor("#aaaacc")))
        # Take-up indicator
        s.addRect(QRectF(midX - 4, bootCY + rB + 1, 8, 5),
                   _pen_visible(0.35), QBrush(QColor("#e8e8d8")))
        _add_text(s, midX, bootCY + rB + 1.5, "T/U", 1.8,
                  align=Qt.AlignmentFlag.AlignCenter)
        # Feed arrow
        feed_y = bootCY + rB * 0.3
        s.addLine(cx_l - 18, feed_y, cx_l - 1, feed_y, _pen_visible(0.5))
        _arrowhead(s, cx_l - 1, feed_y, 0)
        _add_text(s, cx_l - 19, feed_y - 3.5, "FEED", 2.0, bold=True,
                  color=QColor("#884400"))
        _add_text(s, cx_l - 19, feed_y + 0.5, f"{inp.get('Q_req','—')} t/h", 2.0)

        # Discharge chute (from head)
        theta_deg = float(r.get("theta_rel") or 10)
        theta_rad = math.radians(theta_deg)
        chute_len = 20.0
        chute_x2 = midX + rH * math.sin(theta_rad) * 2.5 + chute_len * math.sin(theta_rad)
        chute_y2 = headCY - rH * math.cos(theta_rad) * 1.5 - chute_len * math.cos(theta_rad)
        s.addLine(midX + rH * 0.6, headCY - rH * 0.5, chute_x2, chute_y2,
                   _pen_visible(0.5))
        s.addLine(midX + rH * 0.9, headCY - rH * 0.3, chute_x2 + 3, chute_y2 + 3,
                   _pen_visible(0.5))
        _add_text(s, chute_x2 + 1, chute_y2 - 3, "DISCHARGE", 2.0, bold=True,
                  color=QColor("#884400"))

        # ── Dimensions ────────────────────────────────────────────────
        # Overall height H
        _dim_vertical(s, cx_l - 8, headCY, cx_l - 8, bootCY,
                       f"H = {H_m:.0f} m", offset=10, ext=2)
        # Head pulley D
        _dim_horizontal(s, midX - rH, headCY - rH - 4,
                         midX + rH, headCY - rH - 4,
                         f"Ø{D_head_mm:.0f}", offset=6)
        # Belt width callout (NTS, labelled)
        _leader(s, cx_l + 2, headCY + H_draw * 0.35,
                cx_l - 18, headCY + H_draw * 0.35,
                f"BW = {BW_mm:.0f} mm (NTS)", 2.0)
        # Spacing callout
        _leader(s, bltL - bkt_W_draw * 0.5,
                headCY + bucket_pitch_draw * 0.5 + 3,
                bltL - bkt_W_draw - 5,
                headCY + bucket_pitch_draw * 0.5,
                f"SPC {round(spacing_m * 1000)} mm", 2.0)

        # ── Boot section label ────────────────────────────────────────
        _add_text(s, midX, bootCY + rB + 10, "BOOT / TAKE-UP",
                  2.5, bold=True, align=Qt.AlignmentFlag.AlignCenter)
        _add_text(s, midX, bootCY + rB + 14.5,
                  f"Ø{inp.get('boot_pulley_D_mm') or '—'} mm · {(inp.get('takeup_type') or 'Screw').capitalize()}",
                  2.0, align=Qt.AlignmentFlag.AlignCenter)


# ─── QGraphicsScene + View assembly ───────────────────────────────────────────
def build_elevation_cad_scene(inputs: dict, results: dict,
                               sign_off: Optional[dict] = None) -> QGraphicsScene:
    """Build the full ISO A3 engineering drawing scene for the elevation view.
    Call this on a new calculation; replace the scene on the CADSchematicView."""
    scene = QGraphicsScene()
    scene.setSceneRect(QRectF(-5, -5, A3_W + 10, A3_H + 10))
    CADTemplate(scene, inputs, results, sign_off)
    ElevationCADView(scene, inputs, results)
    return scene


class CADSchematicView(QGraphicsView):
    """QGraphicsView configured for CAD drawing display.
    - Light cream background matching the drawing sheet
    - Smooth anti-aliased rendering
    - Mouse wheel zoom (centred under cursor)
    - Middle-click or right-click drag to pan
    - Fits the A3 sheet on first show
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing |
            QPainter.RenderHint.TextAntialiasing |
            QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setBackgroundBrush(QBrush(QColor("#888888")))  # grey surround
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 0.87
        self.scale(factor, factor)

    def fit_sheet(self):
        if self.scene():
            self.fitInView(QRectF(-2, -2, A3_W + 4, A3_H + 4),
                           Qt.AspectRatioMode.KeepAspectRatio)

    def set_drawing(self, inputs: dict, results: dict,
                    sign_off: Optional[dict] = None):
        """Replace the scene with a freshly built drawing."""
        scene = build_elevation_cad_scene(inputs, results, sign_off)
        self.setScene(scene)
        self.fit_sheet()


class ElevationCADWidget(QWidget):
    """Drop-in widget for the Elevation 'Eng. Drawing' tab."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._view = CADSchematicView()
        layout.addWidget(self._view)

    def set_data(self, inputs: dict, results: dict,
                 sign_off: Optional[dict] = None):
        self._view.set_drawing(inputs, results, sign_off)

    def fit(self):
        self._view.fit_sheet()