"""
components/elevation_view.py -- PySide6/QPainter port of
ElevatorSchematic.jsx's ElevationView().
═══════════════════════════════════════════════════════════════════════════
Pure drawing, deliberately -- no stats-card row above it. Belt speed and
capacity are NOT shown here: they live in the app's top-level performance
cards (main.py's TopNav), and showing them twice was the exact duplication
flagged when this was first built. What's here is what's actually native
to an elevation drawing -- pulley diameters, RPM, belt width, casing
height, discharge angle, bucket pitch -- dimensions and angles, not
throughput numbers that don't have an inherent place on a mechanical
drawing.

Faithful to the original, not a reinterpretation: same variable names
(headD, bootD, rH, rB, casW, topY, botY, bltL, bltR, spacePx, bktH_px,
bktW_px, chuteBaseX/Y, chuteTipX/Y, etc.) and the same geometry formulas
as ElevatorSchematic.jsx, so this is directly comparable line-for-line if
you want to change something.

This widget owns no fetch/network logic of its own -- it's a plain QWidget
that takes (inputs, results) via the constructor or set_data() and draws
exactly what those values describe. That's deliberate: a widget that
fetches its own data can't be reused in a shell that wants to share one
fetch across multiple panels (see main.py's run_calculation()).
"""
import math

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPainterPath, QPolygonF

from theme import DRAWING as C


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


class ElevationView(QWidget):
    """Direct port of ElevatorSchematic.jsx's ElevationView(). Same geometry,
    same variable names, same formulas -- pass (inputs, results) in and it
    draws exactly what those values describe."""

    def __init__(self, inputs=None, results=None, parent=None):
        super().__init__(parent)
        self.inputs = inputs or {}
        self.results = results or {}
        self.setMinimumSize(560, 640)
        self.hovered = None   # "head" | "boot" | "motor" | "bucket" | None, for future hover callouts

    def set_data(self, inputs, results):
        self.inputs = inputs or {}
        self.results = results or {}
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        inp, r = self.inputs, self.results
        bkt = r.get("bucket") or {}

        # ── Background ───────────────────────────────────────────────────
        p.fillRect(QRectF(0, 0, W, H), qc(C["bg"]))

        margin = {"top": 56, "bottom": 68, "left": 52, "right": 120}
        cx = W * 0.36

        # ── Pulleys -- shared scale so equal diameters render as equal
        #    circles (same fix as the JSX's own FIX #2) ────────────────────
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

        # ── Bucket sizing -- proportional to ACTUAL spacing from backend ──
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

        # ── Discharge chute direction from r.theta_rel ────────────────────
        # Calling r.get("theta_rel") only once and storing it lets Pyright
        # correctly narrow the None-check (two separate .get() calls in the
        # condition vs. the branch defeated that narrowing).
        theta_rel = r.get("theta_rel")
        thetaRad = math.radians(theta_rel if theta_rel is not None else 10)
        chuteLen = 48
        chuteBaseX, chuteBaseY = cx + rH * 0.5, topY - rH * 0.5
        chuteTipX = chuteBaseX + math.sin(thetaRad) * chuteLen
        chuteTipY = chuteBaseY - math.cos(thetaRad) * chuteLen

        # ── Casing body ────────────────────────────────────────────────────
        p.setPen(QPen(qc(C["casing"]), 2))
        p.setBrush(QBrush(qc(C["casFill"])))
        p.drawRect(QRectF(cx - casW, topY, casW * 2, elevH))

        # Centreline (dashed)
        pen = QPen(qc(C["dim"]), 0.7, Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.drawLine(QPointF(cx, topY - 12), QPointF(cx, botY + 12))

        # ── Belt lines ──────────────────────────────────────────────────────
        p.setPen(QPen(qc(C["belt"]), 3.5))
        p.drawLine(QPointF(bltL, topY), QPointF(bltL, botY))
        p.setPen(QPen(qc(C["beltRtn"], 165), 2.5))
        p.drawLine(QPointF(bltR, topY), QPointF(bltR, botY))

        # ── Buckets -- carry side (solid, near-opaque) ─────────────────────
        p.setClipRect(QRectF(cx - casW, topY, casW * 2, elevH))
        for by_ in carryBuckets:
            path = QPainterPath()
            path.moveTo(bltL, by_ - bktH_px * 0.5)
            path.lineTo(bltL - bktW_px, by_ - bktH_px * 0.5)
            path.quadTo(bltL - bktW_px - 3, by_, bltL - bktW_px, by_ + bktH_px * 0.5)
            path.lineTo(bltL, by_ + bktH_px * 0.5)
            path.closeSubpath()
            p.setPen(QPen(qc(C["casing"]), 0.6))
            p.setBrush(QBrush(qc(C["bucket"], 209)))   # 0.82 opacity
            p.drawPath(path)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(qc(C["belt"], 77)))      # 0.3 opacity
            p.drawRoundedRect(QRectF(bltL - bktW_px + 1, by_, max(1.0, bktW_px - 3), bktH_px * 0.35), 1, 1)

        # ── Buckets -- return side (faint) ─────────────────────────────────
        for by_ in returnBuckets:
            path = QPainterPath()
            path.moveTo(bltR, by_ + bktH_px * 0.5)
            path.lineTo(bltR + bktW_px, by_ + bktH_px * 0.5)
            path.quadTo(bltR + bktW_px + 3, by_, bltR + bktW_px, by_ - bktH_px * 0.5)
            path.lineTo(bltR, by_ - bktH_px * 0.5)
            path.closeSubpath()
            p.setPen(QPen(qc(C["casing"], 128), 0.5))
            p.setBrush(QBrush(qc(C["bucket"], 56)))    # 0.22 opacity
            p.drawPath(path)
        p.setClipping(False)

        # ── Boot pulley ──────────────────────────────────────────────────
        p.setPen(QPen(qc(C["hub"]), 2))
        p.setBrush(QBrush(qc(C["pulley"], 217)))   # 0.85 opacity
        p.drawEllipse(QPointF(cx, botY), rB, rB)
        p.setBrush(QBrush(qc(C["hub"])))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, botY), rB * 0.3, rB * 0.3)
        pen = QPen(qc(C["dim"]), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(QPointF(cx - rB - 16, botY), QPointF(cx - rB, botY))
        p.drawLine(QPointF(cx + rB, botY), QPointF(cx + rB + 16, botY))
        # Take-up box
        p.setPen(QPen(qc(C["dim"]), 1))
        p.setBrush(QBrush(qc(C["casing"])))
        p.drawRoundedRect(QRectF(cx - 9, botY + rB + 4, 18, 18), 2, 2)
        self._text(p, cx, botY + rB + 16, "T/U", 6, C["text3"], bold=True, center=True)
        p.setPen(QPen(qc(C["dim"]), 1))
        p.drawLine(QPointF(cx, botY + rB + 2), QPointF(cx, botY + rB + 4))

        # ── Head pulley ──────────────────────────────────────────────────
        p.setPen(QPen(qc(C["lagging"], 140), 4))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, topY), rH + 3, rH + 3)
        p.setPen(QPen(qc(C["hub"]), 2))
        p.setBrush(QBrush(qc(C["pulley"], 217)))
        p.drawEllipse(QPointF(cx, topY), rH, rH)
        pen = QPen(qc(C["hub"], 102), 0.9)
        p.setPen(pen)
        for k in (-1, 0, 1):
            p.drawLine(QPointF(cx + k * rH * 0.38, topY - rH * 0.82),
                       QPointF(cx + k * rH * 0.38, topY + rH * 0.82))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(qc(C["hub"])))
        p.drawEllipse(QPointF(cx, topY), rH * 0.28, rH * 0.28)
        pen = QPen(qc(C["dim"]), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(QPointF(cx - rH - 18, topY), QPointF(cx - rH, topY))
        p.drawLine(QPointF(cx + rH, topY), QPointF(cx + rH + 18, topY))

        # ── Discharge chute ──────────────────────────────────────────────
        chute_path = QPainterPath()
        chute_path.moveTo(chuteBaseX - 6, chuteBaseY)
        chute_path.lineTo(chuteTipX, chuteTipY)
        chute_path.lineTo(chuteTipX + 10, chuteTipY + 6)
        chute_path.lineTo(chuteBaseX + 6, chuteBaseY + 8)
        chute_path.closeSubpath()
        p.setPen(QPen(qc(C["chute"]), 1.4))
        p.setBrush(QBrush(qc(C["chute"], 20)))
        p.drawPath(chute_path)
        self._text(p, chuteTipX + 16, chuteTipY, "DISCHARGE", 7.5, C["chute"], bold=True)
        self._text(p, chuteTipX + 16, chuteTipY + 11, f"θ={f(theta_rel, 0)}°", 6.5, C["label"])

        # ── Drive train ──────────────────────────────────────────────────
        pen = QPen(qc(C["dim"]), 1.5, Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.drawLine(QPointF(cx + rH + 16, topY + rH * 0.5), QPointF(cx + casW + 10, topY + rH * 0.5))
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

        # ── Feed inlet ────────────────────────────────────────────────────
        p.setPen(QPen(qc(C["feed"]), 2))
        p.drawLine(QPointF(cx - casW - 34, botY), QPointF(cx - casW - 4, botY))
        self._draw_arrowhead(p, cx - casW - 4, botY, 0, qc(C["feed"]))
        self._text(p, cx - casW - 38, botY - 5, "FEED", 7.5, C["feed"], bold=True, right=True)

        # ── Dimensions ────────────────────────────────────────────────────
        self._dim_vertical(p, cx - casW - 4, botY, cx - casW - 4, topY, f"H = {f(H_m, 0)} m", offset=24, side=-1)
        self._dim_horizontal(p, bltL, topY - rH - 6, bltR, topY - rH - 6, f"BW = {r.get('belt_w', '—')} mm", offset=16, side=1)
        if spacePx > 16:
            self._dim_vertical(p, cx + casW + 8, botY - 12, cx + casW + 8, botY - 12 - spacePx,
                                f"{round(spacingM * 1000)}mm", offset=20, side=1)

        # ── Head / Boot labels ────────────────────────────────────────────
        self._text(p, cx, 10, "HEAD SECTION", 9, C["labelBr"], bold=True, center=True)
        self._text(p, cx, 21, f"Ø{headD:.0f}mm · {inp.get('n_rpm', '—')}rpm · Lagged", 7, C["label"], center=True)
        self._text(p, cx, botY + rB + 36, "BOOT / TAKE-UP", 9, C["labelBr"], bold=True, center=True)
        self._text(p, cx, botY + rB + 46, f"Ø{bootD:.0f}mm · Gravity", 7, C["label"], center=True)
        self._text(p, cx + rB + 6, botY + 4, f"DB = {bootD:.0f} mm", 7.5, C["text3"])

        # ── Bucket footer ─────────────────────────────────────────────────
        footer = (f"BUCKET {bkt.get('id', '—')} · {bkt.get('W', '—')}×{bkt.get('H', '—')}mm · "
                  f"{bkt.get('V', '—')}L · {realCount} buckets total · spacing {round(spacingM * 1000)}mm")
        self._text(p, W / 2, H - 6, footer, 7.5, C["label"], center=True)

        p.end()

    # ── Drawing helpers ──────────────────────────────────────────────────
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

    def _dim_horizontal(self, p, x1, y1, x2, y2, label, offset, side):
        """Port of Dim() for the horizontal (isHorz) branch."""
        dy = y1 - side * offset
        pen = QPen(qc(C["dim"]), 0.6)
        p.setPen(pen)
        p.drawLine(QPointF(x1, y1), QPointF(x1, dy - side * 4))
        p.drawLine(QPointF(x2, y2), QPointF(x2, dy - side * 4))
        p.setPen(QPen(qc(C["dim"]), 0.8))
        p.drawLine(QPointF(x1, dy), QPointF(x2, dy))
        self._text(p, (x1 + x2) / 2, dy - 4, label, 8.5, C["labelBr"], center=True)

    def _dim_vertical(self, p, x1, y1, x2, y2, label, offset, side):
        """Port of Dim() for the vertical (isVert) branch."""
        dx = x1 + side * offset
        pen = QPen(qc(C["dim"]), 0.6)
        p.setPen(pen)
        p.drawLine(QPointF(x1, y1), QPointF(dx + side * 4, y1))
        p.drawLine(QPointF(x2, y2), QPointF(dx + side * 4, y2))
        p.setPen(QPen(qc(C["dim"]), 0.8))
        p.drawLine(QPointF(dx, y1), QPointF(dx, y2))
        p.save()
        mid_y = (y1 + y2) / 2
        p.translate(dx - side * 3, mid_y)
        p.rotate(-90)
        self._text(p, 0, 0, label, 8.5, C["labelBr"], center=True)
        p.restore()