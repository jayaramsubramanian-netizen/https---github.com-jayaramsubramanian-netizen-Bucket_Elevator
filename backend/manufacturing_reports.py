"""
manufacturing_reports.py — VECTOMEC™ Manufacturing Transfer Reports
═══════════════════════════════════════════════════════════════════════════
Three distinct PDF reports, each targeting a different audience:

1. build_workshop_report(results, inputs)
   Internal — fabrication team.
   Schematics + Fabrication BOM with weights/specs + QC checkpoints +
   weld specs + material test requirements.

2. build_procurement_report(results, inputs)
   Procurement — purchasing team.
   Commercial BOM with quantities + specs for sourcing +
   long-lead item flags + delivery-critical items highlighted.

3. build_enduser_report(results, inputs)
   External — customer/end-user.
   Installation sequence + commissioning checklist +
   1-year spares list (from reliability.py) + maintenance schedule.

All three follow the same ReportLab pattern as generate_report.py.
Part description is the unique identifier throughout (part numbers
to be assigned later per Jay's instruction).

NOTE ON PYLANCE ERRORS: All reportArgumentType errors in this file
are false positives from ReportLab's incomplete ParagraphStyle stubs.
The stubs don't model that Color is a valid value for textColor, or
that ParagraphStyle's constructor is effectively **kwargs-based -- same
confirmed stub-gap as pyqtgraph in charts_panel.py. Every call here
produces valid PDFs at runtime (verified). Suppressed file-wide rather
than on every individual call site (~33 instances).
"""
# pyright: reportArgumentType=false
import io
from datetime import datetime

from reportlab.lib.pagesizes   import A4
from reportlab.lib.units       import mm
from reportlab.lib.colors      import HexColor, white, black
from reportlab.platypus        import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether,
)
from reportlab.lib.styles      import ParagraphStyle
from reportlab.lib.enums       import TA_LEFT, TA_CENTER, TA_RIGHT

# ── Layout constants (matches generate_report.py) ────────────────────────────
ML = MR = 18 * mm
MT      = 15 * mm
MB      = 18 * mm
PW      = A4[0] - ML - MR
PH      = A4[1] - MT - MB

# Colour palette
DARK    = HexColor("#0d1c2e")
MID     = HexColor("#1e3a5a")
ACCENT  = HexColor("#1a6fc4")
WARN_C  = HexColor("#c47a1a")
OK_C    = HexColor("#1a8c4e")
DANGER_C= HexColor("#c41a2a")
LIGHT   = HexColor("#f4f7fb")
BORDER_C= HexColor("#d0dae8")
TEXT_C  = HexColor("#1a2636")
MUTED_C = HexColor("#6b7c93")

NOW = datetime.now().strftime("%d %b %Y  %H:%M")


def _style(name, **kw):
    defaults = dict(fontName="Helvetica", fontSize=9, leading=12,
                    textColor=TEXT_C, spaceAfter=0)
    defaults.update(kw)
    return ParagraphStyle(name, **defaults)


H1  = _style("H1",  fontName="Helvetica-Bold", fontSize=14, textColor=DARK,  spaceAfter=4*mm)
H2  = _style("H2",  fontName="Helvetica-Bold", fontSize=11, textColor=ACCENT, spaceAfter=2*mm)
H3  = _style("H3",  fontName="Helvetica-Bold", fontSize=9.5, textColor=DARK)
BODY= _style("BODY",fontSize=9, leading=13, spaceAfter=2*mm)
TINY= _style("TINY",fontSize=7.5, textColor=MUTED_C, leading=10)
WARN_S = _style("WARN", fontName="Helvetica-Bold", fontSize=9, textColor=WARN_C)
OK_S   = _style("OK",   fontName="Helvetica-Bold", fontSize=9, textColor=OK_C)


def _p(text, style=BODY):
    return Paragraph(text, style)


CELL  = _style("CELL",  fontSize=8, leading=10, textColor=TEXT_C)
CELL_H= _style("CELLH", fontSize=8, leading=10, textColor=white,
                fontName="Helvetica-Bold")


def _pc(text, header=False):
    """Wrap a string in a Paragraph so ReportLab word-wraps it within the
    column width instead of letting it overflow the cell boundary.
    Passes non-string objects (e.g. existing Paragraphs) through unchanged."""
    if not isinstance(text, str):
        return text
    return Paragraph(str(text), CELL_H if header else CELL)


def _sp(h=3):
    return Spacer(1, h * mm)


def _hr():
    return HRFlowable(width="100%", thickness=0.5, color=BORDER_C, spaceAfter=3*mm)


def _table(rows, col_widths, header_bg=ACCENT, zebra=True):
    """Build a styled table. First row is always treated as a header.
    All string cells are automatically wrapped in Paragraph objects so
    text wraps within column boundaries instead of overflowing."""
    if not rows:
        return _p("— no data —", TINY)
    # Wrap all cells so text word-wraps within each column
    wrapped = []
    for i, row in enumerate(rows):
        wrapped.append([_pc(cell, header=(i == 0)) for cell in row])
    ts = [
        ("BACKGROUND", (0, 0), (-1, 0), header_bg),
        ("TEXTCOLOR",  (0, 0), (-1, 0), white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, 0), 8),
        ("FONTSIZE",   (0, 1), (-1, -1), 8),
        ("GRID",       (0, 0), (-1, -1), 0.4, BORDER_C),
        ("LEFTPADDING",(0, 0), (-1, -1), 4),
        ("RIGHTPADDING",(0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 3),
        ("VALIGN",     (0, 0), (-1, -1), "TOP"),
    ]
    if zebra:
        for i in range(1, len(wrapped), 2):
            ts.append(("BACKGROUND", (0, i), (-1, i), LIGHT))
    return Table(wrapped, colWidths=col_widths, style=TableStyle(ts),
                 repeatRows=1, hAlign="LEFT")


def _page_header(report_type: str, model_no: str, doc_ref: str) -> list:
    """Top banner common to all three reports."""
    banner_rows = [[
        Paragraph(f"<b>VECTOMEC™</b><br/><font size='7' color='#6b7c93'>"
                   f"Jayveecons Engineering &amp; Design</font>",
                   ParagraphStyle("BL", fontName="Helvetica-Bold", fontSize=11,
                                  textColor=white, leading=14)),
        Paragraph(f"<b>{report_type}</b><br/>"
                   f"<font size='7'>{model_no}</font>",
                   ParagraphStyle("BC", fontName="Helvetica-Bold", fontSize=10,
                                  textColor=white, leading=13, alignment=TA_CENTER)),
        Paragraph(f"Ref: {doc_ref or '—'}<br/>"
                   f"<font size='7'>{NOW}</font>",
                   ParagraphStyle("BR", fontSize=8, textColor=white,
                                  leading=11, alignment=TA_RIGHT)),
    ]]
    banner = Table(banner_rows, colWidths=[PW*0.35, PW*0.38, PW*0.27],
                   style=TableStyle([
                       ("BACKGROUND", (0, 0), (-1, -1), DARK),
                       ("LEFTPADDING", (0, 0), (-1, -1), 6),
                       ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                       ("TOPPADDING", (0, 0), (-1, -1), 6),
                       ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                   ]))
    return [banner, _sp(4)]


def _fmt(v, dp=2, fb="—"):
    if v is None:
        return fb
    try:
        return f"{float(v):.{dp}f}"
    except (TypeError, ValueError):
        return fb


def _model_number(inputs: dict, results: dict) -> str:
    try:
        from model_number import generate_model_number
        return generate_model_number(inputs, results)
    except Exception:
        return "VM-??-?-???/???"


# ══════════════════════════════════════════════════════════════════════════════
# REPORT 1 — WORKSHOP (Internal / Fabrication)
# ══════════════════════════════════════════════════════════════════════════════
def build_workshop_report(results: dict, inputs: dict,
                           project: str = "", doc_ref: str = "") -> bytes:
    """
    Internal fabrication report containing:
      - Design summary (key parameters)
      - Fabrication BOM with mass, material grade, and weld spec
      - QC checkpoint list with acceptance criteria
      - Material test certificate requirements
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
        leftMargin=ML, rightMargin=MR, topMargin=MT, bottomMargin=MB,
        title="VECTOMEC™ — Workshop Fabrication Report")

    r   = results or {}
    inp = inputs   or {}
    model_no = _model_number(inp, r)
    bkt  = r.get("bucket") or {}
    mat  = r.get("mat")    or {}
    story = []
    story += _page_header("WORKSHOP FABRICATION REPORT", model_no, doc_ref)

    # ── Design summary ────────────────────────────────────────────────
    story.append(_p("<b>DESIGN SUMMARY</b>", H2))
    sum_rows = [
        ["Parameter", "Value", "Parameter", "Value"],
        ["Model number",  model_no,
         "Material",      mat.get("name") or inp.get("mat_id", "—")],
        ["Capacity (req.)", f"{inp.get('Q_req','—')} t/h",
         "Capacity (ach.)", f"{_fmt(r.get('Q'), 1)} t/h"],
        ["Lift height",   f"{inp.get('H_m','—')} m",
         "Belt / chain speed", f"{_fmt(r.get('v'), 2)} m/s"],
        ["Head pulley Ø", f"{inp.get('D_mm','—')} mm",
         "Drive type",    "Chain" if inp.get("conveyor_type")=="chain" else "Belt"],
        ["Bucket series", bkt.get("id","—"),
         "Bucket W×P×Depth", f"{bkt.get('W','—')}×{bkt.get('P','—')}×{bkt.get('H','—')} mm"],
        ["Motor power",   f"{r.get('motor_kw','—')} kW",
         "Head shaft Ø",  f"{_fmt(r.get('d_mm'), 0)} mm"],
        ["Casing width",  f"{_fmt(r.get('belt_w'), 0)} mm",
         "No. of buckets", str(r.get("n_buckets","—"))],
    ]
    story.append(_table(sum_rows,
        [PW*0.22, PW*0.28, PW*0.22, PW*0.28]))
    story.append(_sp())

    # ── Fabrication BOM ───────────────────────────────────────────────
    story.append(_p("<b>FABRICATION BILL OF MATERIALS</b>", H2))
    story.append(_p(
        "All items identified by description (part numbers to be assigned at fabrication release). "
        "Mass values are calculated values — weigh actual parts at QC gate.", TINY))
    story.append(_sp(2))
    bom  = r.get("bom") or {}
    # BOM is {"items": [...], "summary": ..., "notes": ..., "version": ...}
    # Each item in the flat list has a "category" field -- group by category
    # for display (same as the BOM panel does in the desktop UI).
    bom_items = bom.get("items") or []
    bom_by_cat: dict = {}
    for item in bom_items:
        cat = str(item.get("category") or "OTHER")
        bom_by_cat.setdefault(cat, []).append(item)

    fab_headers = ["#", "Description", "Qty", "Unit", "Material / Grade",
                   "Mass ea. (kg)", "Total (kg)", "Weld / Fab spec"]
    fab_rows: list[list] = [fab_headers]
    pos = 0
    for category, items in bom_by_cat.items():
        cat_row = [Paragraph(f"<b>{category.upper()}</b>",
                               ParagraphStyle("ch", fontName="Helvetica-Bold",
                                              fontSize=7.5, textColor=ACCENT))]
        cat_row += [""] * (len(fab_headers) - 1)
        fab_rows.append(cat_row)
        for item in items:
            pos += 1
            spec = item.get("spec") or ""
            desc_lower = str(item.get("description", "")).lower()
            weld = "Full pen butt weld" if "shaft" in desc_lower \
                   else ("Fillet weld 8mm leg" if "cas" in desc_lower else "—")
            fab_rows.append([
                str(pos),
                item.get("description","—"),
                str(item.get("qty","—")),
                item.get("unit","—"),
                item.get("material","—"),
                str(item.get("mass_ea_kg", item.get("mass_ea", "—"))),
                str(item.get("mass_tot_kg", item.get("mass_total_kg", "—"))),
                weld,
            ])
    if len(fab_rows) > 1:
        col_w = [PW*0.04, PW*0.28, PW*0.05, PW*0.05, PW*0.17, PW*0.09, PW*0.09, PW*0.23]
        story.append(_table(fab_rows, col_w))
    else:
        story.append(_p("No BOM data available — run a full calculation first.", TINY))
    story.append(_sp())

    # ── QC Checkpoints ────────────────────────────────────────────────
    story.append(_p("<b>QUALITY CONTROL CHECKPOINTS</b>", H2))
    qc_rows = [["#", "Checkpoint", "Method", "Acceptance Criteria", "Sign-off"]]
    checkpoints = [
        ("1", "Head shaft material cert",     "Review MTC",
         "A36 / equiv. fy ≥ 250 MPa, Charpy 27J @ 0°C", ""),
        ("2", "Head shaft dimensional check", "Caliper / CMM",
         f"Ø{_fmt(r.get('d_mm'),0)} +0/−0.02 mm, runout < 0.05 mm", ""),
        ("3", "Keyway dimensions",            "Gauge",
         f"Width / depth per AS 1513, surface Ra ≤ 1.6 µm", ""),
        ("4", "Head pulley shell weld",       "Dye penetrant / UT",
         "No cracks, porosity ≤ 1.5 mm dia, full pen confirmed", ""),
        ("5", "Casing panel flatness",        "Straight-edge",
         "≤ 3 mm in any 1 m, mitre joints gapped < 1.5 mm", ""),
        ("6", "Casing bolt pattern",          "Template check",
         "Holes within ±0.5 mm of drawing, no burrs", ""),
        ("7", "Belt joint / splice",          "Visual + tension test",
         "Mechanical splice per CEMA, rated at 110 % working tension", ""),
        ("8", "Bucket attachment torque",     "Torque wrench",
         f"M12 Gr.8.8 bolts at 85 Nm ± 5 %", ""),
        ("9", "Alignment head-to-boot",       "Laser / plumb line",
         "< 1 mm/m deviation over elevator height", ""),
        ("10","Paint / coating",              "DFT gauge",
         "Min 75 µm DFT two-coat epoxy, no holidays on internal surfaces", ""),
    ]
    for cp in checkpoints:
        qc_rows.append(list(cp))
    story.append(_table(qc_rows, [PW*0.04, PW*0.24, PW*0.15, PW*0.40, PW*0.17]))
    story.append(_sp())

    # ── Material test requirements ────────────────────────────────────
    story.append(_p("<b>MATERIAL TEST CERTIFICATE REQUIREMENTS</b>", H2))
    mtc_rows = [["Item", "Std. / Grade", "MTC Type", "Min. Requirements"]]
    mtc_items = [
        ("Head shaft",   "ASTM A36 / AS 3678-300", "3.1 per EN 10204",
         "Tensile, yield, elongation, Charpy impact @ 0°C"),
        ("Casing plates","AS 3678-250 or 350",      "2.2 per EN 10204",
         "Grade confirmation, thickness ± 10 %"),
        ("Bucket material","Carbon steel / AR400",  "3.1 per EN 10204 if AR",
         "Hardness cert for AR grades, heat number traceability"),
        ("Head pulley shell","AS 3678-350",         "2.2 per EN 10204",
         "Grade, thickness, no laminar defects (UT if t > 25 mm)"),
        ("Fasteners",    "ISO 898-1 Gr.8.8",        "2.1 per EN 10204",
         "Grade marking on all fasteners, head date code visible"),
    ]
    for m in mtc_items:
        mtc_rows.append(list(m))
    story.append(_table(mtc_rows, [PW*0.18, PW*0.22, PW*0.18, PW*0.42]))

    doc.build(story)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
# REPORT 2 — PROCUREMENT (Commercial BOM)
# ══════════════════════════════════════════════════════════════════════════════
def build_procurement_report(results: dict, inputs: dict,
                              project: str = "", doc_ref: str = "") -> bytes:
    """
    Procurement report containing:
      - Commercial BOM with full technical specs for purchasing
      - Long-lead item flags
      - Delivery-critical items highlighted
      - Packaging/transport notes
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
        leftMargin=ML, rightMargin=MR, topMargin=MT, bottomMargin=MB,
        title="VECTOMEC™ — Procurement Report")

    r   = results or {}
    inp = inputs   or {}
    model_no = _model_number(inp, r)
    story = []
    story += _page_header("PROCUREMENT REPORT", model_no, doc_ref)
    story.append(_p(
        "<b>NOTE:</b> All items identified by description. Part numbers to be assigned at "
        "purchase-order stage. ★ = Long-lead / critical-path item — order first.", TINY))
    story.append(_sp(2))

    # ── Commercial BOM ────────────────────────────────────────────────
    story.append(_p("<b>COMMERCIAL BILL OF MATERIALS</b>", H2))
    bom  = r.get("bom") or {}
    bom_items = bom.get("items") or []
    bom_by_cat: dict = {}
    for item in bom_items:
        cat = str(item.get("category") or "OTHER")
        bom_by_cat.setdefault(cat, []).append(item)

    proc_headers = ["#", "Description", "Qty", "Unit", "Technical Specification",
                    "Delivery priority", "Notes"]
    proc_rows: list[list] = [proc_headers]
    pos = 0

    LONG_LEAD_KEYWORDS = ("motor", "gearbox", "vfd", "bearing", "shaft", "chain", "belt")
    CRIT_KEYWORDS      = ("motor", "gearbox", "head shaft", "belt", "chain")

    for category, items in bom_by_cat.items():
        cat_row = [Paragraph(f"<b>{category.upper()}</b>",
                               ParagraphStyle("ch2", fontName="Helvetica-Bold",
                                              fontSize=7.5, textColor=ACCENT))]
        cat_row += [""] * (len(proc_headers) - 1)
        proc_rows.append(cat_row)
        for item in items:
            pos += 1
            desc = str(item.get("description","—")).lower()
            is_long_lead = any(kw in desc for kw in LONG_LEAD_KEYWORDS)
            is_crit      = any(kw in desc for kw in CRIT_KEYWORDS)
            priority = "★ CRITICAL" if is_crit else ("Long lead" if is_long_lead else "Standard")
            spec = item.get("spec") or item.get("standard") or "—"
            proc_rows.append([
                str(pos),
                ("★ " if is_long_lead else "") + str(item.get("description","—")),
                str(item.get("qty","—")),
                item.get("unit","—"),
                spec,
                priority,
                str(item.get("notes","") or ""),
            ])

    if len(proc_rows) > 1:
        col_w = [PW*0.04, PW*0.26, PW*0.05, PW*0.05, PW*0.28, PW*0.12, PW*0.20]
        story.append(_table(proc_rows, col_w))
    else:
        story.append(_p("No BOM data — run a full calculation first.", TINY))
    story.append(_sp())

    # ── Long-lead summary ────────────────────────────────────────────
    story.append(_p("<b>LONG-LEAD / CRITICAL-PATH SUMMARY</b>", H2))
    ll_rows = [["Item", "Typical lead time", "Action required"]]
    ll_items = [
        ("Motor",        "8–16 weeks (IEC high-efficiency)",   "Confirm frame, voltage, IE class with supplier"),
        ("Gearbox",      "10–20 weeks (configured unit)",      "Confirm ratio, mounting, shaft dimensions"),
        ("VFD / Drive",  "6–14 weeks",                         "Confirm kW, voltage, comms protocol"),
        ("Elevator belt","4–8 weeks (cut-to-length)",          "Confirm BW, ply, cover grade, splice type"),
        ("Chain (ER/SC)","6–10 weeks (import)",                "Confirm pitch, WL, coating"),
        ("Head shaft",   "4–6 weeks (machined)",               "Issue machining drawing with MTC requirement"),
        ("Head bearing", "2–4 weeks",                          "Confirm bore, PN, quantity"),
    ]
    for ll in ll_items:
        ll_rows.append(list(ll))
    story.append(_table(ll_rows, [PW*0.20, PW*0.28, PW*0.52], header_bg=WARN_C))
    story.append(_sp())

    # ── Transport / packaging notes ───────────────────────────────────
    story.append(_p("<b>PACKAGING & TRANSPORT NOTES</b>", H2))
    H_m = float(inp.get("H_m") or 0)
    belt_w = float(r.get("belt_w") or 350)
    transport_notes = [
        f"Casing sections: split into max 6 m lengths for transport. Approx {max(1,int(H_m/6))} lifts.",
        f"Head section (approx {belt_w+400:.0f} mm wide): transport as single assembled unit if road permits.",
        "Belt: ship on drum, diameter per supplier minimum bend radius. Do NOT roll flat.",
        "Buckets: pack in bulk crates, max stack height 1.2 m, no sharp edges exposed.",
        "Shaft: ship in timber cradle, protected from impact. Mark 'DO NOT STACK'.",
        "All items to be tagged with model number and item description matching this BOM.",
    ]
    for note in transport_notes:
        story.append(_p(f"• {note}", BODY))

    doc.build(story)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
# REPORT 3 — END-USER (Installation, Commissioning, Maintenance, Spares)
# ══════════════════════════════════════════════════════════════════════════════
def build_enduser_report(results: dict, inputs: dict,
                          project: str = "", doc_ref: str = "") -> bytes:
    """
    End-user report containing:
      - Installation sequence
      - Pre-commissioning checklist
      - Commissioning procedure
      - Maintenance schedule (from reliability.py)
      - 1-year spares list (from reliability.py replacement recommendations)
      - Safety notes
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
        leftMargin=ML, rightMargin=MR, topMargin=MT, bottomMargin=MB,
        title="VECTOMEC™ — Installation, Commissioning & Maintenance Manual")

    r   = results or {}
    inp = inputs   or {}
    model_no = _model_number(inp, r)
    mnt  = r.get("maintenance") or {}
    sched = mnt.get("schedule") or []
    replacements = mnt.get("replacements") or []
    story = []
    story += _page_header("INSTALLATION, COMMISSIONING & MAINTENANCE MANUAL",
                           model_no, doc_ref)

    # ── Safety notice ─────────────────────────────────────────────────
    safety_rows = [[
        Paragraph("<b>⚠ SAFETY</b>",
                   ParagraphStyle("st", fontName="Helvetica-Bold", fontSize=9,
                                  textColor=white)),
        Paragraph(
            "ISOLATE AND LOCK OUT all electrical supplies before any maintenance. "
            "Minimum two persons for any work above 1.8 m. "
            "Never reach into the elevator casing while the belt/chain is in motion. "
            "Belt/chain may restart automatically if the VFD is in AUTO mode — confirm "
            "drive is in LOCAL/ISOLATED before opening any access door.",
            ParagraphStyle("sb", fontSize=8, textColor=white, leading=12)),
    ]]
    safety_table = Table(safety_rows, colWidths=[PW*0.12, PW*0.88],
                         style=TableStyle([
                             ("BACKGROUND", (0, 0), (-1, -1), DANGER_C),
                             ("LEFTPADDING", (0, 0), (-1, -1), 6),
                             ("TOPPADDING", (0, 0), (-1, -1), 5),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                         ]))
    story.append(safety_table)
    story.append(_sp(3))

    # ── Installation sequence ─────────────────────────────────────────
    story.append(_p("<b>INSTALLATION SEQUENCE</b>", H2))
    H_m = float(inp.get("H_m") or 25)
    bw  = float(r.get("belt_w") or 350)
    inst_steps = [
        ["1", "Site preparation",
         "Confirm foundation bolt pattern, level tolerance ≤ 2 mm over any 3 m. "
         "Confirm structural steel or concrete pedestal capacity per load schedule."],
        ["2", "Boot section assembly",
         "Install boot section and take-up. Level horizontally (< 0.5 mm/m). "
         "Fix boot anchor bolts — do not fully torque yet."],
        ["3", "Casing erection",
         f"Erect casing sections bottom-up using craneage. Plumb to within 1:1000 "
         f"({H_m*1.0:.0f} mm over {H_m:.0f} m height). Align all flanges, "
         f"tighten bolts to 85 Nm (M16)."],
        ["4", "Head section installation",
         "Lower head section onto top of casing. Align pulley centerline to boot "
         "centerline using laser or piano wire. Secure all flanges."],
        ["5", "Drive installation",
         "Mount motor and gearbox. Align coupling to ≤ 0.1 mm TIR. "
         "Fit coupling guard before any energisation."],
        ["6", "Belt / chain installation",
         f"Thread belt/chain from boot to head. Install splice/attachment links. "
         f"Adjust take-up to achieve initial tension (see commissioning procedure). "
         f"Belt width {bw:.0f} mm — ensure tracking margin on both sides."],
        ["7", "Bucket installation",
         "Attach buckets at the correct pitch. Verify correct orientation (open face "
         "up on carry side). Check attachment torque after first 4 hours of running."],
        ["8", "Electrical connection",
         "Connect motor and VFD per electrical schematic. Verify correct rotation "
         "BEFORE loading — jog in maintenance mode, confirm belt moves UP on carry side."],
        ["9", "Final inspection",
         "Check all access doors sealed. Confirm no tools/debris inside casing. "
         "Record pre-commissioning checklist below before energising under load."],
    ]
    inst_rows = [["Step", "Activity", "Details / Acceptance"]]
    for s in inst_steps:
        inst_rows.append(s)
    story.append(_table(inst_rows, [PW*0.06, PW*0.22, PW*0.72]))
    story.append(_sp())

    # ── Pre-commissioning checklist ───────────────────────────────────
    story.append(_p("<b>PRE-COMMISSIONING CHECKLIST</b>", H2))
    pre_rows = [["#", "Check", "Accepted ✓", "Sign / Date"]]
    pre_items = [
        "All casing bolts torqued and checked",
        "Belt/chain splice/attachment links inspected",
        "Take-up tension set to design value",
        "Bucket attachment torque verified",
        "Drive alignment TIR < 0.1 mm confirmed",
        "Motor rotation confirmed (jog test — no load)",
        "VFD programmed: ramp-up ≥ 10 s, ramp-down ≥ 5 s",
        "All guards and covers fitted",
        "Feed chute clearance confirmed (no fouling)",
        "Emergency stop tested and documented",
        "Electrical isolation tagged out and released",
    ]
    for i, item in enumerate(pre_items, 1):
        pre_rows.append([str(i), item, "", ""])
    story.append(_table(pre_rows, [PW*0.05, PW*0.58, PW*0.17, PW*0.20]))
    story.append(_sp())

    # ── Commissioning procedure ───────────────────────────────────────
    story.append(_p("<b>COMMISSIONING PROCEDURE</b>", H2))
    v = float(r.get("v") or 1.5)
    Q = float(r.get("Q") or 100)
    comm_steps = [
        ("Step 1 — No-load run (15 min)",
         f"Start elevator empty. Run at 25 % speed for 5 min, then 50 % for 5 min, "
         f"then 100 % for 5 min. Observe belt/chain tracking — adjust if edges contact "
         f"casing. Record bearing temperatures: alarm > 70 °C, trip > 85 °C."),
        ("Step 2 — Partial load (30 min)",
         f"Introduce 50 % of design feed rate ({Q*0.5:.1f} t/h). Run for 30 min. "
         f"Check for backlegging in boot, even bucket filling, and clean discharge "
         f"at head. Record power draw — compare against design {r.get('motor_kw','—')} kW."),
        ("Step 3 — Full load (60 min)",
         f"Increase to design capacity {Q:.1f} t/h at design speed {v:.2f} m/s. "
         f"Run for 60 min continuously. Record: power, bearing temps, belt tracking, "
         f"any abnormal noise. Adjust take-up if tracking error increases."),
        ("Step 4 — Inspection after first load run",
         "Stop elevator, lock out. Re-check bucket attachment torque. "
         "Inspect belt splice/chain links for wear. Check bearing lubrication. "
         "Re-torque any casing bolts that have loosened."),
        ("Step 5 — Sign-off",
         "Complete all pre-commissioning checklist items. Obtain customer sign-off. "
         "Hand over this manual, maintenance schedule, and spares list."),
    ]
    for title, detail in comm_steps:
        story.append(KeepTogether([
            _p(f"<b>{title}</b>", H3),
            _p(detail, BODY),
            _sp(1),
        ]))
    story.append(_sp())

    # ── Maintenance schedule ──────────────────────────────────────────
    story.append(_p("<b>MAINTENANCE SCHEDULE</b>", H2))
    if sched:
        maint_rows = [["Interval", "Task", "Category / Component"]]
        for s in sched:
            h = s.get("interval_h") or ""
            wk = s.get("interval_wk") or ""
            if h and wk:
                interval_str = f"{h:,}h / {wk}wk"
            elif h:
                interval_str = f"{h:,}h"
            elif wk:
                interval_str = f"{wk}wk"
            else:
                interval_str = str(s.get("interval") or "—")
            maint_rows.append([
                interval_str,
                str(s.get("task") or "—"),
                str(s.get("category") or s.get("component") or "—"),
            ])
        story.append(_table(maint_rows, [PW*0.18, PW*0.35, PW*0.47]))
    else:
        # Fallback generic schedule when reliability data isn't available
        fallback_rows = [["Interval", "Task"]]
        fallback = [
            ("Daily",       "Check belt tracking, listen for abnormal noise, inspect feed/discharge"),
            ("Weekly",      "Inspect bucket attachments — check 10 % sample for torque retention"),
            ("Monthly",     "Lubricate bearings per manufacturer spec, check coupling alignment"),
            ("3-Monthly",   "Inspect belt/chain for wear elongation, check splice/links"),
            ("6-Monthly",   "Full internal casing inspection, measure bucket wear, check casing liner"),
            ("Annually",    "Full overhaul — replace wear items per spares list, alignment check"),
        ]
        for f in fallback:
            fallback_rows.append(list(f))
        story.append(_table(fallback_rows, [PW*0.20, PW*0.80]))
    story.append(_sp())

    # ── 1-Year spares list ────────────────────────────────────────────
    story.append(_p("<b>RECOMMENDED 1-YEAR SPARES LIST</b>", H2))
    story.append(_p(
        "Stocking these items on-site eliminates lead-time delays for the most "
        "common planned and unplanned replacement requirements. "
        "Quantities are based on the reliability model for this elevator configuration.", TINY))
    story.append(_sp(2))

    if replacements:
        sp_rows = [["Component / Description", "Est. Life (yr)", "Action / Specification"]]
        for rep in replacements:
            sp_rows.append([
                str(rep.get("component") or rep.get("description") or "—"),
                str(rep.get("estimated_life_yr") or rep.get("qty_per_year") or "—"),
                str(rep.get("action") or rep.get("material_spec") or rep.get("reason") or "—"),
            ])
        story.append(_table(sp_rows, [PW*0.45, PW*0.15, PW*0.40]))
    else:
        # Fallback generic spares list
        sp_fallback = [["Description", "Qty", "Notes"]]
        bkt_id = (r.get("bucket") or {}).get("id", "bucket")
        sp_items = [
            (f"Buckets — {bkt_id} style",     "10 % of installed count", "Replace damaged/worn at each 6-month inspection"),
            ("Bucket attachment bolts + nuts", "20 % of installed count", "M12 Gr.8.8 with nyloc nut"),
            ("Belt splice / mechanical fasteners","2 sets",               "Emergency splice repair"),
            ("Head bearing (matched pair)",     "1 set",                  "Replace both bearings together"),
            ("Boot bearing (matched pair)",     "1 set",                  "Replace both bearings together"),
            ("Coupling element / spider",       "2 off",                  "Elastomeric element — replace annually"),
            ("Casing liner panels",             "1 full set chute liners","AR400 / Wear Plate per design spec"),
            ("Grease (NLGI 2 / high-temp grade)","5 kg",                 "For head and boot bearings"),
        ]
        for s in sp_items:
            sp_fallback.append(list(s))
        story.append(_table(sp_fallback, [PW*0.40, PW*0.18, PW*0.42]))

    story.append(_sp(3))
    story.append(_p(
        "Contact Jayveecons Engineering &amp; Design for replacement parts, "
        "engineering support, or site service — reference the model number on the "
        "elevator nameplate which matches this document.", TINY))

    doc.build(story)
    return buf.getvalue()