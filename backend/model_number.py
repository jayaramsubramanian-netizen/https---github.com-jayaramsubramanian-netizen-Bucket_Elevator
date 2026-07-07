"""
model_number.py — VECTOMEC™ Model Number Generator
═══════════════════════════════════════════════════════════════════════════
Generates the finalized VM model number taxonomy from a results + inputs
dict pair (the same two dicts every other backend module already receives).

Format:
    VM - [FAMILY] - [DRIVE] - [BW_mm] / [D_mm] - [TAKEUP] - [MATERIAL] - [DUTY]

Segments
────────────────────────────────────────────────────────────────────────
VM          Fixed brand prefix.

FAMILY      CD  Centrifugal Discharge  (AA/AC/C buckets, standard service)
            KD  Continuous Discharge   (HF/MF buckets, standard service)
            MD  Mill-Duty              Overrides CD/KD when any of:
                                         • material abrasion class ≥ 5/7
                                         • material temperature > 80 °C
                                         • reinforced casing (t_use_mm > 6.0)
            SC  Super-Capacity         (double-chain, SC bucket, n_strands=2)
            HG  High-Speed Grain       RESERVED — double-leg belt, not yet
                                       implemented; code reserved for catalog.

DRIVE       B   Belt
            C   Chain

BW_mm       Bucket width rounded DOWN to nearest standard step:
            152 · 203 · 254 · 305 · 356 · 406 · 457 · 508 · 610 · 762

D_mm        Head pulley / sprocket pitch diameter in mm.
            Rounded to nearest 50 mm for clarity.

TAKEUP      Omitted for the default (boot / screw).  Only appended for
            non-default arrangements:
            BG  Boot  · Gravity counterweight
            BY  Boot  · Hydraulic cylinder
            HS  Head  · Screw
            HG  Head  · Gravity
            HY  Head  · Hydraulic

MATERIAL    Omitted for carbon steel (default).  Only appended otherwise:
            SS1 Stainless 304
            SS2 Stainless 316
            SS3 Stainless 316L / duplex
            P1  Nylon
            P2  Polyurethane
            P3  UHMWPE / engineering plastic

DUTY        Any combination, alphabetical order:
            AR  Abrasion-resistant bucket + casing liner (abrasion ≥ 5/7)
            DR  Double-row bucket mounting (CD/KD belt only; not SC or HG)
            HT  High-temperature service > 80 °C, ≤ 250 °C

NOTE — HG family (double-leg belt) is reserved for catalog completeness but
       has no backend implementation yet.  A model number will never be auto-
       generated with family=HG from a real calculation until the double-leg
       backend logic is built.  See open task list, item #2 (HG).
"""

_BW_STEPS = [152, 203, 254, 305, 356, 406, 457, 508, 610, 762]


def _nearest_bw(width_mm: float) -> int:
    """Round DOWN to nearest standard bucket-width step."""
    candidates = [w for w in _BW_STEPS if w <= width_mm]
    return candidates[-1] if candidates else _BW_STEPS[0]


def _round_d(d_mm: float) -> int:
    """Round head pulley / sprocket diameter to nearest 50 mm."""
    return max(50, round(d_mm / 50) * 50)


def generate_model_number(inputs: dict, results: dict,
                           material_code: str = "",
                           is_double_row: bool = False) -> str:
    """
    Generate the full VM model number string.

    Parameters
    ----------
    inputs        The raw input dict (same as sent to /calculate).
    results       The full results dict returned by /calculate.
    material_code Optional non-carbon-steel material suffix:
                  "SS1", "SS2", "SS3", "P1", "P2", "P3" — empty for carbon steel.
    is_double_row True to append the DR duty suffix (belt CD/KD only).

    Returns
    -------
    str   e.g. "VM-MD-C-400/700-AR-HT"
    """
    inp = inputs  or {}
    r   = results or {}

    # ── Extract key fields ──────────────────────────────────────────────
    bkt          = r.get("bucket")          or {}
    mat          = r.get("mat")             or r.get("material") or {}
    cp           = r.get("casing_panel")    or {}
    chain_sel    = r.get("chain_selected")  or {}
    boot         = r.get("boot_pulley")     or {}

    bucket_style   = str(bkt.get("style") or bkt.get("type") or "").upper().strip()
    discharge_type = str(bkt.get("discharge_type") or "").lower()
    is_chain       = bool(r.get("is_chain") or (str(inp.get("conveyor_type","")).lower() == "chain"))
    n_strands      = int(chain_sel.get("n_strands") or inp.get("chain_n_strands") or 1)

    abr_class      = int(mat.get("abr_code") or inp.get("custom_abr") or 0)
    mat_temp_c     = float(inp.get("material_temperature_c") or 20)
    casing_t_mm    = float(cp.get("t_use_mm") or 0)

    bw_mm          = float(bkt.get("W") or r.get("belt_w") or inp.get("belt_width_override_mm") or 305)
    d_mm           = float(inp.get("D_mm") or 500)

    takeup_type    = str(inp.get("takeup_type") or "screw").lower()
    takeup_pos     = str(inp.get("takeup_position") or "boot").lower()

    # ── FAMILY ───────────────────────────────────────────────────────────
    # SC overrides everything else (structural: double-chain, between-strand mount)
    if bucket_style == "SC" and n_strands == 2:
        family = "SC"
    # MD: duty-classification override for CD or KD
    elif abr_class >= 5 or mat_temp_c > 80 or casing_t_mm > 6.0:
        family = "MD"
    # KD: continuous discharge bucket styles
    elif discharge_type == "continuous" or bucket_style in ("HF", "MF"):
        family = "KD"
    # CD: centrifugal discharge bucket styles
    else:
        family = "CD"
    # HG not auto-assigned -- reserved for future double-leg implementation

    # ── DRIVE ────────────────────────────────────────────────────────────
    drive = "C" if is_chain else "B"

    # ── DIMENSIONS ───────────────────────────────────────────────────────
    bw_std = _nearest_bw(bw_mm)
    d_std  = _round_d(d_mm)

    # ── TAKEUP ───────────────────────────────────────────────────────────
    # Default (boot + screw) → no suffix.
    _TAKEUP_MAP = {
        ("boot",  "screw"):     "",     # default, omit
        ("boot",  "gravity"):   "BG",
        ("boot",  "hydraulic"): "BY",
        ("head",  "screw"):     "HS",
        ("head",  "gravity"):   "HG",
        ("head",  "hydraulic"): "HY",
    }
    takeup_code = _TAKEUP_MAP.get((takeup_pos, takeup_type), "")

    # ── DUTY suffixes ─────────────────────────────────────────────────────
    duty_flags = []
    if abr_class >= 5:
        duty_flags.append("AR")
    if is_double_row and family in ("CD", "KD") and not is_chain:
        duty_flags.append("DR")
    if mat_temp_c > 80:
        duty_flags.append("HT")
    duty_flags.sort()

    # ── Assemble ─────────────────────────────────────────────────────────
    # Order: VM-FAMILY-DRIVE-BW/D - MATERIAL - TAKEUP - DUTY...
    # Material suffix is immediately after the dimension segment because
    # it designates the bucket construction material, not the machine
    # arrangement -- closest logically to what it modifies.
    parts = [f"VM-{family}-{drive}-{bw_std}/{d_std}"]
    for suffix in [material_code, takeup_code] + duty_flags:
        if suffix:
            parts.append(suffix)
    return "-".join(parts)


def parse_model_number(model: str) -> dict:
    """
    Parse a VM model number string back into its components.
    Returns a dict for display/validation purposes; not used in calculation.
    """
    try:
        parts = model.split("-")
        # VM-FAMILY-DRIVE-BW/D[-...suffixes]
        vm, family, drive, dim_part = parts[0], parts[1], parts[2], parts[3]
        bw_str, d_str = dim_part.split("/")
        bw, d = int(bw_str), int(d_str)
        suffixes = parts[4:] if len(parts) > 4 else []
        return {
            "prefix": vm,
            "family": family,
            "drive": drive,
            "bucket_width_mm": bw,
            "pulley_diameter_mm": d,
            "suffixes": suffixes,
            "valid": True,
        }
    except Exception as e:
        return {"valid": False, "error": str(e), "raw": model}