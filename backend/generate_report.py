"""
VECTRIX™ Bucket Elevator — Engineering Report Generator
Produces an A4 portrait PDF from a results dict (FastAPI /be/solve shape).

v1.1.0 — Task 2 fixes
─────────────────────────────────────────────────────────────────────────────
FIX 1  Tension kN conversion.
       T1, T2, T3, F_eff, R_headshaft are returned in N.
       v1.0.0 labelled them "kN" without dividing by 1000 — values were
       displayed as e.g. "13420.0 kN" (should be "13.4 kN").
       Added rkn() helper that reads the field and divides by 1000.

FIX 2  Tension label meaning.
       "Tight side T₁" / "Slack side T₂" were wrong.  In the VECTRIX backend:
         T1 = material tension component (not tight-side)
         T2 = belt + bucket self-weight  (not slack-side)
         T3 = slack-side (take-up) tension
         F_eff = T1 + T2 = effective tension
         R_headshaft = T1+T2+T3 = total headshaft radial load = belt tight side
       Corrected labels and added belt tension ratio (R_headshaft / T3) vs
       Euler limit (e^μθ) for the slip check row.

FIX 3  Slip display.
       rv("slip_limit") always returned "—" — that field never existed.
       Now reads euler_ratio (added in Task 1 backend update) and shows
       belt tension ratio vs Euler limit alongside slip_safe flag.

FIX 4  Allowable shear stress.
       "55 MPa (mild steel)" → "42 MPa (keyed shaft, ASME B17.1 §6 000 psi)".
       55 MPa is the no-keyway value; all bucket elevator head shafts carry
       a keyway — the correct value is 42 MPa (corrected in constants.py).
       Updated in shaft table and in the notes disclaimer.

FIX 5  New backend fields from Task 1 (Euler) and Task 3 (power).
       Task 3 power decomposition: P_shaft, H_equiv, H_total now displayed
       in the power breakdown table with full CEMA LEQ derivation shown.
       Task 1 Euler fields: T3_ktakeup, T3_euler_min, euler_ratio, slip_safe.
       v1.2.x shaft geometry: shaft_span_mm, shaft_A_mm, shaft_B_mm.
       v1.2.x material advisory: recommended_fill_pct, bucket_mass_kg.
─────────────────────────────────────────────────────────────────────────────

Usage (from FastAPI route or React download handler):
    from generate_report import build_report
    pdf_bytes = build_report(results, inputs)
"""

import io
import math
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white, black, Color
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether,
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import Flowable

# ─── Brand colours ────────────────────────────────────────────────
NAVY      = HexColor("#07111e")
NAVY2     = HexColor("#0d1c2e")
NAVY3     = HexColor("#132238")
BORDER    = HexColor("#1c3050")
CRIMSON   = HexColor("#c8192e")
BLUE      = HexColor("#4a9eff")
GREEN     = HexColor("#1fb86e")
AMBER     = HexColor("#d98e00")
RED       = HexColor("#e05252")
TEAL      = HexColor("#2dd4bf")
TEXT      = HexColor("#ddeaf6")
MUTED     = HexColor("#5a7a9a")
MUTED2    = HexColor("#7a9ab8")
LIGHT_BG  = HexColor("#f0f4f8")
MID_BG    = HexColor("#dde6ef")
DARK_TEXT = HexColor("#0d1c2e")

W, H = A4   # 595.27 × 841.89 pt
ML = 18*mm
MR = 18*mm
MT = 15*mm
MB = 18*mm


# ─── Paragraph styles ─────────────────────────────────────────────
def styles():
    return {
        "h1": ParagraphStyle("h1",
            fontName="Helvetica-Bold", fontSize=18, textColor=white,
            spaceAfter=2, leading=22),
        "h2": ParagraphStyle("h2",
            fontName="Helvetica-Bold", fontSize=10, textColor=CRIMSON,
            spaceBefore=6, spaceAfter=3, leading=13),
        "h3": ParagraphStyle("h3",
            fontName="Helvetica-Bold", fontSize=8, textColor=DARK_TEXT,
            spaceAfter=2, leading=10),
        "body": ParagraphStyle("body",
            fontName="Helvetica", fontSize=8, textColor=DARK_TEXT,
            spaceAfter=2, leading=11),
        "mono": ParagraphStyle("mono",
            fontName="Courier", fontSize=7.5, textColor=DARK_TEXT,
            spaceAfter=1, leading=10),
        "caption": ParagraphStyle("caption",
            fontName="Helvetica", fontSize=6.5, textColor=MUTED,
            spaceAfter=1, leading=9),
        "kpi_val": ParagraphStyle("kpi_val",
            fontName="Helvetica-Bold", fontSize=16, textColor=DARK_TEXT,
            leading=18, alignment=TA_CENTER),
        "kpi_unit": ParagraphStyle("kpi_unit",
            fontName="Helvetica", fontSize=7, textColor=MUTED,
            leading=9, alignment=TA_CENTER),
        "kpi_label": ParagraphStyle("kpi_label",
            fontName="Helvetica-Bold", fontSize=6.5, textColor=MUTED,
            leading=8, alignment=TA_CENTER),
        "footer": ParagraphStyle("footer",
            fontName="Helvetica", fontSize=6.5, textColor=MUTED,
            alignment=TA_CENTER),
        "tag_ok":   ParagraphStyle("tag_ok",   fontName="Helvetica-Bold",
            fontSize=7, textColor=GREEN, leading=9),
        "tag_warn": ParagraphStyle("tag_warn", fontName="Helvetica-Bold",
            fontSize=7, textColor=AMBER, leading=9),
        "tag_fail": ParagraphStyle("tag_fail", fontName="Helvetica-Bold",
            fontSize=7, textColor=RED, leading=9),
        "check_msg": ParagraphStyle("check_msg", fontName="Helvetica",
            fontSize=7.5, textColor=DARK_TEXT, leading=10),
    }

ST = styles()


# ─── Helpers ──────────────────────────────────────────────────────
def fmt(v, dp=2, fb="—"):
    try:
        f = float(v)
        if not math.isfinite(f):
            return fb
        return f"{f:.{dp}f}"
    except (TypeError, ValueError):
        return fb if v is None else str(v)

def safe(d, *keys, fb="—"):
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return fb
        cur = cur.get(k)
        if cur is None:
            return fb
    return cur if cur != "" else fb


class ColorRect(Flowable):
    def __init__(self, w, h, color, radius=0):
        super().__init__()
        self.w, self.h, self.color, self.r = w, h, color, radius

    def draw(self):
        self.canv.setFillColor(self.color)
        if self.r:
            self.canv.roundRect(0, 0, self.w, self.h, self.r, fill=1, stroke=0)
        else:
            self.canv.rect(0, 0, self.w, self.h, fill=1, stroke=0)

    def wrap(self, aW=0, aH=0):
        return self.w, self.h


# ─── Section title ────────────────────────────────────────────────
def section(title):
    return [
        Spacer(1, 5),
        HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=2),
        Paragraph(title.upper(), ST["h2"]),
    ]


# ─── Four-column table (replaces two_col + data_table nesting) ────
#
# ROOT CAUSE of v1.0 layout bug:
#   two_col() created a container ~243pt wide per side.
#   data_table() inside used default col_widths=[(W-ML-MR)*0.52, *0.48]
#   = 256pt + 237pt = 493pt total — 2× the available space.
#   Result: right column always overflowed the page margin.
#
# FIX: flat single Table with 4 columns across the full page width.
#   No nesting → no width mismatch → no overflow.
#   Col widths: 30% label | 20% value | 30% label | 20% value.
#
def four_col_table(left_rows, right_rows):
    """
    Flat 4-column table: left_label | left_value | right_label | right_value.
    Replaces two_col(data_table(), data_table()) entirely.
    Uses full available page width — no nested containers.
    """
    avail = W - ML - MR          # e.g. 493 pt
    c_lab = avail * 0.30         # label column:  148 pt each side
    c_val = avail * 0.20         # value column:  99 pt each side

    max_rows = max(len(left_rows), len(right_rows))
    data = []
    for i in range(max_rows):
        L = left_rows[i]  if i < len(left_rows)  else ("", "")
        R = right_rows[i] if i < len(right_rows) else ("", "")
        data.append([
            Paragraph(str(L[0]), ST["body"]),
            Paragraph(str(L[1]), ST["mono"]),
            Paragraph(str(R[0]), ST["body"]),
            Paragraph(str(R[1]), ST["mono"]),
        ])

    t = Table(data, colWidths=[c_lab, c_val, c_lab, c_val])
    style_cmds = [
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",   (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 2.5),
        ("LEFTPADDING",  (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("GRID",         (0, 0), (-1, -1), 0.3, BORDER),
        # Vertical divider between left and right sections
        ("LINEAFTER",    (1, 0), (1, -1), 1.2, MUTED),
    ]
    for i in range(max_rows):
        bg = LIGHT_BG if i % 2 == 0 else white
        style_cmds.append(("BACKGROUND", (0, i), (-1, i), bg))
    t.setStyle(TableStyle(style_cmds))
    return [t, Spacer(1, 6)]


# ─── KPI card table ───────────────────────────────────────────────
def kpi_row(cards):
    col_w = (W - ML - MR) / len(cards)
    status_colors = {"ok": GREEN, "warn": AMBER, "fail": RED, "info": BLUE}
    cells = []
    for label, value, unit, status in cards:
        cell = [
            Paragraph(str(label), ST["kpi_label"]),
            Paragraph(str(value), ST["kpi_val"]),
            Paragraph(str(unit),  ST["kpi_unit"]),
        ]
        cells.append(cell)
    t = Table([cells], colWidths=[col_w] * len(cards))
    style_cmds = [
        ("BACKGROUND",   (0, 0), (-1, -1), LIGHT_BG),
        ("GRID",         (0, 0), (-1, -1), 0.3, BORDER),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
        ("LEFTPADDING",  (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]
    for i, (_, _, _, status) in enumerate(cards):
        c = status_colors.get(status, BLUE)
        style_cmds.append(("LINEABOVE", (i, 0), (i, 0), 2.5, c))
    t.setStyle(TableStyle(style_cmds))
    return [t, Spacer(1, 4)]


# ─── 2-column data table ──────────────────────────────────────────
def data_table(rows, col_widths=None):
    cw = col_widths or [(W - ML - MR) * 0.52, (W - ML - MR) * 0.48]
    table_data = []
    for row in rows:
        table_data.append([
            Paragraph(row[0], ST["body"]),
            Paragraph(str(row[1]), ST["mono"]),
        ])
    t = Table(table_data, colWidths=cw)
    style_cmds = [
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",   (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 2.5),
        ("LEFTPADDING",  (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("GRID",         (0, 0), (-1, -1), 0.3, BORDER),
    ]
    for i in range(len(table_data)):
        bg = LIGHT_BG if i % 2 == 0 else white
        style_cmds.append(("BACKGROUND", (0, i), (-1, i), bg))
    t.setStyle(TableStyle(style_cmds))
    return [t, Spacer(1, 4)]


# ─── Two-column layout helper ─────────────────────────────────────
def two_col(left_flowables, right_flowables):
    cw = (W - ML - MR - 4*mm) / 2
    ldata = [[f] for f in left_flowables]
    rdata = [[f] for f in right_flowables]
    lt = Table(ldata, colWidths=[cw])
    lt.setStyle(TableStyle([
        ("TOPPADDING",   (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    rt = Table(rdata, colWidths=[cw])
    rt.setStyle(TableStyle([
        ("TOPPADDING",   (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    outer = Table([[lt, rt]], colWidths=[cw + 2*mm, cw + 2*mm])
    outer.setStyle(TableStyle([
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",   (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2*mm),
    ]))
    return outer


# ─── Checks table ────────────────────────────────────────────────
def checks_table(checks):
    icons   = {"pass": "✓", "ok": "✓", "warn": "⚠", "fail": "✗", "info": "ℹ"}
    styles_ = {"pass":"tag_ok","ok":"tag_ok","warn":"tag_warn","fail":"tag_fail","info":"tag_ok"}
    status_colors = {"pass": GREEN, "ok": GREEN, "warn": AMBER, "fail": RED, "info": BLUE}
    rows = []
    for c in checks:
        st   = c.get("status") or c.get("type", "info")
        if st == "ok": st = "pass"
        icon = icons.get(st, "ℹ")
        sty  = styles_.get(st, "tag_ok")
        rows.append([
            Paragraph(icon, ST[sty]),
            Paragraph(c.get("code", ""), ST["caption"]),
            Paragraph(c.get("msg", ""), ST["check_msg"]),
        ])
    cw = [8*mm, 14*mm, W - ML - MR - 22*mm]
    t = Table(rows, colWidths=cw)
    style_cmds = [
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",   (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 2),
        ("LEFTPADDING",  (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("GRID",         (0, 0), (-1, -1), 0.2, BORDER),
    ]
    for i in range(len(rows)):
        bg = LIGHT_BG if i % 2 == 0 else white
        style_cmds.append(("BACKGROUND", (0, i), (-1, i), bg))
    t.setStyle(TableStyle(style_cmds))
    return [t, Spacer(1, 4)]


# ─── Header band ─────────────────────────────────────────────────
def header_flowables(inp, res, project="", doc_ref=""):
    now    = datetime.now().strftime("%d %b %Y  %H:%M")
    mat    = res.get("material") or {}
    status = res.get("status", "—").upper()
    status_color = {"PASS": GREEN, "WARNING": AMBER, "FAIL": RED}.get(status, BLUE)
    content_w = W - ML - MR
    logo_col = [
        Paragraph("<b>VECTRIX™</b>", ParagraphStyle("logo",
            fontName="Helvetica-Bold", fontSize=16, textColor=white, leading=18)),
        Paragraph("BUCKET ELEVATOR", ParagraphStyle("sub",
            fontName="Helvetica", fontSize=7, textColor=MUTED2, leading=9, spaceBefore=1)),
        Paragraph("Engineering Design Report", ParagraphStyle("sub2",
            fontName="Helvetica", fontSize=6.5, textColor=MUTED, leading=8)),
    ]
    proj_col = [
        Paragraph(f"<b>Project:</b> {project or 'Unspecified'}", ParagraphStyle("pi",
            fontName="Helvetica", fontSize=8, textColor=white, leading=10)),
        Paragraph(f"<b>Ref:</b> {doc_ref or 'VX-BE-001'}", ParagraphStyle("pi",
            fontName="Helvetica", fontSize=8, textColor=white, leading=10)),
        Paragraph(f"<b>Date:</b> {now}", ParagraphStyle("pi",
            fontName="Helvetica", fontSize=8, textColor=white, leading=10)),
        Paragraph(
            f"<b>Material:</b> {mat.get('name') or inp.get('mat_id','Custom')}",
            ParagraphStyle("pi", fontName="Helvetica", fontSize=8, textColor=white, leading=10)),
    ]
    status_col = [
        Paragraph(f"<b>{status}</b>", ParagraphStyle("st",
            fontName="Helvetica-Bold", fontSize=14, textColor=status_color,
            alignment=TA_CENTER, leading=16)),
        Paragraph("Design Status", ParagraphStyle("stl",
            fontName="Helvetica", fontSize=6.5, textColor=MUTED,
            alignment=TA_CENTER, leading=8)),
        Spacer(1, 2),
        Paragraph("JAYVEECONS<br/>Engineering &amp; Design", ParagraphStyle("jv",
            fontName="Helvetica", fontSize=6, textColor=MUTED2,
            alignment=TA_CENTER, leading=8)),
    ]
    hdr = Table(
        [[logo_col, proj_col, status_col]],
        colWidths=[content_w * 0.28, content_w * 0.46, content_w * 0.26],
    )
    hdr.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), NAVY),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",   (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW",    (0, 0), (-1, 0), 2.5, CRIMSON),
    ]))
    return [hdr, Spacer(1, 6)]


# ─── Main builder ─────────────────────────────────────────────────
def build_report(results: dict, inputs: dict,
                 project: str = "", doc_ref: str = "",
                 output_path: "str | None" = None) -> bytes:
    """
    Build A4 portrait PDF. Returns bytes (for FastAPI StreamingResponse)
    and optionally writes to output_path.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=ML, rightMargin=MR, topMargin=MT, bottomMargin=MB,
        title="VECTRIX™ Bucket Elevator Report",
        author="Jayveecons Engineering & Design",
    )

    r   = results
    inp = inputs
    bkt = r.get("bucket") or {}
    mat = r.get("mat") or r.get("material") or {}

    # ── Field readers ──────────────────────────────────────────────────────────
    def rv(*keys, dp=2, fb="—"):
        """Read scalar field, return formatted string."""
        for k in keys:
            v = r.get(k)
            if v is not None:
                return fmt(v, dp, fb)
        return fb

    # FIX 1 — tensions are stored in N; report labels them kN
    def rkn(*keys, dp=2, fb="—"):
        """Read tension field [N] and return formatted kN string."""
        for k in keys:
            v = r.get(k)
            if v is not None:
                try:
                    return fmt(float(v) / 1000.0, dp, fb)
                except (TypeError, ValueError):
                    return fb
        return fb

    # ── Performance ────────────────────────────────────────────────────────────
    Q_th = rv("Q_th",  "Q",        dp=1)
    v_ms = rv("v_ms",  "v",        dp=2)

    # ── Power (Task 3 decomposition fields) ────────────────────────────────────
    P_total  = rv("P_total",     "power_P_total",  dp=2)
    P_lift   = rv("P_lift",      "power_P_lift",   dp=2)
    P_dig    = rv("P_digging",   "P_dig",          dp=2)
    P_frict  = rv("P_drive_loss","power_P_frict",  dp=2)
    # FIX 5 — new Task 3 fields
    P_shaft  = rv("P_shaft",     dp=2)
    H_equiv  = rv("H_equiv",     dp=2)
    H_total  = rv("H_total",     dp=2)

    # ── Motor ──────────────────────────────────────────────────────────────────
    motor = r.get("motor_kw") or r.get("motor_kW") or r.get("motorKW") or "—"

    # ── Tensions — FIX 1: divide by 1000 for kN display ───────────────────────
    T1_kn      = rkn("T1",           dp=2)
    T2_kn      = rkn("T2",           dp=2)
    T3_kn      = rkn("T3",           dp=2)
    F_eff_kn   = rkn("F_eff",        dp=2)
    R_head_kn  = rkn("R_headshaft",  dp=2)

    # FIX 5 — Task 1 Euler fields
    T3_ktakeup_kn   = rkn("T3_ktakeup",   dp=2)
    T3_euler_min_kn = rkn("T3_euler_min", dp=2)
    euler_ratio     = rv("euler_ratio",   dp=3)
    slip_safe       = r.get("slip_safe")
    mu_val          = r.get("mu")   or inp.get("mu",   "—")
    wrap_val        = r.get("wrap_deg") or inp.get("wrap_deg", "—")

    # FIX 2 — meaningful belt tension ratio: R_headshaft / T3 (tight/slack)
    r_head_raw = float(r.get("R_headshaft") or 0)
    t3_raw     = float(r.get("T3") or 1)
    belt_ratio = fmt(r_head_raw / t3_raw if t3_raw else 0, 3)
    slip_label = "✓ PASS" if slip_safe is True else ("✗ FAIL" if slip_safe is False else "—")

    # ── Shaft ──────────────────────────────────────────────────────────────────
    shaft_T     = rv("shaft_torque_Nm","T_Nm",  dp=1)
    shaft_d     = rv("shaft_d_mm",    "d_mm",   dp=1)
    governed_by = r.get("governed_by") or "—"
    # FIX 5 — new v1.2.x shaft geometry fields
    shaft_span  = rv("shaft_span_mm",            dp=0)
    shaft_A     = rv("shaft_A_mm",               dp=0)
    shaft_B     = rv("shaft_B_mm",               dp=0)

    # ── Belt ───────────────────────────────────────────────────────────────────
    belt_w_raw = r.get("belt_width_mm") or r.get("belt_w") or "—"
    belt_w     = str(belt_w_raw)
    belt_cls   = r.get("belt_class") or f"{r.get('belt_ply','—')} PLY"

    # ── Bearing ────────────────────────────────────────────────────────────────
    L10 = rv("L10_hours","L10", dp=0)

    # ── Discharge ──────────────────────────────────────────────────────────────
    cr    = rv("centrifugal_ratio","cr",        dp=3)
    theta = rv("release_angle_deg","theta_rel", dp=1)

    # ── Spacing ────────────────────────────────────────────────────────────────
    spacing    = r.get("spacing_m") or r.get("spacing")
    spacing_mm = f"{spacing*1000:.0f}" if spacing else "—"

    # ── Material behaviour (v1.2.x advisory) ───────────────────────────────────
    rec_fill = rv("recommended_fill_pct", dp=1)
    bkt_mass = rv("bucket_mass_kg",       dp=2)

    # ── Component design ───────────────────────────────────────────────────────
    casing_t = rv("casing_t_mm",     dp=1)
    therm    = rv("thermal_exp_mm",  dp=1)
    boot_v   = rv("boot_vol_min_m3", dp=4)

    # ── Bucket sub-object ──────────────────────────────────────────────────────
    bkt_ser = bkt.get("series") or bkt.get("id") or "—"
    bkt_w   = bkt.get("width_mm")      or bkt.get("W") or "—"
    bkt_d   = bkt.get("depth_mm")      or bkt.get("H") or "—"
    bkt_p   = bkt.get("projection_mm") or bkt.get("P") or "—"
    bkt_v   = bkt.get("volume_L")      or bkt.get("V") or "—"
    bkt_st  = bkt.get("style")         or bkt.get("type") or "centrifugal"

    # ── Material ───────────────────────────────────────────────────────────────
    mat_name    = mat.get("name") or inp.get("mat_id", "Custom")
    mat_density = mat.get("rho_loose") or mat.get("rho") or r.get("rho") or inp.get("rho_kgm3","—")

    # ── Status booleans ────────────────────────────────────────────────────────
    cap_ok  = float(r.get("Q_th") or r.get("Q") or 0) >= float(inp.get("Q_req", 0))
    v_raw   = float(r.get("v_ms") or r.get("v") or 0)
    spd_ok  = v_raw >= 0.5
    cr_val  = float(r.get("centrifugal_ratio") or r.get("cr") or 0)
    cr_ok   = 1.0 <= cr_val <= 2.5
    l10_raw = float(r.get("L10_hours") or r.get("L10") or 0)
    l10_ok  = l10_raw >= 20000
    belt_ok = r_head_raw <= 50000

    # ──────────────────────────────────────────────────────────────────────────
    # STORY BUILD
    # ──────────────────────────────────────────────────────────────────────────
    story = []

    # 1. Header
    story += header_flowables(inp, r, project, doc_ref)

    # 2. Key KPIs
    story += kpi_row([
        ("Capacity",          Q_th,        "t/h",  "ok" if cap_ok else "fail"),
        ("Belt Speed",         v_ms,        "m/s",  "ok" if spd_ok else "warn"),
        ("Total Power",        P_total,     "kW",   "info"),
        ("Motor Selected",     str(motor),  "kW",   "info"),
        ("Centrifugal Ratio",  cr,          "—",    "ok" if cr_ok else "warn"),
        ("Bearing L10",        L10,         "h",    "ok" if l10_ok else "warn"),
    ])

    # 3. Two-column: Process inputs | Belt tensions
    # FIX: four_col_table() — flat 4-column layout, no overflow
    # FIX: ASCII-only labels — Unicode subscripts (T1 not T_subscript) render in Helvetica
    left_rows = [
        ("Required capacity",      f"{inp.get('Q_req','—')} t/h"),
        ("Lift height",            f"{inp.get('H_m','—')} m"),
        ("Material",               mat_name),
        ("Bulk density",           f"{mat_density} kg/m3"),
        ("Head pulley dia.",       f"{inp.get('D_mm','—')} mm"),
        ("Head shaft speed",       f"{inp.get('n_rpm','—')} rpm"),
        ("Fill factor (user)",     f"{inp.get('fill_pct','—')}%"),
        ("Fill (material DB)",     f"{rec_fill}%  advisory"),
        ("Service factor",         f"{inp.get('sf','—')}"),
    ]
    right_rows = [
        # ASCII labels — subscripts 1/2/3 rendered as regular digits
        ("Material tension T1",        f"{T1_kn} kN"),
        ("Self-weight tension T2",     f"{T2_kn} kN"),
        ("Effective tension F=T1+T2",  f"{F_eff_kn} kN"),
        ("Slack-side tension T3",      f"{T3_kn} kN"),
        ("Belt tight side R=F+T3",     f"{R_head_kn} kN"),
        ("Belt ratio R/T3",            belt_ratio),
        ("Euler limit e^(mu*theta)",   euler_ratio),
        ("Belt slip check",            slip_label),
        ("Belt class",                 str(belt_cls)),
        ("Belt width",                 f"{belt_w} mm"),
        ("Friction mu / wrap",         f"{mu_val} / {wrap_val} deg"),
    ]

    story += section("1. Design Parameters & Belt Tensions")
    story += four_col_table(left_rows, right_rows)

    # 4. Two-column: Bucket geometry | Shaft & drive
    bkt_rows = [
        ("Series / style",          f"{bkt_ser}  {bkt_st}"),
        ("Width x depth",           f"{bkt_w} x {bkt_d} mm"),
        ("Projection (P)",          f"{bkt_p} mm"),
        ("Volume (struck)",         f"{bkt_v} L"),
        ("Bucket mass (catalogue)", f"{bkt_mass} kg"),
        ("Spacing",                 f"{spacing_mm} mm"),
        ("Buckets per metre",       f"{1/spacing:.2f}" if spacing else "—"),
        ("Active vol / bucket",
            f"{float(bkt_v or 0)*inp.get('fill_pct',75)/100:.3f} L"
            if bkt_v != "—" else "—"),
    ]

    # FIX 4 — 42 MPa (keyed shaft) in plain ASCII; value shortened to fit column
    shaft_rows = [
        ("Shaft torque",            f"{shaft_T} Nm"),
        ("Min shaft dia.",          f"{shaft_d} mm"),
        ("Governed by",             governed_by),
        ("Allowable shear (keyed)", "42 MPa — ASME B17.1"),
        ("Bearing span L",          f"{shaft_span} mm"),
        ("Drive arm A",             f"{shaft_A} mm"),
        ("Tail arm B",              f"{shaft_B} mm"),
        ("Bearing L10 life",        f"{L10} h"),
        ("Discharge angle",         f"{theta} deg from vertical"),
        ("Recommended fill",        f"{rec_fill}% (material DB)"),
        ("Casing thickness",        f"{casing_t} mm"),
        ("Boot min. volume",        f"{boot_v} m3"),
    ]

    story += section("2. Bucket Geometry & Mechanical Design")
    story += four_col_table(bkt_rows, shaft_rows)

    # 5. Power breakdown — full-width single table with wider label column
    sf      = float(inp.get("sf", 1.25))
    P_tot_raw = float(r.get("P_total") or 0)
    story += section("3. Power Breakdown  (CEMA 375 §4 LEQ Method)")
    avail = W - ML - MR
    pw_rows = [
        ("Boot equiv. height  H_equiv = D_boot x Leq", f"{H_equiv} m"),
        ("Total equiv. height H_total = H + H_equiv",  f"{H_total} m"),
        ("Lift power   P_lift = G x g x H_lift / 1000",f"{P_lift} kW"),
        ("Boot power   P_dig  = G x g x H_equiv / 1000",f"{P_dig} kW"),
        ("Shaft power  P_shaft = G x g x H_total / 1000",f"{P_shaft} kW"),
        ("Drive losses = P_shaft x (Ceff - 1)",        f"{P_frict} kW"),
        ("Total power  P_total = P_shaft x Ceff",      f"{P_total} kW"),
        (f"Design power  (x SF {sf})",                 f"{fmt(P_tot_raw * sf, 2)} kW"),
        ("Selected motor",                             f"{motor} kW"),
        ("Gearbox ratio (@ 1450 rpm input)",           f"{1450/inp.get('n_rpm',60):.1f} : 1"),
    ]
    story += data_table(pw_rows, col_widths=[avail * 0.60, avail * 0.40])

    # 6. Inlet chute (unchanged)
    ic = r.get("inlet_chute") or {}
    if ic:
        story += section("4. Inlet Chute Design")
        chute_rows = [
            ("Inlet area required",  f"{fmt(ic.get('area_m2'),4)} m²"),
            ("Chute width",          f"{fmt(ic.get('width_mm'),0)} mm"),
            ("Chute slope angle",    f"{fmt(ic.get('chute_angle'),1)}°"),
            ("Feed velocity",        f"{fmt(ic.get('feed_v_ms'),2)} m/s"),
            ("Liner recommendation", ic.get("liner","—")),
        ]
        story += data_table(chute_rows)

    # 7. Engineering checks
    checks = r.get("checks") or []
    if checks:
        story += section("5. Engineering Validation Checks")
        story += checks_table(checks)

    # 8. Notes — plain ASCII throughout (no Unicode special chars)
    story += section("6. Notes")
    notes = [
        "Shaft sizing per ASME B17.1 / CEMA 375 §4.  Allowable shear = 42 MPa "
        "(keyed shaft, 6000 psi, A36 mild steel).  Use 55 MPa only for keyway-free shafts.  "
        "Add 10-15% diameter margin in detailed design for keyway stress concentration.",

        "Belt tension ratio (R/T3) must remain below the Euler limit e^(mu x theta) for "
        "no-slip operation.  Increase take-up tension, add snub pulley, or upgrade to "
        "ceramic lagging if slip check fails.",

        "Power decomposition: P_shaft = G x g x H_total / 1000 where "
        "H_total = H_lift + D_boot x Leq.  Ceff covers gearbox, bearing, and belt-flexure "
        "losses.  P_digging is a shaft load (boot scooping), NOT a drive loss — no "
        "double-counting with Ceff.",

        "Belt ply rating requires verification against manufacturer catalogue using working "
        "tension per mm belt width with SF >= 6.  Confirm EP or ST class with belt supplier.",

        "Bearing L10 life computed from combined head-shaft radial load R = T1+T2+T3.  "
        "Consult bearing manufacturer for actual catalogue selection.",

        "Recommended fill % is an advisory from the VECTRIX material database (CEMA §6 "
        "fill factor adjusted for cohesion and moisture).  It does not override the "
        "user-entered fill factor used in capacity calculation.",

        "This report is a preliminary engineering estimate.  Full detailed design, "
        "structural analysis, and CEMA 375-2017 compliance verification are required "
        "before fabrication.",
    ]
    for n in notes:
        story.append(Paragraph(f"*  {n}", ST["caption"]))
        story.append(Spacer(1, 2))

    # 9. Footer
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
    story.append(Spacer(1, 2))
    story.append(Paragraph(
        f"VECTRIX™ Bucket Elevator Module  •  Jayveecons Engineering &amp; Design  "
        f"•  Generated {datetime.now().strftime('%d %b %Y %H:%M')}  "
        f"•  AkshayVipra EL-MEC PVT. LTD.",
        ST["footer"]
    ))

    doc.build(story)
    pdf_bytes = buf.getvalue()
    if output_path:
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
    return pdf_bytes


# ─── CLI test ──────────────────────────────────────────────────────
if __name__ == "__main__":
    # Sample data uses actual backend field names (rv() handles fallbacks)
    sample_inputs = {
        "Q_req": 120, "H_m": 30, "mat_id": "limestone",
        "rho_kgm3": 1450, "D_mm": 500, "n_rpm": 65,
        "fill_pct": 75, "bucket_gap": 20,
        "mu": 0.35, "wrap_deg": 180, "sf": 1.25,
    }
    sample_results = {
        # Performance — backend uses Q and v (not Q_th / v_ms)
        "Q": 123.4, "v": 1.70, "spacing": 0.275,
        "cr": 1.19, "theta_rel": 33.2,
        # Power — Task 3 fields
        "P_lift": 9.82, "P_drive_loss": 0.59, "P_digging": 0.41,
        "P_shaft": 10.23, "P_total": 12.79,
        "H_equiv": 2.45, "H_total": 32.45,
        # Tensions — in N (rkn() divides by 1000 for kN display)
        "T1":  4010, "T2":  7220, "T3":  7876,
        "F_eff": 11230, "R_headshaft": 19106,
        "T3_ktakeup": 7876, "T3_euler_min": 5621,
        # Task 1 Euler
        "euler_ratio": 3.003, "slip_safe": True,
        # Motor / belt
        "motor_kw": 15, "belt_w": 330, "belt_ply": 4,
        # Shaft — v1.2.x geometry
        "T_Nm": 1878, "d_mm": 55.2, "d_stress_mm": 52.1, "d_deflect_mm": 55.2,
        "governed_by": "deflection",
        "shaft_span_mm": 635, "shaft_A_mm": 286, "shaft_B_mm": 349,
        # Bearing
        "L10": 38200,
        # Material advisory
        "recommended_fill_pct": 72.5,
        "bucket_mass_kg": 3.9,
        # Bucket
        "bucket": {
            "id": "A", "type": "centrifugal",
            "W": 254, "H": 178, "P": 165, "V": 5.0,
        },
        "mat": {
            "name": "Limestone (crushed)", "rho_loose": 1442,
            "abr_code": 6, "flowability": 3, "Km": 1.2,
        },
        "rho": 1442,
        "checks": [
            {"type": "ok",   "msg": "Capacity 123.4 t/h ≥ required 120 t/h [CEMA 375 §4]"},
            {"type": "ok",   "msg": "Speed 1.70 m/s within CEMA range 1.14–1.91 m/s [CEMA 375 §6]"},
            {"type": "ok",   "msg": "CR=1.190 — optimal centrifugal range 1.0–1.8 [CEMA 375 §3]"},
            {"type": "ok",   "msg": "Belt slip check: T3=7876 N ≥ Euler min 5621 N (e^μθ=3.003) [CEMA 375 §4]"},
            {"type": "warn", "msg": "Abrasion class 6/7 — AR400/AR500 buckets and casing liners strongly recommended [CEMA 550]"},
            {"type": "ok",   "msg": "Bearing L10=38200 h — excellent [CEMA 375 §4]"},
        ],
        "status": "warning",
        "Leq": 9, "Ceff": 1.25,
    }

    out = "/mnt/user-data/outputs/bucket_elevator_report.pdf"
    build_report(sample_results, sample_inputs,
                 project="Cement Plant SC-101",
                 doc_ref="VX-BE-2024-001",
                 output_path=out)
    print(f"Report written → {out}")


# ═══════════════════════════════════════════════════════════════════════════════
# VARIANT COMPARISON REPORT
# ═══════════════════════════════════════════════════════════════════════════════

def build_variant_report(candidates: list, inputs: dict,
                         project: str = "", doc_ref: str = "",
                         output_path: "str | None" = None) -> bytes:
    """
    Build A4 portrait PDF comparing multiple optimizer candidates.
    candidates: list of optimizer result dicts (from run_optimizer).
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=ML, rightMargin=MR, topMargin=MT, bottomMargin=MB,
        title="VECTRIX™ Design Variants Comparison",
        author="Jayveecons Engineering & Design",
    )
    inp = inputs
    now = datetime.now().strftime("%d %b %Y  %H:%M")
    n   = len(candidates)
    story = []

    # Header
    hdr = Table([[
        [
            Paragraph("<b>VECTRIX™</b>", ParagraphStyle("logo",
                fontName="Helvetica-Bold", fontSize=16, textColor=white, leading=18)),
            Paragraph("BUCKET ELEVATOR", ParagraphStyle("sub",
                fontName="Helvetica", fontSize=7, textColor=MUTED2, leading=9)),
            Paragraph("Design Variant Comparison", ParagraphStyle("sub2",
                fontName="Helvetica", fontSize=6.5, textColor=MUTED, leading=8)),
        ],
        [
            Paragraph(f"<b>Project:</b> {project or 'Unspecified'}", ParagraphStyle("pi",
                fontName="Helvetica", fontSize=8, textColor=white, leading=10)),
            Paragraph(f"<b>Ref:</b> {doc_ref or 'VX-BE-VAR'}", ParagraphStyle("pi",
                fontName="Helvetica", fontSize=8, textColor=white, leading=10)),
            Paragraph(f"<b>Date:</b> {now}", ParagraphStyle("pi",
                fontName="Helvetica", fontSize=8, textColor=white, leading=10)),
            Paragraph(f"<b>Variants:</b> {n} selected", ParagraphStyle("pi",
                fontName="Helvetica", fontSize=8, textColor=white, leading=10)),
        ],
        [
            Paragraph(f"<b>{n} VARIANTS</b>", ParagraphStyle("st",
                fontName="Helvetica-Bold", fontSize=14, textColor=BLUE,
                alignment=TA_CENTER, leading=16)),
            Paragraph("Comparison Report", ParagraphStyle("stl",
                fontName="Helvetica", fontSize=6.5, textColor=MUTED,
                alignment=TA_CENTER, leading=8)),
        ],
    ]], colWidths=[(W - ML - MR) * 0.28, (W - ML - MR) * 0.46, (W - ML - MR) * 0.26])
    hdr.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,-1), NAVY),
        ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",   (0,0), (-1,-1), 8),
        ("BOTTOMPADDING",(0,0), (-1,-1), 8),
        ("LEFTPADDING",  (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("LINEBELOW",    (0,0), (-1, 0), 2.5, CRIMSON),
    ]))
    story += [hdr, Spacer(1, 8)]

    # Design basis
    story += section("Design Basis")
    basis = [
        ("Required capacity", f"{inp.get('Q_req','—')} t/h"),
        ("Lift height",       f"{inp.get('H_m','—')} m"),
        ("Material",          inp.get('mat_id','—')),
        ("Head pulley dia.",  f"{inp.get('D_mm','—')} mm"),
        ("Service factor",    str(inp.get('sf','—'))),
        ("Fill target",       f"{inp.get('fill_pct','—')}%"),
    ]
    story += data_table(basis, col_widths=[(W-ML-MR)*0.4, (W-ML-MR)*0.6])

    # Variant comparison table
    story += section("Variant Comparison")
    col_w_first = 42*mm
    col_w_unit  = 14*mm
    col_w_var   = (W - ML - MR - col_w_first - col_w_unit) / max(n, 1)
    col_widths  = [col_w_first, col_w_unit] + [col_w_var] * n

    def vrow(label, unit, getter):
        vals = []
        for c in candidates:
            try:    vals.append(str(getter(c)))
            except: vals.append("—")
        return ([Paragraph(label, ST["body"]),
                 Paragraph(unit, ST["caption"])] +
                [Paragraph(v, ST["mono"]) for v in vals])

    col_labels = ["Parameter", "Units"] + [f"Variant {i+1}" for i in range(n)]
    header_row = [Paragraph(h, ST["h3"]) for h in col_labels]
    table_data = [header_row,
        vrow("Bucket series", "—",    lambda c: c.get("bucket_id","—")),
        vrow("RPM",           "rpm",  lambda c: c.get("rpm","—")),
        vrow("Fill factor",   "%",    lambda c: c.get("fill","—")),
        vrow("Belt speed",    "m/s",  lambda c: c.get("speed","—")),
        vrow("Capacity",      "t/h",  lambda c: c.get("capacity","—")),
        vrow("Total power",   "kW",   lambda c: c.get("power","—")),
        vrow("Motor selected","kW",   lambda c: c.get("motor_kw","—")),
        vrow("Head load R",   "kN",   lambda c: c.get("T1_kN","—")),
        vrow("Cent. ratio",   "—",    lambda c: c.get("cr","—")),
        vrow("Score",         "—",    lambda c: fmt(c.get("score"),3)),
        vrow("Rank",          "—",    lambda c: c.get("rank","—")),
    ]
    ranks         = [c.get("rank", 99) for c in candidates]
    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    style_cmds = [
        ("BACKGROUND",   (0, 0), (-1,  0), NAVY),
        ("TEXTCOLOR",    (0, 0), (-1,  0), TEXT),
        ("FONTNAME",     (0, 0), (-1,  0), "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1,  0), 7.5),
        ("GRID",         (0, 0), (-1, -1), 0.3, BORDER),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",   (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 2.5),
        ("LEFTPADDING",  (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]
    for i in range(1, len(table_data)):
        bg = LIGHT_BG if i % 2 == 1 else white
        style_cmds.append(("BACKGROUND", (0, i), (-1, i), bg))
    best_rank_idx = ranks.index(min(ranks)) if ranks else 0
    col_idx = 2 + best_rank_idx
    style_cmds.append(("LINEABOVE", (col_idx, 0), (col_idx, 0), 2.5, GREEN))
    style_cmds.append(("LINEBELOW", (col_idx, len(table_data)-1),
                        (col_idx, len(table_data)-1), 1.5, GREEN))
    t.setStyle(TableStyle(style_cmds))
    story += [t, Spacer(1, 6)]

    # Per-variant checks
    story += section("Engineering Validation by Variant")
    for i, c in enumerate(candidates):
        story.append(Paragraph(
            f"<b>Variant {i+1}</b>  —  Bucket {c.get('bucket_id','—')} · "
            f"{c.get('rpm','—')} RPM · Fill {c.get('fill','—')}% · "
            f"P={c.get('power','—')} kW · CR={c.get('cr','—')}",
            ST["h3"]
        ))
        cv    = float(c.get("capacity", 0) or 0)
        Q_req = float(inp.get("Q_req", 0))
        cr_v  = float(c.get("cr", 0) or 0)
        chks  = [
            ("pass" if cv >= Q_req else "fail",
             f"Capacity: {cv:.1f} t/h {'≥' if cv >= Q_req else '<'} {Q_req:.1f} t/h"),
            ("pass" if 1.0 <= cr_v <= 2.5 else "warn",
             f"CR={cr_v:.3f} — {'optimal centrifugal' if 1.0 <= cr_v <= 2.5 else 'outside 1.0–2.5 range'}"),
        ]
        for st, msg in chks:
            icon  = {"pass":"✓","warn":"⚠","fail":"✗"}.get(st,"ℹ")
            style = {"pass":"tag_ok","warn":"tag_warn","fail":"tag_fail"}.get(st,"tag_ok")
            story.append(Table(
                [[Paragraph(icon, ST[style]), Paragraph(msg, ST["check_msg"])]],
                colWidths=[8*mm, W-ML-MR-8*mm],
            ))
        story.append(Spacer(1, 4))

    # Footer
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
    story.append(Spacer(1, 2))
    story.append(Paragraph(
        f"VECTRIX™  ·  Jayveecons Engineering &amp; Design  "
        f"·  Generated {now}  ·  AkshayVipra EL-MEC PVT. LTD.",
        ST["footer"]
    ))

    doc.build(story)
    pdf_bytes = buf.getvalue()
    if output_path:
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
    return pdf_bytes