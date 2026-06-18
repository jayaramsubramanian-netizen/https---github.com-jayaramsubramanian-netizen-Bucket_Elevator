"""
Task 13 — generate_report.py patch: Engineering Sign-Off Block
==============================================================
Add these two pieces to YOUR generate_report.py v2.0.0.
Do NOT replace the entire file — your version is far more complete.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PART A: Add this helper function anywhere before build_report()
         (e.g. after the _design_notes() function)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _sign_off_block(sign_off: dict | None) -> list:
    \"\"\"
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
    \"\"\"
    from reportlab.platypus import HRFlowable

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


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PART B: Update build_report() signature and add sign-off section
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Find this line at the top of build_report():

    def build_report(results: dict, inputs: dict,
                     project: str = "", doc_ref: str = "",
                     output_path=None) -> bytes:

   Replace with:

    def build_report(results: dict, inputs: dict,
                     project: str = "", doc_ref: str = "",
                     sign_off: dict | None = None,
                     output_path=None) -> bytes:


2. Find this block near the END of build_report(), just before the footer:

    # ── FOOTER ───────────────────────────────────────────────────────────────
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))

   Replace with:

    # ── SECTION 8: ENGINEERING SIGN-OFF ──────────────────────────────────────
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

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
That is the complete Task 13 change to generate_report.py.
Only 3 edit points — no other lines change.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
