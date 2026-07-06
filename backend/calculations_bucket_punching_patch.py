"""
calculations.py PATCH — Bucket Punching Data (CEMA Standard)
═══════════════════════════════════════════════════════════════════════════
Adds the bolt mounting-flange data that is missing from BUCKET_SERIES.
This is real catalog reference data and belongs in Python next to the
other catalog-sourced fields (bucket_mass_kg, front_angle_deg, etc.) —
NOT hardcoded in the .jsx frontend.

HONESTY NOTE on AC and SC styles
─────────────────────────────────────────────────────────────────────────
Industry-standard bucket punching catalogs do not publish bolt patterns
for AC and SC styles -- vendor confirmation is required before
fabrication for these two specifically.
For AC, I have used the same B6/B7/B8 family as Style AA & C (same
catalog page, same general bucket construction) as an ENGINEERING
ESTIMATE — flagged "punch_confirmed": False below.
For SC, buckets mount BETWEEN TWO CHAIN STRANDS (not on a belt) —
"punch" is set to "chain" and the bolt fields represent chain
attachment pin spacing, not belt punching. This also needs vendor
confirmation before fabrication, flagged the same way.

HOW TO APPLY
─────────────────────────────────────────────────────────────────────────
For every dict in BUCKET_SERIES, add these 6 keys. Below is the complete
mapping by id → field values. Apply by adding the keys to each dict
literal in BUCKET_SERIES (calculations.py lines ~115-280 in your file).
"""

# punch, A_mm (hole spacing), B_mm (edge inset / row offset),
# bolt_dia_mm, n_holes, punch_confirmed
BUCKET_PUNCHING = {
    # ── Style AA (centrifugal) — catalog H-152 "Style AA & C" table ─────────
    "AA_6x4":   {"punch":"B1","boltA_mm":76.2, "boltB_mm":25.4, "boltDia_mm":6.4,"boltN":2,"punch_confirmed":True},
    "AA_8x5":   {"punch":"B6","boltA_mm":76.2, "boltB_mm":25.4, "boltDia_mm":7.9,"boltN":3,"punch_confirmed":True},
    "AA_10x6":  {"punch":"B6","boltA_mm":88.9, "boltB_mm":25.4, "boltDia_mm":7.9,"boltN":3,"punch_confirmed":True},
    "AA_12x7":  {"punch":"B6","boltA_mm":114.3,"boltB_mm":25.4, "boltDia_mm":7.9,"boltN":3,"punch_confirmed":True},
    "AA_14x8":  {"punch":"B7","boltA_mm":101.6,"boltB_mm":25.4, "boltDia_mm":7.9,"boltN":4,"punch_confirmed":True},
    "AA_16x8":  {"punch":"B7","boltA_mm":114.3,"boltB_mm":25.4, "boltDia_mm":7.9,"boltN":4,"punch_confirmed":True},
    "AA_18x8":  {"punch":"B7","boltA_mm":127.0,"boltB_mm":25.4, "boltDia_mm":7.9,"boltN":4,"punch_confirmed":True},
    "AA_18x10": {"punch":"B7","boltA_mm":127.0,"boltB_mm":25.4, "boltDia_mm":7.9,"boltN":4,"punch_confirmed":True},

    # ── Style AC (centrifugal, mill duty) — NOT in catalog table; estimate ──
    # Not published in industry-standard catalogs -- vendor confirmation required
    "AC_12x8":  {"punch":"B6","boltA_mm":114.3,"boltB_mm":25.4,"boltDia_mm":9.5,"boltN":3,"punch_confirmed":False},
    "AC_14x8":  {"punch":"B7","boltA_mm":101.6,"boltB_mm":25.4,"boltDia_mm":9.5,"boltN":4,"punch_confirmed":False},
    "AC_16x8":  {"punch":"B7","boltA_mm":114.3,"boltB_mm":25.4,"boltDia_mm":9.5,"boltN":4,"punch_confirmed":False},
    "AC_18x10": {"punch":"B7","boltA_mm":127.0,"boltB_mm":25.4,"boltDia_mm":9.5,"boltN":4,"punch_confirmed":False},
    "AC_20x10": {"punch":"B8","boltA_mm":101.6,"boltB_mm":25.4,"boltDia_mm":9.5,"boltN":5,"punch_confirmed":False},
    "AC_24x10": {"punch":"B8","boltA_mm":127.0,"boltB_mm":25.4,"boltDia_mm":9.5,"boltN":5,"punch_confirmed":False},

    # ── Style C (centrifugal, open front) — catalog H-152 "Style AA & C" ────
    "C_6x4":  {"punch":"B1","boltA_mm":76.2, "boltB_mm":25.4,"boltDia_mm":6.4,"boltN":2,"punch_confirmed":True},
    "C_8x4":  {"punch":"B6","boltA_mm":76.2, "boltB_mm":25.4,"boltDia_mm":6.4,"boltN":3,"punch_confirmed":True},
    "C_10x5": {"punch":"B6","boltA_mm":88.9, "boltB_mm":25.4,"boltDia_mm":6.4,"boltN":3,"punch_confirmed":True},
    "C_14x7": {"punch":"B7","boltA_mm":101.6,"boltB_mm":25.4,"boltDia_mm":6.4,"boltN":4,"punch_confirmed":True},
    "C_16x7": {"punch":"B7","boltA_mm":114.3,"boltB_mm":25.4,"boltDia_mm":6.4,"boltN":4,"punch_confirmed":True},

    # ── Style MF (continuous) — catalog H-152 "Style LF & MF" table ─────────
    "MF_10x7": {"punch":"B6","boltA_mm":88.9, "boltB_mm":133.4,"boltDia_mm":7.9,"boltN":3,"punch_confirmed":True},
    "MF_12x7": {"punch":"B6","boltA_mm":114.3,"boltB_mm":134.9,"boltDia_mm":7.9,"boltN":3,"punch_confirmed":True},
    "MF_12x8": {"punch":"B6","boltA_mm":114.3,"boltB_mm":134.9,"boltDia_mm":7.9,"boltN":3,"punch_confirmed":True},
    "MF_14x8": {"punch":"B7","boltA_mm":101.6,"boltB_mm":134.9,"boltDia_mm":7.9,"boltN":4,"punch_confirmed":True},
    "MF_16x8": {"punch":"B7","boltA_mm":114.3,"boltB_mm":134.9,"boltDia_mm":7.9,"boltN":4,"punch_confirmed":True},
    "MF_18x8": {"punch":"B7","boltA_mm":127.0,"boltB_mm":134.9,"boltDia_mm":7.9,"boltN":4,"punch_confirmed":True},
    "MF_24x10":{"punch":"B8","boltA_mm":127.0,"boltB_mm":134.9,"boltDia_mm":7.9,"boltN":5,"punch_confirmed":True},

    # ── Style HF (continuous, high front) — same B-series as MF per catalog ─
    # (catalog "Style LF & MF" header is generic to continuous-style buckets;
    #  HF uses the same family by bucket length)
    "HF_10x7": {"punch":"B6","boltA_mm":88.9, "boltB_mm":133.4,"boltDia_mm":7.9,"boltN":3,"punch_confirmed":True},
    "HF_12x7": {"punch":"B6","boltA_mm":114.3,"boltB_mm":134.9,"boltDia_mm":7.9,"boltN":3,"punch_confirmed":True},
    "HF_14x7": {"punch":"B7","boltA_mm":101.6,"boltB_mm":134.9,"boltDia_mm":7.9,"boltN":4,"punch_confirmed":True},
    "HF_14x8": {"punch":"B7","boltA_mm":101.6,"boltB_mm":134.9,"boltDia_mm":7.9,"boltN":4,"punch_confirmed":True},
    "HF_16x8": {"punch":"B7","boltA_mm":114.3,"boltB_mm":134.9,"boltDia_mm":7.9,"boltN":4,"punch_confirmed":True},
    "HF_18x8": {"punch":"B7","boltA_mm":127.0,"boltB_mm":134.9,"boltDia_mm":7.9,"boltN":4,"punch_confirmed":True},

    # ── Style SC — mounts BETWEEN TWO CHAIN STRANDS, not belt-punched ───────
    # Not published in industry-standard catalogs -- vendor confirmation required
    # "punch":"chain" signals attachment-to-chain, not belt B-pattern.
    # boltA/B here represent the two mounting-hole pin centres shown in the
    # H-151 SC diagram (estimated from drawing proportions, NOT a published
    # dimension table) — flag punch_confirmed False.
    "SC_12x8":  {"punch":"chain","boltA_mm":165.0,"boltB_mm":0,"boltDia_mm":12.7,"boltN":2,"punch_confirmed":False},
    "SC_14x8":  {"punch":"chain","boltA_mm":165.0,"boltB_mm":0,"boltDia_mm":12.7,"boltN":2,"punch_confirmed":False},
    "SC_16x8":  {"punch":"chain","boltA_mm":190.5,"boltB_mm":0,"boltDia_mm":12.7,"boltN":2,"punch_confirmed":False},
    "SC_18x8":  {"punch":"chain","boltA_mm":190.5,"boltB_mm":0,"boltDia_mm":12.7,"boltN":2,"punch_confirmed":False},
    "SC_20x8":  {"punch":"chain","boltA_mm":215.9,"boltB_mm":0,"boltDia_mm":12.7,"boltN":2,"punch_confirmed":False},
    "SC_20x12": {"punch":"chain","boltA_mm":279.4,"boltB_mm":0,"boltDia_mm":15.9,"boltN":2,"punch_confirmed":False},
    "SC_24x12": {"punch":"chain","boltA_mm":279.4,"boltB_mm":0,"boltDia_mm":15.9,"boltN":2,"punch_confirmed":False},
    "SC_30x12": {"punch":"chain","boltA_mm":330.2,"boltB_mm":0,"boltDia_mm":15.9,"boltN":2,"punch_confirmed":False},
}


def apply_punching_data(bucket_series: list) -> None:
    """
    Mutates BUCKET_SERIES in place, adding punching fields to each entry.
    Call once at module load, immediately after the BUCKET_SERIES list
    literal in calculations.py:

        BUCKET_SERIES = [ ... ]
        from .calculations_bucket_punching_patch import apply_punching_data
        apply_punching_data(BUCKET_SERIES)

    Or simply merge the BUCKET_PUNCHING dict keys directly into each
    BUCKET_SERIES dict literal by hand — either approach works, this
    function just avoids retyping 32 dict literals.
    """
    for b in bucket_series:
        p = BUCKET_PUNCHING.get(b["id"])
        if p:
            b.update(p)
        else:
            # Defensive fallback for any future entries not yet catalogued
            b.setdefault("punch", "B6")
            b.setdefault("boltA_mm", 114.3)
            b.setdefault("boltB_mm", 25.4)
            b.setdefault("boltDia_mm", 7.9)
            b.setdefault("boltN", 3)
            b.setdefault("punch_confirmed", False)