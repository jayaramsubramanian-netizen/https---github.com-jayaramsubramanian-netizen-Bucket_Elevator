"""
VECTRIX™ — Engineering Constants
CEMA No. 375-2017, ANSI/CEMA 550-2020, ASME B17.1, ISO 281

v1.1.0 — Audit Corrections & Material Property Groups
─────────────────────────────────────────────────────────────────────────────
1. FIXED    STEEL_ALLOWABLE_STRESS: 55 MPa → 42 MPa.
            55 MPa is the ASME B17.1 value for shafts WITHOUT a keyway.
            Bucket elevator head shafts always carry a keyway → 6000 psi
            = 41.4 MPa → 42 MPa is the correct default.
            STEEL_ALLOWABLE_NO_KEY = 55 MPa added for the no-keyway case.
            Consequence: shaft diameters computed with the old 55 MPa default
            were 10–15 % undersized for keyed shafts.

2. FIXED    Startup factor split.
            DEFAULT_STARTUP_FACTOR = 2.0 covered belt elevators correctly
            but chain elevators require 2.0–2.5 (CEMA 375 §4).
            Added DEFAULT_STARTUP_FACTOR_BELT = 2.0
                  DEFAULT_STARTUP_FACTOR_CHAIN = 2.5
            DEFAULT_STARTUP_FACTOR kept as backward-compat alias → BELT value.

3. FIXED    Belt weight: BELT_PIW_DEFAULT = 1.5 kg/m² → BELT_WEIGHT_DEFAULT = 8.0.
            1.5 kg/m² is 5–10× below real elevator belt weights (4–20 kg/m²)
            and propagates into T2, shaft loads, bearing loads, startup inertia.
            BELT_PIW_DEFAULT retained as deprecated alias → BELT_WEIGHT_DEFAULT.
            BELT_WEIGHTS table added for common EP and ST constructions.

4. NEW      SHAFT_MATERIALS dict — property groups for A36, 1045 HR, 1045 CD,
            4140 Q&T.  Allowable shear stresses derived from the ASME B17.1
            effective safety factor (FS = 3.43 back-calculated from A36 ASME
            empirical values) applied to Ssy = 0.577 × Sy for each grade.
            Will migrate to shaft_materials.py; dict format is the target schema.

5. NEW      BUCKET_MATERIALS stub — mild steel, AR400, AR500, polymer.
            Allowable bending stress and abrasion class bounds per grade.
            Will migrate to bucket_materials.py.
            The volume × 1.5 bucket weight proxy (flagged as largest remaining
            error source in the audit) must be replaced by actual catalogue
            weights in BUCKET_SERIES entries in calculations.py.

6. FLAGGED  LEQ_DEFAULT and CEFF_BELT / CEFF_CHAIN are provisional.
            LEQ depends on bucket style, spacing, and boot geometry — it is
            not a universal constant.  CEFF lumps five distinct loss mechanisms
            into one number.  Both will migrate once bucket_database.py and
            the loss decomposition model exist.
─────────────────────────────────────────────────────────────────────────────
"""

# ── Gravity ───────────────────────────────────────────────────────────────────

GRAVITY = 9.81   # m/s²


# ── CEMA 375 §4 — Service and startup factors ─────────────────────────────────

DEFAULT_SERVICE_FACTOR       = 1.25   # CEMA: 1.15–1.25 belt
DEFAULT_SERVICE_FACTOR_CHAIN = 1.50   # CEMA: 1.40–1.60 chain

# Audit fix #2 — split into belt / chain
DEFAULT_STARTUP_FACTOR_BELT  = 2.0    # CEMA 375 §4: 1.5–2.0 range, belt type
DEFAULT_STARTUP_FACTOR_CHAIN = 2.5    # CEMA 375 §4: 2.0–2.5 range, chain type

# Backward-compatible alias (resolves to belt; pass explicitly for chain)
DEFAULT_STARTUP_FACTOR = DEFAULT_STARTUP_FACTOR_BELT


# ── Shaft allowable stresses — ASME B17.1 / CEMA 375 §4 ─────────────────────
#
# ASME B17.1 empirical values (conservative, widely accepted for power
# transmission shafts in industrial machinery):
#   Without keyway: τ_allow = 8 000 psi = 55.2 MPa
#   With keyway:    τ_allow = 6 000 psi = 41.4 MPa → rounded to 42 MPa
#
# Implied safety factor from A36 (Sy = 250 MPa):
#   Ssy = 0.577 × 250 = 144 MPa
#   FS  = 144 / 42    = 3.43   (with keyway)
#
# This FS = 3.43 is then applied to Ssy of higher-grade materials
# in SHAFT_MATERIALS below, giving consistent allowable scaling across grades.

STEEL_ALLOWABLE_STRESS  = 42e6    # Pa — A36 with keyway   (ASME B17.1: 6 000 psi)
STEEL_ALLOWABLE_NO_KEY  = 55e6    # Pa — A36 without keyway (ASME B17.1: 8 000 psi)


# ── Shaft material property groups ────────────────────────────────────────────
#
# Schema target for the future shaft_materials.py module.
# Each entry contains material constants needed by StructuralStressEngine:
#   Sy, Su, E               — yield, ultimate, modulus [Pa]
#   tau_allow_key_Pa        — τ_allow with keyway    [Pa]
#   tau_allow_no_key_Pa     — τ_allow without keyway [Pa]
#   density_kgm3            — for self-weight and inertia calculations
#
# Allowable shear stress derivation for each grade:
#   Ssy = 0.577 × Sy
#   τ_allow_key = Ssy / 3.43      (ASME B17.1 A36 keyway FS applied consistently)
#   τ_allow_no_key ≈ 1.30 × τ_allow_key   (ASME ratio: 8000/6000 = 1.33)

SHAFT_MATERIALS: dict[str, dict] = {

    "A36": {
        "name":                "ASTM A36 Mild Steel",
        "Sy_Pa":               250e6,
        "Su_Pa":               400e6,
        "E_Pa":                200e9,
        "tau_allow_key_Pa":    42e6,       # 6 000 psi — ASME B17.1 keyed default
        "tau_allow_no_key_Pa": 55e6,       # 8 000 psi — ASME B17.1 plain shaft
        "density_kgm3":        7850,
        "note": "CEMA 375 §4 default shaft material for most bucket elevators.",
    },

    "1045_HR": {
        "name":                "AISI/SAE 1045 Hot Rolled",
        "Sy_Pa":               310e6,
        "Su_Pa":               565e6,
        "E_Pa":                200e9,
        "tau_allow_key_Pa":    52e6,       # Ssy=179 / 3.43 ≈ 52 MPa
        "tau_allow_no_key_Pa": 68e6,       # 52 × 1.30
        "density_kgm3":        7850,
        "note": "Step-up from A36 for higher-capacity or impact-service elevators.",
    },

    "1045_CD": {
        "name":                "AISI/SAE 1045 Cold Drawn",
        "Sy_Pa":               415e6,
        "Su_Pa":               565e6,
        "E_Pa":                200e9,
        "tau_allow_key_Pa":    70e6,       # Ssy=240 / 3.43 ≈ 70 MPa
        "tau_allow_no_key_Pa": 91e6,       # 70 × 1.30
        "density_kgm3":        7850,
        "note": "Preferred for precision-machined shafts; tighter tolerance than HR.",
    },

    "4140_QT": {
        "name":                "AISI/SAE 4140 Quenched & Tempered (HT)",
        "Sy_Pa":               655e6,
        "Su_Pa":               1020e6,
        "E_Pa":                200e9,
        "tau_allow_key_Pa":    110e6,      # Ssy=378 / 3.43 ≈ 110 MPa
        "tau_allow_no_key_Pa": 143e6,      # 110 × 1.30
        "density_kgm3":        7850,
        "note": "Heavy-duty, high-impact, or corrosive / abrasive service.",
    },
}

# Backward-compat flat constants for StructuralStressEngine (A36 defaults)
SHAFT_E_PA  = SHAFT_MATERIALS["A36"]["E_Pa"]
SHAFT_Sy_PA = SHAFT_MATERIALS["A36"]["Sy_Pa"]
SHAFT_Su_PA = SHAFT_MATERIALS["A36"]["Su_Pa"]

# Additional shaft fatigue modifiers (ASME-Shigley, used by future fatigue module)
SHAFT_Ka = 0.80    # surface factor — machined finish
SHAFT_Kc = 0.897   # reliability factor — 99 %
SHAFT_Kd = 1.00    # temperature factor — ≤ 150 °C


# ── CEMA Pulley Standard ──────────────────────────────────────────────────────

CEMA_MAX_SHAFT_SLOPE = 0.0015   # rad (in/in) — max slope at bushing per CEMA Pulley Std


# ── Belt weight (CEMA 375 §4 — T2 calculation) ───────────────────────────────
#
# Audit fix #3: BELT_PIW_DEFAULT = 1.5 kg/m² → 1.5 is unrealistic.
# Actual elevator EP belt range: 4–20 kg/m² depending on construction.
# Using 1.5 underestimates T2, shaft bending, bearing load, and startup
# inertia by a factor of 5–10 for common belt constructions.
#
# BELT_WEIGHT_DEFAULT = 8.0 kg/m² — representative of EP400/EP500 elevator belt.
# BELT_PIW_DEFAULT kept as deprecated alias to avoid breaking existing callers.

BELT_WEIGHT_DEFAULT = 8.0    # kg/m² — default; replace with actual spec from BELT_WEIGHTS
BELT_PIW_DEFAULT    = BELT_WEIGHT_DEFAULT     # DEPRECATED — use BELT_WEIGHT_DEFAULT

# Belt weight reference table
# Schema target for belt_database.py.
# Source: Bridgestone, Fenner, ContiTech manufacturer data (ranges — use midpoint).
# weight_kgm2  : linear density of the belt per unit width and length [kg/m²]
# piw_kNm      : rated belt strength [kN/m width] — basis for tension rating
# min_pulley_mm: minimum head/boot pulley diameter [mm] per belt standard

BELT_WEIGHTS: dict[str, dict] = {
    "EP315_3": {"weight_kgm2": 5.5,  "piw_kNm": 315,  "plies": 3, "min_pulley_mm": 250},
    "EP400_3": {"weight_kgm2": 6.5,  "piw_kNm": 400,  "plies": 3, "min_pulley_mm": 315},
    "EP400_4": {"weight_kgm2": 7.5,  "piw_kNm": 400,  "plies": 4, "min_pulley_mm": 315},
    "EP500_4": {"weight_kgm2": 8.5,  "piw_kNm": 500,  "plies": 4, "min_pulley_mm": 400},
    "EP630_4": {"weight_kgm2": 10.0, "piw_kNm": 630,  "plies": 4, "min_pulley_mm": 500},
    "EP630_5": {"weight_kgm2": 11.5, "piw_kNm": 630,  "plies": 5, "min_pulley_mm": 500},
    "EP800_5": {"weight_kgm2": 13.0, "piw_kNm": 800,  "plies": 5, "min_pulley_mm": 630},
    "EP1000_5":{"weight_kgm2": 16.0, "piw_kNm": 1000, "plies": 5, "min_pulley_mm": 800},
    "ST1000":  {"weight_kgm2": 17.0, "piw_kNm": 1000, "plies": 1, "min_pulley_mm": 630,
                "note": "Steel cord"},
    "ST2000":  {"weight_kgm2": 24.0, "piw_kNm": 2000, "plies": 1, "min_pulley_mm": 800,
                "note": "Steel cord"},
    "ST3150":  {"weight_kgm2": 33.0, "piw_kNm": 3150, "plies": 1, "min_pulley_mm": 1000,
                "note": "Steel cord — heavy mining/cement"},
}


# ── Bucket materials ──────────────────────────────────────────────────────────
#
# Schema target for bucket_materials.py.
# allowable_bending_Pa: σ_allow for plate-bending thickness calculation in
#                       StructuralStressEngine.bucket_thickness().
# abrasion_class_max  : highest abrasion class this material is recommended for
#                       (CEMA 375 §7 Table 7-x classification: 1=light, 4=very heavy).
#
# ⚠ CRITICAL NOTE (audit "Hidden Problem"):
# The remaining largest source of error in the engine is bucket weight
# estimated from volume × 1.5 kg/L.  A 10 L bucket weighs 4–12 kg
# depending on gauge, style, and lip weldment.  Each entry in BUCKET_SERIES
# (calculations.py) must carry an actual catalogue bucket_mass_kg field.
# This table does not fix that; it fixes the bucket MATERIAL properties used
# in the plate-bending thickness model.

BUCKET_MATERIALS: dict[str, dict] = {

    "Mild_Steel_A36": {
        "name":                 "Mild Steel (ASTM A36 / equivalent)",
        "Sy_Pa":                250e6,
        "Su_Pa":                400e6,
        "hardness_HB":          120,
        "density_kgm3":         7850,
        "allowable_bending_Pa": 140e6,     # 0.56 × Sy — CEMA §7 plate bending
        "abrasion_class_max":   2,
        "note": "Standard; avoid for abrasive service (Class 3+).",
    },

    "Mild_Steel_HR": {
        "name":                 "Hot-Rolled Mild Steel (generic)",
        "Sy_Pa":                230e6,
        "Su_Pa":                380e6,
        "hardness_HB":          110,
        "density_kgm3":         7850,
        "allowable_bending_Pa": 130e6,
        "abrasion_class_max":   2,
        "note": "Economy buckets; Class 1–2 materials only.",
    },

    "AR400": {
        "name":                 "Abrasion-Resistant Steel AR400",
        "Sy_Pa":                1100e6,
        "Su_Pa":                1380e6,
        "hardness_HB":          400,
        "density_kgm3":         7850,
        "allowable_bending_Pa": 340e6,     # Limited by impact / notch sensitivity
        "abrasion_class_max":   4,
        "note": "Clinker, limestone, ore, quarried rock.  Verify weldability.",
    },

    "AR500": {
        "name":                 "Abrasion-Resistant Steel AR500",
        "Sy_Pa":                1300e6,
        "Su_Pa":                1560e6,
        "hardness_HB":          500,
        "density_kgm3":         7850,
        "allowable_bending_Pa": 400e6,
        "abrasion_class_max":   4,
        "note": "Extreme abrasion; limited weldability — preheat required.",
    },

    "SS316L": {
        "name":                 "Stainless Steel 316L",
        "Sy_Pa":                170e6,
        "Su_Pa":                485e6,
        "hardness_HB":          149,
        "density_kgm3":         8000,
        "allowable_bending_Pa": 95e6,
        "abrasion_class_max":   1,
        "note": "Food, pharma, chemical service.  Low abrasion resistance.",
    },

    "UHMW_PE": {
        "name":                 "Ultra-High Molecular Weight Polyethylene",
        "Sy_Pa":                20e6,
        "Su_Pa":                40e6,
        "hardness_HB":          None,
        "density_kgm3":         950,
        "allowable_bending_Pa": 10e6,
        "abrasion_class_max":   1,
        "note": "Grain, seed, food processing.  Very light; check centrifugal loading.",
    },
}


# ── Bucket steel density (legacy — see note) ──────────────────────────────────
#
# DEPRECATED for thickness and self-weight calculations.
# Previously used as: bucket_mass ≈ bucket_volume_L × 1.5 kg
# This proxy is unreliable (4–12 kg per 10 L bucket depending on gauge).
# Use actual catalogue bucket_mass_kg from BUCKET_SERIES entries instead.
# Retained as a physics reference constant (not for mass estimation).

BUCKET_STEEL_DENSITY = 7850   # kg/m³ — steel density reference only


# ── CEMA 375 §4 — Power method constants (provisional) ───────────────────────
#
# LEQ_DEFAULT: Length Equivalency factor for the CEMA power method.
# This is NOT a universal constant — it depends on:
#   • Bucket style (AA, CC, continuous, etc.)
#   • Bucket spacing
#   • Loading method (centrifugal, gravity, boot geometry)
# Currently a placeholder; will migrate to BUCKET_SERIES entries in
# calculations.py or a dedicated bucket_database.py.

LEQ_DEFAULT    = 7    # centrifugal spaced-bucket (provisional)
LEQ_CONTINUOUS = 4    # continuous bucket (provisional)

# CEFF: Drive efficiency correction factor (CEMA 375 §4 power method).
# This single factor lumps five distinct loss mechanisms:
#   1. Rolling element bearing losses
#   2. Belt flexure losses around pulleys
#   3. Material loading / digging losses (boot section)
#   4. Discharge chute impact losses
#   5. Gearbox / coupling mechanical losses
#
# Future decomposition (flagged in audit — not yet implemented):
#   P_total = P_lift + P_digging + P_bearing + P_flexure + P_chute
#
# Until that model exists, CEFF_BELT = 1.15 and CEFF_CHAIN = 1.25 are
# reasonable preliminary-design estimates for their respective drive types.

CEFF_BELT  = 1.15    # belt + shaft-mount gearbox (provisional)
CEFF_CHAIN = 1.25    # chain + sprocket (provisional)


# ── Air and environment ───────────────────────────────────────────────────────

AIR_DENSITY = 1.225   # kg/m³ — sea level, 15 °C (ISO 2533)