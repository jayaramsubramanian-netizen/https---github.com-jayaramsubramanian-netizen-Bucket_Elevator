"""
backend/bucket_model_number.py -- VECTOMEC bucket model number (VB-).
═══════════════════════════════════════════════════════════════════════════
    VB-[Series]-[Material]-[Style]-[WWPPxHH]-[Attachment]-[Hole]-[Options...]

    VB-CM-AR500-AA-2428X40-D6-WR              (belt)
    VB-MN-DI-AA-3035X50-K2-D6-WR              (chain -- attachment field present)

WHY THIS IS GENERATED, NOT A COLUMN
───────────────────────────────────
Only THREE of the seven fields are properties of the bucket itself:

    Style   -> buckets.style
    Size    -> buckets.W_mm / P_mm / H_mm
    Hole    -> buckets.boltN

The other four -- Series, Material, Attachment, Options -- are properties of the
DESIGN THAT SELECTS the bucket. The same physical AA bucket is
VB-AG-HDPE-AA-...-D2 in a grain elevator and VB-CM-AR500-AA-...-D6-WR in a cement
one. So a static model_number column would be wrong for every design but one.

It therefore belongs here, generated at solve time from (bucket row + inputs) --
structurally the same as the elevator's own VM- number in model_number.py. This is
also what the spec document itself calls for: "generated from validated engineering
calculations rather than selected manually."

SCOPE -- METRIC VECTOMEC LINE ONLY  (option A, Jay's decision)
─────────────────────────────────────────────────────────────
The 40 existing Martin-derived buckets KEEP their imperial identity ("AA 12x8",
bucket_id AA_12x8) and are NOT given VB- numbers. Their dimensions stay stored in
metric (W_mm/P_mm/H_mm) and every calculation uses those, unchanged -- only the
LABEL stays imperial.

The reason is in the data. The VB size code packs each dimension into two digits
(tens of mm), so it can only express a metric-first line:

    AA_12x7 is really 305 x 178 x 184 mm  ->  a 2-digit code says 300 x 180 x 180

No two Martin buckets actually COLLIDE onto the same code (checked all 40), so the
scheme is not ambiguous -- but it is lossy, and stamping a VECTOMEC part number on
a bucket whose real width is 305mm while the number says 300mm would put a wrong
dimension on a purchase order. Martin buckets are catalogued as Martin buckets.
VB- numbers are for the metric line, whose dimensions will be chosen ON the tens
grid and therefore encode exactly.

═══════════════════════════════════════════════════════════════════════════
WHAT IS NOT IMPLEMENTED HERE, AND WHY  --  READ THIS
═══════════════════════════════════════════════════════════════════════════
The FORMATTER below is complete and the code tables are transcribed from the spec.

The SELECTION RULES are not, and I have not invented them. Choosing:

    abrasiveness + temperature + moisture  ->  AR400 vs AR500 vs ST316 vs HDPE
    material category + hazard codes       ->  CM vs MN vs FD vs AG series
    abrasion + food + ATEX flags           ->  which of WR / ATX / FD / AR options

is ENGINEERING JUDGEMENT with real consequences -- specify AR400 where AR500 was
needed and the bucket wears out in service. There is no CEMA table for it, and the
spec document lists the codes without giving the thresholds that map a design onto
them.

So build_model_number() takes those four as EXPLICIT ARGUMENTS. Until you give me
the rules, the caller must supply them; nothing here guesses. select_series() /
select_material() / select_options() are stubs that raise, deliberately, rather
than returning a plausible-looking default that would silently ship a wrong
material spec on a real drawing.
"""
from __future__ import annotations

# ── Section 1: application series ────────────────────────────────────────
SERIES = {
    "AG": "Agriculture — grain, corn, soybeans",
    "FD": "Food — FDA, sanitary",
    "CM": "Cement — heavy abrasive",
    "MN": "Mining — severe abrasion",
    "PM": "Power — fly ash",
    "CH": "Chemical — general chemicals",
    "PH": "Pharmaceutical — hygienic",
    "FR": "Fertilizer — corrosion resistant",
    "SD": "Sand & Aggregate — heavy duty",
    "RM": "Recycling — impact resistant",
    "WD": "Wood Products — chips, pellets",
    "CU": "Custom — engineered",
}

# ── Section 2: bucket material ───────────────────────────────────────────
MATERIALS = {
    "HDPE":  "High-density polyethylene",
    "NY":    "Nylon",
    "PU":    "Polyurethane",
    "ST304": "Stainless 304",
    "ST316": "Stainless 316",
    "CS":    "Carbon steel",
    "AR400": "Abrasion-resistant 400 BHN",
    "AR450": "Abrasion-resistant 450 BHN",
    "AR500": "Abrasion-resistant 500 BHN",
    "DI":    "Ductile iron",
    "AL":    "Aluminium",
}

# ── Section 3: bucket style ──────────────────────────────────────────────
# NOTE: CC is a STYLE (CC-HD), per Jay -- the spec document's first example
# ("VB-CC-HDPE-AA-...") put CC in the series slot, which was a typo for CM.
STYLES = {
    "AA":  "Standard centrifugal",
    "AC":  "Deep centrifugal",
    "CC":  "CC-HD",
    "HF":  "High front",
    "MF":  "Medium front",
    "SC":  "Super capacity",
    "LP":  "Low profile",
    "SD":  "Shallow digging",
    "DIG": "Digging bucket",
    "EN":  "Elevator bucket special",
}

# ── Section 5: hole pattern ──────────────────────────────────────────────
HOLE_PATTERNS = {
    "D2": "2-hole", "D4": "4-hole", "D6": "6-hole", "D8": "8-hole",
    "HC": "Heavy chain", "HB": "Heavy belt", "SB": "Standard belt",
}

# ── Chain attachment (chain buckets only) ────────────────────────────────
ATTACHMENTS = {
    "K2":  "K attachment", "A2": "A attachment", "DIN": "DIN chain attachment",
    "WH":  "Welded hub",   "DS": "Double strand",
    "BT":  "Belt (no chain attachment)",
}

# ── Section 6: optional features ─────────────────────────────────────────
OPTIONS = {
    "WR": "Wear lip",          "NR": "Non-return lip",   "AB": "Anti-backlegging",
    "AT": "Anti-static",       "FD": "FDA",              "ATX": "ATEX",
    "FR": "Flame resistant",   "UV": "UV stabilized",    "AR": "Abrasion-resistant coating",
    "RB": "Rubber backed",     "SP": "Special drilling",
}


def size_code(W_mm: float, P_mm: float, H_mm: float) -> str:
    """WWPPxHH -- each dimension in TENS of mm, two digits.

    305 x 178 x 184  ->  "3018X18"   (lossy: this is why Martin buckets don't
                                       get VB numbers -- see the module docstring)
    240 x 280 x 400  ->  "2428X40"   (exact: on the tens grid, as a metric-line
                                       bucket will be by design)
    """
    return f"{round(W_mm / 10):02d}{round(P_mm / 10):02d}X{round(H_mm / 10):02d}"


def hole_code(boltN: int) -> str:
    """boltN -> D2/D4/D6/D8. Raises on an odd or unsupported count rather than
    rounding to the nearest -- a bucket with 3 bolts is not a 'D4', and quietly
    calling it one would put a wrong drilling spec on a fabrication drawing.

    NOTE this bites immediately: 16 of the 40 Martin buckets have boltN=3 or 5.
    Another reason the VB scheme belongs to the metric line, whose hole patterns
    will be specified as D2/D4/D6/D8 from the start.
    """
    mapping = {2: "D2", 4: "D4", 6: "D6", 8: "D8"}
    if boltN not in mapping:
        raise ValueError(
            f"boltN={boltN} has no VB hole code. The scheme defines D2/D4/D6/D8 "
            f"only (even counts). Supply an explicit hole= code for this bucket."
        )
    return mapping[boltN]


def build_model_number(
    *,
    series: str,
    material: str,
    style: str,
    W_mm: float,
    P_mm: float,
    H_mm: float,
    hole: str,
    attachment: str | None = None,
    options: tuple = (),
) -> str:
    """Assemble and VALIDATE a VB- number. Every code is checked against the
    enumerations above -- an unknown code raises rather than silently producing a
    model number that no catalogue can resolve.

    attachment: pass a chain attachment (K2/A2/DIN/WH/DS) for chain elevators, or
    None/BT for belt. The spec gives chain buckets the extra field:
        belt : VB-[Series]-[Mat]-[Style]-[Size]-[Hole]-[Opts]
        chain: VB-[Series]-[Mat]-[Style]-[Size]-[Attach]-[Hole]-[Opts]
    """
    if series not in SERIES:
        raise ValueError(f"unknown series {series!r}; expected one of {sorted(SERIES)}")
    if material not in MATERIALS:
        raise ValueError(f"unknown material {material!r}; expected one of {sorted(MATERIALS)}")
    if style not in STYLES:
        raise ValueError(f"unknown style {style!r}; expected one of {sorted(STYLES)}")
    if hole not in HOLE_PATTERNS:
        raise ValueError(f"unknown hole pattern {hole!r}; expected one of {sorted(HOLE_PATTERNS)}")
    if attachment is not None and attachment not in ATTACHMENTS:
        raise ValueError(f"unknown attachment {attachment!r}; expected one of {sorted(ATTACHMENTS)}")
    for o in options:
        if o not in OPTIONS:
            raise ValueError(f"unknown option {o!r}; expected from {sorted(OPTIONS)}")

    parts = ["VB", series, material, style, size_code(W_mm, P_mm, H_mm)]
    if attachment and attachment != "BT":
        parts.append(attachment)
    parts.append(hole)
    parts.extend(options)
    return "-".join(parts)


# ═══════════════════════════════════════════════════════════════════════
# SELECTION RULES -- NOT IMPLEMENTED. These need Jay's engineering input.
# ═══════════════════════════════════════════════════════════════════════
def select_series(inputs, results) -> str:
    """material category / hazard codes -> AG, CM, MN, FD, ...

    NOT IMPLEMENTED. The materials table has `category`, `hazard_codes` and
    `flags`, so the inputs exist -- but the MAPPING from a material category onto
    an application series is a business/engineering decision, not a derivation.
    ('clinker' -> CM is obvious; 'salt' -> CH or FD or AG is not.)
    """
    raise NotImplementedError(
        "select_series(): needs the category->series mapping. Not guessed. "
        "See bucket_model_number.py."
    )


def select_material(inputs, results) -> str:
    """abrasiveness / temperature / moisture / FDA -> AR400, ST316, HDPE, ...

    NOT IMPLEMENTED, and this is the one with teeth. Specifying AR400 where AR500
    was required means the bucket wears out early in service. The thresholds
    (which abr_code demands AR500 over AR400? at what temperature does HDPE stop
    being valid?) are not in CEMA and are not in the spec document. They must come
    from Jay.
    """
    raise NotImplementedError(
        "select_material(): needs abrasiveness/temperature thresholds. NOT guessed "
        "-- a wrong material spec ships a bucket that fails in service."
    )


def select_options(inputs, results) -> tuple:
    """hazard codes / abrasion / food-contact -> (WR, ATX, FD, ...)

    NOT IMPLEMENTED. hazard_codes exists on the material row, but which hazard
    demands ATX vs AT, and at what abrasiveness a wear lip (WR) becomes standard,
    is Jay's call.
    """
    raise NotImplementedError("select_options(): needs the hazard->option mapping.")