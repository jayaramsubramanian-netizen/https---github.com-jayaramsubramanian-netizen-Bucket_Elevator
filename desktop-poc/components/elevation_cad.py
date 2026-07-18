"""
components/elevation_cad.py — ISO A3 Engineering Drawing: Elevation View
═══════════════════════════════════════════════════════════════════════════
QGraphicsScene-based ISO A3 engineering drawing. All scene coordinates
are in PIXELS (1 scene unit = 1px at 96 dpi). Physical mm values are
converted using MM = 3.779528 px/mm throughout.

Layout: ISO A3 landscape 420×297mm, ISO 5457 frame, zone markers,
left notes panel (boot/TU), right KPI panel, ISO 7200 title block,
full elevation drawing in the centre pane.

Line conventions: ISO 128
  Visible  0.5mm = 1.9px  solid black
  Hidden   0.25mm = 0.9px dashed
  Centre   0.35mm = 1.3px chain-dash (blue)
  Dim      0.25mm = 0.9px solid grey
  Hatch    0.18mm = 0.7px solid
  Frame    0.70mm = 2.6px border
"""

import math
from typing import Optional, Union

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QGraphicsScene, QGraphicsView,
    QGraphicsRectItem, QGraphicsLineItem, QGraphicsTextItem,
    QGraphicsPathItem, QGraphicsPolygonItem,
    QGraphicsItemGroup, QGraphicsItem,
)
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (
    QPen, QBrush, QColor, QFont, QPainterPath, QPolygonF,
    QPainter, QFontMetricsF,
)

# Type alias for the 'scene' parameter every CAD draw helper accepts:
# always either the real QGraphicsScene, or an _ItemRecorder proxy that
# forwards to one while recording items (see _ItemRecorder below). Using
# a plain Union instead of a hand-written Protocol -- Pyright checks a
# Union call-site against each member's OWN real signature directly, with
# no structural/return-type matching fragility (a Protocol with loosely-
# typed stub methods can end up rejecting the real QGraphicsScene itself,
# which is what happened here: QGraphicsScene.addRect() returns a real
# QGraphicsRectItem, not None, so it failed to satisfy a Protocol method
# stub that Pyright inferred as returning None).
SceneLike = Union[QGraphicsScene, "_ItemRecorder"]

# ── Coordinate system ─────────────────────────────────────────────────────────
MM = 3.779528    # px per mm at 96 dpi (1 scene unit = 1px)

def m(mm: float) -> float:
    """Convert mm to scene pixel units."""
    return mm * MM

# ── Sheet constants (in mm, converted via m() when used) ─────────────────────
A3_W_MM, A3_H_MM = 420.0, 297.0
FRAME_L_MM  = 20.0
FRAME_R_MM  = 10.0
FRAME_T_MM  = 10.0
FRAME_B_MM  = 10.0

RIGHT_W_MM  = 85.0    # right column: KPI + title block
LEFT_W_MM   = 55.0    # left column: boot/TU notes
TITLE_H_MM  = 60.0    # title block height (bottom of right column)

FW_MM = A3_W_MM - FRAME_L_MM - FRAME_R_MM   # 390
FH_MM = A3_H_MM - FRAME_T_MM - FRAME_B_MM   # 277

DA_X_MM = FRAME_L_MM + LEFT_W_MM             # drawing area left edge: 75
DA_Y_MM = FRAME_T_MM                          # drawing area top: 10
DA_W_MM = FW_MM - LEFT_W_MM - RIGHT_W_MM     # 250
DA_H_MM = FH_MM - TITLE_H_MM                 # 217 (above title block)

KPI_X_MM = FRAME_L_MM + FW_MM - RIGHT_W_MM   # 325
KPI_Y_MM = FRAME_T_MM                         # 10
KPI_H_MM = FH_MM - TITLE_H_MM                # 217

TB_X_MM  = KPI_X_MM                          # title block
TB_Y_MM  = FRAME_T_MM + FH_MM - TITLE_H_MM  # 227
TB_W_MM  = RIGHT_W_MM                        # 85
TB_H_MM  = TITLE_H_MM                        # 60

LN_X_MM = FRAME_L_MM                         # 20
LN_Y_MM = FRAME_T_MM                         # 10
LN_W_MM = LEFT_W_MM                          # 55
LN_H_MM = FH_MM - TITLE_H_MM               # 217

# ── ISO 5455 scales ───────────────────────────────────────────────────────────
_ISO_SCALES = [1,2,5,10,20,25,50,100,125,200,250,500,1000]

def _choose_scale(real_mm: float, avail_mm: float = DA_H_MM - 15) -> int:
    for k in _ISO_SCALES:
        if real_mm / k <= avail_mm:
            return k
    return _ISO_SCALES[-1]

# ── Colours ───────────────────────────────────────────────────────────────────
class C:
    BG         = QColor("#fafaf7")
    BORDER     = QColor("#1a1a1a")
    VISIBLE    = QColor("#1a1a1a")
    HIDDEN     = QColor("#666666")
    CENTRE     = QColor("#0000aa")
    DIM        = QColor("#555555")
    HATCH      = QColor("#444444")
    TEXT       = QColor("#1a1a1a")
    TEXT_MUTED = QColor("#666666")
    PANEL_BG   = QColor("#f0f0eb")
    HDR_BG     = QColor("#d8d8d0")
    ROW_ALT    = QColor("#f5f5f0")
    ROW_SEP    = QColor("#cccccc")
    GREEN      = QColor("#005500")
    AMBER      = QColor("#885500")
    RED        = QColor("#880000")
    PULLEY     = QColor("#d0d0e8")
    CASING     = QColor("#e8efe8")
    DRIVE_GB   = QColor("#d0e8d0")
    DRIVE_M    = QColor("#c8e8c8")
    BUCKET     = QColor("#e0e0f8")

# ── ISO 128 pens (widths in mm, converted to px) ─────────────────────────────
def pen_visible(w_mm=0.5):
    return QPen(C.VISIBLE, m(w_mm), Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.FlatCap, Qt.PenJoinStyle.MiterJoin)

def pen_hidden():
    p = QPen(C.HIDDEN, m(0.25), Qt.PenStyle.CustomDashLine)
    p.setDashPattern([m(2.0), m(0.8)])
    return p

def pen_centre():
    p = QPen(C.CENTRE, m(0.35), Qt.PenStyle.CustomDashLine)
    p.setDashPattern([m(10), m(1.5), m(2.5), m(1.5)])
    return p

def pen_dim():
    return QPen(C.DIM, m(0.25), Qt.PenStyle.SolidLine)

def pen_hatch():
    return QPen(C.HATCH, m(0.18), Qt.PenStyle.SolidLine)

def pen_border():
    return QPen(C.BORDER, m(0.7), Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.SquareCap, Qt.PenJoinStyle.MiterJoin)

def pen_frame():
    return QPen(C.BORDER, m(0.35), Qt.PenStyle.SolidLine)

def no_pen():
    return QPen(Qt.PenStyle.NoPen)

# ── Font helpers ──────────────────────────────────────────────────────────────
def font(size_mm: float, bold: bool = False) -> QFont:
    """mm text height → QFont (72pt = 1 inch = 25.4mm)."""
    f = QFont("Arial Narrow", 0)
    f.setPointSizeF(size_mm * 72.0 / 25.4)
    f.setBold(bold)
    return f

def font_px_height(size_mm: float, bold: bool = False) -> float:
    """Return actual ascent height of font in scene px using QFontMetricsF."""
    fm = QFontMetricsF(font(size_mm, bold))
    return fm.ascent()

# ── Text helper ───────────────────────────────────────────────────────────────
def add_text(scene: SceneLike, x_mm: float, y_mm: float, text: str,
             size_mm: float = 2.5, bold: bool = False,
             color: Optional[QColor] = None, max_w_mm: float = 0,
             align_right: bool = False) -> QGraphicsTextItem:
    """Add a text item. (x_mm, y_mm) = TOP-LEFT of the text in mm.
    max_w_mm enables word-wrap within the column."""
    color = color or C.TEXT
    t = QGraphicsTextItem(text)
    t.setDefaultTextColor(color)
    t.setFont(font(size_mm, bold))
    t.document().setDocumentMargin(0)    # remove Qt's internal padding
    if max_w_mm > 0:
        t.setTextWidth(m(max_w_mm))
    if align_right:
        from PySide6.QtCore import Qt as _Qt
        t.setTextWidth(m(max_w_mm) if max_w_mm > 0 else t.boundingRect().width())
    scene.addItem(t)
    t.setPos(m(x_mm), m(y_mm))
    return t

# ── Geometry helpers ──────────────────────────────────────────────────────────
def arrowhead(scene: SceneLike, tip_x_mm, tip_y_mm, angle_deg,
              color=None, size_mm=2.5):
    color = color or C.DIM
    rad = math.radians(angle_deg)
    half = 0.38
    s = m(size_mm)
    tip = QPointF(m(tip_x_mm), m(tip_y_mm))
    b1  = QPointF(m(tip_x_mm) - s*math.cos(rad-half), m(tip_y_mm) - s*math.sin(rad-half))
    b2  = QPointF(m(tip_x_mm) - s*math.cos(rad+half), m(tip_y_mm) - s*math.sin(rad+half))
    scene.addPolygon(QPolygonF([tip, b1, b2]), no_pen(), QBrush(color))

def dim_h(scene: SceneLike, x1, y1, x2, y2, label, offset_mm=6.0, ext_mm=2.5, size_mm=2.0):
    """Horizontal dimension. All args in mm."""
    dy = min(y1,y2) - offset_mm
    dp = pen_dim()
    scene.addLine(m(x1), m(y1), m(x1), m(dy-ext_mm), dp)
    scene.addLine(m(x2), m(y2), m(x2), m(dy-ext_mm), dp)
    scene.addLine(m(x1), m(dy), m(x2), m(dy), dp)
    arrowhead(scene, x1, dy, 0 if x2 > x1 else 180)
    arrowhead(scene, x2, dy, 180 if x2 > x1 else 0)
    add_text(scene, (x1+x2)/2 - len(label)*size_mm*0.25,
             dy - offset_mm*0.6, label, size_mm)

def dim_v(scene: SceneLike, x1, y1, x2, y2, label, offset_mm=8.0, ext_mm=2.5, size_mm=2.0):
    """Vertical dimension. All args in mm."""
    dx = min(x1,x2) - offset_mm
    dp = pen_dim()
    scene.addLine(m(x1), m(y1), m(dx-ext_mm), m(y1), dp)
    scene.addLine(m(x2), m(y2), m(dx-ext_mm), m(y2), dp)
    scene.addLine(m(dx), m(y1), m(dx), m(y2), dp)
    arrowhead(scene, dx, y1, 270 if y2>y1 else 90)
    arrowhead(scene, dx, y2, 90 if y2>y1 else 270)
    mid_y = (y1+y2)/2
    t = add_text(scene, 0, 0, label, size_mm)
    t.setTransformOriginPoint(t.boundingRect().center())
    t.setRotation(-90)
    t.setPos(m(dx) - t.boundingRect().height()*0.6,
             m(mid_y) + t.boundingRect().width()*0.5)

def leader(scene: SceneLike, tip_x, tip_y, shelf_x, shelf_y, label, size_mm=2.0):
    """Leader line with arrowhead and text shelf. All mm."""
    dp = pen_dim()
    scene.addLine(m(tip_x), m(tip_y), m(shelf_x), m(shelf_y), dp)
    scene.addLine(m(shelf_x), m(shelf_y), m(shelf_x+8), m(shelf_y), dp)
    ang = math.degrees(math.atan2(m(tip_y)-m(shelf_y), m(tip_x)-m(shelf_x)))
    arrowhead(scene, tip_x, tip_y, ang)
    add_text(scene, shelf_x+8.5, shelf_y - size_mm*0.9, label, size_mm)

def centre_line(scene: SceneLike, x1, y1, x2, y2):
    return scene.addLine(m(x1), m(y1), m(x2), m(y2), pen_centre())

def hatch_rect(scene: SceneLike, x_mm, y_mm, w_mm, h_mm, angle_deg=45, pitch_mm=2.5):
    """Hatch a rectangle with ISO hatching lines, clipped to the rect."""
    hp  = pen_hatch()
    rad = math.radians(angle_deg)
    diag = math.sqrt(w_mm**2 + h_mm**2)
    cx, cy = x_mm + w_mm/2, y_mm + h_mm/2
    steps = int(diag/pitch_mm) + 2
    for i in range(-steps, steps+1):
        d  = i * pitch_mm
        dx = d * math.cos(rad + math.pi/2)
        dy = d * math.sin(rad + math.pi/2)
        lx1 = cx + dx - diag*math.cos(rad)
        ly1 = cy + dy - diag*math.sin(rad)
        lx2 = cx + dx + diag*math.cos(rad)
        ly2 = cy + dy + diag*math.sin(rad)
        path = QPainterPath()
        path.addRect(QRectF(m(x_mm), m(y_mm), m(w_mm), m(h_mm)))
        lp = QPainterPath()
        lp.moveTo(m(lx1), m(ly1)); lp.lineTo(m(lx2), m(ly2))
        clipped = path.intersected(lp)
        for j in range(clipped.elementCount()-1):
            e1 = clipped.elementAt(j); e2 = clipped.elementAt(j+1)
            if e1.isMoveTo() or e2.isCurveTo():
                continue
            scene.addLine(e1.x, e1.y, e2.x, e2.y, hp)

# ── Table row helper ──────────────────────────────────────────────────────────
def table_rows(scene: SceneLike, x_mm, y_mm, w_mm, rows,
               row_h_mm, label_size=1.8, value_size=2.4,
               pad_mm=1.5):
    """Draw a standard two-line (label/value) table within a bounding box.
    rows: list of (label, value, color) tuples."""
    sep_pen = QPen(C.ROW_SEP, m(0.15))
    for i, row in enumerate(rows):
        label, value = row[0], row[1]
        color = row[2] if len(row) > 2 else C.TEXT
        ry = y_mm + i * row_h_mm
        # Alternating row bg
        if i % 2 == 0:
            scene.addRect(QRectF(m(x_mm), m(ry), m(w_mm), m(row_h_mm)),
                          no_pen(), QBrush(C.ROW_ALT))
        # Row separator
        scene.addLine(m(x_mm), m(ry+row_h_mm),
                      m(x_mm+w_mm), m(ry+row_h_mm), sep_pen)
        # Label (top of cell)
        add_text(scene, x_mm+pad_mm, ry+0.8, label,
                 label_size, color=C.TEXT_MUTED, max_w_mm=w_mm-2*pad_mm)
        # Value (below label)
        add_text(scene, x_mm+pad_mm, ry+label_size+2.0, value,
                 value_size, bold=True, color=color,
                 max_w_mm=w_mm-2*pad_mm)


class SnapGroup(QGraphicsItemGroup):
    """A QGraphicsItemGroup that is user-draggable and snaps to a grid
    on release. Used to make each elevation view (or, in broken-view
    mode, each segment) an independently repositionable object within
    the otherwise-fixed drawing template -- so the user can click any
    point on a view and drag it to align with the sheet or with another
    view, rather than everything being permanently fixed in place.

    Grid snap: GRID_MM controls the snap spacing (default 5mm, a
    sensible drafting-grid size at this drawing scale)."""

    GRID_MM = 5.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setCursor(Qt.CursorShape.SizeAllCursor)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            grid_px = m(self.GRID_MM)
            new_pos = QPointF(value)
            new_pos.setX(round(new_pos.x() / grid_px) * grid_px)
            new_pos.setY(round(new_pos.y() / grid_px) * grid_px)
            return new_pos
        return super().itemChange(change, value)

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        # Faint selection outline so it's clear the whole view is one
        # draggable unit when selected (helps discoverability).
        if self.isSelected():
            painter.setPen(QPen(QColor("#2266cc"), 1, Qt.PenStyle.DashLine))
            painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            painter.drawRect(self.boundingRect())


class _ItemRecorder:
    """Proxy that forwards add*() calls to the real QGraphicsScene while
    recording every item created, so the caller can group them all into
    one SnapGroup afterward. All the CAD draw helpers above (add_text,
    dim_h, dim_v, leader, centre_line, hatch_rect, table_rows, etc.) take
    a 'scene'-like object as their first argument and only ever call
    addRect/addLine/addEllipse/addPath/addPolygon/addItem on it -- so
    passing a recorder instead of the real scene requires no changes to
    any of those helpers."""

    def __init__(self, real_scene):
        self._scene = real_scene
        self.items: list = []

    def _rec(self, item):
        self.items.append(item)
        return item

    def addRect(self, *a, **kw):
        return self._rec(self._scene.addRect(*a, **kw))

    def addLine(self, *a, **kw):
        return self._rec(self._scene.addLine(*a, **kw))

    def addEllipse(self, *a, **kw):
        return self._rec(self._scene.addEllipse(*a, **kw))

    def addPath(self, *a, **kw):
        return self._rec(self._scene.addPath(*a, **kw))

    def addPolygon(self, *a, **kw):
        return self._rec(self._scene.addPolygon(*a, **kw))

    def addItem(self, item):
        self._scene.addItem(item)
        return self._rec(item)


def _group_recorded_items(recorder: _ItemRecorder, real_scene: QGraphicsScene,
                          label: str = "") -> SnapGroup:
    """Wrap every item captured by an _ItemRecorder into one SnapGroup
    (movable + grid-snapping) and add it to the real scene."""
    group = SnapGroup()
    if label:
        group.setToolTip(label)
    real_scene.addItem(group)
    for item in recorder.items:
        group.addToGroup(item)
    return group


# ── Template: border, zones, panels ──────────────────────────────────────────
class CADTemplate:
    def __init__(self, scene: QGraphicsScene, inputs, results, sign_off=None,
                 view_title: str = "BUCKET ELEVATOR — ELEVATION VIEW"):
        self.s: QGraphicsScene = scene
        self.inp = inputs or {}
        self.r = results or {}
        self.so = sign_off or {}
        self.view_title = view_title
        try:
            from api_client import fetch_model_number
            self.model_no = fetch_model_number(self.inp, self.r)
        except Exception:
            self.model_no = f"VM-??-?-???/{int(self.inp.get('D_mm', 500))}"
        self._sheet()
        self._zones()
        self._params_table()
        self._bom_table()
        self._title_block()

    def _sheet(self):
        s = self.s
        # Cream background
        s.addRect(QRectF(0, 0, m(A3_W_MM), m(A3_H_MM)),
                  no_pen(), QBrush(C.BG)).setZValue(-10)
        # Outer edge
        s.addRect(QRectF(0, 0, m(A3_W_MM), m(A3_H_MM)), pen_frame(),
                  QBrush(Qt.BrushStyle.NoBrush))
        # Inner frame (heavy border)
        s.addRect(QRectF(m(FRAME_L_MM), m(FRAME_T_MM), m(FW_MM), m(FH_MM)),
                  pen_border(), QBrush(Qt.BrushStyle.NoBrush))
        # Panel dividers
        s.addLine(m(LN_X_MM+LN_W_MM), m(FRAME_T_MM),
                  m(LN_X_MM+LN_W_MM), m(FRAME_T_MM+FH_MM), pen_visible(0.4))
        s.addLine(m(KPI_X_MM), m(FRAME_T_MM),
                  m(KPI_X_MM), m(FRAME_T_MM+FH_MM), pen_visible(0.4))
        s.addLine(m(TB_X_MM), m(TB_Y_MM),
                  m(TB_X_MM+TB_W_MM), m(TB_Y_MM), pen_visible(0.4))

    def _zones(self):
        s = self.s
        n_col, n_row = 8, 4
        letters = "ABCDEFGH"
        zp = QPen(C.TEXT_MUTED, m(0.2))
        for i in range(n_col+1):
            x = FRAME_L_MM + i * FW_MM / n_col
            s.addLine(m(x), 0, m(x), m(FRAME_T_MM), zp)
            s.addLine(m(x), m(A3_H_MM-FRAME_B_MM), m(x), m(A3_H_MM), zp)
        for i in range(n_row+1):
            y = FRAME_T_MM + i * FH_MM / n_row
            s.addLine(0, m(y), m(FRAME_L_MM), m(y), zp)
            s.addLine(m(A3_W_MM-FRAME_R_MM), m(y), m(A3_W_MM), m(y), zp)
        for i in range(n_col):
            cx = FRAME_L_MM + (i+0.5) * FW_MM / n_col
            for y in [FRAME_T_MM/2 - 1.2, A3_H_MM - FRAME_B_MM/2 - 1.2]:
                add_text(s, cx - 1.8, y, letters[i], 2.0, color=C.TEXT_MUTED)
        for i in range(n_row):
            cy = FRAME_T_MM + (i+0.5) * FH_MM / n_row
            for x in [FRAME_L_MM/2 - 1.5, A3_W_MM - FRAME_R_MM/2 - 1.5]:
                add_text(s, x, cy - 1.5, str(i+1), 2.0, color=C.TEXT_MUTED)

    # ── Model code segment meanings (for the explanation rows) ────────
    _FAMILY_MEANING = {
        "CD": "Centrifugal Discharge",
        "KD": "Continuous Discharge",
        "MD": "Mill-Duty (abrasive/hot/reinforced)",
        "SC": "Super-Capacity (double-chain)",
        "HG": "High-Speed Grain (double-row belt)",
    }
    _DRIVE_MEANING = {"B": "Belt", "C": "Chain"}
    _SUFFIX_MEANING = {
        "BG": "Boot gravity take-up", "BY": "Boot hydraulic take-up",
        "HS": "Head screw take-up", "HG": "Head gravity take-up",
        "HY": "Head hydraulic take-up",
        "SS1": "Stainless 304", "SS2": "Stainless 316", "SS3": "Stainless 316L/duplex",
        "P1": "Nylon", "P2": "Polyurethane", "P3": "UHMWPE",
        "AR": "Abrasion-resistant liner", "DR": "Double-row buckets",
        "HT": "High-temperature service",
    }

    def _explain_model_code(self) -> list:
        """Returns [(segment_text, meaning_text), ...] describing what
        each part of self.model_no encodes, in plain English."""
        parts = self.model_no.split("-")
        rows = []
        if len(parts) >= 4:
            rows.append((parts[0], "Brand prefix (fixed)"))
            fam = parts[1]
            rows.append((fam, self._FAMILY_MEANING.get(fam, "Unknown family")))
            drv = parts[2]
            rows.append((drv, self._DRIVE_MEANING.get(drv, "Unknown drive")))
            dims = parts[3]
            rows.append((dims, "Bucket width / pulley Ø (mm)"))
            for suf in parts[4:]:
                rows.append((suf, self._SUFFIX_MEANING.get(suf, "Custom suffix")))
        return rows

    def _params_table(self):
        """ONE consolidated table: design INPUT parameters (not computed/
        achieved results -- those move to later CAD pages) plus a plain-
        English explanation of what the model number encodes. Replaces
        the previous separate boot/takeup panel and KPI panel per Jay's
        request to merge into a single table."""
        s, r, inp = self.s, self.r, self.inp
        x, y, w = LN_X_MM, LN_Y_MM, LN_W_MM + (RIGHT_W_MM - LN_W_MM) * 0  # left column width
        w = LN_W_MM
        h = LN_H_MM
        hdr_h = 8.0

        s.addRect(QRectF(m(x), m(y), m(w), m(hdr_h)), no_pen(), QBrush(C.HDR_BG))
        add_text(s, x+1.5, y+1.5, "DESIGN INPUT PARAMETERS", 2.0, bold=True, max_w_mm=w-3)

        def _f(v, dp=0, unit=""):
            if v is None: return "—"
            try: return f"{float(v):.{dp}f}{' '+unit if unit else ''}"
            except: return str(v)

        # Design INPUTS only (from inp, never from computed results r)
        param_rows = [
            ("Required capacity", f"{inp.get('Q_req','—')} t/h"),
            ("Lift height",        f"{inp.get('H_m','—')} m"),
            ("Material",           inp.get("mat_id","—")),
            ("Material temp.",     _f(inp.get("material_temperature_c"), 0, "°C")),
            ("Fill factor (input)", f"{inp.get('fill_pct', 75)} %"),
            ("Conveyor type",      str(inp.get("conveyor_type","belt")).capitalize()),
            ("Bucket selection",   "Auto" if inp.get("auto_bucket", True) else inp.get("bucket_id","—")),
            ("Bucket rows",        "2 (HG double-row)" if int(inp.get("n_rows",1))==2 else "1 (standard)"),
            ("Take-up type",       str(inp.get("takeup_type","screw")).capitalize()),
            ("Take-up position",  str(inp.get("takeup_position","boot")).capitalize()),
        ]

        n_param = len(param_rows)
        code_rows = self._explain_model_code()
        n_code = len(code_rows) + 1   # +1 for the model number line itself

        # Split available height: params table gets proportional space,
        # model-code explanation gets the rest
        avail_h = h - hdr_h
        total_rows = n_param + n_code + 1  # +1 for section divider row
        row_h = avail_h / total_rows

        table_rows(s, x, y+hdr_h, w, param_rows, row_h,
                   label_size=1.6, value_size=2.1, pad_mm=1.5)

        # Section divider: "MODEL CODE" header
        div_y = y + hdr_h + n_param * row_h
        s.addRect(QRectF(m(x), m(div_y), m(w), m(row_h)), no_pen(), QBrush(C.HDR_BG))
        add_text(s, x+1.5, div_y+row_h*0.25, "MODEL CODE BREAKDOWN", 1.8, bold=True, max_w_mm=w-3)

        # Model number itself, then each segment's meaning
        code_display_rows = [("Full model no.", self.model_no)] + \
                            [(seg, meaning) for seg, meaning in code_rows]
        table_rows(s, x, div_y+row_h, w, code_display_rows, row_h,
                   label_size=1.6, value_size=1.9, pad_mm=1.5)

        s.addRect(QRectF(m(x), m(y), m(w), m(h)), pen_visible(0.35),
                  QBrush(Qt.BrushStyle.NoBrush))

    def _bom_table(self):
        """Real itemized Bill of Materials, from the actual bom.py output
        (pos/description/qty/unit/material/spec/mass) -- replaces the old
        KPI/achieved-values panel per Jay's request. Achieved/computed
        performance values move to a later CAD page (not this sheet)."""
        s, r = self.s, self.r
        x, y, w, h = KPI_X_MM, KPI_Y_MM, RIGHT_W_MM, KPI_H_MM
        hdr_h = 7.0

        s.addRect(QRectF(m(x), m(y), m(w), m(hdr_h)), no_pen(), QBrush(C.HDR_BG))
        add_text(s, x+1.5, y+1.2, "BILL OF MATERIALS", 2.0, bold=True, max_w_mm=w-3)

        items = (r.get("bom") or {}).get("items") or []

        # Column layout within the BOM panel width
        col_pos_w  = w * 0.08
        col_desc_w = w * 0.52
        col_qty_w  = w * 0.10
        col_mat_w  = w * 0.30

        # Column header row
        col_hdr_y = y + hdr_h
        col_hdr_h = 4.5
        s.addRect(QRectF(m(x), m(col_hdr_y), m(w), m(col_hdr_h)),
                  no_pen(), QBrush(C.ROW_ALT))
        add_text(s, x+0.5, col_hdr_y+0.3, "#", 1.5, bold=True, color=C.TEXT_MUTED)
        add_text(s, x+col_pos_w+0.5, col_hdr_y+0.3, "DESCRIPTION", 1.5, bold=True, color=C.TEXT_MUTED)
        add_text(s, x+col_pos_w+col_desc_w+0.5, col_hdr_y+0.3, "QTY", 1.5, bold=True, color=C.TEXT_MUTED)
        add_text(s, x+col_pos_w+col_desc_w+col_qty_w+0.5, col_hdr_y+0.3, "MATERIAL", 1.5, bold=True, color=C.TEXT_MUTED)
        s.addLine(m(x), m(col_hdr_y+col_hdr_h), m(x+w), m(col_hdr_y+col_hdr_h), pen_visible(0.3))

        avail_h = h - hdr_h - col_hdr_h
        n_show = max(1, len(items))
        row_h = max(3.2, avail_h / max(n_show, 1))
        # If too many items to fit at a legible row height, cap row height
        # at a legible minimum and let the rest overflow with a note
        MIN_ROW_H = 3.2
        max_rows_that_fit = int(avail_h / MIN_ROW_H)
        row_h = max(MIN_ROW_H, avail_h / max(min(len(items), max_rows_that_fit), 1))

        sep_pen = QPen(C.ROW_SEP, m(0.12))
        shown = items[:max_rows_that_fit] if items else []
        for i, item in enumerate(shown):
            ry = col_hdr_y + col_hdr_h + i * row_h
            if i % 2 == 0:
                s.addRect(QRectF(m(x), m(ry), m(w), m(row_h)), no_pen(), QBrush(C.ROW_ALT))
            s.addLine(m(x), m(ry+row_h), m(x+w), m(ry+row_h), sep_pen)
            add_text(s, x+0.5, ry+0.3, str(item.get("pos","—")), 1.6, color=C.TEXT_MUTED)
            add_text(s, x+col_pos_w+0.5, ry+0.3, str(item.get("description","—")),
                     1.7, max_w_mm=col_desc_w-1)
            add_text(s, x+col_pos_w+col_desc_w+0.5, ry+0.3, str(item.get("qty","—")), 1.7)
            add_text(s, x+col_pos_w+col_desc_w+col_qty_w+0.5, ry+0.3,
                     str(item.get("material","—")), 1.5, color=C.TEXT_MUTED,
                     max_w_mm=col_mat_w-1)

        if not items:
            add_text(s, x+2, col_hdr_y+col_hdr_h+3, "No BOM data — run a calculation first.",
                     1.8, color=C.TEXT_MUTED)
        elif len(items) > max_rows_that_fit:
            note_y = col_hdr_y + col_hdr_h + max_rows_that_fit * row_h
            add_text(s, x+0.5, note_y+0.3,
                     f"... +{len(items)-max_rows_that_fit} more items — see full BOM report",
                     1.6, color=C.TEXT_MUTED)

        s.addRect(QRectF(m(x), m(y), m(w), m(h)), pen_visible(0.35),
                  QBrush(Qt.BrushStyle.NoBrush))

    def _title_block(self):
        s, r, inp = self.s, self.r, self.inp
        x, y, w, h = TB_X_MM, TB_Y_MM, TB_W_MM, TB_H_MM
        model_no = self.model_no

        s.addRect(QRectF(m(x), m(y), m(w), m(h)), pen_visible(0.5),
                  QBrush(C.PANEL_BG))

        # Row heights
        r1h = 14.0   # company + model
        r2h = 9.0    # drawing title
        r3h = 9.0    # material/Q/H
        r3bh = 6.0   # engineering disclaimer (structural sizing not modeled)
        r4h = 9.0    # scale/sheet
        r5h = h - r1h - r2h - r3h - r3bh - r4h  # sign-offs

        # Row 1: company block | model number
        s.addRect(QRectF(m(x), m(y), m(w), m(r1h)), no_pen(), QBrush(C.HDR_BG))
        s.addLine(m(x), m(y+r1h), m(x+w), m(y+r1h), pen_visible(0.35))
        # Split row1: company left 38mm, model right
        s.addLine(m(x+38), m(y), m(x+38), m(y+r1h), pen_visible(0.25))
        add_text(s, x+1.5, y+1.0,  "JAYVEECONS",   2.8, bold=True)
        add_text(s, x+1.5, y+6.0,  "Engineering & Design", 1.7, color=C.TEXT_MUTED)
        add_text(s, x+39.5, y+2.0, model_no, 2.5, bold=True, max_w_mm=w-41)

        # Row 2: drawing title
        s.addLine(m(x), m(y+r1h+r2h), m(x+w), m(y+r1h+r2h), pen_visible(0.25))
        add_text(s, x+1.5, y+r1h+1.0,
                 self.view_title, 2.2, bold=True,
                 max_w_mm=w-3)

        # Row 3: material / Q / H
        s.addLine(m(x), m(y+r1h+r2h+r3h), m(x+w), m(y+r1h+r2h+r3h), pen_visible(0.25))
        mat_name = (r.get("mat") or {}).get("name") or inp.get("mat_id","—")
        add_text(s, x+1.5, y+r1h+r2h+1.0,
                 f"Mat: {mat_name}  |  H={inp.get('H_m','—')}m  Q={inp.get('Q_req','—')}t/h",
                 2.0, max_w_mm=w-3)

        # Row 3b: engineering disclaimer -- base/foundation/structural
        # support framework is NOT modeled in this drawing (skipped per
        # Jay's decision -- no verified sizing basis exists yet). Flagged
        # here so nobody mistakes the absence of a base frame for "there
        # is none needed."
        y3b = y + r1h + r2h + r3h
        s.addRect(QRectF(m(x), m(y3b), m(w), m(r3bh)), no_pen(),
                  QBrush(QColor("#f5e8d0")))
        s.addLine(m(x), m(y3b+r3bh), m(x+w), m(y3b+r3bh), pen_visible(0.25))
        add_text(s, x+1.5, y3b+0.6,
                 "⚠ Base/foundation & other structural sizing NOT shown —",
                 1.5, bold=True, color=QColor("#885500"), max_w_mm=w-3)
        add_text(s, x+1.5, y3b+3.2,
                 "consult structural engineer before fabrication",
                 1.5, bold=True, color=QColor("#885500"), max_w_mm=w-3)

        # Row 4: scale / sheet  (vertical separator at mid)
        y4 = y + r1h + r2h + r3h + r3bh
        s.addLine(m(x), m(y4+r4h), m(x+w), m(y4+r4h), pen_visible(0.25))
        s.addLine(m(x+w/2), m(y4), m(x+w/2), m(y4+r4h), pen_visible(0.25))
        add_text(s, x+1.5, y4+1.0, "SCALE", 1.7, color=C.TEXT_MUTED)
        add_text(s, x+1.5, y4+4.5, f"1:{r.get('_draw_scale','?')}", 2.5, bold=True)
        add_text(s, x+w/2+1.5, y4+1.0, "SHEET", 1.7, color=C.TEXT_MUTED)
        add_text(s, x+w/2+1.5, y4+4.5, "1 of 1", 2.5)

        # Row 5: sign-offs in 3 columns
        y5 = y4 + r4h
        col3 = w / 3
        for i, role in enumerate(["DRAWN", "CHECKED", "APPROVED"]):
            cx = x + i * col3
            if i > 0:
                s.addLine(m(cx), m(y5), m(cx), m(y5+r5h), pen_visible(0.25))
            name = (self.so.get(role.lower()) or {}).get("display_name", "—")
            date = (self.so.get(role.lower()) or {}).get("signed_at", "—")[:10]
            # Tightened vertical spacing (was 1.0/4.2/8.5) -- row5 shrank
            # to make room for the structural-sizing disclaimer row above,
            # so these 3 lines now need to fit more compactly, leaving
            # clear space at the bottom for the ISO/date strip below.
            add_text(s, cx+1.2, y5+0.8, role, 1.6, color=C.TEXT_MUTED,
                     max_w_mm=col3-2)
            add_text(s, cx+1.2, y5+3.4, name, 1.9, bold=True, max_w_mm=col3-2)
            add_text(s, cx+1.2, y5+6.6, date, 1.6, color=C.TEXT_MUTED,
                     max_w_mm=col3-2)

        # Bottom strip -- placed at a fixed clear offset from the row5
        # boundary, safely below the sign-off content's tightened spacing
        from datetime import datetime
        add_text(s, x+1.5, y5+r5h-3.0,
                 f"ISO A3 · {datetime.now().strftime('%Y-%m-%d')} · VECTOMEC™",
                 1.5, color=C.TEXT_MUTED)


# ── Elevation Drawing ─────────────────────────────────────────────────────────
def draw_structural_elements(s, inp, r, cx_l, cx_r, headCY, bootCY,
                          CAS_W, H_draw, K):
    """Structural elements pass -- called after the casing outline is
    already drawn so these sit on top of it cleanly.

    Standalone function (not a method) so it can be called identically
    from ElevationCADDraw (front view) and SideElevationCADDraw (side
    view) without the type mismatch that comes from calling an unbound
    method with a 'self' of the wrong class.

    Implemented increments (task #9):
      1. Casing section joints / stiffener rings (real spacing data)
      2. Inspection doors (600×600mm, boot + every 3rd ring)
      3. Balloon callouts (ISO-style circled numbers)
      4. Access platforms with handrails (OSHA 1910.23 / ISO 14122-3)
      5. Caged ladder (ISO 14122-4)

    Next increment:
      - Structural support framework / base legs
    """
    H_m = float(inp.get("H_m") or 25)
    BW_mm = float(r.get("belt_w") or 350)

    # ── Stiffener/section joints ───────────────────────────────────
    cs = r.get("casing_stiffener") or {}
    stiff_spacing_mm = float(cs.get("recommended_mm") or 1200)
    stiff_draw = stiff_spacing_mm / K
    flange_t   = max(0.8, 4.0 / K)
    flange_pen = pen_visible(0.4)
    stiff_brush = QBrush(QColor("#d0d8c8"))

    y = headCY
    stiff_y_positions = []
    while y + stiff_draw < bootCY - 2:
        y += stiff_draw
        stiff_y_positions.append(y)
        s.addRect(QRectF(m(cx_l), m(y - flange_t), m(CAS_W), m(flange_t * 2)),
                  flange_pen, stiff_brush)
        s.addLine(m(cx_l), m(y), m(cx_r), m(y), pen_visible(0.4))

    # ── Inspection doors ───────────────────────────────────────────
    door_w_draw = max(4.0, min(600 / K, CAS_W * 0.5))
    door_h_draw = max(3.5, min(600 / K, stiff_draw * 0.8 if stiff_draw > 0 else 6.0))
    door_pen    = pen_visible(0.35)
    door_brush  = QBrush(QColor("#dce4f0"))

    def _draw_door(dy_centre):
        dx     = cx_l
        dy_top = dy_centre - door_h_draw / 2
        dy_bot = dy_centre + door_h_draw / 2
        if dy_top < headCY or dy_bot > bootCY:
            return
        s.addRect(QRectF(m(dx), m(dy_top), m(door_w_draw), m(door_h_draw)),
                  door_pen, door_brush)
        s.addLine(m(dx), m(dy_top), m(dx+door_w_draw), m(dy_bot), door_pen)
        s.addLine(m(dx+door_w_draw), m(dy_top), m(dx), m(dy_bot), door_pen)

    _draw_door(bootCY - door_h_draw * 0.8)
    for i, sy in enumerate(stiff_y_positions):
        if (i + 1) % 3 == 0:
            _draw_door(sy)

    # ── Access platforms with handrails ────────────────────────────
    # OSHA 1910.23 / ISO 14122-3: max 6000mm between access platforms.
    # Platforms coincide with the nearest stiffener ring so the
    # structural load transfers cleanly into the casing stiffener.
    # Real dimensions:
    #   Grating platform: 1000mm each side of casing face
    #   Top handrail:     1100mm above platform floor
    #   Mid-rail:          550mm above platform floor
    #   Toe board:         100mm above platform floor
    #   Posts: one at the outer end of each platform + one at mid-span

    MAX_PLATFORM_SPACING_MM = 6000.0
    plat_real  = 1000.0            # grating width each side (mm)
    rail_h_mm  = 1100.0            # top rail height (mm)
    midr_h_mm  =  550.0            # mid-rail height (mm)
    toe_h_mm   =  100.0            # toe board height (mm)
    post_w_mm  =   50.0            # square hollow post width (mm)

    # Drawing sizes (scaled)
    plat_draw  = max(5.0, plat_real / K)
    rail_h     = max(1.5, rail_h_mm / K)
    midr_h     = max(0.8, midr_h_mm / K)
    toe_h      = max(0.5, toe_h_mm  / K)
    post_w     = max(0.6, post_w_mm / K)

    # Choose platform levels: walk through stiffener positions and pick
    # every ring that is ≥ MAX_PLATFORM_SPACING_MM below the previous
    # platform. Always include the ring nearest 2/3 up the leg (a
    # mandatory intermediate platform for elevators >12m tall per code).
    platform_y_positions = []
    last_plat_real_y = H_m * 1000   # start from bottom (boot = 0 reference)
    # Build a mapping: stiffener index → real y from bottom
    n_stiff = len(stiff_y_positions)
    for i, sy in enumerate(reversed(stiff_y_positions)):
        # Real height from boot = (n_stiff - i) * stiff_spacing_mm
        real_y_from_boot = (n_stiff - i) * stiff_spacing_mm
        if last_plat_real_y - real_y_from_boot >= MAX_PLATFORM_SPACING_MM:
            platform_y_positions.append(sy)
            last_plat_real_y = real_y_from_boot

    # Always add a platform near head if last one is > 3m below it
    if stiff_y_positions:
        top_stiff = stiff_y_positions[0]
        if not platform_y_positions or abs(platform_y_positions[-1] - top_stiff) > 3000/K:
            if top_stiff > headCY + 2:
                platform_y_positions.append(top_stiff)

    platform_pen   = QPen(QColor("#2d5a2d"), m(0.4), Qt.PenStyle.SolidLine)
    platform_brush = QBrush(QColor("#c8dcc8"))   # muted green grating
    rail_pen       = QPen(QColor("#2d5a2d"), m(0.35), Qt.PenStyle.SolidLine)
    post_pen       = QPen(QColor("#2d5a2d"), m(0.4), Qt.PenStyle.SolidLine)

    for py in platform_y_positions:
        if py <= headCY + 2 or py >= bootCY - 2:
            continue
        # LEFT platform grating
        s.addRect(QRectF(m(cx_l - plat_draw), m(py - toe_h),
                          m(plat_draw), m(toe_h)),
                  platform_pen, platform_brush)
        # RIGHT platform grating
        s.addRect(QRectF(m(cx_r), m(py - toe_h),
                          m(plat_draw), m(toe_h)),
                  platform_pen, platform_brush)

        # Toe boards (front edge, both sides)
        s.addLine(m(cx_l - plat_draw), m(py),
                  m(cx_l - plat_draw), m(py - toe_h), post_pen)
        s.addLine(m(cx_r + plat_draw), m(py),
                  m(cx_r + plat_draw), m(py - toe_h), post_pen)

        for side_l, side_r in [(cx_l - plat_draw, cx_l),
                                (cx_r, cx_r + plat_draw)]:
            mid_x = (side_l + side_r) / 2
            outer_x = side_l if side_l < cx_l else side_r

            # Outer post (full height from floor to top rail)
            s.addLine(m(outer_x), m(py),
                       m(outer_x), m(py - rail_h), post_pen)
            # Mid post
            s.addLine(m(mid_x),   m(py),
                       m(mid_x),   m(py - rail_h), post_pen)

            # Top handrail
            s.addLine(m(side_l), m(py - rail_h),
                       m(side_r), m(py - rail_h), rail_pen)
            # Mid-rail
            s.addLine(m(side_l), m(py - midr_h),
                       m(side_r), m(py - midr_h), rail_pen)

        # Platform level label (right side, small, muted)
        real_h_m = (n_stiff - stiff_y_positions.index(py) - 1) * stiff_spacing_mm / 1000
        add_text(s, cx_r + plat_draw + 1.5, py - midr_h,
                 f"EL +{real_h_m:.1f}m", 1.7, color=QColor("#2d5a2d"))

    # ── Caged ladder (increment 4 of structural elements) ─────────
    # ISO 14122-4 / OSHA 1910.23: vertical ladder on the right face
    # of the casing, from boot to head, offset so it clears the casing
    # wall. Cage (safety cage) required when height > 3m.
    #
    # Real dimensions:
    #   Stringer spacing:     400mm (inside width of ladder)
    #   Rung pitch:           250mm (step spacing)
    #   Cage hoop pitch:      900mm (ISO 14122-4 maximum)
    #   Cage hoop radius:     350mm from stringer centreline
    #   Ladder offset from casing face: 150mm (clearance for cage)

    STRINGER_SPACING_MM = 400.0
    RUNG_PITCH_MM       = 250.0
    CAGE_HOOP_PITCH_MM  = 900.0
    CAGE_R_MM           = 350.0
    LADDER_OFFSET_MM    = 150.0

    str_w  = max(3.0, STRINGER_SPACING_MM / K)
    rung_p = max(1.0, RUNG_PITCH_MM / K)
    cage_p = max(3.0, CAGE_HOOP_PITCH_MM / K)
    cage_r = max(2.5, CAGE_R_MM / K)
    lad_off = max(3.0, LADDER_OFFSET_MM / K)

    # Ladder centreline: right face of casing + offset
    lad_cx = cx_r + lad_off
    lad_l  = lad_cx - str_w / 2    # left stringer x
    lad_r  = lad_cx + str_w / 2    # right stringer x

    ladder_pen  = QPen(QColor("#2d5a2d"), m(0.35), Qt.PenStyle.SolidLine)
    cage_pen    = QPen(QColor("#3a7a3a"), m(0.25), Qt.PenStyle.SolidLine)

    # Stringers (full height, boot to head)
    s.addLine(m(lad_l), m(headCY), m(lad_l), m(bootCY), ladder_pen)
    s.addLine(m(lad_r), m(headCY), m(lad_r), m(bootCY), ladder_pen)

    # Rungs
    y = headCY + rung_p
    while y < bootCY - rung_p * 0.3:
        s.addLine(m(lad_l), m(y), m(lad_r), m(y), ladder_pen)
        y += rung_p

    # Cage hoops (semi-circular arcs, bowing rightward from ladder)
    # In a 2D elevation view, a cage hoop is shown as a horizontal
    # bar at each hoop level (the arc projects to a straight line in
    # this projection), with short vertical stubs at the attachment
    # points showing the hoop depth.
    cage_stub = max(1.0, cage_r * 0.25)   # stub depth
    y = headCY + cage_p
    while y < bootCY - cage_p * 0.3:
        # Horizontal bar (cage hoop arc, in elevation)
        s.addLine(m(lad_l - cage_stub), m(y), m(lad_r + cage_r), m(y), cage_pen)
        # Left + right attachment stubs
        s.addLine(m(lad_l), m(y - cage_stub*0.5),
                   m(lad_l), m(y + cage_stub*0.5), cage_pen)
        s.addLine(m(lad_r + cage_r), m(y - cage_stub*0.5),
                   m(lad_r + cage_r), m(y + cage_stub*0.5), cage_pen)
        y += cage_p

    # Ladder label
    add_text(s, lad_r + cage_r + 1.5, (headCY + bootCY) / 2 - 3.0,
             "CAGE LADDER", 1.8, bold=True, color=QColor("#2d5a2d"))
    add_text(s, lad_r + cage_r + 1.5, (headCY + bootCY) / 2 + 0.5,
             "ISO 14122-4", 1.5, color=QColor("#3a7a3a"))

    # ── Balloon callouts ───────────────────────────────────────────
    balloon_r   = 3.5
    balloon_pen = pen_visible(0.25)
    for by, num in [(headCY, "①"), (headCY + H_draw*0.50, "③"), (bootCY, "②")]:
        bx = cx_r + 6.0
        if by < headCY - 2 or by > bootCY + 8:
            continue
        s.addEllipse(QRectF(m(bx-balloon_r), m(by-balloon_r),
                             m(balloon_r*2), m(balloon_r*2)),
                     balloon_pen, QBrush(QColor("#ffffff")))
        s.addLine(m(cx_r), m(by), m(bx-balloon_r), m(by), pen_dim())
        add_text(s, bx-balloon_r*0.55, by-balloon_r*0.85,
                 num, 2.2, bold=True, color=C.BORDER)


class ElevationCADDraw:
    """Draws the elevator elevation in the drawing area. All dimensions mm.

    Scale policy (per Jay's spec):
      - Default target scale is 1:8. If drawing_scale is given explicitly
        (from the UI scale selector), that value is used instead.
      - If the elevator's real height doesn't fit in the available drawing
        area at the target scale, the view switches to a BROKEN (2-segment)
        layout: head section + boot section side by side, each at the SAME
        scale, joined by a conventional ISO break line and match-line
        reference -- rather than silently coarsening the scale (which
        would make horizontal features too small to read, the exact
        problem Jay flagged).
      - Only if two segments still can't fit (extreme height) does the
        scale widen automatically, with a note on the drawing.
    """

    DEFAULT_SCALE = 8

    def __init__(self, scene: QGraphicsScene, inputs, results, drawing_scale: Optional[int] = None):
        self.s: SceneLike = scene
        self._real_scene: QGraphicsScene = scene   # kept for restoring self.s after each recorder pass
        self.inp, self.r = inputs or {}, results or {}
        self._user_scale = drawing_scale
        self._draw()

    # ── Scale selection ────────────────────────────────────────────────
    def _select_scale_and_layout(self, H_total_mm: float, avail_h_mm: float):
        """Returns (scale, n_segments). n_segments=1 for a normal single
        view; n_segments=2 for a broken (head/boot) view at the same scale.

        If the user explicitly picked a scale (drawing_scale != None), it
        is ALWAYS honoured exactly -- never silently substituted for a
        different value. If it doesn't fit even as 2 segments, the
        drawing is still rendered at that scale (broken into 2 segments)
        and may extend past the nominal drawing-area boundary; that's the
        visible, honest consequence of the user's own scale choice, not
        a silent substitution. Only in Auto-fit mode (drawing_scale=None)
        does the system choose/widen the scale on the user's behalf."""
        if self._user_scale:
            target = self._user_scale
            if H_total_mm / target <= avail_h_mm:
                return target, 1
            return target, 2   # broken view at the user's own scale -- never widened

        # Auto-fit mode
        target = self.DEFAULT_SCALE
        if H_total_mm / target <= avail_h_mm:
            return target, 1
        if H_total_mm / target <= avail_h_mm * 2:
            return target, 2
        widened = _choose_scale(H_total_mm, avail_h_mm * 2)
        return widened, 2

    def _draw(self):
        s, inp, r = self.s, self.inp, self.r
        bkt = r.get("bucket") or {}

        H_m       = float(inp.get("H_m") or 25)
        D_head_mm = float(inp.get("D_mm") or 500)
        D_boot_mm = float(inp.get("boot_pulley_D_mm") or 300)
        BW_mm     = float(r.get("belt_w") or 350)
        spacing_m = float(r.get("spacing") or 0.20)

        H_total_mm = H_m*1000 + D_head_mm/2 + D_boot_mm/2 + 80
        avail_h_mm = DA_H_MM - 22
        K, n_seg = self._select_scale_and_layout(H_total_mm, avail_h_mm)
        r["_draw_scale"] = K
        r["_draw_segments"] = n_seg
        sc = lambda mm: mm / K

        if n_seg == 1:
            self._draw_single(sc, K, H_m, D_head_mm, D_boot_mm, BW_mm,
                              spacing_m, bkt, avail_h_mm)
        else:
            self._draw_broken(sc, K, H_m, D_head_mm, D_boot_mm, BW_mm,
                              spacing_m, bkt, avail_h_mm)

    # ── Envelope centering helper ─────────────────────────────────────
    def _envelope_offsets(self, CAS_W, ext, gb_w, m_w, feed_len=17.5):
        """Compute the left/right extent of the full visual assembly
        (feed arrow annotation on the left, drive assembly on the right)
        relative to an assumed midX=0, so the caller can shift midX to
        centre the WHOLE assembly -- not just the casing centreline --
        within the drawing area. This is the fix for 'image not centred'."""
        left_extent  = -(CAS_W/2 + feed_len)
        right_extent = +(CAS_W/2 + ext + 2.5 + gb_w + 1.5 + m_w)
        centre_offset = (left_extent + right_extent) / 2
        return centre_offset

    # ── Single (unbroken) view ─────────────────────────────────────────
    def _draw_single(self, sc, K, H_m, D_head_mm, D_boot_mm, BW_mm,
                     spacing_m, bkt, avail_h_mm):
        inp, r = self.inp, self.r
        real_scene = self._real_scene

        MARGIN_T = 12.0
        H_draw   = sc(H_m * 1000)
        rH       = sc(D_head_mm / 2)
        rB       = sc(D_boot_mm / 2)
        shaft_r  = max(1.8, sc(float(r.get("d_mm") or 90) / 2))
        shaft_rB = max(1.5, sc(D_boot_mm * 0.12))

        CAS_W  = max(30.0, min(sc(BW_mm + 220), DA_W_MM * 0.55))
        ext    = 9.0
        gb_w, gb_h = 14.0, 10.0
        m_w, m_h   = 14.0, 12.0

        # ── Centering fix: shift midX so the FULL visual envelope
        # (feed arrow ... drive assembly) is centred in DA_W, not just
        # the casing centreline.
        centre_offset = self._envelope_offsets(CAS_W, ext, gb_w, m_w)
        midX   = DA_X_MM + DA_W_MM/2 - centre_offset
        headCY = DA_Y_MM + MARGIN_T + rH
        bootCY = headCY + rH + H_draw + rB
        cx_l   = midX - CAS_W/2
        cx_r   = midX + CAS_W/2

        # Fixed template annotation -- not part of the movable view group
        add_text(real_scene, DA_X_MM+1, DA_Y_MM+DA_H_MM-4.5,
                 f"SCALE 1:{K}  |  HORIZ. NTS — SEE DIMENSION CALLOUTS",
                 1.8, color=C.TEXT_MUTED)

        # Everything else routes through a recorder so it can be grouped
        # into one draggable, grid-snapping unit -- per Jay's request to
        # make the view itself moveable within the fixed template.
        rec = _ItemRecorder(real_scene)
        self.s = rec

        self._draw_casing_and_internals(
            midX, headCY, bootCY, cx_l, cx_r, CAS_W, H_draw,
            rH, rB, shaft_r, shaft_rB, ext, gb_w, gb_h, m_w, m_h,
            D_head_mm, D_boot_mm, BW_mm, spacing_m, bkt,
            draw_head=True, draw_boot=True)

        self._draw_dimensions(midX, headCY, bootCY, cx_l, cx_r,
                              CAS_W, H_draw, rH, H_m, D_head_mm, BW_mm,
                              spacing_m, bkt)

        self.s = real_scene
        _group_recorded_items(rec, real_scene, "Elevation view — drag to reposition, snaps to 5mm grid")

    # ── Broken (2-segment) view ────────────────────────────────────────
    def _draw_broken(self, sc, K, H_m, D_head_mm, D_boot_mm, BW_mm,
                     spacing_m, bkt, avail_h_mm):
        """Two side-by-side segments at the SAME scale: head section on
        the left, boot section on the right, each showing as much of the
        casing as fits, joined by an ISO break line and a match-line
        reference. Each segment is its own independently draggable
        SnapGroup -- Jay reported the two segments weren't aligned with
        each other, so rather than trying to auto-align them perfectly,
        each can now be manually dragged (with grid-snap) to line up."""
        inp, r = self.inp, self.r
        real_scene = self._real_scene

        MARGIN_T = 12.0
        rH = sc(D_head_mm / 2)
        rB = sc(D_boot_mm / 2)
        shaft_r  = max(1.8, sc(float(r.get("d_mm") or 90) / 2))
        shaft_rB = max(1.5, sc(D_boot_mm * 0.12))
        ext = 9.0
        gb_w, gb_h = 14.0, 10.0
        m_w, m_h   = 14.0, 12.0

        max_draw_h = avail_h_mm - MARGIN_T
        max_real_mm_per_seg = max_draw_h * K
        H_total_real_mm = H_m * 1000
        seg_real_mm = min(H_total_real_mm / 2, max_real_mm_per_seg - 40)
        seg_real_mm = max(seg_real_mm, 200)
        H_draw_seg  = sc(seg_real_mm)

        # Honesty check: at a fine user-selected scale, 2 segments may not
        # be enough to cover the FULL real height without silently
        # dropping the middle portion. Rather than omit material with no
        # indication, warn clearly on the drawing. (Full N-segment
        # support is future scope -- this is the first-pass safety net.)
        total_covered_mm = 2 * seg_real_mm
        if total_covered_mm < H_total_real_mm - 1:
            missing_mm = H_total_real_mm - total_covered_mm
            add_text(real_scene, DA_X_MM+1, DA_Y_MM+5.5,
                     f"⚠ INCOMPLETE AT THIS SCALE: {missing_mm/1000:.1f}m of casing not shown "
                     f"(2 segments insufficient at 1:{K}) — increase scale or use Auto-fit",
                     1.8, bold=True, color=C.RED)

        col_w  = DA_W_MM * 0.46
        gap    = DA_W_MM * 0.08
        col1_cx = DA_X_MM + col_w/2 + 2
        col2_cx = DA_X_MM + col_w + gap + col_w/2 - 2
        CAS_W = max(24.0, min(sc(BW_mm + 220), col_w * 0.65))

        # Fixed template annotations -- not part of either movable group
        add_text(real_scene, DA_X_MM+1, DA_Y_MM+DA_H_MM-4.5,
                 f"SCALE 1:{K} (BROKEN VIEW — 2 SEGMENTS, SEE MATCH LINE A-A)",
                 1.7, color=C.TEXT_MUTED)
        add_text(real_scene, DA_X_MM+1, DA_Y_MM+2,
                 f"OVERALL H = {H_m:.0f} m  (shown broken — drag segments to align, snaps to 5mm grid)",
                 2.0, bold=True)

        # ── HEAD segment: own recorder + independently draggable group ──
        headCY = DA_Y_MM + MARGIN_T + rH
        head_break_y = headCY + rH + H_draw_seg
        cx_l1, cx_r1 = col1_cx - CAS_W/2, col1_cx + CAS_W/2

        head_rec = _ItemRecorder(real_scene)
        self.s = head_rec
        s = self.s

        centre_line(s, col1_cx, headCY-rH-6, col1_cx, head_break_y+6)
        s.addRect(QRectF(m(cx_l1), m(headCY), m(CAS_W), m(H_draw_seg)),
                  pen_visible(0.5), QBrush(C.CASING))
        hatch_rect(s, cx_l1, headCY, 3.5, H_draw_seg)
        hatch_rect(s, cx_r1-3.5, headCY, 3.5, H_draw_seg)

        # Structural elements (stiffeners, doors, platforms, ladder) --
        # THIS WAS MISSING: previously only called from the single-view
        # path (_draw_casing_and_internals), which the broken-view path
        # (used by virtually every real elevator) never goes through.
        draw_structural_elements(s, self.inp, self.r, cx_l1, cx_r1, headCY, head_break_y,
                                  CAS_W, H_draw_seg, K)

        belt_off1 = CAS_W * 0.20
        s.addLine(m(col1_cx-belt_off1), m(headCY), m(col1_cx-belt_off1), m(head_break_y), pen_visible(0.5))
        s.addLine(m(col1_cx+belt_off1), m(headCY), m(col1_cx+belt_off1), m(head_break_y), pen_visible(0.35))

        self._draw_head_group(col1_cx, headCY, rH, shaft_r, cx_l1, cx_r1,
                              ext, gb_w, gb_h, m_w, m_h, D_head_mm)
        self._break_line(cx_l1, cx_r1, head_break_y)
        add_text(s, col1_cx - CAS_W/2 - 2, head_break_y + 5,
                 "MATCH LINE A-A", 2.0, bold=True, color=C.RED)

        self.s = real_scene
        _group_recorded_items(head_rec, real_scene,
                              "Head section — drag to reposition, snaps to 5mm grid")

        # ── BOOT segment: own recorder + independently draggable group ──
        bootCY = DA_Y_MM + DA_H_MM - 18 - rB
        boot_break_y = bootCY - rB - H_draw_seg
        cx_l2, cx_r2 = col2_cx - CAS_W/2, col2_cx + CAS_W/2

        boot_rec = _ItemRecorder(real_scene)
        self.s = boot_rec
        s = self.s

        centre_line(s, col2_cx, boot_break_y-6, col2_cx, bootCY+rB+16)
        s.addRect(QRectF(m(cx_l2), m(boot_break_y), m(CAS_W), m(H_draw_seg)),
                  pen_visible(0.5), QBrush(C.CASING))
        hatch_rect(s, cx_l2, boot_break_y, 3.5, H_draw_seg)
        hatch_rect(s, cx_r2-3.5, boot_break_y, 3.5, H_draw_seg)

        # Structural elements -- same fix as the head segment above
        draw_structural_elements(s, self.inp, self.r, cx_l2, cx_r2, boot_break_y, bootCY,
                                  CAS_W, H_draw_seg, K)

        belt_off2 = CAS_W * 0.20
        s.addLine(m(col2_cx-belt_off2), m(boot_break_y), m(col2_cx-belt_off2), m(bootCY), pen_visible(0.5))
        s.addLine(m(col2_cx+belt_off2), m(boot_break_y), m(col2_cx+belt_off2), m(bootCY), pen_visible(0.35))

        self._draw_boot_group(col2_cx, bootCY, rB, shaft_rB, D_boot_mm)
        self._break_line(cx_l2, cx_r2, boot_break_y)
        add_text(s, col2_cx - CAS_W/2 - 2, boot_break_y - 6,
                 "MATCH LINE A-A", 2.0, bold=True, color=C.RED)

        self.s = real_scene
        _group_recorded_items(boot_rec, real_scene,
                              "Boot section — drag to reposition, snaps to 5mm grid")

    def _break_line(self, x_l, x_r, y):
        """ISO convention break line: a shallow zigzag across the casing
        width indicating removed/continued material."""
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

    # ── Shared sub-drawing helpers ─────────────────────────────────────
    def _draw_head_group(self, midX, headCY, rH, shaft_r, cx_l, cx_r,
                         ext, gb_w, gb_h, m_w, m_h, D_head_mm):
        s, inp, r = self.s, self.inp, self.r
        lag_extra = max(1.2, rH*0.15)
        s.addEllipse(QRectF(m(midX-(rH+lag_extra)), m(headCY-(rH+lag_extra)),
                             m((rH+lag_extra)*2), m((rH+lag_extra)*2)),
                     pen_hidden(), QBrush(Qt.BrushStyle.NoBrush))
        s.addEllipse(QRectF(m(midX-rH), m(headCY-rH), m(rH*2), m(rH*2)),
                     pen_visible(0.5), QBrush(C.PULLEY))
        centre_line(s, midX-rH*0.9, headCY, midX+rH*0.9, headCY)
        centre_line(s, midX, headCY-rH*0.9, midX, headCY+rH*0.9)
        s.addEllipse(QRectF(m(midX-shaft_r), m(headCY-shaft_r),
                             m(shaft_r*2), m(shaft_r*2)),
                     pen_hidden(), QBrush(QColor("#c8c8e0")))
        hub_r = max(0.8, shaft_r*0.3)
        s.addEllipse(QRectF(m(midX-hub_r), m(headCY-hub_r),
                             m(hub_r*2), m(hub_r*2)), no_pen(), QBrush(C.VISIBLE))
        for sx, ex in [(cx_l, cx_l-ext), (cx_r, cx_r+ext)]:
            s.addLine(m(sx), m(headCY-shaft_r), m(ex), m(headCY-shaft_r), pen_visible(0.35))
            s.addLine(m(sx), m(headCY+shaft_r), m(ex), m(headCY+shaft_r), pen_visible(0.35))
            s.addLine(m(ex), m(headCY-shaft_r-1.5), m(ex), m(headCY+shaft_r+1.5), pen_visible(0.5))
        drv_x = cx_r + ext + 2.5
        s.addRect(QRectF(m(drv_x), m(headCY-gb_h/2), m(gb_w), m(gb_h)),
                  pen_visible(0.35), QBrush(C.DRIVE_GB))
        add_text(s, drv_x+1.5, headCY-gb_h/2+2.0, "GB", 2.5, bold=True)
        s.addLine(m(cx_r+ext), m(headCY), m(drv_x), m(headCY), pen_visible(0.35))
        m_x = drv_x + gb_w + 1.5
        s.addRect(QRectF(m(m_x), m(headCY-m_h/2), m(m_w), m(m_h)),
                  pen_visible(0.35), QBrush(C.DRIVE_M))
        add_text(s, m_x+1.5, headCY-m_h/2+2.5, "MOTOR", 2.0, bold=True)
        s.addLine(m(drv_x+gb_w), m(headCY), m(m_x), m(headCY), pen_visible(0.35))
        add_text(s, midX - 18, DA_Y_MM+2.0, "HEAD SECTION", 2.5, bold=True)
        add_text(s, midX - 18, DA_Y_MM+6.5,
                 f"Ø{D_head_mm:.0f}mm · {inp.get('n_rpm','—')}rpm · LAGGED",
                 1.8, color=C.TEXT_MUTED)
        theta_rad = math.radians(float(r.get("theta_rel") or 10))
        chute_len = 16.0
        csx = midX + rH*0.5*math.sin(theta_rad) + chute_len*math.sin(theta_rad)
        csy = headCY - rH*0.5*math.cos(theta_rad) - chute_len*math.cos(theta_rad)
        s.addLine(m(midX+rH*0.4), m(headCY-rH*0.4), m(csx), m(csy), pen_visible(0.5))
        add_text(s, csx+1.5, csy-4.0, "DISCHARGE", 2.0, bold=True, color=QColor("#884400"))

    def _draw_boot_group(self, midX, bootCY, rB, shaft_rB, D_boot_mm):
        s, inp = self.s, self.inp
        s.addEllipse(QRectF(m(midX-rB), m(bootCY-rB), m(rB*2), m(rB*2)),
                     pen_visible(0.5), QBrush(C.PULLEY))
        s.addEllipse(QRectF(m(midX-shaft_rB), m(bootCY-shaft_rB),
                             m(shaft_rB*2), m(shaft_rB*2)),
                     pen_hidden(), QBrush(QColor("#c8c8e0")))
        tu_w, tu_h = 12.0, 6.0
        s.addRect(QRectF(m(midX-tu_w/2), m(bootCY+rB+1.5), m(tu_w), m(tu_h)),
                  pen_visible(0.35), QBrush(QColor("#e8e8d0")))
        add_text(s, midX-tu_w/2+1, bootCY+rB+3.0, "T/U", 2.0, bold=True)
        feed_y = bootCY + rB*0.2
        s.addLine(m(midX-rB-15), m(feed_y), m(midX-rB-0.5), m(feed_y), pen_visible(0.5))
        arrowhead(s, midX-rB-0.5, feed_y, 0, C.AMBER)
        add_text(s, midX-rB-15.5, feed_y-5.0, "FEED", 2.0, bold=True, color=C.AMBER)
        add_text(s, midX - 18, bootCY+rB+9.0, "BOOT / TAKE-UP", 2.3, bold=True)
        add_text(s, midX - 18, bootCY+rB+12.8,
                 f"Ø{D_boot_mm:.0f}mm · {(inp.get('takeup_type') or 'Screw').capitalize()}",
                 1.7, color=C.TEXT_MUTED)

    def _draw_casing_and_internals(self, midX, headCY, bootCY, cx_l, cx_r,
                                   CAS_W, H_draw, rH, rB, shaft_r, shaft_rB,
                                   ext, gb_w, gb_h, m_w, m_h,
                                   D_head_mm, D_boot_mm, BW_mm, spacing_m,
                                   bkt, draw_head=True, draw_boot=True):
        s, inp, r = self.s, self.inp, self.r
        K = r.get("_draw_scale") or 8

        centre_line(s, midX, headCY - rH - 6, midX, bootCY + rB + 6)
        s.addRect(QRectF(m(cx_l), m(headCY), m(CAS_W), m(H_draw)),
                  pen_visible(0.5), QBrush(C.CASING))
        hatch_rect(s, cx_l, headCY, 4, H_draw)
        hatch_rect(s, cx_r-4, headCY, 4, H_draw)

        # Structural elements on top of casing outline
        draw_structural_elements(s, self.inp, self.r, cx_l, cx_r, headCY, bootCY,
                                  CAS_W, H_draw, K)

        belt_off = CAS_W * 0.20
        bltL, bltR = midX - belt_off, midX + belt_off
        s.addLine(m(bltL), m(headCY), m(bltL), m(bootCY), pen_visible(0.5))
        s.addLine(m(bltR), m(headCY), m(bltR), m(bootCY), pen_visible(0.35))

        # Buckets
        pitch_draw = max(0.1, spacing_m * 1000 / K)
        bkt_proj   = max(3.5, (float(bkt.get("P") or 178) * 0.75) / K)
        bkt_h_draw = max(2.5, (float(bkt.get("H") or 216) * 0.55) / K)
        n_vis = min(int(H_draw / pitch_draw) + 1, 24) if pitch_draw > 0 else 0
        for i in range(n_vis):
            by = headCY + i * pitch_draw + pitch_draw * 0.25
            if by + bkt_h_draw > bootCY - 1.5: break
            p = QPainterPath()
            p.moveTo(m(bltL), m(by))
            p.lineTo(m(bltL - bkt_proj), m(by))
            p.quadTo(m(bltL - bkt_proj - 1.2), m(by + bkt_h_draw*0.5),
                     m(bltL - bkt_proj), m(by + bkt_h_draw))
            p.lineTo(m(bltL), m(by + bkt_h_draw))
            p.closeSubpath()
            s.addPath(p, pen_visible(0.35), QBrush(C.BUCKET))

        if draw_head:
            self._draw_head_group(midX, headCY, rH, shaft_r, cx_l, cx_r,
                                  ext, gb_w, gb_h, m_w, m_h, D_head_mm)
        if draw_boot:
            self._draw_boot_group(midX, bootCY, rB, shaft_rB, D_boot_mm)

    def _draw_dimensions(self, midX, headCY, bootCY, cx_l, cx_r,
                         CAS_W, H_draw, rH, H_m, D_head_mm, BW_mm,
                         spacing_m, bkt):
        s = self.s
        dim_v(s, cx_l-4, headCY, cx_l-4, bootCY,
              f"H = {H_m:.0f} m", offset_mm=10, ext_mm=2)
        dim_h(s, midX-rH, headCY-rH-3, midX+rH, headCY-rH-3,
              f"Ø{D_head_mm:.0f}", offset_mm=6, ext_mm=2)
        leader(s, cx_l+2, headCY + H_draw*0.45,
               cx_l - 18, headCY + H_draw*0.45,
               f"BW = {BW_mm:.0f} mm (NTS)", 1.9)
        pitch_draw = spacing_m * 1000 / (self.r.get("_draw_scale") or 8)
        bkt_proj = max(3.5, (float(bkt.get("P") or 178) * 0.75) / (self.r.get("_draw_scale") or 8))
        belt_off = CAS_W * 0.20
        bltL = midX - belt_off
        if pitch_draw > 6:
            leader(s, bltL - bkt_proj*0.5,
                   headCY + pitch_draw*0.5,
                   bltL - bkt_proj - 7,
                   headCY + pitch_draw*0.5,
                   f"SPC {round(spacing_m*1000)} mm", 1.9)


# ── Scene builder ─────────────────────────────────────────────────────────────
def build_scene(inputs: dict, results: dict,
                sign_off: Optional[dict] = None,
                drawing_scale: Optional[int] = None) -> QGraphicsScene:
    scene = QGraphicsScene()
    scene.setSceneRect(QRectF(m(-5), m(-5), m(A3_W_MM+10), m(A3_H_MM+10)))
    # Draw the elevation FIRST so it computes and stores the scale in
    # results['_draw_scale'] before the title block reads it -- fixes the
    # "SCALE 1:?" bug where the title block was built before the scale
    # was ever computed.
    ElevationCADDraw(scene, inputs, results, drawing_scale)
    CADTemplate(scene, inputs, results, sign_off)
    return scene


# ── View widget ───────────────────────────────────────────────────────────────
class CADSchematicView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing |
            QPainter.RenderHint.TextAntialiasing |
            QPainter.RenderHint.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        # NoDrag (not ScrollHandDrag) -- ScrollHandDrag captures ALL
        # left-click-drags for panning the view, which prevents any
        # QGraphicsItem from ever receiving a drag (movable views could
        # never be dragged). NoDrag lets Qt's normal item-drag behavior
        # work: click-drag on a SnapGroup moves that view; click-drag on
        # empty background does nothing. Panning is now on the middle
        # mouse button instead (see mousePressEvent/mouseMoveEvent below).
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setBackgroundBrush(QBrush(QColor("#888888")))
        self._panning = False
        self._pan_start = None

    def wheelEvent(self, event):
        f = 1.15 if event.angleDelta().y() > 0 else 0.87
        self.scale(f, f)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning and self._pan_start is not None:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()
            h_bar = self.horizontalScrollBar()
            v_bar = self.verticalScrollBar()
            h_bar.setValue(h_bar.value() - int(delta.x()))
            v_bar.setValue(v_bar.value() - int(delta.y()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton and self._panning:
            self._panning = False
            self._pan_start = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def fit_sheet(self):
        if self.scene():
            self.fitInView(QRectF(m(-2), m(-2), m(A3_W_MM+4), m(A3_H_MM+4)),
                           Qt.AspectRatioMode.KeepAspectRatio)

    def set_drawing(self, inputs: dict, results: dict,
                    sign_off: Optional[dict] = None,
                    drawing_scale: Optional[int] = None):
        scene = build_scene(inputs, results, sign_off, drawing_scale)
        self.setScene(scene)
        self.fit_sheet()


class ElevationCADWidget(QWidget):
    """Drop-in widget for the Elevation 'Eng. Drawing' tab. Includes a
    scale selector (default 1:8, per Jay's spec) that lets the user
    override the auto-fit scale. When the elevator doesn't fit at the
    chosen scale, the drawing automatically switches to a broken
    (2-segment) vertical view rather than silently coarsening the scale."""

    SCALE_OPTIONS = [1, 2, 5, 8, 10, 20, 25, 50, 100, 125, 200, 250, 500]

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(6, 4, 6, 4)
        from PySide6.QtWidgets import QLabel, QComboBox
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
        self._scale_combo.addItem("Auto-fit (default 1:8)", None)
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
        self._view.set_drawing(inputs, results, sign_off, chosen_scale)

    def fit(self):
        self._view.fit_sheet()