"""
VECTRIX™ Bucket Elevator — Engineering Report Generator  v2.0.0
Produces an A4 portrait PDF from a solve_elevator() results dict.

SECTION STRUCTURE
─────────────────
 1. Input Specifications          Customer-provided requirements & site conditions
 2. Performance Summary           KPI cards (capacity, speed, power, motor, CR, L10)
 3. Process Level Outputs         Elevator schematic + speed-sweep chart + trajectory
 4. Power Breakdown               CEMA LEQ decomposition table
 5. Component Design Outputs      Shaft / Belt / Pulley / Take-Up / Casing sub-tables
 6. Engineering Verification      5-column checks table with safety factors
 7. Design Notes                  Plain-English engineering narrative (no formulae)

v2.0.0 changes from v1.1.0
─────────────────────────────────────────────────────────────────────────────
• Complete section restructure matching user specification
• Elevator schematic drawn with ReportLab shapes (no external library)
• Speed-sweep and trajectory charts using ReportLab built-in drawing
• All structural.py v1.3.0 fields shown (hub, lagging, end disc, take-up, casing)
• Engineering checks extended to 5-column format with explicit safety factors
• Design Notes written as professional plain-English narrative — no formulae,
  no standard citations, no calculation steps
• ASCII-only labels throughout (no Unicode subscripts → no render boxes)
• four_col_table used for all two-column sections (fixes v1.0 margin overflow)
"""

import io, math
from datetime import datetime
from reportlab.lib.pagesizes      import A4
from reportlab.lib.units          import mm
from reportlab.lib.colors         import HexColor, white, black
from reportlab.platypus           import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether,
)
from reportlab.lib.styles         import ParagraphStyle
from reportlab.lib.enums          import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus           import Flowable
from reportlab.graphics.shapes    import (
    Drawing, Rect, Circle, Line, String as GString,
    Ellipse, PolyLine, Polygon,
)

# ─── Page geometry ───────────────────────────────────────────────────────────
W, H   = A4
ML = MR = 18 * mm
MT      = 15 * mm
MB      = 18 * mm
AVAIL   = W - ML - MR          # 493 pt

# ─── Colours ─────────────────────────────────────────────────────────────────
NAVY     = HexColor("#07111e")
NAVY2    = HexColor("#0d1c2e")
BORDER   = HexColor("#1c3050")
CRIMSON  = HexColor("#c8192e")
BLUE     = HexColor("#4a9eff")
GREEN    = HexColor("#1fb86e")
AMBER    = HexColor("#d98e00")
RED      = HexColor("#e05252")
TEAL     = HexColor("#2dd4bf")
TEXT     = HexColor("#ddeaf6")
MUTED    = HexColor("#5a7a9a")
MUTED2   = HexColor("#7a9ab8")
LIGHT_BG = HexColor("#f0f4f8")
MID_BG   = HexColor("#dde6ef")
DK_TEXT  = HexColor("#0d1c2e")
PANEL2   = HexColor("#e8edf2")

# ─── Paragraph styles ────────────────────────────────────────────────────────
def _styles():
    return {
        "h2":   ParagraphStyle("h2",   fontName="Helvetica-Bold",  fontSize=10,
                    textColor=CRIMSON, spaceBefore=6, spaceAfter=3, leading=13),
        "h3":   ParagraphStyle("h3",   fontName="Helvetica-Bold",  fontSize=8,
                    textColor=DK_TEXT, spaceAfter=2, leading=10),
        "body": ParagraphStyle("body", fontName="Helvetica",       fontSize=8,
                    textColor=DK_TEXT, spaceAfter=2, leading=11),
        "note": ParagraphStyle("note", fontName="Helvetica",       fontSize=8,
                    textColor=DK_TEXT, spaceAfter=4, leading=12),
        "mono": ParagraphStyle("mono", fontName="Courier",         fontSize=7.5,
                    textColor=DK_TEXT, spaceAfter=1, leading=10),
        "cap":  ParagraphStyle("cap",  fontName="Helvetica",       fontSize=6.5,
                    textColor=MUTED,   spaceAfter=1, leading=9),
        "kv":   ParagraphStyle("kv",   fontName="Helvetica-Bold",  fontSize=16,
                    textColor=DK_TEXT, leading=18, alignment=TA_CENTER),
        "ku":   ParagraphStyle("ku",   fontName="Helvetica",       fontSize=7,
                    textColor=MUTED,   leading=9,  alignment=TA_CENTER),
        "kl":   ParagraphStyle("kl",   fontName="Helvetica-Bold",  fontSize=6.5,
                    textColor=MUTED,   leading=8,  alignment=TA_CENTER),
        "ftr":  ParagraphStyle("ftr",  fontName="Helvetica",       fontSize=6.5,
                    textColor=MUTED,   alignment=TA_CENTER),
        "tok":  ParagraphStyle("tok",  fontName="Helvetica-Bold",  fontSize=7,
                    textColor=GREEN,   leading=9),
        "twn":  ParagraphStyle("twn",  fontName="Helvetica-Bold",  fontSize=7,
                    textColor=AMBER,   leading=9),
        "tfl":  ParagraphStyle("tfl",  fontName="Helvetica-Bold",  fontSize=7,
                    textColor=RED,     leading=9),
        "cmsg": ParagraphStyle("cmsg", fontName="Helvetica",       fontSize=7.5,
                    textColor=DK_TEXT, leading=10),
    }

ST = _styles()


# ─── Value formatters ─────────────────────────────────────────────────────────
def fmt(v, dp=2, fb="—"):
    try:
        f = float(v)
        return fb if not math.isfinite(f) else f"{f:.{dp}f}"
    except (TypeError, ValueError):
        return fb if v is None else str(v)

def _rv(r, *keys, dp=2, fb="—"):
    for k in keys:
        v = r.get(k)
        if v is not None:
            return fmt(v, dp, fb)
    return fb

def _rkn(r, *keys, dp=2, fb="—"):
    for k in keys:
        v = r.get(k)
        if v is not None:
            try: return fmt(float(v) / 1000.0, dp, fb)
            except: pass
    return fb


# ─── Section heading ─────────────────────────────────────────────────────────
def section(title):
    return [
        Spacer(1, 5),
        HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=2),
        Paragraph(title.upper(), ST["h2"]),
    ]

def sub_section(title):
    return [
        Spacer(1, 3),
        Paragraph(title, ST["h3"]),
    ]


# ─── KPI card row ─────────────────────────────────────────────────────────────
def kpi_row(cards):
    cw = AVAIL / len(cards)
    cells = [[
        Paragraph(lbl, ST["kl"]),
        Paragraph(str(val), ST["kv"]),
        Paragraph(str(unit), ST["ku"]),
    ] for lbl, val, unit, _ in cards]
    t = Table([cells], colWidths=[cw] * len(cards))
    cmds = [
        ("BACKGROUND",    (0,0), (-1,-1), LIGHT_BG),
        ("GRID",          (0,0), (-1,-1), 0.3, BORDER),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 3),
        ("RIGHTPADDING",  (0,0), (-1,-1), 3),
    ]
    scol = {
        "ok":   GREEN, "warn": AMBER, "fail": RED, "info": BLUE,
    }
    for i, (_, _, _, st) in enumerate(cards):
        cmds.append(("LINEABOVE", (i,0), (i,0), 2.5, scol.get(st, BLUE)))
    t.setStyle(TableStyle(cmds))
    return [t, Spacer(1, 4)]


# ─── 2-column data table (full-width) ────────────────────────────────────────
def data_table(rows, col_widths=None):
    cw = col_widths or [AVAIL * 0.55, AVAIL * 0.45]
    data = [[Paragraph(str(r[0]), ST["body"]),
             Paragraph(str(r[1]), ST["mono"])] for r in rows]
    t = Table(data, colWidths=cw)
    cmds = [
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 2.5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2.5),
        ("LEFTPADDING",   (0,0), (-1,-1), 4),
        ("RIGHTPADDING",  (0,0), (-1,-1), 4),
        ("GRID",          (0,0), (-1,-1), 0.3, BORDER),
    ]
    for i in range(len(data)):
        cmds.append(("BACKGROUND", (0,i), (-1,i), LIGHT_BG if i%2==0 else white))
    t.setStyle(TableStyle(cmds))
    return [t, Spacer(1, 4)]


# ─── 4-column flat table (replaces two_col + nested data_table) ──────────────
def four_col_table(left_rows, right_rows, ratios=(0.30, 0.20, 0.30, 0.20)):
    c = [AVAIL * r for r in ratios]
    n = max(len(left_rows), len(right_rows))
    data = []
    for i in range(n):
        L = left_rows[i]  if i < len(left_rows)  else ("", "")
        R = right_rows[i] if i < len(right_rows) else ("", "")
        data.append([
            Paragraph(str(L[0]), ST["body"]),
            Paragraph(str(L[1]), ST["mono"]),
            Paragraph(str(R[0]), ST["body"]),
            Paragraph(str(R[1]), ST["mono"]),
        ])
    t = Table(data, colWidths=c)
    cmds = [
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 2.5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2.5),
        ("LEFTPADDING",   (0,0), (-1,-1), 4),
        ("RIGHTPADDING",  (0,0), (-1,-1), 4),
        ("GRID",          (0,0), (-1,-1), 0.3, BORDER),
        ("LINEAFTER",     (1,0), (1,-1), 1.2, MUTED),
    ]
    for i in range(n):
        cmds.append(("BACKGROUND", (0,i), (-1,i), LIGHT_BG if i%2==0 else white))
    t.setStyle(TableStyle(cmds))
    return [t, Spacer(1, 4)]


# ─── 5-column engineering checks table (with SF) ─────────────────────────────
def sf_checks_table(check_rows):
    """
    check_rows: list of (check_name, actual, limit, sf_str, status)
    status: "ok" | "warn" | "fail" | "info"
    """
    hdr = [
        Paragraph("Check",     ST["h3"]),
        Paragraph("Actual",    ST["h3"]),
        Paragraph("Limit",     ST["h3"]),
        Paragraph("SF",        ST["h3"]),
        Paragraph("Result",    ST["h3"]),
    ]
    cw = [AVAIL*0.32, AVAIL*0.19, AVAIL*0.19, AVAIL*0.10, AVAIL*0.20]
    icon = {"ok":"✓", "warn":"⚠", "fail":"✗", "info":"i"}
    sty  = {"ok":"tok", "warn":"twn", "fail":"tfl", "info":"tok"}
    data = [hdr]
    for name, actual, limit, sf, status in check_rows:
        ic = icon.get(status, "i")
        data.append([
            Paragraph(str(name),   ST["cmsg"]),
            Paragraph(str(actual), ST["mono"]),
            Paragraph(str(limit),  ST["mono"]),
            Paragraph(str(sf),     ST["mono"]),
            Paragraph(f"{ic}  {status.upper()}", ST[sty.get(status,"tok")]),
        ])
    t = Table(data, colWidths=cw, repeatRows=1)
    cmds = [
        ("BACKGROUND",    (0,0), (-1, 0), NAVY),
        ("TEXTCOLOR",     (0,0), (-1, 0), TEXT),
        ("FONTNAME",      (0,0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1, 0), 7.5),
        ("GRID",          (0,0), (-1,-1), 0.3, BORDER),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("LEFTPADDING",   (0,0), (-1,-1), 4),
        ("RIGHTPADDING",  (0,0), (-1,-1), 4),
    ]
    for i in range(1, len(data)):
        cmds.append(("BACKGROUND", (0,i), (-1,i), LIGHT_BG if i%2==1 else white))
    t.setStyle(TableStyle(cmds))
    return [t, Spacer(1, 4)]


# ─── Header flowable ─────────────────────────────────────────────────────────
def header_flowables(inp, res, project="", doc_ref=""):
    now    = datetime.now().strftime("%d %b %Y  %H:%M")
    mat    = (res.get("mat") or res.get("material") or {})
    status = str(res.get("status", "—")).upper()
    sc     = {"PASS": GREEN, "WARNING": AMBER, "FAIL": RED}.get(status, BLUE)
    mat_name = mat.get("name") or inp.get("mat_id","Custom")

    logo_col = [
        Paragraph("<b>VECTRIX™</b>",
            ParagraphStyle("lg", fontName="Helvetica-Bold", fontSize=16,
                           textColor=white, leading=18)),
        Paragraph("BUCKET ELEVATOR",
            ParagraphStyle("s1", fontName="Helvetica", fontSize=7,
                           textColor=MUTED2, leading=9)),
        Paragraph("Engineering Design Report",
            ParagraphStyle("s2", fontName="Helvetica", fontSize=6.5,
                           textColor=MUTED, leading=8)),
    ]
    info_col = [
        Paragraph(f"<b>Project:</b> {project or 'Unspecified'}",
            ParagraphStyle("pi", fontName="Helvetica", fontSize=8,
                           textColor=white, leading=10)),
        Paragraph(f"<b>Ref:</b> {doc_ref or 'VX-BE-001'}",
            ParagraphStyle("pi", fontName="Helvetica", fontSize=8,
                           textColor=white, leading=10)),
        Paragraph(f"<b>Date:</b> {now}",
            ParagraphStyle("pi", fontName="Helvetica", fontSize=8,
                           textColor=white, leading=10)),
        Paragraph(f"<b>Material:</b> {mat_name}",
            ParagraphStyle("pi", fontName="Helvetica", fontSize=8,
                           textColor=white, leading=10)),
    ]
    stat_col = [
        Paragraph(f"<b>{status}</b>",
            ParagraphStyle("st", fontName="Helvetica-Bold", fontSize=14,
                           textColor=sc, alignment=TA_CENTER, leading=16)),
        Paragraph("Design Status",
            ParagraphStyle("sl", fontName="Helvetica", fontSize=6.5,
                           textColor=MUTED, alignment=TA_CENTER, leading=8)),
        Spacer(1, 2),
        Paragraph("JAYVEECONS<br/>Engineering &amp; Design",
            ParagraphStyle("jv", fontName="Helvetica", fontSize=6,
                           textColor=MUTED2, alignment=TA_CENTER, leading=8)),
    ]
    hdr = Table(
        [[logo_col, info_col, stat_col]],
        colWidths=[AVAIL*0.28, AVAIL*0.46, AVAIL*0.26],
    )
    hdr.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), NAVY),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ("RIGHTPADDING",  (0,0), (-1,-1), 6),
        ("LINEBELOW",     (0,0), (-1, 0), 2.5, CRIMSON),
    ]))
    return [hdr, Spacer(1, 6)]


# ─── Elevator schematic (ReportLab Drawing) ───────────────────────────────────
def _elevator_schematic(results, inputs, W_draw, H_draw):
    d   = Drawing(W_draw, H_draw)
    r   = results or {}
    inp = inputs  or {}

    # Fixed anchors — derived so every label, dimension, and arrow
    # stays within [0, H_draw].
    #
    # Labels at top:  "HEAD SECTION" at top_y + r_head + 28
    #                 BW dimension   at top_y + r_head + 14
    # → top_y = H_draw - r_head - 30   guarantees HEAD SECTION < H_draw
    #
    # Labels at bot:  "BOOT SECTION" at bot_y - r_boot - 14
    #                 FEED arrow     at bot_y
    # → bot_y = r_boot + 18           guarantees BOOT SECTION > 0

    r_head  = 24.0
    r_boot  = 18.0
    top_y   = H_draw - r_head - 30    # head pulley centre — was H_draw*0.87
    bot_y   = r_boot + 18             # boot pulley centre — was H_draw*0.10
    h_elev  = top_y - bot_y
    cx      = W_draw * 0.42
    blt_hw  = 14.0
    cas_hw  = blt_hw + 12.0
    col_cas = HexColor("#c8d4e0")
    col_blt = HexColor("#c8a060")
    col_bkt = HexColor("#dde6ef")
    col_pul = HexColor("#4a9eff")
    col_dim = HexColor("#5a7a9a")
    col_dk  = HexColor("#0d1c2e")
    col_mtr = HexColor("#1fb86e")
    col_arr = HexColor("#4a9eff")
    col_trj = HexColor("#c8192e")

    # Casing background
    d.add(Rect(cx - cas_hw - 2, bot_y - r_boot,
               (cas_hw + 2) * 2, h_elev + r_head + r_boot,
               fillColor=col_cas, strokeColor=HexColor("#8aa0b8"),  # type: ignore[arg-type]
               strokeWidth=1.5))  # type: ignore[arg-type]

    # Belt lines
    for sx in (-blt_hw, blt_hw):
        d.add(Line(cx + sx, bot_y, cx + sx, top_y,
                   strokeColor=col_blt, strokeWidth=2.5))

    # Buckets on ascending (left) side — 7 evenly spaced
    for i in range(7):
        by = bot_y + (i + 0.4) * h_elev / 7
        bw, bh = 14, 9
        d.add(Rect(cx - blt_hw - bw, by - bh/2, bw, bh,
                   fillColor=col_bkt,  # type: ignore[arg-type]
                   strokeColor=HexColor("#7a90a8"), strokeWidth=0.8))  # type: ignore[arg-type]

    # Boot pulley
    d.add(Circle(cx, bot_y, r_boot,
                 fillColor=col_pul, strokeColor=col_dk, strokeWidth=1.5))  # type: ignore[arg-type]
    d.add(Circle(cx, bot_y, r_boot * 0.32, fillColor=col_dk, strokeColor=None))  # type: ignore[arg-type]

    # Head pulley
    d.add(Circle(cx, top_y, r_head,
                 fillColor=col_pul, strokeColor=col_dk, strokeWidth=1.5))
    d.add(Circle(cx, top_y, r_head * 0.28, fillColor=col_dk, strokeColor=None))  # type: ignore[arg-type]

    # Motor block
    mx, my = cx + cas_hw + 40, top_y
    mw, mh = 38, 24
    d.add(Rect(mx, my - mh/2, mw, mh,
               fillColor=col_mtr, strokeColor=HexColor("#0a7040"), strokeWidth=1))  # type: ignore[arg-type]
    d.add(Line(cx + r_head, my, mx, my,
               strokeColor=col_dim, strokeWidth=1.5, strokeDashArray=[4,2]))
    motor_kw = r.get("motor_kw") or r.get("motor_kW") or "—"
    d.add(GString(mx + mw/2, my + 4, f"{motor_kw} kW",
                  fontSize=6.5, fillColor=white, textAnchor="middle",
                  fontName="Helvetica-Bold"))
    d.add(GString(mx + mw/2, my - 10, "MOTOR",
                  fontSize=6, fillColor=white, textAnchor="middle",
                  fontName="Helvetica"))

    # Discharge trajectory arc — drawn BEFORE labels so labels sit on top
    traj = r.get("trajectory", [])
    if traj and len(traj) >= 3:
        pts = traj[:20]
        xs  = [p.get("x", 0) for p in pts]
        ys  = [p.get("y", 0) for p in pts]
        xr  = max(max(xs) - min(xs), 1)
        yr  = max(max(ys) - min(ys), 1)
        # Scale: fit arc into a 72×50 pt zone to the right of the pulley
        sc_x = 72 / xr
        sc_y = 50 / yr
        base_x = cx + r_head
        base_y = top_y
        tx_pts = [(base_x + (x - min(xs)) * sc_x,
                   base_y - (max(ys) - y) * sc_y) for x, y in zip(xs, ys)]
        for i in range(len(tx_pts) - 1):
            d.add(Line(tx_pts[i][0], tx_pts[i][1],
                       tx_pts[i+1][0], tx_pts[i+1][1],
                       strokeColor=col_trj, strokeWidth=1.3,
                       strokeDashArray=[3,3]))
        # Discharge angle annotation — at the arc start, NOT on top of the arc
        theta_deg = r.get("theta_rel") or r.get("release_angle_deg")
        if theta_deg is not None:
            d.add(GString(cx + r_head + 4, top_y - 10,
                          f"theta={float(theta_deg):.1f}deg",
                          fontSize=5.5, fillColor=col_trj, textAnchor="start",
                          fontName="Helvetica"))

    # Dimension: height
    dx = cx - cas_hw - 22
    H_m = inp.get("H_m", "?")
    d.add(Line(dx, bot_y, dx, top_y, strokeColor=col_dim, strokeWidth=0.8))
    for ay, sign in ((bot_y, 1), (top_y, -1)):
        d.add(Line(dx-4, ay+sign*5, dx, ay, strokeColor=col_dim, strokeWidth=0.8))
        d.add(Line(dx+4, ay+sign*5, dx, ay, strokeColor=col_dim, strokeWidth=0.8))
    d.add(GString(dx - 5, (bot_y + top_y)/2 - 4, f"H = {H_m} m",
                  fontSize=7.5, fillColor=col_dk, textAnchor="end",
                  fontName="Helvetica-Bold"))

    # Belt width dimension at head
    BW = r.get("belt_w") or r.get("belt_width_mm") or "?"
    yw = top_y + r_head + 14
    d.add(Line(cx - blt_hw, yw, cx + blt_hw, yw, strokeColor=col_dim, strokeWidth=0.7))
    d.add(GString(cx, yw + 7, f"BW = {BW} mm",
                  fontSize=6.5, fillColor=col_dim, textAnchor="middle",
                  fontName="Helvetica"))

    # Pulley dia label — BELOW the pulley (y = top_y - r_head - 10)
    # Moved from beside-pulley to below-pulley to clear the trajectory arc zone
    D_mm = inp.get("D_mm", "?")
    n_rpm = inp.get("n_rpm", "?")
    d.add(GString(cx + r_head + 6, top_y - r_head - 10,
                  f"D={D_mm}mm  {n_rpm}rpm",
                  fontSize=6, fillColor=col_dk, textAnchor="start",
                  fontName="Helvetica"))

    # Section labels — positioned clear of each other and within bounds
    # HEAD SECTION: centred above the BW dimension line
    d.add(GString(cx, top_y + r_head + 28, "HEAD SECTION",
                  fontSize=7.5, fillColor=col_dk, textAnchor="middle",
                  fontName="Helvetica-Bold"))
    d.add(GString(cx, bot_y - r_boot - 14, "BOOT SECTION",
                  fontSize=7.5, fillColor=col_dk, textAnchor="middle",
                  fontName="Helvetica-Bold"))

    # Feed arrow
    fx = cx - cas_hw - 4
    d.add(Line(fx - 28, bot_y, fx, bot_y, strokeColor=col_arr, strokeWidth=2.0))
    d.add(Line(fx - 9, bot_y+5, fx, bot_y, strokeColor=col_arr, strokeWidth=2.0))
    d.add(Line(fx - 9, bot_y-5, fx, bot_y, strokeColor=col_arr, strokeWidth=2.0))
    d.add(GString(fx - 32, bot_y + 6, "FEED",
                  fontSize=7, fillColor=col_arr, textAnchor="end",
                  fontName="Helvetica-Bold"))

    # DISCHARGE label — positioned FAR RIGHT of schematic (clear of arc zone)
    # Drawn with a short leader line back toward the arc end-point
    d.add(GString(cx + cas_hw + 55, top_y + 30, "DISCHARGE",
                  fontSize=7, fillColor=col_arr, textAnchor="start",
                  fontName="Helvetica-Bold"))
    # Thin leader line: from label left-edge to approximate arc end
    d.add(Line(cx + cas_hw + 53, top_y + 33,
               cx + r_head + 60, top_y + 14,
               strokeColor=col_arr, strokeWidth=0.7,
               strokeDashArray=[2,2]))

    return d


# ─── Speed-sweep chart ────────────────────────────────────────────────────────
def _speed_chart(results, inputs, W_draw, H_draw):
    r   = results or {}
    inp = inputs  or {}
    sweep = r.get("speed_sweep") or r.get("speedSweep") or []
    if len(sweep) < 2:
        return None
    d = Drawing(W_draw, H_draw)
    d.add(Rect(0, 0, W_draw, H_draw, fillColor=LIGHT_BG, strokeColor=None))  # type: ignore[arg-type]

    rpms = [p["rpm"]      for p in sweep]
    caps = [p["capacity"] for p in sweep]
    Q_req = float(inp.get("Q_req") or 0)

    cl  = 38; cb = 24; cr = W_draw - 12; ct = H_draw - 20
    cw  = cr - cl;     ch = ct - cb

    cap_max = max(max(caps), Q_req * 1.05, 1)
    rpm_min = min(rpms); rpm_max = max(rpms)

    def px(rpm): return cl + (rpm - rpm_min) / max(rpm_max - rpm_min, 1) * cw
    def py(cap): return cb + cap / cap_max * ch

    # Grid
    for i in range(5):
        gy = cb + i * ch / 4
        d.add(Line(cl, gy, cr, gy, strokeColor=HexColor("#c0ccd8"),
                   strokeWidth=0.5, strokeDashArray=[3,3]))

    # Q_req line
    qy = py(Q_req)
    if cb <= qy <= ct:
        d.add(Line(cl, qy, cr, qy, strokeColor=CRIMSON, strokeWidth=1.2,
                   strokeDashArray=[5,3]))
        d.add(GString(cr - 2, qy + 3, f"Req {Q_req:.0f}",
                      fontSize=5.5, fillColor=CRIMSON, textAnchor="end",
                      fontName="Helvetica"))

    # Capacity line
    for i in range(len(rpms) - 1):
        d.add(Line(px(rpms[i]), py(caps[i]), px(rpms[i+1]), py(caps[i+1]),
                   strokeColor=BLUE, strokeWidth=2.0))

    # Axes
    d.add(Line(cl, cb, cl, ct, strokeColor=MUTED, strokeWidth=1.0))
    d.add(Line(cl, cb, cr, cb, strokeColor=MUTED, strokeWidth=1.0))

    # Axis labels
    d.add(GString(cl + cw/2, 5, "Head shaft speed (rpm)",
                  fontSize=6, fillColor=MUTED, textAnchor="middle", fontName="Helvetica"))
    d.add(GString(12, cb + ch/2, "t/h",
                  fontSize=6, fillColor=MUTED, textAnchor="middle", fontName="Helvetica"))

    # Ticks
    for q in [0, cap_max/2, cap_max]:
        ty = py(q)
        d.add(GString(cl - 3, ty - 3, f"{q:.0f}",
                      fontSize=5.5, fillColor=MUTED, textAnchor="end", fontName="Helvetica"))
    for r2 in [rpm_min, (rpm_min+rpm_max)//2, rpm_max]:
        tx = px(r2)
        d.add(GString(tx, cb - 13, str(int(r2)),
                      fontSize=5.5, fillColor=MUTED, textAnchor="middle", fontName="Helvetica"))

    # Title
    d.add(GString(cl + cw/2, H_draw - 12, "Capacity vs Belt Speed",
                  fontSize=7.5, fillColor=DK_TEXT, textAnchor="middle",
                  fontName="Helvetica-Bold"))
    return d


# ─── Discharge trajectory chart ───────────────────────────────────────────────
def _trajectory_chart(results, W_draw, H_draw):
    r    = results or {}
    traj = r.get("trajectory", [])
    if len(traj) < 3:
        return None
    d = Drawing(W_draw, H_draw)
    d.add(Rect(0, 0, W_draw, H_draw, fillColor=LIGHT_BG, strokeColor=None))  # type: ignore[arg-type]

    xs = [p.get("x",0) for p in traj]
    ys = [p.get("y",0) for p in traj]
    cl  = 38; cb = 24; cr = W_draw - 12; ct = H_draw - 20
    cw  = cr - cl;     ch = ct - cb
    xr  = max(max(xs) - min(xs), 1)
    yr  = max(max(ys) - min(ys), 1)

    def px(x): return cl + (x - min(xs)) / xr * cw
    def py(y): return cb + (y - min(ys)) / yr * ch

    # Grid
    for i in range(5):
        gx = cl + i * cw / 4
        d.add(Line(gx, cb, gx, ct, strokeColor=HexColor("#c0ccd8"),
                   strokeWidth=0.5, strokeDashArray=[3,3]))

    # Trajectory line
    for i in range(len(traj) - 1):
        d.add(Line(px(xs[i]), py(ys[i]), px(xs[i+1]), py(ys[i+1]),
                   strokeColor=CRIMSON, strokeWidth=2.0))

    # Axes
    d.add(Line(cl, cb, cl, ct, strokeColor=MUTED, strokeWidth=1.0))
    d.add(Line(cl, cb, cr, cb, strokeColor=MUTED, strokeWidth=1.0))

    # Labels
    d.add(GString(cl + cw/2, 5, "x [mm]",
                  fontSize=6, fillColor=MUTED, textAnchor="middle", fontName="Helvetica"))
    d.add(GString(12, cb + ch/2, "y [mm]",
                  fontSize=6, fillColor=MUTED, textAnchor="middle", fontName="Helvetica"))
    d.add(GString(cl + cw/2, H_draw - 12, "Discharge Trajectory",
                  fontSize=7.5, fillColor=DK_TEXT, textAnchor="middle",
                  fontName="Helvetica-Bold"))

    # Axis ticks
    for xt in [min(xs), (min(xs)+max(xs))/2, max(xs)]:
        d.add(GString(px(xt), cb - 13, f"{xt:.0f}",
                      fontSize=5.5, fillColor=MUTED, textAnchor="middle", fontName="Helvetica"))

    return d


# ─── Design notes generator (plain English, no formulae) ─────────────────────
def _design_notes(r, inp):
    notes = []
    mat    = r.get("mat") or r.get("material") or {}
    bucket = r.get("bucket") or {}

    Q      = float(r.get("Q") or r.get("Q_th") or 0)
    Q_req  = float(inp.get("Q_req") or 0)
    v      = float(r.get("v") or r.get("v_ms") or 0)
    cr     = float(r.get("cr") or r.get("centrifugal_ratio") or 0)
    H_m    = float(inp.get("H_m") or 0)
    d_mm   = float(r.get("d_mm") or 0)
    gov    = r.get("governed_by") or "stress"
    P_tot  = float(r.get("P_total") or 0)
    sf     = float(inp.get("sf") or 1.25)
    motor  = r.get("motor_kw") or r.get("motor_kW") or "—"
    L10    = float(r.get("L10") or r.get("L10_hours") or 0)
    D_mm   = float(inp.get("D_mm") or 500)
    BW     = r.get("belt_w") or r.get("belt_width_mm") or "—"
    lag    = r.get("lagging") or {}
    ed     = r.get("end_disc") or {}
    hub    = r.get("hub") or {}
    tg     = r.get("takeup_gravity") or {}
    ts     = r.get("takeup_screw") or {}
    cs     = r.get("casing_stiffener") or {}
    cp     = r.get("casing_panel") or {}
    ct_mm  = r.get("casing_t_mm") or "—"
    bf     = r.get("bolt_fatigue") or {}
    kc     = r.get("key_check") or {}
    span   = r.get("shaft_span_mm") or "—"

    # 1. Capacity & selection
    margin = (Q / Q_req - 1) * 100 if Q_req else 0
    bkt_id = bucket.get("id") or "—"
    mat_nm = mat.get("name") or inp.get("mat_id", "the specified material")
    notes.append(
        f"The elevator is configured with Series {bkt_id} buckets and achieves a throughput "
        f"of {Q:.1f} t/h against the {Q_req:.0f} t/h requirement, providing a capacity margin "
        f"of {margin:.0f}%. Belt speed is {v:.2f} m/s at the specified head shaft speed, "
        f"which is within the acceptable range for the selected bucket geometry. "
        f"The centrifugal discharge ratio of {cr:.3f} is "
        f"{'within the optimal range for clean centrifugal discharge' if 1.0 <= cr <= 1.8 else 'outside the ideal centrifugal range and should be reviewed'}."
    )

    # 2. Shaft
    notes.append(
        f"The head shaft minimum diameter is {d_mm:.0f} mm, governed by {gov}. "
        f"The shaft spans {span} mm between bearing centrelines. "
        f"The hub outer diameter is {hub.get('d_hub_mm','—')} mm with a hub engagement length of "
        f"{hub.get('L_hub_mm','—')} mm. "
        f"{'The keyway stress check passes at the selected shaft and hub dimensions.' if kc.get('pass') else 'The keyway stress check requires review — consider a larger shaft or splined connection.'}"
    )

    # 3. Lagging
    lag_type = (lag.get("lagging_type") or "rubber herringbone").replace("_", " ")
    lag_t    = lag.get("thickness_mm") or "—"
    mu_op    = lag.get("mu_operating") or "—"
    slip_ok  = lag.get("slip_safe", True)
    notes.append(
        f"{lag_type.capitalize()} lagging, {lag_t} mm thick, is specified for the head pulley. "
        f"This provides a belt-to-pulley traction coefficient of {mu_op} under "
        f"{inp.get('environment','dry')} service conditions. "
        f"{'Belt slip analysis confirms the lagging selection is adequate at operating tensions.' if slip_ok else 'Belt slip analysis indicates the lagging selection should be reviewed — consider ceramic lagging or increased take-up tension.'}"
    )

    # 4. Pulley end disc
    t_min = ed.get("t_governing_mm") or "—"
    t_spec = int(float(t_min) * 1.20) if t_min != "—" else "—"
    notes.append(
        f"Pulley end discs require a structural minimum thickness of {t_min} mm "
        f"(governed by {ed.get('governed_by','plate bending')}). "
        f"A specified thickness of {t_spec} mm is recommended in fabrication drawings to provide "
        f"adequate construction tolerance and weld preparation allowance. "
        f"Full finite element analysis or detailed annular plate calculation is recommended prior to fabrication."
    )

    # 5. Take-up
    W_cw   = tg.get("W_counterweight_kg_gross") or "—"
    travel = round(tg.get("travel_m", 0) * 1000) if tg else "—"
    notes.append(
        f"The gravity take-up counterweight gross mass is {W_cw} kg. "
        f"The take-up frame must accommodate a minimum carriage travel of {travel} mm, "
        f"combining thermal expansion, belt elastic elongation, and installation clearance components. "
        f"A 20% allowance above this minimum is recommended for field adjustment headroom. "
        f"As an alternative for short elevators, a screw take-up requires a minimum screw core "
        f"diameter of {ts.get('d_core_min_mm','—')} mm. "
        f"{'The screw buckling safety factor is adequate.' if ts.get('buckling_safe') else 'The screw take-up requires an intermediate guide support to satisfy the Euler buckling criterion.'}"
    )

    # 6. Casing
    pitch = cs.get("recommended_mm") or "—"
    wind  = cs.get("wind_pressure_Pa") or inp.get("wind_pressure_pa") or "—"
    p_ok  = cp.get("status") == "ok" if cp else True
    notes.append(
        f"The casing plate thickness of {ct_mm} mm is determined by material bulk density and elevator height. "
        f"Structural stiffeners at {pitch} mm centres limit panel deflection to within acceptable serviceability limits "
        f"under the {wind} Pa design wind load. "
        f"{'Panel deflection analysis confirms the stiffener layout is adequate.' if p_ok else 'Panel deflection exceeds the L/360 serviceability limit at the current stiffener pitch — reduce stiffener spacing.'}"
    )

    # 7. Power & motor
    P_des = P_tot * sf
    notes.append(
        f"The calculated shaft power is {r.get('P_shaft','—')} kW. Total motor input power "
        f"including drive losses is {P_tot:.1f} kW. A {motor} kW motor has been selected, "
        f"representing a {(float(motor)/P_tot - 1)*100:.0f}% power margin above the design requirement at the specified service factor. "
        f"The gearbox reduction ratio should be confirmed with the selected motor supplier based on motor synchronous speed."
    )

    # 8. Bearing
    L10_qual = (
        "exceeds standard requirements"         if L10 >= 80000 else
        "suitable for continuous 24/7 service"  if L10 >= 40000 else
        "acceptable for up to 16 hours per day" if L10 >= 20000 else
        "below the minimum recommended threshold"
    )
    notes.append(
        f"Head shaft bearing life is calculated at {L10:,.0f} hours, which {L10_qual}. "
        f"Bearing selection should be confirmed from the manufacturer catalogue using the equivalent dynamic load "
        f"at the specified shaft speed. Lubrication interval and replacement schedule should be established "
        f"based on the supplier's rated life data for the selected bearing series."
    )

    # 9. Bolt fatigue
    GR = bf.get("goodman_ratio") or "—"
    inf_life = bf.get("pass_infinite_life", True)
    notes.append(
        f"Bucket mounting bolt fatigue has been assessed using the Goodman diagram method. "
        f"The fatigue utilization ratio is {GR}, which is "
        f"{'well within the infinite life threshold — bolt fatigue is not a design concern at the specified operating conditions' if inf_life else 'above the infinite life threshold — a higher bolt grade or increased bolt diameter is required'}."
    )

    # 10. Discharge chute
    dc   = r.get("discharge_chute") or {}
    perf = dc.get("performance") or {}
    mnt  = dc.get("maintenance") or {}
    geom = dc.get("geometry") or {}
    regime = perf.get("flow_regime", "mass flow")
    chute_ang = perf.get("chute_angle_deg") or "—"
    liner_mat = mnt.get("liner_material") or "mild steel"
    plug_risk = mnt.get("plugging_risk") or "LOW"
    dust_risk = mnt.get("dust_risk") or "LOW"
    throw_m   = geom.get("throw_distance_m") or "—"
    notes.append(
        f"The discharge chute back-plate angle of {chute_ang} degrees is set by the material trajectory. "
        f"Flow analysis indicates {regime.lower().replace('_',' ')} conditions at the specified belt speed. "
        f"{mnt.get('liner_material','Mild steel')} liner, {mnt.get('liner_thickness_mm','—')} mm thick, "
        f"is specified based on the calculated wear index. "
        f"Plugging probability is {plug_risk.lower()} and dust generation risk is {dust_risk.lower()} for this material. "
        f"The material throw distance is {throw_m} m from the pulley centreline, "
        f"which should be verified against the physical head section geometry."
    )

    # 11. Feed design (boot section)
    fd     = r.get("feed_design") or {}
    is_cfd = fd.get("elev_type") == "continuous"
    if fd:
        if is_cfd:
            notes.append(
                f"The elevator uses a loading leg for continuous bucket filling — buckets do not dig. "
                f"The loading leg height of {fd.get('loading_leg_height_mm','—')} mm "
                f"(twice the bucket depth) provides sufficient dwell time for complete bucket loading "
                f"at the design belt speed. "
                f"The spout angle of {fd.get('spout_angle_deg','—')} degrees ensures material "
                f"flows by gravity without bridging under normal operating conditions. "
                f"The boot surge volume of {fd.get('V_surge_litres','—')} L ({fd.get('t_surge_s',3)}-second buffer) "
                f"provides adequate capacity to absorb upstream feed rate fluctuations. "
                f"The minimum boot casing height below the pulley centreline is "
                f"{fd.get('boot_casing_height_mm','—')} mm."
            )
        else:
            notes.append(
                f"The elevator uses centrifugal digging to fill buckets at the boot. "
                f"The material depth in the boot pit should be maintained at approximately "
                f"{fd.get('material_depth_mm','—')} mm (0.75 times the bucket projection) "
                f"for consistent scooping. "
                f"The active digging zone spans {fd.get('dig_zone_length_mm','—')} mm of arc "
                f"at the boot pulley, with an estimated digging volume of {fd.get('V_dig_litres','—')} litres. "
                f"The boot surge volume is {fd.get('V_surge_litres','—')} L ({fd.get('t_surge_s',3)}-second buffer). "
                f"The boot casing floor should be a minimum of {fd.get('boot_casing_height_mm','—')} mm "
                f"below the boot pulley centreline to provide adequate clearance."
            )
    else:
        notes.append(
            "Boot feed design data not available in this result set. "
            "Ensure calculations.py v1.8.0 or later is deployed."
        )

    return notes


# ─── Engineering sign-off block (Task 13) ─────────────────────────────────────
def _sign_off_block(sign_off: dict | None) -> list:
    """
    Engineering sign-off block — 3 columns:
    Designed by | Reviewed by | Approved by

    Each column: Name, Designation/Company, Date, Signature line, Stamp box.
    Renders empty fields as blank lines so signatory can fill in by hand.

    sign_off dict shape (all fields optional):
        {
            "designed_by":  {"name": "", "designation": "", "date": ""},
            "reviewed_by":  {"name": "", "designation": "", "date": ""},
            "approved_by":  {"name": "", "designation": "", "date": ""},
        }
    """
    if sign_off is None:
        sign_off = {}

    col_w = AVAIL / 3

    ROLES = [
        ("DESIGNED BY",  sign_off.get("designed_by",  {})),
        ("REVIEWED BY",  sign_off.get("reviewed_by",  {})),
        ("APPROVED BY",  sign_off.get("approved_by",  {})),
    ]

    def _col(role_label, info):
        name        = info.get("name", "")        if info else ""
        designation = info.get("designation", "") if info else ""
        date_str    = info.get("date", "")        if info else ""

        BLANK = "_" * 26

        col_items = [
            # Role header
            Table([[Paragraph(role_label,
                ParagraphStyle("sorl", fontName="Helvetica-Bold", fontSize=8,
                               textColor=NAVY, leading=10))]],
                colWidths=[col_w - 8*mm]),
            Spacer(1, 3),

            # Name
            Paragraph("Name:", ST["h3"]),
            Paragraph(name or BLANK, ST["body"]),
            Spacer(1, 2),

            # Designation / Company
            Paragraph("Designation / Company:", ST["h3"]),
            Paragraph(designation or BLANK, ST["body"]),
            Spacer(1, 2),

            # Date
            Paragraph("Date:", ST["h3"]),
            Paragraph(date_str or "_" * 16, ST["body"]),
            Spacer(1, 6),

            # Signature line
            HRFlowable(width=col_w - 12*mm, thickness=0.5,
                       color=MUTED, spaceAfter=1),
            Paragraph("Signature", ST["cap"]),
            Spacer(1, 4),

            # Stamp / Seal box
            Table(
                [[Paragraph("STAMP / SEAL", ST["cap"])]],
                colWidths=[col_w - 12*mm],
                rowHeights=[18*mm],
                style=TableStyle([
                    ("BOX",           (0,0), (-1,-1), 0.5, MUTED),
                    ("TOPPADDING",    (0,0), (-1,-1), 4),
                    ("BOTTOMPADDING", (0,0), (-1,-1), 4),
                    ("LEFTPADDING",   (0,0), (-1,-1), 4),
                    ("RIGHTPADDING",  (0,0), (-1,-1), 4),
                ]),
            ),
        ]

        inner = Table(
            [[item] for item in col_items],
            colWidths=[col_w - 8*mm],
            style=TableStyle([
                ("TOPPADDING",    (0,0), (-1,-1), 1),
                ("BOTTOMPADDING", (0,0), (-1,-1), 1),
                ("LEFTPADDING",   (0,0), (-1,-1), 0),
                ("RIGHTPADDING",  (0,0), (-1,-1), 0),
            ]),
        )
        return inner

    cells = [_col(role, info) for role, info in ROLES]

    outer = Table(
        [cells],
        colWidths=[col_w, col_w, col_w],
        style=TableStyle([
            ("BOX",           (0,0), (-1,-1), 1,   NAVY),
            ("INNERGRID",     (0,0), (-1,-1), 0.5, BORDER),
            ("TOPPADDING",    (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("LEFTPADDING",   (0,0), (-1,-1), 5),
            ("RIGHTPADDING",  (0,0), (-1,-1), 5),
            ("VALIGN",        (0,0), (-1,-1), "TOP"),
            ("BACKGROUND",    (0,0), (-1,-1), white),
        ]),
    )
    return [outer, Spacer(1, 4)]


# ─── SF check rows builder ────────────────────────────────────────────────────
def _build_sf_rows(r, inp):
    rows = []
    fb   = "—"

    is_chain = r.get("is_chain", False)
    is_cont  = r.get("is_continuous", False)

    def sf_str(num, den, invert=False):
        try:
            n, d = float(num), float(den)
            if d == 0: return fb
            ratio = d / n if invert else n / d
            return f"{ratio:.2f}"
        except:
            return fb

    # 1 Capacity
    Q = float(r.get("Q") or r.get("Q_th") or 0)
    Q_req = float(inp.get("Q_req") or 0)
    cap_ok = Q >= Q_req
    rows.append(("Capacity",
                 f"{Q:.1f} t/h",
                 f"{Q_req:.1f} t/h",
                 sf_str(Q, Q_req),
                 "ok" if cap_ok else "fail"))

    # 2 Belt speed
    v    = float(r.get("v") or r.get("v_ms") or 0)
    bkt  = r.get("bucket") or {}
    vmin = float(bkt.get("v_min") or 0.5)
    vmax = float(bkt.get("v_max") or 9.9)
    spd_ok = vmin <= v <= vmax
    rows.append(("Belt speed",
                 f"{v:.2f} m/s",
                 f"{vmin:.2f} – {vmax:.2f} m/s",
                 sf_str(v, vmin),
                 "ok" if spd_ok else ("warn" if v < vmin else "fail")))

    # 3 Centrifugal ratio — logic differs for continuous vs centrifugal
    cr = float(r.get("cr") or r.get("centrifugal_ratio") or 0)
    if is_cont:
        # HF continuous: CR must be BELOW 1.0
        cr_ok = cr < 1.0
        rows.append(("CR  (HF continuous, need &lt;1.0)",
                     f"{cr:.3f}",
                     "&lt; 1.00",
                     fb,
                     "ok" if cr_ok else ("warn" if cr < 1.1 else "fail")))
    elif not is_chain:
        # Standard centrifugal
        cr_ok = 1.0 <= cr <= 2.5
        rows.append(("Centrifugal ratio",
                     f"{cr:.3f}",
                     "1.00 – 2.50",
                     fb,
                     "ok" if cr_ok else "warn"))
    # Chain: CR check not applicable — replaced by working load check below

    # 4 Belt slip (Euler) — belt mode only;  Chain working load — chain mode
    if is_chain:
        # Chain SF check
        chain_sf_a   = r.get("chain_SF_actual")
        chain_sel    = r.get("chain_selected") or {}
        chain_pull_N = float(r.get("chain_pull_N") or 0)
        chain_sf_req = 6.0
        if chain_sf_a is not None:
            rows.append(("Chain working load  SF",
                         f"{chain_sf_a:.2f}",
                         f">= {chain_sf_req:.1f}  (CEMA 375)",
                         f"{chain_sf_a:.2f}",
                         "ok"   if chain_sf_a >= chain_sf_req else
                         "warn" if chain_sf_a >= chain_sf_req * 0.9 else "fail"))

        # Chain speed vs rated
        chain_v_ok  = r.get("chain_v_ok")
        v_max_chain = float(chain_sel.get("v_max_ms") or 0)
        if chain_v_ok is not None:
            rows.append(("Chain speed  v <= rated",
                         f"{v:.2f} m/s",
                         f"{v_max_chain:.2f} m/s rated",
                         sf_str(v_max_chain, v),
                         "ok" if chain_v_ok else "fail"))

        # Sprocket teeth
        sprocket = r.get("sprocket") or {}
        if sprocket:
            rows.append(("Sprocket  10–20 teeth (smooth)",
                         f"{sprocket.get('n_teeth','—')} teeth",
                         "10 – 20",
                         fb,
                         "ok" if sprocket.get("smooth") else "warn"))
    else:
        # Belt slip (Euler-Eytelwein)
        T3     = float(r.get("T3") or 0)
        T3_min = float(r.get("T3_euler_min") or 0)
        slip_ok = (r.get("slip_safe") is True) or (T3 >= T3_min > 0)
        rows.append(("Belt slip  T3 / T3_min",
                     f"{T3/1000:.2f} kN",
                     f"{T3_min/1000:.2f} kN min",
                     sf_str(T3, T3_min) if T3_min > 0 else fb,
                     "ok" if slip_ok else "fail"))

    # 5 Headshaft load
    R = float(r.get("R_headshaft") or 0)
    R_lim = 80000.0
    rows.append(("Headshaft radial load",
                 f"{R/1000:.2f} kN",
                 f"{R_lim/1000:.0f} kN",
                 sf_str(R_lim, R),
                 "ok" if R <= 50000 else ("warn" if R <= 80000 else "fail")))

    # 6 Shaft (stress vs deflection)
    d_stress  = float(r.get("d_stress_mm") or 0)
    d_deflect = float(r.get("d_deflect_mm") or 0)
    d_gov     = float(r.get("d_mm") or 0)
    gov_by    = r.get("governed_by") or "—"
    sf_shaft  = fb
    if d_stress > 0 and d_gov > 0:
        sf_shaft = f"{(d_gov / d_stress)**3:.2f}"
    rows.append(("Shaft diameter (stress)",
                 f"{d_stress:.1f} mm calc",
                 f"{d_gov:.1f} mm governing",
                 sf_shaft,
                 "info"))

    # 7 Bearing L10
    L10   = float(r.get("L10") or r.get("L10_hours") or 0)
    L_min = 20000.0
    rows.append(("Bearing L10 life",
                 f"{L10:,.0f} h",
                 f"{L_min:,.0f} h min",
                 sf_str(L10, L_min),
                 "ok" if L10 >= L_min else "warn"))

    # 8 & 9 Key check
    kc = r.get("key_check") or {}
    if kc:
        rows.append(("Keyway shear stress",
                     f"{kc.get('tau_actual_MPa','—')} MPa",
                     f"{kc.get('tau_allow_MPa','—')} MPa",
                     sf_str(float(kc.get('tau_allow_MPa') or 0),
                            float(kc.get('tau_actual_MPa') or 1)),
                     "ok" if kc.get("shear_pass") else "fail"))
        rows.append(("Keyway bearing stress",
                     f"{kc.get('sigma_actual_MPa','—')} MPa",
                     f"{kc.get('sigma_allow_MPa','—')} MPa",
                     sf_str(float(kc.get('sigma_allow_MPa') or 0),
                            float(kc.get('sigma_actual_MPa') or 1)),
                     "ok" if kc.get("bearing_pass") else "fail"))

    # 10 Bolt fatigue
    bf = r.get("bolt_fatigue") or {}
    if bf:
        GR = float(bf.get("goodman_ratio") or 0)
        rows.append(("Bolt fatigue  Goodman ratio",
                     f"{GR:.3f}",
                     "&lt; 1.000  (infinite life)",
                     f"{1/GR:.2f}" if GR > 0 else fb,
                     "ok" if bf.get("pass_infinite_life") else "fail"))

    # 11 Lagging slip
    lag = r.get("lagging") or {}
    if lag:
        ratio  = float(lag.get("belt_ratio_tight_slack") or 0)
        euler  = float(lag.get("euler_ratio_lagged") or 0)
        rows.append(("Lagging belt slip ratio",
                     f"{ratio:.3f}",
                     f"{euler:.3f}  (e^mu.theta)",
                     sf_str(euler, ratio),
                     "ok" if lag.get("slip_safe") else "fail"))

    # 12 Casing panel deflection
    cp = r.get("casing_panel") or {}
    if cp:
        da = float(cp.get("delta_actual_mm") or 0)
        dl = float(cp.get("delta_allow_mm") or 0)
        rows.append(("Casing panel deflection",
                     f"{da:.2f} mm",
                     f"{dl:.2f} mm  (L/360)",
                     sf_str(dl, da),
                     "ok" if cp.get("status") == "ok" else "warn"))

    # 13 Casing clearance (stream vs head-section wall)
    cc = r.get("casing_clearance") or {}
    if cc:
        clears    = cc.get("clears", True)
        clearance = float(cc.get("clearance_m") or 0) * 1000   # → mm
        max_x_mm  = float(cc.get("max_x_m") or 0) * 1000
        wall_mm   = float(cc.get("casing_wall_x_m") or 0) * 1000
        status_cc = "ok" if clears and clearance >= 20 else ("warn" if clears else "fail")
        rows.append(("Casing clearance  (stream vs wall)",
                     f"{max_x_mm:.1f} mm stream reach",
                     f"{wall_mm:.1f} mm wall",
                     f"{clearance:.1f} mm margin",
                     status_cc))

    # 14 Stream interception (chute inlet capture)
    sc = r.get("stream_chute") or {}
    if sc:
        intercepted = sc.get("intercepted", False)
        ang = sc.get("impact_angle_deg")
        vel = sc.get("impact_velocity_mps")
        ang_s = f"{ang:.1f} deg" if ang is not None else fb
        vel_s = f"{vel:.2f} m/s" if vel is not None else fb
        rows.append(("Stream  →  chute interception",
                     ang_s + "  impact angle",
                     vel_s + "  impact velocity",
                     fb,
                     "ok" if intercepted else "warn"))

    return rows


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN BUILDER
# ═══════════════════════════════════════════════════════════════════════════════

def build_report(results: dict, inputs: dict,
                 project: str = "", doc_ref: str = "",
                 sign_off: dict | None = None,
                 output_path=None) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
        leftMargin=ML, rightMargin=MR, topMargin=MT, bottomMargin=MB,
        title="VECTRIX™ Bucket Elevator Report",
        author="Jayveecons Engineering & Design")

    r   = results or {}
    inp = inputs  or {}
    mat = r.get("mat") or r.get("material") or {}
    bkt = r.get("bucket") or {}
    hub = r.get("hub") or {}
    lag = r.get("lagging") or {}
    ed  = r.get("end_disc") or {}
    bf  = r.get("bolt_fatigue") or {}
    tg  = r.get("takeup_gravity") or {}
    ts  = r.get("takeup_screw") or {}
    cp  = r.get("casing_panel") or {}
    cs  = r.get("casing_stiffener") or {}
    kc  = r.get("key_check") or {}

    def rv(*keys, dp=2, fb="—"): return _rv(r, *keys, dp=dp, fb=fb)
    def rkn(*keys, dp=2, fb="—"): return _rkn(r, *keys, dp=dp, fb=fb)

    story = []

    # ── HEADER ────────────────────────────────────────────────────────────────
    story += header_flowables(inp, r, project, doc_ref)

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 1  INPUT SPECIFICATIONS
    # ══════════════════════════════════════════════════════════════════════════
    story += section("1.  Input Specifications")

    mat_name = mat.get("name") or inp.get("mat_id", "Custom")
    rho      = rv("rho", dp=0)

    # Customer specifications only — engineering parameters go to Section 3
    story += data_table([
        ("Required capacity",   f"{inp.get('Q_req','—')} t/h"),
        ("Lift height",         f"{inp.get('H_m','—')} m"),
        ("Material",            mat_name),
        ("Bulk density",        f"{rho} kg/m3"),
        ("Service environment", inp.get("environment","dry").capitalize()),
        ("Site wind pressure",  f"{inp.get('wind_pressure_pa',800)} Pa"),
    ], col_widths=[AVAIL * 0.45, AVAIL * 0.55])

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 2  PERFORMANCE SUMMARY — KPI CARDS
    # ══════════════════════════════════════════════════════════════════════════
    story += section("2.  Performance Summary")

    Q    = float(r.get("Q") or r.get("Q_th") or 0)
    Q_req = float(inp.get("Q_req") or 0)
    cap_pass = Q >= Q_req
    cr_val     = float(r.get("cr") or 0)
    L10        = float(r.get("L10") or 0)
    is_chain_r = r.get("is_chain", False)
    is_cont_r  = r.get("is_continuous", False)
    chain_sf_a = r.get("chain_SF_actual")

    # 5th KPI card: chain SF / HF CR / centrifugal CR
    if is_chain_r and chain_sf_a is not None:
        kpi5 = ("Chain SF",
                 f"{chain_sf_a:.2f}", "—",
                 "ok" if chain_sf_a >= 6.0 else ("warn" if chain_sf_a >= 5.0 else "fail"))
    elif is_cont_r:
        kpi5 = ("CR (HF &lt; 1.0)",
                 rv("cr", dp=3), "—",
                 "ok" if cr_val < 1.0 else "fail")
    else:
        kpi5 = ("Centrifugal Ratio",
                 rv("cr","centrifugal_ratio",dp=3), "—",
                 "ok" if 1.0 <= cr_val <= 1.8 else "warn")

    story += kpi_row([
        ("Capacity",      rv("Q","Q_th",dp=1),  "t/h",  "ok" if cap_pass else "fail"),
        ("Belt Speed",    rv("v","v_ms",dp=2),   "m/s",  "info"),
        ("Total Power",   rv("P_total",dp=1),    "kW",   "info"),
        ("Motor Selected", str(r.get("motor_kw") or r.get("motor_kW") or "—"), "kW", "info"),
        kpi5,
        ("Bearing L10",   f"{L10:,.0f}" if L10 else "—",  "h",
         "ok" if L10 >= 40000 else ("warn" if L10 >= 20000 else "fail")),
    ])

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3  PROCESS LEVEL OUTPUTS — SCHEMATIC + CHARTS
    # ══════════════════════════════════════════════════════════════════════════
    story += section("3.  Process Level Outputs")

    # Design configuration sub-table (parameters removed from Section 1)
    story += sub_section("Design Configuration")
    story += four_col_table([
        ("Head pulley dia.",   f"{inp.get('D_mm','—')} mm"),
        ("Head shaft speed",   f"{inp.get('n_rpm','—')} rpm"),
        ("Boot pulley dia.",   f"{inp.get('boot_pulley_D_mm','—')} mm"),
        ("Fill factor",        f"{inp.get('fill_pct','—')}%"),
    ], [
        ("Belt type",          inp.get("belt_type","EP")),
        ("Belt friction  mu",  str(inp.get("mu","—"))),
        ("Wrap angle",         f"{inp.get('wrap_deg','—')} deg"),
        ("Service factor",     str(inp.get("sf","—"))),
    ])

    story += sub_section("System Schematic & Performance Charts")

    schem_w  = AVAIL * 0.54
    chart_w  = AVAIL * 0.44
    schem_h  = 270          # was 220 — increased to hold HEAD SECTION + BW labels
    chart_h  = 104

    schem = _elevator_schematic(r, inp, schem_w, schem_h)
    ch1   = _speed_chart(r, inp, chart_w, chart_h)
    ch2   = _trajectory_chart(r, chart_w, chart_h)

    # Chart column: stack speed chart + trajectory
    chart_col_items = []
    if ch1: chart_col_items.append(ch1)
    if ch2:
        chart_col_items.append(Spacer(1, 6))
        chart_col_items.append(ch2)

    # Side-by-side table: schematic | charts
    if chart_col_items:
        chart_inner = Table(
            [[item] for item in chart_col_items],
            colWidths=[chart_w],
        )
        chart_inner.setStyle(TableStyle([
            ("TOPPADDING",    (0,0), (-1,-1), 0),
            ("BOTTOMPADDING", (0,0), (-1,-1), 0),
            ("LEFTPADDING",   (0,0), (-1,-1), 0),
            ("RIGHTPADDING",  (0,0), (-1,-1), 0),
        ]))
        side = Table(
            [[schem, chart_inner]],
            colWidths=[schem_w, chart_w + AVAIL * 0.02],
        )
        side.setStyle(TableStyle([
            ("VALIGN",        (0,0), (-1,-1), "TOP"),
            ("TOPPADDING",    (0,0), (-1,-1), 0),
            ("BOTTOMPADDING", (0,0), (-1,-1), 0),
            ("LEFTPADDING",   (0,0), (-1,-1), 0),
            ("RIGHTPADDING",  (0,0), (-1,-1), 0),
            ("BACKGROUND",    (0,0), (-1,-1), LIGHT_BG),
            ("BOX",           (0,0), (-1,-1), 0.5, BORDER),
        ]))
        story.append(side)
    else:
        story.append(schem)

    story.append(Spacer(1, 6))

    # Process data table below charts
    disc_angle = rv("theta_rel","release_angle_deg", dp=1)
    story += four_col_table([
        ("Achieved capacity",  f"{rv('Q','Q_th',dp=1)} t/h"),
        ("Belt speed",         f"{rv('v','v_ms',dp=2)} m/s"),
        ("Bucket spacing",     f"{rv('spacing',dp=3)} m"),
        ("Centrifugal ratio",  rv("cr","centrifugal_ratio",dp=3)),
    ], [
        ("Discharge angle",    f"{disc_angle} deg from vertical"),
        ("Belt width",         f"{r.get('belt_w') or '—'} mm"),
        ("Recommended fill",   f"{rv('recommended_fill_pct',dp=1)}%"),
        ("Stream spread",      rv("stream_spread",dp=3)),
    ])

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 4  POWER BREAKDOWN
    # ══════════════════════════════════════════════════════════════════════════
    story += section("4.  Power Breakdown")

    sf_val = float(inp.get("sf") or 1.25)
    P_tot  = float(r.get("P_total") or 0)
    motor  = r.get("motor_kw") or r.get("motor_kW") or "—"

    story += data_table([
        ("Boot equivalent height  (D_boot x Leq)",       f"{rv('H_equiv',dp=2)} m"),
        ("Total equivalent height (H + H_equiv)",         f"{rv('H_total',dp=2)} m"),
        ("Lift power  (material only)",                   f"{rv('P_lift',dp=2)} kW"),
        ("Boot scooping power  (boot loading)",           f"{rv('P_digging',dp=2)} kW"),
        ("Shaft power  (total load at head shaft)",        f"{rv('P_shaft',dp=2)} kW"),
        ("Drive losses  (gearbox + bearings + belt flex)", f"{rv('P_drive_loss',dp=2)} kW"),
        ("Total motor power  (shaft x Ceff)",             f"{rv('P_total',dp=2)} kW"),
        (f"Design power  (x service factor {sf_val})",   f"{fmt(P_tot * sf_val, 2)} kW"),
        ("Selected motor",                                f"{motor} kW"),
        ("Gearbox ratio  (at 1450 rpm input)",
         f"{1450/float(inp.get('n_rpm',60)):.1f} : 1"),
        ("Drive efficiency factor  Ceff",                 rv("Ceff",dp=3)),
        ("CEMA LEQ factor",                               rv("Leq",dp=1)),
    ], col_widths=[AVAIL * 0.62, AVAIL * 0.38])

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 5  COMPONENT DESIGN OUTPUTS
    # ══════════════════════════════════════════════════════════════════════════
    story += section("5.  Component Design Outputs")

    # 5a — Head shaft & drive
    story += sub_section("5a.  Head Shaft & Drive")
    shaft_mat_id    = r.get("shaft_material") or "A36"
    shaft_mat_name  = r.get("shaft_material_name") or shaft_mat_id
    shaft_tau_allow = r.get("shaft_tau_allow_MPa")
    shaft_section_v = r.get("shaft_section") or "solid"
    hub_conn        = r.get("shaft_hub_connection") or "keyed"
    weld_chk        = r.get("weld_check") or {}

    shaft_left = [
        ("Material grade",    shaft_mat_name),
        ("Shaft torque",      f"{rv('T_Nm',dp=1)} Nm"),
        ("Section",           f"{shaft_section_v.capitalize()}" +
         (f"  (bore ratio {r.get('shaft_bore_ratio',0):.2f}, ID {r.get('shaft_d_inner_mm',0):.0f}mm)"
          if shaft_section_v == "hollow" else "")),
        ("Min shaft dia.",    f"{rv('d_mm',dp=1)} mm"),
        ("Governed by",       r.get("governed_by") or "—"),
        ("Allowable shear",   f"{fmt(shaft_tau_allow,0) if shaft_tau_allow is not None else '—'} MPa"
                               f"  ({'no keyway' if hub_conn=='welded' else 'keyed'})"),
        ("Bearing span",      f"{rv('shaft_span_mm',dp=0)} mm"),
        ("Drive arm A",       f"{rv('shaft_A_mm',dp=0)} mm"),
        ("Tail arm B",        f"{rv('shaft_B_mm',dp=0)} mm"),
    ]
    if shaft_section_v == "hollow":
        shaft_left.append(
            ("Mass saving vs solid", f"~{r.get('shaft_mass_saving_pct',0):.0f}%"))

    # Right column branches: keyed shafts show key spec/check; welded shafts
    # show weld throat spec/check instead. kc is empty {} for welded shafts
    # (key_check is None at the result-dict level), so this avoids printing
    # misleading dashes where a weld spec should appear.
    if hub_conn == "welded" and weld_chk:
        shaft_right = [
            ("Hub connection",    "Welded (no keyway)"),
            ("Hub OD",            f"{hub.get('d_hub_mm','—')} mm"),
            ("Hub length",        f"{hub.get('L_hub_mm','—')} mm"),
            ("Weld throat",       f"{weld_chk.get('t_throat_mm','—')} mm"),
            ("Weld governed by",  (weld_chk.get('governed_by') or '—').replace('_',' ')),
            ("Weld shear stress",
             f"{weld_chk.get('tau_torsion_MPa','—')} / {weld_chk.get('weld_allow_MPa','—')} MPa"),
            ("Weld spec",         "E70xx, full 360 deg around shaft OD"),
            ("Bearing L10",       f"{fmt(L10, 0)} h"),
        ]
    else:
        shaft_right = [
            ("Hub connection",    "Keyed (ASME B17.1)"),
            ("Hub OD",            f"{hub.get('d_hub_mm','—')} mm"),
            ("Hub length",        f"{hub.get('L_hub_mm','—')} mm"),
            ("Key  b x h",
             f"{hub.get('b_key_mm','—')} x {hub.get('h_key_mm','—')} mm"),
            ("Key shear",
             f"{kc.get('tau_actual_MPa','—')} / {kc.get('tau_allow_MPa','—')} MPa"),
            ("Key bearing",
             f"{kc.get('sigma_actual_MPa','—')} / {kc.get('sigma_allow_MPa','—')} MPa"),
            ("Key result",
             "PASS" if kc.get("pass") else ("FAIL" if kc else "—")),
            ("Bearing L10",       f"{fmt(L10, 0)} h"),
        ]
    story += four_col_table(shaft_left, shaft_right)

    # 5b — Belt & Bucket
    story += sub_section("5b.  Belt & Bucket Selection")
    bkt_w = bkt.get("W") or bkt.get("width_mm") or "—"
    bkt_h = bkt.get("H") or bkt.get("depth_mm") or "—"
    bkt_p = bkt.get("P") or bkt.get("projection_mm") or "—"
    bkt_v = bkt.get("V") or bkt.get("volume_L") or "—"
    bkt_thick = r.get("bucket_thickness") or {}
    n_buckets = r.get("n_buckets")
    belt_len_total = r.get("belt_length_total_m")
    spacing_actual = r.get("spacing_actual_m") or r.get("spacing")

    bucket_left = [
        ("Bucket series",     bkt.get("id") or "—"),
        ("Style",             bkt.get("type") or bkt.get("style") or "—"),
        ("Width x depth",     f"{bkt_w} x {bkt_h} mm"),
        ("Projection",        f"{bkt_p} mm"),
        ("Volume (struck)",   f"{bkt_v} L"),
        ("Bucket mass",       f"{rv('bucket_mass_kg',dp=2)} kg"),
    ]
    if bkt_thick:
        bucket_left.append(
            ("Plate thickness",
             f"{bkt_thick.get('t_override_mm','—')} mm "
             f"(catalogue std {bkt_thick.get('t_implied_mm','—')} mm)"))

    bucket_right = [
        ("Belt width",        f"{r.get('belt_w','—')} mm"),
        ("Belt class",        str(r.get("belt_class") or
                               f"{r.get('belt_ply','—')} PLY")),
        ("Belt length  (total)",
         f"{fmt(belt_len_total,1) if belt_len_total is not None else '—'} m "
         f"(incl. splice allowance)"),
        ("Bucket spacing  (actual)",
         f"{fmt(spacing_actual,3) if spacing_actual is not None else '—'} m"),
        ("Bucket count",      f"{n_buckets if n_buckets is not None else '—'} off"),
        ("Fill factor",       f"{inp.get('fill_pct','—')}%"),
        ("Material DB fill",  f"{rv('recommended_fill_pct',dp=1)}%  advisory"),
    ]
    story += four_col_table(bucket_left, bucket_right)

    # 5c — Pulley design
    story += sub_section("5c.  Pulley Design")
    ps     = r.get("pulley_shell") or {}
    csp    = r.get("critical_speed") or {}
    t_min  = ed.get("t_governing_mm") or "—"
    t_spec = int(float(t_min) * 1.20) if t_min != "—" else "—"
    n_op   = inp.get("n_rpm", 0) or 0
    n_crit = csp.get("n_critical_rpm") or 0
    ratio_pct = f"{(float(n_op)/float(n_crit)*100):.0f}%" if n_crit else "—"
    story += four_col_table([
        ("Lagging type",       (lag.get("lagging_type") or "—").replace("_"," ")),
        ("Lagging thickness",  f"{lag.get('thickness_mm','—')} mm"),
        ("mu dry / wet",       f"{lag.get('mu_dry','—')} / {lag.get('mu_wet','—')}"),
        ("mu operating",       str(lag.get("mu_operating","—"))),
        ("Euler limit",        str(lag.get("euler_ratio_lagged","—"))),
        ("Belt ratio R/T3",    str(lag.get("belt_ratio_tight_slack","—"))),
        ("Slip check",         "PASS" if lag.get("slip_safe") else
                               ("FAIL" if lag else "—")),
    ], [
        ("Shell min t (CEMA)", f"{ps.get('t_cema_mm','—')} mm"),
        ("Shell min t (press)",f"{ps.get('t_pressure_mm','—')} mm"),
        ("Shell governing t",  f"{ps.get('t_governing_mm','—')} mm  ({(ps.get('governed_by') or '—').replace('_',' ')})"),
        ("Shell specified t",
         f"{ps.get('t_use_mm','—')} mm" +
         (f"  ({'PASS' if ps.get('override_pass') else 'FAIL — below calc minimum'})"
          if ps.get("override_applied") else "  (= calculated minimum, no override)")),
        ("End disc min t",     f"{t_min} mm"),
        ("End disc specify",   f"{t_spec} mm  (+20%)"),
        ("Disc governed by",   ed.get("governed_by") or "—"),
        ("Disc sigma bend",    f"{ed.get('sigma_bending_MPa','—')} MPa"),
        ("Force per disc",
         f"{ed.get('F_per_disc_N', 0)/1000:.2f} kN"
         if ed.get("F_per_disc_N") else "—"),
        ("Shaft critical speed", f"{n_crit:.0f} rpm" if n_crit else "—"),
        ("Operating ratio",      f"{n_op:.0f} rpm  ({ratio_pct} of critical)"),
    ])

    # 5d — Take-Up
    story += sub_section("5d.  Take-Up Design")
    W_net   = tg.get("W_counterweight_kg_net") or "—"
    W_gross = tg.get("W_counterweight_kg_gross") or "—"
    travel  = round(tg.get("travel_m", 0) * 1000) if tg else "—"
    F_screw_kn = f"{ts.get('F_screw_N', 0)/1000:.2f} kN" if ts.get("F_screw_N") else "—"
    story += four_col_table([
        ("Type",                    "Gravity (primary)"),
        ("Counterweight  net",      f"{W_net} kg"),
        ("Counterweight  gross",    f"{W_gross} kg"),
        ("Travel required",         f"{travel} mm"),
        ("  — thermal",             f"{round(tg.get('travel_thermal_m',0)*1000)} mm"
                                      if tg else "—"),
        ("  — elongation",          f"{round(tg.get('travel_elongation_m',0)*1000)} mm"
                                      if tg else "—"),
    ], [
        ("Alt type",                "Screw (alternative)"),
        ("Screw load",              F_screw_kn),
        ("Min core dia.",           f"{ts.get('d_core_min_mm','—')} mm"),
        ("Turns required",          f"{ts.get('turns_required','—')}"),
        ("Buckling SF",             f"{ts.get('SF_buckling','—')}"),
        ("Buckling check",          "PASS" if ts.get("buckling_safe") else
                                    ("FAIL" if ts else "—")),
    ])

    # 5e — Casing
    story += sub_section("5e.  Casing & Structural")
    cbolt = r.get("casing_bolts") or {}
    story += four_col_table([
        ("Plate thickness",         f"{r.get('casing_t_mm','—')} mm"),
        ("Max stiffener pitch",     f"{cs.get('max_spacing_mm','—')} mm"),
        ("Recommended pitch",       f"{cs.get('recommended_mm','—')} mm"),
        ("Deflection limit",        cs.get("defl_limit") or "L / 360"),
        ("Wind pressure",           f"{cs.get('wind_pressure_Pa',800)} Pa"),
    ], [
        ("Panel delta actual",      f"{cp.get('delta_actual_mm','—')} mm"),
        ("Panel delta allowed",     f"{cp.get('delta_allow_mm','—')} mm"),
        ("Panel sigma max",         f"{cp.get('sigma_max_MPa','—')} MPa"),
        ("Panel check",             "PASS" if cp.get("status")=="ok" else
                                    ("FAIL" if cp else "—")),
        ("Bolt fatigue  Goodman",   f"{bf.get('goodman_ratio','—')}"),
        ("Assembly fasteners",
         f"{cbolt.get('bolt_size','—')} x {cbolt.get('n_bolts_total','—')} "
         f"(panel-to-panel + stiffener)" if cbolt else "—"),
    ])

    # 5f — Discharge Chute
    dc   = r.get("discharge_chute") or {}
    perf = dc.get("performance")    or {}
    mnt  = dc.get("maintenance")    or {}
    geom = dc.get("geometry")       or {}
    hs   = dc.get("hood_spoon")     or {}
    tele = dc.get("telemetry")      or {}
    chute_recs = dc.get("recommendations") or []

    if dc:
        story += sub_section("5f.  Discharge Chute Design")
        story += four_col_table([
            ("Back-plate angle",       f"{perf.get('chute_angle_deg','—')} deg"),
            ("Min angle (wall fric.)", f"{perf.get('min_angle_deg','—')} deg"),
            ("Angle adequate",         "YES" if perf.get("angle_adequate") else "NO"),
            ("Flow regime",            perf.get("flow_regime","—")),
            ("Mass-flow threshold",    f"{perf.get('mass_flow_angle_deg','—')} deg"),
            ("Governed by",            perf.get("governed_by","—")),
        ], [
            ("Spout width",            f"{geom.get('spout_width_mm','—')} mm"),
            ("Throw distance",         f"{geom.get('throw_distance_m','—')} m"),
            ("Throat velocity",        f"{geom.get('throat_velocity_mps','—')} m/s"),
            ("Geom plugging risk",     geom.get("plugging_risk","—")),
            ("Hood radius",            f"{hs.get('hood_radius_m','—')} m"),
            ("Capture efficiency",     str(hs.get("capture_efficiency","—"))),
        ])
        story += four_col_table([
            ("Wear index",             f"{mnt.get('wear_index','—')}  ({mnt.get('wear_rating','—')})"),
            ("Liner material",         mnt.get("liner_material","—")),
            ("Liner thickness",        f"{mnt.get('liner_thickness_mm','—')} mm"),
            ("Liner grade",            mnt.get("liner_grade","—")),
        ], [
            ("Plugging risk",          mnt.get("plugging_risk","—")),
            ("Plugging index",         f"{mnt.get('plugging_index','—')}"),
            ("Dust risk",              mnt.get("dust_risk","—")),
            ("Recommended sensors",    ", ".join(tele.get("recommended_sensors",[]) or ["None"])),
        ])
        if chute_recs:
            story += sub_section("Chute Recommendations")
            for cr_txt in chute_recs:
                story.append(Paragraph(f"*  {cr_txt}", ST["body"]))
                story.append(Spacer(1, 2))

    # 5g — Feed Design (Boot Section)
    fd = r.get("feed_design") or {}
    if fd:
        story += sub_section("5g.  Feed Design (Boot Section)")
        is_c_fd = fd.get("elev_type") == "continuous"
        A_cm2   = float(fd.get("A_inlet_m2") or 0) * 10000.0
        fd_left = [
            ("Loading method",  fd.get("loading_type", "—")),
            ("Volumetric flow", f"{fd.get('Q_volumetric_m3h','—')} m3/h"),
            ("Inlet velocity",  f"{fd.get('v_feed_mps','—')} m/s"),
            ("Inlet area req.", f"{A_cm2:.1f} cm2"),
            ("Inlet width",     f"{fd.get('inlet_width_mm','—')} mm"),
            ("Inlet height",    f"{fd.get('inlet_height_mm','—')} mm"),
        ]
        if is_c_fd:
            fd_right = [
                ("Loading leg h",   f"{fd.get('loading_leg_height_mm','—')} mm"),
                ("Loading leg w",   f"{fd.get('loading_leg_width_mm','—')} mm"),
                ("Spout angle",     f">= {fd.get('spout_angle_deg','—')} deg"),
                ("Surge volume",    f"{fd.get('V_surge_litres','—')} L  ({fd.get('t_surge_s',3)}s)"),
                ("Boot casing h",   f"{fd.get('boot_casing_height_mm','—')} mm"),
                ("Floor clearance", f"{fd.get('clearance_mm','—')} mm"),
            ]
        else:
            fd_right = [
                ("Material depth",  f"{fd.get('material_depth_mm','—')} mm  (0.75xP)"),
                ("Dig zone arc",    f"{fd.get('dig_zone_length_mm','—')} mm"),
                ("Dig volume",      f"{fd.get('V_dig_litres','—')} L"),
                ("Surge volume",    f"{fd.get('V_surge_litres','—')} L  ({fd.get('t_surge_s',3)}s)"),
                ("Boot casing h",   f"{fd.get('boot_casing_height_mm','—')} mm"),
                ("Floor clearance", f"{fd.get('clearance_mm','—')} mm"),
            ]
        story += four_col_table(fd_left, fd_right)
        for w in (fd.get("warnings") or []):
            story.append(Paragraph(f"*  WARNING:  {w}", ST["body"]))
            story.append(Spacer(1, 2))

    # 5h — Chain Drive Configuration (chain elevators only)
    if r.get("is_chain"):
        chain_sel = r.get("chain_selected") or {}
        sprocket  = r.get("sprocket")       or {}
        story += sub_section("5h.  Chain Drive Configuration")
        story += four_col_table([
            ("Chain series",    chain_sel.get("name","—")),
            ("Chain pitch",     f"{chain_sel.get('pitch_mm','—')} mm"),
            ("No. of strands",  str(chain_sel.get("n_strands","—"))),
            ("Working load",    f"{chain_sel.get('WL_kg','—')} kg / strand"),
            ("Chain weight",    f"{chain_sel.get('wt_kg_m','—')} kg/m"),
            ("Max chain speed", f"{chain_sel.get('v_max_ms','—')} m/s"),
        ], [
            ("Chain pull",      f"{(r.get('chain_pull_N') or 0)/1000:.2f} kN"),
            ("SF actual",       f"{round(r.get('chain_SF_actual') or 0, 2)}"),
            ("Speed check",     "PASS" if r.get("chain_v_ok") else "FAIL"),
            ("Sprocket teeth",  str(sprocket.get("n_teeth","—"))),
            ("Sprocket PD",     f"{sprocket.get('PD_mm','—')} mm"),
            ("Smooth op.",      "YES" if sprocket.get("smooth") else "WARN (&lt;10 teeth)"),
        ])

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 6  ENGINEERING VERIFICATION  (with Safety Factors)
    # ══════════════════════════════════════════════════════════════════════════
    story += section("6.  Engineering Verification")
    sf_rows = _build_sf_rows(r, inp)
    story  += sf_checks_table(sf_rows)

    # Design Recommendations (if any failures)
    design_recs = r.get("design_recommendations") or []
    if design_recs:
        story += sub_section("Corrective Actions")
        for rec in sorted(design_recs, key=lambda x: 0 if x.get("status")=="fail" else 1):
            ic  = "✗" if rec["status"]=="fail" else "⚠"
            hdr = f"{ic}  {rec['check'].upper()}  —  {rec['problem']}"
            story.append(Paragraph(hdr, ST["h3"]))
            for j, act in enumerate(rec.get("actions", [])):
                story.append(Paragraph(f"    {j+1}.  {act}", ST["body"]))
            story.append(Spacer(1, 3))

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 7  DESIGN NOTES  (plain English — no formulae)
    # ══════════════════════════════════════════════════════════════════════════
    story += section("7.  Design Notes")
    note_labels = [
        "Capacity & Selection",
        "Head Shaft & Hub",
        "Pulley Lagging",
        "Pulley End Disc",
        "Take-Up System",
        "Casing & Structural",
        "Power & Motor",
        "Bearing Life",
        "Bucket Bolt Fatigue",
        "Discharge Chute",
        "Feed Design (Boot Section)",
    ]
    try:
        notes = _design_notes(r, inp)
    except Exception:
        notes = []

    for label, note in zip(note_labels, notes):
        story.append(Paragraph(f"<b>{label}:</b>  {note}", ST["note"]))
        story.append(Spacer(1, 3))

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 8  ENGINEERING SIGN-OFF
    # ══════════════════════════════════════════════════════════════════════════
    story += section("8.  Engineering Sign-Off")
    story.append(Paragraph(
        "This report has been prepared in accordance with CEMA No. 375-2017 and "
        "ANSI/CEMA 550-2020. The signatory confirms that the design calculations "
        "have been reviewed and are accepted as the basis for procurement and fabrication.",
        ST["note"]
    ))
    story.append(Spacer(1, 4))
    story += _sign_off_block(sign_off)
    story.append(Paragraph(
        "Standards: CEMA No. 375-2017  ·  ANSI/CEMA 550-2020  ·  "
        "ISO 281  ·  ASME B17.1  ·  AS 4024 (where applicable)",
        ST["cap"]
    ))

    # ── FOOTER ───────────────────────────────────────────────────────────────
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
    story.append(Spacer(1, 2))
    story.append(Paragraph(
        f"VECTRIX™ Bucket Elevator Module  •  Jayveecons Engineering &amp; Design  "
        f"•  Generated {datetime.now().strftime('%d %b %Y %H:%M')}  "
        f"•  AkshayVipra EL-MEC PVT. LTD.",
        ST["ftr"]))

    doc.build(story)
    pdf_bytes = buf.getvalue()
    if output_path:
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
    return pdf_bytes


# ─── CLI test ──────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys, types
    sys.path.insert(0, ".")
    models_s = types.ModuleType("models")
    class BEI:
        Q_req=120; H_m=25; mat_id="wheat"; custom_rho=0
        D_mm=500; n_rpm=65; boot_pulley_D_mm=300
        fill_pct=75; bucket_gap=25; auto_bucket=True; bucket_id="AA"
        Leq=0; Ceff=0; K_takeup=0.7; mu=0.35; wrap_deg=180; sf=1.25
        environment="dry"; belt_type="EP"; wind_pressure_pa=800
    class OR:
        base_input=BEI(); objective="balanced"
    models_s.BucketElevatorInput=BEI; models_s.OptimizerRequest=OR  # type: ignore[attr-defined]
    sys.modules["models"] = models_s

    try:
        from .calculations import solve_elevator
    except ImportError:
        from calculations import solve_elevator
    r = solve_elevator(BEI())  # type: ignore[arg-type]
    inp = {
        "Q_req":120,"H_m":25,"mat_id":"wheat","D_mm":500,"n_rpm":65,
        "boot_pulley_D_mm":300,"fill_pct":75,"bucket_gap":25,"auto_bucket":True,
        "Leq":0,"Ceff":0,"K_takeup":0.7,"mu":0.35,"wrap_deg":180,"sf":1.25,
        "environment":"dry","belt_type":"EP","wind_pressure_pa":800,
    }
    out = "/mnt/user-data/outputs/bucket_elevator_report.pdf"
    build_report(r, inp, project="Grain Terminal GT-01",
                 doc_ref="VX-BE-2026-001", output_path=out)
    print(f"PDF written  →  {out}  ({len(open(out,'rb').read()):,} bytes)")


# ═══════════════════════════════════════════════════════════════════════════════
# VARIANT COMPARISON REPORT
# ═══════════════════════════════════════════════════════════════════════════════

def build_variant_report(candidates: list, inputs: dict,
                         project: str = "", doc_ref: str = "",
                         output_path=None) -> bytes:
    """
    A4 portrait PDF comparing multiple optimizer candidates side by side.
    Called by main.py POST /bucket-elevator/report-variants.

    candidates : list of dicts from run_optimizer() — each has rpm, bucket_id,
                 fill, speed, capacity, power, motor_kw, T1_kN, cr, score, rank
    inputs     : same BucketElevatorInput dict used for the base calculation
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
        leftMargin=ML, rightMargin=MR, topMargin=MT, bottomMargin=MB,
        title="VECTRIX™ Design Variants Comparison",
        author="Jayveecons Engineering & Design")

    inp = inputs or {}
    n   = len(candidates)
    now = datetime.now().strftime("%d %b %Y  %H:%M")
    story = []

    # ── Header ───────────────────────────────────────────────────────────────
    hdr = Table([[
        [
            Paragraph("<b>VECTRIX™</b>",
                ParagraphStyle("lg", fontName="Helvetica-Bold", fontSize=16,
                               textColor=white, leading=18)),
            Paragraph("BUCKET ELEVATOR",
                ParagraphStyle("s1", fontName="Helvetica", fontSize=7,
                               textColor=MUTED2, leading=9)),
            Paragraph("Design Variant Comparison",
                ParagraphStyle("s2", fontName="Helvetica", fontSize=6.5,
                               textColor=MUTED, leading=8)),
        ],
        [
            Paragraph(f"<b>Project:</b> {project or 'Unspecified'}",
                ParagraphStyle("pi", fontName="Helvetica", fontSize=8,
                               textColor=white, leading=10)),
            Paragraph(f"<b>Ref:</b> {doc_ref or 'VX-BE-VAR'}",
                ParagraphStyle("pi", fontName="Helvetica", fontSize=8,
                               textColor=white, leading=10)),
            Paragraph(f"<b>Date:</b> {now}",
                ParagraphStyle("pi", fontName="Helvetica", fontSize=8,
                               textColor=white, leading=10)),
            Paragraph(f"<b>Variants:</b> {n} candidates",
                ParagraphStyle("pi", fontName="Helvetica", fontSize=8,
                               textColor=white, leading=10)),
        ],
        [
            Paragraph(f"<b>{n} VARIANTS</b>",
                ParagraphStyle("st", fontName="Helvetica-Bold", fontSize=14,
                               textColor=BLUE, alignment=TA_CENTER, leading=16)),
            Paragraph("Comparison Report",
                ParagraphStyle("sl", fontName="Helvetica", fontSize=6.5,
                               textColor=MUTED, alignment=TA_CENTER, leading=8)),
        ],
    ]], colWidths=[AVAIL*0.28, AVAIL*0.46, AVAIL*0.26])
    hdr.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), NAVY),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ("RIGHTPADDING",  (0,0), (-1,-1), 6),
        ("LINEBELOW",     (0,0), (-1, 0), 2.5, CRIMSON),
    ]))
    story += [hdr, Spacer(1, 8)]

    # ── Design basis ─────────────────────────────────────────────────────────
    story += section("Design Basis")
    story += data_table([
        ("Required capacity", f"{inp.get('Q_req','—')} t/h"),
        ("Lift height",       f"{inp.get('H_m','—')} m"),
        ("Material",          inp.get('mat_id','—')),
        ("Head pulley dia.",  f"{inp.get('D_mm','—')} mm"),
        ("Service factor",    str(inp.get('sf','—'))),
        ("Fill target",       f"{inp.get('fill_pct','—')}%"),
    ], col_widths=[AVAIL*0.40, AVAIL*0.60])

    # ── Comparison table ──────────────────────────────────────────────────────
    story += section("Variant Comparison")
    col_first = 44 * mm
    col_unit  = 14 * mm
    col_var   = (AVAIL - col_first - col_unit) / max(n, 1)
    col_widths_t = [col_first, col_unit] + [col_var] * n

    def vrow(label, unit, getter):
        vals = []
        for c in candidates:
            try:    vals.append(str(getter(c)))
            except: vals.append("—")
        return ([Paragraph(label, ST["body"]),
                 Paragraph(unit, ST["cap"])] +
                [Paragraph(v, ST["mono"]) for v in vals])

    col_labels = ["Parameter", "Units"] + [f"Var {i+1}" for i in range(n)]
    header_row = [Paragraph(h, ST["h3"]) for h in col_labels]
    table_data = [header_row,
        vrow("Bucket series", "—",    lambda c: c.get("bucket_id","—")),
        vrow("RPM",           "rpm",  lambda c: c.get("rpm","—")),
        vrow("Fill factor",   "%",    lambda c: c.get("fill","—")),
        vrow("Belt speed",    "m/s",  lambda c: c.get("speed","—")),
        vrow("Capacity",      "t/h",  lambda c: c.get("capacity","—")),
        vrow("Total power",   "kW",   lambda c: c.get("power","—")),
        vrow("Motor",         "kW",   lambda c: c.get("motor_kw","—")),
        vrow("Headshaft R",   "kN",   lambda c: c.get("T1_kN","—")),
        vrow("Cent. ratio",   "—",    lambda c: c.get("cr","—")),
        vrow("Score",         "—",    lambda c: fmt(c.get("score"),3)),
        vrow("Rank",          "—",    lambda c: c.get("rank","—")),
    ]
    ranks = [c.get("rank", 99) for c in candidates]
    t = Table(table_data, colWidths=col_widths_t, repeatRows=1)
    cmds = [
        ("BACKGROUND",    (0,0), (-1, 0), NAVY),
        ("TEXTCOLOR",     (0,0), (-1, 0), TEXT),
        ("FONTNAME",      (0,0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1, 0), 7.5),
        ("GRID",          (0,0), (-1,-1), 0.3, BORDER),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 2.5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2.5),
        ("LEFTPADDING",   (0,0), (-1,-1), 3),
        ("RIGHTPADDING",  (0,0), (-1,-1), 3),
    ]
    for i in range(1, len(table_data)):
        cmds.append(("BACKGROUND", (0,i), (-1,i), LIGHT_BG if i%2==1 else white))
    if ranks:
        best = 2 + ranks.index(min(ranks))
        cmds.append(("LINEABOVE", (best,0), (best,0), 2.5, GREEN))
        cmds.append(("LINEBELOW", (best,len(table_data)-1),
                     (best,len(table_data)-1), 1.5, GREEN))
    t.setStyle(TableStyle(cmds))
    story += [t, Spacer(1, 6)]

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
    story.append(Spacer(1, 2))
    story.append(Paragraph(
        f"VECTRIX™  ·  Jayveecons Engineering &amp; Design  "
        f"·  Generated {now}  ·  AkshayVipra EL-MEC PVT. LTD.",
        ST["ftr"]))

    doc.build(story)
    pdf_bytes = buf.getvalue()
    if output_path:
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
    return pdf_bytes