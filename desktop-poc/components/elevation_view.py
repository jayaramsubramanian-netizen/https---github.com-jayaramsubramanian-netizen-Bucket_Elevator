"""
components/elevation_view.py -- PySide6/QPainter port of ElevatorSchematic.jsx.
═══════════════════════════════════════════════════════════════════════════
Full multi-view schematic, not just the single Elevation drawing this file
used to contain. Ported view-by-view from the real 1101-line JSX (read
directly, not assumed): Elevation, Head Plan, Side Elevation, Trajectory,
Bucket Detail -- same variable names, same geometry formulas as the source
throughout, so this stays directly comparable line-for-line.

Architecture: `ElevationView` (the name main.py already imports and wires
into the Results tab splitter) is now the full container -- tab bar,
zoom/pan controls, overlay stat cards, hover status bar -- matching the
JSX's default-exported `ElevatorSchematic` component. The actual drawing
surface is `_SchematicCanvas`, a QWidget whose paintEvent dispatches to one
of five `_paint_<view>()` methods depending on the active tab, with a
QTransform applied first for zoom/pan (mirroring the JSX's CSS
`transform: translate(...) scale(...)`).

Hover callouts: the JSX tracks hover via onMouseEnter/onMouseLeave on
individual SVG <g> elements. QPainter has no per-shape hit-testing, so each
_paint_<view>() method records {region_name: QRectF} into
self._hover_regions during painting (in canvas/unscaled coordinates), and
mouseMoveEvent checks the cursor position (transformed back through the
zoom/pan) against those rects to decide what's hovered, then triggers a
repaint to show the callout box -- functionally equivalent to the JSX's
per-element hover state.
"""
import math
from typing import Optional, Callable

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton
from PySide6.QtCore import Qt, QRectF, QPointF, QTimer
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPainterPath, QPolygonF, QTransform, QCursor

from theme import (
    DRAWING as C, PANEL, PANEL2, SURFACE, BORDER, BORDER2,
    TEXT, TEXT2, TEXT3, PRIMARY, PRIMARY_DIM, SUCCESS, WARNING, DANGER,
    R_SM, scoped, plain_bg,
)
from .dialog_helpers import KPIChip


def f(v, dp=1, fb="—"):
    """Port of the f() helper."""
    if v is None:
        return fb
    try:
        return f"{float(v):.{dp}f}"
    except (TypeError, ValueError):
        return fb


def qc(hexstr, alpha=255):
    c = QColor(hexstr)
    c.setAlpha(alpha)
    return c


VIEWS = [
    ("elevation", "Elevation"),
    ("plan",      "Head Plan"),
    ("side",      "Side Elevation"),
    ("trajectory","Trajectory"),
    ("bucket",    "Bucket Detail"),
    ("cad",       "Eng. Drawing"),   # ISO A3 QGraphicsScene CAD view
    ("cad_side",  "Side Eng. Drawing"),  # ISO A3 side elevation CAD view
    ("cad_head",  "Head Detail"),        # ISO A3 head + discharge chute + trajectory
    ("cad_bucket","Bucket Drawing"),     # ISO A3 bucket front/profile/bolt-hole detail
    # ^ was ALSO labelled "Bucket Detail" -- identical to the QPainter
    #   "bucket" tab above it. Two visually identical tabs in one bar doing
    #   different things. Renamed to match how cad/cad_side are already
    #   distinguished ("Eng. Drawing").
]

SVG_W, SVG_H = 580, 460   # matches the JSX's fixed internal drawing canvas size


class _SchematicCanvas(QWidget):
    """The actual drawing surface -- dispatches to one of 5 view painters,
    handles zoom (wheel) / pan (drag) / hover (mouse move + region hit-test),
    same interaction model as the JSX's container div."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.inputs = {}
        self.results = {}
        self.view = "elevation"
        self.zoom = 1.0
        self.pan = QPointF(0, 0)
        self._dragging = False
        self._drag_start = QPointF(0, 0)
        self._pan_start = QPointF(0, 0)
        self.hovered = None
        self._hover_regions = {}   # {name: QRectF} in canvas (pre-transform) coords
        self.on_hover_changed: Optional[Callable[[Optional[str]], None]] = None   # callback(name_or_None) for the status bar

    def set_data(self, inputs, results):
        self.inputs = inputs or {}
        self.results = results or {}
        self.update()

    def set_view(self, view_id):
        self.view = view_id
        self.zoom = 1.0
        self.pan = QPointF(0, 0)
        self.hovered = None
        self.update()

    def reset_view(self):
        self.zoom = 1.0
        self.pan = QPointF(0, 0)
        self.update()

    # ── Interaction ──────────────────────────────────────────────────
    def wheelEvent(self, event):
        factor = 1.12 if event.angleDelta().y() > 0 else 0.89
        self.zoom = min(4.0, max(0.25, self.zoom * factor))
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_start = event.position()
            self._pan_start = QPointF(self.pan)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self._dragging:
            delta = event.position() - self._drag_start
            self.pan = self._pan_start + delta
            self.update()
            return
        # Hover hit-test: transform cursor pos back to canvas coordinates
        canvas_pt = self._screen_to_canvas(event.position())
        hit = None
        for name, rect in self._hover_regions.items():
            if rect.contains(canvas_pt):
                hit = name
                break
        if hit != self.hovered:
            self.hovered = hit
            if self.on_hover_changed:
                self.on_hover_changed(hit)
            self.update()

    def mouseReleaseEvent(self, event):
        self._dragging = False
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def leaveEvent(self, event):
        if self.hovered is not None:
            self.hovered = None
            if self.on_hover_changed:
                self.on_hover_changed(None)
            self.update()

    def mouseDoubleClickEvent(self, event):
        self.reset_view()

    def _canvas_transform(self):
        """Same transform as the JSX's `translate(pan) scale(zoom)`,
        centered on the widget, mapping the fixed SVG_W x SVG_H internal
        canvas to fit this widget's actual size (letterboxed)."""
        w, h = self.width(), self.height()
        base_scale = min(w / SVG_W, h / SVG_H) if w and h else 1.0
        t = QTransform()
        t.translate(w / 2 + self.pan.x(), h / 2 + self.pan.y())
        t.scale(self.zoom * base_scale, self.zoom * base_scale)
        t.translate(-SVG_W / 2, -SVG_H / 2)
        return t

    def _screen_to_canvas(self, pos):
        inv, ok = self._canvas_transform().inverted()
        if not ok:
            return QPointF(pos)
        return inv.map(QPointF(pos))

    # ── Paint dispatch ───────────────────────────────────────────────
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.fillRect(self.rect(), qc(C["bg"]))

        self._hover_regions = {}
        p.save()
        p.setTransform(self._canvas_transform(), True)
        # Clip to the internal canvas so nothing draws outside it even at
        # high zoom -- matches the JSX's overflow:hidden container.
        p.setClipRect(QRectF(0, 0, SVG_W, SVG_H))

        dispatch = {
            "elevation": self._paint_elevation,
            "plan": self._paint_plan,
            "side": self._paint_side,
            "trajectory": self._paint_trajectory,
            "bucket": self._paint_bucket_detail,
        }
        dispatch.get(self.view, self._paint_elevation)(p)
        p.restore()
        p.end()

    # ── Shared drawing helpers (ported from Dim/Callout/text JSX fns) ──
    def _text(self, p, x, y, text, size, color, bold=False, center=False, right=False):
        font = QFont()
        font.setPointSizeF(size)
        font.setBold(bold)
        p.setFont(font)
        p.setPen(QPen(qc(color)))
        metrics = p.fontMetrics()
        w = metrics.horizontalAdvance(text)
        if center:
            x -= w / 2
        elif right:
            x -= w
        p.drawText(QPointF(x, y + size * 0.35), text)

    def _draw_arrowhead(self, p, x, y, angle_deg, color):
        size = 5
        rad = math.radians(angle_deg)
        tip = QPointF(x, y)
        back1 = QPointF(x - size * math.cos(rad - 0.4), y - size * math.sin(rad - 0.4))
        back2 = QPointF(x - size * math.cos(rad + 0.4), y - size * math.sin(rad + 0.4))
        p.setBrush(QBrush(color))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPolygon(QPolygonF([tip, back1, back2]))

    def _dim_horizontal(self, p, x1, y1, x2, y2, label, offset, side, size=8.5):
        dy = y1 - side * offset
        p.setPen(QPen(qc(C["dim"]), 0.6))
        p.drawLine(QPointF(x1, y1), QPointF(x1, dy - side * 4))
        p.drawLine(QPointF(x2, y2), QPointF(x2, dy - side * 4))
        p.setPen(QPen(qc(C["dim"]), 0.8))
        p.drawLine(QPointF(x1, dy), QPointF(x2, dy))
        self._text(p, (x1 + x2) / 2, dy - 4, label, size, C["labelBr"], center=True)

    def _dim_vertical(self, p, x1, y1, x2, y2, label, offset, side, size=8.5):
        dx = x1 + side * offset
        p.setPen(QPen(qc(C["dim"]), 0.6))
        p.drawLine(QPointF(x1, y1), QPointF(dx + side * 4, y1))
        p.drawLine(QPointF(x2, y2), QPointF(dx + side * 4, y2))
        p.setPen(QPen(qc(C["dim"]), 0.8))
        p.drawLine(QPointF(dx, y1), QPointF(dx, y2))
        p.save()
        mid_y = (y1 + y2) / 2
        p.translate(dx - side * 3, mid_y)
        p.rotate(-90)
        self._text(p, 0, 0, label, size, C["labelBr"], center=True)
        p.restore()

    def _grid(self, p, W, H):
        p.setPen(QPen(QColor(59, 130, 246, 10), 0.5))
        for x in range(0, int(W) + 1, 20):
            p.drawLine(QPointF(x, 0), QPointF(x, H))
        for y in range(0, int(H) + 1, 20):
            p.drawLine(QPointF(0, y), QPointF(W, y))

    def _title_block(self, p, W, H, view_name):
        r, inp = self.results, self.inputs
        bkt = r.get("bucket") or {}
        bw, bh = 200, 54
        bx, by = W - bw - 4, H - bh - 4
        p.setPen(QPen(qc(C["dim"]), 0.8))
        p.setBrush(QBrush(qc(C["panel"])))
        p.drawRect(QRectF(bx, by, bw, bh))
        p.setPen(QPen(qc(C["dim"]), 0.5))
        p.drawLine(QPointF(bx, by + 16), QPointF(bx + bw, by + 16))
        p.drawLine(QPointF(bx, by + 32), QPointF(bx + bw, by + 32))
        p.drawLine(QPointF(bx + 100, by + 16), QPointF(bx + 100, by + bh))
        self._text(p, bx + bw / 2, by + 11, "VECTOMEC™ BUCKET ELEVATOR", 8, C["labelBr"], bold=True, center=True)
        self._text(p, bx + 4, by + 25,
                    f"BUCKET: {bkt.get('id','—')} · {bkt.get('W','—')}×{bkt.get('H','—')}mm · H = {inp.get('H_m','—')} m",
                    7, C["text3"])
        self._text(p, bx + 4, by + 41, view_name.upper() + " VIEW", 7, C["text3"])
        self._text(p, bx + 104, by + 41, f"D = {inp.get('D_mm','—')} mm", 7, C["text3"])
        self._text(p, bx + 4, by + 52, "JAYVEECONS · VECTRIX™", 6, C["label"])

    def _no_data(self, p, W, H, view_name):
        self._grid(p, W, H)
        self._text(p, W / 2, H / 2, "No trajectory data — run calculation first", 12, C["text3"], center=True)
        self._title_block(p, W, H, view_name)

    # ═══════════════════════════════════════════════════════════════
    # ELEVATION VIEW -- unchanged from the previous single-view port
    # ═══════════════════════════════════════════════════════════════
    def _paint_elevation(self, p):
        W, H = SVG_W, SVG_H
        inp, r = self.inputs, self.results
        bkt = r.get("bucket") or {}
        p.fillRect(QRectF(0, 0, W, H), qc(C["bg"]))
        self._grid(p, W, H)

        margin = {"top": 56, "bottom": 68, "left": 52, "right": 120}
        cx = W * 0.36

        headD = float(inp.get("D_mm") or 500)
        boot_pulley = r.get("boot_pulley") or {}
        bootD = float(boot_pulley.get("boot_D_mm") or inp.get("boot_pulley_D_mm") or 300)
        maxD = max(headD, bootD, 1)
        PULLEY_PX_MAX, PULLEY_PX_MIN = 32, 10
        pScale = PULLEY_PX_MAX / maxD
        rH = max(PULLEY_PX_MIN, headD * pScale)
        rB = max(PULLEY_PX_MIN, bootD * pScale)

        casW = max(rH, rB) + 18
        topY = margin["top"] + rH
        botY = H - margin["bottom"] - rB
        elevH = botY - topY
        bltL = cx - max(rH, rB) * 0.55
        bltR = cx + max(rH, rB) * 0.55

        spacingM = r.get("spacing") or 0.20
        H_m = float(inp.get("H_m") or 25)
        pxPerMeter = elevH / max(H_m, 1)
        spacePx = max(8.0, spacingM * pxPerMeter)
        bktH_px = max(4.0, spacePx * 0.72)
        projMM = float(bkt.get("P") or bkt.get("W") or 178)
        bktW_px = min(casW - 4, max(6.0, projMM * pxPerMeter * 0.001 * 0.9))

        realCount = r.get("n_buckets") or round((2 * H_m) / spacingM)
        nVisible = min(int(elevH // spacePx) + 2, 30)
        carryBuckets = [botY - i * spacePx - bktH_px * 0.5 for i in range(nVisible)]
        nReturn = math.ceil(nVisible * 0.55)
        returnBuckets = [topY + i * spacePx * 1.2 + bktH_px * 0.5 for i in range(nReturn)]

        theta_rel = r.get("theta_rel")
        thetaRad = math.radians(theta_rel if theta_rel is not None else 10)
        chuteLen = 48
        chuteBaseX, chuteBaseY = cx + rH * 0.5, topY - rH * 0.5
        chuteTipX = chuteBaseX + math.sin(thetaRad) * chuteLen
        chuteTipY = chuteBaseY - math.cos(thetaRad) * chuteLen

        self._hover_regions["casing"] = QRectF(cx - casW, topY, casW * 2, elevH)

        p.setPen(QPen(qc(C["casing"]), 2))
        p.setBrush(QBrush(qc(C["casFill"])))
        p.drawRect(QRectF(cx - casW, topY, casW * 2, elevH))

        p.setPen(QPen(qc(C["dim"]), 0.7, Qt.PenStyle.DashLine))
        p.drawLine(QPointF(cx, topY - 12), QPointF(cx, botY + 12))

        p.setPen(QPen(qc(C["belt"]), 3.5))
        p.drawLine(QPointF(bltL, topY), QPointF(bltL, botY))
        p.setPen(QPen(qc(C["beltRtn"], 165), 2.5))
        p.drawLine(QPointF(bltR, topY), QPointF(bltR, botY))

        p.setClipRect(QRectF(cx - casW, topY, casW * 2, elevH), Qt.ClipOperation.IntersectClip)
        for by_ in carryBuckets:
            path = QPainterPath()
            path.moveTo(bltL, by_ - bktH_px * 0.5)
            path.lineTo(bltL - bktW_px, by_ - bktH_px * 0.5)
            path.quadTo(bltL - bktW_px - 3, by_, bltL - bktW_px, by_ + bktH_px * 0.5)
            path.lineTo(bltL, by_ + bktH_px * 0.5)
            path.closeSubpath()
            p.setPen(QPen(qc(C["casing"]), 0.6))
            p.setBrush(QBrush(qc(C["bucket"], 209)))
            p.drawPath(path)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(qc(C["belt"], 77)))
            p.drawRoundedRect(QRectF(bltL - bktW_px + 1, by_, max(1.0, bktW_px - 3), bktH_px * 0.35), 1, 1)

        for by_ in returnBuckets:
            path = QPainterPath()
            path.moveTo(bltR, by_ + bktH_px * 0.5)
            path.lineTo(bltR + bktW_px, by_ + bktH_px * 0.5)
            path.quadTo(bltR + bktW_px + 3, by_, bltR + bktW_px, by_ - bktH_px * 0.5)
            path.lineTo(bltR, by_ - bktH_px * 0.5)
            path.closeSubpath()
            p.setPen(QPen(qc(C["casing"], 128), 0.5))
            p.setBrush(QBrush(qc(C["bucket"], 56)))
            p.drawPath(path)
        p.setClipRect(QRectF(0, 0, SVG_W, SVG_H))

        self._hover_regions["boot"] = QRectF(cx - rB - 20, botY - rB - 4, (rB + 20) * 2, (rB + 4) * 2 + 20)
        p.setPen(QPen(qc(C["hub"]), 2))
        p.setBrush(QBrush(qc(C["pulley"], 217)))
        p.drawEllipse(QPointF(cx, botY), rB, rB)
        p.setBrush(QBrush(qc(C["hub"])))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, botY), rB * 0.3, rB * 0.3)
        p.setPen(QPen(qc(C["dim"]), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(cx - rB - 16, botY), QPointF(cx - rB, botY))
        p.drawLine(QPointF(cx + rB, botY), QPointF(cx + rB + 16, botY))
        p.setPen(QPen(qc(C["dim"]), 1))
        p.setBrush(QBrush(qc(C["casing"])))
        p.drawRoundedRect(QRectF(cx - 9, botY + rB + 4, 18, 18), 2, 2)
        self._text(p, cx, botY + rB + 16, "T/U", 6, C["text3"], bold=True, center=True)
        p.setPen(QPen(qc(C["dim"]), 1))
        p.drawLine(QPointF(cx, botY + rB + 2), QPointF(cx, botY + rB + 4))

        self._hover_regions["head"] = QRectF(cx - rH - 20, topY - rH - 4, (rH + 20) * 2, (rH + 4) * 2)
        p.setPen(QPen(qc(C["lagging"], 140), 4))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, topY), rH + 3, rH + 3)
        p.setPen(QPen(qc(C["hub"]), 2))
        p.setBrush(QBrush(qc(C["pulley"], 217)))
        p.drawEllipse(QPointF(cx, topY), rH, rH)
        p.setPen(QPen(qc(C["hub"], 102), 0.9))
        for k in (-1, 0, 1):
            p.drawLine(QPointF(cx + k * rH * 0.38, topY - rH * 0.82),
                       QPointF(cx + k * rH * 0.38, topY + rH * 0.82))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(qc(C["hub"])))
        p.drawEllipse(QPointF(cx, topY), rH * 0.28, rH * 0.28)
        p.setPen(QPen(qc(C["dim"]), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(cx - rH - 18, topY), QPointF(cx - rH, topY))
        p.drawLine(QPointF(cx + rH, topY), QPointF(cx + rH + 18, topY))

        chute_path = QPainterPath()
        chute_path.moveTo(chuteBaseX - 6, chuteBaseY)
        chute_path.lineTo(chuteTipX, chuteTipY)
        chute_path.lineTo(chuteTipX + 10, chuteTipY + 6)
        chute_path.lineTo(chuteBaseX + 6, chuteBaseY + 8)
        chute_path.closeSubpath()
        self._hover_regions["chute"] = chute_path.boundingRect().adjusted(-4, -4, 4, 4)
        p.setPen(QPen(qc(C["chute"]), 1.4))
        p.setBrush(QBrush(qc(C["chute"], 20)))
        p.drawPath(chute_path)
        self._text(p, chuteTipX + 16, chuteTipY, "DISCHARGE", 7.5, C["chute"], bold=True)
        self._text(p, chuteTipX + 16, chuteTipY + 11, f"θ={f(theta_rel, 0)}°", 6.5, C["label"])

        p.setPen(QPen(qc(C["dim"]), 1.5, Qt.PenStyle.DashLine))
        p.drawLine(QPointF(cx + rH + 16, topY + rH * 0.5), QPointF(cx + casW + 10, topY + rH * 0.5))
        self._hover_regions["drive"] = QRectF(cx + casW + 15, topY + rH * 0.5 - 16, 60, 55)
        p.setPen(QPen(qc(C["hub"]), 1))
        p.setBrush(QBrush(qc(C["coupling"])))
        p.drawEllipse(QPointF(cx + casW + 18, topY + rH * 0.5), 5, 8)
        p.setPen(QPen(QColor("#047857"), 1))
        p.setBrush(QBrush(qc(C["gearbox"], 191)))
        p.drawRoundedRect(QRectF(cx + casW + 23, topY + rH * 0.5 - 12, 22, 24), 2, 2)
        self._text(p, cx + casW + 34, topY + rH * 0.5 + 4, "GB", 7, "#ffffff", bold=True, center=True)
        p.setPen(QPen(QColor("#065f46"), 1))
        p.setBrush(QBrush(qc(C["motor"], 204)))
        p.drawRoundedRect(QRectF(cx + casW + 45, topY + rH * 0.5 - 10, 28, 20), 2, 2)
        self._text(p, cx + casW + 59, topY + rH * 0.5 + 3, "M", 8, "#ffffff", bold=True, center=True)
        self._text(p, cx + casW + 22, topY + rH * 0.5 + 30, f"{r.get('motor_kw', '—')} kW motor", 7, C["text3"])

        p.setPen(QPen(qc(C["feed"]), 2))
        p.drawLine(QPointF(cx - casW - 34, botY), QPointF(cx - casW - 4, botY))
        self._draw_arrowhead(p, cx - casW - 4, botY, 0, qc(C["feed"]))
        self._text(p, cx - casW - 38, botY - 5, "FEED", 7.5, C["feed"], bold=True, right=True)

        self._dim_vertical(p, cx - casW - 4, botY, cx - casW - 4, topY, f"H = {f(H_m, 0)} m", offset=24, side=-1)
        self._dim_horizontal(p, bltL, topY - rH - 6, bltR, topY - rH - 6, f"BW = {r.get('belt_w', '—')} mm", offset=16, side=1)
        if spacePx > 16:
            self._dim_vertical(p, cx + casW + 8, botY - 12, cx + casW + 8, botY - 12 - spacePx,
                                f"{round(spacingM * 1000)}mm", offset=20, side=1)

        self._text(p, cx, 10, "HEAD SECTION", 9, C["labelBr"], bold=True, center=True)
        self._text(p, cx, 21, f"Ø{headD:.0f}mm · {inp.get('n_rpm', '—')}rpm · Lagged", 7, C["label"], center=True)
        self._text(p, cx, botY + rB + 36, "BOOT / TAKE-UP", 9, C["labelBr"], bold=True, center=True)
        self._text(p, cx, botY + rB + 46, f"Ø{bootD:.0f}mm · Gravity", 7, C["label"], center=True)
        self._text(p, cx + rB + 6, botY + 4, f"DB = {bootD:.0f} mm", 7.5, C["text3"])

        footer = (f"BUCKET {bkt.get('id', '—')} · {bkt.get('W', '—')}×{bkt.get('H', '—')}mm · "
                  f"{bkt.get('V', '—')}L · {realCount} buckets total · spacing {round(spacingM * 1000)}mm")
        self._text(p, W / 2, H - 6, footer, 7.5, C["label"], center=True)
        self._title_block(p, W, H, "elevation")

    # ═══════════════════════════════════════════════════════════════
    # PLAN VIEW -- port of PlanView() from ElevatorSchematic.jsx
    # ═══════════════════════════════════════════════════════════════
    def _paint_plan(self, p):
        W, H = SVG_W, SVG_H
        r, inp = self.results, self.inputs
        p.fillRect(QRectF(0, 0, W, H), qc(C["bg"]))
        self._grid(p, W, H)

        BW = float(r.get("belt_w") or inp.get("D_mm") or 300)
        D = float(inp.get("D_mm") or 500)
        dShaft = float(r.get("d_mm") or 60)
        CW = BW + 120
        PL = BW + 50
        bkt = r.get("bucket") or {}
        CD = float(bkt.get("P") or 130) + 120

        scale = min((W - 140) / CW, (H - 140) / (CD + 80))
        cw, cd, pl, bw = CW * scale, CD * scale, PL * scale, BW * scale
        cx, cy = W / 2, H / 2 + 10
        dSh = dShaft * scale

        bhW = max(dSh * 2.6, 16)
        bh = max(dSh * 2.4, 20)

        self._text(p, W / 2, 18, "HEAD SECTION — PLAN VIEW", 10, C["text3"], bold=True, center=True)
        self._text(p, W / 2, 30, "Top-down cross-section at head pulley centre-line", 7.5, C["label"], center=True)

        self._hover_regions["casing"] = QRectF(cx - cw / 2, cy - cd / 2, cw, cd)
        p.setPen(QPen(qc(C["casing"]), 2))
        p.setBrush(QBrush(qc(C["casFill"])))
        p.drawRect(QRectF(cx - cw / 2, cy - cd / 2, cw, cd))
        p.setPen(QPen(qc(C["casing"]), 0.5, Qt.PenStyle.DashLine))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(QRectF(cx - cw / 2 + 8 * scale, cy - cd / 2 + 8 * scale, cw - 16 * scale, cd - 16 * scale))

        self._hover_regions["head"] = QRectF(cx - pl / 2 - 5 * scale, cy - D * scale / 2 - 6 * scale,
                                              pl + 10 * scale, D * scale + 12 * scale)
        p.setPen(QPen(qc(C["lagging"], 153), 3.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(QRectF(cx - pl / 2 - 5 * scale, cy - D * scale / 2 - 6 * scale, pl + 10 * scale, D * scale + 12 * scale))
        p.setPen(QPen(qc(C["hub"]), 1.5))
        p.setBrush(QBrush(qc(C["pulley"], 191)))
        p.drawRect(QRectF(cx - pl / 2, cy - D * scale / 2, pl, D * scale))
        p.setPen(QPen(qc(C["hub"], 102), 0.8))
        for k in (-0.3, 0, 0.3):
            p.drawLine(QPointF(cx + k * pl * 0.35, cy - D * scale / 2), QPointF(cx + k * pl * 0.35, cy + D * scale / 2))

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(qc(C["dim"], 178)))
        p.drawRect(QRectF(cx - cw / 2 - bhW - 10, cy - dSh / 2, cw + 2 * (bhW + 10), dSh))
        p.setPen(QPen(qc(C["dimTxt"]), 0.8, Qt.PenStyle.DashLine))
        p.drawLine(QPointF(cx - cw / 2 - bhW - 20, cy), QPointF(cx + cw / 2 + bhW + 20, cy))

        p.setPen(QPen(qc(C["belt"]), 2))
        p.drawLine(QPointF(cx - bw / 2, cy - cd / 2 - 10), QPointF(cx - bw / 2, cy + cd / 2 + 10))
        p.drawLine(QPointF(cx + bw / 2, cy - cd / 2 - 10), QPointF(cx + bw / 2, cy + cd / 2 + 10))

        self._hover_regions["bearings"] = QRectF(cx - cw / 2 - bhW - 10, cy - bh / 2, cw + 2 * (bhW + 10), bh)
        for side in (-1, 1):
            bx = cx - cw / 2 - bhW - 10 if side < 0 else cx + cw / 2 + 10
            p.setPen(QPen(qc(C["motor"]), 1.2))
            p.setBrush(QBrush(qc(C["gearbox"], 128)))
            p.drawRect(QRectF(bx, cy - bh / 2, bhW, bh))
            p.setPen(QPen(qc(C["dim"]), 0.8))
            p.setBrush(QBrush(qc(C["hub"])))
            for d in (-1, 1):
                rr = max(1.5, bhW * 0.08)
                p.drawEllipse(QPointF(bx + bhW / 2, cy + d * bh * 0.34), rr, rr)
            self._text(p, bx + bhW / 2, cy - bh / 2 - 5 if side < 0 else cy + bh / 2 + 11, "BRG", 6.5, C["labelBr"], bold=True, center=True)

        bktW_plan = float(bkt.get("W") or 250) * scale * 0.5
        bktD_plan = 18 * scale
        bktSpacing = (float(r.get("spacing") or 0.20) * 1000) * scale * 0.4
        p.setPen(QPen(qc(C["casing"]), 0.8))
        p.setBrush(QBrush(qc(C["bucket"], 153)))
        for i in (-2, -1, 0, 1, 2):
            p.drawRoundedRect(QRectF(cx - bktW_plan / 2, cy - bktD_plan / 2 + i * bktSpacing, bktW_plan, bktD_plan), 1, 1)

        self._dim_horizontal(p, cx - bw / 2, cy + cd / 2 + 14, cx + bw / 2, cy + cd / 2 + 14, f"BW = {BW:.0f} mm", offset=18, side=1)
        self._dim_horizontal(p, cx - cw / 2, cy - cd / 2 - 22, cx + cw / 2, cy - cd / 2 - 22, f"Casing = {CW:.0f} mm", offset=16, side=1)
        self._dim_horizontal(p, cx - pl / 2, cy - cd / 2 - 42, cx + pl / 2, cy - cd / 2 - 42, f"Pulley face = {PL:.0f} mm", offset=16, side=1)
        self._dim_vertical(p, cx - cw / 2 - bhW - 10, cy - dSh / 2, cx - cw / 2 - bhW - 10, cy + dSh / 2, f"d = {f(dShaft,0)} mm", offset=20, side=-1)
        self._dim_vertical(p, cx + cw / 2 + bhW + 22, cy - D * scale / 2, cx + cw / 2 + bhW + 22, cy + D * scale / 2, f"D = {D:.0f} mm", offset=22, side=1)

        self._title_block(p, W, H, "plan")
        self._draw_hover_callout(p, W, H, {
            "head": ("HEAD PULLEY", [f"D = {D:.0f} mm", f"Pulley face = {PL:.0f} mm", "Lagged — amber ring", f"Shaft Ø{f(dShaft,0)} mm"], cx + pl / 2 + 10, cy - 40),
            "bearings": ("BEARINGS (×2)", [
                f"L10 = {(r.get('L10') or 0)/1000:.0f}k h" if (r.get('L10') or 0) > 9999 else f"L10 = {f(r.get('L10'),0)} h",
                f"Load: {f((r.get('R_headshaft') or 0)/1000 if r.get('R_headshaft') is not None else None,2)} kN",
                "ISO 281 · C = 355 kN", f"Housing ≈ {bhW/scale:.0f}×{bh/scale:.0f}mm",
            ], cx, cy + bh / 2 + 40),
            "casing": ("CASING (PLAN)", [f"Width: {CW:.0f} mm  (BW + 120)", f"Depth: {CD:.0f} mm  (P + 120)", f"H = {inp.get('H_m','—')} m total"], cx, cy),
        })

    # ═══════════════════════════════════════════════════════════════
    # SIDE ELEVATION -- port of SideView()
    # ═══════════════════════════════════════════════════════════════
    def _paint_side(self, p):
        W, H = SVG_W, SVG_H
        r, inp = self.results, self.inputs
        p.fillRect(QRectF(0, 0, W, H), qc(C["bg"]))
        self._grid(p, W, H)

        bkt = r.get("bucket") or {}
        CD = float(bkt.get("P") or 130) + 120
        H_m = float(inp.get("H_m") or 25)
        D = float(inp.get("D_mm") or 500)
        boot_pulley = r.get("boot_pulley") or {}
        bootD = float(boot_pulley.get("boot_D_mm") or inp.get("boot_pulley_D_mm") or 300)

        scale = min((W - 100) / (CD + 180), (H - 140) / (H_m * 38 + D * 0.6))
        casDepth = CD * scale
        elevH_px = H_m * 38 * scale
        rH_px, rB_px = (D / 2) * scale, (bootD / 2) * scale
        cx = W / 2
        topY = 64 + rH_px
        botY = topY + elevH_px

        self._text(p, W / 2, 18, "SIDE ELEVATION — COMPLETE ELEVATOR", 10, C["text3"], bold=True, center=True)
        self._text(p, W / 2, 30, "Viewed from drive side  ·  Casing depth shown", 7.5, C["label"], center=True)
        self._dim_horizontal(p, cx - casDepth / 2, 62, cx + casDepth / 2, 62, f"Casing depth = {CD:.0f} mm", offset=14, side=1)

        p.setPen(QPen(qc(C["casing"]), 2))
        p.setBrush(QBrush(qc(C["casFill"])))
        p.drawRect(QRectF(cx - casDepth / 2, topY, casDepth, elevH_px))

        for side in (-1, 1):
            p.setPen(QPen(qc(C["dim"]), 0.8))
            p.setBrush(QBrush(qc(C["leg"])))
            leg_x = cx + side * (casDepth / 2 + 4)
            p.drawRect(QRectF(leg_x, topY + elevH_px * 0.15, 10 * scale, elevH_px * 0.85))
            p.setPen(QPen(qc(C["leg"], 178), 1.5))
            x1 = cx + side * (casDepth / 2 + 4 + (10 * scale if side > 0 else 0))
            x2 = cx + side * (casDepth / 2 + 8 + 30 * scale)
            p.drawLine(QPointF(x1, topY + elevH_px * 0.15), QPointF(x2, topY + elevH_px * 0.6))

        p.setPen(QPen(qc(C["hub"]), 1.5))
        p.setBrush(QBrush(qc(C["pulley"], 153)))
        p.drawRect(QRectF(cx - casDepth / 2 - 10, topY - rH_px / 3, casDepth + 20, rH_px / 1.5))
        p.setPen(QPen(qc(C["lagging"], 128), 3))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(QRectF(cx - casDepth / 2 - 14, topY - rH_px / 3 - 4, casDepth + 28, rH_px / 1.5 + 8))
        self._text(p, cx, topY, "HEAD", 8, "#ffffff", bold=True, center=True)

        p.setPen(QPen(qc(C["hub"]), 1))
        p.setBrush(QBrush(qc(C["pulley"], 128)))
        p.drawRect(QRectF(cx - casDepth / 2 - 8, botY - rB_px / 4, casDepth + 16, rB_px / 2))

        p.setPen(QPen(qc(C["dimTxt"]), 0.8, Qt.PenStyle.DashLine))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for frac in (0.25, 0.55, 0.78):
            p.drawRect(QRectF(cx - casDepth / 4, topY + elevH_px * frac, casDepth / 2, elevH_px * 0.07))

        p.setPen(QPen(qc(C["dim"]), 0.8))
        p.setBrush(QBrush(qc(C["leg"], 178)))
        p.drawRect(QRectF(cx + casDepth / 2 + 14, topY - 16, 44 * scale, 9 * scale))
        self._text(p, cx + casDepth / 2 + 16 + 22 * scale, topY - 20, "DRIVE", 6.5, C["label"], center=True)

        p.setPen(QPen(qc(C["belt"], 153), 2))
        p.drawLine(QPointF(cx - casDepth / 4, topY), QPointF(cx - casDepth / 4, botY))
        p.setPen(QPen(qc(C["beltRtn"], 102), 1.5))
        p.drawLine(QPointF(cx + casDepth / 4, topY), QPointF(cx + casDepth / 4, botY))

        self._dim_vertical(p, cx - casDepth / 2 - 30, topY, cx - casDepth / 2 - 30, botY, f"H = {f(H_m,0)} m", offset=24, side=-1)
        self._text(p, cx, botY + rB_px / 2 + 18, "BOOT / T/U", 8.5, C["labelBr"], bold=True, center=True)
        self._text(p, cx + casDepth / 2 + 20, topY + elevH_px * 0.4, "INSPECTION DOORS", 7, C["label"])

        self._title_block(p, W, H, "side")

    # ═══════════════════════════════════════════════════════════════
    # TRAJECTORY VIEW -- port of TrajectoryView() (SVG version, distinct
    # from the pyqtgraph chart in charts_panel.py -- the JSX itself keeps
    # both, so this stays faithful to that rather than de-duplicating)
    # ═══════════════════════════════════════════════════════════════
    def _paint_trajectory(self, p):
        W, H = SVG_W, SVG_H
        r = self.results
        p.fillRect(QRectF(0, 0, W, H), qc(C["bg"]))
        traj = r.get("trajectory") or []
        upper = r.get("trajectory_upper") or []
        lower = r.get("trajectory_lower") or []
        m = r.get("trajectory_metrics") or {}

        if not traj:
            self._no_data(p, W, H, "trajectory")
            return

        pad = {"top": 58, "bot": 46, "left": 60, "right": 26}
        pw, ph = W - pad["left"] - pad["right"], H - pad["top"] - pad["bot"]
        all_pts = traj + upper + lower
        all_x = [pt["x"] for pt in all_pts]
        all_y = [pt["y"] for pt in all_pts]
        x_min, x_max = min(all_x), max(all_x)
        y_min, y_max = min(all_y), max(all_y)
        x_r, y_r = max(x_max - x_min, 0.01), max(y_max - y_min, 0.01)

        def tx(x):
            return pad["left"] + (x - x_min) / x_r * pw

        def ty(y):
            return pad["top"] + (y_max - y) / y_r * ph

        self._grid(p, W, H)
        p.setPen(QPen(qc(C["dim"]), 0.8))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(QRectF(pad["left"], pad["top"], pw, ph))

        p.setPen(QPen(qc(C["casing"]), 0.6))
        for t in (0, 0.25, 0.5, 0.75, 1.0):
            gx, gy = pad["left"] + t * pw, pad["top"] + t * ph
            xv, yv = x_min + t * x_r, y_max - t * y_r
            p.drawLine(QPointF(gx, pad["top"]), QPointF(gx, pad["top"] + ph))
            p.drawLine(QPointF(pad["left"], gy), QPointF(pad["left"] + pw, gy))
            self._text(p, gx, pad["top"] + ph + 12, f"{xv:.0f}", 7.5, C["label"], center=True)
            self._text(p, pad["left"] - 4, gy + 3, f"{yv:.0f}", 7.5, C["label"], right=True)

        def build_path(pts):
            path = QPainterPath()
            for i, pt in enumerate(pts):
                (path.moveTo if i == 0 else path.lineTo)(tx(pt["x"]), ty(pt["y"]))
            return path

        if upper and lower:
            p.setPen(QPen(qc(C["danger"], 102), 1, Qt.PenStyle.DashLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(build_path(upper))
            p.drawPath(build_path(lower))
            band = QPainterPath(build_path(upper))
            for pt in reversed(lower):
                band.lineTo(tx(pt["x"]), ty(pt["y"]))
            band.closeSubpath()
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(qc(C["danger"], 15)))
            p.drawPath(band)

        p.setPen(QPen(qc(C["danger"]), 2.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(build_path(traj))
        if traj:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(qc(C["danger"])))
            p.drawEllipse(QPointF(tx(traj[0]["x"]), ty(traj[0]["y"])), 4, 4)

        self._text(p, W / 2, 22, "DISCHARGE TRAJECTORY", 10, C["text3"], bold=True, center=True)
        self._text(p, W / 2, 36,
                    f"Throw {f(m.get('throw_distance_m'),3)} m  ·  CR = {f(r.get('cr'),3)}  ·  θ = {f(r.get('theta_rel'),1)}° from vertical",
                    8, C["label"], center=True)
        self._text(p, W / 2, H - 8, "x [mm]", 9, C["labelBr"], center=True)
        p.save()
        p.translate(14, H / 2)
        p.rotate(-90)
        self._text(p, 0, 0, "y [mm]", 9, C["labelBr"], center=True)
        p.restore()

        self._title_block(p, W, H, "trajectory")

    # ═══════════════════════════════════════════════════════════════
    # BUCKET DETAIL VIEW -- port of BucketDetailView()
    # ═══════════════════════════════════════════════════════════════
    @staticmethod
    def _polygon_area(poly):
        """Shoelace formula. Works on any QPolygonF, including ones
        produced by QPainterPath.toFillPolygon() from a path built with
        curves -- Qt flattens beziers into line segments automatically,
        so this is exact for the polygon Qt actually renders, not an
        approximation of the true curve."""
        pts = list(poly)
        if len(pts) < 3:
            return 0.0
        area = 0.0
        for i in range(len(pts)):
            x1, y1 = pts[i].x(), pts[i].y()
            x2, y2 = pts[(i + 1) % len(pts)].x(), pts[(i + 1) % len(pts)].y()
            area += x1 * y2 - x2 * y1
        return abs(area) / 2.0

    def _solve_fill_height(self, side_path, y_top, y_bottom, x_min, x_max, target_frac):
        """Numerically finds the screen-y of the horizontal line such that
        the area of side_path BELOW that line equals target_frac of the
        path's total area. General-purpose: works identically for the
        rounded centrifugal scoop (bezier curves) and the straight-edged
        continuous wedge, since it operates on the actual rendered
        polygon rather than a shape-specific closed-form formula.
        Returns None if the path has no area (shouldn't happen for a
        real bucket, but guards against a degenerate case)."""
        total_area = self._polygon_area(side_path.toFillPolygon())
        if total_area <= 0:
            return None

        def area_below(y):
            clip = QPainterPath()
            clip.addRect(QRectF(x_min - 10, y, (x_max - x_min) + 20, (y_bottom - y) + 10))
            clipped = side_path.intersected(clip)
            return self._polygon_area(clipped.toFillPolygon())

        lo, hi = y_top, y_bottom   # lo = 0% filled, hi = 100% filled
        for _ in range(28):        # binary search, well past float precision needed for a schematic
            mid = (lo + hi) / 2
            frac = area_below(mid) / total_area
            if frac < target_frac:
                hi = mid
            else:
                lo = mid
        return (lo + hi) / 2

    def _paint_bucket_detail(self, p):
        W, H = SVG_W, SVG_H
        r = self.results
        inp = self.inputs
        bkt = r.get("bucket") or {}
        p.fillRect(QRectF(0, 0, W, H), qc(C["bg"]))
        self._grid(p, W, H)

        bW = float(bkt.get("W") or 305)
        bH = float(bkt.get("H") or bkt.get("depth_mm") or 295)
        bP = float(bkt.get("P") or 178)
        bV = float(bkt.get("V") or 0)
        frontAngle = bkt.get("front_angle_deg")
        frontAngle = float(frontAngle) if frontAngle is not None else None
        discType = bkt.get("discharge_type") or "centrifugal"
        seriesId = str(bkt.get("id") or "?").upper().strip()
        styleLabel = "Continuous" if discType == "continuous" else "Centrifugal"

        punch = bkt.get("punch") or "—"
        boltN = int(bkt.get("boltN") or 0)
        boltA_mm = float(bkt.get("boltA_mm") or 0)
        boltB_mm = float(bkt.get("boltB_mm") or 0)
        boltDia_mm = float(bkt.get("boltDia_mm") or 0)
        punchConfirmed = bkt.get("punch_confirmed") is not False

        scale = min((W - 140) / (bW + bP + 100), (H - 160) / (bH + 80))
        bWs, bHs, bPs = bW * scale, bH * scale, bP * scale

        fCx, sCx = W * 0.28, W * 0.74
        midY = H * 0.46
        fX, fY = fCx - bWs / 2, midY - bHs / 2
        sX, sY = sCx - bPs / 2, midY - bHs / 2

        fillPct = float(inp.get("fill_pct") or 75) / 100
        # FIX (Jay: found the front elevation and side profile fill lines
        # didn't align -- confirmed why: this line used an arbitrary 0.72
        # scaling factor that was never actually tied to any real
        # calculation. Corrected to a plain linear height fraction, which
        # is the mathematically correct assumption for a UNIFORM
        # rectangular cross-section (what this simplified front-elevation
        # rectangle represents). This is explicitly NOT the same
        # computation as the Side Profile's fill line below, which
        # accounts for the bucket's actual tapered/lip shape -- the two
        # views use different simplifying assumptions about the bucket's
        # 3D form, so they will legitimately show different heights even
        # both being "correct" for what each view represents. Labelled
        # accordingly rather than silently implying agreement.
        fillY = fY + bHs * (1 - fillPct)

        # FIX (Jay: "bucket fill changes you made do not seem to work"):
        # confirmed by reading the real InputSidebar.jsx source -- the
        # authoritative range is dynamic_fill.min_fill_pct/max_fill_pct
        # (spacing + speed + flowability adjusted, same fields the
        # sidebar's own "DYNAMIC FILL ADVISORY" panel displays), NOT the
        # static mat_behavior.recommended_fill_pct ± 10 rule used here
        # previously. The backend itself never compared fill_pct against
        # this dynamic range either (confirmed via direct grep) -- fixed
        # in calculations.py alongside this (new 5d-2 check).
        dynamic_fill = r.get("dynamic_fill") or {}
        dyn_min = dynamic_fill.get("min_fill_pct")
        dyn_max = dynamic_fill.get("max_fill_pct")
        user_fill = float(inp.get("fill_pct") or 75)
        fill_unsafe = (dyn_min is not None and dyn_max is not None
                       and (user_fill < dyn_min or user_fill > dyn_max))
        fill_color = C["danger"] if fill_unsafe else C["belt"]

        self._text(p, W / 2, 18, f"STYLE {seriesId} — {styleLabel.upper()} DISCHARGE", 10, C["text3"], bold=True, center=True)
        self._text(p, W / 2, 30, f"Front Elevation (left) · Side Profile (right) · Punching: {punch}", 7.5, C["label"], center=True)
        disclaimers = []
        if not punchConfirmed:
            disclaimers.append(f"⚠ Bolt pattern is an estimate for {seriesId.split('_')[0]} style — confirm against approved manufacturing drawing")
        if discType != "centrifugal":
            disclaimers.append("ⓘ Lip height shown is illustrative, pending confirmed bucket profile dimensions")
        if fill_unsafe:
            disclaimers.append(f"⚠ Fill {user_fill:.0f}% is outside the safe range {dyn_min:.0f}–{dyn_max:.0f}% for this spacing/speed — overflow or under-fill risk")
        for i, d in enumerate(disclaimers):
            self._text(p, W / 2, 41 + i * 11, d, 6.5, C["danger"] if d.startswith("⚠") else C["warning"], center=True)

        # Front elevation
        front_path = QPainterPath()
        front_path.addRect(QRectF(fX, fY, bWs, bHs))
        p.setPen(QPen(qc(C["bucket"]), 1.5))
        p.setBrush(QBrush(qc(C["casFill"])))
        p.drawPath(front_path)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(qc(fill_color, 51)))
        p.drawRect(QRectF(fX + 1, fillY, bWs - 2, fY + bHs - fillY - 1))
        p.setPen(QPen(qc(fill_color, 178), 1, Qt.PenStyle.DashLine))
        p.drawLine(QPointF(fX + 1, fillY), QPointF(fX + bWs - 1, fillY))
        fill_label = f"{inp.get('fill_pct', 75)}% (rect. approx.)" + (" ⚠" if fill_unsafe else "")
        self._text(p, fX + bWs + 4, fillY, fill_label, 7, fill_color)

        hasBolts = boltN > 0 and boltA_mm > 0
        if hasBolts:
            p.setPen(QPen(qc(C["lagging"]), 0.8, Qt.PenStyle.DashLine))
            p.setBrush(QBrush(QColor(255, 158, 11, 18)))
            p.drawRect(QRectF(fX, fY, bWs, 11 * scale))

        boltRowY = fY + 5 * scale
        bolts = []
        if hasBolts:
            if punch == "chain":
                halfSpan = boltA_mm * scale / 2
                bolts = [QPointF(fCx - halfSpan, boltRowY), QPointF(fCx + halfSpan, boltRowY)]
            else:
                usableW = bWs - 2 * (boltB_mm * scale)
                step = usableW / (boltN - 1) if boltN > 1 else 0
                bolts = [QPointF(fX + boltB_mm * scale + i * step, boltRowY) for i in range(boltN)]

        boltRadius = max(2.2, boltDia_mm * scale * 0.5)
        for b in bolts:
            p.setPen(QPen(qc(C["dimTxt"]), 1))
            p.setBrush(QBrush(qc(C["dim"])))
            p.drawEllipse(b, boltRadius, boltRadius)
            p.drawLine(QPointF(b.x() - 2.5, b.y()), QPointF(b.x() + 2.5, b.y()))
            p.drawLine(QPointF(b.x(), b.y() - 2.5), QPointF(b.x(), b.y() + 2.5))
        if hasBolts:
            self._text(p, fX + bWs / 2, fY - 4, f"{punch} — {boltN} holes × Ø{boltDia_mm:.1f}mm", 6.5, C["lagging"], center=True)

        p.setPen(QPen(qc(C["dim"]), 0.7, Qt.PenStyle.DashLine))
        p.drawLine(QPointF(fCx, fY - 22), QPointF(fCx, fY + bHs + 8))
        self._text(p, fCx, fY - 28, "FRONT ELEVATION", 9, C["labelBr"], bold=True, center=True)
        self._dim_horizontal(p, fX, fY + bHs + 14, fX + bWs, fY + bHs + 14, f"L = {bW:.0f} mm", offset=16, side=1)
        self._dim_vertical(p, fX - 20, fY, fX - 20, fY + bHs, f"Depth = {bH:.0f} mm", offset=22, side=-1)
        if hasBolts and boltN > 1 and bolts:
            self._dim_horizontal(p, bolts[0].x(), boltRowY - 14, bolts[-1].x(), boltRowY - 14,
                                  f"A = {boltA_mm:.0f} mm × {boltN-1}", offset=10, side=1, size=7)

        # Side profile
        side_path = QPainterPath()
        tipYFrac = None
        if discType == "centrifugal" and (frontAngle is None or frontAngle <= 35):
            side_path.moveTo(sX, sY)
            side_path.lineTo(sX, sY + bHs * 0.55)
            side_path.quadTo(sX, sY + bHs, sX + bPs * 0.55, sY + bHs)
            side_path.quadTo(sX + bPs, sY + bHs, sX + bPs, sY + bHs * 0.78)
            side_path.lineTo(sX, sY)
        elif discType == "centrifugal" and frontAngle is not None and frontAngle <= 10:
            side_path.moveTo(sX, sY)
            side_path.lineTo(sX, sY + bHs)
            side_path.lineTo(sX + bPs, sY + bHs)
            side_path.lineTo(sX, sY)
        else:
            ang = frontAngle if frontAngle is not None else 45
            tipYFrac = 0.15 + 0.55 * (1 - ang / 90)
            side_path.moveTo(sX, sY)
            side_path.lineTo(sX, sY + bHs)
            side_path.lineTo(sX + bPs, sY + bHs * (1 - tipYFrac))
            side_path.lineTo(sX + bPs * 0.92, sY + bHs * (1 - tipYFrac) - 6)
            side_path.lineTo(sX, sY)
        side_path.closeSubpath()
        p.setPen(QPen(qc(C["bucket"]), 1.5))
        p.setBrush(QBrush(qc(C["casFill"])))
        p.drawPath(side_path)

        # FIX (Jay: confirmed by direct geometric calculation that fill
        # level can sit above the front lip for continuous buckets at
        # high fill% -- no view previously showed this at all). General
        # numerical solve against whichever shape variant was just built
        # above, so this works identically for the centrifugal scoop and
        # the continuous wedge without a separate formula per case.
        fill_frac = float(inp.get("fill_pct") or 75) / 100.0
        fill_y = self._solve_fill_height(side_path, sY, sY + bHs, sX, sX + bPs, fill_frac)
        lip_y = None
        if tipYFrac is not None:
            # The lip is the drawn front vertex -- same point used for the
            # "FRONT"/"LIP" label below, at height (1-tipYFrac) from the top.
            # Only ever set for the continuous wedge shape (see side_path
            # construction above) -- the centrifugal scoop cases don't have
            # a comparable "short front wall" lip, so no comparison is drawn
            # for those.
            lip_y = sY + bHs * (1 - tipYFrac)

        if fill_y is not None:
            fill_over_lip = lip_y is not None and fill_y < lip_y   # screen-y: smaller y = higher
            line_color = C["danger"] if fill_over_lip else C["belt"]
            p.setPen(QPen(qc(line_color), 1.6, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(sX - 4, fill_y), QPointF(sX + bPs + 4, fill_y))
            fill_pct_label = f"{inp.get('fill_pct', 75):.0f}% fill"
            if fill_over_lip:
                fill_pct_label += "  ⚠ above lip"
            self._text(p, sX - 8, fill_y - 3, fill_pct_label, 6.5, line_color, right=True)

        if lip_y is not None:
            note_color = C["danger"] if (fill_y is not None and fill_y < lip_y) else C["dimTxt"]
            p.setPen(QPen(qc(note_color, 140), 0.6, Qt.PenStyle.DotLine))
            p.drawLine(QPointF(sX + bPs - 3, lip_y), QPointF(sX + bPs + 14, lip_y))
            self._text(p, sX + bPs + 16, lip_y + 2, "lip height", 6, note_color)

        if frontAngle is not None:
            self._text(p, sX + bPs * 0.5, sY + bHs * 0.85, f"{frontAngle:.0f}°", 6.5, C["primary"], center=True)

        self._text(p, sCx, fY - 28, "SIDE PROFILE", 9, C["labelBr"], bold=True, center=True)
        self._dim_horizontal(p, sX, sY + bHs + 14, sX + bPs, sY + bHs + 14, f"P = {bP:.0f} mm", offset=16, side=1)
        self._dim_vertical(p, sX + bPs + 20, sY, sX + bPs + 20, sY + bHs, f"Depth = {bH:.0f} mm", offset=22, side=1)
        if frontAngle is not None:
            self._text(p, sX + bPs + 6, sY + bHs * 0.5, "FRONT" if discType == "continuous" else "LIP", 7.5, C["primary"], bold=True)

        # Spec table
        activeVol = bkt.get("active_volume_L")
        activeVol_text = f"{float(activeVol):.2f} L" if activeVol is not None else (f"{bV*fillPct:.2f} L" if bV > 0 else "—")
        nBuckets = r.get("n_buckets", "—")
        specRows = [
            ("Style / catalog", f"{seriesId} — {bkt.get('catalog', seriesId)} ({styleLabel})"),
            ("L × P × Depth", f"{bW:.0f} × {bP:.0f} × {bH:.0f} mm"),
            ("Struck capacity", f"{bV:.2f} L" if bV > 0 else "—"),
            ("Active volume", f"{activeVol_text} ({inp.get('fill_pct', 75)}% fill)"),
            ("Bucket mass", f"{float(bkt['bucket_mass_kg']):.1f} kg" if bkt.get("bucket_mass_kg") is not None else "— kg"),
            ("Total buckets", str(nBuckets)),
            ("Belt punching", f"{punch}  (CEMA standard)" if hasBolts else "chain mount — see manufacturing drawing"),
            ("Bolt holes", f"{boltN} × Ø{boltDia_mm:.1f}mm" if hasBolts else "—"),
            ("Hole spacing (A)", f"{boltA_mm:.1f} mm" if hasBolts and punch != "chain" else "—"),
            ("Edge inset (B)", f"{boltB_mm:.1f} mm" if hasBolts and punch != "chain" else "—"),
        ]
        table_x, table_y0, row_h = 14, H - 135, 13
        p.setPen(QPen(qc(C["dim"]), 0.8))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(QRectF(12, H - 138, 212, len(specRows) * row_h + 6))
        self._text(p, 118, H - 145, "BUCKET SPECIFICATION", 8.5, C["text3"], bold=True, center=True)
        for i, (k, v) in enumerate(specRows):
            if i % 2 == 0:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(qc(C["primary"], 13)))
                p.drawRect(QRectF(table_x, table_y0 + i * row_h, 208, row_h))
            self._text(p, 18, H - 126 + i * row_h, k, 7.5, C["text3"])
            self._text(p, 140, H - 126 + i * row_h, v, 7.5, C["labelBr"], bold=True)

        self._title_block(p, W, H, f"bucket {seriesId}")

    # ── Hover callout (shared) ───────────────────────────────────────
    def _draw_hover_callout(self, p, W, H, callouts):
        if not self.hovered or self.hovered not in callouts:
            return
        title, lines, x, y = callouts[self.hovered]
        boxW, lineH = 155, 13
        boxH = 18 + len(lines) * lineH
        bx = min(max(x + 8, 4), W - boxW - 4)
        by = min(max(y - boxH / 2, 4), H - boxH - 4)
        p.setPen(QPen(qc(C["primary"]), 1))
        p.setBrush(QBrush(qc(C["panel"], 247)))
        p.drawRoundedRect(QRectF(bx, by, boxW, boxH), 4, 4)
        self._text(p, bx + 8, by + 12, title, 9, C["primary"], bold=True)
        for i, line in enumerate(lines):
            self._text(p, bx + 8, by + 12 + (i + 1) * lineH, line, 8.5, C["labelBr"])


class _ViewTabBtn(QPushButton):
    def __init__(self, label, parent=None):
        super().__init__(label, parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggled.connect(self._style)
        self._style(False)

    def _style(self, checked):
        # SCOPED. The parent tab_bar carried a BARE `border-bottom`, which Qt
        # reads as `* { ... }` -- so it landed on every one of these buttons,
        # and the active tab drew a 1px inherited border UNDERNEATH its own 2px
        # primary underline. That is the doubled underline.
        # (The rgba(59,130,246,.12) tint was already correct v2 -- rare in this
        # codebase -- so only the selector changes, not the colour.)
        if checked:
            self.setStyleSheet(scoped(
                self,
                f"background-color: {PRIMARY_DIM}; color: {PRIMARY}; border: none; "
                f"border-bottom: 2px solid {PRIMARY}; padding: 3px 10px; "
                f"font-size: 10px; font-weight: 700;"
            ))
        else:
            self.setStyleSheet(scoped(
                self,
                f"background-color: transparent; color: {TEXT3}; border: none; "
                f"border-bottom: 2px solid transparent; padding: 3px 10px; "
                f"font-size: 10px;",
                extra="{sel}:hover { color: %s; }" % TEXT2,
            ))


class ElevationView(QWidget):
    """Full ElevatorSchematic container -- tab bar (5 views), zoom controls,
    canvas, overlay stat cards, hover status bar. This is the widget
    main.py imports and wires into the Results tab splitter; the name is
    kept for compatibility even though it's now the whole multi-view
    schematic, not just the elevation drawing."""

    def __init__(self, inputs=None, results=None, parent=None):
        super().__init__(parent)
        self.inputs = inputs or {}
        self.results = results or {}
        self.setMinimumSize(560, 640)
        self.setStyleSheet(plain_bg(self, C['bg']))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Tab bar ──────────────────────────────────────────────────
        tab_bar = QFrame()
        tab_bar.setFixedHeight(34)
        tab_bar.setStyleSheet(scoped(
            tab_bar,
            f"background-color: {PANEL2}; border: none; "
            f"border-bottom: 1px solid {BORDER};"
        ))
        tbl = QHBoxLayout(tab_bar)
        tbl.setContentsMargins(10, 0, 10, 0)
        tbl.setSpacing(2)
        self._tab_btns = {}
        for vid, label in VIEWS:
            btn = _ViewTabBtn(label)
            btn.setChecked(vid == "elevation")
            btn.clicked.connect(lambda _, v=vid: self._switch_view(v))
            tbl.addWidget(btn)
            self._tab_btns[vid] = btn
        tbl.addStretch()

        self._zoom_lbl = QLabel("100%")
        self._zoom_lbl.setStyleSheet(f"color:{TEXT3};font-size:9px;margin-right:4px;")
        tbl.addWidget(self._zoom_lbl)
        reset_btn = QPushButton("⊡ Reset")
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.setStyleSheet(scoped(
            reset_btn,
            f"background-color: transparent; color: {TEXT3}; "
            f"border: 1px solid {BORDER2}; border-radius: 3px; "
            f"padding: 2px 8px; font-size: 9px;",
            extra="{sel}:hover { background-color: %s; color: %s; }" % (SURFACE, TEXT),
        ))
        reset_btn.clicked.connect(self._reset_view)
        tbl.addWidget(reset_btn)
        for label, factor in [("+", 1.2), ("−", 0.8)]:
            zb = QPushButton(label)
            zb.setFixedSize(22, 22)
            zb.setCursor(Qt.CursorShape.PointingHandCursor)
            zb.setStyleSheet(scoped(
                zb,
                f"background-color: transparent; color: {TEXT3}; "
                f"border: 1px solid {BORDER2}; border-radius: 3px; "
                f"font-size: 13px; margin-left: 3px;",
                extra="{sel}:hover { background-color: %s; color: %s; }" % (SURFACE, TEXT),
            ))
            zb.clicked.connect(lambda _, f=factor: self._zoom_by(f))
            tbl.addWidget(zb)
        outer.addWidget(tab_bar)

        # ── Canvas + overlay stat cards ──────────────────────────────
        from PySide6.QtWidgets import QStackedWidget as _SWid
        from .elevation_cad import ElevationCADWidget
        from .elevation_side_cad import SideElevationCADWidget
        from .elevation_head_cad import HeadDetailCADWidget
        from .elevation_bucket_cad import BucketDetailCADWidget

        self._view_stack = _SWid()

        canvas_container = QWidget()
        canvas_container.setStyleSheet(plain_bg(canvas_container, C['bg']))
        self.canvas = _SchematicCanvas(canvas_container)
        self._cad_widget = ElevationCADWidget()
        self._cad_side_widget = SideElevationCADWidget()
        self._cad_head_widget = HeadDetailCADWidget()
        self._cad_bucket_widget = BucketDetailCADWidget()

        self._view_stack.addWidget(canvas_container)     # index 0 — QPainter views
        self._view_stack.addWidget(self._cad_widget)     # index 1 — CAD drawing (front)
        self._view_stack.addWidget(self._cad_side_widget) # index 2 — CAD drawing (side)
        self._view_stack.addWidget(self._cad_head_widget) # index 3 — CAD drawing (head detail)
        self._view_stack.addWidget(self._cad_bucket_widget) # index 4 — CAD drawing (bucket detail)
        self.canvas.on_hover_changed = self._on_hover_changed
        self.canvas.setCursor(Qt.CursorShape.OpenHandCursor)

        self._stat_overlay = QFrame(canvas_container)
        self._stat_overlay.setStyleSheet(scoped(
            self._stat_overlay, "background-color: transparent; border: none;"))
        stat_layout = QVBoxLayout(self._stat_overlay)
        stat_layout.setContentsMargins(0, 0, 0, 0)
        stat_layout.setSpacing(6)
        self._stat_chips = {}
        for key, label, unit in [
            ("v", "BELT SPEED", "m/s"), ("Q", "CAPACITY", "t/h"),
            ("motor_kw", "MOTOR", "kW"), ("theta_rel", "DISCHARGE θ", "° vert"),
            ("cr", "CR", ""),
        ]:
            chip = KPIChip(label, unit, min_size=(100, 56), value_pixel_size=17)
            stat_layout.addWidget(chip)
            self._stat_chips[key] = chip
        stat_layout.addStretch()
        self._stat_overlay.setFixedWidth(110)

        outer.addWidget(self._view_stack, 1)

        # Position canvas + overlay via resize handling (Qt has no CSS
        # position:absolute, so the overlay is a raw child widget moved
        # in resizeEvent)
        self._canvas_container = canvas_container
        canvas_container.resizeEvent = self._on_container_resize

        # ── Status bar ────────────────────────────────────────────────
        status_bar = QFrame()
        status_bar.setFixedHeight(22)
        status_bar.setStyleSheet(scoped(
            status_bar,
            f"background-color: {C['bg']}; border: none; "
            f"border-top: 1px solid {BORDER};"
        ))
        sl = QHBoxLayout(status_bar)
        sl.setContentsMargins(10, 0, 10, 0)
        hint = QLabel("Scroll to zoom · Drag to pan · Double-click to reset")
        hint.setStyleSheet(f"color:{TEXT3};font-size:8px;")
        sl.addWidget(hint)
        sl.addStretch()
        self._hover_status = QLabel("Hover components for engineering details")
        self._hover_status.setStyleSheet(f"color:{TEXT3};font-size:8px;")
        sl.addWidget(self._hover_status)
        outer.addWidget(status_bar)

        # Poll zoom label since canvas zoom changes via wheel events
        # internal to the canvas widget, not via a signal
        self._zoom_poll = QTimer(self)
        self._zoom_poll.timeout.connect(self._sync_zoom_label)
        self._zoom_poll.start(150)

    def _on_container_resize(self, event):
        self.canvas.setGeometry(0, 0, event.size().width(), event.size().height())
        self._stat_overlay.move(event.size().width() - self._stat_overlay.width() - 8, 8)
        self._stat_overlay.resize(self._stat_overlay.width(), event.size().height() - 16)

    def _switch_view(self, view_id):
        for vid, btn in self._tab_btns.items():
            btn.setChecked(vid == view_id)
        if view_id == "cad":
            self._view_stack.setCurrentIndex(1)
        elif view_id == "cad_side":
            self._view_stack.setCurrentIndex(2)
        elif view_id == "cad_head":
            self._view_stack.setCurrentIndex(3)
        elif view_id == "cad_bucket":
            self._view_stack.setCurrentIndex(4)
        else:
            self._view_stack.setCurrentIndex(0)
            self.canvas.set_view(view_id)

    def _reset_view(self):
        self.canvas.reset_view()

    def _zoom_by(self, factor):
        self.canvas.zoom = min(4.0, max(0.25, self.canvas.zoom * factor))
        self.canvas.update()

    def _sync_zoom_label(self):
        self._zoom_lbl.setText(f"{round(self.canvas.zoom * 100)}%")

    def _on_hover_changed(self, name):
        if name:
            self._hover_status.setText(f"{name.upper()} — hover for callout")
            self._hover_status.setStyleSheet(f"color:{PRIMARY};font-size:8px;")
        else:
            self._hover_status.setText("Hover components for engineering details")
            self._hover_status.setStyleSheet(f"color:{TEXT3};font-size:8px;")

    def set_data(self, inputs, results):
        self.inputs = inputs or {}
        self.results = results or {}
        self.canvas.set_data(self.inputs, self.results)
        self._cad_widget.set_data(self.inputs, self.results)
        self._cad_side_widget.set_data(self.inputs, self.results)
        self._cad_head_widget.set_data(self.inputs, self.results)
        self._cad_bucket_widget.set_data(self.inputs, self.results)

        r = self.results
        q_req = self.inputs.get("Q_req")
        cr = r.get("cr")
        stats = {
            "v": (f(r.get("v"), 2), PRIMARY if r.get("v") is not None else TEXT3),
            "Q": (f"{r.get('Q'):.0f}" if r.get("Q") is not None else "—",
                  (SUCCESS if (r.get("Q") or 0) >= (q_req or 0) else DANGER) if r.get("Q") is not None else TEXT3),
            "motor_kw": (str(r.get("motor_kw", "—")), SUCCESS),
            "theta_rel": (f(r.get("theta_rel"), 1), WARNING),
            "cr": (f(cr, 3), SUCCESS if r.get("cr_ok") else WARNING),

        }
        for key, (text, color) in stats.items():
            self._stat_chips[key].set_value(text, color)