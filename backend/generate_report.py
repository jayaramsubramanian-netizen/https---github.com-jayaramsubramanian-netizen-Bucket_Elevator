"""
VECTRIX™ Bucket Elevator — Engineering Report Generator
Produces an A4 portrait PDF from a results dict (FastAPI /be/solve shape).

Usage (from FastAPI route or React download handler):
    from generate_report import build_report
    pdf_bytes = build_report(results, inputs)

Usage (CLI test with sample data):
    python3 generate_report.py
"""

import io
import math
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import (
    HexColor, white, black, Color
)
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
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

W, H = A4          # 595.27 x 841.89 pt
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
    """Safely traverse nested dict."""
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return fb
        cur = cur.get(k)
        if cur is None:
            return fb
    return cur if cur != "" else fb

class ColorRect(Flowable):
    """Filled rectangle background — used for header band."""
    def __init__(self, w, h, color, radius=0):
        super().__init__()
        self.w, self.h, self.color, self.r = w, h, color, radius

    def draw(self):
        self.canv.setFillColor(self.color)
        if self.r:
            self.canv.roundRect(0, 0, self.w, self.h, self.r, fill=1, stroke=0)
        else:
            self.canv.rect(0, 0, self.w, self.h, fill=1, stroke=0)

    def wrap(self, aW=0, aH=0):  # noqa: N803
        return self.w, self.h

# ─── Section title ────────────────────────────────────────────────
def section(title):
    return [
        Spacer(1, 5),
        HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=2),
        Paragraph(title.upper(), ST["h2"]),
    ]

# ─── KPI card table ───────────────────────────────────────────────
def kpi_row(cards):
    """
    cards: list of (label, value, unit, status)
    status: 'ok' | 'warn' | 'fail' | 'info'
    Renders as a single-row table of equal-width cards.
    """
    col_w = (W - ML - MR) / len(cards)
    status_colors = {"ok": GREEN, "warn": AMBER, "fail": RED, "info": BLUE}

    cells = []
    for label, value, unit, status in cards:
        c = status_colors.get(status, BLUE)
        cell = [
            Paragraph(str(label), ST["kpi_label"]),
            Paragraph(str(value), ST["kpi_val"]),
            Paragraph(str(unit),  ST["kpi_unit"]),
        ]
        cells.append(cell)

    t = Table([cells], colWidths=[col_w] * len(cards))
    style_cmds = [
        ("BACKGROUND",  (0, 0), (-1, -1), LIGHT_BG),
        ("GRID",        (0, 0), (-1, -1), 0.3, BORDER),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",  (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING",(0, 0), (-1, -1), 3),
    ]
    # Color accent top border per status
    for i, (_, _, _, status) in enumerate(cards):
        c = status_colors.get(status, BLUE)
        style_cmds.append(("LINEABOVE", (i, 0), (i, 0), 2.5, c))
    t.setStyle(TableStyle(style_cmds))
    return [t, Spacer(1, 4)]

# ─── 2-column data table ──────────────────────────────────────────
def data_table(rows, col_widths=None):
    """rows: list of (label, value) or (label, value, color_hint)"""
    cw = col_widths or [(W - ML - MR) * 0.52, (W - ML - MR) * 0.48]
    table_data = []
    for i, row in enumerate(rows):
        label = row[0]
        value = row[1]
        table_data.append([
            Paragraph(label, ST["body"]),
            Paragraph(str(value), ST["mono"]),
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
    """Pack two lists of flowables side by side."""
    cw = (W - ML - MR - 4*mm) / 2
    # Flatten each side into a single Table cell
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
        st  = c.get("status") or c.get("type", "info")
        if st == "ok":
            st = "pass"
        icon = icons.get(st, "ℹ")
        sty  = styles_.get(st, "tag_ok")
        col  = status_colors.get(st, BLUE)
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

    band_h = 28*mm
    content_w = W - ML - MR

    # Header table: logo block | project info | status stamp
    logo_col = [
        Paragraph("<b>VECTRIX™</b>", ParagraphStyle("logo",
            fontName="Helvetica-Bold", fontSize=16, textColor=white, leading=18)),
        Paragraph("BUCKET ELEVATOR", ParagraphStyle("sub",
            fontName="Helvetica", fontSize=7, textColor=MUTED2, leading=9,
            spaceBefore=1)),
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
        Paragraph(f"<b>Material:</b> {mat.get('name') or mat.get('rho_loose') and mat.get('name') or inp.get('mat_id','Custom')}", ParagraphStyle("pi",
            fontName="Helvetica", fontSize=8, textColor=white, leading=10)),
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
        ("BACKGROUND",  (0, 0), (-1, -1), NAVY),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",  (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",(0, 0), (-1, -1), 6),
        ("LINEBELOW",   (0, 0), (-1, 0), 2.5, CRIMSON),
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
    # Your backend returns bucket as a dict with keys: id, W, H, P, V, type etc.
    # mat is returned as the full material dict with keys: rho_loose, name, abr_code etc.
    bkt = r.get("bucket") or {}
    mat = r.get("mat") or r.get("material") or {}
    ic  = r.get("inlet_chute") or {}

    # Helper: try multiple key names, return formatted string
    def rv(*keys, dp=2, fb="—"):
        for k in keys:
            v = r.get(k)
            if v is not None:
                return fmt(v, dp, fb)
        return fb

    # ── Performance ─────────────────────────────────────────────
    # Backend returns: Q (old), v (old) — also accept Q_th, v_ms from normaliser
    Q_th    = rv("Q_th",  "Q",       dp=1)
    v_ms    = rv("v_ms",  "v",       dp=2)

    # ── Power ────────────────────────────────────────────────────
    # Backend returns: P_total, P_lift, P_digging, P_drive_loss
    P_total = rv("P_total", "power_P_total",              dp=2)
    P_lift  = rv("P_lift",  "power_P_lift",               dp=2)
    P_dig   = rv("P_digging","P_dig","power_P_dig",       dp=2)
    P_frict = rv("P_drive_loss","power_P_frict",          dp=2)

    # ── Motor ────────────────────────────────────────────────────
    # Backend returns: motor_kw
    motor   = r.get("motor_kw") or r.get("motor_kW") or r.get("motorKW") or "—"

    # ── Tension ──────────────────────────────────────────────────
    # Backend returns: T1, T2, T3, F_eff, R_headshaft
    T1      = rv("T1",            dp=1)
    T2      = rv("T2",            dp=1)
    T3      = rv("T3",            dp=1)
    F_eff   = rv("F_eff",         dp=1)
    R_head  = rv("R_headshaft",   dp=1)
    # tension_ratio not in backend — compute from T1/T2
    t1_raw  = float(r.get("T1") or 0)
    t2_raw  = float(r.get("T2") or 1)
    t_ratio = fmt(t1_raw / t2_raw if t2_raw else 0, 3)
    slip_lim = rv("slip_limit",   dp=3)   # not in backend; may be added by normaliser

    # ── Shaft ────────────────────────────────────────────────────
    # Backend returns: T_Nm, d_mm, d_stress_mm, d_deflect_mm, governed_by
    shaft_T = rv("shaft_torque_Nm","T_Nm",  dp=2)
    shaft_d = rv("shaft_d_mm",    "d_mm",  dp=1)
    governed_by = r.get("governed_by") or "—"

    # ── Belt ─────────────────────────────────────────────────────
    # Backend returns: belt_w (int, mm), belt_ply
    belt_w_raw = r.get("belt_width_mm") or r.get("belt_w") or "—"
    belt_w     = str(belt_w_raw)
    belt_cls   = r.get("belt_class") or f"{r.get('belt_ply','—')} PLY"

    # ── Bearing ──────────────────────────────────────────────────
    # Backend returns: L10 (hours)
    L10     = rv("L10_hours","L10",         dp=0)

    # ── Discharge ────────────────────────────────────────────────
    # Backend returns: cr, theta_rel
    cr      = rv("centrifugal_ratio","cr",        dp=3)
    theta   = rv("release_angle_deg","theta_rel", dp=1)

    # ── Spacing ──────────────────────────────────────────────────
    # Backend returns: spacing (m)
    spacing = r.get("spacing_m") or r.get("spacing")
    spacing_mm = f"{spacing*1000:.0f}" if spacing else "—"

    # ── Component design fields (may not be in backend) ──────────
    casing_t = rv("casing_t_mm",    dp=1)
    therm    = rv("thermal_exp_mm", dp=1)
    boot_v   = rv("boot_vol_min_m3",dp=4)

    # ── Bucket fields — backend uses: id, W, H, P, V, type, name ─
    bkt_ser = bkt.get("series") or bkt.get("id") or "—"
    bkt_w   = bkt.get("width_mm")  or bkt.get("W") or "—"
    bkt_d   = bkt.get("depth_mm")  or bkt.get("H") or "—"
    bkt_p   = bkt.get("projection_mm") or bkt.get("P") or "—"
    bkt_v   = bkt.get("volume_L")  or bkt.get("V") or "—"
    bkt_st  = bkt.get("style")     or bkt.get("type") or "centrifugal"

    # ── Material — backend uses: rho_loose, name, abr_code ────────
    mat_name    = mat.get("name") or inp.get("mat_id","Custom")
    mat_density = mat.get("rho_loose") or mat.get("rho") or r.get("rho") or inp.get("rho_kgm3","—")

    # ── Status booleans ───────────────────────────────────────────
    cap_ok  = float(r.get("Q_th") or r.get("Q") or 0) >= float(inp.get("Q_req",0))
    v_raw   = float(r.get("v_ms") or r.get("v") or 0)
    spd_ok  = v_raw >= 0.5
    cr_val  = float(r.get("centrifugal_ratio") or r.get("cr") or 0)
    cr_ok   = 1.0 <= cr_val <= 2.5
    l10_raw = float(r.get("L10_hours") or r.get("L10") or 0)
    l10_ok  = l10_raw >= 20000
    belt_ok = t1_raw <= 50000

    # ── Story ──────────────────────────────────────────────────────
    story = []

    # 1. Header
    story += header_flowables(inp, r, project, doc_ref)

    # 2. Key KPIs (top row)
    story += kpi_row([
        ("Capacity",         Q_th,    "t/h",  "ok" if cap_ok else "fail"),
        ("Belt Speed",        v_ms,    "m/s",  "ok" if spd_ok else "warn"),
        ("Total Power",       P_total, "kW",   "info"),
        ("Motor Selected",    str(motor), "kW", "info"),
        ("Centrifugal Ratio", cr,      "—",    "ok" if cr_ok else "warn"),
        ("Bearing L10",       L10,     "h",    "ok" if l10_ok else "warn"),
    ])

    # 3. Two-column: Process inputs | Belt tensions
    left_rows = [
        ("Required capacity",  f"{inp.get('Q_req','—')} t/h"),
        ("Lift height",        f"{inp.get('H_m','—')} m"),
        ("Material",           mat_name),
        ("Bulk density",       f"{mat_density} kg/m³"),
        ("Head pulley dia.",   f"{inp.get('D_mm','—')} mm"),
        ("Head shaft speed",   f"{inp.get('n_rpm','—')} rpm"),
        ("Fill factor",        f"{inp.get('fill_pct','—')}%"),
        ("Service factor",     f"{inp.get('sf','—')}"),
    ]
    right_rows = [
        ("Effective tension",  f"{F_eff} kN"),
        ("Tight side T\u2081", f"{T1} kN"),
        ("Slack side T\u2082", f"{T2} kN"),
        ("Tension ratio",      t_ratio),
        ("Slip limit e\u1d50\u1d9d", slip_lim),
        ("Belt class",         str(belt_cls)),
        ("Belt width",         f"{belt_w} mm"),
        ("Friction \u03bc / wrap", f"{inp.get('mu','—')} / {inp.get('wrap_deg','—')}\u00b0"),
    ]

    story += section("1. Design Parameters & Belt Tensions")
    tbl = two_col(
        data_table(left_rows),
        data_table(right_rows),
    )
    story.append(tbl)

    # 4. Two-column: Bucket geometry | Shaft & drive
    bkt_rows = [
        ("Series / style",     f"{bkt_ser} — {bkt_st}"),
        ("Width \u00d7 depth", f"{bkt_w} \u00d7 {bkt_d} mm"),
        ("Projection (P)",     f"{bkt_p} mm"),
        ("Volume (struck)",    f"{bkt_v} L"),
        ("Spacing",            f"{spacing_mm} mm"),
        ("Buckets per metre",  f"{1/spacing:.2f}" if spacing else "—"),
        ("Active vol/bucket",  f"{float(bkt_v or 0)*inp.get('fill_pct',75)/100:.3f} L" if bkt_v != '—' else "—"),
    ]
    shaft_rows = [
        ("Shaft torque",       f"{shaft_T} Nm"),
        ("Min shaft dia.",     f"{shaft_d} mm"),
        ("Governed by",        governed_by),
        ("Allowable shear",    "55 MPa (mild steel)"),
        ("L10 bearing life",   f"{L10} h"),
        ("Discharge angle",    f"{theta}\u00b0 from vertical"),
        ("Casing thickness",   f"{casing_t} mm"),
        ("Thermal expansion",  f"{therm} mm (\u0394T=80\u00b0C)"),
        ("Boot min. volume",   f"{boot_v} m\u00b3"),
    ]

    story += section("2. Bucket Geometry & Mechanical Design")
    tbl2 = two_col(
        data_table(bkt_rows),
        data_table(shaft_rows),
    )
    story.append(tbl2)

    # 5. Power breakdown
    story += section("3. Power Breakdown")
    pw_rows = [
        ("Lift power  (Q\u00d7H / 367)",              f"{P_lift} kW"),
        ("Drive losses / friction",                    f"{P_frict} kW"),
        ("Boot digging power",                         f"{P_dig} kW"),
        ("Total shaft power  (\u00d7Ceff)",            f"{P_total} kW"),
        (f"Design power  (\u00d7SF {inp.get('sf',1.25)})",
                f"{fmt(float(r.get('P_total',0) or 0) * float(inp.get('sf',1.25)),2)} kW"),
        ("Selected motor",                             f"{motor} kW"),
        ("Required gearbox ratio",
                f"{1450/inp.get('n_rpm',60):.1f} : 1  (@ 1450 rpm input)"),
    ]
    story += data_table(pw_rows)

    # 6. Inlet chute
    if ic:
        story += section("4. Inlet Chute Design")
        chute_rows = [
            ("Inlet area required",  f"{fmt(ic.get('area_m2'),4)} m\u00b2"),
            ("Chute width",          f"{fmt(ic.get('width_mm'),0)} mm"),
            ("Chute slope angle",    f"{fmt(ic.get('chute_angle'),1)}\u00b0"),
            ("Feed velocity",        f"{fmt(ic.get('feed_v_ms'),2)} m/s"),
            ("Liner recommendation", ic.get("liner","—")),
        ]
        story += data_table(chute_rows)

    # 7. Engineering checks
    checks = r.get("checks") or []
    if checks:
        story += section("5. Engineering Validation Checks")
        story += checks_table(checks)

    # 8. Notes / disclaimer
    story += section("6. Notes")
    notes = [
        "Shaft sizing based on pure torsion at 55 MPa allowable shear (mild steel). "
        "Apply 15\u201320% margin for keyway stress concentration and combined bending in detailed design.",
        "Belt ply rating requires verification against manufacturer\u2019s catalogue "
        "using working tension per mm belt width with SF \u2265 6.",
        "Bearing L10 life computed from combined head-shaft radial load (T1 + T2). "
        "Consult bearing manufacturer for actual catalogue selection.",
        "Thermal expansion based on \u0394T = 80\u00b0C and steel \u03b1 = 12\u00d710\u207b\u2076/\u00b0C. "
        "Verify against actual operating temperature.",
        "This report is a preliminary engineering estimate. Full detailed design, "
        "structural analysis, and CEMA standard compliance verification are required "
        "before fabrication.",
    ]
    for n in notes:
        story.append(Paragraph(f"\u2022  {n}", ST["caption"]))
        story.append(Spacer(1, 2))

    # 9. Footer line
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
    story.append(Spacer(1, 2))
    story.append(Paragraph(
        f"VECTRIX\u2122 Bucket Elevator Module  \u2022  Jayveecons Engineering &amp; Design  "
        f"\u2022  Generated {datetime.now().strftime('%d %b %Y %H:%M')}  "
        f"\u2022  AkshayVipra EL-MEC PVT. LTD.",
        ST["footer"]
    ))

    # ── Build ──────────────────────────────────────────────────────
    doc.build(story)
    pdf_bytes = buf.getvalue()

    if output_path:
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)

    return pdf_bytes


# ─── CLI test with sample data ────────────────────────────────────
if __name__ == "__main__":
    sample_inputs = {
        "Q_req": 120, "H_m": 30, "mat_id": "limestone",
        "rho_kgm3": 1450, "D_mm": 500, "n_rpm": 65,
        "fill_pct": 75, "bucket_gap": 20,
        "mu": 0.35, "wrap_deg": 180, "sf": 1.25,
    }
    sample_results = {
        "Q_th": 123.4, "v_ms": 1.70, "spacing_m": 0.275,
        "centrifugal_ratio": 1.19, "release_angle_deg": 33.2,
        "power_P_lift": 9.82, "power_P_frict": 0.59, "power_P_dig": 0.41,
        "power_P_total": 11.87,
        "T1": 13420, "T2": 4470, "F_eff": 8950,
        "tension_ratio": 3.00, "slip_limit": 3.003,
        "shaft_torque_Nm": 1740, "shaft_d_mm": 52.4,
        "motor_kW": 15, "belt_width_mm": 330, "belt_class": "EP400",
        "L10_hours": 38200,
        "casing_t_mm": 3.9, "thermal_exp_mm": 28.8, "boot_vol_min_m3": 0.0235,
        "bucket": {
            "series": "A", "style": "centrifugal",
            "width_mm": 254, "depth_mm": 178, "projection_mm": 165,
            "volume_L": 5.0,
        },
        "material": {
            "name": "Limestone (crushed)", "rho": 1450,
            "Km": 1.2, "abr": "C",
        },
        "inlet_chute": {
            "area_m2": 0.0082, "width_mm": 635,
            "chute_angle": 48.0, "feed_v_ms": 1.36, "liner": "AR400",
        },
        "trajectory": [],
        "checks": [
            {"status": "pass", "code": "CAP",  "msg": "Capacity 123.4 t/h \u2265 required 120 t/h"},
            {"status": "pass", "code": "SPD",  "msg": "Belt speed 1.70 m/s OK"},
            {"status": "pass", "code": "CR",   "msg": "CR=1.190 — centrifugal discharge OK (1.0\u20132.5)"},
            {"status": "pass", "code": "SLIP", "msg": "T1/T2=3.000 vs e^\u03bc\u03b8=3.003 — no slip"},
            {"status": "pass", "code": "BELT", "msg": "T1=13.4 kN — belt class EP400"},
            {"status": "pass", "code": "BRG",  "msg": "Bearing L10=38200 h"},
        ],
        "status": "pass",
    }

    out = "/mnt/user-data/outputs/bucket_elevator_report.pdf"
    build_report(sample_results, sample_inputs,
                 project="Cement Plant SC-101",
                 doc_ref="VX-BE-2024-001",
                 output_path=out)
    print(f"Report written to {out}")


# ═══════════════════════════════════════════════════════════════════════════════
# VARIANT COMPARISON REPORT
# Generates a single PDF comparing multiple optimizer candidates side-by-side
# ═══════════════════════════════════════════════════════════════════════════════

def build_variant_report(candidates: list, inputs: dict,
                         project: str = "", doc_ref: str = "",
                         output_path: "str | None" = None) -> bytes:
    """
    Build A4 portrait PDF comparing multiple optimizer candidates.
    candidates: list of optimizer result dicts (from run_optimizer).
    inputs: the base BucketElevatorInput dict.
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

    # ── Header ────────────────────────────────────────────────────
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

    # ── Design basis ──────────────────────────────────────────────
    story += section("Design Basis")
    basis = [
        ("Required capacity", f"{inp.get('Q_req','—')} t/h"),
        ("Lift height",       f"{inp.get('H_m','—')} m"),
        ("Material",          inp.get('mat_id','—')),
        ("Head pulley dia.",  f"{inp.get('D_mm','—')} mm"),
        ("Service factor",    str(inp.get('sf','—'))),
        ("Fill target",       f"{inp.get('fill_pct','—')}%"),
    ]
    cw = [(W-ML-MR)*0.4, (W-ML-MR)*0.6]
    story += data_table(basis, col_widths=cw)

    # ── Variant comparison table ──────────────────────────────────
    story += section("Variant Comparison")

    col_labels = ["Parameter", "Units"] + [f"Variant {i+1}" for i in range(n)]
    col_w_first = 42 * mm
    col_w_unit  = 14 * mm
    col_w_var   = (W - ML - MR - col_w_first - col_w_unit) / max(n, 1)
    col_widths  = [col_w_first, col_w_unit] + [col_w_var] * n

    def vrow(label, unit, getter):
        """Build one comparison row across all candidates."""
        vals = []
        for c in candidates:
            try:
                vals.append(str(getter(c)))
            except Exception:
                vals.append("—")
        return [Paragraph(label, ST["body"]),
                Paragraph(unit,  ST["caption"])] + \
               [Paragraph(v, ST["mono"]) for v in vals]

    header_row = [Paragraph(h, ST["h3"]) for h in col_labels]

    table_data = [header_row,
        vrow("Bucket series",    "—",    lambda c: c.get("bucket_id","—")),
        vrow("RPM",              "rpm",  lambda c: c.get("rpm","—")),
        vrow("Fill factor",      "%",    lambda c: c.get("fill","—")),
        vrow("Belt speed",       "m/s",  lambda c: c.get("speed","—")),
        vrow("Capacity",         "t/h",  lambda c: c.get("capacity","—")),
        vrow("Total power",      "kW",   lambda c: c.get("power","—")),
        vrow("Motor selected",   "kW",   lambda c: c.get("motor_kw","—")),
        vrow("Head load T",      "kN",   lambda c: c.get("T1_kN","—")),
        vrow("Centrifugal ratio","—",    lambda c: c.get("cr","—")),
        vrow("Score",            "—",    lambda c: fmt(c.get("score"),3)),
        vrow("Rank",             "—",    lambda c: c.get("rank","—")),
    ]

    # Status colour for score row (rank 1 = green, others neutral)
    ranks = [c.get("rank", 99) for c in candidates]

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

    # Highlight best variant column
    best_rank_idx = ranks.index(min(ranks)) if ranks else 0
    col_idx = 2 + best_rank_idx
    style_cmds.append(("LINEABOVE",  (col_idx, 0), (col_idx, 0), 2.5, GREEN))
    style_cmds.append(("LINEBELOW",  (col_idx, len(table_data)-1),
                        (col_idx, len(table_data)-1), 1.5, GREEN))

    t.setStyle(TableStyle(style_cmds))
    story += [t, Spacer(1, 6)]

    # ── Per-variant checks summary ────────────────────────────────
    story += section("Engineering Validation by Variant")
    for i, c in enumerate(candidates):
        story.append(Paragraph(
            f"<b>Variant {i+1}</b>  —  Bucket {c.get('bucket_id','—')} · "
            f"{c.get('rpm','—')} RPM · Fill {c.get('fill','—')}% · "
            f"P={c.get('power','—')} kW · CR={c.get('cr','—')}",
            ST["h3"]
        ))
        # Quick pass/warn/fail based on key values
        cv   = float(c.get("capacity", 0) or 0)
        Q_req = float(inp.get("Q_req", 0))
        cr_v  = float(c.get("cr", 0) or 0)
        chks = [
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

    # ── Footer ────────────────────────────────────────────────────
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